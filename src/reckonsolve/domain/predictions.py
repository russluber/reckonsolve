"""Binary and numeric prediction values and validation rules."""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class PredictionValidationError(ValueError):
    """Raised when prediction input violates a domain rule."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class PredictionStatus(StrEnum):
    """Lifecycle state; Locked is derived and is never stored in SQLite."""

    OPEN = "open"
    LOCKED = "locked"
    RESOLVED = "resolved"
    INVALID = "invalid"


class PredictionType(StrEnum):
    """The forecast model fixed for a Prediction's lifetime."""

    BINARY = "binary"
    NUMERIC = "numeric"


class BinaryOutcome(StrEnum):
    """The factual Yes/No result of a resolved binary prediction."""

    YES = "yes"
    NO = "no"


MIN_NUMERIC_DECIMAL_PLACES = 0
MAX_NUMERIC_DECIMAL_PLACES = 6
MAX_NUMERIC_SCALED_VALUE = 999_999_999_999_999_999
_PLAIN_DECIMAL_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


@dataclass(frozen=True, slots=True)
class FixedPrecisionValue:
    """One exact base-ten value represented as a signed scaled integer."""

    scaled_value: int
    decimal_places: int

    def __post_init__(self) -> None:
        _validate_decimal_places(self.decimal_places)
        if isinstance(self.scaled_value, bool) or not isinstance(
            self.scaled_value, int
        ):
            raise PredictionValidationError(
                "Numeric values must use an exact scaled integer.",
                field="scaled_value",
            )
        if abs(self.scaled_value) > MAX_NUMERIC_SCALED_VALUE:
            raise PredictionValidationError(
                "Numeric value is outside the supported range.",
                field="scaled_value",
            )

    @classmethod
    def from_value(
        cls,
        value: Decimal | int | str,
        decimal_places: int,
        *,
        field: str = "value",
    ) -> "FixedPrecisionValue":
        """Normalize a plain decimal input without passing through float."""

        _validate_decimal_places(decimal_places)
        if isinstance(value, (bool, float)):
            raise PredictionValidationError(
                "Numeric values must be exact decimal numbers, not floats.",
                field=field,
            )
        if isinstance(value, int):
            decimal_value = Decimal(value)
        elif isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, str):
            normalized = value.strip()
            if not normalized or _PLAIN_DECIMAL_PATTERN.fullmatch(normalized) is None:
                raise PredictionValidationError(
                    "Numeric value must be a plain decimal number.",
                    field=field,
                )
            decimal_value = Decimal(normalized)
        else:
            raise PredictionValidationError(
                "Numeric value must be a plain decimal number.",
                field=field,
            )

        if not decimal_value.is_finite():
            raise PredictionValidationError(
                "Numeric value must be finite.",
                field=field,
            )
        quantum = Decimal(1).scaleb(-decimal_places)
        try:
            quantized = decimal_value.quantize(quantum)
        except InvalidOperation as error:
            raise PredictionValidationError(
                "Numeric value is outside the supported range.",
                field=field,
            ) from error
        if quantized != decimal_value:
            raise PredictionValidationError(
                f"Numeric value must use at most {decimal_places} decimal places.",
                field=field,
            )
        scaled_value = int(quantized.scaleb(decimal_places))
        if abs(scaled_value) > MAX_NUMERIC_SCALED_VALUE:
            raise PredictionValidationError(
                "Numeric value is outside the supported range.",
                field=field,
            )
        return cls(scaled_value=scaled_value, decimal_places=decimal_places)

    @property
    def decimal_value(self) -> Decimal:
        """Return the exact Decimal represented by this value."""

        return Decimal(self.scaled_value).scaleb(-self.decimal_places)

    def __str__(self) -> str:
        return format(self.decimal_value, f".{self.decimal_places}f")


