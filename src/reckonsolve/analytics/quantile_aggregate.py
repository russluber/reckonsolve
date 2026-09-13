"""Exactly-once, scale-free five-quantile calibration and update feedback."""

from dataclasses import dataclass
from fractions import Fraction
from math import sqrt

from reckonsolve.domain.analytics import QuantileAnalyticsSource
from reckonsolve.domain.quantiles import QUANTILE_LEVELS, NumericValueConstraint

from .quantiles import QuantileScorecard, resolved_quantile_scorecard


@dataclass(frozen=True, slots=True)
class Proportion:
    """Exact empirical proportion with a display-only 95% Wilson interval."""

    count: int
    total: int

    def __post_init__(self) -> None:
        if (
            type(self.count) is not int
            or type(self.total) is not int
            or not 0 <= self.count <= self.total
        ):
            raise ValueError("Proportion counts must satisfy 0 <= count <= total.")

    @property
    def fraction(self) -> Fraction | None:
        return Fraction(self.count, self.total) if self.total else None

    @property
    def wilson_95(self) -> tuple[float, float] | None:
        if not self.total:
            return None
        z = 1.959963984540054
        p, n = self.count / self.total, self.total
        divisor = 1 + z * z / n
        center = (p + z * z / (2 * n)) / divisor
        radius = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / divisor
        return max(0.0, center - radius), min(1.0, center + radius)


@dataclass(frozen=True, slots=True)
class QuantileCalibrationLevel:
    nominal_percent: int
    strict: Proportion  # actual < elicited quantile
    inclusive: Proportion  # actual <= elicited quantile


@dataclass(frozen=True, slots=True)
class OutcomeBalance:
    below: Proportion
    inside: Proportion  # equal for the median; inclusive for intervals
    above: Proportion


@dataclass(frozen=True, slots=True)
class QuantileCalibrationGroup:
    value_constraint: NumericValueConstraint
    sample_size: int
    levels: tuple[QuantileCalibrationLevel, ...]
    interval_50: OutcomeBalance
    interval_90: OutcomeBalance
    median: OutcomeBalance


@dataclass(frozen=True, slots=True)
class QuantileAnalyticsSnapshot:
    scored_predictions: tuple[QuantileScorecard, ...]
    resolved_candidate_count: int
    unscored_prediction_count: int
    continuous: QuantileCalibrationGroup
    whole_number: QuantileCalibrationGroup
    better: Proportion
    equal: Proportion
    worse: Proportion
    unrevised_count: int  # final scoring revision is still sequence one
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]

    @property
    def scored_prediction_count(self) -> int:
        return len(self.scored_predictions)


def summarize_quantile_analytics(
    source: QuantileAnalyticsSource,
    *,
    tag: str | None = None,
    unit: str | None = None,
) -> QuantileAnalyticsSnapshot:
    """Reuse the individual exact scorer; never average WIS across questions."""
    ids = [r.revisions[0].prediction_id for r in source.records]
    resolution_ids = [
        r.resolution_history.original.resolution_id for r in source.records
    ]
    if len(set(ids)) != len(ids) or len(set(resolution_ids)) != len(resolution_ids):
        raise ValueError("Each five-quantile Prediction must contribute at most once.")
    tag_key = None if tag is None else tag.strip().casefold() or None
    unit = None if unit is None else unit.strip() or None
    records = tuple(
        r
        for r in source.records
        if (
            (tag_key is None or tag_key in {t.casefold() for t in r.tags})
            and (unit is None or r.definition.unit == unit)
        )
    )
    cards = tuple(
        resolved_quantile_scorecard(
            r.contract,
            r.definition,
            r.revisions,
            r.resolution_history,
        )
        for r in records
    )
    scored = tuple(c for c in cards if c.final is not None)
    revised = tuple(
        c
        for c in scored
        if (c.scoring_revision is not None and c.scoring_revision.sequence > 1)
    )
    gains = tuple(c.delta_wis for c in revised)
    assert all(gain is not None for gain in gains)
    tags: dict[str, str] = {}
    for record in source.records:
        for label in record.tags:
            tags.setdefault(label.casefold(), label)
    return QuantileAnalyticsSnapshot(
        scored,
        len(cards),
        len(cards) - len(scored),
        _group(scored, NumericValueConstraint.CONTINUOUS),
        _group(scored, NumericValueConstraint.WHOLE_NUMBER),
        Proportion(sum(g > 0 for g in gains), len(gains)),
        Proportion(sum(g == 0 for g in gains), len(gains)),
        Proportion(sum(g < 0 for g in gains), len(gains)),
        len(scored) - len(revised),
        tuple(tags[key] for key in sorted(tags)),
        tuple(sorted({r.definition.unit for r in source.records})),
    )


def _group(
    cards: tuple[QuantileScorecard, ...],
    constraint: NumericValueConstraint,
) -> QuantileCalibrationGroup:
    selected = tuple(c for c in cards if c.definition.value_constraint is constraint)
    # Scorer validation guarantees matching fixed precision within each pair.
    # Scaled integers avoid loss of equality for large or signed decimal values.
    pairs = tuple(
        (
            c.actual_value.scaled_value,
            tuple(v.scaled_value for v in c.scoring_revision.quantiles.values),
        )
        for c in selected
    )
    n = len(pairs)
    levels = tuple(
        QuantileCalibrationLevel(
            level,
            Proportion(sum(y < q[index] for y, q in pairs), n),
            Proportion(sum(y <= q[index] for y, q in pairs), n),
        )
        for index, level in enumerate(QUANTILE_LEVELS)
    )

    def balance(lower: int, upper: int) -> OutcomeBalance:
        return OutcomeBalance(
            Proportion(sum(y < q[lower] for y, q in pairs), n),
            Proportion(sum(q[lower] <= y <= q[upper] for y, q in pairs), n),
            Proportion(sum(y > q[upper] for y, q in pairs), n),
        )

    return QuantileCalibrationGroup(
        constraint, n, levels, balance(1, 3), balance(0, 4), balance(2, 2)
    )
