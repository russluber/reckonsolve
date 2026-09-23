"""Calendar choices must produce the exact commitment visible to the user."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest
from PySide6.QtCore import QDate, Qt, QTime, QTimeZone
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QScrollArea

from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.ui.exact_deadline_input import ExactDeadlineInput
from reckonsolve.ui.screens import NewPredictionScreen


@dataclass
class Clock:
    instant: datetime = datetime(2026, 10, 30, 18, 14, 35, tzinfo=UTC)

    def now(self):
        return self.instant


@pytest.fixture
def picker(qtbot):
    widget = ExactDeadlineInput(
        clock=Clock(), time_zone=QTimeZone(b"America/Los_Angeles")
    )
    qtbot.addWidget(widget)
    widget.show()
    return widget


@pytest.mark.parametrize(
    "days, expected",
    [
        (0, datetime(2026, 10, 31, 6, 59, tzinfo=UTC)),
        (1, datetime(2026, 11, 1, 6, 59, tzinfo=UTC)),
        (7, datetime(2026, 11, 7, 7, 59, tzinfo=UTC)),
        (30, datetime(2026, 11, 30, 7, 59, tzinfo=UTC)),
    ],
)
def test_shortcuts_use_calendar_days_and_target_dates_dst(
    picker, qtbot, days, expected
):
    assert not picker.is_set
    assert picker.editor.isHidden() or not picker.editor.isVisible()
    assert picker.findChild(QCheckBox, "exactDeadlineToggle") is None
    with pytest.raises(ValidationError, match="Set an exact"):
        picker.value()
    qtbot.mouseClick(picker.preset_buttons[days], Qt.MouseButton.LeftButton)
    assert picker.value() == expected
    assert picker.editor.time() == QTime(23, 59)
    assert "11:59 PM" in picker.summary.text()
    assert ("UTC-07:00" if days < 7 else "UTC-08:00") in picker.summary.text()


def test_year_rollover_click_time_and_no_moving_deadline(qtbot):
    clock = Clock(datetime(2027, 1, 1, 4, tzinfo=UTC))  # Dec 31 in California
    widget = ExactDeadlineInput(
        clock=clock, time_zone=QTimeZone(b"America/Los_Angeles")
    )
    qtbot.addWidget(widget)
    widget.choose_preset(1)
    assert widget.value() == datetime(2027, 1, 2, 7, 59, tzinfo=UTC)
    clock.instant += timedelta(days=2)
    assert widget.value() == datetime(2027, 1, 2, 7, 59, tzinfo=UTC)
    widget.choose_preset(1)
    assert widget.value() == datetime(2027, 1, 4, 7, 59, tzinfo=UTC)


def test_custom_preserves_selection_and_reset_is_unset(picker, qtbot):
    qtbot.mouseClick(picker.custom_button, Qt.MouseButton.LeftButton)
    picker.editor.setDate(QDate(2027, 6, 21))
    picker.editor.setTime(QTime(14, 37, 58, 111))
    assert picker.value() == datetime(2027, 6, 21, 21, 37, tzinfo=UTC)
    qtbot.mouseClick(picker.custom_button, Qt.MouseButton.LeftButton)
    assert picker.value() == datetime(2027, 6, 21, 21, 37, tzinfo=UTC)
    picker.reset()
    assert "Not set" in picker.summary.text()
    assert not picker.is_set
    with pytest.raises(ValidationError):
        picker.value()


def test_gap_is_not_silently_shifted(picker):
    picker.choose_custom()
    picker.editor.setDate(QDate(2027, 3, 14))
    picker.editor.setTime(QTime(2, 30))
    assert picker.editor.time() == QTime(2, 30)
    assert "does not exist" in picker.summary.text()
    with pytest.raises(ValidationError, match="does not exist"):
        picker.value()
    picker.editor.setTime(QTime(3, 30))
    assert picker.value() == datetime(2027, 3, 14, 10, 30, tzinfo=UTC)


def test_fold_requires_explicit_occurrence_and_resets_for_changed_time(picker):
    picker.choose_custom()
    picker.editor.setDate(QDate(2026, 11, 1))
    picker.editor.setTime(QTime(1, 30))
    assert picker.occurrence.isVisible()
    with pytest.raises(ValidationError, match="occurs twice"):
        picker.value()
    picker.occurrence.setCurrentIndex(1)
    assert picker.value() == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    picker.occurrence.setCurrentIndex(2)
    assert picker.value() == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    picker.editor.setTime(QTime(1, 31))
    with pytest.raises(ValidationError, match="occurs twice"):
        picker.value()
    picker.editor.setTime(QTime(2, 30))
    assert not picker.occurrence.isVisible()
    assert picker.value() == datetime(2026, 11, 1, 10, 30, tzinfo=UTC)


def test_explicit_offset_and_return_to_local(picker):
    picker.choose_preset(7)
    local = picker.value()
    picker.use_offset.setChecked(True)
    with pytest.raises(ValidationError, match="UTC offset"):
        picker.value()
    picker.offset.setText("+05:45")
    assert picker.value() == datetime(2026, 11, 6, 18, 14, tzinfo=UTC)
    assert "Explicit offset" in picker.summary.text()
    picker.use_offset.setChecked(False)
    assert picker.value() == local
    picker.use_offset.setChecked(True)
    picker.choose_preset(7)
    assert not picker.use_offset.isChecked()
    assert picker.value() == local


@pytest.mark.parametrize("numeric", [False, True])
def test_shared_draft_creation_failure_reset_and_restart(
    qtbot, tmp_path, monkeypatch, numeric
):
    clock = Clock()
    monkeypatch.setattr(
        "reckonsolve.ui.screens.ExactDeadlineInput",
        partial(
            ExactDeadlineInput, clock=clock, time_zone=QTimeZone(b"America/Los_Angeles")
        ),
    )
    path = tmp_path / "deadline.sqlite3"
    database = Database.open(path)
    try:
        operations = PredictionOperations(database, clock, UTC)
        screen = NewPredictionScreen(operations)
        qtbot.addWidget(screen)
        screen.show()
        screen.question_input.setText("What will the station report?")
        screen.numeric_unit_input.setText("degrees")
        screen.numeric_constraint_input.setCurrentIndex(1)
        for level, value in zip((5, 25, 50, 75, 95), (1, 2, 3, 4, 5)):
            screen.quantile_input.inputs[level].setText(str(value))
        screen.exact_deadline.choose_preset(7)
        chosen = screen.exact_deadline.value()
        screen.prediction_type_input.setCurrentIndex(1)
        assert screen.numeric_exact_deadline.value() == chosen
        screen.prediction_type_input.setCurrentIndex(0)
        assert screen.exact_deadline.value() == chosen
        screen.prediction_type_input.setCurrentIndex(int(numeric))
        screen.exact_deadline.editor.setDate(QDate(2025, 1, 1))
        screen.submit()
        assert screen.form_error.isVisible()
        assert not operations.browse_predictions().predictions
        assert screen.question_input.text() == "What will the station report?"
        screen.exact_deadline.choose_preset(7)
        # A future deadline may expire while the form is open. Commit must recheck.
        clock.instant = chosen
        screen.submit()
        assert not operations.browse_predictions().predictions
        clock.instant = datetime(2026, 10, 30, 18, 14, tzinfo=UTC)
        screen.expected_resolution_toggle.setChecked(True)
        screen.expected_resolution_input.setDate(QDate(2028, 1, 1))
        screen.submit()
        assert not screen.exact_deadline.is_set
        assert screen.question_input.text() == ""
        rows = operations.browse_predictions().predictions
        assert len(rows) == 1
        prediction_id = rows[0].prediction_id
    finally:
        database.close()
    reopened = Database.open(path)
    try:
        operations = PredictionOperations(reopened, clock, UTC)
        prediction = (
            operations.get_numeric_prediction(prediction_id)
            if numeric
            else operations.get_prediction(prediction_id)
        )
        assert prediction.forecast_contract.forecast_deadline.instant == chosen
        assert str(prediction.expected_resolution) == "2028-01-01"
    finally:
        reopened.close()


@pytest.mark.parametrize("points", [9, 14])
def test_shortcuts_wrap_without_clipping_or_overlap(qtbot, points):
    picker = ExactDeadlineInput(clock=Clock(), time_zone=QTimeZone.utc())
    picker.setFont(QFont("Segoe UI", points))
    qtbot.addWidget(picker)
    scroll = QScrollArea()
    qtbot.addWidget(scroll)
    scroll.setWidgetResizable(True)
    scroll.setWidget(picker)
    scroll.show()
    picker.choose_preset(7)
    for width in (960, 360, 520, 960):
        scroll.resize(width, 600)
        qtbot.wait(20)
        assert scroll.horizontalScrollBar().maximum() == 0
        buttons = [*picker.preset_buttons.values(), picker.custom_button]
        for index, button in enumerate(buttons):
            assert picker.shortcut_row.rect().contains(button.geometry())
            assert button.width() >= button.sizeHint().width()
            for other in buttons[index + 1 :]:
                assert not button.geometry().intersects(other.geometry())
        assert not picker.shortcut_row.geometry().intersects(
            picker.edit_controls.geometry()
        )
