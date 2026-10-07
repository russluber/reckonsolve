"""Binary and Numeric creation forms, validation, and reset behavior."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from main_window_fakes import (
    CreatePredictionCall,
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
    _set_exact_deadline,
)
from main_window_helpers import (
    operations as operations,  # noqa: PLC0414 - pytest fixture registration
)
from main_window_helpers import (
    window as window,  # noqa: PLC0414 - pytest fixture registration
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.predictions import (
    PredictionType,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    SurfaceRole,
    TextRole,
)


def test_new_prediction_form_has_integer_probability_bounds_and_focus(
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")

    assert window.focusWidget() is question
    assert probability.minimum() == 0
    assert probability.maximum() == 100
    assert probability.value() == 50
    assert probability.suffix() == "%"

    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details_content = _required_child(
        window,
        QWidget,
        "newPredictionMoreDetailsContent",
    )
    assert not more_details.isChecked()
    assert more_details_content.isHidden()


def test_m42_creation_form_uses_shared_hierarchy_and_type_aware_guidance(
    window: MainWindow,
) -> None:
    window.navigate_to("New Prediction")

    title = _required_child(window, QLabel, "newPredictionScreenTitle")
    supporting = _required_child(
        window,
        QLabel,
        "newPredictionScreenSupportingText",
    )
    panel = _required_child(window, ContentPanel, "newPredictionForecastPanel")
    create = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert supporting.property(TEXT_ROLE_PROPERTY) == TextRole.SECONDARY.value
    assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert panel.supporting_label.text() == (
        "Binary forecasts need a question, probability, and permanent exact deadline."
    )
    assert create.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value

    prediction_type = _required_child(window, QComboBox, "predictionTypeInput")
    prediction_type.setCurrentIndex(
        prediction_type.findData(PredictionType.NUMERIC.value)
    )

    assert panel.supporting_label.text() == (
        "Numeric forecasts need a question, unit, precision, value constraint, five percentiles, and permanent exact deadline."
    )


def test_numeric_creation_switches_the_forecast_form_and_displays_complete_detail(
    qtbot, tmp_path
):
    from reckonsolve.application.predictions import PredictionOperations
    from reckonsolve.data.database import Database
    from reckonsolve.ui.screens import NewPredictionScreen

    database = Database.open(tmp_path / "new-numeric.sqlite3")
    operations = PredictionOperations(database)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("New Prediction")
    screen = window.findChild(NewPredictionScreen)
    screen.prediction_type_input.setCurrentIndex(
        screen.prediction_type_input.findData("numeric")
    )
    screen.question_input.setText("How many days until a response?")
    screen.numeric_unit_input.setText("days")
    screen.numeric_precision_input.setValue(1)
    screen.numeric_constraint_input.setCurrentIndex(1)
    for level, value in {
        5: "3.0",
        25: "5.0",
        50: "7.5",
        75: "14.0",
        95: "21.0",
    }.items():
        screen.quantile_input.inputs[level].setText(value)
    screen.numeric_exact_deadline.choose_custom()
    screen.numeric_exact_deadline.use_offset.setChecked(True)
    screen.numeric_exact_deadline.editor.setDate(QDate(2099, 12, 30))
    screen.numeric_exact_deadline.offset.setText("+00:00")
    screen.tags_input.setText("offer, timing")
    screen.submit()
    assert window.current_screen_name == "Prediction Detail"
    assert (
        _required_child(window, QLabel, "numericCurrentInterval").text()
        == "90% interval: 3.0 to 21.0 days"
    )
    assert (
        "50% interval: 5.0 to 14.0"
        in _required_child(window, QLabel, "numericCurrentMedian").text()
    )
    assert _required_child(
        window, QPushButton, "resolveNumericPredictionButton"
    ).isEnabled()
    assert _required_child(
        window, QPushButton, "editNumericPredictionDetailsButton"
    ).isEnabled()
    assert set(operations.get_numeric_prediction(1).tags) == {"offer", "timing"}
    window.navigate_to("New Prediction")
    assert screen.numeric_unit_input.text() == ""
    assert all(not field.text() for field in screen.quantile_input.inputs.values())
    database.close()


def test_numeric_creation_failure_keeps_the_form_values_for_correction(qtbot, tmp_path):
    from reckonsolve.application.predictions import PredictionOperations
    from reckonsolve.data.database import Database
    from reckonsolve.ui.screens import NewPredictionScreen

    database = Database.open(tmp_path / "invalid-numeric.sqlite3")
    operations = PredictionOperations(database)
    screen = NewPredictionScreen(operations)
    qtbot.addWidget(screen)
    screen.prediction_type_input.setCurrentIndex(
        screen.prediction_type_input.findData("numeric")
    )
    screen.question_input.setText("How many days?")
    screen.numeric_unit_input.setText("days")
    screen.numeric_constraint_input.setCurrentIndex(2)
    for level, value in {5: "8", 25: "2", 50: "3", 75: "9", 95: "10"}.items():
        screen.quantile_input.inputs[level].setText(value)
    screen.numeric_exact_deadline.choose_custom()
    screen.numeric_exact_deadline.use_offset.setChecked(True)
    screen.numeric_exact_deadline.editor.setDate(QDate(2099, 12, 30))
    screen.numeric_exact_deadline.offset.setText("+00:00")
    screen.submit()
    assert screen.form_error.text()
    assert screen.quantile_input.inputs[50].text() == "3"
    assert screen.numeric_unit_input.text() == "days"
    assert not operations.browse_predictions().predictions
    database.close()


def test_more_details_date_controls_are_visually_unset_until_enabled(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(window, QComboBox, "predictionTypeInput").setCurrentIndex(1)
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialExpectedResolutionToggle",
    )
    deadline = _required_child(
        window,
        QDateEdit,
        "initialExpectedResolutionInput",
    )

    assert not deadline_toggle.isChecked()
    assert deadline.isHidden()
    qtbot.mouseClick(deadline_toggle, Qt.MouseButton.LeftButton)
    assert deadline.isVisible()
    assert deadline.date() == QDate.currentDate()


def test_complete_creation_submits_all_optional_details_once_and_resets(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will all initial details persist?"
    )
    _required_child(window, QSpinBox, "probabilityInput").setValue(73)
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Initial evidence"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Relevant background"
    )
    _required_child(
        window,
        QPlainTextEdit,
        "initialResolutionCriteriaInput",
    ).setPlainText("A published result counts.")
    expected_toggle = _required_child(
        window,
        QCheckBox,
        "initialExpectedResolutionToggle",
    )
    expected_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialExpectedResolutionInput").setDate(
        QDate(2026, 9, 15)
    )
    _required_child(window, QLineEdit, "initialTagsInput").setText(" release, desktop ")

    _set_exact_deadline(window)
    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will all initial details persist?",
            probability_percent=73,
            rationale="Initial evidence",
            background="Relevant background",
            resolution_criteria="A published result counts.",
            forecast_deadline=datetime(2099, 12, 30, 18, tzinfo=UTC),
            expected_resolution=date(2026, 9, 15),
            tags=("release", "desktop"),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert (
        _required_child(window, QLabel, "forecastRevisionRationale1").text()
        == "Initial evidence"
    )

    window.navigate_to("New Prediction")
    assert _required_child(window, QLineEdit, "questionInput").text() == ""
    assert _required_child(window, QSpinBox, "probabilityInput").value() == 50
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == ""
    )
    assert window.findChild(QCheckBox, "initialForecastDeadlineToggle") is None
    assert not expected_toggle.isChecked()
    assert _required_child(window, QLineEdit, "initialTagsInput").text() == ""
    assert not _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).isChecked()


def test_collapsing_more_details_preserves_entered_values_for_creation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will collapsed details remain part of the prediction?"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Keep this context"
    )
    more_details.setChecked(False)

    _set_exact_deadline(window)
    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls[0].background == "Keep this context"


def test_creation_failure_keeps_optional_details_for_correction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError(
        "Forecast Deadline cannot be before today."
    )
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will this invalid deadline remain editable?"
    )
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Keep me"
    )

    _set_exact_deadline(window)
    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.current_screen_name == "New Prediction"
    assert more_details.isChecked()
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == "Keep me"
    )
    error = _required_child(window, QLabel, "predictionFormError")
    assert "before today" in error.text()
    assert not error.isHidden()


def test_probability_shortcuts_are_exactly_ten_through_ninety(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    shortcuts = _required_child(window, QWidget, "probabilityShortcuts")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    buttons = shortcuts.findChildren(QPushButton)

    assert tuple(button.text() for button in buttons) == tuple(
        str(value) for value in range(10, 100, 10)
    )
    for expected, button in zip(range(10, 100, 10), buttons, strict=True):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert probability.value() == expected


@pytest.mark.parametrize("endpoint", [0, 100])
def test_probability_endpoint_note_only_appears_for_absolute_certainty(
    window: MainWindow,
    endpoint: int,
) -> None:
    probability = _required_child(window, QSpinBox, "probabilityInput")
    note = _required_child(window, QLabel, "probabilityEndpointNote")

    for ordinary_probability in (1, 50, 99):
        probability.setValue(ordinary_probability)
        assert note.isHidden()

    probability.setValue(endpoint)
    assert not note.isHidden()
    assert "absolute certainty" in note.text()


def test_missing_question_is_shown_inline_without_calling_operation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")

    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert not error.isHidden()
    assert "Enter a question" in error.text()
    assert operations.create_calls == []
    assert window.current_screen_name == "New Prediction"


def test_expected_application_failure_is_shown_inline(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError("That prediction could not be saved.")
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")
    question.setText("Will this remain on the form?")

    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert error.text() == "That prediction could not be saved."
    assert not error.isHidden()
    assert question.text() == "Will this remain on the form?"
    assert window.current_screen_name == "New Prediction"


@pytest.mark.parametrize("probability_percent", [0, 50, 100])
def test_successful_creation_accepts_probability_bounds_and_opens_detail(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
    probability_percent: int,
) -> None:
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    question.setText("  Will the UI preserve history?  ")
    probability.setValue(probability_percent)

    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will the UI preserve history?",
            probability_percent=probability_percent,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=datetime(2099, 12, 30, 18, tzinfo=UTC),
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Will the UI preserve history?"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{probability_percent}%"
    )
    assert question.text() == ""
    assert probability.value() == 50


def test_enter_submits_new_prediction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    question.setText("Will Enter submit this prediction?")

    _set_exact_deadline(window)

    qtbot.keyPress(question, Qt.Key.Key_Return)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will Enter submit this prediction?",
            probability_percent=50,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=datetime(2099, 12, 30, 18, tzinfo=UTC),
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
