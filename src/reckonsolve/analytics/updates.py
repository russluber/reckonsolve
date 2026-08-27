"""Retrospective initial-versus-final feedback for resolved Predictions."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, localcontext

from reckonsolve.domain.analytics import (
    AnalyticsSource,
    NumericAnalyticsSource,
    NumericScoringObservation,
)
from reckonsolve.domain.predictions import FixedPrecisionValue

from .numeric import score_numeric_observation
from .scoring import brier_score


@dataclass(frozen=True, slots=True)
class BinaryUpdatePair:
    """One revised-and-resolved Binary Prediction scored at two revisions."""

    prediction_id: int
    resolved_at: datetime
    initial_revision_id: int
    final_revision_id: int
    initial_probability_percent: int
    final_probability_percent: int
    initial_brier: float
    final_brier: float
    score_improvement: float


@dataclass(frozen=True, slots=True)
class BinaryUpdateAnalyticsSnapshot:
    """Paired Binary update feedback plus the separate unrevised count."""

    pairs: tuple[BinaryUpdatePair, ...]
    unrevised_count: int
    mean_initial_brier: float | None
    mean_final_brier: float | None
    mean_score_improvement: float | None

    @property
    def paired_count(self) -> int:
        return len(self.pairs)


@dataclass(frozen=True, slots=True)
class NumericUpdatePair:
    """One revised-and-resolved Numeric Prediction scored at two revisions."""

    prediction_id: int
    resolved_at: datetime
    unit: str
    initial_revision_id: int
    final_revision_id: int
    initial_confidence_percent: int
    final_confidence_percent: int
    initial_contained: bool
    final_contained: bool
    initial_median_absolute_error: Decimal
    final_median_absolute_error: Decimal
    initial_interval_width: Decimal
    final_interval_width: Decimal
    initial_interval_score: Decimal
    final_interval_score: Decimal


@dataclass(frozen=True, slots=True)
class NumericUnitUpdateSummary:
    """Raw paired Numeric comparisons for one exact unit label."""

    unit: str
    count: int
    mean_initial_median_absolute_error: Decimal
    mean_final_median_absolute_error: Decimal
    mean_median_error_reduction: Decimal
    mean_initial_interval_width: Decimal
    mean_final_interval_width: Decimal
    mean_narrowing: Decimal
    mean_initial_interval_score: Decimal
    mean_final_interval_score: Decimal
    mean_interval_score_improvement: Decimal


@dataclass(frozen=True, slots=True)
class NumericUpdateAnalyticsSnapshot:
    """Unitless paired containment feedback and optional exact-unit metrics."""

    pairs: tuple[NumericUpdatePair, ...]
    unrevised_count: int
    mean_initial_confidence_percent: Decimal | None
    mean_final_confidence_percent: Decimal | None
    initial_contained_count: int
    final_contained_count: int
    unit_summary: NumericUnitUpdateSummary | None

    @property
    def paired_count(self) -> int:
        return len(self.pairs)


def summarize_binary_updates(
    source: AnalyticsSource,
    *,
    tag: str | None = None,
) -> BinaryUpdateAnalyticsSnapshot:
    """Compare revision one with the captured scoring revision exactly once."""

    tag_key = _tag_key(tag)
    observations = tuple(
        observation
        for observation in source.observations
        if tag_key is None or tag_key in {item.casefold() for item in observation.tags}
    )
    _validate_unique_prediction_ids(
        tuple(observation.prediction_id for observation in observations),
        "Binary",
    )
    pairs: list[BinaryUpdatePair] = []
    unrevised_count = 0
    for observation in observations:
        initial_revision_id, initial_probability = _binary_initial_values(
            observation.initial_revision_id,
            observation.initial_probability_percent,
            observation.scoring_revision_id,
            observation.probability_percent,
        )
        initial_brier = brier_score(initial_probability, observation.outcome)
        final_brier = brier_score(
            observation.probability_percent,
            observation.outcome,
        )
        if initial_revision_id == observation.scoring_revision_id:
            if initial_probability != observation.probability_percent:
                raise ValueError(
                    "An unrevised Binary observation has conflicting initial values."
                )
            unrevised_count += 1
            continue
        pairs.append(
            BinaryUpdatePair(
                prediction_id=observation.prediction_id,
                resolved_at=observation.resolved_at,
                initial_revision_id=initial_revision_id,
                final_revision_id=observation.scoring_revision_id,
                initial_probability_percent=initial_probability,
                final_probability_percent=observation.probability_percent,
                initial_brier=initial_brier,
                final_brier=final_brier,
                score_improvement=initial_brier - final_brier,
            )
        )
    return BinaryUpdateAnalyticsSnapshot(
        pairs=tuple(pairs),
        unrevised_count=unrevised_count,
        mean_initial_brier=_mean_float(tuple(item.initial_brier for item in pairs)),
        mean_final_brier=_mean_float(tuple(item.final_brier for item in pairs)),
        mean_score_improvement=_mean_float(
            tuple(item.score_improvement for item in pairs)
        ),
    )


def summarize_numeric_updates(
    source: NumericAnalyticsSource,
    *,
    tag: str | None = None,
    unit: str | None = None,
) -> NumericUpdateAnalyticsSnapshot:
    """Compare Numeric revision one with the captured scoring revision once."""

    tag_key = _tag_key(tag)
    observations = tuple(
        observation
        for observation in source.observations
        if (
            tag_key is None or tag_key in {item.casefold() for item in observation.tags}
        )
        and (unit is None or observation.unit == unit)
    )
    _validate_unique_prediction_ids(
        tuple(observation.prediction_id for observation in observations),
        "Numeric",
    )
    pairs: list[NumericUpdatePair] = []
    unrevised_count = 0
    for observation in observations:
        initial_revision_id, initial_values = _numeric_initial_values(observation)
        if initial_revision_id == observation.scoring_revision_id:
            if initial_values != (
                observation.lower_bound,
                observation.median_estimate,
                observation.upper_bound,
                observation.confidence_percent,
            ):
                raise ValueError(
                    "An unrevised Numeric observation has conflicting initial values."
                )
            unrevised_count += 1
            continue
        initial_lower, initial_median, initial_upper, initial_confidence = (
            initial_values
        )
        initial_scored = score_numeric_observation(
            replace(
                observation,
                scoring_revision_id=initial_revision_id,
                lower_bound=initial_lower,
                median_estimate=initial_median,
                upper_bound=initial_upper,
                confidence_percent=initial_confidence,
            )
        )
        final_scored = score_numeric_observation(observation)
        pairs.append(
            NumericUpdatePair(
                prediction_id=observation.prediction_id,
                resolved_at=observation.resolved_at,
                unit=observation.unit,
                initial_revision_id=initial_revision_id,
                final_revision_id=observation.scoring_revision_id,
                initial_confidence_percent=initial_confidence,
                final_confidence_percent=observation.confidence_percent,
                initial_contained=initial_scored.contained,
                final_contained=final_scored.contained,
                initial_median_absolute_error=(initial_scored.median_absolute_error),
                final_median_absolute_error=final_scored.median_absolute_error,
                initial_interval_width=initial_scored.interval_width,
                final_interval_width=final_scored.interval_width,
                initial_interval_score=initial_scored.interval_score,
                final_interval_score=final_scored.interval_score,
            )
        )
    paired = tuple(pairs)
    return NumericUpdateAnalyticsSnapshot(
        pairs=paired,
        unrevised_count=unrevised_count,
        mean_initial_confidence_percent=_mean_decimal(
            tuple(Decimal(item.initial_confidence_percent) for item in paired)
        ),
        mean_final_confidence_percent=_mean_decimal(
            tuple(Decimal(item.final_confidence_percent) for item in paired)
        ),
        initial_contained_count=sum(item.initial_contained for item in paired),
        final_contained_count=sum(item.final_contained for item in paired),
        unit_summary=(
            None if unit is None or not paired else _numeric_unit_summary(unit, paired)
        ),
    )


def _numeric_initial_values(
    observation: NumericScoringObservation,
) -> tuple[
    int,
    tuple[
        FixedPrecisionValue,
        FixedPrecisionValue,
        FixedPrecisionValue,
        int,
    ],
]:
    values = (
        observation.initial_lower_bound,
        observation.initial_median_estimate,
        observation.initial_upper_bound,
        observation.initial_confidence_percent,
    )
    if observation.initial_revision_id is None and all(
        value is None for value in values
    ):
        return observation.scoring_revision_id, (
            observation.lower_bound,
            observation.median_estimate,
            observation.upper_bound,
            observation.confidence_percent,
        )
    if observation.initial_revision_id is None or any(
        value is None for value in values
    ):
        raise ValueError("Numeric initial revision context must be complete.")
    lower, median, upper, confidence = values
    if not isinstance(lower, FixedPrecisionValue):
        raise TypeError("Numeric initial lower bound is invalid.")
    if not isinstance(median, FixedPrecisionValue):
        raise TypeError("Numeric initial median is invalid.")
    if not isinstance(upper, FixedPrecisionValue):
        raise TypeError("Numeric initial upper bound is invalid.")
    if not isinstance(confidence, int) or isinstance(confidence, bool):
        raise TypeError("Numeric initial confidence is invalid.")
    return observation.initial_revision_id, (lower, median, upper, confidence)


def _binary_initial_values(
    initial_revision_id: int | None,
    initial_probability_percent: int | None,
    final_revision_id: int,
    final_probability_percent: int,
) -> tuple[int, int]:
    if initial_revision_id is None and initial_probability_percent is None:
        return final_revision_id, final_probability_percent
    if initial_revision_id is None or initial_probability_percent is None:
        raise ValueError("Binary initial revision context must be complete.")
    return initial_revision_id, initial_probability_percent


def _numeric_unit_summary(
    unit: str,
    pairs: tuple[NumericUpdatePair, ...],
) -> NumericUnitUpdateSummary:
    initial_error = _mean_decimal(
        tuple(item.initial_median_absolute_error for item in pairs)
    )
    final_error = _mean_decimal(
        tuple(item.final_median_absolute_error for item in pairs)
    )
    initial_width = _mean_decimal(tuple(item.initial_interval_width for item in pairs))
    final_width = _mean_decimal(tuple(item.final_interval_width for item in pairs))
    initial_score = _mean_decimal(tuple(item.initial_interval_score for item in pairs))
    final_score = _mean_decimal(tuple(item.final_interval_score for item in pairs))
    assert initial_error is not None
    assert final_error is not None
    assert initial_width is not None
    assert final_width is not None
    assert initial_score is not None
    assert final_score is not None
    return NumericUnitUpdateSummary(
        unit=unit,
        count=len(pairs),
        mean_initial_median_absolute_error=initial_error,
        mean_final_median_absolute_error=final_error,
        mean_median_error_reduction=initial_error - final_error,
        mean_initial_interval_width=initial_width,
        mean_final_interval_width=final_width,
        mean_narrowing=initial_width - final_width,
        mean_initial_interval_score=initial_score,
        mean_final_interval_score=final_score,
        mean_interval_score_improvement=initial_score - final_score,
    )


def _tag_key(tag: str | None) -> str | None:
    return None if tag is None else tag.strip().casefold() or None


def _validate_unique_prediction_ids(
    prediction_ids: tuple[int, ...],
    forecast_type: str,
) -> None:
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError(
            f"Each revised-and-resolved {forecast_type} Prediction must appear once."
        )


def _mean_float(values: tuple[float, ...]) -> float | None:
    return None if not values else sum(values) / len(values)


def _mean_decimal(values: tuple[Decimal, ...]) -> Decimal | None:
    if not values:
        return None
    with localcontext() as context:
        context.prec = 50
        return sum(values, Decimal(0)) / Decimal(len(values))
