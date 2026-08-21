"""Pure containment calibration and unit-scoped Numeric scoring."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from reckonsolve.domain.analytics import (
    NumericAnalyticsSource,
    NumericScoringObservation,
)


@dataclass(frozen=True, slots=True)
class NumericScoredPrediction:
    """Derived metrics for one exactly-once Numeric scoring observation."""

    observation: NumericScoringObservation
    contained: bool
    median_absolute_error: Decimal
    interval_width: Decimal
    interval_score: Decimal


@dataclass(frozen=True, slots=True)
class ContainmentCalibrationBin:
    """One fixed confidence band, occupied or empty."""

    lower_percent: int
    upper_percent: int
    count: int
    mean_confidence_percent: Decimal | None
    observed_containment_percent: Decimal | None

    @property
    def label(self) -> str:
        """Return the same ten-band label used by Binary calibration."""

        return f"{self.lower_percent}-{self.upper_percent}%"


@dataclass(frozen=True, slots=True)
class NumericUnitSummary:
    """Raw Numeric averages that are meaningful only within one exact unit."""

    unit: str
    count: int
    mean_median_absolute_error: Decimal
    mean_interval_width: Decimal
    mean_interval_score: Decimal


@dataclass(frozen=True, slots=True)
class NumericAnalyticsSnapshot:
    """Numeric analytics for one coherent tag and optional exact-unit subset."""

    scored_predictions: tuple[NumericScoredPrediction, ...]
    calibration_bins: tuple[ContainmentCalibrationBin, ...]
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]
    selected_tag: str | None = None
    selected_unit: str | None = None
    unit_summary: NumericUnitSummary | None = None

    @property
    def scored_prediction_count(self) -> int:
        """Return the number of resolved Numeric Predictions counted once."""

        return len(self.scored_predictions)


def score_numeric_observation(
    observation: NumericScoringObservation,
) -> NumericScoredPrediction:
    """Calculate containment, median error, width, and proper interval score."""

    _validate_numeric_observation(observation)
    lower = observation.lower_bound.decimal_value
    median = observation.median_estimate.decimal_value
    upper = observation.upper_bound.decimal_value
    actual = observation.actual_value.decimal_value
    contained = lower <= actual <= upper
    width = upper - lower
    with localcontext() as context:
        context.prec = 50
        alpha = Decimal(100 - observation.confidence_percent) / Decimal(100)
        interval_score = width
        if actual < lower:
            interval_score += Decimal(2) / alpha * (lower - actual)
        elif actual > upper:
            interval_score += Decimal(2) / alpha * (actual - upper)
    return NumericScoredPrediction(
        observation=observation,
        contained=contained,
        median_absolute_error=abs(median - actual),
        interval_width=width,
        interval_score=interval_score,
    )


def summarize_numeric_analytics(
    source: NumericAnalyticsSource,
    *,
    tag: str | None = None,
    unit: str | None = None,
) -> NumericAnalyticsSnapshot:
    """Build Numeric views after applying one tag and optional exact unit."""

    _validate_numeric_observations(source.observations)
    tag_key = None if tag is None else tag.strip().casefold() or None
    observations = tuple(
        observation
        for observation in source.observations
        if (
            tag_key is None or tag_key in {item.casefold() for item in observation.tags}
        )
        and (unit is None or observation.unit == unit)
    )
    scored = tuple(score_numeric_observation(item) for item in observations)
    unit_summary = None
    if unit is not None and scored:
        count = len(scored)
        unit_summary = NumericUnitSummary(
            unit=unit,
            count=count,
            mean_median_absolute_error=_mean_decimal(
                tuple(item.median_absolute_error for item in scored)
            ),
            mean_interval_width=_mean_decimal(
                tuple(item.interval_width for item in scored)
            ),
            mean_interval_score=_mean_decimal(
                tuple(item.interval_score for item in scored)
            ),
        )
    return NumericAnalyticsSnapshot(
        scored_predictions=scored,
        calibration_bins=_containment_bins(scored),
        available_tags=source.available_tags,
        available_units=source.available_units,
        selected_tag=tag,
        selected_unit=unit,
        unit_summary=unit_summary,
    )


def _containment_bins(
    scored: tuple[NumericScoredPrediction, ...],
) -> tuple[ContainmentCalibrationBin, ...]:
    members: list[list[NumericScoredPrediction]] = [[] for _index in range(10)]
    for item in scored:
        confidence = item.observation.confidence_percent
        members[min(confidence // 10, 9)].append(item)

    bins: list[ContainmentCalibrationBin] = []
    for index, bin_members in enumerate(members):
        lower = index * 10
        upper = 100 if index == 9 else lower + 9
        count = len(bin_members)
        bins.append(
            ContainmentCalibrationBin(
                lower_percent=lower,
                upper_percent=upper,
                count=count,
                mean_confidence_percent=(
                    None
                    if not count
                    else _mean_decimal(
                        tuple(
                            Decimal(item.observation.confidence_percent)
                            for item in bin_members
                        )
                    )
                ),
                observed_containment_percent=(
                    None
                    if not count
                    else _percentage(
                        sum(item.contained for item in bin_members),
                        count,
                    )
                ),
            )
        )
    return tuple(bins)


def _validate_numeric_observations(
    observations: tuple[NumericScoringObservation, ...],
) -> None:
    prediction_ids = tuple(item.prediction_id for item in observations)
    resolution_ids = tuple(item.resolution_id for item in observations)
    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError(
            "Each resolved Numeric Prediction must contribute exactly once."
        )
    if len(set(resolution_ids)) != len(resolution_ids):
        raise ValueError("Each Numeric Resolution must contribute exactly once.")
    for observation in observations:
        _validate_numeric_observation(observation)


def _validate_numeric_observation(observation: NumericScoringObservation) -> None:
    if (
        observation.resolved_at.tzinfo is None
        or observation.resolved_at.utcoffset() is None
    ):
        raise ValueError("Numeric Resolution timestamps must be timezone-aware.")
    values = (
        observation.lower_bound,
        observation.median_estimate,
        observation.upper_bound,
        observation.actual_value,
    )
    decimal_places = values[0].decimal_places
    if any(value.decimal_places != decimal_places for value in values[1:]):
        raise ValueError("Numeric scoring values must use one fixed precision.")
    if (
        isinstance(observation.confidence_percent, bool)
        or not isinstance(observation.confidence_percent, int)
        or not 1 <= observation.confidence_percent <= 99
    ):
        raise ValueError(
            "Numeric confidence must be a whole percent from 1 through 99."
        )
    if not (
        observation.lower_bound.scaled_value
        <= observation.median_estimate.scaled_value
        <= observation.upper_bound.scaled_value
    ):
        raise ValueError("Numeric scoring intervals must be ordered lower to upper.")


def _mean_decimal(values: tuple[Decimal, ...]) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return sum(values, start=Decimal(0)) / len(values)


def _percentage(numerator: int, denominator: int) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(100) * numerator / denominator
