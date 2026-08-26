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
    BinaryResolutionHistory,
    DefinitionChange,
    FixedPrecisionValue,
    InvalidationHistory,
    InvalidationReasonCorrection,
    NumericResolutionCorrection,
    NumericResolutionHistory,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
    ResolutionCorrection,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.numeric_history_chart import NumericHistoryChart
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
    """Read-only Numeric Prediction data needed by the Detail screen."""

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
    resolution: NumericResolutionSnapshot | None
    invalidation: InvalidationSnapshot | None
    deletion_allowed: bool


class NumericResolutionSnapshot(Protocol):
    """Read-only exact Numeric Resolution shown on Prediction Detail."""

    resolution_id: int
    prediction_id: int
    actual_value: object
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    resolution_notes: str | None
    postmortem: str | None


class NumericForecastTimelineSnapshot(Protocol):
    """One immutable Numeric ForecastRevision prepared for the timeline."""

    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    lower_bound: object
    median_estimate: object
    upper_bound: object
    confidence_percent: int
    previous_lower_bound: object | None
    previous_median_estimate: object | None
    previous_upper_bound: object | None
    previous_confidence_percent: int | None
    rationale: str | None


class NumericJournalTimelineSnapshot(Protocol):
    """A Numeric Journal entry with its exact interval-at-the-time context."""

    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    numeric_forecast_revision_id: int
    forecast_revision_sequence: int
    lower_bound: object
    median_estimate: object
    upper_bound: object
    confidence_percent: int
    current_correction_id: int | None
    corrections: tuple[JournalCorrectionSnapshot, ...]


class NumericForecastReviewTimelineSnapshot(Protocol):
    """One Numeric Forecast Review with its retained interval context."""

    review_id: int
    prediction_id: int
    created_at: datetime
    numeric_forecast_revision_id: int
    forecast_revision_sequence: int
    lower_bound: object
    median_estimate: object
    upper_bound: object
    confidence_percent: int
    note: str | None


NumericTimelineSnapshot = (
    NumericForecastTimelineSnapshot
    | NumericJournalTimelineSnapshot
    | NumericForecastReviewTimelineSnapshot
)


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


class ForecastReviewTimelineSnapshot(Protocol):
    """One Binary Forecast Review with its retained probability context."""

    review_id: int
    prediction_id: int
    created_at: datetime
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    note: str | None