@dataclass(frozen=True, slots=True)
class NewPrediction:
    """Validated initial prediction state and its sequence-one forecast."""

    question: str
    probability_percent: int
    rationale: str | None = None
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        _validate_probability(self.probability_percent)
        object.__setattr__(
            self, "rationale", _optional_text(self.rationale, "rationale")
        )
        object.__setattr__(
            self,
            "background",
            _optional_text(self.background, "background"),
        )
        object.__setattr__(
            self,
            "resolution_criteria",
            _optional_text(self.resolution_criteria, "resolution_criteria"),
        )
        _validate_date_only(self.forecast_deadline, "forecast_deadline")
        _validate_date_only(self.expected_resolution, "expected_resolution")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class NewForecastRevision:
    """Validated input for an append-only forecast change."""

    probability_percent: int
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_probability(self.probability_percent)
        object.__setattr__(
            self, "rationale", _optional_text(self.rationale, "rationale")
        )


@dataclass(frozen=True, slots=True)
class NewNumericForecastRevision:
    """Validated input for one central numeric prediction interval."""

    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_numeric_interval(
            self.lower_bound,
            self.median_estimate,
            self.upper_bound,
            self.confidence_percent,
        )
        object.__setattr__(
            self, "rationale", _optional_text(self.rationale, "rationale")
        )


@dataclass(frozen=True, slots=True)
class NewNumericPrediction:
    """Validated enduring numeric definition and sequence-one revision."""

    question: str
    unit: str
    decimal_places: int
    initial_revision: NewNumericForecastRevision
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        object.__setattr__(self, "unit", _required_unit(self.unit))
        _validate_decimal_places(self.decimal_places)
        if not isinstance(self.initial_revision, NewNumericForecastRevision):
            raise PredictionValidationError(
                "An initial numeric forecast is required.",
                field="initial_revision",
            )
        if self.initial_revision.lower_bound.decimal_places != self.decimal_places:
            raise PredictionValidationError(
                "Numeric forecast values must match the Prediction precision.",
                field="decimal_places",
            )
        object.__setattr__(
            self,
            "background",
            _optional_text(self.background, "background"),
        )
        object.__setattr__(
            self,
            "resolution_criteria",
            _optional_text(self.resolution_criteria, "resolution_criteria"),
        )
        _validate_date_only(self.forecast_deadline, "forecast_deadline")
        _validate_date_only(self.expected_resolution, "expected_resolution")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class NewJournalEntry:
    """Validated reasoning that leaves the current forecast unchanged."""

    body: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", _journal_body(self.body))


@dataclass(frozen=True, slots=True)
class NewJournalCorrection:
    """Validated replacement text preserved as an audited correction."""

    body: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", _journal_body(self.body))


@dataclass(frozen=True, slots=True)
class NewForecastReview:
    """Validated deliberate reconsideration that retains the current forecast."""

    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "note", _optional_text(self.note, "note"))


@dataclass(frozen=True, slots=True)
class NewResolution:
    """Validated terminal outcome with optional factual and reflective notes."""

    outcome: BinaryOutcome
    resolution_notes: str | None = None
    postmortem: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, BinaryOutcome):
            raise PredictionValidationError(
                "Outcome must be Yes or No.",
                field="outcome",
            )
        object.__setattr__(
            self,
            "resolution_notes",
            _optional_text(self.resolution_notes, "resolution_notes"),
        )
        object.__setattr__(
            self,
            "postmortem",
            _optional_text(self.postmortem, "postmortem"),
        )


@dataclass(frozen=True, slots=True)
class NewNumericResolution:
    """Validated realized numeric outcome and optional notes."""

    actual_value: FixedPrecisionValue
    resolution_notes: str | None = None
    postmortem: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actual_value, FixedPrecisionValue):
            raise PredictionValidationError(
                "A numeric actual value is required.",
                field="actual_value",
            )
        object.__setattr__(
            self,
            "resolution_notes",
            _optional_text(self.resolution_notes, "resolution_notes"),
        )
        object.__setattr__(
            self,
            "postmortem",
            _optional_text(self.postmortem, "postmortem"),
        )


