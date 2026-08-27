"""Derived Dashboard attention values and rules."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)

DEFAULT_STALE_THRESHOLD_DAYS = 14
MIN_STALE_THRESHOLD_DAYS = 1
MAX_STALE_THRESHOLD_DAYS = 9999


class AttentionValidationError(ValueError):
    """Raised when an attention setting is not a supported value."""


@dataclass(frozen=True, slots=True)
class DashboardPrediction:
    """One nonterminal prediction and its derived Dashboard classifications."""

    prediction_id: int
    question: str
    probability_percent: int | None
    status: PredictionStatus
    latest_revision_at: datetime
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    needs_attention: bool = False
    ready_to_resolve: bool = False
    prediction_type: PredictionType = PredictionType.BINARY
    numeric_lower_bound: FixedPrecisionValue | None = None
    numeric_median_estimate: FixedPrecisionValue | None = None
    numeric_upper_bound: FixedPrecisionValue | None = None
    numeric_confidence_percent: int | None = None
    numeric_unit: str | None = None
    latest_review_at: datetime | None = None

    @property
    def attention_reference_at(self) -> datetime:
        """Latest instant at which the current forecast was set or retained."""

        if self.latest_review_at is None:
            return self.latest_revision_at
        return max(self.latest_revision_at, self.latest_review_at)


@dataclass(frozen=True, slots=True)
class NeedsPostmortemPrediction:
    """One Resolved Prediction awaiting an optional reflection decision."""

    prediction_id: int
    question: str
    prediction_type: PredictionType
    resolved_at: datetime
    current_correction_id: int | None
    binary_outcome: BinaryOutcome | None = None
    numeric_actual_value: FixedPrecisionValue | None = None
    numeric_unit: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Deterministic Dashboard action views, including postmortem work."""

    stale_threshold_days: int
    open_predictions: tuple[DashboardPrediction, ...]
    needs_attention_predictions: tuple[DashboardPrediction, ...]
    ready_to_resolve_predictions: tuple[DashboardPrediction, ...]
    locked_predictions: tuple[DashboardPrediction, ...]
    needs_postmortem_predictions: tuple[NeedsPostmortemPrediction, ...] = ()


def validate_stale_threshold_days(value: object) -> int:
    """Return a supported whole-day threshold or raise a domain error."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise AttentionValidationError(
            "Needs Attention threshold must be a whole number of days."
        )
    if not MIN_STALE_THRESHOLD_DAYS <= value <= MAX_STALE_THRESHOLD_DAYS:
        raise AttentionValidationError(
            "Needs Attention threshold must be between 1 and 9999 days."
        )
    return value


def needs_attention(
    status: PredictionStatus,
    latest_revision_at: datetime,
    now: datetime,
    stale_threshold_days: int,
) -> bool:
    """Whether a nonterminal forecast has reached its elapsed stale threshold."""

    threshold = validate_stale_threshold_days(stale_threshold_days)
    if status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
        return False
    if latest_revision_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("Attention instants must include timezone information.")
    return now - latest_revision_at >= timedelta(days=threshold)


def ready_to_resolve(
    status: PredictionStatus,
    expected_resolution: date | None,
    current_date: date,
) -> bool:
    """Whether an inclusive Expected Resolution date has passed locally."""

    return (
        status in (PredictionStatus.OPEN, PredictionStatus.LOCKED)
        and expected_resolution is not None
        and current_date > expected_resolution
    )
