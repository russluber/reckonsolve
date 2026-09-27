"""One committed forecast and documentary times, independent of UI and SQLite."""

from dataclasses import dataclass
from datetime import date, datetime

from .forecast_contracts import ForecastCohort, ForecastContract
from .predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
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
    """Internal foundation request; no public creation operation exists in M56."""

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
