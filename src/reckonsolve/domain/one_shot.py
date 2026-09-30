"""One committed forecast and documentary times, independent of UI and SQLite."""

from dataclasses import dataclass
from datetime import date, datetime

from .forecast_contracts import ForecastCohort, ForecastContract
from .predictions import (
    BinaryOutcome,
    DefinitionChange,
    FixedPrecisionValue,
    InvalidationHistory,
    JournalCorrection,
    PostmortemCompletion,
    PredictionStatus,
    PredictionValidationError,
    _normalize_tags,
    _optional_text,
    _required_text,
    _validate_date_only,
    _validate_probability,
)
from .quantiles import FiveQuantiles, QuantileDefinition


@dataclass(frozen=True, slots=True)
class ReportedTime:
    """A reported wall-clock minute, never a canonical event or score cutoff."""

    wall_time: datetime
    approximate: bool = False
    offset_minutes: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.wall_time, datetime)
            or self.wall_time.tzinfo is not None
            or self.wall_time.second
            or self.wall_time.microsecond
            or self.wall_time.fold
        ):
            raise PredictionValidationError(
                "Report a date and wall-clock minute; an offset is separate context.",
                field="reported_time",
            )
        if type(self.approximate) is not bool or (
            self.offset_minutes is not None
            and (
                type(self.offset_minutes) is not int or abs(self.offset_minutes) >= 1440
            )
        ):
            raise PredictionValidationError(
                "Reported time context is invalid.", field="reported_time"
            )


@dataclass(frozen=True, slots=True)
class OneShotValues:
    """A complete original or effective snapshot. Corrections retain both."""

    probability_percent: int | None = None
    quantiles: FiveQuantiles | None = None
    answer: BinaryOutcome | FixedPrecisionValue | None = None
    forecast_reported: ReportedTime | None = None
    reveal_reported: ReportedTime | None = None
    resolution_notes: str | None = None
    postmortem: str | None = None

    def __post_init__(self) -> None:
        if (self.probability_percent is None) == (self.quantiles is None):
            raise PredictionValidationError(
                "Supply exactly one Binary or Numeric forecast.", field="forecast"
            )
        if self.probability_percent is not None:
            _validate_probability(self.probability_percent)
            if self.answer is not None and not isinstance(self.answer, BinaryOutcome):
                raise PredictionValidationError(
                    "Answer must be Yes or No.", field="answer"
                )
        elif not isinstance(self.quantiles, FiveQuantiles) or (
            self.answer is not None and not isinstance(self.answer, FixedPrecisionValue)
        ):
            raise PredictionValidationError(
                "Exact Numeric values are required.", field="answer"
            )
        for field in ("forecast_reported", "reveal_reported"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, ReportedTime):
                raise PredictionValidationError(
                    "A reported time is invalid.", field=field
                )
        for field in ("resolution_notes", "postmortem"):
            object.__setattr__(self, field, _optional_text(getattr(self, field), field))
        if self.answer is None and any(
            v is not None
            for v in (self.reveal_reported, self.resolution_notes, self.postmortem)
        ):
            raise PredictionValidationError(
                "Answer details require an answer.", field="answer"
            )

    def validate_contract(
        self, contract: ForecastContract, definition: QuantileDefinition | None
    ) -> None:
        if contract.cohort is ForecastCohort.ONE_SHOT_BINARY:
            if self.probability_percent is None or definition is not None:
                raise PredictionValidationError(
                    "A Binary One-Shot is required.", field="forecast"
                )
        elif contract.cohort is ForecastCohort.ONE_SHOT_NUMERIC:
            if not isinstance(definition, QuantileDefinition):
                raise PredictionValidationError(
                    "A Numeric definition is required.", field="definition"
                )
            definition.validate_quantiles(self.quantiles)
            if self.answer is not None:
                definition.validate_value(self.answer)
        else:
            raise PredictionValidationError(
                "A One-Shot contract is required.", field="forecast_model"
            )


@dataclass(frozen=True, slots=True)
class NewOneShotPrediction:
    """Complete atomic creation request shared by both interfaces."""

    question: str
    contract: ForecastContract
    values: OneShotValues
    definition: QuantileDefinition | None = None
    rationale: str | None = None
    background: str | None = None
    resolution_criteria: str | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.values.validate_contract(self.contract, self.definition)
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        for field in ("rationale", "background", "resolution_criteria"):
            object.__setattr__(self, field, _optional_text(getattr(self, field), field))
        _validate_date_only(self.expected_resolution, "expected_resolution")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class OneShotCorrection:
    correction_id: int
    sequence: int
    before: OneShotValues
    after: OneShotValues
    corrected_at: datetime
    note: str | None


@dataclass(frozen=True, slots=True)
class OneShotRecord:
    prediction_id: int
    contract: ForecastContract
    definition: QuantileDefinition | None
    status: PredictionStatus
    recorded_at: datetime
    answer_recorded_at: datetime | None
    metadata_version: int
    original: OneShotValues
    effective: OneShotValues
    corrections: tuple[OneShotCorrection, ...]

    @property
    def context(self) -> tuple[int, int | None, int | None]:
        return (
            self.metadata_version,
            self.corrections[-1].correction_id if self.corrections else None,
            1 if self.answer_recorded_at is not None else None,
        )


@dataclass(frozen=True, slots=True)
class OneShotDetail:
    """One consistent individual read; original forecast facts stay explicit."""

    record: OneShotRecord
    question: str
    rationale: str | None
    background: str | None
    resolution_criteria: str | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    updated_at: datetime
    deletion_allowed: bool
    definition_changes: tuple[DefinitionChange, ...] = ()
    journals: tuple["OneShotJournal", ...] = ()
    invalidation_history: InvalidationHistory | None = None
    postmortem_completion: PostmortemCompletion | None = None

    @property
    def prediction_id(self) -> int:
        return self.record.prediction_id

    @property
    def status(self) -> PredictionStatus:
        return self.record.status

    @property
    def forecast_contract(self) -> ForecastContract:
        return self.record.contract

    @property
    def created_at(self) -> datetime:
        return self.record.recorded_at

    @property
    def metadata_version(self) -> int:
        return self.record.metadata_version

    @property
    def forecast_deadline(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class OneShotJournal:
    entry_id: int
    created_at: datetime
    original_body: str
    corrections: tuple[JournalCorrection, ...]

    @property
    def body(self) -> str:
        return self.corrections[-1].body if self.corrections else self.original_body

    @property
    def current_correction_id(self) -> int | None:
        return self.corrections[-1].correction_id if self.corrections else None
