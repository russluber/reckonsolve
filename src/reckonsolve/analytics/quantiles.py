"""Exact individual WIS and cutoff selection, never cross-question raw aggregation."""

from dataclasses import dataclass
from fractions import Fraction

from reckonsolve.domain.forecast_contracts import (
    ForecastCohort,
    ForecastContract,
    ForecastingWindow,
    ResolutionTiming,
)
from reckonsolve.domain.predictions import FixedPrecisionValue
from reckonsolve.domain.quantiles import (
    QUANTILE_LEVELS,
    FiveQuantiles,
    QuantileDefinition,
    QuantileRevision,
)


def _exact(value: FixedPrecisionValue) -> Fraction:
    return Fraction(value.scaled_value, 10**value.decimal_places)


@dataclass(frozen=True, slots=True)
class IntervalScore:
    width: Fraction
    outcome_location: str
    miss_distance: Fraction
    underprediction: Fraction
    overprediction: Fraction

    @property
    def score(self) -> Fraction:
        return self.width + self.underprediction + self.overprediction


def interval_score(
    lower: FixedPrecisionValue,
    upper: FixedPrecisionValue,
    actual: FixedPrecisionValue,
    alpha: Fraction,
) -> IntervalScore:
    if not isinstance(alpha, Fraction) or not 0 < alpha < 1:
        raise ValueError(
            "Tail probability must be an exact fraction strictly between zero and one."
        )
    if len({v.decimal_places for v in (lower, upper, actual)}) != 1:
        raise ValueError("Interval and outcome precision must match.")
    lo, hi, y = map(_exact, (lower, upper, actual))
    if lo > hi:
        raise ValueError("Interval endpoints are crossed.")
    below, above = max(lo - y, 0), max(y - hi, 0)
    return IntervalScore(
        hi - lo,
        "below" if below else "above" if above else "inside",
        Fraction(below + above),
        2 * above / alpha,
        2 * below / alpha,
    )


def quantile_score(
    value: FixedPrecisionValue, actual: FixedPrecisionValue, level: int
) -> Fraction:
    """Twice pinball loss; the mean of the fixed five equals WIS."""
    if type(level) is not int or level not in QUANTILE_LEVELS:
        raise ValueError("Only the five elicited quantile levels are supported.")
    if value.decimal_places != actual.decimal_places:
        raise ValueError("Quantile and outcome precision must match.")
    error = _exact(actual) - _exact(value)
    tau = Fraction(level, 100)
    return 2 * (tau * error if error >= 0 else (tau - 1) * error)


@dataclass(frozen=True, slots=True)
class WISScore:
    wis: Fraction
    median_absolute_error: Fraction
    signed_median_miss: Fraction  # actual minus median: positive is underprediction
    interval_50: IntervalScore
    interval_90: IntervalScore
    median_contribution: Fraction
    interval_50_contribution: Fraction
    interval_90_contribution: Fraction
    dispersion: Fraction
    underprediction: Fraction
    overprediction: Fraction


def weighted_interval_score(
    definition: QuantileDefinition,
    quantiles: FiveQuantiles,
    actual: FixedPrecisionValue,
) -> WISScore:
    definition.validate_quantiles(quantiles)
    definition.validate_value(actual)
    middle = interval_score(quantiles.q25, quantiles.q75, actual, Fraction(1, 2))
    outer = interval_score(quantiles.q05, quantiles.q95, actual, Fraction(1, 10))
    signed_miss = _exact(actual) - _exact(quantiles.q50)
    median_term = abs(signed_miss) / 5
    middle_term, outer_term = middle.score / 10, outer.score / 50
    return WISScore(
        median_term + middle_term + outer_term,
        abs(signed_miss),
        signed_miss,
        middle,
        outer,
        median_term,
        middle_term,
        outer_term,
        middle.width / 10 + outer.width / 50,
        max(signed_miss, Fraction()) / 5
        + middle.underprediction / 10
        + outer.underprediction / 50,
        max(-signed_miss, Fraction()) / 5
        + middle.overprediction / 10
        + outer.overprediction / 50,
    )


def select_final_revision(
    contract: ForecastContract,
    definition: QuantileDefinition,
    revisions: tuple[QuantileRevision, ...],
    timing: ResolutionTiming,
) -> QuantileRevision | None:
    """Reject incoherent histories; R <= t0 deliberately has no scoring revision."""
    if contract.cohort is not ForecastCohort.QUANTILE_NUMERIC or not revisions:
        raise ValueError("WIS requires a five-quantile Numeric history.")
    assert contract.forecast_deadline is not None
    window = ForecastingWindow(revisions[0].created_at, contract.forecast_deadline)
    ids = set()
    for index, revision in enumerate(revisions):
        if (
            revision.prediction_id != revisions[0].prediction_id
            or revision.sequence != index + 1
            or revision.revision_id in ids
        ):
            raise ValueError(
                "Revisions must form one complete ordered Prediction history."
            )
        ids.add(revision.revision_id)
        definition.validate_quantiles(revision.quantiles)
        if revision.created_at > timing.recorded_at:
            raise ValueError("A forecast revision cannot follow recorded Resolution.")
        if index:
            window.validate_revision(
                previous_revision_at=revisions[index - 1].created_at,
                proposed_revision_at=revision.created_at,
            )
            definition.validate_replacement(
                revisions[index - 1].quantiles, revision.quantiles
            )
    cutoff = window.scoring_cutoff(timing.effective)
    return next((r for r in reversed(revisions) if r.created_at < cutoff), None)


@dataclass(frozen=True, slots=True)
class QuantileScorecard:
    prediction_id: int
    final_revision_id: int | None
    excluded_revision_ids: tuple[int, ...]
    initial: WISScore | None
    final: WISScore | None
    delta_wis: Fraction | None
    unscored_reason: str | None


def quantile_scorecard(
    contract: ForecastContract,
    definition: QuantileDefinition,
    revisions: tuple[QuantileRevision, ...],
    timing: ResolutionTiming,
    actual: FixedPrecisionValue,
) -> QuantileScorecard:
    definition.validate_value(actual)
    final = select_final_revision(contract, definition, revisions, timing)
    assert contract.forecast_deadline is not None
    cutoff = min(contract.forecast_deadline.instant, timing.effective.instant)
    excluded = tuple(r.revision_id for r in revisions if r.created_at >= cutoff)
    if final is None:
        return QuantileScorecard(
            revisions[0].prediction_id,
            None,
            excluded,
            None,
            None,
            None,
            "The outcome was already fixed at or before the first forecast. No WIS or calibration observation is produced.",
        )
    initial_score = weighted_interval_score(definition, revisions[0].quantiles, actual)
    final_score = weighted_interval_score(definition, final.quantiles, actual)
    return QuantileScorecard(
        final.prediction_id,
        final.revision_id,
        excluded,
        initial_score,
        final_score,
        initial_score.wis - final_score.wis,
        None,
    )
