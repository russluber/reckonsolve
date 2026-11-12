"""Native task, header and confirmation regressions on disposable real stores."""

import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QWidget

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotSourceAction,
    OneShotValues,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)
from reckonsolve.ui.detail_workspace import DetailWorkspace
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.numeric_interval import NumericInterval
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
)


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 11, 12, tzinfo=UTC)

    def now(self):
        return self.value

    def advance(self):
        self.value += timedelta(hours=1)


@pytest.fixture
def detail(qtbot, tmp_path):
    clock = Clock()
    database = Database.open(tmp_path / "detail.sqlite3")
    operations = PredictionOperations(database, clock, UTC)
    prediction = operations.create_prediction(
        "A complete committed Question",
        65,
        forecast_deadline=clock.now() + timedelta(days=10),
    )
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(window)
    window.resize(1100, 850)
    window.show()
    window._open_prediction(prediction.prediction_id)
    yield window, operations, clock, prediction
    for workspace in window.findChildren(DetailWorkspace):
        workspace.clear_editor()
    window.creation_task.reset()
    window.close()
    database.close()


def choose(label):
    def answer():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        next(button for button in dialog.buttons() if button.text() == label).click()

    QTimer.singleShot(0, answer)


def test_detail_review_profile_exposes_exact_terminal_cases(tmp_path):
    fixture = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/run_visual_review.py")
    )
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    database = Database.open(tmp_path / "profile.sqlite3")
    try:
        fixture["_seed_detail_cases"](database, now=now)
        operations = PredictionOperations(database, fixture["_ReviewClock"](now), UTC)
        page = operations.journal.query(JournalRequest())
        assert page.total == 10
        assert (
            len(
                [
                    row
                    for row in page.rows
                    if row.prediction.status is PredictionStatus.INVALID
                ]
            )
            == 4
        )
        assert (
            len(
                [
                    row
                    for row in page.rows
                    if row.prediction.status is PredictionStatus.OPEN
                ]
            )
            == 2
        )
        for row in page.rows:
            if row.prediction.question.startswith("No eligible forecast"):
                assert operations.get_prediction_scorecard(
                    row.prediction.prediction_id
                ).unscored_reason
                assert row.probability_percent is None and row.quantiles is None
            elif row.prediction.question.startswith("Earlier forecast scored"):
                assert row.excluded_later_forecast
                assert (
                    row.probability_percent == 65
                    if row.probability_percent is not None
                    else str(row.quantiles.q50) == "3"
                )
            elif row.prediction.status is PredictionStatus.INVALID:
                history = operations.get_invalidation_history(
                    row.prediction.prediction_id
                )
                assert len(history.corrections) == 1
                assert history.original.reason != history.effective.reason
                assert (
                    history.original.invalidated_at
                    < history.corrections[0].corrected_at
                )
    finally:
        database.close()


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("invalid", [False, True])
def test_terminal_reading_leads_with_results_or_reason(detail, qtbot, numeric, invalid):
    window, operations, clock, binary = detail
    prediction = (
        operations.create_numeric_prediction(
            "Terminal Numeric reading",
            "items",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=clock.now() + timedelta(days=10),
        )
        if numeric
        else binary
    )
    context = {
        "expected_revision_id": (
            prediction.current_revision.revision_id
            if numeric
            else prediction.current_revision_id
        ),
        "expected_metadata_version": prediction.metadata_version,
    }
    clock.advance()
    if invalid:
        operation = (
            operations.invalidate_numeric_prediction
            if numeric
            else operations.invalidate_prediction
        )
        operation(
            prediction.prediction_id, reason="The question is ambiguous.", **context
        )
    elif numeric:
        operations.resolve_numeric_prediction(
            prediction.prediction_id, 1, use_recorded_time=True, **context
        )
    else:
        operations.resolve_prediction(
            prediction.prediction_id,
            BinaryOutcome.YES,
            use_recorded_time=True,
            **context,
        )
    before = (
        operations.get_prediction_scorecard(prediction.prediction_id)
        if not invalid
        else None
    )
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    summary = screen.findChild(QWidget, "detailTerminalSummary")
    assert summary is not None and summary.isVisible()
    assert (
        summary.mapTo(screen.workspace.widget(), QPoint()).y()
        < screen.action_strip.mapTo(screen.workspace.widget(), QPoint()).y()
    )
    assert (screen.interval_display if numeric else screen.probability).isHidden()
    assert screen.header_timing.isHidden()
    assert (
        "Not scored" in summary.score.text()
        if invalid
        else ("WIS" if numeric else "Trajectory Brier") in summary.score.text()
    )
    if invalid:
        assert "ambiguous" in summary.note.text()
        assert "Last forecast" in summary.context.disclosure_button.text()
    else:
        assert ("1 items" if numeric else "Yes") in summary.outcome.text()
        assert not summary.context.disclosure_button.isChecked()
        summary.context.disclosure_button.click()
        assert summary.context.disclosure_body.isVisible()
    for mode in (AppearanceMode.DARK, AppearanceMode.LIGHT):
        window.appearance.select(mode)
        qtbot.wait(20)
        assert summary.isVisible()
    if not invalid:
        assert operations.get_prediction_scorecard(prediction.prediction_id) == before


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("unscored", [False, True])
def test_terminal_header_preserves_earlier_cutoff_and_unscored_context(
    detail, numeric, unscored
):
    window, operations, clock, binary = detail
    prediction = (
        operations.create_numeric_prediction(
            "Earlier scoring context",
            "items",
            0,
            {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=clock.now() + timedelta(days=10),
        )
        if numeric
        else binary
    )
    created = clock.now()
    original_revision_id = (
        prediction.current_revision.revision_id
        if numeric
        else prediction.current_revision_id
    )
    clock.advance()
    revise = (
        operations.revise_quantile_forecast if numeric else operations.revise_forecast
    )
    latest = revise(
        prediction.prediction_id,
        {5: 10, 25: 20, 50: 30, 75: 40, 95: 50} if numeric else 90,
        expected_revision_id=original_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    clock.advance()
    resolve = (
        operations.resolve_numeric_prediction
        if numeric
        else operations.resolve_prediction
    )
    resolve(
        prediction.prediction_id,
        2 if numeric else BinaryOutcome.YES,
        effective_resolution_at=created
        if unscored
        else created + timedelta(minutes=30),
        expected_revision_id=latest.current_revision.revision_id
        if numeric
        else latest.current_revision_id,
        expected_metadata_version=latest.metadata_version,
    )
    before = operations.get_prediction_scorecard(prediction.prediction_id)
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    summary = screen.terminal_summary
    if unscored:
        assert summary.score.text() == "Not scored"
        assert before.unscored_reason in summary.note.text()
        assert summary.context.isHidden()
    else:
        assert str(original_revision_id) in summary.facts.text()
        assert ("median: 3" if numeric else "65%") in summary.facts.text()
        assert "excluded" in summary.note.text().lower()
        assert not summary.context.disclosure_button.isChecked()
    assert operations.get_prediction_scorecard(prediction.prediction_id) == before


@pytest.mark.parametrize("numeric", [False, True])
def test_invalid_one_shot_reason_leads_and_forecast_stays_available(detail, numeric):
    window, operations, clock, _ = detail
    pending = operations.one_shots.create(
        NewOneShotPrediction(
            "Invalid One-Shot reading",
            one_shot_contract(
                PredictionType.NUMERIC if numeric else PredictionType.BINARY
            ),
            OneShotValues(
                quantiles=FiveQuantiles.from_values(
                    {5: 1, 25: 2, 50: 3, 75: 4, 95: 5}, 0
                )
            )
            if numeric
            else OneShotValues(probability_percent=70),
            QuantileDefinition("items", 0, NumericValueConstraint.CONTINUOUS)
            if numeric
            else None,
        )
    )
    clock.advance()
    invalid = operations.one_shots.invalidate(
        pending, reason="The original exercise was ambiguous."
    )
    clock.advance()
    history = operations.correct_invalidation_reason(
        pending.prediction_id,
        "Clarified reason: the source used two incompatible answers.",
        expected_correction_id=None,
    )
    before = operations.one_shots.get(pending.prediction_id)
    window._open_prediction(pending.prediction_id)
    screen = window._prediction_detail_host._one_shot_detail
    summary = screen.terminal_summary
    assert summary.isVisible() and summary.score.text() == "Not scored"
    assert summary.note.text() == history.effective.reason
    assert "Original decision date unchanged" in summary.timing.text()
    assert not screen.forecast.isVisible()
    assert screen.answer_button.isHidden()
    assert "Last forecast" in summary.context.disclosure_button.text()
    assert (
        history.original.invalidated_at
        == invalid.invalidation_history.original.invalidated_at
    )
    assert operations.one_shots.get(pending.prediction_id) == before


@pytest.mark.parametrize("numeric", [False, True])
def test_timeline_jump_stays_with_history_and_terminal_actions_leave_no_gaps(
    detail, qtbot, numeric
):
    window, operations, clock, binary = detail
    prediction = (
        operations.create_numeric_prediction(
            "Readable Numeric controls",
            "units",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=clock.now() + timedelta(days=10),
        )
        if numeric
        else binary
    )
    revision_id = (
        prediction.current_revision.revision_id
        if numeric
        else prediction.current_revision_id
    )
    add_journal = (
        operations.add_numeric_journal_entry
        if numeric
        else operations.add_journal_entry
    )
    for index in range(12):
        clock.advance()
        add_journal(
            prediction.prediction_id,
            f"History entry {index}: " + "Preserve this reasoning. " * 12,
            expected_revision_id=revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    window._open_prediction(prediction.prediction_id)
    screen = (
        window._numeric_prediction_detail_screen
        if numeric
        else window._prediction_detail_screen
    )
    controls = screen.findChild(QWidget, "detailTimelineControls")
    jump = screen.current_revision_button
    assert controls.isAncestorOf(jump)
    assert not screen.action_strip.isAncestorOf(jump)
    bar = screen.workspace.timeline.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0)
    position = jump.mapTo(screen.workspace.panes, QPoint())
    bar.setValue(bar.maximum())
    qtbot.wait(20)
    assert jump.isVisible()
    assert jump.mapTo(screen.workspace.panes, QPoint()) == position
    screen.timeline_order.setCurrentIndex(1)
    qtbot.wait(20)
    bar.setValue(bar.maximum())
    jump.click()
    qtbot.waitUntil(lambda: bar.value() == 0)
    for width in (1100, 760):
        window.resize(width, 850)
        qtbot.wait(30)
        for control in (jump, screen.timeline_order):
            assert controls.rect().contains(control.geometry())
        assert not jump.geometry().intersects(screen.timeline_order.geometry())
    clock.advance()
    if numeric:
        resolved = operations.resolve_numeric_prediction(
            prediction.prediction_id,
            "1",
            use_recorded_time=True,
            expected_revision_id=revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    else:
        resolved = operations.resolve_prediction(
            prediction.prediction_id,
            BinaryOutcome.YES,
            use_recorded_time=True,
            expected_revision_id=revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    screen.show_prediction(resolved)
    qtbot.wait(30)
    assert screen.more_button.isVisible()
    assert screen.more_button.geometry().left() == 0
    assert all(
        button.isHidden()
        for button in (
            screen.revise_forecast_button,
            screen.review_forecast_button,
            screen.add_journal_entry_button,
            screen.resolve_button,
        )
    )


def test_revision_is_contextual_retains_overview_and_commits_once(detail, qtbot):
    window, operations, clock, prediction = detail
    screen = window._prediction_detail_screen
    screen.open_revise_forecast()
    editor = screen.workspace.editor
    assert editor is not None and not editor.isWindow()
    assert QApplication.activeModalWidget() is None
    editor.probability_input.setValue(73)
    editor.rationale_input.setPlainText("New evidence, still an unsaved draft")
    screen.workspace.tabs.setCurrentIndex(0)
    assert screen.probability.text() == "65%"
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 1
    screen.workspace.tabs.setCurrentIndex(1)
    assert editor.probability_input.value() == 73
    clock.advance()
    editor.submit()
    assert screen.workspace.editor is None
    assert screen.probability.text() == "73%"
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 2


def test_appearance_and_overview_consultation_preserve_entered_revision(detail):
    window, operations, _clock, prediction = detail
    screen = window._prediction_detail_screen
    screen.open_revise_forecast()
    editor = screen.workspace.editor
    editor.probability_input.setValue(72)
    editor.rationale_input.setPlainText("Retain this through appearance changes")
    for mode in (AppearanceMode.LIGHT, AppearanceMode.DARK):
        window.appearance.select(mode)
        screen.workspace.tabs.setCurrentIndex(0)
        screen.workspace.tabs.setCurrentIndex(1)
        assert screen.workspace.editor is editor
        assert editor.probability_input.value() == 72
        assert (
            editor.rationale_input.toPlainText()
            == "Retain this through appearance changes"
        )
        assert screen.workspace.dirty
        assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 1


def test_exact_search_reveals_long_journal_body_then_fresh_visit_collapses(
    detail, qtbot
):
    window, operations, clock, prediction = detail
    clock.advance()
    entry = operations.add_journal_entry(
        prediction.prediction_id,
        "Substantial context. " * 50 + "Distinctive needle",
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    screen = window._prediction_detail_screen
    screen.refresh()
    body = screen.findChild(QLabel, f"journalEntryBody{entry.entry_id}")
    assert body.isHidden()
    hit = operations.search_predictions("needle").hits[0]
    screen.focus_search_match(hit.best_match.document)
    qtbot.waitUntil(body.isVisible)
    assert body.property("searchMatchEmphasis")
    screen.refresh()
    assert screen.findChild(QLabel, f"journalEntryBody{entry.entry_id}").isHidden()


def test_new_guard_keeps_then_discards_revision_without_resurrecting_it(detail):
    window, operations, _clock, prediction = detail
    screen = window._prediction_detail_screen
    screen.open_revise_forecast()
    screen.workspace.editor.probability_input.setValue(72)
    choose("Keep editing")
    window.navigate_to("New Prediction")
    assert window.current_screen_name == "Prediction Detail"
    assert screen.workspace.editor.probability_input.value() == 72
    choose("Discard revision and start New")
    window.navigate_to("New Prediction")
    assert window.current_screen_name == "New Prediction"
    window.return_to_source()
    assert screen.workspace.editor is None
    assert operations.get_prediction(prediction.prediction_id).probability_percent == 65


def test_resolution_preparation_requires_separate_terminal_confirmation(detail):
    window, operations, clock, prediction = detail
    screen = window._prediction_detail_screen
    screen.open_resolve_prediction()
    editor = screen.workspace.editor
    editor.outcome_yes.setChecked(True)
    editor.notes_input.setPlainText("The event occurred")
    choose("Keep editing")
    editor.submit()
    assert (
        operations.get_prediction(prediction.prediction_id).status
        is PredictionStatus.OPEN
    )
    assert editor.notes_input.toPlainText() == "The event occurred"
    clock.advance()
    choose("Resolve")
    editor.submit()
    assert (
        operations.get_prediction(prediction.prediction_id).status
        is PredictionStatus.RESOLVED
    )
    assert screen.workspace.editor is None


def test_postmortem_direct_save_preserves_facts_and_stale_form(detail, monkeypatch):
    window, operations, clock, prediction = detail
    from reckonsolve.domain.predictions import BinaryOutcome

    clock.advance()
    resolved = operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    screen = window._prediction_detail_screen
    screen.show_prediction(resolved)
    original = operations.get_binary_resolution_history(
        prediction.prediction_id
    ).original
    screen.open_postmortem()
    editor = screen.workspace.editor
    editor.body_input.setPlainText("A reflection without factual changes")
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: pytest.fail("Nonblank reflection must save directly"),
    )
    clock.advance()
    editor.submit()
    history = operations.get_binary_resolution_history(prediction.prediction_id)
    assert history.original == original
    assert history.effective.postmortem == "A reflection without factual changes"
    screen.open_postmortem()
    editor = screen.workspace.editor
    editor.body_input.setPlainText("Keep my stale form")
    clock.advance()
    save_postmortem(operations, history, "Saved elsewhere")
    clock.advance()
    editor.submit()
    assert screen.workspace.editor is editor
    assert editor.body_input.toPlainText() == "Keep my stale form"
    assert editor.error.isVisible()
    assert (
        len(
            operations.get_binary_resolution_history(
                prediction.prediction_id
            ).corrections
        )
        == 2
    )


@pytest.mark.parametrize(
    "values,groups",
    [
        ([1, 2, 3, 3, 5], 4),
        ([3, 3, 3, 3, 3], 1),
        (["-12500", "-1000.25", "-1000", "-999.75", "8000"], 5),
    ],
)
def test_interval_retains_exact_groups_and_true_marks(qtbot, values, groups):
    interval = NumericInterval()
    qtbot.addWidget(interval)
    interval.resize(660, 150)
    forecast = FiveQuantiles.from_values(
        dict(zip((5, 25, 50, 75, 95), values, strict=True)), 2
    )
    interval.set_forecast(forecast, "USD")
    interval.show()
    qtbot.wait(20)
    assert len(interval.labels) == groups
    for value in forecast.values:
        assert any(str(value) in label.text() for label in interval.labels)
    if values[0] == values[-1]:
        assert len(set(interval.positions)) == 1
    else:
        assert interval.positions == sorted(interval.positions)
    for index, label in enumerate(interval.labels):
        assert interval.rect().contains(label.geometry())
        assert all(
            not label.geometry().intersects(other.geometry())
            for other in interval.labels[index + 1 :]
        )


def test_expired_numeric_revision_retains_draft_and_repeats_compact_notice(detail):
    window, operations, clock, _prediction = detail
    numeric = operations.create_numeric_prediction(
        "Exact Numeric context",
        "USD",
        2,
        {5: "-2.00", 25: "-1.00", 50: "0.00", 75: "1.00", 95: "2.00"},
        value_constraint=NumericValueConstraint.CONTINUOUS,
        forecast_deadline=clock.now() + timedelta(days=1),
    )
    window._open_prediction(numeric.prediction_id)
    screen = window._numeric_prediction_detail_screen
    screen.open_revise_forecast()
    editor = screen.workspace.editor
    editor.quantile_input.inputs[50].setText("0.25")
    original = screen.interval_display.quantiles
    clock.value += timedelta(days=2)
    editor.submit()
    assert screen.workspace.editor is editor
    assert editor.quantile_input.inputs[50].text() == "0.25"
    assert screen.interval_display.quantiles == original
    assert len(operations.list_numeric_forecast_revisions(numeric.prediction_id)) == 1
    assert screen.locked_explanation.isVisible(), editor.form_error.text()
    assert screen.revise_forecast_button.isHidden()
    cue = editor.findChild(QPushButton, "deadlineFailureRepeatButton")
    assert cue.isVisible()
    editor._deadline_explain()
    notice = editor.findChild(QLabel, "revisionFailureNotification")
    assert notice.isVisible()
    notice.hide()
    editor._deadline_repeat.click()
    assert notice.isVisible()


@pytest.mark.parametrize("numeric", [False, True])
def test_one_shot_contextual_journal_inline_reflection_and_internal_repair(
    detail, qtbot, numeric
):
    window, operations, clock, _prediction = detail
    pending = operations.one_shots.create(
        NewOneShotPrediction(
            "One-Shot workspace",
            one_shot_contract(
                PredictionType.NUMERIC if numeric else PredictionType.BINARY
            ),
            OneShotValues(
                quantiles=FiveQuantiles.from_values(
                    {5: -2, 25: -1, 50: 0, 75: 1, 95: 2}, 0
                )
            )
            if numeric
            else OneShotValues(probability_percent=70),
            QuantileDefinition("units", 0, NumericValueConstraint.WHOLE_NUMBER)
            if numeric
            else None,
        )
    )
    window._open_prediction(pending.prediction_id)
    screen = window._prediction_detail_host._one_shot_detail
    assert not any(label.text() == "Overview" for label in screen.findChildren(QLabel))
    screen.open_journal()
    editor = screen.workspace.editor
    editor.body_input.setPlainText("An anchored journal entry")
    clock.advance()
    editor.submit()
    qtbot.waitUntil(lambda: screen.journals.isVisible())
    assert screen.workspace.editor is None
    pending = operations.one_shots.get(pending.prediction_id)
    assert len(pending.journals) == 1
    screen.open_values(correction=False)
    dialog = screen._dialog
    if numeric:
        dialog.form.actual.setText("1")
    else:
        dialog.form.outcome.setCurrentIndex(1)
    clock.advance()
    dialog.submit()
    assert (
        operations.one_shots.get(pending.prediction_id).status
        is PredictionStatus.RESOLVED
    )
    screen.add_postmortem()
    screen.workspace.editor.body_input.setPlainText("Discard this temporary reflection")
    choose("Discard changes and continue")
    screen.open_values(correction=True)
    assert screen.workspace.editor is None
    assert not screen.add_postmortem_button.isHidden()
    screen._dialog.reject()
    screen.add_postmortem()
    editor = screen.workspace.editor
    assert screen.workspace.inline
    assert screen.reflection.isAncestorOf(editor)
    editor.body_input.setPlainText("Reflection only, separate from repair")
    clock.advance()
    editor.submit()
    saved = operations.one_shots.get(pending.prediction_id)
    assert saved.record.corrections[-1].source_action is OneShotSourceAction.POSTMORTEM
    screen.open_values(correction=True)
    dialog = screen._dialog
    if numeric:
        dialog.form.quantiles.inputs[50].setText("1")
    else:
        dialog.form.probability.setValue(75)
    dialog.submit()
    assert dialog.review.active
    assert operations.one_shots.get(pending.prediction_id) == saved
    dialog.review.back.click()
    assert (
        (dialog.form.quantiles.inputs[50].text() == "1")
        if numeric
        else (dialog.form.probability.value() == 75)
    )
    dialog.submit()
    clock.advance()
    dialog.submit()
    repaired = operations.one_shots.get(pending.prediction_id)
    assert repaired.record.original == saved.record.original
    assert repaired.record.effective.postmortem == saved.record.effective.postmortem
    assert (
        repaired.record.corrections[-1].source_action
        is OneShotSourceAction.TRANSCRIPTION
    )


@pytest.mark.parametrize("numeric", [False, True])
def test_adaptive_reflection_command_preserves_exact_terminal_facts_and_score(
    detail, numeric
):
    _window, operations, clock, binary = detail
    prediction = (
        operations.create_numeric_prediction(
            "Numeric reflection",
            "units",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=clock.now() + timedelta(days=1),
        )
        if numeric
        else binary
    )
    clock.advance()
    if numeric:
        operations.resolve_numeric_prediction(
            prediction.prediction_id,
            "1",
            use_recorded_time=True,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        get_history = operations.get_numeric_resolution_history
    else:
        operations.resolve_prediction(
            prediction.prediction_id,
            BinaryOutcome.YES,
            use_recorded_time=True,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        get_history = operations.get_binary_resolution_history
    history = get_history(prediction.prediction_id)
    score = operations.get_prediction_scorecard(prediction.prediction_id)
    clock.advance()
    written = save_postmortem(operations, history, "What I learned")
    assert written.original == history.original
    assert written.corrections[-1].changed_fields == ("postmortem",)
    assert operations.get_prediction_scorecard(prediction.prediction_id) == score
    with pytest.raises(ApplicationError):
        save_postmortem(operations, history, "Stale overwrite")
    with pytest.raises(ApplicationError, match="Confirm clearing"):
        save_postmortem(operations, written, None)
    clock.advance()
    cleared = save_postmortem(
        operations,
        written,
        None,
        confirm_clear=True,
        correction_reason="Removing mistaken reflection",
    )
    assert cleared.original == history.original
    assert cleared.effective.postmortem is None
    assert operations.get_prediction_scorecard(prediction.prediction_id) == score
