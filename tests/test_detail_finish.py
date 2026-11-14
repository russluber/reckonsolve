"""Complete Detail reading, reflection and preserved-history journeys."""

import runpy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.domain.quantiles import NumericValueConstraint
from reckonsolve.ui.detail_workspace import DetailWorkspace
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
)


@dataclass
class Clock:
    instant: datetime = datetime(2026, 11, 12, 12, tzinfo=UTC)

    def now(self):
        return self.instant

    def advance(self):
        self.instant += timedelta(hours=1)


@pytest.fixture
def workspace(qtbot, tmp_path):
    database = Database.open(tmp_path / "finish.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(window)
    window.resize(1100, 850)
    window.show()
    yield window, operations, clock, database
    for pane in window.findChildren(DetailWorkspace):
        pane.clear_editor()
    window.creation_task.reset()
    window.close()
    database.close()


def create(operations, clock, numeric):
    if numeric:
        return operations.create_numeric_prediction(
            "How many items will the finished Detail retain?",
            "items",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=clock.now() + timedelta(days=10),
            resolution_criteria="Count the published items.",
        )
    return operations.create_prediction(
        "Will the finished Detail retain the recorded context?",
        65,
        forecast_deadline=clock.now() + timedelta(days=10),
        resolution_criteria="Use the published answer.",
    )


def context(prediction, numeric):
    return {
        "expected_revision_id": prediction.current_revision.revision_id
        if numeric
        else prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


def test_binary_journal_heading_does_not_absorb_timeline_height(workspace, qtbot):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, False)
    clock.advance()
    entry = operations.add_journal_entry(
        prediction.prediction_id,
        "The public notice gives a planned date, not a guaranteed opening.",
        **context(prediction, False),
    )
    window._open_prediction(prediction.prediction_id)
    screen = window._prediction_detail_screen
    for width in (1600, 760, 1200):
        window.resize(width, 1000)
        qtbot.wait(80)
        heading = screen.findChild(QLabel, f"journalEntryKind{entry.entry_id}")
        row = heading.parentWidget()
        assert row.height() <= row.layout().heightForWidth(row.width()) + 4
        body = screen.findChild(QLabel, f"journalEntryBody{entry.entry_id}")
        assert body.text() == entry.body


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("one_shot", [False, True])
def test_focused_widths_keep_native_window_geometry_and_detail_panes(
    workspace, qtbot, numeric, one_shot
):
    from test_one_shot_persistence import request

    window, operations, clock, _database = workspace
    prediction = (
        operations.one_shots.create(request(numeric, answered=False))
        if one_shot
        else create(operations, clock, numeric)
    )
    before = operations.get_prediction_for_navigation(prediction.prediction_id)
    for width in (1600, 900, 760):
        window.resize(width, 850)
        window.navigate_to("Journal")
        qtbot.waitUntil(lambda: not window._journal_screen.loading)
        qtbot.wait(40)
        content = window._workspace_content
        assert content.width() == min(window.width(), 1024)
        assert (
            abs(
                content.geometry().center().x()
                - window.centralWidget().rect().center().x()
            )
            <= 1
        )
        window._open_prediction(prediction.prediction_id)
        qtbot.wait(60)
        assert content.width() == min(window.width(), 1200)
        assert (
            abs(
                content.geometry().center().x()
                - window.centralWidget().rect().center().x()
            )
            <= 1
        )
        screen = (
            window._prediction_detail_host._one_shot_detail
            if one_shot
            else window._numeric_prediction_detail_screen
            if numeric
            else window._prediction_detail_screen
        )
        assert screen.workspace._proportion == 600
        for pane in (
            screen.workspace,
            screen.workspace.timeline,
            screen.workspace.overview,
        ):
            assert pane.horizontalScrollBar().maximum() == 0
    window.resize(1600, 850)
    window.navigate_to("Settings")
    qtbot.wait(50)
    assert window._workspace_content.width() == window.width()
    window.navigate_to("Journal")
    qtbot.wait(50)
    window._save_presentation_state()
    assert window._presentation_settings.state.normal_geometry[2] == 1600
    assert operations.get_prediction_for_navigation(prediction.prediction_id) == before


@pytest.mark.parametrize("status", ["open", "locked", "resolved", "invalid"])
@pytest.mark.parametrize("points", [9, 12])
def test_numeric_definition_stays_visible_below_criteria_without_duplicate_metadata(
    workspace, qtbot, qapp, status, points
):
    window, operations, clock, _database = workspace
    unit = "centimetres above reference level" if points == 12 else "items"
    precision = 2 if points == 12 else 0
    prediction = operations.create_numeric_prediction(
        "A readable Numeric definition",
        unit,
        precision,
        {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
        value_constraint=NumericValueConstraint.CONTINUOUS,
        forecast_deadline=clock.now() + timedelta(days=10),
        resolution_criteria=None
        if status == "resolved"
        else "Use the published measurement.",
        background="Supporting context stays in More Information."
        if points == 12
        else None,
    )
    clock.advance()
    if status == "locked":
        clock.instant += timedelta(days=11)
    elif status == "resolved":
        operations.resolve_numeric_prediction(
            prediction.prediction_id,
            1,
            use_recorded_time=True,
            **context(prediction, True),
        )
    elif status == "invalid":
        operations.invalidate_numeric_prediction(
            prediction.prediction_id,
            reason="The source was withdrawn.",
            **context(prediction, True),
        )
    before = operations.get_prediction_for_navigation(prediction.prediction_id)
    original_font = QFont(qapp.font())
    try:
        qapp.setFont(QFont("Segoe UI", points))
        window._open_prediction(prediction.prediction_id)
        screen = window._numeric_prediction_detail_screen
        for width in (1200, 760):
            window.resize(width, 850)
            qtbot.waitUntil(screen.workspace.timeline.widgetResizable)
            qtbot.wait(30)
            assert screen.unit.text() == unit
            assert screen.precision.text() == str(precision)
            assert screen.unit.isVisible() and screen.precision.isVisible()
            assert not screen.metadata_disclosure.disclosure_button.isChecked()
            assert not screen.metadata_panel.isAncestorOf(screen.unit)
            assert not screen.metadata_panel.isAncestorOf(screen.precision)
            assert screen.workspace.overview_body.isAncestorOf(
                screen.definition_summary
            )
            assert (
                screen.definition_summary.y()
                >= screen.resolution_criteria_section.geometry().bottom()
            )
            assert (
                screen.unit_row.mapTo(screen.definition_summary, QPoint()).x()
                < screen.precision_row.mapTo(screen.definition_summary, QPoint()).x()
            )
            assert screen.unit.height() >= screen.unit.heightForWidth(
                screen.unit.width()
            )
            assert screen.workspace.overview.horizontalScrollBar().maximum() == 0
        screen.metadata_disclosure.disclosure_button.setChecked(True)
        assert screen.metadata_empty.isVisible() == (points == 9)
        if points == 12:
            assert screen.background.isVisible()
        assert (
            operations.get_prediction_for_navigation(prediction.prediction_id) == before
        )
    finally:
        qapp.setFont(original_font)


@pytest.mark.parametrize("numeric", [False, True])
def test_more_information_does_not_call_unavailable_history_empty(
    workspace, qtbot, monkeypatch, numeric
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, numeric)

    def unavailable(_identifier):
        raise ApplicationError("History could not be read.")

    with monkeypatch.context() as patch:
        patch.setattr(operations, "list_definition_changes", unavailable)
        window._open_prediction(prediction.prediction_id)
        screen = (
            window._numeric_prediction_detail_screen
            if numeric
            else window._prediction_detail_screen
        )
        screen.metadata_disclosure.disclosure_button.setChecked(True)
        assert screen.metadata_empty.text() == "Definition history is unavailable."
        if numeric:
            assert screen.unit.isVisible()
    screen.refresh()
    qtbot.wait(20)
    assert screen.metadata_empty.text() == "No additional information recorded."


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("status", ["open", "resolved", "invalid"])
def test_adaptive_overview_reveals_use_compact_chevrons_and_keep_defaults(
    workspace, qtbot, numeric, status
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, numeric)
    clock.advance()
    if status == "invalid":
        operation = (
            operations.invalidate_numeric_prediction
            if numeric
            else operations.invalidate_prediction
        )
        operation(
            prediction.prediction_id,
            reason="An archival example",
            **context(prediction, numeric),
        )
    elif status == "resolved":
        operation = (
            operations.resolve_numeric_prediction
            if numeric
            else operations.resolve_prediction
        )
        operation(
            prediction.prediction_id,
            1 if numeric else BinaryOutcome.YES,
            use_recorded_time=True,
            **context(prediction, numeric),
        )
    before = operations.get_prediction_for_navigation(prediction.prediction_id)
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    history = screen.distribution_disclosure if numeric else screen.chart_disclosure
    has_history_toggle = status != "open" if numeric else status == "invalid"
    qtbot.wait(30)
    assert history.disclosure_button.isVisible() == has_history_toggle
    assert history.disclosure_body.isVisible() != has_history_toggle
    controls = [screen.metadata_disclosure]
    if has_history_toggle:
        controls.append(history)
    for mode in (AppearanceMode.LIGHT, AppearanceMode.DARK):
        window.appearance.select(mode)
        for control in controls:
            toggle = control.disclosure_button
            assert isinstance(toggle, QToolButton)
            assert not toggle.isChecked()
            screen.workspace.overview.ensureWidgetVisible(toggle)
            toggle.setFocus()
            qtbot.keyClick(toggle, Qt.Key.Key_Space)
            assert control.disclosure_body.isVisible()
            assert toggle.arrowType() is Qt.ArrowType.DownArrow
            qtbot.keyClick(toggle, Qt.Key.Key_Space)
            assert not control.disclosure_body.isVisible()
        window.resize(760, 520)
        qtbot.wait(30)
        assert screen.workspace.overview.horizontalScrollBar().maximum() == 0
    assert operations.get_prediction_for_navigation(prediction.prediction_id) == before


@pytest.mark.parametrize("one_shot", [False, True])
def test_journal_preview_spacing_and_shared_forecast_size(workspace, qtbot, one_shot):
    from test_one_shot_persistence import request

    from reckonsolve.ui.journal.rows import QuestionLabel
    from reckonsolve.ui.visual_system import TextRole, apply_text_role

    window, operations, clock, _database = workspace
    if one_shot:
        binary = operations.one_shots.create(request(False))
        numeric = operations.one_shots.create(request(True))
    else:
        binary = create(operations, clock, False)
        numeric = create(operations, clock, True)
    originals = operations.journal.query(JournalRequest())
    window.navigate_to("Journal")
    journal = window._journal_screen
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    binary_card = next(
        c for c in journal.cards if c.prediction_id == binary.prediction_id
    )
    numeric_card = next(
        c for c in journal.cards if c.prediction_id == numeric.prediction_id
    )
    binary_value = next(
        label
        for label in binary_card.findChildren(QLabel)
        if label.text().endswith("% Yes")
    )
    preview = numeric_card.findChild(
        QWidget, f"journalNumericForecast{numeric.prediction_id}"
    )
    numbers = [
        preview.findChild(QLabel, f"journalPercentile{numeric.prediction_id}_{level}")
        for level in (5, 25, 50, 75, 95)
    ]
    assert "50th" in {label.text() for label in preview.findChildren(QLabel)}
    assert not any("Median" in label.text() for label in preview.findChildren(QLabel))
    detail_forecast = QLabel(window)
    apply_text_role(detail_forecast, TextRole.FORECAST)
    assert all(number.font() == binary_value.font() for number in numbers)
    assert binary_value.font().pointSizeF() < detail_forecast.font().pointSizeF()
    assert (
        binary_value.font().pointSizeF()
        < binary_card.findChild(QuestionLabel).font().pointSizeF()
    )
    spans = []
    for width in (1600, 1100, 760):
        window.resize(width, 850)
        qtbot.wait(60)
        cells = [
            QRect(number.mapTo(preview, QPoint()), number.size()) for number in numbers
        ]
        gaps = [right.x() - left.right() - 1 for left, right in pairwise(cells)]
        assert len(set(gaps)) == 1 and gaps[0] >= 12
        assert cells[-1].right() < numeric_card.width() * 0.75
        assert journal.scroll.horizontalScrollBar().maximum() == 0
        spans.append(cells[-1].right() - cells[0].left())
    assert max(spans) - min(spans) <= 2
    assert operations.journal.query(JournalRequest()) == originals


@pytest.mark.parametrize("numeric", [False, True])
def test_resolved_body_reflection_actions_and_real_terminal_chronology(
    workspace, qtbot, numeric
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, numeric)
    clock.advance()
    clock.instant += timedelta(microseconds=123456)
    resolve = (
        operations.resolve_numeric_prediction
        if numeric
        else operations.resolve_prediction
    )
    resolve(
        prediction.prediction_id,
        1 if numeric else BinaryOutcome.YES,
        use_recorded_time=True,
        resolution_notes="Observed factual evidence.",
        **context(prediction, numeric),
    )
    before = operations.get_prediction_scorecard(prediction.prediction_id)
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    card = screen.quantile_scorecard if numeric else screen.scorecard_section
    disclosure = screen.terminal_summary.context
    assert isinstance(disclosure.disclosure_button, QToolButton)
    assert not disclosure.disclosure_button.isChecked()
    disclosure.disclosure_button.setFocus()
    qtbot.keyClick(disclosure.disclosure_button, Qt.Key.Key_Space)
    assert disclosure.disclosure_body.isVisible()
    assert disclosure.disclosure_button.arrowType() is Qt.ArrowType.DownArrow
    qtbot.keyClick(disclosure.disclosure_button, Qt.Key.Key_Space)
    assert not disclosure.disclosure_body.isVisible()
    assert screen.workspace.overview_body.isAncestorOf(card)
    assert screen.action_strip.isAncestorOf(screen.write_postmortem_button)
    assert screen.action_strip.isAncestorOf(screen.skip_postmortem_button)
    assert screen.skip_postmortem_button.isVisible()
    assert not screen.resolution_section.isVisible()
    assert screen.workspace.overview_body.isAncestorOf(screen.postmortem)
    terminal = screen.findChild(QWidget, "terminalResolutionRecorded")
    assert terminal is not None and terminal.isVisible()
    assert clock.now().isoformat() in screen.terminal_summary.timing.toolTip()
    assert any(
        clock.now().isoformat() in label.toolTip()
        for label in terminal.findChildren(QLabel)
    )
    marker = screen.findChild(QWidget, "currentCommittedRevisionMarker")
    pane = screen.workspace.timeline_body
    assert terminal.mapTo(pane, QPoint()).y() < marker.mapTo(pane, QPoint()).y()
    screen.timeline_order.setCurrentIndex(1)
    qtbot.wait(20)
    terminal = screen.findChild(QWidget, "terminalResolutionRecorded")
    marker = screen.findChild(QWidget, "currentCommittedRevisionMarker")
    assert terminal.mapTo(pane, QPoint()).y() > marker.mapTo(pane, QPoint()).y()
    screen.write_postmortem_button.click()
    editor = screen.workspace.editor
    editor.body_input.setPlainText(
        "A later reflection preserves the outcome and score."
    )
    for mode in (AppearanceMode.DARK, AppearanceMode.LIGHT):
        window.appearance.select(mode)
        assert editor.body_input.toPlainText().startswith("A later reflection")
    screen.workspace.tabs.setCurrentIndex(0)
    screen.workspace.tabs.setCurrentIndex(1)
    assert editor.body_input.toPlainText().startswith("A later reflection")
    clock.advance()
    editor.submit()
    assert screen.workspace.editor is None
    assert "later reflection" in screen.postmortem.text()
    assert screen.postmortem.isVisible()
    assert screen.skip_postmortem_button.isHidden()
    assert screen.write_postmortem_button.text() == "Edit Postmortem"
    assert operations.get_prediction_scorecard(prediction.prediction_id) == before
    assert any(
        widget.objectName().startswith("terminalReflectionUpdated")
        for widget in screen.findChildren(QWidget)
    )


def test_current_numeric_distribution_is_distinct_from_earlier_scoring(
    workspace, qtbot
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, True)
    initial_time = clock.now()
    clock.advance()
    latest = operations.revise_quantile_forecast(
        prediction.prediction_id,
        {5: 10, 25: 20, 50: 30, 75: 40, 95: 50},
        **context(prediction, True),
    )
    clock.advance()
    operations.resolve_numeric_prediction(
        prediction.prediction_id,
        1,
        effective_resolution_at=initial_time + timedelta(minutes=30),
        **context(latest, True),
    )
    window._open_prediction(prediction.prediction_id)
    screen = window._numeric_prediction_detail_screen
    disclosure = screen.distribution_disclosure
    assert disclosure.disclosure_button.isVisible()
    assert not disclosure.disclosure_button.isChecked()
    disclosure.disclosure_button.click()
    assert "Latest committed distribution" in screen.numeric_history_label.text()
    assert "not the forecast used for scoring" in screen.quantile_cdf_summary.text()
    assert "30" in screen.quantile_cdf_summary.text()
    assert "median: 0" in screen.terminal_summary.facts.text()
    assert screen.quantile_scorecard.findChild(
        QLabel, "individualMedianErrorSummary"
    ).isVisible()
    window.resize(760, 520)
    qtbot.wait(30)
    assert screen.workspace.horizontalScrollBar().maximum() == 0
    assert screen.workspace.overview.horizontalScrollBar().maximum() == 0
    screen.refresh()
    assert not disclosure.disclosure_button.isChecked()
    assert screen.terminal_summary.isVisible()


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("one_shot", [False, True])
def test_corrected_histories_reveal_exact_sources_and_reset_on_fresh_visit(
    workspace, qtbot, numeric, one_shot
):
    window, operations, clock, database = workspace
    fixture = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/run_visual_review.py")
    )
    fixture["_seed_finish_cases"](database, now=clock.now())
    rows = operations.journal.query(JournalRequest()).rows
    prefix = (
        "Corrected exercise · One-Shot " if one_shot else "Long history · Adaptive "
    ) + ("Numeric" if numeric else "Binary")
    prediction = next(
        row.prediction for row in rows if row.prediction.question.startswith(prefix)
    )
    identifier = prediction.prediction_id
    before = operations.get_prediction_for_navigation(identifier)
    if not one_shot:
        revisions = (
            operations.list_numeric_forecast_revisions(identifier)
            if numeric
            else operations.list_forecast_revisions(identifier)
        )
        assert len(revisions) == 25
    assert not operations.search_predictions("birchbeacon").hits
    journal_hit = next(
        hit
        for hit in operations.search_predictions(
            "birchbeacon", include_superseded=True
        ).hits
        if hit.prediction.prediction_id == identifier
    )
    assert journal_hit.best_match.document.is_superseded
    window._open_prediction(identifier)
    screen = (
        window._prediction_detail_host._one_shot_detail
        if one_shot
        else window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    screen.focus_search_match(journal_hit.best_match.document)
    original = screen.findChild(
        QLabel,
        f"journalEntryOriginalBody{journal_hit.best_match.document.source_record_id}",
    )
    assert original is not None
    qtbot.waitUntil(original.isVisible)
    assert "Birchbeacon" in original.text()
    assert original.property("searchMatchEmphasis")
    definition_hit = next(
        hit
        for hit in operations.search_predictions(
            "copperbridge", include_superseded=True
        ).hits
        if hit.prediction.prediction_id == identifier
    )
    screen.focus_search_match(definition_hit.best_match.document)
    qtbot.wait(20)
    assert any(
        widget.isVisible()
        and widget.property("searchMatchEmphasis")
        and "copperbridge"
        in (
            widget.text().lower()
            if isinstance(widget, QLabel)
            else " ".join(label.text().lower() for label in widget.findChildren(QLabel))
        )
        for widget in screen.findChildren(QWidget)
    )
    assert operations.get_prediction_for_navigation(identifier) == before
    if one_shot:
        assert [
            correction.source_action.value for correction in before.record.corrections
        ] == ["transcription", "postmortem"]
        history_text = "\n".join(
            label.text() for label in screen.recorded_timeline.findChildren(QLabel)
        )
        assert "Postmortem update 2" in history_text
        assert "Transcription correction 2" not in history_text
    screen.refresh()
    qtbot.wait(20)
    current_history = screen.findChild(
        QGroupBox,
        f"journalEntryEditHistory{journal_hit.best_match.document.source_record_id}",
    )
    assert current_history is not None and not current_history.isChecked()
    assert operations.get_prediction_for_navigation(identifier) == before


@pytest.mark.parametrize("numeric", [False, True])
def test_terminal_repair_menu_and_keyboard_focus_keep_modal_boundaries(
    workspace, qtbot, numeric
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, numeric)
    clock.advance()
    resolve = (
        operations.resolve_numeric_prediction
        if numeric
        else operations.resolve_prediction
    )
    resolve(
        prediction.prediction_id,
        1 if numeric else BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction, numeric),
    )
    before = operations.get_prediction_for_navigation(prediction.prediction_id)
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    screen.current_revision_button.setFocus()
    qtbot.keyClick(screen.current_revision_button, Qt.Key.Key_Tab)
    assert screen.timeline_order.hasFocus()
    action = next(
        action
        for action in screen.more_menu.actions()
        if action.text() == "Correct Resolution"
    )
    assert action.isVisible()
    action.trigger()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is not None)
    dialog = QApplication.activeModalWidget()
    assert dialog.isVisible()
    qtbot.keyClick(dialog, Qt.Key.Key_N, modifier=Qt.KeyboardModifier.ControlModifier)
    assert window.current_screen_name == "Prediction Detail"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is None)
    assert operations.get_prediction_for_navigation(prediction.prediction_id) == before


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("points", [9, 12])
def test_long_history_small_window_keeps_reading_and_revision_controls_reachable(
    workspace, qtbot, qapp, numeric, points
):
    window, operations, clock, database = workspace
    fixture = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/run_visual_review.py")
    )
    fixture["_seed_finish_cases"](database, now=clock.now())
    question = "Long history · Adaptive " + ("Numeric" if numeric else "Binary")
    row = next(
        row
        for row in operations.journal.query(JournalRequest()).rows
        if row.prediction.question.startswith(question)
    )
    original_font = qapp.font()
    try:
        qapp.setFont(QFont("Segoe UI", points))
        window.resize(760, 520)
        window._open_prediction(row.prediction.prediction_id)
        screen = (
            window._numeric_prediction_detail_screen
            if numeric
            else window._prediction_detail_screen
        )
        qtbot.wait(30)
        for pane in (
            screen.workspace,
            screen.workspace.timeline,
            screen.workspace.overview,
        ):
            assert pane.horizontalScrollBar().maximum() == 0
        history = next(
            group
            for group in screen.findChildren(QGroupBox)
            if group.objectName().startswith("journalEntryEditHistory")
        )
        history.setChecked(True)
        qtbot.wait(20)
        assert screen.workspace.timeline.horizontalScrollBar().maximum() == 0
        screen.open_revise_forecast()
        editor = screen.workspace.editor
        qtbot.waitUntil(lambda: screen.workspace._proportion == 400)
        # The proportion can round to 400 before the final animation frame.
        # Inspect overflow after normal Timeline wrapping has resumed.
        qtbot.waitUntil(screen.workspace.timeline.widgetResizable)
        qtbot.wait(20)
        for pane in (
            screen.workspace,
            screen.workspace.timeline,
            screen.workspace.editor_scroll,
        ):
            assert pane.horizontalScrollBar().maximum() == 0, (
                pane.objectName(),
                screen.workspace.timeline.widgetResizable(),
                screen.workspace._transition.state(),
                screen.workspace._transition.currentTime(),
                screen.workspace._transition.duration(),
                screen.workspace.timeline.widget().minimumSizeHint(),
            )
        if numeric:
            for field in editor.quantile_input.inputs.values():
                screen.workspace.ensureWidgetVisible(field)
                qtbot.wait(10)
                assert (
                    screen.workspace.editor_scroll.viewport()
                    .rect()
                    .intersects(
                        field.rect().translated(
                            field.mapTo(
                                screen.workspace.editor_scroll.viewport(), QPoint()
                            )
                        )
                    )
                )
        else:
            presets = editor.findChild(QWidget, "revisionProbabilityShortcuts")
            for probability in range(10, 100, 10):
                button = presets.findChild(
                    QPushButton, f"revisionProbabilityShortcut{probability}"
                )
                assert presets.rect().contains(button.geometry())
                button.click()
                assert editor.probability_input.value() == probability
        save = editor.buttons.button(QDialogButtonBox.StandardButton.Save)
        screen.workspace.ensureWidgetVisible(save)
        qtbot.wait(20)
        assert (
            screen.workspace.editor_scroll.viewport()
            .rect()
            .intersects(
                save.rect().translated(
                    save.mapTo(screen.workspace.editor_scroll.viewport(), QPoint())
                )
            )
        )
    finally:
        screen.workspace.clear_editor()
        qapp.setFont(original_font)


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("one_shot", [False, True])
def test_invalid_current_reason_has_one_visible_home_and_exact_search_target(
    workspace, qtbot, numeric, one_shot
):
    window, operations, clock, database = workspace
    fixture = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/run_visual_review.py")
    )
    fixture["_seed_detail_cases"](database, now=clock.now())
    prefix = (
        "Corrected Invalid reason · "
        + ("One-Shot " if one_shot else "Adaptive ")
        + ("Numeric" if numeric else "Binary")
    )
    row = next(
        row
        for row in operations.journal.query(JournalRequest()).rows
        if row.prediction.question.startswith(prefix)
    )
    identifier = row.prediction.prediction_id
    before = operations.get_invalidation_history(identifier)
    window._open_prediction(identifier)
    screen = (
        window._prediction_detail_host._one_shot_detail
        if one_shot
        else window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    assert (
        len(
            [
                label
                for label in screen.findChildren(QLabel)
                if label.isVisible() and before.effective.reason in label.text()
            ]
        )
        == 1
    )
    query = '"Two different answer keys"' if one_shot else '"two incompatible outcomes"'
    hit = next(
        hit
        for hit in operations.search_predictions(query).hits
        if hit.prediction.prediction_id == identifier
    )
    screen.focus_search_match(hit.best_match.document)
    qtbot.waitUntil(
        lambda: bool(screen.terminal_summary.note.property("searchMatchEmphasis"))
    )
    assert screen.terminal_summary.note.isVisible()
    assert (
        before.original.invalidated_at.isoformat()
        in screen.terminal_summary.timing.toolTip()
    )
    assert (
        before.corrections[-1].corrected_at.isoformat()
        in screen.terminal_summary.timing.toolTip()
    )
    actions = screen.more_button.menu().actions()
    assert any(
        action.isVisible()
        and ("Reason" in action.text() or "Invalid reason" in action.text())
        for action in actions
    )
    assert operations.get_invalidation_history(identifier) == before


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("invalid", [False, True])
def test_terminal_panes_are_equal_and_task_tabs_own_the_context_heading(
    workspace, qtbot, numeric, invalid
):
    window, operations, clock, _database = workspace
    prediction = create(operations, clock, numeric)
    clock.advance()
    if invalid:
        operation = (
            operations.invalidate_numeric_prediction
            if numeric
            else operations.invalidate_prediction
        )
        current = operation(
            prediction.prediction_id,
            reason="A clear Invalid reason",
            **context(prediction, numeric),
        )
    else:
        operation = (
            operations.resolve_numeric_prediction
            if numeric
            else operations.resolve_prediction
        )
        current = operation(
            prediction.prediction_id,
            1 if numeric else BinaryOutcome.YES,
            use_recorded_time=True,
            **context(prediction, numeric),
        )
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    pane = screen.workspace
    qtbot.waitUntil(lambda: pane._proportion == 500)
    assert pane.columns.stretch(0) == pane.columns.stretch(1)
    assert screen.overview_heading.text() == (
        "ARCHIVAL CONTEXT" if invalid else "OVERVIEW"
    )
    if not invalid:
        screen.open_postmortem()
        qtbot.waitUntil(lambda: pane._proportion == 400)
        assert screen.overview_heading.isHidden()
        pane.tabs.setCurrentIndex(0)
        qtbot.waitUntil(lambda: pane._proportion == 500)
        assert screen.overview_heading.isHidden()
        pane.clear_editor()
        assert not screen.overview_heading.isHidden()
    assert operations.get_prediction_for_navigation(prediction.prediction_id) == current
