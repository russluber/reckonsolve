"""M48 desktop/CLI terminal workflows use the same exact persisted contract."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QMessageBox

from reckonsolve import cli
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.ui.effective_time_input import EffectiveTimeInput
from reckonsolve.ui.screens import (
    CorrectBinaryResolutionDialog,
    PredictionDetailScreen,
    ResolvePredictionDialog,
)
from reckonsolve.ui.visual_system import install_visual_system

START = datetime(2026, 9, 10, 12, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = START

    def now(self):
        return self.instant


@pytest.fixture
def active(tmp_path):
    database = Database.open(tmp_path / "forms.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    prediction = operations.create_prediction(
        "Will this finish?", 20, forecast_deadline=START + timedelta(hours=4)
    )
    clock.instant += timedelta(hours=1)
    prediction = operations.revise_forecast(
        prediction.prediction_id,
        90,
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    clock.instant += timedelta(hours=2)
    yield database, clock, operations, prediction
    database.close()


def set_time(widget, instant):
    widget.use_now.setChecked(False)
    widget.editor.setDate(QDate(instant.year, instant.month, instant.day))
    widget.editor.setTime(
        QTime(instant.hour, instant.minute, instant.second, instant.microsecond // 1000)
    )
    widget.offset.setText("+00:00")


def resolve(operations, prediction, effective_at):
    return operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=effective_at,
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )


def test_resolve_now_and_scorecard_progressive_diagnostics(qtbot, active):
    _, clock, operations, prediction = active
    dialog = ResolvePredictionDialog(operations, prediction)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.effective_time.use_now.isChecked()
    assert not dialog.effective_time.editor.isEnabled()
    dialog.outcome_yes.setChecked(True)
    dialog.submit()
    resolved = operations.get_prediction(prediction.prediction_id)
    assert (
        resolved.resolution.effective_resolution_at
        == resolved.resolution.resolved_at
        == clock.instant
    )
    screen = PredictionDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(resolved)
    screen.show()
    assert screen.scorecard_section.isVisible()
    assert "Trajectory Brier" in screen.scorecard_brier.text()
    assert not screen.trajectory_diagnostics.isChecked()
    assert "Outcome became knowable" in screen.resolution_resolved_at.text()
    assert "Recorded at" in screen.resolution_resolved_at.text()
    screen.trajectory_diagnostics.setChecked(True)
    texts = "\n".join(
        label.text() for label in screen.trajectory_diagnostics.findChildren(QLabel)
    )
    assert "Initial Brier" in texts
    assert "Final Brier" in texts
    assert "Updating Gain" in texts
    assert "Active Forecast Fraction" in texts
    assert "mechanical hindsight" in texts


def test_explicit_resolution_rejects_future_and_displays_excluded_history(
    qtbot, active
):
    _, clock, operations, prediction = active
    dialog = ResolvePredictionDialog(operations, prediction)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.outcome_yes.setChecked(True)
    set_time(dialog.effective_time, clock.instant + timedelta(hours=1))
    dialog.submit()
    assert dialog.form_error.isVisible()
    assert not operations.get_prediction(prediction.prediction_id).resolution
    set_time(dialog.effective_time, START + timedelta(hours=1))
    dialog.submit()
    screen = PredictionDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(operations.get_prediction(prediction.prediction_id))
    screen.show()
    assert "Final eligible forecast: 20%" in screen.scorecard_forecast.text()
    assert (
        str(prediction.current_revision_id) in screen.scorecard_correction_notice.text()
    )
    assert screen.probability_history_chart.revision_count == 2
    assert (
        screen.findChild(
            QLabel, f"forecastRevisionScoringExclusion{prediction.current_revision_id}"
        )
        is not None
    )
    assert len(operations.list_timeline(prediction.prediction_id)) == 2


def test_cancel_resolution_and_correction_never_write(qtbot, active, monkeypatch):
    _, _, operations, prediction = active
    dialog = ResolvePredictionDialog(operations, prediction)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.outcome_no.setChecked(True)
    dialog.reject()
    assert operations.get_prediction(prediction.prediction_id).resolution is None
    resolve(operations, prediction, START + timedelta(hours=2))
    history = operations.get_binary_resolution_history(prediction.prediction_id)
    correction = CorrectBinaryResolutionDialog(operations, history)
    correction.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(correction)
    correction.show()
    set_time(correction.effective_time, START)
    correction.submit()
    assert "Explain why" in correction.form_error.text()
    correction.reason_input.setText("Publication preceded creation")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Cancel
    )
    correction.submit()
    assert operations.get_binary_resolution_history(prediction.prediction_id) == history
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Yes
    )
    correction.submit()
    screen = PredictionDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(operations.get_prediction(prediction.prediction_id))
    screen.show()
    assert screen.scorecard_brier.text() == "Not scored"
    assert "at or before" in screen.scorecard_guidance.text()
    assert not screen.trajectory_diagnostics.isVisible()
    assert "Effective resolution time" in "\n".join(
        label.text() for label in screen.resolution_history.findChildren(QLabel)
    )


def test_text_only_correction_retains_hidden_microsecond_precision(
    qtbot, active, monkeypatch
):
    _, _, operations, prediction = active
    instant = START + timedelta(hours=2, seconds=37, microseconds=123456)
    resolve(operations, prediction, instant)
    history = operations.get_binary_resolution_history(prediction.prediction_id)
    dialog = CorrectBinaryResolutionDialog(operations, history)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.effective_time.editor.displayFormat() == "yyyy-MM-dd HH:mm"
    assert dialog.effective_time.value() == instant
    dialog.effective_time.precise.setChecked(True)
    assert dialog.effective_time.value() == instant
    dialog.effective_time.precise.setChecked(False)
    dialog.notes_input.setPlainText("Later evidence link")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Yes
    )
    dialog.submit()
    updated = operations.get_binary_resolution_history(prediction.prediction_id)
    assert updated.effective.effective_resolution_at == instant
    assert updated.corrections[-1].changed_fields == ("resolution_notes",)
    assert updated.original == history.original


def test_effective_time_editor_offsets_and_optional_precision(qtbot):
    widget = EffectiveTimeInput(None)
    qtbot.addWidget(widget)
    set_time(widget, START.replace(second=42, microsecond=123000))
    widget.offset.setText("+05:45")
    assert widget.value() == START - timedelta(hours=5, minutes=45)
    widget.precise.setChecked(True)
    assert widget.value() == START - timedelta(hours=5, minutes=45) + timedelta(
        seconds=42, microseconds=123000
    )


@pytest.mark.parametrize("width", [450, 600, 850])
def test_styled_effective_time_forms_do_not_clip_or_overlap(qtbot, qapp, active, width):
    _, _, operations, prediction = active
    original_font = qapp.font()
    qapp.setFont(QFont("Segoe UI", 9))
    try:
        resolve_dialog = ResolvePredictionDialog(operations, prediction)
        resolve(operations, prediction, START + timedelta(hours=2))
        correction_dialog = CorrectBinaryResolutionDialog(
            operations,
            operations.get_binary_resolution_history(prediction.prediction_id),
        )
        for dialog in (resolve_dialog, correction_dialog):
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            qtbot.addWidget(dialog)
            install_visual_system(dialog)
            dialog.resize(width, 400)
            dialog.show()
            qtbot.waitUntil(
                lambda dialog=dialog: (
                    dialog.effective_time.editor.height()
                    >= dialog.effective_time.editor.minimumSizeHint().height()
                )
            )
            field = dialog.effective_time
            index = dialog.layout().indexOf(field)
            next_widget = next(
                dialog.layout().itemAt(i).widget()
                for i in range(index + 1, dialog.layout().count())
                if dialog.layout().itemAt(i).widget() is not None
                and dialog.layout().itemAt(i).widget().isVisible()
            )
            assert field.geometry().bottom() < next_widget.geometry().top()
            assert field.precise.geometry().bottom() < field.height()
            assert field.offset.height() >= field.offset.minimumSizeHint().height()
            dialog.hide()
    finally:
        qapp.setFont(original_font)


@pytest.mark.parametrize("effective_text", ["now", "2026-09-10T15:00:00+05:00"])
def test_cli_resolve_and_show_share_gui_time_history_and_score(
    active, monkeypatch, effective_text
):
    database, clock, operations, prediction = active
    factory = cli.create_runtime

    def runtime(**kwargs):
        result = factory(**kwargs)
        result.operations = PredictionOperations(result.database, clock, UTC)
        return result

    monkeypatch.setattr(cli, "create_runtime", runtime)
    output, errors = StringIO(), StringIO()
    assert (
        cli.run(
            ["resolve", str(prediction.prediction_id)],
            database_path=database.path,
            stdin=StringIO(f"yes\ninvalid\n{effective_text}\nSource\nReflection\ny\n"),
            stdout=output,
            stderr=errors,
        )
        == 0
    )
    assert "exact time with an offset" in errors.getvalue()
    resolved = operations.get_prediction(prediction.prediction_id)
    expected = (
        clock.instant
        if effective_text == "now"
        else datetime(2026, 9, 10, 10, tzinfo=UTC)
    )
    assert resolved.resolution.effective_resolution_at == expected
    output = StringIO()
    assert (
        cli.run(
            ["show", str(prediction.prediction_id)],
            database_path=database.path,
            stdout=output,
            stderr=StringIO(),
        )
        == 0
    )
    rendered = output.getvalue()
    assert "Recorded at:" in rendered
    assert "Effective resolution time:" in rendered
    assert "Trajectory Brier:" in rendered
    assert "Forecast at recording (audit only)" in rendered
    if effective_text == "now":
        assert "Updating Gain:" in rendered
    else:
        assert "Unscored" in rendered
    operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.NO,
        effective_resolution_at=START + timedelta(hours=1),
        resolution_notes="Corrected source",
        postmortem="Reflection",
        correction_reason="Corrected chronology",
        expected_correction_id=None,
    )
    output = StringIO()
    assert (
        cli.run(
            ["show", str(prediction.prediction_id)],
            database_path=database.path,
            stdout=output,
            stderr=StringIO(),
        )
        == 0
    )
    assert "Corrected chronology" in output.getvalue()
    assert "Effective resolution time" in output.getvalue()
    assert "history only" in output.getvalue()


def test_cli_resolution_cancel_and_invalid_future_never_commit(active, monkeypatch):
    database, clock, operations, prediction = active
    factory = cli.create_runtime

    def runtime(**kwargs):
        result = factory(**kwargs)
        result.operations = PredictionOperations(result.database, clock, UTC)
        return result

    monkeypatch.setattr(cli, "create_runtime", runtime)
    for prompts, expected_status in (
        ("yes\n", 130),
        ("yes\nnow\n\n\nn\n", 130),
        ("yes\n2099-01-01T00:00:00Z\n\n\ny\n", 1),
    ):
        assert (
            cli.run(
                ["resolve", str(prediction.prediction_id)],
                database_path=database.path,
                stdin=StringIO(prompts),
                stdout=StringIO(),
                stderr=StringIO(),
            )
            == expected_status
        )
        assert operations.get_prediction(prediction.prediction_id).resolution is None
