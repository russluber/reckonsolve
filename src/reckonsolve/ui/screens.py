"""Prediction creation and detail screens with a thin application boundary."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import (
    ApplicationError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.predictions import (
    MAX_METADATA_DATE,
    MIN_METADATA_DATE,
    DefinitionChange,
    PredictionStatus,
)


class PredictionSnapshot(Protocol):
    """Read-only prediction data needed by the creation and detail screens."""

    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus
    created_at: datetime
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    updated_at: datetime | None
    metadata_version: int
    current_revision_id: int
    current_revision_sequence: int
    current_rationale: str | None


class ForecastRevisionSnapshot(Protocol):
    """Read-only revision data needed by the forecast timeline."""

    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None


class PredictionOperations(Protocol):
    """Complete prediction use cases invoked by the UI."""

    def create_prediction(
        self,
        question: str,
        probability_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> PredictionSnapshot:
        """Create a prediction and its initial revision atomically."""

    def revise_forecast(
        self,
        prediction_id: int,
        probability_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionSnapshot:
        """Append an eligible immutable forecast revision."""

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[ForecastRevisionSnapshot, ...]:
        """Return immutable forecast revisions in sequence order."""

    def get_latest_prediction(self) -> PredictionSnapshot | None:
        """Return the most recently created prediction, if one exists."""

    def get_prediction(self, prediction_id: int) -> PredictionSnapshot:
        """Return one prediction with its current forecast and metadata."""

    def update_metadata(
        self,
        prediction_id: int,
        *,
        question: str,
        background: str | None,
        resolution_criteria: str | None,
        forecast_deadline: date | None,
        expected_resolution: date | None,
        tags: tuple[str, ...],
        expected_metadata_version: int,
        confirm_meaning_change: bool = False,
    ) -> PredictionSnapshot:
        """Apply a complete metadata edit after any required confirmation."""

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...]:
        """Return immutable meaning-bearing definition changes."""


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

        self.more_details = QGroupBox("More details", self)
        self.more_details.setObjectName("newPredictionMoreDetailsGroup")
        self.more_details.setCheckable(True)
        self.more_details.setChecked(False)

        self.more_details_content = QWidget(self.more_details)
        self.more_details_content.setObjectName("newPredictionMoreDetailsContent")
        more_details_layout = QVBoxLayout(self.more_details_content)
        more_details_layout.setContentsMargins(4, 8, 4, 4)

        rationale_label = QLabel(
            "Initial rationale (optional)", self.more_details_content
        )
        self.rationale_input = QPlainTextEdit(self.more_details_content)
        self.rationale_input.setObjectName("initialRationaleInput")
        self.rationale_input.setAccessibleName("Initial rationale")
        self.rationale_input.setPlaceholderText("Why is this your initial forecast?")
        self.rationale_input.setMaximumHeight(100)
        self.rationale_input.setTabChangesFocus(True)
        rationale_label.setBuddy(self.rationale_input)

        background_label = QLabel("Background (optional)", self.more_details_content)
        self.background_input = QPlainTextEdit(self.more_details_content)
        self.background_input.setObjectName("initialBackgroundInput")
        self.background_input.setAccessibleName("Background")
        self.background_input.setMaximumHeight(100)
        self.background_input.setTabChangesFocus(True)
        background_label.setBuddy(self.background_input)

        criteria_label = QLabel(
            "Resolution Criteria (optional)",
            self.more_details_content,
        )
        self.resolution_criteria_input = QPlainTextEdit(self.more_details_content)
        self.resolution_criteria_input.setObjectName("initialResolutionCriteriaInput")
        self.resolution_criteria_input.setAccessibleName("Resolution criteria")
        self.resolution_criteria_input.setMaximumHeight(100)
        self.resolution_criteria_input.setTabChangesFocus(True)
        criteria_label.setBuddy(self.resolution_criteria_input)

        self.forecast_deadline_toggle, self.forecast_deadline_input = (
            _create_optional_date_controls(
                self.more_details_content,
                "Forecast deadline",
                "initialForecastDeadlineToggle",
                "initialForecastDeadlineInput",
                None,
            )
        )
        self.expected_resolution_toggle, self.expected_resolution_input = (
            _create_optional_date_controls(
                self.more_details_content,
                "Expected resolution",
                "initialExpectedResolutionToggle",
                "initialExpectedResolutionInput",
                None,
            )
        )

        tags_label = QLabel(
            "Tags (optional, comma-separated)",
            self.more_details_content,
        )
        self.tags_input = QLineEdit(self.more_details_content)
        self.tags_input.setObjectName("initialTagsInput")
        self.tags_input.setAccessibleName("Tags")
        tags_label.setBuddy(self.tags_input)

        more_details_layout.addWidget(rationale_label)
        more_details_layout.addWidget(self.rationale_input)
        more_details_layout.addWidget(background_label)
        more_details_layout.addWidget(self.background_input)
        more_details_layout.addWidget(criteria_label)
        more_details_layout.addWidget(self.resolution_criteria_input)
        more_details_layout.addWidget(
            _date_input_row(
                self.forecast_deadline_toggle,
                self.forecast_deadline_input,
            )
        )
        more_details_layout.addWidget(
            _date_input_row(
                self.expected_resolution_toggle,
                self.expected_resolution_input,
            )
        )
        more_details_layout.addWidget(tags_label)
        more_details_layout.addWidget(self.tags_input)

        more_details_group_layout = QVBoxLayout(self.more_details)
        more_details_group_layout.addWidget(self.more_details_content)
        self.more_details.toggled.connect(self.more_details_content.setVisible)
        self.more_details_content.setHidden(True)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("predictionFormError")
        self.form_error.setAccessibleName("Prediction form error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.create_button = QPushButton("Create Prediction", self)
        self.create_button.setObjectName("createPredictionButton")
        self.create_button.setAccessibleName("Create prediction")

        form_content = QWidget(self)
        form_content.setObjectName("newPredictionFormContent")
        layout = QVBoxLayout(form_content)
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
        layout.addWidget(self.more_details)
        layout.addWidget(self.form_error)
        layout.addWidget(self.create_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("newPredictionScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(form_content)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

        self.setTabOrder(self.question_input, self.probability_input)
        self.setTabOrder(self.probability_input, self.more_details)
        self.setTabOrder(self.more_details, self.rationale_input)
        self.setTabOrder(self.rationale_input, self.background_input)
        self.setTabOrder(self.background_input, self.resolution_criteria_input)
        self.setTabOrder(
            self.resolution_criteria_input,
            self.forecast_deadline_toggle,
        )
        self.setTabOrder(
            self.forecast_deadline_toggle,
            self.forecast_deadline_input,
        )
        self.setTabOrder(
            self.forecast_deadline_input,
            self.expected_resolution_toggle,
        )
        self.setTabOrder(
            self.expected_resolution_toggle,
            self.expected_resolution_input,
        )
        self.setTabOrder(self.expected_resolution_input, self.tags_input)
        self.setTabOrder(self.tags_input, self.create_button)

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
                rationale=self.rationale_input.toPlainText(),
                background=self.background_input.toPlainText(),
                resolution_criteria=self.resolution_criteria_input.toPlainText(),
                forecast_deadline=_optional_date(
                    self.forecast_deadline_toggle,
                    self.forecast_deadline_input,
                ),
                expected_resolution=_optional_date(
                    self.expected_resolution_toggle,
                    self.expected_resolution_input,
                ),
                tags=_parse_tags(self.tags_input.text()),
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return

        self._reset_form()
        self.prediction_created.emit(prediction)

    def _reset_form(self) -> None:
        self.question_input.clear()
        self.probability_input.setValue(50)
        self.rationale_input.clear()
        self.background_input.clear()
        self.resolution_criteria_input.clear()
        self.forecast_deadline_toggle.setChecked(False)
        self.forecast_deadline_input.setDate(QDate.currentDate())
        self.expected_resolution_toggle.setChecked(False)
        self.expected_resolution_input.setDate(QDate.currentDate())
        self.tags_input.clear()
        self.more_details.setChecked(False)
        self._hide_error()

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


class EditPredictionDetailsDialog(QDialog):
    """Edit stable prediction metadata through one complete application operation."""

    metadata_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("editPredictionDetailsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Edit Prediction Details")
        self.setModal(True)
        self.resize(620, 600)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._baseline_metadata_version = prediction.metadata_version

        title = QLabel("Edit Prediction Details", self)
        title.setObjectName("editPredictionDetailsTitle")

        question_label = QLabel("Question", self)
        self.question_input = QLineEdit(prediction.question, self)
        self.question_input.setObjectName("editQuestionInput")
        self.question_input.setAccessibleName("Question")
        question_label.setBuddy(self.question_input)

        background_label = QLabel("Background (optional)", self)
        self.background_input = QPlainTextEdit(self)
        self.background_input.setObjectName("editBackgroundInput")
        self.background_input.setAccessibleName("Background")
        self.background_input.setPlainText(prediction.background or "")
        self.background_input.setMaximumHeight(110)
        self.background_input.setTabChangesFocus(True)
        background_label.setBuddy(self.background_input)

        criteria_label = QLabel("Resolution Criteria (optional)", self)
        self.resolution_criteria_input = QPlainTextEdit(self)
        self.resolution_criteria_input.setObjectName("editResolutionCriteriaInput")
        self.resolution_criteria_input.setAccessibleName("Resolution criteria")
        self.resolution_criteria_input.setPlainText(
            prediction.resolution_criteria or ""
        )
        self.resolution_criteria_input.setMaximumHeight(110)
        self.resolution_criteria_input.setTabChangesFocus(True)
        criteria_label.setBuddy(self.resolution_criteria_input)

        self.forecast_deadline_toggle, self.forecast_deadline_input = (
            self._create_optional_date_input(
                "Forecast deadline",
                "editForecastDeadlineToggle",
                "editForecastDeadlineInput",
                prediction.forecast_deadline,
            )
        )
        self.expected_resolution_toggle, self.expected_resolution_input = (
            self._create_optional_date_input(
                "Expected resolution",
                "editExpectedResolutionToggle",
                "editExpectedResolutionInput",
                prediction.expected_resolution,
            )
        )

        tags_label = QLabel("Tags (optional, comma-separated)", self)
        self.tags_input = QLineEdit(", ".join(prediction.tags), self)
        self.tags_input.setObjectName("editTagsInput")
        self.tags_input.setAccessibleName("Tags")
        tags_label.setBuddy(self.tags_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("editDetailsError")
        self.form_error.setAccessibleName("Edit details error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("editDetailsButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("savePredictionDetailsButton")
        save_button.setDefault(True)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelPredictionDetailsButton")

        forecast_deadline_row = _date_input_row(
            self.forecast_deadline_toggle,
            self.forecast_deadline_input,
        )
        expected_resolution_row = _date_input_row(
            self.expected_resolution_toggle,
            self.expected_resolution_input,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(question_label)
        layout.addWidget(self.question_input)
        layout.addWidget(background_label)
        layout.addWidget(self.background_input)
        layout.addWidget(criteria_label)
        layout.addWidget(self.resolution_criteria_input)
        layout.addWidget(forecast_deadline_row)
        layout.addWidget(expected_resolution_row)
        layout.addWidget(tags_label)
        layout.addWidget(self.tags_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.question_input, self.background_input)
        self.setTabOrder(self.background_input, self.resolution_criteria_input)
        self.setTabOrder(
            self.resolution_criteria_input,
            self.forecast_deadline_toggle,
        )
        self.setTabOrder(
            self.forecast_deadline_toggle,
            self.forecast_deadline_input,
        )
        self.setTabOrder(
            self.forecast_deadline_input,
            self.expected_resolution_toggle,
        )
        self.setTabOrder(
            self.expected_resolution_toggle,
            self.expected_resolution_input,
        )
        self.setTabOrder(self.expected_resolution_input, self.tags_input)
        self.setTabOrder(self.tags_input, save_button)
        self.question_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save once, asking for confirmation only when the operation requires it."""
        self._hide_error()
        try:
            prediction = self._save(confirm_meaning_change=False)
        except MeaningChangeConfirmationRequired as error:
            if not self._confirm_meaning_change(error):
                return
            try:
                prediction = self._save(confirm_meaning_change=True)
            except ApplicationError as confirmed_error:
                self._show_error(str(confirmed_error))
                return
        except ApplicationError as error:
            self._show_error(str(error))
            return

        self.metadata_saved.emit(prediction)
        self.accept()

    def _save(self, *, confirm_meaning_change: bool) -> PredictionSnapshot:
        return self._operations.update_metadata(
            self._prediction_id,
            question=self.question_input.text(),
            background=self.background_input.toPlainText(),
            resolution_criteria=self.resolution_criteria_input.toPlainText(),
            forecast_deadline=_optional_date(
                self.forecast_deadline_toggle,
                self.forecast_deadline_input,
            ),
            expected_resolution=_optional_date(
                self.expected_resolution_toggle,
                self.expected_resolution_input,
            ),
            tags=_parse_tags(self.tags_input.text()),
            expected_metadata_version=self._baseline_metadata_version,
            confirm_meaning_change=confirm_meaning_change,
        )

    def _confirm_meaning_change(
        self,
        error: MeaningChangeConfirmationRequired,
    ) -> bool:
        semantic_definition_changed = any(
            field in {"question", "resolution_criteria"}
            for field in error.changed_fields
        )
        deadline_changed = "forecast_deadline" in error.changed_fields

        if semantic_definition_changed and deadline_changed:
            title = "Confirm definition and deadline changes"
        elif deadline_changed:
            title = "Confirm forecast deadline change"
        else:
            title = "Confirm definition change"
        answer = QMessageBox.warning(
            self,
            title,
            str(error),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Save

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)

    def _create_optional_date_input(
        self,
        label: str,
        toggle_name: str,
        input_name: str,
        value: date | None,
    ) -> tuple[QCheckBox, QDateEdit]:
        return _create_optional_date_controls(
            self,
            label,
            toggle_name,
            input_name,
            value,
        )


