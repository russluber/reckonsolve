"""Prediction contracts responsibilities extracted from the desktop composition."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from reckonsolve.analytics import PredictionScorecard
from reckonsolve.domain.attention import DashboardSnapshot
from reckonsolve.domain.browser import PredictionBrowserSnapshot
from reckonsolve.domain.forecast_contracts import ForecastContract
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    DefinitionChange,
    InvalidationHistory,
    NumericResolutionHistory,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    NumericValueConstraint,
    QuantileRevision,
    QuantileTimelineEvent,
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
    resolution: ResolutionSnapshot | None
    invalidation: InvalidationSnapshot | None
    deletion_allowed: bool


class NumericPredictionSnapshot(Protocol):
    """Read-only Numeric Prediction data needed by the Detail screen."""

    prediction_id: int
    question: str
    unit: str
    decimal_places: int
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime
    current_revision: QuantileRevision
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    metadata_version: int
    resolution: NumericResolutionSnapshot | None
    invalidation: InvalidationSnapshot | None
    deletion_allowed: bool
    forecast_contract: ForecastContract
    value_constraint: NumericValueConstraint


class NumericResolutionSnapshot(Protocol):
    """Read-only exact Numeric Resolution shown on Prediction Detail."""

    resolution_id: int
    prediction_id: int
    actual_value: object
    resolved_at: datetime
    effective_resolution_at: datetime | None
    scoring_revision_id: int
    scoring_revision_sequence: int
    resolution_notes: str | None
    postmortem: str | None


class ResolutionSnapshot(Protocol):
    """Read-only immutable resolution data shown on Prediction Detail."""

    resolution_id: int
    prediction_id: int
    outcome: BinaryOutcome
    resolved_at: datetime
    effective_resolution_at: datetime | None
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
        forecast_deadline: datetime | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> PredictionSnapshot:
        """Create a prediction and its initial revision atomically."""

    def create_numeric_prediction(
        self,
        question: str,
        unit: str,
        decimal_places: int,
        quantiles: Mapping[int, Decimal | int | str],
        *,
        value_constraint: NumericValueConstraint,
        forecast_deadline: datetime,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> NumericPredictionSnapshot:
        """Create a Numeric Prediction and its first five-quantile revision atomically."""

    def revise_quantile_forecast(
        self,
        prediction_id: int,
        quantiles: Mapping[int, Decimal | int | str],
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        rationale: str | None = None,
    ) -> NumericPredictionSnapshot:
        """Append one complete five-quantile revision."""

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
        effective_resolution_at: datetime | None = None,
        use_recorded_time: bool = False,
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
        effective_resolution_at: datetime | None = None,
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
    ) -> tuple[QuantileRevision, ...]:
        """Return Numeric revisions in immutable sequence order."""

    def add_numeric_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> QuantileTimelineEvent:
        """Append a Numeric Journal entry tied to the reviewed interval."""

    def add_numeric_forecast_review(
        self,
        prediction_id: int,
        *,
        note: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> QuantileTimelineEvent:
        """Record deliberate retention of the current Numeric interval."""

    def correct_numeric_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> QuantileTimelineEvent:
        """Append one transparent Numeric Journal correction."""

    def list_numeric_timeline(
        self,
        prediction_id: int,
    ) -> tuple[QuantileTimelineEvent, ...]:
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
    ) -> PredictionSnapshot | NumericPredictionSnapshot:
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

    def get_prediction_scorecard(
        self,
        prediction_id: int,
    ) -> PredictionScorecard | None:
        """Return a derived scorecard only for one resolved Prediction."""

    def get_stale_threshold_days(self) -> int:
        """Return the persisted Needs Attention threshold."""

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist a validated Needs Attention threshold."""