@dataclass(frozen=True, slots=True)
class NewInvalidation:
    """Validated reason for preserving a prediction outside scoring."""

    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _optional_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class NewResolutionCorrection:
    """Proposed effective values for an audited Binary Resolution correction."""

    outcome: BinaryOutcome
    resolution_notes: str | None = None
    postmortem: str | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, BinaryOutcome):
            raise PredictionValidationError(
                "Outcome must be Yes or No.",
                field="outcome",
            )
        object.__setattr__(
            self,
            "resolution_notes",
            _optional_text(self.resolution_notes, "resolution_notes"),
        )
        object.__setattr__(
            self,
            "postmortem",
            _optional_text(self.postmortem, "postmortem"),
        )
        object.__setattr__(
            self,
            "correction_reason",
            _optional_text(self.correction_reason, "correction_reason"),
        )


@dataclass(frozen=True, slots=True)
class NewNumericResolutionCorrection:
    """Proposed effective values for an audited Numeric Resolution correction."""

    actual_value: FixedPrecisionValue
    resolution_notes: str | None = None
    postmortem: str | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actual_value, FixedPrecisionValue):
            raise PredictionValidationError(
                "A numeric actual value is required.",
                field="actual_value",
            )
        object.__setattr__(
            self,
            "resolution_notes",
            _optional_text(self.resolution_notes, "resolution_notes"),
        )
        object.__setattr__(
            self,
            "postmortem",
            _optional_text(self.postmortem, "postmortem"),
        )
        object.__setattr__(
            self,
            "correction_reason",
            _optional_text(self.correction_reason, "correction_reason"),
        )


@dataclass(frozen=True, slots=True)
class NewInvalidationReasonCorrection:
    """Proposed effective reason for an audited Invalidation correction."""

    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _optional_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class Prediction:
    """The stable identity and lifecycle facts of a binary prediction."""

    prediction_id: int
    question: str
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ForecastRevision:
    """One immutable statement of probability."""

    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class NumericForecastRevision:
    """One immutable central numeric prediction interval."""

    revision_id: int
    prediction_id: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_numeric_interval(
            self.lower_bound,
            self.median_estimate,
            self.upper_bound,
            self.confidence_percent,
        )


@dataclass(frozen=True, slots=True)
class NumericPrediction:
    """Current numeric state derived from its latest immutable revision."""

    prediction_id: int
    question: str
    unit: str
    decimal_places: int
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime
    current_revision: NumericForecastRevision
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()
    metadata_version: int = 1
    resolution: "NumericResolution | None" = None
    invalidation: "Invalidation | None" = None
    deletion_allowed: bool = False


@dataclass(frozen=True, slots=True)
class JournalCorrection:
    """One immutable correction to a Journal entry's displayed text."""

    correction_id: int
    body: str
    corrected_at: datetime


@dataclass(frozen=True, slots=True)
class ForecastTimelineEvent:
    """One immutable forecast revision prepared for unified history display."""

    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    probability_percent: int
    previous_probability_percent: int | None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class JournalTimelineEvent:
    """One Journal event with its forecast anchor and complete edit history."""

    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    current_correction_id: int | None = None
    corrections: tuple[JournalCorrection, ...] = ()


@dataclass(frozen=True, slots=True)
class ForecastReviewTimelineEvent:
    """One immutable Review anchored to an exact Binary revision."""

    review_id: int
    prediction_id: int
    created_at: datetime
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    note: str | None = None


type TimelineEvent = (
    ForecastTimelineEvent | JournalTimelineEvent | ForecastReviewTimelineEvent
)


@dataclass(frozen=True, slots=True)
class NumericForecastTimelineEvent:
    """One immutable Numeric ForecastRevision prepared for history display."""

    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    previous_lower_bound: FixedPrecisionValue | None
    previous_median_estimate: FixedPrecisionValue | None
    previous_upper_bound: FixedPrecisionValue | None
    previous_confidence_percent: int | None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class NumericJournalTimelineEvent:
    """One Numeric Journal event anchored to its exact interval revision."""

    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    numeric_forecast_revision_id: int
    forecast_revision_sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    current_correction_id: int | None = None
    corrections: tuple[JournalCorrection, ...] = ()


