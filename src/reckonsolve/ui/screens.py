"""Prediction creation and detail screens with a thin application boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Protocol

from PySide6.QtCore import QDate, QEvent, QObject, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics import AnalyticsSnapshot
from reckonsolve.application.errors import (
    ApplicationError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.attention import DashboardSnapshot
from reckonsolve.domain.browser import PredictionBrowserSnapshot
from reckonsolve.domain.predictions import (
    MAX_METADATA_DATE,
    MIN_METADATA_DATE,
    BinaryOutcome,
    DefinitionChange,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


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
    resolution: ResolutionSnapshot | None
    invalidation: InvalidationSnapshot | None
    deletion_allowed: bool


class NumericRevisionSnapshot(Protocol):
    """Read-only current Numeric ForecastRevision values for detail display."""

    revision_id: int
    prediction_id: int
    lower_bound: object
    median_estimate: object
    upper_bound: object
    confidence_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None


class NumericPredictionSnapshot(Protocol):
    """Read-only Numeric Prediction data needed by the M14 detail screen."""

    prediction_id: int
    question: str
    unit: str
    decimal_places: int
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime
    current_revision: NumericRevisionSnapshot
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    metadata_version: int


class ResolutionSnapshot(Protocol):
    """Read-only immutable resolution data shown on Prediction Detail."""

    resolution_id: int
    prediction_id: int
    outcome: BinaryOutcome
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    scoring_probability_percent: int
    resolution_notes: str | None
    postmortem: str | None


class InvalidationSnapshot(Protocol):
    """Read-only immutable invalidation data shown on Prediction Detail."""

    invalidation_id: int
    prediction_id: int
    invalidated_at: datetime
    reason: str | None


class ForecastRevisionSnapshot(Protocol):
    """Read-only revision data needed by the probability-history chart."""

    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None


class JournalCorrectionSnapshot(Protocol):
    """Read-only correction data shown in a Journal entry's edit history."""

    correction_id: int
    body: str
    corrected_at: datetime


class ForecastTimelineSnapshot(Protocol):
    """A forecast event prepared for the unified Prediction timeline."""

    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    probability_percent: int
    previous_probability_percent: int | None
    rationale: str | None


class JournalTimelineSnapshot(Protocol):
    """A Journal event prepared with its exact forecast-at-the-time context."""

    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    current_correction_id: int | None
    corrections: tuple[JournalCorrectionSnapshot, ...]


