from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.ui import MainWindow

EXPECTED_SCREEN_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)


@dataclass(frozen=True, slots=True)
class FakePrediction:
    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus = PredictionStatus.OPEN
    created_at: datetime = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)


class FakePredictionOperations:
    def __init__(self, latest: FakePrediction | None = None) -> None:
        self.latest = latest
        self.create_calls: list[tuple[str, int]] = []
        self.create_error: ApplicationError | None = None

    def create_prediction(
        self,
        question: str,
        probability_percent: int,
    ) -> FakePrediction:
        self.create_calls.append((question, probability_percent))
        if self.create_error is not None:
            raise self.create_error
        prediction = FakePrediction(
            prediction_id=1,
            question=question,
            probability_percent=probability_percent,
        )
        self.latest = prediction
        return prediction

    def get_latest_prediction(self) -> FakePrediction | None:
        return self.latest


@pytest.fixture
def operations() -> FakePredictionOperations:
    return FakePredictionOperations()


@pytest.fixture
def window(
    qtbot: QtBot,
    operations: FakePredictionOperations,
) -> MainWindow:
    main_window = MainWindow(operations)
    qtbot.addWidget(main_window)
    return main_window


def test_main_window_has_expected_navigation(window: MainWindow) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")

    assert window.windowTitle() == "Reckonsolve"
    assert window.screen_names == EXPECTED_SCREEN_NAMES
    assert (
        tuple(navigation.item(index).text() for index in range(navigation.count()))
        == EXPECTED_SCREEN_NAMES
    )
    assert window.current_screen_name == "Dashboard"
    assert navigation.currentRow() == 0


def test_main_window_navigates_to_each_primary_screen(window: MainWindow) -> None:
    screen_stack = _required_child(window, QStackedWidget, "screenStack")

    for expected_index, screen_name in enumerate(EXPECTED_SCREEN_NAMES):
        window.navigate_to(screen_name)

        assert window.current_screen_name == screen_name
        assert screen_stack.currentIndex() == expected_index


def test_unimplemented_screens_remain_honest_placeholders(window: MainWindow) -> None:
    placeholder_screens = (
        "Dashboard",
        "Predictions",
        "Analytics",
        "Settings",
    )

    for screen_name in placeholder_screens:
        window.navigate_to(screen_name)
        placeholder = _required_child(
            window,
            QLabel,
            f"{_object_name_prefix(screen_name)}ScreenPlaceholder",
        )

        assert any(word in placeholder.text() for word in ("coming", "will"))


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

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert operations.create_calls == [
        ("Will the UI preserve history?", probability_percent)
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

    qtbot.keyPress(question, Qt.Key.Key_Return)

    assert operations.create_calls == [("Will Enter submit this prediction?", 50)]
    assert window.current_screen_name == "Prediction Detail"


def test_prediction_detail_loads_latest_prediction_at_construction(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will this survive a restart?",
        probability_percent=60,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "60%"
    )
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden() is (
        False
    )
    assert _required_child(window, QLabel, "predictionDetailEmptyState").isHidden()


def test_prediction_detail_has_helpful_empty_state(window: MainWindow) -> None:
    window.navigate_to("Prediction Detail")

    empty_state = _required_child(window, QLabel, "predictionDetailEmptyState")
    assert not empty_state.isHidden()
    assert "Create one" in empty_state.text()
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden()


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()


def _required_child[WidgetType: QWidget](
    parent: QWidget,
    widget_type: type[WidgetType],
    object_name: str,
) -> WidgetType:
    child = parent.findChild(widget_type, object_name)
    assert child is not None
    return child


def _object_name_prefix(screen_name: str) -> str:
    first_word, *remaining_words = screen_name.split()
    return first_word.lower() + "".join(remaining_words)