@dataclass(frozen=True, slots=True)
class NumericForecastReviewTimelineEvent:
    """One immutable Review anchored to an exact Numeric revision."""

    review_id: int
    prediction_id: int
    created_at: datetime
    numeric_forecast_revision_id: int
    forecast_revision_sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    note: str | None = None


type NumericTimelineEvent = (
    NumericForecastTimelineEvent
    | NumericJournalTimelineEvent
    | NumericForecastReviewTimelineEvent
)


@dataclass(frozen=True, slots=True)
class Resolution:
    """One immutable terminal outcome and its captured scoring forecast."""

    resolution_id: int
    prediction_id: int
    outcome: BinaryOutcome
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    scoring_probability_percent: int
    resolution_notes: str | None = None
    postmortem: str | None = None


@dataclass(frozen=True, slots=True)
class NumericResolution:
    """One immutable realized quantity and captured scoring interval."""

    resolution_id: int
    prediction_id: int
    actual_value: FixedPrecisionValue
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    resolution_notes: str | None = None
    postmortem: str | None = None


@dataclass(frozen=True, slots=True)
class Invalidation:
    """One immutable decision to preserve but exclude a prediction."""

    invalidation_id: int
    prediction_id: int
    invalidated_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ResolutionCorrection:
    """One immutable before/after Binary Resolution correction snapshot."""

    correction_id: int
    prediction_id: int
    resolution_id: int
    sequence: int
    corrected_at: datetime
    old_outcome: BinaryOutcome
    new_outcome: BinaryOutcome
    old_resolution_notes: str | None
    new_resolution_notes: str | None
    old_postmortem: str | None
    new_postmortem: str | None
    changed_fields: tuple[str, ...]
    correction_reason: str | None = None


@dataclass(frozen=True, slots=True)
class NumericResolutionCorrection:
    """One immutable before/after Numeric Resolution correction snapshot."""

    correction_id: int
    prediction_id: int
    resolution_id: int
    sequence: int
    corrected_at: datetime
    old_actual_value: FixedPrecisionValue
    new_actual_value: FixedPrecisionValue
    old_resolution_notes: str | None
    new_resolution_notes: str | None
    old_postmortem: str | None
    new_postmortem: str | None
    changed_fields: tuple[str, ...]
    correction_reason: str | None = None


@dataclass(frozen=True, slots=True)
class InvalidationReasonCorrection:
    """One immutable before/after Invalidation reason correction."""

    correction_id: int
    prediction_id: int
    invalidation_id: int
    sequence: int
    corrected_at: datetime
    old_reason: str | None
    new_reason: str | None


@dataclass(frozen=True, slots=True)
class PostmortemCompletion:
    """One immutable fact that an empty Postmortem was deliberately skipped."""

    completion_id: int
    prediction_id: int
    completed_at: datetime


class TerminalHistoryIntegrityError(RuntimeError):
    """Persisted terminal correction history is not a contiguous snapshot chain."""


@dataclass(frozen=True, slots=True)
class BinaryResolutionHistory:
    """Original Binary Resolution plus its complete correction chain."""

    original: Resolution
    corrections: tuple[ResolutionCorrection, ...] = ()
    postmortem_completion: PostmortemCompletion | None = None

    @property
    def effective(self) -> Resolution:
        return derive_effective_resolution(self.original, self.corrections)

    @property
    def current_correction_id(self) -> int | None:
        return None if not self.corrections else self.corrections[-1].correction_id


@dataclass(frozen=True, slots=True)
class NumericResolutionHistory:
    """Original Numeric Resolution plus its complete correction chain."""

    original: NumericResolution
    corrections: tuple[NumericResolutionCorrection, ...] = ()
    postmortem_completion: PostmortemCompletion | None = None

    @property
    def effective(self) -> NumericResolution:
        return derive_effective_numeric_resolution(self.original, self.corrections)

    @property
    def current_correction_id(self) -> int | None:
        return None if not self.corrections else self.corrections[-1].correction_id