TimelineSnapshot = ForecastTimelineSnapshot | JournalTimelineSnapshot


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

    def create_numeric_prediction(
        self,
        question: str,
        unit: str,
        decimal_places: int,
        lower_bound: object,
        median_estimate: object,
        upper_bound: object,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> NumericPredictionSnapshot:
        """Create a Numeric Prediction and its first interval atomically."""

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

    def add_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> JournalTimelineSnapshot:
        """Append reasoning tied to the exact forecast the user reviewed."""

    def correct_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> JournalTimelineSnapshot:
        """Append a transparent correction without replacing earlier text."""

    def resolve_prediction(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionSnapshot:
        """Persist a terminal outcome and the exact scoring forecast."""

    def invalidate_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionSnapshot:
        """Preserve a prediction as terminal and excluded from scoring."""

    def delete_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> PredictionSnapshot | None:
        """Permanently delete an explicitly confirmed untouched Open prediction."""

    def list_timeline(
        self,
        prediction_id: int,
    ) -> tuple[TimelineSnapshot, ...]:
        """Return Forecast and Journal events in deterministic causal order."""

    def get_latest_prediction(self) -> PredictionSnapshot | None:
        """Return the most recently created prediction, if one exists."""

    def get_latest_numeric_prediction(self) -> NumericPredictionSnapshot | None:
        """Return the most recently created Numeric Prediction, if one exists."""

    def get_prediction(self, prediction_id: int) -> PredictionSnapshot:
        """Return one prediction with its current forecast and metadata."""

    def get_numeric_prediction(self, prediction_id: int) -> NumericPredictionSnapshot:
        """Return one Numeric Prediction with its current interval and metadata."""

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

    def get_dashboard(self) -> DashboardSnapshot:
        """Return the current overlapping Dashboard buckets."""

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
    ) -> PredictionBrowserSnapshot:
        """Return filtered prediction summaries and available tags."""

    def get_analytics(self, *, tag: str | None = None) -> AnalyticsSnapshot:
        """Return exactly-once scoring analytics for all or one tag."""

    def get_stale_threshold_days(self) -> int:
        """Return the persisted Needs Attention threshold."""

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist a validated Needs Attention threshold."""


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

        prediction_type_label = QLabel("Forecast type", self)
        prediction_type_label.setObjectName("predictionTypeLabel")
        self._make_primary_label(prediction_type_label)

        self.prediction_type_input = QComboBox(self)
        self.prediction_type_input.setObjectName("predictionTypeInput")
        self.prediction_type_input.setAccessibleName("Forecast type")
        self.prediction_type_input.addItem("Binary (Yes/No)", PredictionType.BINARY)
        self.prediction_type_input.addItem("Numeric interval", PredictionType.NUMERIC)
        prediction_type_label.setBuddy(self.prediction_type_input)

        self.binary_forecast_fields = QWidget(self)
        self.binary_forecast_fields.setObjectName("binaryForecastFields")
        binary_fields_layout = QVBoxLayout(self.binary_forecast_fields)
        binary_fields_layout.setContentsMargins(0, 0, 0, 0)

        probability_label = QLabel("Probability", self.binary_forecast_fields)
        probability_label.setObjectName("probabilityLabel")
        self._make_primary_label(probability_label)

        self.probability_input = QSpinBox(self.binary_forecast_fields)
        self.probability_input.setObjectName("probabilityInput")
        self.probability_input.setAccessibleName("Prediction probability")
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix("%")
        self.probability_input.setValue(50)
        probability_label.setBuddy(self.probability_input)

        shortcuts = QWidget(self.binary_forecast_fields)
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
            self.binary_forecast_fields,
        )
        self.endpoint_note.setObjectName("probabilityEndpointNote")
        self.endpoint_note.setWordWrap(True)

        binary_fields_layout.addWidget(probability_label)
        binary_fields_layout.addWidget(self.probability_input)
        binary_fields_layout.addWidget(shortcuts)
        binary_fields_layout.addWidget(self.endpoint_note)

        self.numeric_forecast_fields = QWidget(self)
        self.numeric_forecast_fields.setObjectName("numericForecastFields")
        numeric_fields_layout = QVBoxLayout(self.numeric_forecast_fields)
        numeric_fields_layout.setContentsMargins(0, 0, 0, 0)

        unit_label = QLabel("Unit", self.numeric_forecast_fields)
        unit_label.setObjectName("numericUnitLabel")
        self._make_primary_label(unit_label)
        self.numeric_unit_input = QLineEdit(self.numeric_forecast_fields)
        self.numeric_unit_input.setObjectName("numericUnitInput")
        self.numeric_unit_input.setAccessibleName("Numeric forecast unit")
        self.numeric_unit_input.setPlaceholderText("For example: days, books, USD")
        self.numeric_unit_input.setClearButtonEnabled(True)
        unit_label.setBuddy(self.numeric_unit_input)

        precision_label = QLabel("Decimal places", self.numeric_forecast_fields)
        precision_label.setObjectName("numericPrecisionLabel")
        self.numeric_precision_input = QSpinBox(self.numeric_forecast_fields)
        self.numeric_precision_input.setObjectName("numericPrecisionInput")
        self.numeric_precision_input.setAccessibleName("Numeric decimal places")
        self.numeric_precision_input.setRange(0, 6)
        self.numeric_precision_input.setValue(0)
        precision_label.setBuddy(self.numeric_precision_input)

        lower_label = QLabel("Lower bound", self.numeric_forecast_fields)
        lower_label.setObjectName("numericLowerBoundLabel")
        self.numeric_lower_bound_input = QLineEdit(self.numeric_forecast_fields)
        self.numeric_lower_bound_input.setObjectName("numericLowerBoundInput")
        self.numeric_lower_bound_input.setAccessibleName("Numeric lower bound")
        self.numeric_lower_bound_input.setPlaceholderText("For example: 3")
        lower_label.setBuddy(self.numeric_lower_bound_input)

        median_label = QLabel("Median estimate", self.numeric_forecast_fields)
        median_label.setObjectName("numericMedianEstimateLabel")
        self.numeric_median_estimate_input = QLineEdit(self.numeric_forecast_fields)
        self.numeric_median_estimate_input.setObjectName("numericMedianEstimateInput")
        self.numeric_median_estimate_input.setAccessibleName("Numeric median estimate")
        self.numeric_median_estimate_input.setPlaceholderText("For example: 7")
        median_label.setBuddy(self.numeric_median_estimate_input)

        upper_label = QLabel("Upper bound", self.numeric_forecast_fields)
        upper_label.setObjectName("numericUpperBoundLabel")
        self.numeric_upper_bound_input = QLineEdit(self.numeric_forecast_fields)
        self.numeric_upper_bound_input.setObjectName("numericUpperBoundInput")
        self.numeric_upper_bound_input.setAccessibleName("Numeric upper bound")
        self.numeric_upper_bound_input.setPlaceholderText("For example: 21")
        upper_label.setBuddy(self.numeric_upper_bound_input)

        confidence_label = QLabel("Confidence", self.numeric_forecast_fields)
        confidence_label.setObjectName("numericConfidenceLabel")
        self.numeric_confidence_input = QSpinBox(self.numeric_forecast_fields)
        self.numeric_confidence_input.setObjectName("numericConfidenceInput")
        self.numeric_confidence_input.setAccessibleName("Numeric interval confidence")
        self.numeric_confidence_input.setRange(1, 99)
        self.numeric_confidence_input.setSingleStep(5)
        self.numeric_confidence_input.setSuffix("%")
        self.numeric_confidence_input.setValue(80)
        confidence_label.setBuddy(self.numeric_confidence_input)

        numeric_shortcuts = QWidget(self.numeric_forecast_fields)
        numeric_shortcuts.setObjectName("numericConfidenceShortcuts")
        numeric_shortcuts_layout = QHBoxLayout(numeric_shortcuts)
        numeric_shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        numeric_shortcuts_layout.setSpacing(6)
        for confidence in (50, 80, 90, 95):
            shortcut = QPushButton(f"{confidence}%", numeric_shortcuts)
            shortcut.setObjectName(f"numericConfidenceShortcut{confidence}")
            shortcut.setAccessibleName(f"Set confidence to {confidence}%")
            shortcut.clicked.connect(
                lambda _checked=False, value=confidence: (
                    self.numeric_confidence_input.setValue(value)
                )
            )
            numeric_shortcuts_layout.addWidget(shortcut)
        numeric_shortcuts_layout.addStretch()

        numeric_fields_layout.addWidget(unit_label)
        numeric_fields_layout.addWidget(self.numeric_unit_input)
        numeric_fields_layout.addWidget(precision_label)
        numeric_fields_layout.addWidget(self.numeric_precision_input)
        numeric_fields_layout.addWidget(lower_label)
        numeric_fields_layout.addWidget(self.numeric_lower_bound_input)
        numeric_fields_layout.addWidget(median_label)
        numeric_fields_layout.addWidget(self.numeric_median_estimate_input)
        numeric_fields_layout.addWidget(upper_label)
        numeric_fields_layout.addWidget(self.numeric_upper_bound_input)
        numeric_fields_layout.addWidget(confidence_label)
        numeric_fields_layout.addWidget(self.numeric_confidence_input)
        numeric_fields_layout.addWidget(numeric_shortcuts)

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
        apply_lucide_icon(self.create_button, LucideIcon.CIRCLE_PLUS)

        form_content = QWidget(self)
        form_content.setObjectName("newPredictionFormContent")
        layout = QVBoxLayout(form_content)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addSpacing(18)
        layout.addWidget(question_label)
        layout.addWidget(self.question_input)
        layout.addSpacing(14)
        layout.addWidget(prediction_type_label)
        layout.addWidget(self.prediction_type_input)
        layout.addSpacing(10)
        layout.addWidget(self.binary_forecast_fields)
        layout.addWidget(self.numeric_forecast_fields)
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

        self.setTabOrder(self.question_input, self.prediction_type_input)
        self.setTabOrder(self.prediction_type_input, self.probability_input)
        self.setTabOrder(self.probability_input, self.numeric_unit_input)
        self.setTabOrder(self.numeric_unit_input, self.numeric_precision_input)
        self.setTabOrder(self.numeric_precision_input, self.numeric_lower_bound_input)
        self.setTabOrder(
            self.numeric_lower_bound_input, self.numeric_median_estimate_input
        )
        self.setTabOrder(
            self.numeric_median_estimate_input, self.numeric_upper_bound_input
        )
        self.setTabOrder(self.numeric_upper_bound_input, self.numeric_confidence_input)
        self.setTabOrder(self.numeric_confidence_input, self.more_details)
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
        self.prediction_type_input.currentIndexChanged.connect(
            self._update_forecast_type
        )
        self.question_input.returnPressed.connect(self.submit)
        self.create_button.clicked.connect(self.submit)
        self._update_endpoint_note(self.probability_input.value())
        self._update_forecast_type(self.prediction_type_input.currentIndex())

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
            details = {
                "rationale": self.rationale_input.toPlainText(),
                "background": self.background_input.toPlainText(),
                "resolution_criteria": self.resolution_criteria_input.toPlainText(),
                "forecast_deadline": _optional_date(
                    self.forecast_deadline_toggle,
                    self.forecast_deadline_input,
                ),
                "expected_resolution": _optional_date(
                    self.expected_resolution_toggle,
                    self.expected_resolution_input,
                ),
                "tags": _parse_tags(self.tags_input.text()),
            }
            if self._is_numeric_type():
                prediction = self._operations.create_numeric_prediction(
                    question,
                    self.numeric_unit_input.text(),
                    self.numeric_precision_input.value(),
                    self.numeric_lower_bound_input.text(),
                    self.numeric_median_estimate_input.text(),
                    self.numeric_upper_bound_input.text(),
                    self.numeric_confidence_input.value(),
                    **details,
                )
            else:
                prediction = self._operations.create_prediction(
                    question=question,
                    probability_percent=self.probability_input.value(),
                    **details,
                )
        except ApplicationError as error:
            self._show_error(str(error))
            return

        self._reset_form()
        self.prediction_created.emit(prediction)

    def _reset_form(self) -> None:
        self.question_input.clear()
        self.prediction_type_input.setCurrentIndex(0)
        self.probability_input.setValue(50)
        self.numeric_unit_input.clear()
        self.numeric_precision_input.setValue(0)
        self.numeric_lower_bound_input.clear()
        self.numeric_median_estimate_input.clear()
        self.numeric_upper_bound_input.clear()
        self.numeric_confidence_input.setValue(80)
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
        self.endpoint_note.setHidden(
            self._is_numeric_type() or probability not in (0, 100)
        )

    def _update_forecast_type(self, _index: int) -> None:
        is_numeric = self._is_numeric_type()
        self.binary_forecast_fields.setHidden(is_numeric)
        self.numeric_forecast_fields.setHidden(not is_numeric)
        self._update_endpoint_note(self.probability_input.value())

    def _is_numeric_type(self) -> bool:
        return self.prediction_type_input.currentData() == PredictionType.NUMERIC.value

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class NumericPredictionDetailScreen(QWidget):
    """Present the current Numeric Prediction without exposing later workflows."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("numericPredictionDetailScreen")
        self._operations = operations
        self._prediction: NumericPredictionSnapshot | None = None

        title = QLabel("Prediction Detail", self)
        title.setObjectName("numericPredictionDetailScreenTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.empty_state = QLabel(
            "No Numeric Prediction has been created yet.",
            self,
        )
        self.empty_state.setObjectName("numericPredictionDetailEmptyState")
        self.empty_state.setWordWrap(True)

        self.detail_error = QLabel("", self)
        self.detail_error.setObjectName("numericPredictionDetailError")
        self.detail_error.setAccessibleName("Numeric Prediction Detail error")
        self.detail_error.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_error.setWordWrap(True)
        self.detail_error.setHidden(True)

        self.detail_content = QWidget(self)
        self.detail_content.setObjectName("numericPredictionDetailContent")
        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.question = QLabel("", self.detail_content)
        self.question.setObjectName("numericPredictionQuestion")
        self.question.setTextFormat(Qt.TextFormat.PlainText)
        self.question.setWordWrap(True)
        question_font = QFont(self.question.font())
        question_font.setPointSize(question_font.pointSize() + 2)
        question_font.setBold(True)
        self.question.setFont(question_font)

        self.tags = QLabel("", self.detail_content)
        self.tags.setObjectName("numericPredictionTags")
        self.tags.setTextFormat(Qt.TextFormat.PlainText)
        self.tags.setWordWrap(True)

        self.status = QLabel("", self.detail_content)
        self.status.setObjectName("numericPredictionStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)

        forecast_label = QLabel("Current Forecast", self.detail_content)
        forecast_label.setObjectName("numericCurrentForecastLabel")
        forecast_font = QFont(forecast_label.font())
        forecast_font.setBold(True)
        forecast_label.setFont(forecast_font)

        self.interval = QLabel("", self.detail_content)
        self.interval.setObjectName("numericCurrentInterval")
        self.interval.setTextFormat(Qt.TextFormat.PlainText)
        self.interval.setWordWrap(True)
        interval_font = QFont(self.interval.font())
        interval_font.setPointSize(interval_font.pointSize() + 1)
        interval_font.setBold(True)
        self.interval.setFont(interval_font)

        self.median = QLabel("", self.detail_content)
        self.median.setObjectName("numericCurrentMedian")
        self.median.setTextFormat(Qt.TextFormat.PlainText)
        self.median.setWordWrap(True)

        self.unit_row, self.unit = _detail_value_row(
            "Unit",
            "numericUnitRow",
            "numericUnitValue",
            self.detail_content,
        )
        self.precision_row, self.precision = _detail_value_row(
            "Decimal places",
            "numericPrecisionRow",
            "numericPrecisionValue",
            self.detail_content,
        )
        self.forecast_deadline_row, self.forecast_deadline = _detail_value_row(
            "Forecast deadline",
            "numericForecastDeadlineRow",
            "numericForecastDeadlineValue",
            self.detail_content,
        )
        self.expected_resolution_row, self.expected_resolution = _detail_value_row(
            "Expected resolution",
            "numericExpectedResolutionRow",
            "numericExpectedResolutionValue",
            self.detail_content,
        )
        self.background_section, self.background = _detail_text_section(
            "BACKGROUND",
            "numericBackgroundSection",
            "numericBackgroundValue",
            self.detail_content,
        )
        self.resolution_criteria_section, self.resolution_criteria = (
            _detail_text_section(
                "RESOLUTION CRITERIA",
                "numericResolutionCriteriaSection",
                "numericResolutionCriteriaValue",
                self.detail_content,
            )
        )
        self.rationale_section, self.rationale = _detail_text_section(
            "INITIAL RATIONALE",
            "numericInitialRationaleSection",
            "numericInitialRationaleValue",
            self.detail_content,
        )

        self.next_steps = QLabel(
            "Numeric revisions, Journal entries, resolution, and history "
            "visualization are added in later v0.2 milestones.",
            self.detail_content,
        )
        self.next_steps.setObjectName("numericPredictionNextSteps")
        self.next_steps.setTextFormat(Qt.TextFormat.PlainText)
        self.next_steps.setWordWrap(True)

        detail_layout.addWidget(self.question)
        detail_layout.addWidget(self.tags)
        detail_layout.addWidget(self.status)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(forecast_label)
        detail_layout.addWidget(self.interval)
        detail_layout.addWidget(self.median)
        detail_layout.addWidget(self.unit_row)
        detail_layout.addWidget(self.precision_row)
        detail_layout.addSpacing(10)
        detail_layout.addWidget(self.forecast_deadline_row)
        detail_layout.addWidget(self.expected_resolution_row)
        detail_layout.addWidget(self.background_section)
        detail_layout.addWidget(self.resolution_criteria_section)
        detail_layout.addWidget(self.rationale_section)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(self.next_steps)
        detail_layout.addStretch()

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("numericPredictionDetailScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.detail_content)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.detail_error)
        layout.addWidget(scroll_area, 1)

        self.show_prediction(None)

    @property
    def prediction_id(self) -> int | None:
        """Return the Numeric Prediction currently presented by the screen."""

        return None if self._prediction is None else self._prediction.prediction_id

    def show_prediction(self, prediction: NumericPredictionSnapshot | None) -> None:
        """Present one Numeric Prediction or the honest empty state."""

        self._prediction = prediction
        self._hide_error()
        if prediction is None:
            self.question.clear()
            self.tags.clear()
            self.status.clear()
            self.interval.clear()
            self.median.clear()
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            return

        revision = prediction.current_revision
        self.question.setText(prediction.question)
        self.tags.setText("  ".join(f"#{tag}" for tag in prediction.tags))
        self.tags.setHidden(not prediction.tags)
        self.status.setText(prediction.status.value.upper())
        self.interval.setText(
            f"{revision.confidence_percent}% interval: "
            f"{revision.lower_bound} to {revision.upper_bound} {prediction.unit}"
        )
        self.median.setText(
            f"Median estimate: {revision.median_estimate} {prediction.unit}"
        )
        self.unit.setText(prediction.unit)
        decimal_label = (
            "decimal place" if prediction.decimal_places == 1 else "decimal places"
        )
        self.precision.setText(f"{prediction.decimal_places} {decimal_label}")
        self._show_optional_metadata(prediction)
        self.rationale.setText(revision.rationale or "")
        self.rationale_section.setHidden(not revision.rationale)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)

    def refresh(self) -> None:
        """Reload the presented Numeric Prediction without hiding prior data on error."""

        try:
            prediction = (
                self._operations.get_latest_numeric_prediction()
                if self._prediction is None
                else self._operations.get_numeric_prediction(
                    self._prediction.prediction_id
                )
            )
        except ApplicationError as error:
            self._show_error(
                f"Numeric Prediction Detail could not be refreshed. {error}"
            )
            return
        self.show_prediction(prediction)

    def _show_optional_metadata(self, prediction: NumericPredictionSnapshot) -> None:
        self.forecast_deadline.setText(_format_date(prediction.forecast_deadline))
        self.forecast_deadline_row.setHidden(prediction.forecast_deadline is None)
        self.expected_resolution.setText(_format_date(prediction.expected_resolution))
        self.expected_resolution_row.setHidden(prediction.expected_resolution is None)
        self.background.setText(prediction.background or "")
        self.background_section.setHidden(not prediction.background)
        self.resolution_criteria.setText(prediction.resolution_criteria or "")
        self.resolution_criteria_section.setHidden(not prediction.resolution_criteria)

    def _show_error(self, message: str) -> None:
        self.detail_error.setText(message)
        self.detail_error.setHidden(False)

    def _hide_error(self) -> None:
        self.detail_error.clear()
        self.detail_error.setHidden(True)


class PredictionDetailHost(QWidget):
    """Keep one primary Detail navigation slot while selecting forecast type."""

    def __init__(
        self,
        operations: PredictionOperations,
        binary_detail: PredictionDetailScreen,
        numeric_detail: NumericPredictionDetailScreen,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionDetailHost")
        self._operations = operations
        self._binary_detail = binary_detail
        self._numeric_detail = numeric_detail
        self._current_type: PredictionType | None = None

        self._stack = QStackedWidget(self)
        self._stack.addWidget(binary_detail)
        self._stack.addWidget(numeric_detail)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def show_prediction(self, prediction: PredictionSnapshot | None) -> None:
        """Select and present the existing Binary detail screen."""

        self._current_type = PredictionType.BINARY
        self._binary_detail.show_prediction(prediction)
        self._stack.setCurrentWidget(self._binary_detail)

    def show_numeric_prediction(
        self,
        prediction: NumericPredictionSnapshot | None,
    ) -> None:
        """Select and present the staged Numeric detail screen."""

        self._current_type = PredictionType.NUMERIC
        self._numeric_detail.show_prediction(prediction)
        self._stack.setCurrentWidget(self._numeric_detail)

    def show_latest_prediction(self) -> None:
        """Present the latest persisted forecast type after app restart."""

        binary = self._operations.get_latest_prediction()
        get_latest_numeric = getattr(
            self._operations,
            "get_latest_numeric_prediction",
            lambda: None,
        )
        numeric = get_latest_numeric()
        if numeric is not None and (
            binary is None
            or (numeric.created_at, numeric.prediction_id)
            > (binary.created_at, binary.prediction_id)
        ):
            self.show_numeric_prediction(numeric)
            return
        self._current_type = PredictionType.BINARY
        self._stack.setCurrentWidget(self._binary_detail)
        if binary is None:
            self._binary_detail.show_prediction(None)
        else:
            self._binary_detail.refresh()

    def refresh(self) -> None:
        """Refresh the selected detail type, or select the latest at first visit."""

        if self._current_type is PredictionType.BINARY:
            self._binary_detail.refresh()
        elif self._current_type is PredictionType.NUMERIC:
            self._numeric_detail.refresh()
        else:
            self.show_latest_prediction()


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
        apply_lucide_icon(save_button, LucideIcon.SAVE)
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
        rationale_helper_text = (
            "This explanation stays attached to the new forecast. To record a "
            "thought without changing probability, add a Journal entry."
        )
        rationale_helper = QLabel(rationale_helper_text, self)
        rationale_helper.setObjectName("revisionRationaleHelper")
        rationale_helper.setTextFormat(Qt.TextFormat.PlainText)
        rationale_helper.setWordWrap(True)
        self.rationale_input = QPlainTextEdit(self)
        self.rationale_input.setObjectName("revisionRationaleInput")
        self.rationale_input.setAccessibleName("What changed")
        self.rationale_input.setAccessibleDescription(rationale_helper_text)
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
        apply_lucide_icon(save_button, LucideIcon.SAVE)
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
        layout.addWidget(rationale_helper)
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


class AddJournalEntryDialog(QDialog):
    """Append reasoning without changing the current forecast."""

    journal_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("addJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Add Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Add Journal Entry", self)
        title.setObjectName("addJournalEntryTitle")

        context_heading = QLabel("Forecast at the time", self)
        self.forecast_probability = QLabel(
            f"{prediction.probability_percent}%",
            self,
        )
        self.forecast_probability.setObjectName("journalForecastAtTime")
        self.forecast_probability.setAccessibleName("Forecast at the time")
        context_font = QFont(self.forecast_probability.font())
        context_font.setBold(True)
        context_font.setPointSize(context_font.pointSize() + 2)
        self.forecast_probability.setFont(context_font)

        body_label = QLabel("Journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("journalEntryBodyInput")
        self.body_input.setAccessibleName("Journal entry")
        self.body_input.setPlaceholderText(
            "Record new evidence, reasoning, or a thought that does not change "
            "the forecast."
        )
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("addJournalEntryError")
        self.form_error.setAccessibleName("Add journal entry error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("addJournalEntryButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveJournalEntryButton")
        save_button.setText("Save Journal Entry")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelJournalEntryButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(context_heading)
        layout.addWidget(self.forecast_probability)
        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.body_input, save_button)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def showEvent(self, event: QShowEvent) -> None:
        """Put keyboard focus in the entry body after the modal is shown."""
        super().showEvent(event)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Append one entry; expected failures remain editable in the dialog."""
        self._hide_error()
        body = self.body_input.toPlainText()
        if not body.strip():
            self._show_error("Write a journal entry before saving.")
            self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        try:
            journal_entry = self._operations.add_journal_entry(
                self._prediction_id,
                body,
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.journal_saved.emit(journal_entry)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class CorrectJournalEntryDialog(QDialog):
    """Append a visible correction while retaining every prior Journal body."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        entry: JournalTimelineSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Journal Entry")
        self.setModal(True)
        self.resize(560, 420)
        self._operations = operations
        self._prediction_id = entry.prediction_id
        self._entry_id = entry.entry_id
        self._expected_correction_id = entry.current_correction_id

        title = QLabel("Edit / Correct Journal Entry", self)
        title.setObjectName("correctJournalEntryTitle")

        explanation = QLabel(
            "Saving records a transparent correction. The original and every "
            "earlier version remain in Edit history.",
            self,
        )
        explanation.setObjectName("journalCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        context = QLabel(
            f"Forecast at the time: {entry.forecast_probability_percent}%",
            self,
        )
        context.setObjectName("correctionForecastAtTime")
        context.setTextFormat(Qt.TextFormat.PlainText)

        body_label = QLabel("Corrected journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("correctJournalEntryBodyInput")
        self.body_input.setAccessibleName("Corrected journal entry")
        self.body_input.setPlainText(entry.body)
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("correctJournalEntryError")
        self.form_error.setAccessibleName("Correct journal entry error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("correctJournalEntryButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveJournalCorrectionButton")
        save_button.setText("Save Correction")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelJournalCorrectionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(context)
        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.body_input, save_button)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def showEvent(self, event: QShowEvent) -> None:
        """Focus and select the displayed latest body when shown."""
        super().showEvent(event)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def submit(self) -> None:
        """Append one correction; never replace the displayed entry in place."""
        self._hide_error()
        body = self.body_input.toPlainText()
        if not body.strip():
            self._show_error("Write the corrected journal entry before saving.")
            self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        try:
            correction = self._operations.correct_journal_entry(
                self._prediction_id,
                self._entry_id,
                body,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(correction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ResolvePredictionDialog(QDialog):
    """Record one deliberate Yes/No terminal outcome."""

    prediction_resolved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resolvePredictionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Resolve Prediction")
        self.setModal(True)
        self.resize(570, 520)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Resolve Prediction", self)
        title.setObjectName("resolvePredictionTitle")
        explanation = QLabel(
            "Resolution records a final Yes/No outcome and the current forecast "
            "for scoring. This terminal decision cannot be reopened or changed "
            "in v0.1.",
            self,
        )
        explanation.setObjectName("resolvePredictionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        reviewed = QLabel(
            f"Scoring forecast: {prediction.probability_percent}% "
            f"(revision {prediction.current_revision_sequence})",
            self,
        )
        reviewed.setObjectName("resolveScoringForecast")
        reviewed.setTextFormat(Qt.TextFormat.PlainText)

        outcome_label = QLabel("Outcome", self)
        self.outcome_yes = QRadioButton("Yes", self)
        self.outcome_yes.setObjectName("resolutionOutcomeYes")
        self.outcome_no = QRadioButton("No", self)
        self.outcome_no.setObjectName("resolutionOutcomeNo")
        outcome_row = QWidget(self)
        outcome_layout = QHBoxLayout(outcome_row)
        outcome_layout.setContentsMargins(0, 0, 0, 0)
        outcome_layout.addWidget(self.outcome_yes)
        outcome_layout.addWidget(self.outcome_no)
        outcome_layout.addStretch()

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("resolutionNotesInput")
        self.notes_input.setAccessibleName("Resolution notes")
        self.notes_input.setPlaceholderText(
            "Record the factual source or evidence that determined the outcome."
        )
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("resolutionPostmortemInput")
        self.postmortem_input.setAccessibleName("Postmortem")
        self.postmortem_input.setPlaceholderText(
            "Reflect on what your reasoning or updates got right or wrong."
        )
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("resolvePredictionError")
        self.form_error.setAccessibleName("Resolve prediction error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("resolvePredictionButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("confirmResolvePredictionButton")
        save_button.setText("Resolve")
        save_button.setEnabled(False)
        apply_lucide_icon(save_button, LucideIcon.CIRCLE_CHECK)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelResolvePredictionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reviewed)
        layout.addSpacing(8)
        layout.addWidget(outcome_label)
        layout.addWidget(outcome_row)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input, 1)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.outcome_yes.toggled.connect(
            lambda _checked: save_button.setEnabled(
                self.outcome_yes.isChecked() or self.outcome_no.isChecked()
            )
        )
        self.outcome_no.toggled.connect(
            lambda _checked: save_button.setEnabled(
                self.outcome_yes.isChecked() or self.outcome_no.isChecked()
            )
        )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.notes_input.installEventFilter(self._submit_key_filter)
        self.postmortem_input.installEventFilter(self._submit_key_filter)
        self.setTabOrder(self.outcome_yes, self.outcome_no)
        self.setTabOrder(self.outcome_no, self.notes_input)
        self.setTabOrder(self.notes_input, self.postmortem_input)
        self.setTabOrder(self.postmortem_input, save_button)
        self.outcome_yes.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save exactly one selected outcome; expected failures remain visible."""

        self._hide_error()
        if self.outcome_yes.isChecked():
            outcome = BinaryOutcome.YES
        elif self.outcome_no.isChecked():
            outcome = BinaryOutcome.NO
        else:
            self._show_error("Choose Yes or No before resolving this prediction.")
            return
        try:
            prediction = self._operations.resolve_prediction(
                self._prediction_id,
                outcome,
                resolution_notes=self.notes_input.toPlainText(),
                postmortem=self.postmortem_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.prediction_resolved.emit(prediction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class MarkInvalidDialog(QDialog):
    """Record one deliberate terminal Invalid decision."""

    prediction_invalidated = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("markInvalidDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Mark Prediction Invalid")
        self.setModal(True)
        self.resize(560, 360)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Mark Prediction Invalid", self)
        title.setObjectName("markInvalidTitle")
        explanation = QLabel(
            "Invalid keeps the prediction and its complete history but excludes it "
            "from scoring. This terminal decision cannot be reopened in v0.1.",
            self,
        )
        explanation.setObjectName("markInvalidExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        reason_label = QLabel("Reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("invalidationReasonInput")
        self.reason_input.setAccessibleName("Invalidation reason")
        self.reason_input.setPlaceholderText(
            "For example: the event was cancelled or the criteria became unresolvable."
        )
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("markInvalidError")
        self.form_error.setAccessibleName("Mark invalid error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("markInvalidButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("confirmMarkInvalidButton")
        save_button.setText("Mark Invalid")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.BAN)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelMarkInvalidButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.reason_input.installEventFilter(self._submit_key_filter)
        self.setTabOrder(self.reason_input, save_button)
        self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save one Invalid record; expected failures remain editable."""

        self._hide_error()
        try:
            prediction = self._operations.invalidate_prediction(
                self._prediction_id,
                reason=self.reason_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.prediction_invalidated.emit(prediction)
        self.accept()

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
        self._journal_dialog: AddJournalEntryDialog | None = None
        self._journal_correction_dialog: CorrectJournalEntryDialog | None = None
        self._resolution_dialog: ResolvePredictionDialog | None = None
        self._invalidation_dialog: MarkInvalidDialog | None = None
        self._chart_prediction_id: int | None = None

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
        apply_lucide_icon(self.edit_details_button, LucideIcon.PENCIL)
        self.edit_details_button.clicked.connect(self.open_edit_details)

        action_row = QWidget(self.detail_content)
        action_row.setObjectName("futurePredictionActions")
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        self.revise_forecast_button = QPushButton("Revise Forecast", action_row)
        self.revise_forecast_button.setObjectName("reviseForecastButton")
        apply_lucide_icon(self.revise_forecast_button, LucideIcon.REFRESH)
        self.revise_forecast_button.clicked.connect(self.open_revise_forecast)
        action_layout.addWidget(self.revise_forecast_button)
        self.add_journal_entry_button = QPushButton(
            "Add Journal Entry",
            action_row,
        )
        self.add_journal_entry_button.setObjectName("addJournalEntryButton")
        apply_lucide_icon(self.add_journal_entry_button, LucideIcon.NOTEBOOK_PEN)
        self.add_journal_entry_button.clicked.connect(self.open_add_journal_entry)
        action_layout.addWidget(self.add_journal_entry_button)
        self.resolve_button = QPushButton("Resolve", action_row)
        self.resolve_button.setObjectName("resolvePredictionButton")
        apply_lucide_icon(self.resolve_button, LucideIcon.CIRCLE_CHECK)
        self.resolve_button.clicked.connect(self.open_resolve_prediction)
        action_layout.addWidget(self.resolve_button)
        self.mark_invalid_button = QPushButton("Mark Invalid", action_row)
        self.mark_invalid_button.setObjectName("markInvalidButton")
        apply_lucide_icon(self.mark_invalid_button, LucideIcon.BAN)
        self.mark_invalid_button.clicked.connect(self.open_mark_invalid)
        action_layout.addWidget(self.mark_invalid_button)
        self.delete_button = QPushButton("Delete", action_row)
        self.delete_button.setObjectName("deletePredictionButton")
        apply_lucide_icon(self.delete_button, LucideIcon.TRASH)
        self.delete_button.clicked.connect(self.delete_prediction)
        action_layout.addWidget(self.delete_button)
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

        self.resolution_section = QGroupBox("RESOLUTION", self.detail_content)
        self.resolution_section.setObjectName("predictionResolutionSection")
        resolution_layout = QVBoxLayout(self.resolution_section)
        self.resolution_outcome = QLabel("", self.resolution_section)
        self.resolution_outcome.setObjectName("predictionResolutionOutcome")
        self.resolution_outcome.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_resolved_at = QLabel("", self.resolution_section)
        self.resolution_resolved_at.setObjectName("predictionResolvedAt")
        self.resolution_resolved_at.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring_forecast = QLabel("", self.resolution_section)
        self.resolution_scoring_forecast.setObjectName(
            "predictionResolutionScoringForecast"
        )
        self.resolution_scoring_forecast.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_notes_heading = QLabel(
            "RESOLUTION NOTES",
            self.resolution_section,
        )
        self.resolution_notes_heading.setObjectName("predictionResolutionNotesHeading")
        self.resolution_notes = QLabel("", self.resolution_section)
        self.resolution_notes.setObjectName("predictionResolutionNotes")
        self.resolution_notes.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_notes.setWordWrap(True)
        self.postmortem_heading = QLabel("POSTMORTEM", self.resolution_section)
        self.postmortem_heading.setObjectName("predictionPostmortemHeading")
        self.postmortem = QLabel("", self.resolution_section)
        self.postmortem.setObjectName("predictionPostmortem")
        self.postmortem.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem.setWordWrap(True)
        resolution_layout.addWidget(self.resolution_outcome)
        resolution_layout.addWidget(self.resolution_resolved_at)
        resolution_layout.addWidget(self.resolution_scoring_forecast)
        resolution_layout.addWidget(self.resolution_notes_heading)
        resolution_layout.addWidget(self.resolution_notes)
        resolution_layout.addWidget(self.postmortem_heading)
        resolution_layout.addWidget(self.postmortem)
        self.resolution_section.setHidden(True)

        self.invalidation_section = QGroupBox("INVALID", self.detail_content)
        self.invalidation_section.setObjectName("predictionInvalidationSection")
        invalidation_layout = QVBoxLayout(self.invalidation_section)
        self.invalidated_at = QLabel("", self.invalidation_section)
        self.invalidated_at.setObjectName("predictionInvalidatedAt")
        self.invalidated_at.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason_heading = QLabel(
            "REASON",
            self.invalidation_section,
        )
        self.invalidation_reason_heading.setObjectName(
            "predictionInvalidationReasonHeading"
        )
        self.invalidation_reason = QLabel("", self.invalidation_section)
        self.invalidation_reason.setObjectName("predictionInvalidationReason")
        self.invalidation_reason.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason.setWordWrap(True)
        invalidation_layout.addWidget(self.invalidated_at)
        invalidation_layout.addWidget(self.invalidation_reason_heading)
        invalidation_layout.addWidget(self.invalidation_reason)
        self.invalidation_section.setHidden(True)

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

        timeline_label = QLabel("TIMELINE", self.detail_content)
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
        self.probability_history_chart = ProbabilityHistoryChart(self.detail_content)
        self.probability_history_chart.setObjectName("probabilityHistoryChart")
        self.probability_history_chart.setHidden(True)
        self.chart_placeholder = QLabel(
            "No forecast revisions are available to chart.",
            self.detail_content,
        )
        self.chart_placeholder.setObjectName("probabilityHistoryPlaceholder")
        self.chart_placeholder.setTextFormat(Qt.TextFormat.PlainText)
        self.chart_placeholder.setWordWrap(True)
        self.chart_placeholder.setHidden(True)

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
        detail_layout.addWidget(self.resolution_section)
        detail_layout.addWidget(self.invalidation_section)
        detail_layout.addWidget(self.definition_history)
        detail_layout.addSpacing(16)
        detail_layout.addWidget(timeline_label)
        detail_layout.addWidget(self.forecast_timeline)
        detail_layout.addWidget(self.timeline_placeholder)
        detail_layout.addSpacing(12)
        detail_layout.addWidget(chart_label)
        detail_layout.addWidget(self.probability_history_chart)
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
            self.probability_history_chart.clear()
            self.probability_history_chart.set_timeline_available(True)
            self.probability_history_chart.setHidden(True)
            self.chart_placeholder.setText(
                "No forecast revisions are available to chart."
            )
            self.chart_placeholder.setHidden(True)
            self._chart_prediction_id = None
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            self.definition_history.setHidden(True)
            self.resolution_section.setHidden(True)
            self.invalidation_section.setHidden(True)
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
        journal_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.add_journal_entry_button.setEnabled(journal_allowed)
        if journal_allowed:
            self.add_journal_entry_button.setToolTip(
                "Record evidence or reasoning without changing the forecast."
            )
        else:
            self.add_journal_entry_button.setToolTip(
                f"New Journal entries are not allowed while this prediction is "
                f"{prediction.status.value}. Existing entries can still be corrected."
            )
        terminal_action_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.resolve_button.setEnabled(terminal_action_allowed)
        self.mark_invalid_button.setEnabled(terminal_action_allowed)
        if terminal_action_allowed:
            self.resolve_button.setToolTip(
                "Record a final Yes or No outcome and capture the scoring forecast."
            )
            self.mark_invalid_button.setToolTip(
                "Preserve this prediction but exclude it from scoring."
            )
        else:
            terminal_tooltip = (
                f"This prediction is already {prediction.status.value}; terminal "
                "decisions cannot be changed in v0.1."
            )
            self.resolve_button.setToolTip(terminal_tooltip)
            self.mark_invalid_button.setToolTip(terminal_tooltip)
        delete_allowed = (
            prediction.status is PredictionStatus.OPEN and prediction.deletion_allowed
        )
        self.delete_button.setEnabled(delete_allowed)
        if delete_allowed:
            self.delete_button.setToolTip(
                "Permanently delete this untouched Open prediction."
            )
        elif prediction.status is PredictionStatus.LOCKED:
            self.delete_button.setToolTip(
                "Locked predictions are preserved. Use Mark Invalid when appropriate."
            )
        elif prediction.status in (
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        ):
            self.delete_button.setToolTip(
                "Terminal prediction history cannot be deleted from the normal "
                "interface."
            )
        else:
            self.delete_button.setToolTip(
                "Predictions with meaningful history are preserved. Use Mark Invalid "
                "when appropriate."
            )
        self.tags.setText("  ".join(f"#{tag}" for tag in prediction.tags))
        self.tags.setHidden(not prediction.tags)
        self._show_optional_metadata(prediction)
        self._show_terminal_information(prediction)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
        self._load_definition_history(prediction.prediction_id)
        timeline_available = self._load_timeline(prediction.prediction_id)
        self.probability_history_chart.set_timeline_available(timeline_available)
        self._load_probability_history(prediction.prediction_id)

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

    def open_add_journal_entry(self) -> None:
        """Refresh context, then open a side-effect-free Journal dialog."""
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"New Journal entries are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
            return
        dialog = AddJournalEntryDialog(self._operations, prediction, self)
        self._journal_dialog = dialog
        dialog.journal_saved.connect(self._journal_saved)
        dialog.finished.connect(self._journal_dialog_finished)
        dialog.open()

    def open_resolve_prediction(self) -> None:
        """Refresh reviewed context before opening the terminal resolution form."""

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"This prediction is already {prediction.status.value} and cannot "
                "be resolved again."
            )
            return
        dialog = ResolvePredictionDialog(self._operations, prediction, self)
        self._resolution_dialog = dialog
        dialog.prediction_resolved.connect(self.show_prediction)
        dialog.finished.connect(self._resolution_dialog_finished)
        dialog.open()

    def open_mark_invalid(self) -> None:
        """Refresh reviewed context before opening the terminal Invalid form."""

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"This prediction is already {prediction.status.value} and cannot "
                "be marked Invalid again."
            )
            return
        dialog = MarkInvalidDialog(self._operations, prediction, self)
        self._invalidation_dialog = dialog
        dialog.prediction_invalidated.connect(self.show_prediction)
        dialog.finished.connect(self._invalidation_dialog_finished)
        dialog.open()

    def delete_prediction(self) -> None:
        """Confirm and permanently delete only refreshed untouched Open state."""

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if (
            not prediction.deletion_allowed
            or prediction.status is not PredictionStatus.OPEN
        ):
            self._show_error(
                "Only an untouched Open prediction can be deleted. Use Mark Invalid "
                "to preserve meaningful history outside scoring."
            )
            return
        answer = QMessageBox.warning(
            self,
            "Permanently delete prediction?",
            "This permanently deletes the prediction and its initial forecast. "
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            latest = self._operations.delete_prediction(
                prediction.prediction_id,
                expected_revision_id=prediction.current_revision_id,
                expected_metadata_version=prediction.metadata_version,
                confirm_permanent_deletion=True,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(latest)

    def open_correct_journal_entry(self, entry: JournalTimelineSnapshot) -> None:
        """Refresh the Journal entry before opening its correction form."""
        try:
            events = self._operations.list_timeline(entry.prediction_id)
        except ApplicationError as error:
            self._show_error(f"Journal entry could not be refreshed. {error}")
            return
        current_entry = next(
            (
                event
                for event in events
                if hasattr(event, "entry_id") and event.entry_id == entry.entry_id
            ),
            None,
        )
        if current_entry is None:
            self._show_error(
                "This Journal entry could not be found. Refresh Prediction Detail "
                "and try again."
            )
            return
        self._hide_error()
        dialog = CorrectJournalEntryDialog(self._operations, current_entry, self)
        self._journal_correction_dialog = dialog
        dialog.correction_saved.connect(self._journal_correction_saved)
        dialog.finished.connect(self._journal_correction_dialog_finished)
        dialog.open()

    def _edit_dialog_finished(self, _result: int) -> None:
        self._edit_dialog = None

    def _revision_dialog_finished(self, _result: int) -> None:
        self._revision_dialog = None

    def _journal_dialog_finished(self, _result: int) -> None:
        self._journal_dialog = None

    def _journal_correction_dialog_finished(self, _result: int) -> None:
        self._journal_correction_dialog = None

    def _resolution_dialog_finished(self, _result: int) -> None:
        self._resolution_dialog = None

    def _invalidation_dialog_finished(self, _result: int) -> None:
        self._invalidation_dialog = None

    def _journal_saved(self, _result: object) -> None:
        if self._prediction is not None:
            self.show_prediction(self._prediction)

    def _journal_correction_saved(self, _corrected: object) -> None:
        if self._prediction is None:
            return
        self.show_prediction(self._prediction)

    def _show_optional_metadata(self, prediction: PredictionSnapshot) -> None:
        self.forecast_deadline.setText(_format_date(prediction.forecast_deadline))
        self.forecast_deadline_row.setHidden(prediction.forecast_deadline is None)
        self.expected_resolution.setText(_format_date(prediction.expected_resolution))
        self.expected_resolution_row.setHidden(prediction.expected_resolution is None)
        self.background.setText(prediction.background or "")
        self.background_section.setHidden(not prediction.background)
        self.resolution_criteria.setText(prediction.resolution_criteria or "")
        self.resolution_criteria_section.setHidden(not prediction.resolution_criteria)

    def _show_terminal_information(self, prediction: PredictionSnapshot) -> None:
        """Render immutable terminal facts without inventing absent notes."""

        resolution = prediction.resolution
        self.resolution_section.setHidden(resolution is None)
        if resolution is not None:
            self.resolution_outcome.setText(
                f"Outcome: {resolution.outcome.value.capitalize()}"
            )
            self.resolution_resolved_at.setText(
                f"Resolved: {_format_local_timestamp(resolution.resolved_at)}"
            )
            self.resolution_scoring_forecast.setText(
                f"Scoring forecast: {resolution.scoring_probability_percent}% "
                f"(revision {resolution.scoring_revision_sequence})"
            )
            self.resolution_notes.setText(resolution.resolution_notes or "")
            has_notes = resolution.resolution_notes is not None
            self.resolution_notes_heading.setHidden(not has_notes)
            self.resolution_notes.setHidden(not has_notes)
            self.postmortem.setText(resolution.postmortem or "")
            has_postmortem = resolution.postmortem is not None
            self.postmortem_heading.setHidden(not has_postmortem)
            self.postmortem.setHidden(not has_postmortem)

        invalidation = prediction.invalidation
        self.invalidation_section.setHidden(invalidation is None)
        if invalidation is not None:
            self.invalidated_at.setText(
                f"Marked Invalid: "
                f"{_format_local_timestamp(invalidation.invalidated_at)}"
            )
            self.invalidation_reason.setText(invalidation.reason or "")
            has_reason = invalidation.reason is not None
            self.invalidation_reason_heading.setHidden(not has_reason)
            self.invalidation_reason.setHidden(not has_reason)

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

    def _load_timeline(self, prediction_id: int) -> bool:
        try:
            events = self._operations.list_timeline(prediction_id)
        except ApplicationError as error:
            self.forecast_timeline.setHidden(True)
            self.timeline_placeholder.setText("Timeline could not be loaded.")
            self.timeline_placeholder.setHidden(False)
            self._show_error(str(error))
            return False

        _clear_widget_layout(self.forecast_timeline_layout)
        for event in events:
            if hasattr(event, "entry_id"):
                self.forecast_timeline_layout.addWidget(
                    _journal_entry_widget(
                        event,
                        self.forecast_timeline,
                        self.open_correct_journal_entry,
                    )
                )
            else:
                self.forecast_timeline_layout.addWidget(
                    _forecast_timeline_widget(event, self.forecast_timeline)
                )
        self.forecast_timeline.setHidden(not events)
        self.timeline_placeholder.setText("No timeline entries are available.")
        self.timeline_placeholder.setHidden(bool(events))
        return True

    def _load_probability_history(self, prediction_id: int) -> None:
        """Reload chart revisions without turning a read failure into emptiness."""

        try:
            revisions = self._operations.list_forecast_revisions(prediction_id)
        except ApplicationError as error:
            has_matching_history = (
                self._chart_prediction_id == prediction_id
                and self.probability_history_chart.revision_count > 0
            )
            if has_matching_history:
                self.probability_history_chart.setHidden(False)
                self.chart_placeholder.setText(
                    "Probability history could not be refreshed. The last loaded "
                    "chart remains visible."
                )
                failure_action = "refreshed"
            else:
                self.probability_history_chart.clear()
                self.probability_history_chart.setHidden(True)
                self._chart_prediction_id = None
                self.chart_placeholder.setText(
                    "Probability history could not be loaded."
                )
                failure_action = "loaded"
            self.chart_placeholder.setHidden(False)
            self._show_error(
                f"Probability history could not be {failure_action}. {error}"
            )
            return

        self.probability_history_chart.set_revisions(revisions)
        self._chart_prediction_id = prediction_id
        has_revisions = self.probability_history_chart.revision_count > 0
        self.probability_history_chart.setHidden(not has_revisions)
        self.chart_placeholder.setText("No forecast revisions are available to chart.")
        self.chart_placeholder.setHidden(has_revisions)

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


def _forecast_timeline_widget(
    revision: ForecastTimelineSnapshot,
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

    if revision.previous_probability_percent is None:
        probability_text = f"FORECAST  {revision.probability_percent}%"
    else:
        probability_text = (
            f"FORECAST  {revision.previous_probability_percent}% "
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


def _journal_entry_widget(
    entry: JournalTimelineSnapshot,
    parent: QWidget,
    correct_entry: Callable[[JournalTimelineSnapshot], None],
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"journalEntry{entry.entry_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)

    timestamp = QLabel(_format_local_timestamp(entry.created_at), frame)
    timestamp.setObjectName(f"journalEntryTimestamp{entry.entry_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(timestamp)

    heading_row = QWidget(frame)
    heading_layout = QHBoxLayout(heading_row)
    heading_layout.setContentsMargins(0, 0, 0, 0)
    kind = QLabel("JOURNAL", heading_row)
    kind.setObjectName(f"journalEntryKind{entry.entry_id}")
    kind.setTextFormat(Qt.TextFormat.PlainText)
    heading_layout.addWidget(kind)
    if entry.current_correction_id is not None:
        latest_correction = entry.corrections[-1]
        edited = QLabel(
            f"Edited {_format_local_timestamp(latest_correction.corrected_at)}",
            heading_row,
        )
        edited.setObjectName(f"journalEntryEdited{entry.entry_id}")
        edited.setTextFormat(Qt.TextFormat.PlainText)
        heading_layout.addWidget(edited)
    heading_layout.addStretch()
    correct_button = QPushButton("Correct Entry", heading_row)
    correct_button.setObjectName(f"correctJournalEntryButton{entry.entry_id}")
    apply_lucide_icon(correct_button, LucideIcon.PENCIL, size=16)
    correct_button.setToolTip(
        "Save a correction while preserving the original and prior versions."
    )
    correct_button.clicked.connect(
        lambda _checked=False, current=entry: correct_entry(current)
    )
    heading_layout.addWidget(correct_button)
    layout.addWidget(heading_row)

    body = QLabel(entry.body, frame)
    body.setObjectName(f"journalEntryBody{entry.entry_id}")
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(body)

    forecast_context = QLabel(
        f"Forecast at the time: {entry.forecast_probability_percent}%",
        frame,
    )
    forecast_context.setObjectName(f"journalEntryForecastAtTime{entry.entry_id}")
    forecast_context.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(forecast_context)

    if entry.corrections:
        layout.addWidget(_journal_edit_history_widget(entry, frame))
    return frame


def _journal_edit_history_widget(
    entry: JournalTimelineSnapshot,
    parent: QWidget,
) -> QGroupBox:
    prior_version_count = len(entry.corrections)
    suffix = "version" if prior_version_count == 1 else "versions"
    history = QGroupBox(
        f"Edit history ({prior_version_count} prior {suffix})",
        parent,
    )
    history.setObjectName(f"journalEntryEditHistory{entry.entry_id}")
    history.setCheckable(True)
    history.setChecked(False)

    content = QWidget(history)
    content.setObjectName(f"journalEntryEditHistoryContent{entry.entry_id}")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(4, 4, 4, 4)

    original_heading = QLabel(
        f"Original · {_format_local_timestamp(entry.created_at)}",
        content,
    )
    original_heading.setObjectName(f"journalEntryOriginalHeading{entry.entry_id}")
    original_heading.setTextFormat(Qt.TextFormat.PlainText)
    original_body = QLabel(entry.original_body, content)
    original_body.setObjectName(f"journalEntryOriginalBody{entry.entry_id}")
    original_body.setTextFormat(Qt.TextFormat.PlainText)
    original_body.setWordWrap(True)
    original_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    content_layout.addWidget(original_heading)
    content_layout.addWidget(original_body)

    for index, correction in enumerate(entry.corrections[:-1], start=1):
        correction_heading = QLabel(
            f"Correction {index} · {_format_local_timestamp(correction.corrected_at)}",
            content,
        )
        correction_heading.setObjectName(
            f"journalCorrectionHeading{correction.correction_id}"
        )
        correction_heading.setTextFormat(Qt.TextFormat.PlainText)
        correction_body = QLabel(correction.body, content)
        correction_body.setObjectName(
            f"journalCorrectionBody{correction.correction_id}"
        )
        correction_body.setTextFormat(Qt.TextFormat.PlainText)
        correction_body.setWordWrap(True)
        correction_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_layout.addWidget(correction_heading)
        content_layout.addWidget(correction_body)

    history_layout = QVBoxLayout(history)
    history_layout.addWidget(content)
    history.toggled.connect(content.setVisible)
    content.setHidden(True)
    return history


class _MultilineSubmitKeyFilter(QObject):
    """Make Ctrl+Enter submit while an ordinary Enter remains a newline."""

    def __init__(
        self,
        submit: Callable[[], None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._submit = submit

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            modifiers = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
                modifiers & Qt.KeyboardModifier.ControlModifier
            ):
                self._submit()
                return True
        return super().eventFilter(watched, event)


def _clear_widget_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
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