TimelineSnapshot = (
    ForecastTimelineSnapshot | JournalTimelineSnapshot | ForecastReviewTimelineSnapshot
)


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

    def add_forecast_review(
        self,
        prediction_id: int,
        *,
        note: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> ForecastReviewTimelineSnapshot:
        """Record deliberate retention of the current Binary forecast."""

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

    def get_binary_resolution_history(
        self,
        prediction_id: int,
    ) -> BinaryResolutionHistory:
        """Return original, effective, and corrected Binary Resolution facts."""

    def get_numeric_resolution_history(
        self,
        prediction_id: int,
    ) -> NumericResolutionHistory:
        """Return original, effective, and corrected Numeric Resolution facts."""

    def get_invalidation_history(self, prediction_id: int) -> InvalidationHistory:
        """Return original, effective, and corrected Invalidation reasons."""

    def correct_binary_resolution(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None,
        postmortem: str | None,
        correction_reason: str | None = None,
        expected_correction_id: int | None,
    ) -> BinaryResolutionHistory:
        """Append one audited Binary Resolution correction."""

    def correct_numeric_resolution(
        self,
        prediction_id: int,
        actual_value: object,
        *,
        resolution_notes: str | None,
        postmortem: str | None,
        correction_reason: str | None = None,
        expected_correction_id: int | None,
    ) -> NumericResolutionHistory:
        """Append one audited exact Numeric Resolution correction."""

    def correct_invalidation_reason(
        self,
        prediction_id: int,
        reason: str | None,
        *,
        expected_correction_id: int | None,
    ) -> InvalidationHistory:
        """Append one audited Invalidation-reason correction."""

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

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> PredictionSnapshot | NumericPredictionSnapshot:
        """Return one current Prediction of either type for Detail routing."""

    def list_numeric_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[NumericRevisionSnapshot, ...]:
        """Return Numeric revisions in immutable sequence order."""

    def revise_numeric_forecast(
        self,
        prediction_id: int,
        lower_bound: object,
        median_estimate: object,
        upper_bound: object,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPredictionSnapshot:
        """Append one eligible, changed Numeric ForecastRevision."""

    def add_numeric_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericJournalTimelineSnapshot:
        """Append a Numeric Journal entry tied to the reviewed interval."""

    def add_numeric_forecast_review(
        self,
        prediction_id: int,
        *,
        note: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericForecastReviewTimelineSnapshot:
        """Record deliberate retention of the current Numeric interval."""

    def correct_numeric_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> NumericJournalTimelineSnapshot:
        """Append one transparent Numeric Journal correction."""

    def list_numeric_timeline(
        self,
        prediction_id: int,
    ) -> tuple[NumericTimelineSnapshot, ...]:
        """Return Numeric Forecast and Journal events in causal order."""

    def resolve_numeric_prediction(
        self,
        prediction_id: int,
        actual_value: object,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPredictionSnapshot:
        """Persist a Numeric outcome and exact scoring interval."""

    def invalidate_numeric_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPredictionSnapshot:
        """Preserve a Numeric Prediction as terminal and unscored."""

    def delete_numeric_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> NumericPredictionSnapshot | None:
        """Delete only an explicitly confirmed untouched Numeric Prediction."""

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
        prediction_type: PredictionType | None = None,
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
    """Present and extend the current Numeric Prediction's honest history."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("numericPredictionDetailScreen")
        self._operations = operations
        self._prediction: NumericPredictionSnapshot | None = None
        self._resolution_history: NumericResolutionHistory | None = None
        self._invalidation_history: InvalidationHistory | None = None

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

        actions = QWidget(self.detail_content)
        actions.setObjectName("numericPredictionActions")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        self.revise_forecast_button = QPushButton("Revise Interval", actions)
        self.revise_forecast_button.setObjectName("reviseNumericForecastButton")
        self.revise_forecast_button.setAccessibleName("Revise numeric interval")
        apply_lucide_icon(self.revise_forecast_button, LucideIcon.PENCIL)
        self.add_journal_entry_button = QPushButton("Add Journal Entry", actions)
        self.add_journal_entry_button.setObjectName("addNumericJournalEntryButton")
        self.add_journal_entry_button.setAccessibleName("Add Numeric Journal entry")
        apply_lucide_icon(self.add_journal_entry_button, LucideIcon.CIRCLE_PLUS)
        self.review_forecast_button = QPushButton("Keep this interval", actions)
        self.review_forecast_button.setObjectName("reviewNumericForecastButton")
        self.review_forecast_button.setAccessibleName(
            "Record a Review retaining this numeric interval"
        )
        apply_lucide_icon(self.review_forecast_button, LucideIcon.CIRCLE_CHECK)
        self.resolve_button = QPushButton("Resolve", actions)
        self.resolve_button.setObjectName("resolveNumericPredictionButton")
        apply_lucide_icon(self.resolve_button, LucideIcon.CIRCLE_CHECK)
        self.mark_invalid_button = QPushButton("Mark Invalid", actions)
        self.mark_invalid_button.setObjectName("markNumericPredictionInvalidButton")
        apply_lucide_icon(self.mark_invalid_button, LucideIcon.BAN)
        self.delete_button = QPushButton("Delete", actions)
        self.delete_button.setObjectName("deleteNumericPredictionButton")
        apply_lucide_icon(self.delete_button, LucideIcon.TRASH)
        actions_layout.addWidget(self.revise_forecast_button)
        actions_layout.addWidget(self.add_journal_entry_button)
        actions_layout.addWidget(self.review_forecast_button)
        actions_layout.addWidget(self.resolve_button)
        actions_layout.addWidget(self.mark_invalid_button)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()

        self.resolution_section = QGroupBox("RESOLVED", self.detail_content)
        self.resolution_section.setObjectName("numericResolutionSection")
        resolution_layout = QVBoxLayout(self.resolution_section)
        self.resolution_actual = QLabel("", self.resolution_section)
        self.resolution_actual.setObjectName("numericResolutionActualValue")
        self.resolution_actual.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_time = QLabel("", self.resolution_section)
        self.resolution_time.setObjectName("numericResolutionTime")
        self.resolution_time.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring = QLabel("", self.resolution_section)
        self.resolution_scoring.setObjectName("numericResolutionScoringForecast")
        self.resolution_scoring.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring.setWordWrap(True)
        self.resolution_notes = QLabel("", self.resolution_section)
        self.resolution_notes.setObjectName("numericResolutionNotes")
        self.resolution_notes.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_notes.setWordWrap(True)
        self.postmortem = QLabel("", self.resolution_section)
        self.postmortem.setObjectName("numericResolutionPostmortem")
        self.postmortem.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem.setWordWrap(True)
        self.correct_resolution_button = QPushButton(
            "Correct Resolution",
            self.resolution_section,
        )
        self.correct_resolution_button.setObjectName("correctNumericResolutionButton")
        self.correct_resolution_button.setAccessibleName(
            "Correct Numeric Resolution or Postmortem"
        )
        self.correct_resolution_button.setToolTip(
            "Correct the actual value or notes, or add or correct the Postmortem. "
            "The original Resolution remains in history."
        )
        apply_lucide_icon(self.correct_resolution_button, LucideIcon.PENCIL)
        self.resolution_history = _collapsible_history_group(
            "Resolution correction history",
            "numericResolutionCorrectionHistory",
            self.resolution_section,
        )
        resolution_layout.addWidget(self.resolution_actual)
        resolution_layout.addWidget(self.resolution_time)
        resolution_layout.addWidget(self.resolution_scoring)
        resolution_layout.addWidget(self.resolution_notes)
        resolution_layout.addWidget(self.postmortem)
        resolution_layout.addWidget(
            self.correct_resolution_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        resolution_layout.addWidget(self.resolution_history)
        self.resolution_section.setHidden(True)

        self.invalidation_section = QGroupBox("INVALID", self.detail_content)
        self.invalidation_section.setObjectName("numericInvalidationSection")
        invalidation_layout = QVBoxLayout(self.invalidation_section)
        self.invalidation_time = QLabel("", self.invalidation_section)
        self.invalidation_time.setObjectName("numericInvalidationTime")
        self.invalidation_time.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason = QLabel("", self.invalidation_section)
        self.invalidation_reason.setObjectName("numericInvalidationReason")
        self.invalidation_reason.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason.setWordWrap(True)
        self.correct_invalidation_button = QPushButton(
            "Correct Reason",
            self.invalidation_section,
        )
        self.correct_invalidation_button.setObjectName(
            "correctNumericInvalidationReasonButton"
        )
        self.correct_invalidation_button.setToolTip(
            "Append a correction while preserving the original Invalid reason."
        )
        apply_lucide_icon(self.correct_invalidation_button, LucideIcon.PENCIL)
        self.invalidation_history = _collapsible_history_group(
            "Invalidation correction history",
            "numericInvalidationCorrectionHistory",
            self.invalidation_section,
        )
        invalidation_layout.addWidget(self.invalidation_time)
        invalidation_layout.addWidget(self.invalidation_reason)
        invalidation_layout.addWidget(
            self.correct_invalidation_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        invalidation_layout.addWidget(self.invalidation_history)
        self.invalidation_section.setHidden(True)

        history_label = QLabel("INTERVAL HISTORY", self.detail_content)
        history_label.setObjectName("numericHistoryLabel")
        history_font = QFont(history_label.font())
        history_font.setBold(True)
        history_label.setFont(history_font)
        self.history_error = QLabel("", self.detail_content)
        self.history_error.setObjectName("numericHistoryError")
        self.history_error.setTextFormat(Qt.TextFormat.PlainText)
        self.history_error.setWordWrap(True)
        self.history_error.setHidden(True)
        self.history_chart = NumericHistoryChart(self.detail_content)

        timeline_label = QLabel("TIMELINE", self.detail_content)
        timeline_label.setObjectName("numericTimelineLabel")
        timeline_font = QFont(timeline_label.font())
        timeline_font.setBold(True)
        timeline_label.setFont(timeline_font)
        self.timeline_error = QLabel("", self.detail_content)
        self.timeline_error.setObjectName("numericTimelineError")
        self.timeline_error.setTextFormat(Qt.TextFormat.PlainText)
        self.timeline_error.setWordWrap(True)
        self.timeline_error.setHidden(True)
        self.timeline_content = QWidget(self.detail_content)
        self.timeline_content.setObjectName("numericTimelineContent")
        self.timeline_layout = QVBoxLayout(self.timeline_content)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(8)

        self.next_steps = QLabel(
            "Numeric archive views, Dashboard support, and analytics arrive in "
            "later v0.2 milestones.",
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
        detail_layout.addWidget(self.resolution_section)
        detail_layout.addWidget(self.invalidation_section)
        detail_layout.addSpacing(10)
        detail_layout.addWidget(actions)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(history_label)
        detail_layout.addWidget(self.history_error)
        detail_layout.addWidget(self.history_chart)
        detail_layout.addSpacing(14)
        detail_layout.addWidget(timeline_label)
        detail_layout.addWidget(self.timeline_error)
        detail_layout.addWidget(self.timeline_content)
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
        self.revise_forecast_button.clicked.connect(self.open_revise_forecast)
        self.add_journal_entry_button.clicked.connect(self.open_add_journal_entry)
        self.review_forecast_button.clicked.connect(self.open_forecast_review)
        self.resolve_button.clicked.connect(self.open_resolve_prediction)
        self.mark_invalid_button.clicked.connect(self.open_mark_invalid)
        self.delete_button.clicked.connect(self.delete_prediction)
        self.correct_resolution_button.clicked.connect(self.open_correct_resolution)
        self.correct_invalidation_button.clicked.connect(
            self.open_correct_invalidation_reason
        )

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
            self.history_chart.clear()
            self.history_error.setHidden(True)
            self._clear_timeline()
            self.timeline_error.setHidden(True)
            self.revise_forecast_button.setEnabled(False)
            self.add_journal_entry_button.setEnabled(False)
            self.review_forecast_button.setEnabled(False)
            self.resolve_button.setEnabled(False)
            self.mark_invalid_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.correct_resolution_button.setEnabled(False)
            self.correct_invalidation_button.setEnabled(False)
            self._resolution_history = None
            self._invalidation_history = None
            self.resolution_section.setHidden(True)
            self.invalidation_section.setHidden(True)
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
        self.revise_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.add_journal_entry_button.setEnabled(
            prediction.status in (PredictionStatus.OPEN, PredictionStatus.LOCKED)
        )
        self.review_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.review_forecast_button.setToolTip(
            "Record deliberate reconsideration while keeping this interval unchanged."
            if prediction.status is PredictionStatus.OPEN
            else "Forecast Reviews can be recorded only while Open."
        )
        terminal_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.resolve_button.setEnabled(terminal_allowed)
        self.mark_invalid_button.setEnabled(terminal_allowed)
        self.delete_button.setEnabled(
            prediction.status is PredictionStatus.OPEN and prediction.deletion_allowed
        )
        self._show_terminal_information(prediction)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
        self._load_history(prediction.prediction_id)
        self._load_timeline(prediction.prediction_id)

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

    def _show_terminal_information(
        self,
        prediction: NumericPredictionSnapshot,
    ) -> None:
        resolution = prediction.resolution
        if resolution is None:
            self._resolution_history = None
            self.correct_resolution_button.setEnabled(False)
            self.resolution_history.setHidden(True)
            self.resolution_section.setHidden(True)
        else:
            try:
                history = self._operations.get_numeric_resolution_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                effective = resolution
                self._resolution_history = None
                self.correct_resolution_button.setEnabled(False)
                self.resolution_history.setHidden(True)
                self._show_error(f"Resolution history is unavailable. {error}")
            else:
                effective = history.effective
                self._resolution_history = history
                self.correct_resolution_button.setEnabled(True)
                _show_numeric_resolution_correction_history(
                    self.resolution_history,
                    history,
                    prediction.unit,
                )
            self.resolution_actual.setText(
                f"Actual value: {effective.actual_value} {prediction.unit}"
            )
            self.resolution_time.setText(
                f"Resolved {_format_local_timestamp(resolution.resolved_at)}"
            )
            self.resolution_scoring.setText(
                f"Scoring interval (revision {resolution.scoring_revision_sequence}): "
                f"{_numeric_forecast_text(prediction.current_revision, prediction.unit)}"
            )
            self.resolution_notes.setText(
                ""
                if not effective.resolution_notes
                else f"Resolution notes: {effective.resolution_notes}"
            )
            self.resolution_notes.setHidden(not effective.resolution_notes)
            self.postmortem.setText(
                ""
                if not effective.postmortem
                else f"Postmortem: {effective.postmortem}"
            )
            self.postmortem.setHidden(not effective.postmortem)
            self.resolution_section.setHidden(False)
        invalidation = prediction.invalidation
        if invalidation is None:
            self._invalidation_history = None
            self.correct_invalidation_button.setEnabled(False)
            self.invalidation_history.setHidden(True)
            self.invalidation_section.setHidden(True)
        else:
            try:
                invalidation_history = self._operations.get_invalidation_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                effective_invalidation = invalidation
                self._invalidation_history = None
                self.correct_invalidation_button.setEnabled(False)
                self.invalidation_history.setHidden(True)
                self._show_error(f"Invalidation history is unavailable. {error}")
            else:
                effective_invalidation = invalidation_history.effective
                self._invalidation_history = invalidation_history
                self.correct_invalidation_button.setEnabled(True)
                _show_invalidation_correction_history(
                    self.invalidation_history,
                    invalidation_history,
                )
            self.invalidation_time.setText(
                f"Marked Invalid {_format_local_timestamp(invalidation.invalidated_at)}"
            )
            self.invalidation_reason.setText(
                ""
                if not effective_invalidation.reason
                else f"Reason: {effective_invalidation.reason}"
            )
            self.invalidation_reason.setHidden(not effective_invalidation.reason)
            self.invalidation_section.setHidden(False)

    def _show_error(self, message: str) -> None:
        self.detail_error.setText(message)
        self.detail_error.setHidden(False)

    def _hide_error(self) -> None:
        self.detail_error.clear()
        self.detail_error.setHidden(True)

    def _load_history(self, prediction_id: int) -> None:
        try:
            revisions = self._operations.list_numeric_forecast_revisions(prediction_id)
        except ApplicationError as error:
            self.history_error.setText(
                f"Numeric interval history is unavailable. {error}"
            )
            self.history_error.setHidden(False)
            return
        self.history_chart.set_revisions(revisions)
        self.history_error.setHidden(True)

    def _load_timeline(self, prediction_id: int) -> None:
        try:
            events = self._operations.list_numeric_timeline(prediction_id)
        except ApplicationError as error:
            self.timeline_error.setText(f"Numeric timeline is unavailable. {error}")
            self.timeline_error.setHidden(False)
            return
        self._clear_timeline()
        for event in events:
            if hasattr(event, "review_id"):
                self.timeline_layout.addWidget(self._review_timeline_row(event))
            elif hasattr(event, "revision_id"):
                self.timeline_layout.addWidget(self._forecast_timeline_row(event))
            else:
                self.timeline_layout.addWidget(self._journal_timeline_row(event))
        if not events:
            empty = QLabel("No Numeric ForecastRevisions have been recorded.")
            empty.setObjectName("numericTimelineEmptyState")
            empty.setTextFormat(Qt.TextFormat.PlainText)
            self.timeline_layout.addWidget(empty)
        self.timeline_error.setHidden(True)

    def _clear_timeline(self) -> None:
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            if widget := item.widget():
                widget.setParent(None)
                widget.deleteLater()

    def _forecast_timeline_row(self, event: NumericForecastTimelineSnapshot) -> QWidget:
        row = QWidget(self.timeline_content)
        row.setObjectName(f"numericTimelineForecast{event.revision_id}")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        timestamp = QLabel(_format_local_timestamp(event.created_at), row)
        timestamp.setTextFormat(Qt.TextFormat.PlainText)
        values = QLabel(
            f"FORECAST  {event.confidence_percent}% interval: "
            f"{event.lower_bound} to {event.upper_bound} {self._prediction.unit if self._prediction else ''}; "
            f"Median: {event.median_estimate}",
            row,
        )
        values.setObjectName(f"numericForecastValues{event.revision_id}")
        values.setTextFormat(Qt.TextFormat.PlainText)
        values.setWordWrap(True)
        layout.addWidget(timestamp)
        layout.addWidget(values)
        if event.rationale:
            rationale = QLabel(event.rationale, row)
            rationale.setObjectName(f"numericForecastRationale{event.revision_id}")
            rationale.setTextFormat(Qt.TextFormat.PlainText)
            rationale.setWordWrap(True)
            layout.addWidget(rationale)
        return row

    def _journal_timeline_row(self, event: NumericJournalTimelineSnapshot) -> QWidget:
        row = QWidget(self.timeline_content)
        row.setObjectName(f"numericTimelineJournal{event.entry_id}")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        timestamp = QLabel(_format_local_timestamp(event.created_at), row)
        timestamp.setTextFormat(Qt.TextFormat.PlainText)
        heading = QLabel("JOURNAL", row)
        heading.setTextFormat(Qt.TextFormat.PlainText)
        body = QLabel(event.body, row)
        body.setObjectName(f"numericJournalBody{event.entry_id}")
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        context = QLabel(
            f"Forecast at the time: {event.confidence_percent}% interval: "
            f"{event.lower_bound} to {event.upper_bound} {self._prediction.unit if self._prediction else ''}; "
            f"Median: {event.median_estimate}",
            row,
        )
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        layout.addWidget(timestamp)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addWidget(context)
        if event.current_correction_id is not None:
            edited = QLabel(
                f"Edited {_format_local_timestamp(event.corrections[-1].corrected_at)}",
                row,
            )
            edited.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(edited)
            layout.addWidget(_journal_edit_history_widget(event, row))
        correct = QPushButton("Correct Entry", row)
        correct.setObjectName(f"correctNumericJournalEntryButton{event.entry_id}")
        correct.clicked.connect(
            lambda _checked=False, current=event: self.open_correct_journal_entry(
                current
            )
        )
        layout.addWidget(correct)
        return row

    def _review_timeline_row(
        self,
        event: NumericForecastReviewTimelineSnapshot,
    ) -> QWidget:
        row = QWidget(self.timeline_content)
        row.setObjectName(f"numericTimelineReview{event.review_id}")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        timestamp = QLabel(_format_local_timestamp(event.created_at), row)
        timestamp.setTextFormat(Qt.TextFormat.PlainText)
        heading = QLabel("REVIEW  INTERVAL RETAINED", row)
        heading.setTextFormat(Qt.TextFormat.PlainText)
        unit = self._prediction.unit if self._prediction else ""
        context = QLabel(
            f"{event.confidence_percent}% interval: {event.lower_bound} to "
            f"{event.upper_bound} {unit}; Median: {event.median_estimate} {unit}",
            row,
        )
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        layout.addWidget(timestamp)
        layout.addWidget(heading)
        layout.addWidget(context)
        if event.note:
            note = QLabel(event.note, row)
            note.setObjectName(f"numericReviewNote{event.review_id}")
            note.setTextFormat(Qt.TextFormat.PlainText)
            note.setWordWrap(True)
            layout.addWidget(note)
        return row

    def open_revise_forecast(self) -> None:
        if self._prediction is None:
            return
        self.refresh()
        if (
            self._prediction is None
            or self._prediction.status is not PredictionStatus.OPEN
        ):
            return
        dialog = ReviseNumericForecastDialog(self._operations, self._prediction, self)
        dialog.revision_saved.connect(self.show_prediction)
        dialog.open()

    def open_add_journal_entry(self) -> None:
        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = AddNumericJournalEntryDialog(self._operations, self._prediction, self)
        dialog.journal_saved.connect(lambda _entry: self.refresh())
        dialog.open()

    def open_forecast_review(self) -> None:
        """Refresh, then offer a side-effect-free Open-only Review dialog."""

        if self._prediction is None:
            return
        self.refresh()
        if (
            self._prediction is None
            or self._prediction.status is not PredictionStatus.OPEN
        ):
            self._show_error("Forecast Reviews can be recorded only while Open.")
            return
        dialog = ForecastReviewDialog(self._operations, self._prediction, self)
        dialog.review_saved.connect(lambda _review: self.refresh())
        dialog.open()

    def open_resolve_prediction(self) -> None:
        """Refresh reviewed Numeric context before opening terminal resolution."""

        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = ResolveNumericPredictionDialog(
            self._operations,
            self._prediction,
            self,
        )
        dialog.prediction_resolved.connect(self.show_prediction)
        dialog.open()

    def open_mark_invalid(self) -> None:
        """Refresh reviewed Numeric context before opening terminal invalidation."""

        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = MarkNumericPredictionInvalidDialog(
            self._operations,
            self._prediction,
            self,
        )
        dialog.prediction_invalidated.connect(self.show_prediction)
        dialog.open()

    def delete_prediction(self) -> None:
        """Confirm permanent deletion of refreshed untouched Numeric state."""

        if self._prediction is None:
            return
        self.refresh()
        prediction = self._prediction
        if (
            prediction is None
            or prediction.status is not PredictionStatus.OPEN
            or not prediction.deletion_allowed
        ):
            self._show_error(
                "Only an untouched Open prediction can be deleted. Use Mark "
                "Invalid to preserve meaningful history outside scoring."
            )
            return
        answer = QMessageBox.warning(
            self,
            "Permanently delete Numeric Prediction?",
            "This permanently deletes the Numeric Prediction and its initial "
            "interval. This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            latest = self._operations.delete_numeric_prediction(
                prediction.prediction_id,
                expected_revision_id=prediction.current_revision.revision_id,
                expected_metadata_version=prediction.metadata_version,
                confirm_permanent_deletion=True,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(latest)

    def open_correct_journal_entry(self, entry: NumericJournalTimelineSnapshot) -> None:
        dialog = CorrectNumericJournalEntryDialog(self._operations, entry, self)
        dialog.correction_saved.connect(lambda _entry: self.refresh())
        dialog.open()

    def open_correct_resolution(self) -> None:
        """Refresh, then correct the effective Numeric Resolution append-only."""

        if self._prediction is None:
            return
        self.refresh()
        history = self._resolution_history
        prediction = self._prediction
        if history is None or prediction is None:
            return
        dialog = CorrectNumericResolutionDialog(
            self._operations,
            prediction,
            history,
            self,
        )
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.open()

    def open_correct_invalidation_reason(self) -> None:
        """Refresh, then correct the effective Invalid reason append-only."""

        if self._prediction is None:
            return
        self.refresh()
        history = self._invalidation_history
        if history is None:
            return
        dialog = CorrectInvalidationReasonDialog(
            self._operations,
            history,
            self,
        )
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.open()


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


class ReviseNumericForecastDialog(QDialog):
    """Collect a changed numeric interval and append one immutable revision."""

    revision_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("reviseNumericForecastDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Revise Numeric Forecast")
        self.setModal(True)
        self.resize(560, 520)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Revise Numeric Forecast", self)
        title.setObjectName("reviseNumericForecastTitle")
        current = QLabel(
            _numeric_forecast_text(prediction.current_revision, prediction.unit),
            self,
        )
        current.setObjectName("reviseNumericCurrentForecast")
        current.setTextFormat(Qt.TextFormat.PlainText)
        current.setWordWrap(True)

        lower_label = QLabel("Lower bound", self)
        self.lower_bound_input = QLineEdit(
            str(prediction.current_revision.lower_bound), self
        )
        self.lower_bound_input.setObjectName("numericRevisionLowerBoundInput")
        lower_label.setBuddy(self.lower_bound_input)
        median_label = QLabel("Median estimate", self)
        self.median_estimate_input = QLineEdit(
            str(prediction.current_revision.median_estimate), self
        )
        self.median_estimate_input.setObjectName("numericRevisionMedianEstimateInput")
        median_label.setBuddy(self.median_estimate_input)
        upper_label = QLabel("Upper bound", self)
        self.upper_bound_input = QLineEdit(
            str(prediction.current_revision.upper_bound), self
        )
        self.upper_bound_input.setObjectName("numericRevisionUpperBoundInput")
        upper_label.setBuddy(self.upper_bound_input)
        confidence_label = QLabel("Confidence", self)
        self.confidence_input = QSpinBox(self)
        self.confidence_input.setObjectName("numericRevisionConfidenceInput")
        self.confidence_input.setRange(1, 99)
        self.confidence_input.setSingleStep(5)
        self.confidence_input.setSuffix("%")
        self.confidence_input.setValue(prediction.current_revision.confidence_percent)
        confidence_label.setBuddy(self.confidence_input)

        rationale_label = QLabel("What changed? (optional)", self)
        self.rationale_input = QPlainTextEdit(self)
        self.rationale_input.setObjectName("numericRevisionRationaleInput")
        self.rationale_input.setAccessibleName("What changed")
        self.rationale_input.setMaximumHeight(100)
        self.rationale_input.setTabChangesFocus(True)
        rationale_label.setBuddy(self.rationale_input)
        helper = QLabel(
            "This explanation stays attached to the new interval. To record a "
            "thought without changing it, add a Journal entry.",
            self,
        )
        helper.setObjectName("numericRevisionRationaleHelper")
        helper.setTextFormat(Qt.TextFormat.PlainText)
        helper.setWordWrap(True)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("reviseNumericForecastError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericForecastRevisionButton")
        save.setText("Save Revision")
        apply_lucide_icon(save, LucideIcon.SAVE)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "cancelNumericForecastRevisionButton"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(QLabel("Current forecast", self))
        layout.addWidget(current)
        layout.addSpacing(8)
        for label, input_widget in (
            (lower_label, self.lower_bound_input),
            (median_label, self.median_estimate_input),
            (upper_label, self.upper_bound_input),
            (confidence_label, self.confidence_input),
        ):
            layout.addWidget(label)
            layout.addWidget(input_widget)
        layout.addWidget(rationale_label)
        layout.addWidget(self.rationale_input)
        layout.addWidget(helper)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.lower_bound_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.lower_bound_input.selectAll()

    def submit(self) -> None:
        self._hide_error()
        try:
            prediction = self._operations.revise_numeric_forecast(
                self._prediction_id,
                self.lower_bound_input.text(),
                self.median_estimate_input.text(),
                self.upper_bound_input.text(),
                self.confidence_input.value(),
                rationale=self.rationale_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.revision_saved.emit(prediction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class AddNumericJournalEntryDialog(QDialog):
    """Append reasoning while preserving the current numeric interval."""

    journal_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("addNumericJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Add Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version
        title = QLabel("Add Journal Entry", self)
        context = QLabel(
            f"Forecast at the time: {_numeric_forecast_text(prediction.current_revision, prediction.unit)}",
            self,
        )
        context.setObjectName("numericJournalForecastAtTime")
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        body_label = QLabel("Journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("numericJournalEntryBodyInput")
        self.body_input.setAccessibleName("Journal entry")
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("addNumericJournalEntryError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericJournalEntryButton")
        save.setText("Add Entry")
        apply_lucide_icon(save, LucideIcon.SAVE)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(context)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self._hide_error()
        if not self.body_input.toPlainText().strip():
            self._show_error("Write a Journal entry before saving.")
            return
        try:
            entry = self._operations.add_numeric_journal_entry(
                self._prediction_id,
                self.body_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.journal_saved.emit(entry)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ResolveNumericPredictionDialog(QDialog):
    """Record one exact, immutable Numeric outcome and scoring interval."""

    prediction_resolved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resolveNumericPredictionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Resolve Numeric Prediction")
        self.setModal(True)
        self.resize(580, 520)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Resolve Numeric Prediction", self)
        explanation = QLabel(
            "Resolution records the realized quantity and captures the current "
            "interval for scoring. The terminal decision cannot be reopened; an "
            "honest mistake in its facts can later be corrected with visible "
            "history.",
            self,
        )
        explanation.setObjectName("resolveNumericPredictionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reviewed = QLabel(
            f"Scoring forecast: {_numeric_forecast_text(prediction.current_revision, prediction.unit)} "
            f"(revision {prediction.current_revision.sequence})",
            self,
        )
        reviewed.setObjectName("resolveNumericScoringForecast")
        reviewed.setTextFormat(Qt.TextFormat.PlainText)
        reviewed.setWordWrap(True)
        actual_label = QLabel(f"Actual value ({prediction.unit})", self)
        self.actual_value_input = QLineEdit(self)
        self.actual_value_input.setObjectName("numericResolutionActualValueInput")
        self.actual_value_input.setAccessibleName(f"Actual value in {prediction.unit}")
        actual_label.setBuddy(self.actual_value_input)
        notes_label = QLabel("Resolution notes (optional)", self)
        self.resolution_notes_input = QPlainTextEdit(self)
        self.resolution_notes_input.setObjectName("numericResolutionNotesInput")
        self.resolution_notes_input.setMaximumHeight(100)
        self.resolution_notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.resolution_notes_input)
        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("numericResolutionPostmortemInput")
        self.postmortem_input.setMaximumHeight(100)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("resolveNumericPredictionError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericResolutionButton")
        save.setText("Resolve Prediction")
        apply_lucide_icon(save, LucideIcon.CIRCLE_CHECK)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "cancelNumericResolutionButton"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reviewed)
        layout.addSpacing(8)
        layout.addWidget(actual_label)
        layout.addWidget(self.actual_value_input)
        layout.addWidget(notes_label)
        layout.addWidget(self.resolution_notes_input)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.actual_value_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            prediction = self._operations.resolve_numeric_prediction(
                self._prediction_id,
                self.actual_value_input.text(),
                resolution_notes=self.resolution_notes_input.toPlainText(),
                postmortem=self.postmortem_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.prediction_resolved.emit(prediction)
        self.accept()


class MarkNumericPredictionInvalidDialog(QDialog):
    """Record one immutable Numeric Invalid decision and optional reason."""

    prediction_invalidated = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("markNumericPredictionInvalidDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Mark Numeric Prediction Invalid")
        self.setModal(True)
        self.resize(560, 360)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version
        title = QLabel("Mark Numeric Prediction Invalid", self)
        explanation = QLabel(
            "Invalid preserves this prediction and its complete history but "
            "excludes it from scoring. The terminal decision cannot be reopened; "
            "its reason can later be corrected with visible history.",
            self,
        )
        explanation.setObjectName("markNumericInvalidExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reason_label = QLabel("Reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("numericInvalidationReasonInput")
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("markNumericPredictionInvalidError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericInvalidationButton")
        save.setText("Mark Invalid")
        apply_lucide_icon(save, LucideIcon.BAN)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "cancelNumericInvalidationButton"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            prediction = self._operations.invalidate_numeric_prediction(
                self._prediction_id,
                reason=self.reason_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.prediction_invalidated.emit(prediction)
        self.accept()


class CorrectBinaryResolutionDialog(QDialog):
    """Append one confirmed Binary Resolution correction snapshot."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        history: BinaryResolutionHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctBinaryResolutionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Resolution")
        self.setModal(True)
        self.resize(600, 620)
        self._operations = operations
        self._prediction_id = history.original.prediction_id
        self._expected_correction_id = history.current_correction_id
        self._current = history.effective

        title = QLabel("Correct Resolution", self)
        explanation = QLabel(
            "This appends a transparent correction. The original Resolution, "
            "resolution time, scoring forecast, and every earlier correction "
            "remain in history.",
            self,
        )
        explanation.setObjectName("binaryResolutionCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        outcome_label = QLabel("Effective outcome", self)
        self.outcome_yes = QRadioButton("Yes", self)
        self.outcome_yes.setObjectName("correctResolutionOutcomeYes")
        self.outcome_no = QRadioButton("No", self)
        self.outcome_no.setObjectName("correctResolutionOutcomeNo")
        if self._current.outcome is BinaryOutcome.YES:
            self.outcome_yes.setChecked(True)
        else:
            self.outcome_no.setChecked(True)
        outcome_row = QWidget(self)
        outcome_layout = QHBoxLayout(outcome_row)
        outcome_layout.setContentsMargins(0, 0, 0, 0)
        outcome_layout.addWidget(self.outcome_yes)
        outcome_layout.addWidget(self.outcome_no)
        outcome_layout.addStretch()

        self.score_change_notice = QLabel(
            "Changing the outcome changes this Prediction's Brier score and "
            "calibration result. A correction explanation is required.",
            self,
        )
        self.score_change_notice.setObjectName("binaryResolutionScoreChangeNotice")
        self.score_change_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.score_change_notice.setWordWrap(True)

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("correctResolutionNotesInput")
        self.notes_input.setPlainText(self._current.resolution_notes or "")
        self.notes_input.setMaximumHeight(110)
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("correctResolutionPostmortemInput")
        self.postmortem_input.setPlainText(self._current.postmortem or "")
        self.postmortem_input.setMaximumHeight(110)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        reason_label = QLabel("Correction explanation", self)
        self.reason_input = QLineEdit(self)
        self.reason_input.setObjectName("binaryOutcomeCorrectionReasonInput")
        self.reason_input.setPlaceholderText(
            "Required only when changing Yes to No or No to Yes"
        )
        reason_label.setBuddy(self.reason_input)

        self.form_error = _dialog_error_label(
            "correctBinaryResolutionError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveBinaryResolutionCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(outcome_label)
        layout.addWidget(outcome_row)
        layout.addWidget(self.score_change_notice)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.outcome_yes.toggled.connect(self._update_score_change_notice)
        self.outcome_no.toggled.connect(self._update_score_change_notice)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._update_score_change_notice()

    def submit(self) -> None:
        self.form_error.setHidden(True)
        outcome = (
            BinaryOutcome.YES if self.outcome_yes.isChecked() else BinaryOutcome.NO
        )
        notes = _normalized_optional_text(self.notes_input.toPlainText())
        postmortem = _normalized_optional_text(self.postmortem_input.toPlainText())
        correction_reason = _normalized_optional_text(self.reason_input.text())
        outcome_changed = outcome is not self._current.outcome
        if (
            outcome is self._current.outcome
            and notes == self._current.resolution_notes
            and postmortem == self._current.postmortem
        ):
            self._show_error(
                "Change the outcome, Resolution notes, or Postmortem before saving."
            )
            return
        if outcome_changed and correction_reason is None:
            self._show_error("Explain why the recorded outcome is being corrected.")
            self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        if not _confirm_terminal_correction(self, score_affecting=outcome_changed):
            return
        try:
            history = self._operations.correct_binary_resolution(
                self._prediction_id,
                outcome,
                resolution_notes=notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _update_score_change_notice(self) -> None:
        selected = (
            BinaryOutcome.YES if self.outcome_yes.isChecked() else BinaryOutcome.NO
        )
        self.score_change_notice.setHidden(selected is self._current.outcome)

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)


class CorrectNumericResolutionDialog(QDialog):
    """Append one confirmed exact Numeric Resolution correction snapshot."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        history: NumericResolutionHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctNumericResolutionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Numeric Resolution")
        self.setModal(True)
        self.resize(600, 620)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._unit = prediction.unit
        self._decimal_places = prediction.decimal_places
        self._expected_correction_id = history.current_correction_id
        self._current = history.effective

        title = QLabel("Correct Numeric Resolution", self)
        explanation = QLabel(
            "This appends a transparent correction. The original Resolution, "
            "resolution time, scoring interval, and every earlier correction "
            "remain in history.",
            self,
        )
        explanation.setObjectName("numericResolutionCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        actual_label = QLabel(f"Effective actual value ({prediction.unit})", self)
        self.actual_value_input = QLineEdit(self)
        self.actual_value_input.setObjectName("correctNumericActualValueInput")
        self.actual_value_input.setText(str(self._current.actual_value))
        actual_label.setBuddy(self.actual_value_input)
        self.score_change_notice = QLabel(
            "Changing the actual value changes containment, error, and interval "
            "score results. A correction explanation is required.",
            self,
        )
        self.score_change_notice.setObjectName("numericResolutionScoreChangeNotice")
        self.score_change_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.score_change_notice.setWordWrap(True)

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("correctNumericResolutionNotesInput")
        self.notes_input.setPlainText(self._current.resolution_notes or "")
        self.notes_input.setMaximumHeight(110)
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("correctNumericResolutionPostmortemInput")
        self.postmortem_input.setPlainText(self._current.postmortem or "")
        self.postmortem_input.setMaximumHeight(110)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        reason_label = QLabel("Correction explanation", self)
        self.reason_input = QLineEdit(self)
        self.reason_input.setObjectName("numericOutcomeCorrectionReasonInput")
        self.reason_input.setPlaceholderText(
            "Required only when changing the actual value"
        )
        reason_label.setBuddy(self.reason_input)

        self.form_error = _dialog_error_label(
            "correctNumericResolutionError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveNumericResolutionCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(actual_label)
        layout.addWidget(self.actual_value_input)
        layout.addWidget(self.score_change_notice)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.actual_value_input.textChanged.connect(self._update_score_change_notice)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._update_score_change_notice()

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            actual_value = FixedPrecisionValue.from_value(
                self.actual_value_input.text(),
                self._decimal_places,
                field="actual_value",
            )
        except PredictionValidationError as error:
            self._show_error(str(error))
            return
        notes = _normalized_optional_text(self.notes_input.toPlainText())
        postmortem = _normalized_optional_text(self.postmortem_input.toPlainText())
        correction_reason = _normalized_optional_text(self.reason_input.text())
        actual_changed = actual_value != self._current.actual_value
        if (
            not actual_changed
            and notes == self._current.resolution_notes
            and postmortem == self._current.postmortem
        ):
            self._show_error(
                "Change the actual value, Resolution notes, or Postmortem before "
                "saving."
            )
            return
        if actual_changed and correction_reason is None:
            self._show_error(
                "Explain why the recorded actual value is being corrected."
            )
            self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        if not _confirm_terminal_correction(self, score_affecting=actual_changed):
            return
        try:
            history = self._operations.correct_numeric_resolution(
                self._prediction_id,
                self.actual_value_input.text(),
                resolution_notes=notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _update_score_change_notice(self) -> None:
        try:
            proposed = FixedPrecisionValue.from_value(
                self.actual_value_input.text(),
                self._decimal_places,
                field="actual_value",
            )
        except PredictionValidationError:
            self.score_change_notice.setHidden(False)
            return
        self.score_change_notice.setHidden(proposed == self._current.actual_value)

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)


class CorrectInvalidationReasonDialog(QDialog):
    """Append one confirmed Invalidation-reason correction."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        history: InvalidationHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctInvalidationReasonDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Invalid Reason")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = history.original.prediction_id
        self._expected_correction_id = history.current_correction_id
        self._current_reason = history.effective.reason

        title = QLabel("Correct Invalid Reason", self)
        explanation = QLabel(
            "This appends a transparent correction. The Prediction remains "
            "Invalid, and its original reason, invalidation time, and every "
            "earlier correction remain in history.",
            self,
        )
        explanation.setObjectName("invalidationReasonCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reason_label = QLabel("Effective reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("correctInvalidationReasonInput")
        self.reason_input.setPlainText(self._current_reason or "")
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)
        self.form_error = _dialog_error_label(
            "correctInvalidationReasonError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveInvalidationReasonCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        reason = _normalized_optional_text(self.reason_input.toPlainText())
        if reason == self._current_reason:
            self._show_error("Change or clear the Invalid reason before saving.")
            return
        if not _confirm_terminal_correction(self, score_affecting=False):
            return
        try:
            history = self._operations.correct_invalidation_reason(
                self._prediction_id,
                reason,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)


class CorrectNumericJournalEntryDialog(QDialog):
    """Append a transparent correction to a Numeric Journal entry."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        entry: NumericJournalTimelineSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctNumericJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = entry.prediction_id
        self._entry_id = entry.entry_id
        self._expected_correction_id = entry.current_correction_id
        title = QLabel("Edit / Correct Journal Entry", self)
        explanation = QLabel(
            "Saving records a transparent correction. Earlier versions remain in history.",
            self,
        )
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("correctNumericJournalEntryBodyInput")
        self.body_input.setPlainText(entry.body)
        self.body_input.setTabChangesFocus(True)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("correctNumericJournalEntryError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericJournalCorrectionButton")
        save.setText("Save Correction")
        apply_lucide_icon(save, LucideIcon.SAVE)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def submit(self) -> None:
        self._hide_error()
        if not self.body_input.toPlainText().strip():
            self._show_error("Write the corrected Journal entry before saving.")
            return
        try:
            correction = self._operations.correct_numeric_journal_entry(
                self._prediction_id,
                self._entry_id,
                self.body_input.toPlainText(),
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


class ForecastReviewDialog(QDialog):
    """Record deliberate reconsideration without changing the forecast."""

    review_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("forecastReviewDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(True)
        self.resize(540, 330)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_metadata_version = prediction.metadata_version
        self._is_numeric = hasattr(prediction, "current_revision")
        if self._is_numeric:
            numeric = prediction
            revision = numeric.current_revision
            self._expected_revision_id = revision.revision_id
            action_text = "Keep this interval"
            context_text = _numeric_forecast_text(revision, numeric.unit)
        else:
            binary = prediction
            self._expected_revision_id = binary.current_revision_id
            action_text = f"Still at {binary.probability_percent}%"
            context_text = f"{binary.probability_percent}%"
        self.setWindowTitle(action_text)

        title = QLabel(action_text, self)
        title.setObjectName("forecastReviewTitle")
        title_font = QFont(title.font())
        title_font.setBold(True)
        title.setFont(title_font)
        explanation = QLabel(
            "Record that you deliberately reconsidered this forecast and chose to "
            "keep it unchanged.",
            self,
        )
        explanation.setObjectName("forecastReviewExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        context = QLabel(context_text, self)
        context.setObjectName("forecastReviewContext")
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)

        note_label = QLabel("Review note (optional)", self)
        self.note_input = QPlainTextEdit(self)
        self.note_input.setObjectName("forecastReviewNoteInput")
        self.note_input.setAccessibleName("Optional Forecast Review note")
        self.note_input.setPlaceholderText(
            "What did you reconsider before retaining this forecast?"
        )
        self.note_input.setTabChangesFocus(True)
        note_label.setBuddy(self.note_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("forecastReviewError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveForecastReviewButton")
        save.setText("Save Review")
        save.setDefault(True)
        apply_lucide_icon(save, LucideIcon.SAVE)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(context)
        layout.addSpacing(8)
        layout.addWidget(note_label)
        layout.addWidget(self.note_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.note_input.installEventFilter(self._submit_key_filter)

    def submit(self) -> None:
        """Save one immutable Review while retaining expected failures inline."""

        self.form_error.setHidden(True)
        kwargs = {
            "note": self.note_input.toPlainText(),
            "expected_revision_id": self._expected_revision_id,
            "expected_metadata_version": self._expected_metadata_version,
        }
        try:
            if self._is_numeric:
                review = self._operations.add_numeric_forecast_review(
                    self._prediction_id,
                    **kwargs,
                )
            else:
                review = self._operations.add_forecast_review(
                    self._prediction_id,
                    **kwargs,
                )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.review_saved.emit(review)
        self.accept()


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
            "for scoring. The terminal decision cannot be reopened; an honest "
            "mistake in its facts can later be corrected with visible history.",
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
            "from scoring. The terminal decision cannot be reopened; its reason "
            "can later be corrected with visible history.",
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
        self._terminal_correction_dialog: QDialog | None = None
        self._resolution_history: BinaryResolutionHistory | None = None
        self._invalidation_history: InvalidationHistory | None = None
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
        self.review_forecast_button = QPushButton("Still at", action_row)
        self.review_forecast_button.setObjectName("reviewForecastButton")
        self.review_forecast_button.setAccessibleName(
            "Record a Review retaining this probability"
        )
        apply_lucide_icon(self.review_forecast_button, LucideIcon.CIRCLE_CHECK)
        self.review_forecast_button.clicked.connect(self.open_forecast_review)
        action_layout.addWidget(self.review_forecast_button)
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
        self.correct_resolution_button = QPushButton(
            "Correct Resolution",
            self.resolution_section,
        )
        self.correct_resolution_button.setObjectName("correctResolutionButton")
        self.correct_resolution_button.setAccessibleName(
            "Correct Binary Resolution or Postmortem"
        )
        self.correct_resolution_button.setToolTip(
            "Correct the outcome or notes, or add or correct the Postmortem. "
            "The original Resolution remains in history."
        )
        apply_lucide_icon(self.correct_resolution_button, LucideIcon.PENCIL)
        self.resolution_history = _collapsible_history_group(
            "Resolution correction history",
            "resolutionCorrectionHistory",
            self.resolution_section,
        )
        resolution_layout.addWidget(self.resolution_outcome)
        resolution_layout.addWidget(self.resolution_resolved_at)
        resolution_layout.addWidget(self.resolution_scoring_forecast)
        resolution_layout.addWidget(self.resolution_notes_heading)
        resolution_layout.addWidget(self.resolution_notes)
        resolution_layout.addWidget(self.postmortem_heading)
        resolution_layout.addWidget(self.postmortem)
        resolution_layout.addWidget(
            self.correct_resolution_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        resolution_layout.addWidget(self.resolution_history)
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
        self.correct_invalidation_button = QPushButton(
            "Correct Reason",
            self.invalidation_section,
        )
        self.correct_invalidation_button.setObjectName(
            "correctInvalidationReasonButton"
        )
        self.correct_invalidation_button.setToolTip(
            "Append a correction while preserving the original Invalid reason."
        )
        apply_lucide_icon(self.correct_invalidation_button, LucideIcon.PENCIL)
        self.invalidation_history = _collapsible_history_group(
            "Invalidation correction history",
            "invalidationCorrectionHistory",
            self.invalidation_section,
        )
        invalidation_layout.addWidget(self.invalidated_at)
        invalidation_layout.addWidget(self.invalidation_reason_heading)
        invalidation_layout.addWidget(self.invalidation_reason)
        invalidation_layout.addWidget(
            self.correct_invalidation_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        invalidation_layout.addWidget(self.invalidation_history)
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

        self.correct_resolution_button.clicked.connect(self.open_correct_resolution)
        self.correct_invalidation_button.clicked.connect(
            self.open_correct_invalidation_reason
        )

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
            self.review_forecast_button.setEnabled(False)
            self.chart_placeholder.setText(
                "No forecast revisions are available to chart."
            )
            self.chart_placeholder.setHidden(True)
            self._chart_prediction_id = None
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            self.definition_history.setHidden(True)
            self.correct_resolution_button.setEnabled(False)
            self.correct_invalidation_button.setEnabled(False)
            self._resolution_history = None
            self._invalidation_history = None
            self.resolution_section.setHidden(True)
            self.invalidation_section.setHidden(True)
            return

        self.question.setText(prediction.question)
        self.status.setText(prediction.status.value.upper())
        self.probability.setText(f"{prediction.probability_percent}%")
        self.review_forecast_button.setText(
            f"Still at {prediction.probability_percent}%"
        )
        self.review_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.review_forecast_button.setToolTip(
            "Record deliberate reconsideration while keeping this probability."
            if prediction.status is PredictionStatus.OPEN
            else "Forecast Reviews can be recorded only while Open."
        )
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

    def open_forecast_review(self) -> None:
        """Refresh, then offer a side-effect-free Open-only Review dialog."""

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status is not PredictionStatus.OPEN:
            self._show_error("Forecast Reviews can be recorded only while Open.")
            return
        dialog = ForecastReviewDialog(self._operations, prediction, self)
        dialog.review_saved.connect(self._review_saved)
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

    def open_correct_resolution(self) -> None:
        """Refresh, then correct the effective Binary Resolution append-only."""

        if self._prediction is None:
            return
        self.refresh()
        history = self._resolution_history
        if history is None:
            return
        dialog = CorrectBinaryResolutionDialog(self._operations, history, self)
        self._terminal_correction_dialog = dialog
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.finished.connect(self._terminal_correction_dialog_finished)
        dialog.open()

    def open_correct_invalidation_reason(self) -> None:
        """Refresh, then correct the effective Invalid reason append-only."""

        if self._prediction is None:
            return
        self.refresh()
        history = self._invalidation_history
        if history is None:
            return
        dialog = CorrectInvalidationReasonDialog(
            self._operations,
            history,
            self,
        )
        self._terminal_correction_dialog = dialog
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.finished.connect(self._terminal_correction_dialog_finished)
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

    def _terminal_correction_dialog_finished(self, _result: int) -> None:
        self._terminal_correction_dialog = None

    def _journal_saved(self, _result: object) -> None:
        if self._prediction is not None:
            self.show_prediction(self._prediction)

    def _review_saved(self, _result: object) -> None:
        if self._prediction is not None:
            self.refresh()

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
        """Render latest effective facts plus inspectable append-only history."""

        resolution = prediction.resolution
        self.resolution_section.setHidden(resolution is None)
        if resolution is not None:
            try:
                history = self._operations.get_binary_resolution_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                self._resolution_history = None
                effective = resolution
                self.correct_resolution_button.setEnabled(False)
                self.resolution_history.setHidden(True)
                self._show_error(f"Resolution history is unavailable. {error}")
            else:
                effective = history.effective
                self._resolution_history = history
                self.correct_resolution_button.setEnabled(True)
                _show_binary_resolution_correction_history(
                    self.resolution_history,
                    history,
                )
            self.resolution_outcome.setText(
                f"Outcome: {effective.outcome.value.capitalize()}"
            )
            self.resolution_resolved_at.setText(
                f"Resolved: {_format_local_timestamp(resolution.resolved_at)}"
            )
            self.resolution_scoring_forecast.setText(
                f"Scoring forecast: {resolution.scoring_probability_percent}% "
                f"(revision {resolution.scoring_revision_sequence})"
            )
            self.resolution_notes.setText(effective.resolution_notes or "")
            has_notes = effective.resolution_notes is not None
            self.resolution_notes_heading.setHidden(not has_notes)
            self.resolution_notes.setHidden(not has_notes)
            self.postmortem.setText(effective.postmortem or "")
            has_postmortem = effective.postmortem is not None
            self.postmortem_heading.setHidden(not has_postmortem)
            self.postmortem.setHidden(not has_postmortem)
        else:
            self._resolution_history = None
            self.correct_resolution_button.setEnabled(False)
            self.resolution_history.setHidden(True)

        invalidation = prediction.invalidation
        self.invalidation_section.setHidden(invalidation is None)
        if invalidation is not None:
            try:
                history = self._operations.get_invalidation_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                self._invalidation_history = None
                effective_invalidation = invalidation
                self.correct_invalidation_button.setEnabled(False)
                self.invalidation_history.setHidden(True)
                self._show_error(f"Invalidation history is unavailable. {error}")
            else:
                effective_invalidation = history.effective
                self._invalidation_history = history
                self.correct_invalidation_button.setEnabled(True)
                _show_invalidation_correction_history(
                    self.invalidation_history,
                    history,
                )
            self.invalidated_at.setText(
                f"Marked Invalid: "
                f"{_format_local_timestamp(invalidation.invalidated_at)}"
            )
            self.invalidation_reason.setText(effective_invalidation.reason or "")
            has_reason = effective_invalidation.reason is not None
            self.invalidation_reason_heading.setHidden(not has_reason)
            self.invalidation_reason.setHidden(not has_reason)
        else:
            self._invalidation_history = None
            self.correct_invalidation_button.setEnabled(False)
            self.invalidation_history.setHidden(True)

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
            if hasattr(event, "review_id"):
                self.forecast_timeline_layout.addWidget(
                    _forecast_review_widget(event, self.forecast_timeline)
                )
            elif hasattr(event, "entry_id"):
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


def _collapsible_history_group(
    title: str,
    object_name: str,
    parent: QWidget,
) -> QGroupBox:
    group = QGroupBox(title, parent)
    group.setObjectName(object_name)
    group.setCheckable(True)
    group.setChecked(False)
    content = QWidget(group)
    content.setObjectName(f"{object_name}Content")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(4, 4, 4, 4)
    layout = QVBoxLayout(group)
    layout.addWidget(content)
    group.toggled.connect(content.setVisible)
    content.setHidden(True)
    group.setHidden(True)
    return group


def _history_content(group: QGroupBox) -> tuple[QWidget, QVBoxLayout]:
    content = group.findChild(QWidget, f"{group.objectName()}Content")
    if content is None or not isinstance(content.layout(), QVBoxLayout):
        raise RuntimeError("Terminal correction history content is unavailable.")
    return content, content.layout()


def _show_binary_resolution_correction_history(
    group: QGroupBox,
    history: BinaryResolutionHistory,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Resolution",
            history.original.resolved_at,
            (
                ("Outcome", history.original.outcome.value.capitalize()),
                ("Resolution notes", history.original.resolution_notes),
                ("Postmortem", history.original.postmortem),
            ),
            "binaryResolutionOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(_binary_resolution_correction_frame(correction, content))
    _finish_terminal_history_group(group, len(history.corrections))


def _show_numeric_resolution_correction_history(
    group: QGroupBox,
    history: NumericResolutionHistory,
    unit: str,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Resolution",
            history.original.resolved_at,
            (
                ("Actual value", f"{history.original.actual_value} {unit}"),
                ("Resolution notes", history.original.resolution_notes),
                ("Postmortem", history.original.postmortem),
            ),
            "numericResolutionOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(
            _numeric_resolution_correction_frame(correction, unit, content)
        )
    _finish_terminal_history_group(group, len(history.corrections))


def _show_invalidation_correction_history(
    group: QGroupBox,
    history: InvalidationHistory,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Invalidation",
            history.original.invalidated_at,
            (("Reason", history.original.reason),),
            "invalidationOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(_invalidation_correction_frame(correction, content))
    _finish_terminal_history_group(group, len(history.corrections))


def _finish_terminal_history_group(group: QGroupBox, correction_count: int) -> None:
    suffix = "correction" if correction_count == 1 else "corrections"
    base_title = (
        "Invalidation correction history"
        if "Invalidation" in group.objectName() or "invalidation" in group.objectName()
        else "Resolution correction history"
    )
    group.setTitle(f"{base_title} ({correction_count} {suffix})")
    group.setChecked(False)
    content, _layout = _history_content(group)
    content.setHidden(True)
    group.setHidden(correction_count == 0)


def _terminal_history_frame(
    heading_text: str,
    timestamp: datetime,
    values: tuple[tuple[str, object | None], ...],
    object_name: str,
    parent: QWidget,
) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName(object_name)
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    heading = QLabel(
        f"{heading_text} · {_format_local_timestamp(timestamp)}",
        frame,
    )
    heading.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(heading)
    for label, value in values:
        item = QLabel(f"{label}: {_terminal_history_value(value)}", frame)
        item.setTextFormat(Qt.TextFormat.PlainText)
        item.setWordWrap(True)
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(item)
    return frame


def _binary_resolution_correction_frame(
    correction: ResolutionCorrection,
    parent: QWidget,
) -> QFrame:
    values = {
        "outcome": (
            correction.old_outcome.value.capitalize(),
            correction.new_outcome.value.capitalize(),
        ),
        "resolution_notes": (
            correction.old_resolution_notes,
            correction.new_resolution_notes,
        ),
        "postmortem": (correction.old_postmortem, correction.new_postmortem),
    }
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        correction.changed_fields,
        values,
        correction.correction_reason,
        "resolutionCorrection",
        parent,
    )


def _numeric_resolution_correction_frame(
    correction: NumericResolutionCorrection,
    unit: str,
    parent: QWidget,
) -> QFrame:
    values = {
        "actual_value": (
            f"{correction.old_actual_value} {unit}",
            f"{correction.new_actual_value} {unit}",
        ),
        "resolution_notes": (
            correction.old_resolution_notes,
            correction.new_resolution_notes,
        ),
        "postmortem": (correction.old_postmortem, correction.new_postmortem),
    }
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        correction.changed_fields,
        values,
        correction.correction_reason,
        "numericResolutionCorrection",
        parent,
    )


def _invalidation_correction_frame(
    correction: InvalidationReasonCorrection,
    parent: QWidget,
) -> QFrame:
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        ("reason",),
        {"reason": (correction.old_reason, correction.new_reason)},
        None,
        "invalidationReasonCorrection",
        parent,
    )


def _terminal_correction_frame(
    correction_id: int,
    sequence: int,
    corrected_at: datetime,
    changed_fields: tuple[str, ...],
    values: dict[str, tuple[object | None, object | None]],
    correction_reason: str | None,
    object_name_prefix: str,
    parent: QWidget,
) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName(f"{object_name_prefix}{correction_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    heading = QLabel(
        f"Correction {sequence} · {_format_local_timestamp(corrected_at)}",
        frame,
    )
    heading.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(heading)
    for field_name in changed_fields:
        old_value, new_value = values[field_name]
        change = QLabel(
            f"{_terminal_field_label(field_name)}: "
            f"{_terminal_history_value(old_value)} "
            f"\N{RIGHTWARDS ARROW} {_terminal_history_value(new_value)}",
            frame,
        )
        change.setObjectName(
            f"{object_name_prefix}{correction_id}{_object_name_part(field_name)}"
        )
        change.setTextFormat(Qt.TextFormat.PlainText)
        change.setWordWrap(True)
        change.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(change)
    if correction_reason is not None:
        reason = QLabel(f"Explanation: {correction_reason}", frame)
        reason.setObjectName(f"{object_name_prefix}{correction_id}Reason")
        reason.setTextFormat(Qt.TextFormat.PlainText)
        reason.setWordWrap(True)
        reason.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(reason)
    return frame


def _dialog_error_label(object_name: str, parent: QWidget) -> QLabel:
    error = QLabel("", parent)
    error.setObjectName(object_name)
    error.setTextFormat(Qt.TextFormat.PlainText)
    error.setWordWrap(True)
    error.setHidden(True)
    return error


def _save_cancel_buttons(
    save_object_name: str,
    save_text: str,
    parent: QWidget,
) -> QDialogButtonBox:
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        parent,
    )
    save = buttons.button(QDialogButtonBox.StandardButton.Save)
    save.setObjectName(save_object_name)
    save.setText(save_text)
    save.setDefault(True)
    apply_lucide_icon(save, LucideIcon.SAVE)
    return buttons


def _confirm_terminal_correction(
    parent: QWidget,
    *,
    score_affecting: bool,
) -> bool:
    if score_affecting:
        title = "Confirm score-affecting correction"
        message = (
            "This correction changes the recorded outcome and recomputes scoring "
            "and calibration from that effective value. The original outcome and "
            "scoring ForecastRevision remain in history. Save this correction?"
        )
    else:
        title = "Confirm terminal correction"
        message = (
            "This appends a correction while preserving the original terminal "
            "record and every earlier version. Save this correction?"
        )
    answer = QMessageBox.warning(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return answer == QMessageBox.StandardButton.Yes


def _normalized_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _terminal_history_value(value: object | None) -> str:
    return "Not set" if value is None or value == "" else str(value)


def _terminal_field_label(field_name: str) -> str:
    return {
        "outcome": "Outcome",
        "actual_value": "Actual value",
        "resolution_notes": "Resolution notes",
        "postmortem": "Postmortem",
        "reason": "Reason",
    }[field_name]


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


def _forecast_review_widget(
    review: ForecastReviewTimelineSnapshot,
    parent: QWidget,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"forecastReview{review.review_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    timestamp = QLabel(_format_local_timestamp(review.created_at), frame)
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    heading = QLabel(
        f"REVIEW  STILL AT {review.forecast_probability_percent}%",
        frame,
    )
    heading.setObjectName(f"forecastReviewHeading{review.review_id}")
    heading.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(timestamp)
    layout.addWidget(heading)
    if review.note:
        note = QLabel(review.note, frame)
        note.setObjectName(f"forecastReviewNote{review.review_id}")
        note.setTextFormat(Qt.TextFormat.PlainText)
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(note)
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


def _numeric_forecast_text(
    revision: NumericRevisionSnapshot,
    unit: str,
) -> str:
    """Format one Numeric ForecastRevision for plain-language UI context."""

    return (
        f"{revision.confidence_percent}% interval: {revision.lower_bound} to "
        f"{revision.upper_bound} {unit}; Median: {revision.median_estimate} {unit}"
    )


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
