"""Long Detail history reuse and real pane geometry without stale write context."""

import runpy
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QWidget

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.presentation_settings import MemoryPresentationSettings


@dataclass
class Clock:
    instant: datetime = datetime(2026, 11, 12, 12, tzinfo=UTC)

    def now(self):
        return self.instant


@pytest.fixture(params=[False, True], ids=["binary", "numeric"])
def long_detail(request, qtbot, tmp_path):
    numeric = request.param
    path = tmp_path / "responsive.sqlite3"
    database = Database.open(path)
    clock = Clock()
    seed = runpy.run_path(str(Path(__file__).parents[1] / "tools/run_visual_review.py"))
    seed["_seed_adaptive_history"](
        database, now=clock.now(), numeric=numeric, resolved=False
    )
    operations = PredictionOperations(database, clock, UTC)
    identifier = (
        operations.journal.query(JournalRequest()).rows[0].prediction.prediction_id
    )
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(window)
    window.resize(1100, 850)
    window.show()
    window._open_prediction(identifier)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    qtbot.wait(30)
    yield window, screen, operations, clock, path, numeric
    screen.workspace.clear_editor()
    window.creation_task.reset()
    window.close()
    database.close()


def widgets(screen):
    return {id(row[2]) for row in screen.timeline_rows.rows}


def test_order_and_task_open_reuse_rows_with_fresh_reads(
    long_detail, qtbot, monkeypatch
):
    _window, screen, operations, _clock, _path, numeric = long_detail
    monkeypatch.setattr(
        "reckonsolve.ui.detail_workspace.animations_enabled", lambda _: False
    )
    rows = widgets(screen)
    assert len(rows) > 50
    calls = []
    name = "list_numeric_timeline" if numeric else "list_timeline"
    original = getattr(operations, name)

    def read(identifier):
        calls.append(identifier)
        return original(identifier)

    monkeypatch.setattr(operations, name, read)
    screen.timeline_order.setCurrentIndex(1)
    qtbot.wait(20)
    assert not calls
    assert widgets(screen) == rows
    earliest = min(screen.timeline_rows.rows, key=lambda row: (row[0], row[1]))[2]
    assert screen.timeline_rows.layout.itemAt(0).widget() is earliest
    before = operations.get_prediction_for_navigation(screen.prediction_id)
    for action in (
        screen.open_resolve_prediction,
        screen.open_forecast_review,
        screen.open_revise_forecast,
    ):
        previous_reads = len(calls)
        action()
        assert screen.workspace.editor is not None
        assert len(calls) > previous_reads
        assert widgets(screen) == rows
        screen.workspace.clear_editor()
    assert operations.get_prediction_for_navigation(screen.prediction_id) == before


def test_external_append_correction_and_review_only_replace_affected_rows(
    long_detail, qtbot, monkeypatch
):
    _window, screen, _operations, clock, path, numeric = long_detail
    monkeypatch.setattr(
        "reckonsolve.ui.detail_workspace.animations_enabled", lambda _: False
    )
    before = widgets(screen)
    with closing(Database.open(path)) as other:
        external = PredictionOperations(other, clock, UTC)
        current = external.get_prediction_for_navigation(screen.prediction_id)
        clock.instant += timedelta(hours=1)
        append = (
            external.add_numeric_journal_entry
            if numeric
            else external.add_journal_entry
        )
        entry = append(
            screen.prediction_id,
            "A new entry from another connection.",
            expected_revision_id=current.current_revision.revision_id
            if numeric
            else current.current_revision_id,
            expected_metadata_version=current.metadata_version,
        )
        screen.open_forecast_review()
        assert widgets(screen) > before
        assert any(
            "another connection" in label.text()
            for label in screen.findChildren(QLabel)
        )
        # Saving a Review appends one row instead of replacing the old history.
        after_append = widgets(screen)
        clock.instant += timedelta(hours=1)
        screen.workspace.editor.submit()
        assert screen.workspace.editor is None
        assert widgets(screen) > after_append
        assert len(widgets(screen)) == len(after_append) + 1
        before_correction = widgets(screen)
        clock.instant += timedelta(hours=1)
        correct = (
            external.correct_numeric_journal_entry
            if numeric
            else external.correct_journal_entry
        )
        correct(
            screen.prediction_id,
            entry.entry_id,
            "Corrected evidence from the independent connection.",
            expected_correction_id=None,
        )
        screen.refresh()
        after_correction = widgets(screen)
        assert len(after_correction) == len(before_correction)
        assert len(before_correction - after_correction) == 1
        assert len(after_correction - before_correction) == 1
        assert any(
            "Corrected evidence" in label.text()
            for label in screen.findChildren(QLabel)
        )
        screen.show_prediction(None)
        assert not screen.timeline_rows.rows
        assert screen.timeline_rows.snapshot is None