@dataclass(frozen=True, slots=True)
class InvalidationHistory:
    """Original Invalidation plus its complete reason-correction chain."""

    original: Invalidation
    corrections: tuple[InvalidationReasonCorrection, ...] = ()

    @property
    def effective(self) -> Invalidation:
        return derive_effective_invalidation(self.original, self.corrections)

    @property
    def current_correction_id(self) -> int | None:
        return None if not self.corrections else self.corrections[-1].correction_id


RESOLUTION_CORRECTION_FIELDS = (
    "outcome",
    "resolution_notes",
    "postmortem",
)
NUMERIC_RESOLUTION_CORRECTION_FIELDS = (
    "actual_value",
    "resolution_notes",
    "postmortem",
)


def changed_resolution_fields(
    current: Resolution,
    proposed: NewResolutionCorrection,
) -> tuple[str, ...]:
    """Return Binary terminal fields changed by a normalized proposal."""

    return tuple(
        field_name
        for field_name in RESOLUTION_CORRECTION_FIELDS
        if getattr(current, field_name) != getattr(proposed, field_name)
    )


def changed_numeric_resolution_fields(
    current: NumericResolution,
    proposed: NewNumericResolutionCorrection,
) -> tuple[str, ...]:
    """Return Numeric terminal fields changed by a normalized proposal."""

    return tuple(
        field_name
        for field_name in NUMERIC_RESOLUTION_CORRECTION_FIELDS
        if getattr(current, field_name) != getattr(proposed, field_name)
    )


def derive_effective_resolution(
    original: Resolution,
    corrections: tuple[ResolutionCorrection, ...],
) -> Resolution:
    """Replay a contiguous Binary correction chain without mutating its origin."""

    current = original
    for expected_sequence, correction in enumerate(corrections, start=1):
        if (
            correction.prediction_id != original.prediction_id
            or correction.resolution_id != original.resolution_id
            or correction.sequence != expected_sequence
            or correction.old_outcome is not current.outcome
            or correction.old_resolution_notes != current.resolution_notes
            or correction.old_postmortem != current.postmortem
        ):
            raise TerminalHistoryIntegrityError(
                "Binary Resolution correction history is inconsistent."
            )
        current = replace(
            current,
            outcome=correction.new_outcome,
            resolution_notes=correction.new_resolution_notes,
            postmortem=correction.new_postmortem,
        )
    return current


def derive_effective_numeric_resolution(
    original: NumericResolution,
    corrections: tuple[NumericResolutionCorrection, ...],
) -> NumericResolution:
    """Replay a contiguous Numeric correction chain with exact values."""

    current = original
    for expected_sequence, correction in enumerate(corrections, start=1):
        if (
            correction.prediction_id != original.prediction_id
            or correction.resolution_id != original.resolution_id
            or correction.sequence != expected_sequence
            or correction.old_actual_value != current.actual_value
            or correction.old_resolution_notes != current.resolution_notes
            or correction.old_postmortem != current.postmortem
        ):
            raise TerminalHistoryIntegrityError(
                "Numeric Resolution correction history is inconsistent."
            )
        current = replace(
            current,
            actual_value=correction.new_actual_value,
            resolution_notes=correction.new_resolution_notes,
            postmortem=correction.new_postmortem,
        )
    return current


def derive_effective_invalidation(
    original: Invalidation,
    corrections: tuple[InvalidationReasonCorrection, ...],
) -> Invalidation:
    """Replay a contiguous Invalidation reason-correction chain."""

    current = original
    for expected_sequence, correction in enumerate(corrections, start=1):
        if (
            correction.prediction_id != original.prediction_id
            or correction.invalidation_id != original.invalidation_id
            or correction.sequence != expected_sequence
            or correction.old_reason != current.reason
        ):
            raise TerminalHistoryIntegrityError(
                "Invalidation correction history is inconsistent."
            )
        current = replace(current, reason=correction.new_reason)
    return current


