"""M57 public entry, correction and GUI/CLI handoff on disposable archives."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from io import StringIO

import pytest
from PySide6.QtCore import QDate, QPoint, QRect, Qt, QTime
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QToolButton, QWidget
from supported_fixtures import create_binary, create_numeric
from test_one_shot_persistence import Clock, request

from reckonsolve.application.errors import (
    ApplicationError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import run
from reckonsolve.data.database import Database
from reckonsolve.data.search_index import SearchIndexRepairRequiredError
from reckonsolve.domain.browser import ArchiveAttention
from reckonsolve.domain.one_shot import OneShotDetail, ReportedTime
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
)
from reckonsolve.domain.quantiles import FiveQuantiles
from reckonsolve.one_shot_display import detail_lines
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.one_shot import (
    OneShotCreationScreen,
    OneShotEditDialog,
    ReportedTimeInput,
)
from reckonsolve.ui.screens import EditPredictionDetailsDialog


@pytest.fixture
def app(tmp_path):
    database = Database.open(tmp_path / "m57.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    yield database, clock, operations
    database.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_public_creation_correction_and_deadline_coexistence(app, numeric):
    database, _, operations = app
    deadline = create_binary(operations, "Tomorrow?", 70)
    numeric_deadline = create_numeric(
        operations, "Tomorrow's quantity?", "m", 0, {5: 0, 25: 1, 50: 2, 75: 3, 95: 4}
    )
    original = operations.one_shots.create(request(numeric))
    assert operations.get_prediction_for_navigation(original.prediction_id) == original
    corrected = operations.one_shots.correct(
        original,
        replace(
            original.record.effective,
            answer=FixedPrecisionValue(300, 2) if numeric else BinaryOutcome.NO,
            resolution_notes="Corrected measurement",
        ),
    )
    assert corrected.record.original == original.record.original
    assert corrected.record.recorded_at == original.record.recorded_at
    assert len(corrected.record.corrections) == 1
    assert operations.one_shots.score(corrected) != operations.one_shots.score(original)
    assert "Before" in detail_lines(corrected, operations.one_shots.score(corrected))
    assert len(operations.browse_predictions().predictions) == 3
    assert operations.get_prediction(deadline.prediction_id) == deadline
    assert (
        operations.get_numeric_prediction(numeric_deadline.prediction_id)
        == numeric_deadline
    )
    assert not operations.get_dashboard().needs_attention_predictions
    assert tuple(
        item.prediction_id
        for item in operations.get_dashboard().needs_postmortem_predictions
    ) == (corrected.prediction_id,)
    analytics = operations.get_forecast_analytics()
    assert analytics.trajectory_binary.resolved_candidate_count == 0
    assert analytics.quantile_numeric.resolved_candidate_count == 0
    database.check_search_index()
    for action in (operations.revise_forecast, operations.add_forecast_review):
        with pytest.raises(ApplicationError, match="One-Shot"):
            if action == operations.revise_forecast:
                action(
                    original.prediction_id,
                    30,
                    expected_revision_id=1,
                    expected_metadata_version=1,
                )
            else:
                action(
                    original.prediction_id,
                    expected_revision_id=1,
                    expected_metadata_version=1,
                )


@pytest.mark.parametrize("numeric", [False, True])
def test_answer_and_correction_reject_stale_independent_connection(app, numeric):
    database, clock, operations = app
    pending = operations.one_shots.create(request(numeric, False))
    other_db = Database.open(database.path)
    try:
        other = PredictionOperations(other_db, clock, UTC)
        copied = other.one_shots.get(pending.prediction_id)
        changed = operations.one_shots.correct(
            pending, replace(pending.record.effective, forecast_reported=None)
        )
        answer = FixedPrecisionValue(0, 2) if numeric else BinaryOutcome.YES
        with pytest.raises(ApplicationError, match="changed"):
            other.one_shots.add_answer(
                copied, replace(copied.record.effective, answer=answer)
            )
        saved = operations.one_shots.add_answer(
            changed, replace(changed.record.effective, answer=answer)
        )
        assert saved.status is PredictionStatus.RESOLVED
        with pytest.raises(ApplicationError, match="changed"):
            other.one_shots.correct(
                changed,
                replace(
                    changed.record.effective,
                    forecast_reported=pending.record.effective.forecast_reported,
                ),
            )
        assert operations.one_shots.get(pending.prediction_id) == saved
    finally:
        other_db.close()


def test_metadata_definition_history_and_guarded_delete(app):
    _, _, operations = app
    pending = operations.one_shots.create(request(False, False))
    fields = {
        "question": "Clarified tree?",
        "background": None,
        "resolution_criteria": pending.resolution_criteria,
        "forecast_deadline": None,
        "expected_resolution": None,
        "tags": pending.tags,
        "expected_metadata_version": 1,
    }
    with pytest.raises(MeaningChangeConfirmationRequired):
        operations.update_metadata(pending.prediction_id, **fields)
    edited = operations.update_metadata(
        pending.prediction_id, **fields, confirm_meaning_change=True
    )
    assert isinstance(edited, OneShotDetail)
    assert edited.definition_changes[0].old_question == pending.question
    assert not edited.deletion_allowed
    with pytest.raises(ApplicationError):
        operations.one_shots.delete(edited, confirmed=True)
    journaled = operations.one_shots.add_journal(
        edited, "Reasoning <plain>\non two lines"
    )
    assert journaled.journals[0].body == "Reasoning <plain>\non two lines"
    invalid = operations.one_shots.invalidate(journaled, reason="Wrong tree")
    assert operations.one_shots.score(invalid) is None
    assert invalid.invalidation_history.effective.reason == "Wrong tree"


def test_deleted_context_fails_cleanly(app):
    _, _, operations = app
    pending = operations.one_shots.create(request(False, False))
    operations.one_shots.delete(pending, confirmed=True)
    with pytest.raises(ApplicationError, match="deleted"):
        operations.one_shots.add_answer(
            pending, replace(pending.record.effective, answer=BinaryOutcome.YES)
        )


def cli(path, args, lines=()):
    output, errors = StringIO(), StringIO()
    code = run(
        args,
        database_path=path,
        stdin=StringIO("\n".join(lines) + "\n"),
        stdout=output,
        stderr=errors,
    )
    return code, output.getvalue(), errors.getvalue()


@pytest.mark.parametrize("numeric", [False, True])
def test_cli_create_then_answer_and_read_corrections(tmp_path, numeric):
    path = tmp_path / "cli.sqlite3"
    forecast = (
        ["Tree?", "m", "2", "w", "1", "1", "1", "1", "1"]
        if numeric
        else ["Tree?", "80"]
    )
    code, output, error = cli(
        path,
        ["create", "numeric" if numeric else "binary", "--one-shot"],
        [*forecast, "", "", "n", "n", "y"],
    )
    assert code == 0, error
    assert "Waiting for answer" in output
    assert "Brier:" not in output and "WIS:" not in output
    code, output, error = cli(
        path, ["resolve", "1"], ["1" if numeric else "yes", "", "", "", "y"]
    )
    assert code == 0, error
    assert ("WIS: 0" if numeric else "Brier: 0.04") in output
    database = Database.open(path)
    try:
        operations = PredictionOperations(database)
        detail = operations.one_shots.get(1)
        operations.one_shots.correct(
            detail,
            replace(
                detail.record.effective,
                answer=FixedPrecisionValue(200, 2) if numeric else BinaryOutcome.NO,
            ),
            note="Copied incorrectly",
        )
    finally:
        database.close()
    code, output, error = cli(path, ["show", "1"])
    assert code == 0, error
    assert "Original saved facts" in output and "Transcription correction 1" in output
    assert "Copied incorrectly" in output
    assert "Trajectory Brier" not in output and "Initial WIS" not in output
    for command in ("revise", "review"):
        code, _, error = cli(path, [command, "1"])
        assert code == 1 and "One-Shot" in error
    code, output, error = cli(path, ["list"])
    assert code == 0, error
    assert "One-Shot" in output


@pytest.mark.parametrize("save", ["n", ""])
def test_cli_cancel_creates_nothing(tmp_path, save):
    path = tmp_path / "cancel.sqlite3"
    code, output, _ = cli(
        path,
        ["create", "binary", "--one-shot"],
        ["Tree?", "80", "", "", "y", "yes", "", "", "", "n", save],
    )
    assert code == 130
    assert "Brier:" not in output
    database = Database.open(path)
    try:
        assert not PredictionOperations(database).browse_predictions().predictions
    finally:
        database.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_desktop_save_with_answer_no_preview_and_correct(
    app, qtbot, monkeypatch, numeric
):
    _, _, operations = app
    screen = OneShotCreationScreen(operations)
    qtbot.addWidget(screen)
    screen.show()
    screen.question.setText("Tree <height>?")
    screen.background.setPlainText("Beside the house; check with the phone camera")
    screen.rationale.setPlainText("Compared it to the roof")
    form = screen.form
    if numeric:
        form.type_input.setCurrentIndex(1)
        form.unit.setText("m")
        form.precision.setValue(2)
        form.constraint.setCurrentIndex(2)
        form.quantiles.set_quantiles(
            FiveQuantiles.from_values(dict.fromkeys((5, 25, 50, 75, 95), 2), 2)
        )
        form.actual.setText("2")
    else:
        form.probability.setValue(80)
        form.outcome.setCurrentIndex(1)
    form.has_answer.setChecked(True)
    form.forecast_time.set_value(request().values.forecast_reported)
    form.reveal_time.set_value(request().values.forecast_reported)
    assert all(
        "WIS" not in label.text() and "Brier" not in label.text()
        for label in screen.findChildren(QLabel)
    )
    saved = []
    screen.prediction_created.connect(saved.append)
    screen.submit()
    assert len(saved) == 1, screen.error.text()
    assert screen.question.text() == ""
    initial = saved[0]
    assert initial.background == "Beside the house; check with the phone camera"
    assert initial.rationale == "Compared it to the roof"
    assert initial.resolution_criteria is None
    assert initial.record.recorded_at == initial.record.answer_recorded_at
    dialog = OneShotEditDialog(operations, initial, correction=True)
    qtbot.addWidget(dialog)
    if numeric:
        dialog.form.actual.setText("3")
    else:
        dialog.form.probability.setValue(20)
    dialog.note.setText("Phone transcription")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )
    dialog.submit()
    assert operations.one_shots.get(initial.prediction_id) == initial
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
    )
    dialog.submit()
    corrected = operations.one_shots.get(initial.prediction_id)
    assert len(corrected.record.corrections) == 1, dialog.error.text()
    assert corrected.record.original == initial.record.original
    assert operations.one_shots.score(corrected) != operations.one_shots.score(initial)


def test_main_window_one_shot_route_defaults_and_detail(app, qtbot):
    _, _, operations = app
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("New Prediction")
    assert window._creation_stack.currentWidget() is window._new_prediction_screen
    window.findChild(QPushButton, "newOneShotButton").click()
    screen = window._one_shot_creation_screen
    assert window._creation_stack.currentWidget() is screen
    screen.question.setText("Tree?")
    screen.deadline_button.click()
    assert window._creation_stack.currentWidget() is window._new_prediction_screen
    window.findChild(QPushButton, "newOneShotButton").click()
    assert screen.question.text() == "Tree?"
    screen.submit()
    assert window.current_screen_name == "Journal"
    window._open_prediction(1)
    detail = window._prediction_detail_host._one_shot_detail
    assert detail.isVisible()
    assert "Answer Pending" in {label.text() for label in detail.findChildren(QLabel)}
    assert detail.answer_button.isVisible()
    assert detail.correct_button.isVisible()
    assert detail.edit_button.isVisible()
    assert not detail.scorecard.isVisible()
    detail.open_values(correction=False)
    dialog = detail._dialog
    assert dialog.form.forecast_fields.isHidden()
    dialog.reject()
    assert operations.one_shots.get(1).record.effective.answer is None
    pending = operations.one_shots.get(1)
    resolved = operations.one_shots.add_answer(
        pending, replace(pending.record.effective, answer=BinaryOutcome.YES)
    )
    detail.show_prediction(resolved)
    qtbot.waitUntil(detail.correct_button.isVisible)
    assert detail.edit_button.isVisible()
    assert not detail.answer_button.isVisible()
    qtbot.waitUntil(detail.scorecard.isVisible)
    assert detail.add_postmortem_button.isVisible()
    assert detail.skip_postmortem_button.isVisible()
    assert "Correct Transcription" in [
        action.text() for action in detail.more_button.menu().actions()
    ]
    assert not any(
        button.text() == "Correct Transcription"
        for button in detail.findChildren(QPushButton)
    )
    window.navigate_to("Predictions")
    window.navigate_to("Dashboard")
    window.navigate_to("New Prediction")
    assert window._creation_stack.currentWidget() is window._new_prediction_screen


@pytest.mark.parametrize("numeric", [False, True])
def test_one_shot_results_hierarchy_and_keyboard_disclosures(app, qtbot, numeric):
    _, _, operations = app
    prediction = operations.one_shots.create(request(numeric))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.resize(1200, 850)
    window.show()
    window._open_prediction(prediction.prediction_id)
    screen = window._prediction_detail_host._one_shot_detail
    qtbot.waitUntil(lambda: screen.scorecard.width() > 300)
    assert screen.scorecard.parentWidget() is screen.answer_panel.parentWidget()
    assert screen.scorecard.geometry().top() > screen.answer_panel.geometry().bottom()
    assert screen.scorecard.width() >= screen.results.body.width() - 2
    assert (
        screen.score_value.font().pointSizeF()
        > screen.answer_result.font().pointSizeF()
    )
    assert operations.one_shots.get(prediction.prediction_id) == prediction
    for name in (
        "oneShotTimelineDisclosure",
        "oneShotRecordedFactsDisclosure",
        "oneShotCorrectionHistoryDisclosure",
    ):
        section = screen.findChild(QWidget, name)
        toggle = section.disclosure_button
        assert isinstance(toggle, QToolButton)
        assert toggle.width() < section.width()
        assert not toggle.isChecked()
        screen.workspace.ensureWidgetVisible(toggle)
        toggle.setFocus()
        qtbot.keyClick(toggle, Qt.Key.Key_Space)
        assert toggle.isChecked()
        assert section.disclosure_body.isVisible()
        assert toggle.arrowType() is Qt.ArrowType.DownArrow
        qtbot.keyClick(toggle, Qt.Key.Key_Space)
        assert not section.disclosure_body.isVisible()


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("font_size", [9, 15])
def test_expanded_one_shot_facts_keep_flat_alignment_and_complete_wrapped_text(
    app, qtbot, qapp, numeric, font_size
):
    _, clock, operations = app
    initial = operations.one_shots.create(request(numeric))
    clock.instant += timedelta(minutes=1)
    corrected = operations.one_shots.correct(
        initial,
        replace(
            initial.record.effective,
            answer=FixedPrecisionValue(100, 2) if numeric else BinaryOutcome.NO,
            resolution_notes="A detailed measurement explanation. " * 25,
        ),
        note="A copied fact was repaired after checking the source. " * 20,
    )
    original_font = QFont(qapp.font())
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    try:
        qapp.setFont(QFont("Segoe UI", font_size))
        window._open_prediction(corrected.prediction_id)
        screen = window._prediction_detail_host._one_shot_detail
        panels = []
        for name in ("oneShotRecordedFacts", "oneShotCorrectionHistory"):
            disclosure = screen.findChild(QWidget, name + "Disclosure")
            disclosure.disclosure_button.setChecked(True)
            panels.append(disclosure.disclosure_body)
        for width in (1200, 760):
            window.resize(width, 850)
            qtbot.wait(50)
            for panel in panels:
                margins = panel.layout().contentsMargins()
                assert margins.isNull()
                inset = panel.contentsRect()
                for label in panel.findChildren(QLabel):
                    if label.isVisible():
                        bounds = QRect(label.mapTo(panel, QPoint()), label.size())
                        assert inset.contains(bounds), (
                            label.text()[:60],
                            bounds,
                            inset,
                        )
                        assert label.height() >= label.heightForWidth(label.width())
            assert screen.workspace.overview.horizontalScrollBar().maximum() == 0
            assert screen.workspace.horizontalScrollBar().maximum() == 0
        text = "\n".join(label.text() for label in panels[1].findChildren(QLabel))
        assert all(
            heading in text for heading in ("Original Saved Facts", "Before", "After")
        )
        assert corrected.record.effective.resolution_notes in text
        assert corrected.record.corrections[-1].note in text
        assert operations.one_shots.get(corrected.prediction_id) == corrected
    finally:
        qapp.setFont(original_font)


@pytest.mark.parametrize("numeric", [False, True])
def test_one_shot_skip_is_settled_and_later_reflection_preserves_completion(
    app, qtbot, monkeypatch, numeric
):
    _, clock, operations = app
    prediction = operations.one_shots.create(request(numeric))
    score = operations.one_shots.score(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window._open_prediction(prediction.prediction_id)
    screen = window._prediction_detail_host._one_shot_detail
    assert screen.add_postmortem_button.isVisible()
    assert not screen.later_postmortem_action.isVisible()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Cancel
    )
    screen.skip_postmortem_button.click()
    assert operations.one_shots.get(prediction.prediction_id) == prediction
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    clock.instant += timedelta(minutes=1)
    screen.skip_postmortem_button.click()
    skipped = operations.one_shots.get(prediction.prediction_id)
    completion = skipped.postmortem_completion
    assert completion is not None
    assert screen.add_postmortem_button.isHidden()
    assert screen.skip_postmortem_button.isHidden()
    assert screen.later_postmortem_action.isVisible()
    assert (
        screen.findChild(QLabel, "oneShotPostmortemCompletion")
        .text()
        .startswith("Postmortem Skipped")
    )
    assert not operations.get_dashboard().needs_postmortem_predictions
    screen.later_postmortem_action.trigger()
    assert screen.workspace.inline
    screen.workspace.editor.reject()
    assert operations.one_shots.get(prediction.prediction_id) == skipped
    assert screen.add_postmortem_button.isHidden()
    assert screen.later_postmortem_action.isVisible()
    screen.later_postmortem_action.trigger()
    screen.workspace.editor.body_input.setPlainText("A deliberate later reflection.")
    clock.instant += timedelta(minutes=1)
    screen.workspace.editor.submit()
    saved = operations.one_shots.get(prediction.prediction_id)
    assert saved.record.original == prediction.record.original
    assert saved.postmortem_completion == completion
    assert saved.record.effective.postmortem == "A deliberate later reflection."
    assert operations.one_shots.score(saved) == score
    assert not any(
        "Uses effective corrected facts" in label.text()
        for label in screen.scorecard.findChildren(QLabel)
    )
    assert screen.add_postmortem_button.text() == "Edit Postmortem"
    qtbot.waitUntil(screen.add_postmortem_button.isVisible)
    assert not screen.later_postmortem_action.isVisible()
    assert (
        screen.findChild(QLabel, "oneShotPostmortemCompletion")
        .text()
        .startswith("Previously Skipped")
    )
    assert not operations.get_dashboard().needs_postmortem_predictions


def test_desktop_invalid_numeric_input_retains_draft_and_cancels(app, qtbot):
    _, _, operations = app
    screen = OneShotCreationScreen(operations)
    qtbot.addWidget(screen)
    screen.question.setText("Tree?")
    screen.form.type_input.setCurrentIndex(1)
    screen.form.unit.setText("m")
    screen.form.constraint.setCurrentIndex(2)
    for value in screen.form.quantiles.inputs.values():
        value.setText("1.2")
    screen.submit()
    assert screen.error.text()
    assert screen.question.text() == "Tree?"
    assert not operations.browse_predictions().predictions
    screen.cancel()
    assert screen.question.text() == ""
    assert not operations.browse_predictions().predictions


def test_failed_search_refresh_rolls_back_creation_and_correction(
    app, qtbot, monkeypatch
):
    _, _, operations = app
    original = operations.one_shots.create(request())

    def fail_refresh(_connection):
        raise SearchIndexRepairRequiredError("Forced refresh failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            "reckonsolve.data.database.refresh_pending_search_documents", fail_refresh
        )
        with pytest.raises(ApplicationError, match="Forced refresh"):
            operations.one_shots.correct(
                original, replace(original.record.effective, probability_percent=20)
            )
        screen = OneShotCreationScreen(operations)
        qtbot.addWidget(screen)
        screen.question.setText("Keep this draft")
        screen.form.has_answer.setChecked(True)
        screen.form.outcome.setCurrentIndex(1)
        screen.submit()
        assert "Forced refresh" in screen.error.text()
        assert screen.question.text() == "Keep this draft"
    assert len(operations.browse_predictions().predictions) == 1
    assert operations.one_shots.get(original.prediction_id) == original


def test_lock_failure_is_clear_and_changes_nothing(app):
    database, _, operations = app
    with database.transaction() as connection:
        connection.execute("PRAGMA busy_timeout = 0")
    other = Database.open(database.path)
    try:
        with other.transaction(), pytest.raises(ApplicationError, match="locked"):
            operations.one_shots.create(request())
        assert not operations.browse_predictions().predictions
    finally:
        other.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_cli_save_with_answer_and_reported_minutes(tmp_path, numeric):
    path = tmp_path / "answered.sqlite3"
    forecast = (
        ["Tree?", "m", "2", "w", "1", "1", "1", "1", "1"]
        if numeric
        else ["Tree?", "80"]
    )
    # The same approximate minute and an optional offset are metadata, not a cutoff.
    reported = ["2026-09-20 12:05", "y", "-07:00"]
    code, output, error = cli(
        path,
        ["create", "numeric" if numeric else "binary", "--one-shot"],
        [
            *forecast,
            *reported,
            "Same tree, phone app",
            "y",
            "1" if numeric else "yes",
            *reported,
            "",
            "",
            "n",
            "y",
        ],
    )
    assert code == 0, error
    assert "(approximate)" in output
    assert ("WIS: 0" if numeric else "Brier: 0.04") in output
    assert output.index("Save this One-Shot?") < output.index(
        "WIS:" if numeric else "Brier:"
    )
    database = Database.open(path)
    try:
        detail = PredictionOperations(database).one_shots.get(1)
        assert detail.record.recorded_at == detail.record.answer_recorded_at
        assert (
            detail.record.effective.forecast_reported
            == detail.record.effective.reveal_reported
        )
    finally:
        database.close()


@pytest.mark.parametrize(
    "wall",
    [
        (2026, 3, 8, 2, 30),
        (2026, 11, 1, 1, 30),
        (2026, 9, 27, 0, 0),
        (2026, 9, 27, 12, 0),
        (2026, 9, 27, 23, 59),
    ],
)
def test_reported_picker_preserves_wall_minutes_and_optional_draft(qtbot, wall):
    # A missing/repeated local hour is still valid documentary data.
    clock = Clock()
    picker = ReportedTimeInput("Forecast finalized", clock=clock)
    qtbot.addWidget(picker)
    picker.show()
    assert picker.value() is None
    assert not picker.controls.isVisible()
    picker.enabled.setChecked(True)
    expected = clock.now().astimezone().replace(tzinfo=None, second=0, microsecond=0)
    assert picker.value() == ReportedTime(expected)
    assert picker.date.calendarPopup()
    picker.date.setDate(QDate(*wall[:3]))
    picker.time.setTime(QTime(*wall[3:]))
    picker.approximate.setChecked(True)
    picker.use_offset.setChecked(True)
    picker.offset.setText("-07:00")
    reported = ReportedTime(datetime(*wall), True, -420)  # noqa: DTZ001
    assert picker.value() == reported
    picker.enabled.setChecked(False)
    assert picker.value() is None
    picker.enabled.setChecked(True)
    assert picker.value() == reported
    picker.set_value(None)
    assert picker.value() is None
    picker.set_value(reported)
    assert picker.value() == reported
    picker.use_offset.setChecked(False)
    assert picker.value() == replace(reported, offset_minutes=None)


def test_one_shot_metadata_preserves_old_expected_date_without_attention(app, qtbot):
    _, _, operations = app
    old_date = date(2026, 9, 20)
    pending = operations.one_shots.create(
        replace(request(False, False), expected_resolution=old_date)
    )
    dialog = EditPredictionDetailsDialog(operations, pending)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.expected_resolution_toggle.isVisible()
    assert not dialog.expected_resolution_input.isVisible()
    dialog.background_input.setPlainText("A new background note")
    dialog.submit()
    saved = operations.one_shots.get(pending.prediction_id)
    assert saved.background == "A new background note"
    assert saved.expected_resolution == old_date
    assert saved.resolution_criteria == pending.resolution_criteria
    assert not operations.get_dashboard().ready_to_resolve_predictions
    assert not operations.browse_predictions(
        attention=ArchiveAttention.READY_TO_RESOLVE
    ).predictions


def test_cli_optional_one_shot_details_without_expected_resolution(tmp_path):
    path = tmp_path / "details.sqlite3"
    code, output, error = cli(
        path,
        ["create", "binary", "--one-shot"],
        [
            "Tree?",
            "80",
            "",
            "Near the park; check with the phone app",
            "n",
            "y",
            "Looks taller than the house",
            "outdoors, trees",
            "y",
        ],
    )
    assert code == 0, error
    assert "Expected resolution" not in output
    database = Database.open(path)
    try:
        saved = PredictionOperations(database).one_shots.get(1)
        assert saved.rationale == "Looks taller than the house"
        assert saved.background == "Near the park; check with the phone app"
        assert saved.resolution_criteria is None
        assert set(saved.tags) == {"outdoors", "trees"}
        assert saved.expected_resolution is None
    finally:
        database.close()
