"""Native task, header and confirmation regressions on disposable real stores."""

from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import one_shot_contract
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
