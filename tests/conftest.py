"""Use real Windows font metrics when Qt's headless plugin has no font database."""

import os
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase


@pytest.fixture(scope="session")
def qapp(qapp):
    if qapp.platformName() == "offscreen" and not QFontDatabase.families():
        font_path = (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
        )
        if (
            not font_path.is_file()
            or QFontDatabase.addApplicationFont(str(font_path)) < 0
        ):
            pytest.fail(
                "Headless native UI checks require a real font, not missing-glyph boxes."
            )
        for name in ("seguisb.ttf", "segoeuib.ttf"):
            QFontDatabase.addApplicationFont(str(font_path.with_name(name)))
        qapp.setFont(QFont("Segoe UI", 9))
    return qapp


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown():
    """Test cleanup discards form inputs; exit-guard tests exercise their dialogs.

    pytest-qt closes widgets before fixture finalizers. An assertion failure in
    a creation test must not leave its cleanup waiting for a human modal answer.
    """
    from PySide6.QtWidgets import QApplication

    from reckonsolve.ui.detail_workspace import DetailWorkspace
    from reckonsolve.ui.main_window import MainWindow

    application = QApplication.instance()
    if application is not None:
        for widget in application.topLevelWidgets():
            if isinstance(widget, MainWindow):
                widget.creation_task.reset()
                for workspace in widget.findChildren(DetailWorkspace):
                    workspace.clear_editor()
    yield


@pytest.fixture
def performance_archive(tmp_path):
    """One reusable disposable four-cohort archive for report checks."""
    from performance_helpers import performance_database

    with performance_database(tmp_path) as archive:
        yield archive
