"""Real M47 form behavior without either personal database or desktop input."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import QDialogButtonBox, QLabel

from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import ForecastCohort
from reckonsolve.ui.exact_deadline_input import ExactDeadlineInput
from reckonsolve.ui.screens import (
    EditPredictionDetailsDialog,
    NewPredictionScreen,
    PredictionDetailScreen,
)


@dataclass
class Clock:
    def now(self):
        return datetime(2026, 9, 10, 18, tzinfo=UTC)


@pytest.fixture
def operations(tmp_path):
    database = Database.open(tmp_path / "forms.sqlite3")
    yield PredictionOperations(database, Clock(), UTC)
    database.close()


def set_deadline(widget):
    widget.toggle.setChecked(True)
    widget.editor.setDate(QDate(2026, 11, 1))
    widget.editor.setTime(QTime(1, 30))
    widget.offset.setText("-07:00")


def test_creation_requires_explicit_deadline_and_reset_does_not_guess_another(
    qtbot, operations
):
    screen = NewPredictionScreen(operations)
    qtbot.addWidget(screen)
    screen.show()
    screen.question_input.setText("An exact Binary commitment?")
    screen.submit()
    assert "Set an exact Forecast Deadline" in screen.form_error.text()
    assert not operations.browse_predictions().predictions
    assert not screen.exact_deadline.toggle.isChecked()
    set_deadline(screen.exact_deadline)
    screen.submit()
    prediction = operations.get_prediction(1)
    assert prediction.forecast_contract.cohort is ForecastCohort.TRAJECTORY_BINARY
    assert prediction.forecast_contract.forecast_deadline.instant == datetime(
        2026, 11, 1, 8, 30, tzinfo=UTC
    )
    assert not screen.exact_deadline.toggle.isChecked()
    assert screen.question_input.text() == ""


def test_explicit_offsets_disambiguate_repeated_dst_hour(qtbot):
    widget = ExactDeadlineInput()
    qtbot.addWidget(widget)
    set_deadline(widget)
    assert widget.value() == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    widget.offset.setText("-08:00")
    assert widget.value() == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    for invalid in ("", "local", "+24:00", "-07:60", "+1:00"):
        widget.offset.setText(invalid)
        with pytest.raises(ValidationError):
            widget.value()


def test_deadline_editor_commits_the_displayed_minute_without_hidden_seconds(qtbot):
    widget = ExactDeadlineInput()
    qtbot.addWidget(widget)
    assert widget.editor.time().second() == 0
    assert widget.editor.displayFormat() == "yyyy-MM-dd HH:mm"
    set_deadline(widget)
    widget.editor.setTime(QTime(1, 30, 59, 987))
    assert widget.value() == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)


def test_timeline_displays_minutes_but_preserves_exact_timestamp(qtbot, tmp_path):
    instant = datetime(2026, 9, 10, 18, 24, 37, 123456, tzinfo=UTC)

    class PreciseClock:
        def now(self):
            return instant

    database = Database.open(tmp_path / "precise.sqlite3")
    operations = PredictionOperations(database, PreciseClock(), UTC)
    prediction = operations.create_prediction(
        "Short timestamps?", 50, forecast_deadline=datetime(2026, 9, 11, tzinfo=UTC)
    )
    screen = PredictionDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(prediction)
    timestamp = screen.findChild(
        QLabel, f"forecastRevisionTimestamp{prediction.current_revision_id}"
    )
    assert timestamp.text() == instant.astimezone().strftime("%b %d, %Y at %H:%M")
    assert timestamp.toolTip() == instant.astimezone().isoformat(sep=" ")
    assert operations.list_timeline(prediction.prediction_id)[0].created_at == instant
    database.close()


def test_new_binary_edit_keeps_deadline_readonly_and_can_save_metadata(
    qtbot, operations
):
    original = operations.create_prediction(
        "Metadata?", 50, forecast_deadline=datetime(2026, 9, 11, tzinfo=UTC)
    )
    dialog = EditPredictionDetailsDialog(operations, original)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.forecast_deadline_toggle.isVisible()
    assert "permanent" in dialog.exact_deadline_context.text()
    dialog.background_input.setPlainText("Added background")
    dialog.submit()
    updated = operations.get_prediction(original.prediction_id)
    assert updated.background == "Added background"
    assert updated.forecast_contract == original.forecast_contract
    assert updated.current_revision_id == original.current_revision_id
    assert updated.latest_revision_at == original.latest_revision_at


def test_cancel_edit_or_revision_does_not_write_history(qtbot, operations):
    original = operations.create_prediction(
        "Cancel?", 50, forecast_deadline=datetime(2026, 9, 11, tzinfo=UTC)
    )
    screen = PredictionDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(original)
    screen.show()
    assert "TRAJECTORY" in screen.forecast_type.text()
    assert "permanent" in screen.forecast_deadline.text()
    assert screen.resolve_button.isEnabled()
    screen.open_revise_forecast()
    dialog = screen._revision_dialog
    assert dialog is not None
    dialog.reject()
    edit = EditPredictionDetailsDialog(operations, original)
    qtbot.addWidget(edit)
    edit.show()
    edit.question_input.setText("Discard this change")
    qtbot.mouseClick(
        edit.buttons.button(QDialogButtonBox.StandardButton.Cancel),
        Qt.MouseButton.LeftButton,
    )
    assert operations.get_prediction(original.prediction_id) == original
    assert len(operations.list_timeline(original.prediction_id)) == 1
