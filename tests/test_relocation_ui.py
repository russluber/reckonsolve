"""Settings consent, in-place failure and fresh relocated runtime composition."""

import os
import stat

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QFileDialog

from reckonsolve import app
from reckonsolve.app import create_runtime
from reckonsolve.application.relocation import RelocationService
from reckonsolve.cli import create_runtime as create_cli_runtime
from reckonsolve.data.relocation_snapshot import snapshot
from reckonsolve.identity import DEVELOPMENT_APPLICATION
from reckonsolve.ui.location_controls import MoveReviewDialog
from reckonsolve.ui.presentation_settings import AppearanceMode
from reckonsolve.ui.workspace_state import Route

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Native Windows relocation")


@pytest.fixture
def managed(qtbot, tmp_path):
    root = tmp_path / DEVELOPMENT_APPLICATION.application_name
    runtime = create_runtime(identity=DEVELOPMENT_APPLICATION, bootstrap_directory=root)
    qtbot.addWidget(runtime.window)
    runtime.window.show()
    runtime.window.navigate_to("Settings")
    folder = tmp_path / "Moved journal"
    folder.mkdir()
    yield runtime, folder
    runtime.close()
    for file in tmp_path.rglob("*"):
        if file.is_file() and file.stat().st_file_attributes & 1:
            assert file.resolve().is_relative_to(tmp_path.resolve())
            file.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_cancel_folder_or_review_has_no_move_artifacts(managed, monkeypatch):
    runtime, folder = managed
    controls = runtime.window._settings_screen.location_controls
    before = snapshot(runtime.database.path)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: "")
    controls.choose.click()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(folder))
    monkeypatch.setattr(
        MoveReviewDialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    controls.choose.click()
    assert runtime.database.is_open and not runtime.restart_requested
    assert not list(folder.iterdir())
    assert snapshot(runtime.database.path) == before
    assert not runtime.location.store.move_file.exists()


def test_busy_move_reconnects_current_operations_and_stays_in_settings(
    managed, monkeypatch
):
    runtime, folder = managed
    other = create_cli_runtime(
        identity=DEVELOPMENT_APPLICATION,
        bootstrap_directory=runtime.location.store.root,
    )
    controls = runtime.window._settings_screen.location_controls
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(folder))
    monkeypatch.setattr(
        MoveReviewDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    try:
        controls.choose.click()
        assert "Close other" in controls.result.text()
        assert runtime.database.is_open and runtime.window.isEnabled()
        assert not runtime.storage_blocked and not runtime.restart_requested
        assert runtime.window.workspace.current.route is Route.SETTINGS
        assert (
            runtime.window.operations.get_data_management_status().database_path
            == runtime.database.path
        )
    finally:
        other.close()


def test_move_reopens_same_identity_in_fresh_journal_with_fixed_preferences(
    managed, qtbot
):
    runtime, folder = managed
    window = runtime.window
    window.appearance.select(AppearanceMode.DARK)
    window._analytics_screen.state.adaptive_unit = "retained only before restart"
    source = runtime.database.path
    expected = snapshot(source)
    service = RelocationService(runtime.location.store)
    runtime.relocate(service.preview(folder))
    assert runtime.restart_requested and not runtime.database.is_open
    assert not window.isVisible()
    reopened = create_runtime(
        identity=DEVELOPMENT_APPLICATION,
        bootstrap_directory=runtime.location.store.root,
    )
    qtbot.addWidget(reopened.window)
    try:
        assert reopened.database.path == folder / source.name
        assert snapshot(reopened.database.path) == expected
        assert reopened.window.workspace.current.route is Route.JOURNAL
        assert reopened.window.appearance.dark
        assert reopened.window._analytics_screen.state.adaptive_unit is None
        assert reopened.location.presentation_path.parent == runtime.location.store.root
        cli = create_cli_runtime(
            identity=DEVELOPMENT_APPLICATION,
            bootstrap_directory=runtime.location.store.root,
        )
        try:
            assert cli.database.path == reopened.database.path
        finally:
            cli.close()
    finally:
        reopened.close()


def test_failure_after_protection_blocks_old_runtime_and_requires_recovery(
    managed, monkeypatch
):
    runtime, folder = managed
    review = RelocationService(runtime.location.store).preview(folder)
    original = RelocationService._complete_locked

    def fail(self, state):
        raise OSError("Could not save the new location")

    monkeypatch.setattr(RelocationService, "_complete_locked", fail)
    with pytest.raises(Exception, match="recovery"):
        runtime.relocate(review)
    assert runtime.storage_blocked and runtime.window.archive_blocked
    assert not runtime.database.is_open
    monkeypatch.setattr(RelocationService, "_complete_locked", original)
    RelocationService(runtime.location.store).recover("finish")


def test_run_automatically_reconstructs_window_after_move(
    qapp, qtbot, tmp_path, monkeypatch
):
    root = tmp_path / DEVELOPMENT_APPLICATION.application_name
    destination = tmp_path / "Destination"
    destination.mkdir()
    original = app.create_runtime
    windows = []
    old_quit = qapp.quitOnLastWindowClosed()
    qapp.setQuitOnLastWindowClosed(True)
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda: qapp.exit(99))
    watchdog.start(15000)

    def compose(**kwargs):
        runtime = original(**kwargs)
        windows.append(runtime)
        # app.run owns/deletes these windows during its real restart loop.
        if len(windows) == 1:

            def move():
                runtime.window.navigate_to("Settings")
                service = RelocationService(runtime.location.store)
                runtime.relocate(service.preview(destination))

            QTimer.singleShot(0, move)
        else:
            QTimer.singleShot(0, runtime.window.close)
        return runtime

    monkeypatch.setattr(app, "create_runtime", compose)
    try:
        assert (
            app.run([], identity=DEVELOPMENT_APPLICATION, bootstrap_directory=root) == 0
        )
        assert len(windows) == 2
        assert windows[1].database.path == destination / "reckonsolve.sqlite3"
        assert windows[1].window.workspace.current.route is Route.JOURNAL
    finally:
        watchdog.stop()
        qapp.setQuitOnLastWindowClosed(old_quit)
        for file in tmp_path.rglob("*"):
            if file.is_file() and file.stat().st_file_attributes & 1:
                file.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_integrated_review_profile_keeps_the_whole_workspace_in_disposable_bootstrap(
    qtbot, monkeypatch
):
    import runpy
    import sys
    from pathlib import Path

    from reckonsolve.app import create_runtime
    from reckonsolve.domain.journal import JournalRequest
    from reckonsolve.identity import DEVELOPMENT_APPLICATION

    tool = runpy.run_path(str(Path(__file__).parents[1] / "tools/run_visual_review.py"))
    seen = []

    def inspect_run(*, argv, identity, bootstrap_directory):
        assert identity == DEVELOPMENT_APPLICATION
        assert bootstrap_directory.name == identity.application_name
        assert (bootstrap_directory.parent / "New journal folder").is_dir()
        runtime = create_runtime(
            argv=argv, identity=identity, bootstrap_directory=bootstrap_directory
        )
        try:
            assert runtime.location.store.root == bootstrap_directory
            assert runtime.window._settings_screen.location_controls is not None
            page = runtime.window.operations.journal.query(JournalRequest())
            assert page.total == 41
            assert (
                len(
                    {
                        (
                            row.prediction.prediction_type,
                            row.prediction.forecast_contract.is_one_shot,
                        )
                        for row in page.rows
                    }
                )
                == 4
            )
            assert any("Long history" in row.prediction.question for row in page.rows)
            seen.append(bootstrap_directory.parent)
        finally:
            runtime.close()
        return 0

    tool["main"].__globals__["run"] = inspect_run
    monkeypatch.setattr(sys, "argv", ["run_visual_review.py", "integrated"])
    assert tool["main"]() == 0
    assert len(seen) == 1 and not seen[0].exists()