class ReviseForecastDialog(QDialog):
    """Collect a new probability and append exactly one forecast revision."""

    revision_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("reviseForecastDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Revise Forecast")
        self.setModal(True)
        self.resize(520, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Revise Forecast", self)
        title.setObjectName("reviseForecastTitle")

        current_heading = QLabel("Current forecast", self)
        self.current_probability = QLabel(
            f"{prediction.probability_percent}%",
            self,
        )
        self.current_probability.setObjectName("reviseCurrentProbability")
        self.current_probability.setAccessibleName("Current forecast")
        current_font = QFont(self.current_probability.font())
        current_font.setBold(True)
        current_font.setPointSize(current_font.pointSize() + 3)
        self.current_probability.setFont(current_font)

        probability_label = QLabel("New forecast", self)
        self.probability_input = QSpinBox(self)
        self.probability_input.setObjectName("revisionProbabilityInput")
        self.probability_input.setAccessibleName("New forecast probability")
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix("%")
        self.probability_input.setValue(prediction.probability_percent)
        probability_label.setBuddy(self.probability_input)

        shortcuts = QWidget(self)
        shortcuts.setObjectName("revisionProbabilityShortcuts")
        shortcuts_layout = QHBoxLayout(shortcuts)
        shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        shortcuts_layout.setSpacing(6)
        for probability in range(10, 100, 10):
            shortcut = QPushButton(str(probability), shortcuts)
            shortcut.setObjectName(f"revisionProbabilityShortcut{probability}")
            shortcut.setAccessibleName(f"Set new probability to {probability}%")
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
        self.endpoint_note.setObjectName("revisionProbabilityEndpointNote")
        self.endpoint_note.setWordWrap(True)

        rationale_label = QLabel("What changed? (optional)", self)
        self.rationale_input = QPlainTextEdit(self)
        self.rationale_input.setObjectName("revisionRationaleInput")
        self.rationale_input.setAccessibleName("What changed")
        self.rationale_input.setMaximumHeight(110)
        self.rationale_input.setTabChangesFocus(True)
        rationale_label.setBuddy(self.rationale_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("reviseForecastError")
        self.form_error.setAccessibleName("Revise forecast error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("reviseForecastButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveForecastRevisionButton")
        save_button.setText("Save Revision")
        save_button.setDefault(True)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelForecastRevisionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(current_heading)
        layout.addWidget(self.current_probability)
        layout.addSpacing(8)
        layout.addWidget(probability_label)
        layout.addWidget(self.probability_input)
        layout.addWidget(shortcuts)
        layout.addWidget(self.endpoint_note)
        layout.addWidget(rationale_label)
        layout.addWidget(self.rationale_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.setTabOrder(self.probability_input, self.rationale_input)
        self.setTabOrder(self.rationale_input, save_button)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.probability_input.valueChanged.connect(self._update_endpoint_note)
        self._update_endpoint_note(self.probability_input.value())
        self.probability_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.probability_input.selectAll()

    def submit(self) -> None:
        """Invoke the append operation; expected failures remain in the dialog."""
        self._hide_error()
        try:
            prediction = self._operations.revise_forecast(
                self._prediction_id,
                self.probability_input.value(),
                rationale=self.rationale_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.revision_saved.emit(prediction)
        self.accept()

    def _update_endpoint_note(self, probability: int) -> None:
        self.endpoint_note.setHidden(probability not in (0, 100))

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class PredictionDetailScreen(QWidget):
    """Display the current prediction definition and safe metadata editing."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionDetailScreen")
        self._operations = operations
        self._prediction: PredictionSnapshot | None = None
        self._edit_dialog: EditPredictionDetailsDialog | None = None
        self._revision_dialog: ReviseForecastDialog | None = None

        title = QLabel("Prediction Detail", self)
        title.setObjectName("predictionDetailScreenTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.empty_state = QLabel(
            "No prediction yet. Create one from New Prediction to see it here.",
            self,
        )
        self.empty_state.setObjectName("predictionDetailEmptyState")
        self.empty_state.setWordWrap(True)

        self.detail_error = QLabel("", self)
        self.detail_error.setObjectName("predictionDetailError")
        self.detail_error.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_error.setWordWrap(True)
        self.detail_error.setHidden(True)

        self.detail_content = QWidget(self)
        self.detail_content.setObjectName("predictionDetailContent")
        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setContentsMargins(4, 4, 12, 4)

        self.question = QLabel("", self.detail_content)
        self.question.setObjectName("predictionDetailQuestion")
        self.question.setWordWrap(True)
        self.question.setTextFormat(Qt.TextFormat.PlainText)
        self.question.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        question_font = QFont(self.question.font())
        question_font.setPointSize(question_font.pointSize() + 3)
        question_font.setBold(True)
        self.question.setFont(question_font)

        self.status = QLabel("", self.detail_content)
        self.status.setObjectName("predictionDetailStatus")
        self.status.setAccessibleName("Prediction status")

        self.tags = QLabel("", self.detail_content)
        self.tags.setObjectName("predictionDetailTags")
        self.tags.setWordWrap(True)
        self.tags.setTextFormat(Qt.TextFormat.PlainText)

        current_forecast_label = QLabel("Current Forecast", self.detail_content)
        current_forecast_label.setObjectName("currentForecastLabel")
        self.probability = QLabel("", self.detail_content)
        self.probability.setObjectName("predictionDetailProbability")
        self.probability.setAccessibleName("Current probability")
        probability_font = QFont(self.probability.font())
        probability_font.setPointSize(probability_font.pointSize() + 8)
        probability_font.setBold(True)
        self.probability.setFont(probability_font)

        self.edit_details_button = QPushButton("Edit Details", self.detail_content)
        self.edit_details_button.setObjectName("editPredictionDetailsButton")
        self.edit_details_button.clicked.connect(self.open_edit_details)

        action_row = QWidget(self.detail_content)
        action_row.setObjectName("futurePredictionActions")
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        self.revise_forecast_button = QPushButton("Revise Forecast", action_row)
        self.revise_forecast_button.setObjectName("reviseForecastButton")
        self.revise_forecast_button.clicked.connect(self.open_revise_forecast)
        action_layout.addWidget(self.revise_forecast_button)
        for label, object_name in (
            ("Add Journal Entry", "addJournalEntryButton"),
            ("Resolve", "resolvePredictionButton"),
            ("Mark Invalid", "markInvalidButton"),
        ):
            button = QPushButton(label, action_row)
            button.setObjectName(object_name)
            button.setEnabled(False)
            button.setToolTip("This action is coming in a later milestone.")
            action_layout.addWidget(button)
        action_layout.addStretch()

        self.forecast_deadline_row, self.forecast_deadline = _detail_value_row(
            "Forecast deadline",
            "predictionDetailForecastDeadlineRow",
            "predictionDetailForecastDeadline",
            self.detail_content,
        )
        self.expected_resolution_row, self.expected_resolution = _detail_value_row(
            "Expected resolution",
            "predictionDetailExpectedResolutionRow",
            "predictionDetailExpectedResolution",
            self.detail_content,
        )
        self.background_section, self.background = _detail_text_section(
            "BACKGROUND",
            "predictionDetailBackgroundSection",
            "predictionDetailBackground",
            self.detail_content,
        )
        self.resolution_criteria_section, self.resolution_criteria = (
            _detail_text_section(
                "RESOLUTION CRITERIA",
                "predictionDetailResolutionCriteriaSection",
                "predictionDetailResolutionCriteria",
                self.detail_content,
            )
        )

        self.definition_history = QGroupBox("Definition history", self.detail_content)
        self.definition_history.setObjectName("definitionHistoryGroup")
        self.definition_history.setCheckable(True)
        self.definition_history.setChecked(False)
        self.definition_history_content = QWidget(self.definition_history)
        self.definition_history_content.setObjectName("definitionHistoryContent")
        self.definition_history_layout = QVBoxLayout(self.definition_history_content)
        history_group_layout = QVBoxLayout(self.definition_history)
        history_group_layout.addWidget(self.definition_history_content)
        self.definition_history.toggled.connect(
            self.definition_history_content.setVisible
        )
        self.definition_history_content.setHidden(True)

        timeline_label = QLabel("FORECAST HISTORY", self.detail_content)
        timeline_label.setObjectName("timelineHeading")
        self.forecast_timeline = QWidget(self.detail_content)
        self.forecast_timeline.setObjectName("forecastTimeline")
        self.forecast_timeline_layout = QVBoxLayout(self.forecast_timeline)
        self.forecast_timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_placeholder = QLabel(
            "No forecast revisions are available.",
            self.detail_content,
        )
        self.timeline_placeholder.setObjectName("timelinePlaceholder")
        self.timeline_placeholder.setWordWrap(True)

        chart_label = QLabel("PROBABILITY HISTORY", self.detail_content)
        chart_label.setObjectName("probabilityHistoryHeading")
        self.chart_placeholder = QLabel(
            "Probability history visualization is coming in a later milestone.",
            self.detail_content,
        )
        self.chart_placeholder.setObjectName("probabilityHistoryPlaceholder")
        self.chart_placeholder.setWordWrap(True)

        detail_layout.addWidget(self.question)
        detail_layout.addWidget(self.tags)
        detail_layout.addWidget(self.status)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(current_forecast_label)
        detail_layout.addWidget(self.probability)
        detail_layout.addWidget(action_row)
        detail_layout.addWidget(self.edit_details_button, 0, Qt.AlignmentFlag.AlignLeft)
        detail_layout.addSpacing(10)
        detail_layout.addWidget(self.forecast_deadline_row)
        detail_layout.addWidget(self.expected_resolution_row)
        detail_layout.addWidget(self.background_section)
        detail_layout.addWidget(self.resolution_criteria_section)
        detail_layout.addWidget(self.definition_history)
        detail_layout.addSpacing(16)
        detail_layout.addWidget(timeline_label)
        detail_layout.addWidget(self.forecast_timeline)
        detail_layout.addWidget(self.timeline_placeholder)
        detail_layout.addSpacing(12)
        detail_layout.addWidget(chart_label)
        detail_layout.addWidget(self.chart_placeholder)
        detail_layout.addStretch()

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("predictionDetailScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.detail_content)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.detail_error)
        layout.addWidget(scroll_area, 1)

        self.show_prediction(self._operations.get_latest_prediction())

    @property
    def prediction_id(self) -> int | None:
        """Return the identifier currently presented by the screen."""
        return None if self._prediction is None else self._prediction.prediction_id

    def show_prediction(self, prediction: PredictionSnapshot | None) -> None:
        """Present a prediction or the new-database empty state."""
        self._prediction = prediction
        self._hide_error()
        if prediction is None:
            self.question.clear()
            self.status.clear()
            self.probability.clear()
            self.tags.clear()
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            self.definition_history.setHidden(True)
            return

        self.question.setText(prediction.question)
        self.status.setText(prediction.status.value.upper())
        self.probability.setText(f"{prediction.probability_percent}%")
        revision_allowed = prediction.status is PredictionStatus.OPEN
        self.revise_forecast_button.setEnabled(revision_allowed)
        if revision_allowed:
            self.revise_forecast_button.setToolTip(
                "Append a new probability while preserving this forecast."
            )
        else:
            self.revise_forecast_button.setToolTip(
                f"Forecast revisions are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
        self.tags.setText("  ".join(f"#{tag}" for tag in prediction.tags))
        self.tags.setHidden(not prediction.tags)
        self._show_optional_metadata(prediction)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
        self._load_definition_history(prediction.prediction_id)
        self._load_forecast_timeline(prediction.prediction_id)

    def refresh(self) -> None:
        """Reload the displayed prediction while retaining data on a read failure."""
        try:
            if self._prediction is None:
                prediction = self._operations.get_latest_prediction()
            else:
                prediction = self._operations.get_prediction(
                    self._prediction.prediction_id
                )
        except ApplicationError as error:
            self._show_error(f"Prediction Detail could not be refreshed. {error}")
            return
        self.show_prediction(prediction)

    def open_edit_details(self) -> None:
        """Open a prefilled metadata dialog without mutating on open or cancel."""
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        dialog = EditPredictionDetailsDialog(
            self._operations,
            prediction,
            self,
        )
        self._edit_dialog = dialog
        dialog.metadata_saved.connect(self.show_prediction)
        dialog.finished.connect(self._edit_dialog_finished)
        dialog.open()

    def open_revise_forecast(self) -> None:
        """Refresh eligibility, then open a side-effect-free revision dialog."""
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status is not PredictionStatus.OPEN:
            self._show_error(
                f"Forecast revisions are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
            return
        dialog = ReviseForecastDialog(self._operations, prediction, self)
        self._revision_dialog = dialog
        dialog.revision_saved.connect(self.show_prediction)
        dialog.finished.connect(self._revision_dialog_finished)
        dialog.open()

    def _edit_dialog_finished(self, _result: int) -> None:
        self._edit_dialog = None

    def _revision_dialog_finished(self, _result: int) -> None:
        self._revision_dialog = None

    def _show_optional_metadata(self, prediction: PredictionSnapshot) -> None:
        self.forecast_deadline.setText(_format_date(prediction.forecast_deadline))
        self.forecast_deadline_row.setHidden(prediction.forecast_deadline is None)
        self.expected_resolution.setText(_format_date(prediction.expected_resolution))
        self.expected_resolution_row.setHidden(prediction.expected_resolution is None)
        self.background.setText(prediction.background or "")
        self.background_section.setHidden(not prediction.background)
        self.resolution_criteria.setText(prediction.resolution_criteria or "")
        self.resolution_criteria_section.setHidden(not prediction.resolution_criteria)

    def _load_definition_history(self, prediction_id: int) -> None:
        try:
            changes = self._operations.list_definition_changes(prediction_id)
        except ApplicationError as error:
            self.definition_history.setHidden(True)
            self._show_error(str(error))
            return

        _clear_widget_layout(self.definition_history_layout)
        for change in changes:
            self.definition_history_layout.addWidget(
                _definition_change_widget(change, self.definition_history_content)
            )
        self.definition_history.setChecked(False)
        self.definition_history_content.setHidden(True)
        self.definition_history.setHidden(not changes)

    def _load_forecast_timeline(self, prediction_id: int) -> None:
        try:
            revisions = self._operations.list_forecast_revisions(prediction_id)
        except ApplicationError as error:
            self.forecast_timeline.setHidden(True)
            self.timeline_placeholder.setText("Forecast history could not be loaded.")
            self.timeline_placeholder.setHidden(False)
            self._show_error(str(error))
            return

        _clear_widget_layout(self.forecast_timeline_layout)
        previous_probability: int | None = None
        for revision in revisions:
            self.forecast_timeline_layout.addWidget(
                _forecast_revision_widget(
                    revision,
                    previous_probability,
                    self.forecast_timeline,
                )
            )
            previous_probability = revision.probability_percent
        self.forecast_timeline.setHidden(not revisions)
        self.timeline_placeholder.setText("No forecast revisions are available.")
        self.timeline_placeholder.setHidden(bool(revisions))

    def _show_error(self, message: str) -> None:
        self.detail_error.setText(message)
        self.detail_error.setHidden(False)

    def _hide_error(self) -> None:
        self.detail_error.clear()
        self.detail_error.setHidden(True)


def _date_input_row(toggle: QCheckBox, date_input: QDateEdit) -> QWidget:
    row = QWidget(toggle.parentWidget())
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(toggle)
    layout.addWidget(date_input)
    layout.addStretch()
    return row


def _create_optional_date_controls(
    parent: QWidget,
    label: str,
    toggle_name: str,
    input_name: str,
    value: date | None,
) -> tuple[QCheckBox, QDateEdit]:
    toggle = QCheckBox(f"Set {label.lower()}", parent)
    toggle.setObjectName(toggle_name)
    date_input = QDateEdit(parent)
    date_input.setObjectName(input_name)
    date_input.setAccessibleName(label)
    date_input.setCalendarPopup(True)
    date_input.setDisplayFormat("yyyy-MM-dd")
    date_input.setDateRange(
        _to_qdate(MIN_METADATA_DATE),
        _to_qdate(MAX_METADATA_DATE),
    )
    initial_date = QDate.currentDate() if value is None else _to_qdate(value)
    date_input.setDate(initial_date)
    toggle.setChecked(value is not None)
    date_input.setEnabled(toggle.isChecked())
    date_input.setVisible(toggle.isChecked())
    toggle.toggled.connect(date_input.setEnabled)
    toggle.toggled.connect(date_input.setVisible)
    return toggle, date_input


def _optional_date(toggle: QCheckBox, date_input: QDateEdit) -> date | None:
    if not toggle.isChecked():
        return None
    value = date_input.date()
    return date(value.year(), value.month(), value.day())


def _parse_tags(value: str) -> tuple[str, ...]:
    return tuple(tag.strip() for tag in value.split(",") if tag.strip())


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _detail_value_row(
    label: str,
    row_name: str,
    value_name: str,
    parent: QWidget,
) -> tuple[QWidget, QLabel]:
    row = QWidget(parent)
    row.setObjectName(row_name)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    heading = QLabel(f"{label}:", row)
    value = QLabel("", row)
    value.setObjectName(value_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(heading)
    layout.addWidget(value)
    layout.addStretch()
    return row, value


def _detail_text_section(
    heading_text: str,
    section_name: str,
    value_name: str,
    parent: QWidget,
) -> tuple[QWidget, QLabel]:
    section = QWidget(parent)
    section.setObjectName(section_name)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 8, 0, 0)
    heading = QLabel(heading_text, section)
    value = QLabel("", section)
    value.setObjectName(value_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(True)
    value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(heading)
    layout.addWidget(value)
    return section, value


def _definition_change_widget(
    change: DefinitionChange,
    parent: QWidget,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"definitionChange{change.change_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    timestamp = QLabel(_format_local_timestamp(change.changed_at), frame)
    timestamp.setObjectName(f"definitionChangeTimestamp{change.change_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(timestamp)
    values = {
        "question": (change.old_question, change.new_question),
        "resolution_criteria": (
            change.old_resolution_criteria,
            change.new_resolution_criteria,
        ),
        "forecast_deadline": (
            change.old_forecast_deadline,
            change.new_forecast_deadline,
        ),
    }
    for field_name in change.changed_fields:
        old_value, new_value = values[field_name]
        field_change = QLabel(
            f"{_field_label(field_name)}: {_history_value(old_value)} → "
            f"{_history_value(new_value)}",
            frame,
        )
        field_change.setObjectName(
            f"definitionChange{change.change_id}{_object_name_part(field_name)}"
        )
        field_change.setTextFormat(Qt.TextFormat.PlainText)
        field_change.setWordWrap(True)
        field_change.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(field_change)
    return frame


def _forecast_revision_widget(
    revision: ForecastRevisionSnapshot,
    previous_probability: int | None,
    parent: QWidget,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"forecastRevision{revision.revision_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)

    timestamp = QLabel(_format_local_timestamp(revision.created_at), frame)
    timestamp.setObjectName(f"forecastRevisionTimestamp{revision.revision_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(timestamp)

    if previous_probability is None:
        probability_text = f"FORECAST  {revision.probability_percent}%"
    else:
        probability_text = (
            f"FORECAST  {previous_probability}% "
            f"\N{RIGHTWARDS ARROW} {revision.probability_percent}%"
        )
    probability = QLabel(probability_text, frame)
    probability.setObjectName(f"forecastRevisionProbability{revision.revision_id}")
    probability.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(probability)

    if revision.rationale:
        rationale = QLabel(revision.rationale, frame)
        rationale.setObjectName(f"forecastRevisionRationale{revision.revision_id}")
        rationale.setTextFormat(Qt.TextFormat.PlainText)
        rationale.setWordWrap(True)
        rationale.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(rationale)
    return frame


def _clear_widget_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _format_local_timestamp(value: datetime) -> str:
    local_value = value.astimezone()
    return local_value.strftime("%b %d, %Y at %H:%M %Z").strip()


def _format_date(value: date | None) -> str:
    return "" if value is None else value.strftime("%b %d, %Y")


def _history_value(value: str | date | None) -> str:
    if value is None or value == "":
        return "Not set"
    if isinstance(value, date):
        return _format_date(value)
    return f"“{value}”"


def _field_label(field_name: str) -> str:
    return {
        "question": "Question",
        "resolution_criteria": "Resolution Criteria",
        "forecast_deadline": "Forecast Deadline",
    }.get(field_name, field_name.replace("_", " ").title())


def _object_name_part(field_name: str) -> str:
    words = field_name.split("_")
    return "".join(word.title() for word in words)