def test_bidirectional_motion_has_intermediate_geometry_and_restores_wrapping(
    long_detail, qtbot, monkeypatch
):
    _window, screen, operations, _clock, _path, numeric = long_detail
    monkeypatch.setattr(
        "reckonsolve.ui.detail_workspace.animations_enabled", lambda _: True
    )
    workspace = screen.workspace
    before = operations.get_prediction_for_navigation(screen.prediction_id)
    screen.open_revise_forecast()
    editor = workspace.editor
    field = editor.quantile_input.inputs[50] if numeric else editor.probability_input
    field.setValue(73) if not numeric else field.setText("24")
    original_text = field.text()
    for target, tab in ((400, 1), (600, 0), (400, 1)):
        workspace.tabs.setCurrentIndex(tab)
        workspace._transition.pause()
        widths = []
        for moment in (40, 85, 135):
            workspace._transition.setCurrentTime(moment)
            qtbot.wait(1)
            widths.append(workspace.timeline_column.width())
            assert not workspace.timeline.widgetResizable()
            assert (
                workspace.timeline.horizontalScrollBarPolicy()
                == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        assert len(set(widths)) == 3
        assert widths == sorted(widths, reverse=target == 400)
        workspace._transition.resume()
        qtbot.waitUntil(
            lambda: workspace._transition.state() == QAbstractAnimation.State.Stopped
        )
        qtbot.wait(10)
        assert workspace._proportion == target
        assert workspace.timeline.widgetResizable()
        assert (
            workspace.timeline.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert workspace.timeline.horizontalScrollBar().maximum() == 0
        assert field.text() == original_text
    assert operations.get_prediction_for_navigation(screen.prediction_id) == before
    # Rapid direction changes finish with live controls and normal scroll policy.
    workspace.tabs.setCurrentIndex(0)
    workspace.tabs.setCurrentIndex(1)
    qtbot.waitUntil(
        lambda: workspace._transition.state() == QAbstractAnimation.State.Stopped
    )
    assert workspace.timeline.widgetResizable()
    assert workspace._proportion == 400
    workspace.clear_editor()


def test_reduced_motion_switches_directly_without_freezing_history(
    long_detail, monkeypatch
):
    _window, screen, _operations, _clock, _path, _numeric = long_detail
    monkeypatch.setattr(
        "reckonsolve.ui.detail_workspace.animations_enabled", lambda _: False
    )
    screen.open_resolve_prediction()
    workspace = screen.workspace
    assert workspace._proportion == 400
    assert workspace._transition.state() == QAbstractAnimation.State.Stopped
    assert workspace.timeline.widgetResizable()
    workspace.tabs.setCurrentIndex(0)
    assert workspace._proportion == 600
    assert workspace.timeline.widgetResizable()


def test_retained_rows_reset_ordinary_disclosures_and_repeat_exact_search(
    long_detail, qtbot
):
    _window, screen, operations, _clock, _path, _numeric = long_detail
    rows = widgets(screen)
    hit = operations.search_predictions("birchbeacon", include_superseded=True).hits[0]
    document = hit.best_match.document
    screen.focus_search_match(document)
    target = screen.findChild(
        QWidget, f"journalEntryOriginalBody{document.source_record_id}"
    )
    history = screen.findChild(
        QGroupBox, f"journalEntryEditHistory{document.source_record_id}"
    )
    assert target.property("searchMatchEmphasis") and history.isChecked()
    screen.refresh()
    assert widgets(screen) == rows
    assert not target.property("searchMatchEmphasis")
    assert not history.isChecked()
    screen.focus_search_match(document)
    assert target.property("searchMatchEmphasis") and history.isChecked()
