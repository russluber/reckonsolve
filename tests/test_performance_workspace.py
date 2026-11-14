"""Current report scope, worker publication, source return and visit-local tools."""

from dataclasses import replace
from threading import Event

import pytest
from main_window_fakes import FakePredictionOperations
from performance_helpers import (
    adaptive_binary,
    adaptive_numeric,
    loaded,
    one_shot_numeric,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QToolButton

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.performance import PerformanceRequest, Section
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.domain.tags import TagLibraryItem
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.performance_screen import PerformanceScreen
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
)
from reckonsolve.ui.settings_screen import SettingsScreen
from reckonsolve.ui.tag_manager import TagChange, TagManagerDialog


@pytest.mark.parametrize("detour", ["Journal", "Settings"])
def test_session_scope_disclosures_position_and_reset_without_canonical_writes(
    qtbot, performance_archive, detour
):
    database, operations = performance_archive
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(window)
    window.resize(1200, 900)
    window.show()
    window.navigate_to("Performance")
    screen = window._analytics_screen
    report = loaded(screen, qtbot, refresh=False)
    tag = next(t for t in report.tags if t.display_name == "Detail review")
    screen.tag_filter.setCurrentIndex(screen.tag_filter.findData(tag.tag_id))
    loaded(screen, qtbot, refresh=False)
    adaptive_numeric(screen).unit_filter.setCurrentIndex(
        adaptive_numeric(screen).unit_filter.findData("items")
    )
    loaded(screen, qtbot, refresh=False)
    one_shot_numeric(screen).unit_filter.setCurrentIndex(
        one_shot_numeric(screen).unit_filter.findData("items")
    )
    loaded(screen, qtbot, refresh=False)
    adaptive_binary(screen).comparison.table_toggle.setChecked(True)
    adaptive_numeric(screen).supporting.disclosure_button.setChecked(True)
    qtbot.wait(50)
    bar = screen.scroll_area.verticalScrollBar()
    bar.setValue(500)
    qtbot.wait(30)
    assert screen.controls.y() == 0  # One pinned control strip, no duplicate.
    position = bar.value()
    request = screen.state.request
    before = database._require_connection().total_changes
    window.navigate_to(detour)
    if detour == "Settings":
        window._toolbar.performance.click()
    else:
        window.navigate_to("Performance")
    loaded(screen, qtbot, refresh=False)
    assert screen.state.request == request
    assert bar.value() == position
    assert adaptive_binary(screen).comparison.table_toggle.isChecked()
    assert adaptive_numeric(screen).supporting.disclosure_button.isChecked()
    screen.reset_button.click()
    loaded(screen, qtbot, refresh=False)
    assert screen.state.request == PerformanceRequest() and bar.value() == 0
    assert not adaptive_binary(screen).comparison.table_toggle.isChecked()
    assert not adaptive_numeric(screen).supporting.disclosure_button.isChecked()
    assert database._require_connection().total_changes == before
    # A new workspace never persists report scope or disclosures to settings.
    fresh = PerformanceScreen(operations)
    qtbot.addWidget(fresh)
    loaded(fresh, qtbot)
    assert fresh.state.request == PerformanceRequest()
    assert fresh.state.position == 0
    window.close()


def test_report_supporting_reveals_use_keyboard_chevrons_without_writes(
    qtbot, performance_archive
):
    database, operations = performance_archive
    screen = PerformanceScreen(operations)
    qtbot.addWidget(screen)
    screen.resize(1200, 900)
    screen.show()
    report = loaded(screen, qtbot)
    before = database._require_connection().total_changes
    controls = [
        control
        for section in screen.sections.values()
        for control in section.findChildren(QToolButton)
        if control.property("reckonsolveDisclosure") == "true" and control.isVisible()
    ]
    assert len(controls) == 6
    for control in controls:
        assert not control.isChecked()
        assert control.arrowType() is Qt.ArrowType.RightArrow
        screen.scroll_area.ensureWidgetVisible(control)
        control.setFocus()
        qtbot.keyClick(control, Qt.Key.Key_Space)
        assert control.isChecked()
        assert control.arrowType() is Qt.ArrowType.DownArrow
        assert control.parentWidget().disclosure_body.isVisible()
        qtbot.keyClick(control, Qt.Key.Key_Space)
        assert not control.parentWidget().disclosure_body.isVisible()
    assert screen.report == report
    assert database._require_connection().total_changes == before


