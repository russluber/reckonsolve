"""Exact five-quantile values; no persistence or presentation dependencies."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise

from .forecast_contracts import EffectiveResolutionTime, ForecastDeadline
from .predictions import (
    FixedPrecisionValue,
    JournalCorrection,
    PredictionValidationError,
    _normalize_tags,
    _optional_text,
    _required_text,
    _required_unit,
    _validate_date_only,
)

QUANTILE_LEVELS = (5, 25, 50, 75, 95)


class NumericValueConstraint(StrEnum):
    CONTINUOUS = "continuous"
    WHOLE_NUMBER = "whole-number"


@dataclass(frozen=True, slots=True)
class FiveQuantiles:
    q05: FixedPrecisionValue
    q25: FixedPrecisionValue
    q50: FixedPrecisionValue
    q75: FixedPrecisionValue
    q95: FixedPrecisionValue

    def __post_init__(self) -> None:
        values = self.values
        if not all(isinstance(v, FixedPrecisionValue) for v in values):
            raise PredictionValidationError(
                "All five exact quantiles are required.", field="quantiles"
            )
        if len({v.decimal_places for v in values}) != 1:
            raise PredictionValidationError(
                "Quantiles must share the fixed precision.", field="quantiles"
            )
        if any(a.scaled_value > b.scaled_value for a, b in pairwise(values)):
            raise PredictionValidationError(
                "Quantiles must satisfy q05 <= q25 <= q50 <= q75 <= q95; equal values are allowed.",
                field="quantiles",
            )

    @classmethod
    def from_values(
        cls, values: Mapping[int, Decimal | int | str], decimal_places: int
    ) -> "FiveQuantiles":
        if any(type(level) is not int for level in values) or set(values) != set(
            QUANTILE_LEVELS
        ):
            raise PredictionValidationError(
                "Supply exactly the 5th, 25th, 50th, 75th, and 95th percentiles.",
                field="quantiles",
            )
        return cls(
            *(
                FixedPrecisionValue.from_value(
                    values[level], decimal_places, field=f"q{level:02}"
                )
                for level in QUANTILE_LEVELS
            )
        )

    @property
    def values(self) -> tuple[FixedPrecisionValue, ...]:
        return (self.q05, self.q25, self.q50, self.q75, self.q95)


@dataclass(frozen=True, slots=True)
class QuantileDefinition:
    """Immutable measurement context, including integral versus continuous semantics."""

    unit: str
    decimal_places: int
    value_constraint: NumericValueConstraint

    def __post_init__(self) -> None:
        object.__setattr__(self, "unit", _required_unit(self.unit))
        FixedPrecisionValue(0, self.decimal_places)
        if not isinstance(self.value_constraint, NumericValueConstraint):
            raise PredictionValidationError(
                "Select a recognized Numeric value constraint.",
                field="value_constraint",
            )

    def validate_value(self, value: FixedPrecisionValue) -> None:
        if (
            not isinstance(value, FixedPrecisionValue)
            or value.decimal_places != self.decimal_places
        ):
            raise PredictionValidationError(
                "Value must use this Prediction's fixed precision.", field="value"
            )
        if (
            self.value_constraint is NumericValueConstraint.WHOLE_NUMBER
            and value.scaled_value % (10**self.decimal_places)
        ):
            raise PredictionValidationError(
                "Whole-number forecasts require integral values.", field="value"
            )

    def validate_quantiles(self, quantiles: FiveQuantiles) -> None:
        if not isinstance(quantiles, FiveQuantiles):
            raise PredictionValidationError(
                "A complete five-quantile forecast is required.", field="quantiles"
            )
        for value in quantiles.values:
            self.validate_value(value)

    def validate_replacement(
        self, current: FiveQuantiles, proposed: FiveQuantiles
    ) -> None:
        self.validate_quantiles(current)
        self.validate_quantiles(proposed)
        if current == proposed:
            raise PredictionValidationError(
                "The five quantiles are unchanged. Use Forecast Review to keep the current forecast.",
                field="quantiles",
            )


@dataclass(frozen=True, slots=True)
class QuantileRevision:
    revision_id: int
    prediction_id: int
    quantiles: FiveQuantiles
    sequence: int
    created_at: datetime
    rationale: str | None = None

    def __post_init__(self) -> None:
        if any(
            type(v) is not int or v < 1
            for v in (self.revision_id, self.prediction_id, self.sequence)
        ):
            raise PredictionValidationError(
                "Revision identifiers and sequence must be positive integers.",
                field="sequence",
            )
        if not isinstance(self.quantiles, FiveQuantiles):
            raise PredictionValidationError(
                "A complete five-quantile forecast is required.", field="quantiles"
            )
        object.__setattr__(
            self, "created_at", EffectiveResolutionTime(self.created_at).instant
        )
        object.__setattr__(
            self, "rationale", _optional_text(self.rationale, "rationale")
        )


@dataclass(frozen=True, slots=True)
class NewQuantilePrediction:
    question: str
    definition: QuantileDefinition
    quantiles: FiveQuantiles
    forecast_deadline: ForecastDeadline
    rationale: str | None = None
    background: str | None = None
    resolution_criteria: str | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        if not isinstance(self.definition, QuantileDefinition):
            raise PredictionValidationError(
                "A Numeric definition is required.", field="definition"
            )
        self.definition.validate_quantiles(self.quantiles)
        if not isinstance(self.forecast_deadline, ForecastDeadline):
            raise PredictionValidationError(
                "An exact Forecast Deadline is required.", field="forecast_deadline"
            )
        for field in ("rationale", "background", "resolution_criteria"):
            object.__setattr__(self, field, _optional_text(getattr(self, field), field))
        _validate_date_only(self.expected_resolution, "expected_resolution")
        object.__setattr__(self, "tags", _normalize_tags(self.tags))


@dataclass(frozen=True, slots=True)
class QuantileTimelineEvent:
    """A complete revision or a shared-history event anchored to that revision."""

    kind: str
    record_id: int
    revision: QuantileRevision
    created_at: datetime
    text: str | None = None
    original_text: str | None = None
    corrections: tuple[JournalCorrection, ...] = ()