@dataclass(frozen=True, slots=True)
class PredictionDetail:
    """Current display data derived from a prediction and its latest revision."""

    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus
    created_at: datetime
    current_revision_id: int
    current_revision_sequence: int
    current_rationale: str | None = None
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()
    updated_at: datetime | None = None
    metadata_version: int = 1
    resolution: Resolution | None = None
    invalidation: Invalidation | None = None
    deletion_allowed: bool = False


@dataclass(frozen=True, slots=True)
class PredictionMetadataUpdate:
    """Validated replacement values for editable prediction metadata."""

    question: str
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        object.__setattr__(
            self,
            "background",
            _optional_text(self.background, "background"),
        )
        object.__setattr__(
            self,
            "resolution_criteria",
            _optional_text(self.resolution_criteria, "resolution_criteria"),
        )
        _validate_date_only(self.forecast_deadline, "forecast_deadline")
        _validate_date_only(self.expected_resolution, "expected_resolution")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class DefinitionChange:
    """One immutable before/after snapshot of meaning-bearing metadata."""

    change_id: int
    prediction_id: int
    changed_at: datetime
    changed_fields: tuple[str, ...]
    old_question: str
    new_question: str
    old_resolution_criteria: str | None
    new_resolution_criteria: str | None
    old_forecast_deadline: date | None
    new_forecast_deadline: date | None


DEFINITION_FIELDS = (
    "question",
    "resolution_criteria",
    "forecast_deadline",
)

MIN_METADATA_DATE = date(1752, 9, 14)
MAX_METADATA_DATE = date(9999, 12, 31)


def changed_definition_fields(
    current: PredictionDetail,
    update: PredictionMetadataUpdate,
) -> tuple[str, ...]:
    """Return meaning-bearing fields whose normalized values would change."""

    return tuple(
        field_name
        for field_name in DEFINITION_FIELDS
        if getattr(current, field_name) != getattr(update, field_name)
    )


def metadata_would_change(
    current: PredictionDetail,
    update: PredictionMetadataUpdate,
) -> bool:
    """Whether an update differs semantically from the persisted metadata."""

    scalar_fields = (
        "question",
        "background",
        "resolution_criteria",
        "forecast_deadline",
        "expected_resolution",
    )
    if any(
        getattr(current, field_name) != getattr(update, field_name)
        for field_name in scalar_fields
    ):
        return True
    return {tag.casefold() for tag in current.tags} != {
        tag.casefold() for tag in update.tags
    }


def display_status(
    persisted_status: PredictionStatus,
    forecast_deadline: date | None,
    current_date: date,
) -> PredictionStatus:
    """Derive Locked after an inclusive date-only forecast deadline."""

    if (
        persisted_status is PredictionStatus.OPEN
        and forecast_deadline is not None
        and current_date > forecast_deadline
    ):
        return PredictionStatus.LOCKED
    return persisted_status