def test_confirmed_merge_follows_target_and_verified_deletion_broadens(
    qtbot, performance_archive
):
    _, operations = performance_archive
    screen = PerformanceScreen(operations)
    qtbot.addWidget(screen)
    report = loaded(screen, qtbot)
    source = next(t for t in report.tags if t.display_name == "Detail review")
    target = next(t for t in report.tags if t.display_name == "Visual review")
    screen.tag_filter.setCurrentIndex(screen.tag_filter.findData(source.tag_id))
    loaded(screen, qtbot, refresh=False)
    operations.merge_tags(operations.preview_tag_merge((source.tag_id,), target.tag_id))
    screen.tag_changed(
        TagChange(
            "merge", (source.tag_id,), target.tag_id, "Merged.", target.display_name
        )
    )
    report = loaded(screen, qtbot)
    assert report.effective_tag_id == target.tag_id and not report.notice
    expected = operations.get_forecast_analytics(tag=target.display_name)
    assert report.sections[0].data == expected.trajectory_binary
    assert report.sections[1].data == expected.quantile_numeric
    operations.rename_tag(
        operations.preview_tag_rename(target.tag_id, "Renamed target")
    )
    report = loaded(screen, qtbot)
    assert report.effective_tag_id == target.tag_id
    assert screen.tag_filter.currentText() == "Renamed target"
    operations.delete_tag(operations.preview_tag_delete(target.tag_id))
    report = loaded(screen, qtbot)
    assert report.effective_tag_id is None and "deleted" in screen.message.text()


def test_section_retry_leaves_other_current_sections_usable(qtbot, performance_archive):
    _, operations = performance_archive
    initial = operations.performance.query(PerformanceRequest())
    failed = replace(
        initial,
        sections=tuple(
            replace(s, data=None, error="Identified calculation failure")
            if s.section is Section.ADAPTIVE_NUMERIC
            else s
            for s in initial.sections
        ),
    )
    started, release = Event(), Event()
    calls = []

    def query(request):
        calls.append(request)
        if len(calls) == 1:
            return failed
        started.set()
        assert release.wait(5)
        return initial

    screen = PerformanceScreen(operations, query=query)
    qtbot.addWidget(screen)
    loaded(screen, qtbot)
    numeric = adaptive_numeric(screen)
    assert numeric.results.isHidden() and not numeric.retry.isHidden()
    numeric.retry.click()
    try:
        qtbot.waitUntil(started.is_set)
        assert screen.loading and numeric.results.isHidden()
        assert not adaptive_binary(screen).results.isHidden()
        assert "other results are current" not in numeric.status.text()
    finally:
        release.set()
    loaded(screen, qtbot, refresh=False)
    assert not numeric.results.isHidden() and numeric.retry.isHidden()


def test_latest_worker_generation_only_and_confirmed_merge_expires_old_read(qtbot):
    operations = FakePredictionOperations()
    operations.tag_library = [
        TagLibraryItem(1, "Source", "source", 0),
        TagLibraryItem(2, "Target", "target", 0),
    ]
    reports = {
        i: operations.performance.query_independently(PerformanceRequest(i))
        for i in (1, 2)
    }
    started, release = Event(), Event()
    calls = []

    def query(request):
        calls.append(request.tag_id)
        if len(calls) == 1:
            started.set()
            assert release.wait(5)
        return reports[request.tag_id]

    screen = PerformanceScreen(operations, query=query)
    qtbot.addWidget(screen)
    screen.state.tag_id = 1
    screen.refresh()
    try:
        qtbot.waitUntil(started.is_set)
        screen.tag_changed(TagChange("merge", (1,), 2, "Merged.", "Target"))
        screen.refresh()
        assert all(s.results.isHidden() for s in screen.sections.values())
    finally:
        release.set()
    loaded(screen, qtbot, refresh=False)
    assert calls == [1, 2]
    assert screen.report.effective_tag_id == screen.state.tag_id == 2
    assert screen.tag_filter.currentText() == "Target"


def test_whole_failure_and_retry_preserve_useful_reading_position(
    qtbot, performance_archive
):
    _, operations = performance_archive
    current = operations.performance.query(PerformanceRequest())
    unavailable = False

    def query(request):
        if unavailable:
            raise ApplicationError("Report unavailable")
        return current

    screen = PerformanceScreen(operations, query=query)
    qtbot.addWidget(screen)
    screen.resize(1100, 700)
    screen.show()
    loaded(screen, qtbot)
    bar = screen.scroll_area.verticalScrollBar()
    bar.setValue(500)
    position = bar.value()
    unavailable = True
    screen.refresh()
    qtbot.waitUntil(lambda: not screen.loading)
    assert screen.report is None
    screen.leave()
    assert screen.state.position == position
    unavailable = False
    screen.retry_button.click()
    loaded(screen, qtbot, refresh=False)
    assert bar.value() == position


