"""Separate One-Shot summaries derived from one effective forecast per Prediction."""

from dataclasses import dataclass
from fractions import Fraction

from reckonsolve.domain.analytics import OneShotAnalyticsSource
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)

from .one_shot import one_shot_score
from .quantile_aggregate import (
    Proportion,
    QuantileCalibrationGroup,
    quantile_calibration_group,
)
from .quantiles import WISScore
from .scoring import CalibrationBin, calibration_bins


@dataclass(frozen=True, slots=True)
class OneShotBinaryObservation:
    prediction_id: int
    probability_percent: int
    outcome: BinaryOutcome
    brier: Fraction


@dataclass(frozen=True, slots=True)
class OneShotNumericObservation:
    prediction_id: int
    definition: QuantileDefinition
    quantiles: FiveQuantiles
    actual: FixedPrecisionValue
    wis: WISScore


@dataclass(frozen=True, slots=True)
class OneShotBinaryAnalytics:
    observations: tuple[OneShotBinaryObservation, ...]
    mean_brier: Fraction | None
    calibration_bins: tuple[CalibrationBin, ...]
    observed_yes: tuple[Proportion, ...]

    @property
    def resolved_count(self) -> int:
        return len(self.observations)


@dataclass(frozen=True, slots=True)
class OneShotNumericAnalytics:
    observations: tuple[OneShotNumericObservation, ...]
    continuous: QuantileCalibrationGroup
    whole_number: QuantileCalibrationGroup

    @property
    def resolved_count(self) -> int:
        return len(self.observations)


@dataclass(frozen=True, slots=True)
class OneShotAnalyticsSnapshot:
    binary: OneShotBinaryAnalytics
    numeric: OneShotNumericAnalytics
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]
    selected_type: PredictionType | None = None
    selected_tag: str | None = None
    selected_unit: str | None = None


def summarize_one_shot_analytics(
    source: OneShotAnalyticsSource,
    *,
    prediction_type: PredictionType | None = None,
    tag: str | None = None,
    unit: str | None = None,
) -> OneShotAnalyticsSnapshot:
    """Score corrected facts once; documentary times never select observations."""
    ids = tuple(item.record.prediction_id for item in source.records)
    if len(set(ids)) != len(ids):
        raise ValueError("Each One-Shot Prediction must contribute at most once.")
    if any(not item.record.contract.is_one_shot for item in source.records):
        raise ValueError("One-Shot analytics requires One-Shot contracts.")
    if prediction_type is not None and not isinstance(prediction_type, PredictionType):
        raise ValueError("The analytics forecast-type filter is invalid.")
    unit = None if unit is None else unit.strip() or None
    if unit is not None and prediction_type is not PredictionType.NUMERIC:
        raise ValueError("Choose Numeric analytics before filtering by unit.")
    tag_key = None if tag is None else tag.strip().casefold() or None
    eligible = tuple(
        item
        for item in source.records
        if item.record.status is PredictionStatus.RESOLVED
        and item.record.effective.answer is not None
    )
    typed = tuple(
        item
        for item in eligible
        if prediction_type is None
        or item.record.contract.prediction_type is prediction_type
    )
    tags: dict[str, str] = {}
    for item in typed:
        for label in item.tags:
            tags.setdefault(label.casefold(), label)
    binary: list[OneShotBinaryObservation] = []
    numeric: list[OneShotNumericObservation] = []
    for item in typed:
        record = item.record
        if tag_key is not None and tag_key not in {
            label.casefold() for label in item.tags
        }:
            continue
        if unit is not None and (
            record.definition is None or record.definition.unit != unit
        ):
            continue
        values = record.effective
        score = one_shot_score(
            record.contract, record.status, values, record.definition
        )
        if record.definition is None:
            assert isinstance(score, Fraction)
            binary.append(
                OneShotBinaryObservation(
                    record.prediction_id,
                    values.probability_percent,
                    values.answer,
                    score,
                )
            )
        else:
            assert isinstance(score, WISScore)
            numeric.append(
                OneShotNumericObservation(
                    record.prediction_id,
                    record.definition,
                    values.quantiles,
                    values.answer,
                    score,
                )
            )
    bins = calibration_bins(
        tuple((item.probability_percent, item.outcome) for item in binary)
    )
    proportions = tuple(
        Proportion(
            sum(
                item.outcome is BinaryOutcome.YES
                for item in binary
                if band.lower_percent <= item.probability_percent <= band.upper_percent
            ),
            band.count,
        )
        for band in bins
    )

    def group(constraint: NumericValueConstraint) -> QuantileCalibrationGroup:
        return quantile_calibration_group(
            tuple(
                (item.actual, item.quantiles)
                for item in numeric
                if item.definition.value_constraint is constraint
            ),
            constraint,
        )

    return OneShotAnalyticsSnapshot(
        OneShotBinaryAnalytics(
            tuple(binary),
            sum((item.brier for item in binary), Fraction()) / len(binary)
            if binary
            else None,
            bins,
            proportions,
        ),
        OneShotNumericAnalytics(
            tuple(numeric),
            group(NumericValueConstraint.CONTINUOUS),
            group(NumericValueConstraint.WHOLE_NUMBER),
        ),
        tuple(tags[key] for key in sorted(tags)),
        tuple(
            sorted(
                {
                    item.record.definition.unit
                    for item in eligible
                    if item.record.definition is not None
                }
            )
        ),
        prediction_type,
        tag,
        unit,
    )
