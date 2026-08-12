"""Milestone 2 prediction screens and their application-operation boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import PredictionStatus


class PredictionSnapshot(Protocol):
    """Read-only prediction data needed by the Milestone 2 screens."""

    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus
    created_at: datetime


class PredictionOperations(Protocol):
    """Complete prediction use cases invoked by the UI."""

    def create_prediction(
        self,
        question: str,
        probability_percent: int,
    ) -> PredictionSnapshot:
        """Create a prediction and its initial revision atomically."""

    def get_latest_prediction(self) -> PredictionSnapshot | None:
        """Return the most recently created prediction, if one exists."""


class NewPredictionScreen(QWidget):
    """Collect the minimum information needed for a binary prediction."""

    prediction_created = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("newPredictionScreen")
        self._operations = operations

        title = QLabel("New Prediction", self)
        title.setObjectName("newPredictionScreenTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        question_label = QLabel("Question", self)
        question_label.setObjectName("questionLabel")
        self._make_primary_label(question_label)

        self.question_input = QLineEdit(self)
        self.question_input.setObjectName("questionInput")
        self.question_input.setAccessibleName("Prediction question")
        self.question_input.setPlaceholderText("What do you think will happen?")
        self.question_input.setClearButtonEnabled(True)
        question_label.setBuddy(self.question_input)

        probability_label = QLabel("Probability", self)
        probability_label.setObjectName("probabilityLabel")
        self._make_primary_label(probability_label)

        self.probability_input = QSpinBox(self)
        self.probability_input.setObjectName("probabilityInput")
        self.probability_input.setAccessibleName("Prediction probability")
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix("%")
        self.probability_input.setValue(50)
        probability_label.setBuddy(self.probability_input)

        shortcuts = QWidget(self)
        shortcuts.setObjectName("probabilityShortcuts")
        shortcuts_layout = QHBoxLayout(shortcuts)
        shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        shortcuts_layout.setSpacing(6)
        for probability in range(10, 100, 10):
            shortcut = QPushButton(str(probability), shortcuts)
            shortcut.setObjectName(f"probabilityShortcut{probability}")
            shortcut.setAccessibleName(f"Set probability to {probability}%")
            shortcut.clicked.connect(
                lambda _checked=False, value=probability: (
                    self.probability_input.setValue(value)
                )
            )
            shortcuts_layout.addWidget(shortcut)
        shortcuts_layout.addStretch()

        self.endpoint_note = QLabel(
            "0% and 100% express absolute certainty.",
            self,
        )
        self.endpoint_note.setObjectName("probabilityEndpointNote")
        self.endpoint_note.setWordWrap(True)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("predictionFormError")
        self.form_error.setAccessibleName("Prediction form error")
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.create_button = QPushButton("Create Prediction", self)
        self.create_button.setObjectName("createPredictionButton")
        self.create_button.setAccessibleName("Create prediction")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addSpacing(18)
        layout.addWidget(question_label)
        layout.addWidget(self.question_input)
        layout.addSpacing(14)
        layout.addWidget(probability_label)
        layout.addWidget(self.probability_input)
        layout.addWidget(shortcuts)
        layout.addWidget(self.endpoint_note)
        layout.addSpacing(10)
        layout.addWidget(self.form_error)
        layout.addWidget(self.create_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        self.setTabOrder(self.question_input, self.probability_input)
        self.setTabOrder(self.probability_input, self.create_button)

        self.probability_input.valueChanged.connect(self._update_endpoint_note)
        self.question_input.returnPressed.connect(self.submit)
        self.create_button.clicked.connect(self.submit)
        self._update_endpoint_note(self.probability_input.value())

    def focus_question(self) -> None:
        """Put keyboard focus at the start of the creation flow."""
        self.question_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Validate the form shape and invoke the complete creation operation."""
        self._hide_error()
        question = self.question_input.text().strip()
        if not question:
            self._show_error("Enter a question before creating the prediction.")
            self.focus_question()
            return

        try:
            prediction = self._operations.create_prediction(
                question=question,
                probability_percent=self.probability_input.value(),
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return

        self.question_input.clear()
        self.probability_input.setValue(50)
        self.prediction_created.emit(prediction)

    @staticmethod
    def _make_primary_label(label: QLabel) -> None:
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)

    def _update_endpoint_note(self, probability: int) -> None:
        self.endpoint_note.setHidden(probability not in (0, 100))

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class PredictionDetailScreen(QWidget):
    """Show the minimal persisted prediction needed by Milestone 2."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionDetailScreen")
        self._operations = operations
        self._prediction_id: int | None = None

        title = QLabel("Prediction Detail", self)
        title.setObjectName("predictionDetailScreenTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.empty_state = QLabel(
            "No prediction yet. Create one from New Prediction to see it here.",
            self,
        )
        self.empty_state.setObjectName("predictionDetailEmptyState")
        self.empty_state.setWordWrap(True)

        self.detail_content = QWidget(self)
        self.detail_content.setObjectName("predictionDetailContent")

        self.question = QLabel("", self.detail_content)
        self.question.setObjectName("predictionDetailQuestion")
        self.question.setWordWrap(True)
        self.question.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.status = QLabel("", self.detail_content)
        self.status.setObjectName("predictionDetailStatus")
        self.status.setAccessibleName("Prediction status")

        current_forecast_label = QLabel("Current Forecast", self.detail_content)
        current_forecast_label.setObjectName("currentForecastLabel")

        self.probability = QLabel("", self.detail_content)
        self.probability.setObjectName("predictionDetailProbability")
        self.probability.setAccessibleName("Current probability")

        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.question)
        detail_layout.addWidget(self.status)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(current_forecast_label)
        detail_layout.addWidget(self.probability)
        detail_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addSpacing(18)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.detail_content)
        layout.addStretch()

        self.show_prediction(self._operations.get_latest_prediction())

    @property
    def prediction_id(self) -> int | None:
        """Return the identifier currently presented by the screen."""
        return self._prediction_id

    def show_prediction(self, prediction: PredictionSnapshot | None) -> None:
        """Present a prediction or the new-database empty state."""
        if prediction is None:
            self._prediction_id = None
            self.question.clear()
            self.status.clear()
            self.probability.clear()
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            return

        self._prediction_id = prediction.prediction_id
        self.question.setText(prediction.question)
        self.status.setText(prediction.status.value.upper())
        self.probability.setText(f"{prediction.probability_percent}%")
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
