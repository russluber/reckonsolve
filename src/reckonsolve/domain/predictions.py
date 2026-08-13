"""Binary-prediction values and validation rules."""

from dataclasses import dataclass
from datetime import date, datetime
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


type TimelineEvent = ForecastTimelineEvent | JournalTimelineEvent


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
        if not isinstance(candidate, str):
            raise PredictionValidationError(
                "Every tag must be text.",
                field="tags",
            )
        tag = candidate.strip()
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
        normalized_name = tag.casefold()
        if not normalized_name or normalized_name in seen:
            continue
        seen.add(normalized_name)
        normalized_tags.append(tag)
    return tuple(normalized_tags)