def _validate_decimal_places(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PredictionValidationError(
            "Decimal precision must be a whole number from 0 to 6.",
            field="decimal_places",
        )
    if not MIN_NUMERIC_DECIMAL_PLACES <= value <= MAX_NUMERIC_DECIMAL_PLACES:
        raise PredictionValidationError(
            "Decimal precision must be between 0 and 6.",
            field="decimal_places",
        )


def _validate_numeric_interval(
    lower_bound: object,
    median_estimate: object,
    upper_bound: object,
    confidence_percent: object,
) -> None:
    values = (lower_bound, median_estimate, upper_bound)
    if any(not isinstance(value, FixedPrecisionValue) for value in values):
        raise PredictionValidationError(
            "Lower bound, median, and upper bound must be exact numeric values.",
            field="interval",
        )
    lower = lower_bound
    median = median_estimate
    upper = upper_bound
    assert isinstance(lower, FixedPrecisionValue)
    assert isinstance(median, FixedPrecisionValue)
    assert isinstance(upper, FixedPrecisionValue)
    decimal_places = lower.decimal_places
    if any(value.decimal_places != decimal_places for value in (median, upper)):
        raise PredictionValidationError(
            "Lower bound, median, and upper bound must use one precision.",
            field="interval",
        )
    if not lower.scaled_value <= median.scaled_value <= upper.scaled_value:
        raise PredictionValidationError(
            "Numeric forecasts require lower bound <= median <= upper bound.",
            field="interval",
        )
    if isinstance(confidence_percent, bool) or not isinstance(confidence_percent, int):
        raise PredictionValidationError(
            "Confidence must be a whole percentage from 1 to 99.",
            field="confidence_percent",
        )
    if not 1 <= confidence_percent <= 99:
        raise PredictionValidationError(
            "Confidence must be between 1 and 99.",
            field="confidence_percent",
        )


def _required_unit(value: object) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise PredictionValidationError(
            "Unit is required.",
            field="unit",
        )
    if "\x00" in normalized:
        raise PredictionValidationError(
            "Unit cannot contain the NUL control character.",
            field="unit",
        )
    return normalized


def _validate_probability(probability: object) -> None:
    if isinstance(probability, bool) or not isinstance(probability, int):
        raise PredictionValidationError(
            "Probability must be a whole percentage from 0 to 100.",
            field="probability_percent",
        )
    if not 0 <= probability <= 100:
        raise PredictionValidationError(
            "Probability must be between 0 and 100.",
            field="probability_percent",
        )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise PredictionValidationError("Question is required.", field=field)
    if "\x00" in normalized:
        raise PredictionValidationError(
            "Question cannot contain the NUL control character.",
            field=field,
        )
    return normalized


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PredictionValidationError(
            "Optional text must be text or left blank.",
            field=field,
        )
    normalized = value.strip()
    if "\x00" in normalized:
        raise PredictionValidationError(
            "Text cannot contain the NUL control character.",
            field=field,
        )
    return normalized or None


def _journal_body(value: object) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise PredictionValidationError(
            "Journal entry text is required.",
            field="body",
        )
    if "\x00" in normalized:
        raise PredictionValidationError(
            "Journal entry text cannot contain the NUL control character.",
            field="body",
        )
    return normalized


def _validate_date_only(value: object, field: str) -> None:
    if value is not None and (
        not isinstance(value, date) or isinstance(value, datetime)
    ):
        raise PredictionValidationError(
            "Date values must be calendar dates.",
            field=field,
        )
    if isinstance(value, date) and not MIN_METADATA_DATE <= value <= MAX_METADATA_DATE:
        raise PredictionValidationError(
            "Date values must be between 1752-09-14 and 9999-12-31.",
            field=field,
        )


def _normalize_tags(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        raise PredictionValidationError(
            "Tags must be supplied as separate labels.",
            field="tags",
        )
    try:
        candidates = tuple(values)  # type: ignore[arg-type]
    except TypeError as error:
        raise PredictionValidationError(
            "Tags must be supplied as separate labels.",
            field="tags",
        ) from error

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, str) and not candidate.strip():
            continue
        tag, normalized_name = normalize_tag_label(candidate)
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        normalized_tags.append(tag)
    return tuple(normalized_tags)


def normalize_tag_label(value: object) -> tuple[str, str]:
    """Apply the authoritative tag-label validation and identity rules."""

    if not isinstance(value, str):
        raise PredictionValidationError(
            "Every tag must be text.",
            field="tags",
        )
    tag = value.strip()
    if not tag:
        raise PredictionValidationError("A tag name is required.", field="tags")
    if "\x00" in tag:
        raise PredictionValidationError(
            "Tags cannot contain the NUL control character.",
            field="tags",
        )
    if any(delimiter in tag for delimiter in (",", "\r", "\n")):
        raise PredictionValidationError(
            "Tags cannot contain commas or line breaks.",
            field="tags",
        )
    return tag, tag.casefold()