def test_missing_unit_and_failed_tag_read_retain_scope_and_clear_stale_data(
    qtbot, performance_archive, monkeypatch
):
    _, operations = performance_archive
    screen = PerformanceScreen(operations)
    qtbot.addWidget(screen)
    report = loaded(screen, qtbot)
    tag = next(t for t in report.tags if t.display_name == "Detail review")
    screen.state.tag_id = tag.tag_id
    screen.state.adaptive_unit = "missing exact unit"
    loaded(screen, qtbot)
    assert adaptive_numeric(screen).unit_filter.currentData() == "missing exact unit"
    assert "retained" in adaptive_numeric(screen).status.text()
    assert not adaptive_binary(screen).results.isHidden()
    request = screen.state.request

    def fail(request):
        raise ApplicationError("Tag library could not load")

    monkeypatch.setattr(operations.performance, "query_independently", fail)
    screen.refresh()
    qtbot.waitUntil(lambda: not screen.loading)
    assert screen.state.request == request
    assert screen.report is None and "deleted" not in screen.message.text()
    assert all(s.results.isHidden() for s in screen.sections.values())


def test_archive_refusal_is_global_instead_of_isolated_empty_result(qtbot, monkeypatch):
    operations = FakePredictionOperations()

    def fail(request):
        raise ForecastContractIntegrityError("Unsupported performance_archive identity")

    operations.performance.query_independently = fail
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args: QMessageBox.StandardButton.Ok
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Performance")
    qtbot.waitUntil(lambda: window._analytics_screen.refused)
    assert window._analytics_screen.report is None
    assert window.archive_blocked
    assert not window._toolbar.new.isEnabled()
    assert not window._toolbar.home.isEnabled()
    assert not window._screen_stack.isEnabled()


def test_settings_results_are_independent_persistent_selectable_and_visit_local(
    qtbot, monkeypatch, tmp_path
):
    operations = FakePredictionOperations()
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Settings")
    screen = window._settings_screen
    destinations = iter((str(tmp_path / "backup"), str(tmp_path / "export")))
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args: (next(destinations), "")
    )
    screen.backup_button.click()
    backup = screen.backup_tool.result.text()
    last_backup = screen.last_backup_label.text()
    operations.export_error = ApplicationError("Export unavailable")
    screen.export_button.click()
    failure = screen.export_tool.result.text()
    assert str(tmp_path / "export.zip") in failure
    screen.repair_search_button.click()
    assert "repaired" in screen.search_tool.result.text()
    assert screen.backup_tool.result.text() == backup
    assert screen.last_backup_label.text() == last_backup
    window.appearance.select(AppearanceMode.DARK)
    window.showMinimized()
    qtbot.wait(20)
    window.showNormal()
    assert screen.backup_tool.result.text() == backup
    assert screen.export_tool.result.text() == failure
    for tool in screen.tools:
        assert (
            tool.result.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    screen.export_button.click()
    assert screen.export_tool.result.text() == failure
    window.navigate_to("Journal")
    window.navigate_to("Settings")
    assert all(tool.result.isHidden() for tool in screen.tools)
    assert screen.last_backup_label.text() == last_backup
    window.close()


def test_failed_tag_operation_remains_beside_tool_without_committed_event(
    qtbot, monkeypatch
):
    operations = FakePredictionOperations()
    operations.tag_library = [TagLibraryItem(1, "Work", "work", 1)]
    screen = SettingsScreen(operations)
    qtbot.addWidget(screen)
    committed = []
    screen.tags_changed.connect(committed.append)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("Career", True))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Yes
    )

    def fail(preview):
        raise ApplicationError("Tag rename could not complete")

    def interact(dialog):
        dialog.table.selectRow(0)
        dialog._rename_selected()
        return 0

    monkeypatch.setattr(operations, "rename_tag", fail)
    monkeypatch.setattr(TagManagerDialog, "exec", interact)
    screen._manage_tags()
    assert screen.tag_tool.result.text() == "Tag rename could not complete"
    assert not committed
    assert operations.tag_library[0].display_name == "Work"


def test_initial_tag_archive_refusal_reaches_settings_global_boundary(qtbot):
    operations = FakePredictionOperations()
    operations.tag_library_error = ForecastContractIntegrityError(
        "Unsupported identity"
    )
    screen = SettingsScreen(operations)
    qtbot.addWidget(screen)
    with qtbot.waitSignal(screen.archive_refused):
        screen._manage_tags()
    assert screen.tag_tool.result.isHidden()
