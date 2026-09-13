"""Shared plain-text presentation of already calculated individual WIS facts."""

from decimal import Decimal, localcontext
from fractions import Fraction

from reckonsolve.analytics.quantiles import QuantileScorecard
from reckonsolve.domain.quantiles import quantile_summary


def exact_score_text(value: Fraction) -> str:
    """WIS has a terminating base-ten representation; never pass through float."""
    with localcontext() as context:
        context.prec = max(
            28, len(str(abs(value.numerator))) + len(str(value.denominator)) + 2
        )
        text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def quantile_scorecard_lines(card: QuantileScorecard) -> tuple[str, ...]:
    assert card.definition is not None and card.actual_value is not None
    unit = card.definition.unit
    lines = [f"Effective actual: {card.actual_value} {unit}"]
    if card.final is None:
        assert card.unscored_reason is not None
        lines.extend(("Not scored", card.unscored_reason))
    else:
        score = card.final
        revision = card.scoring_revision
        assert (
            revision is not None
            and card.initial is not None
            and card.delta_wis is not None
        )
        lines += [
            f"WIS: {exact_score_text(score.wis)} {unit} — lower is better",
            f"Scored revision {revision.sequence} (ID {revision.revision_id}): {quantile_summary(revision.quantiles, unit)}",
            f"Initial WIS: {exact_score_text(card.initial.wis)} {unit} · Final WIS: {exact_score_text(score.wis)} {unit}",
            f"Delta WIS (initial minus final): {exact_score_text(card.delta_wis)} {unit}. Positive means the final forecast scored better; negative means worse.",
            "This compares forecasts within this Prediction, not causal updating skill or a cross-question score.",
            f"Median absolute error: {exact_score_text(score.median_absolute_error)} {unit}; signed miss (actual minus median): {exact_score_text(score.signed_median_miss)} {unit}",
            f"Median weighted contribution to WIS: {exact_score_text(score.median_contribution)} {unit}",
        ]
        for level, interval, contribution in (
            (50, score.interval_50, score.interval_50_contribution),
            (90, score.interval_90, score.interval_90_contribution),
        ):
            lines.append(
                f"{level}% interval: actual {interval.outcome_location} the interval; width {exact_score_text(interval.width)} {unit}; "
                f"outside distance {exact_score_text(interval.miss_distance)} {unit}; "
                f"interval score {exact_score_text(interval.score)} {unit}; "
                f"weighted contribution to WIS {exact_score_text(contribution)} {unit}"
            )
        lines.append(
            "Weighted contributions include the 2.5 denominator and sum to WIS. Endpoint equality has no outside penalty."
        )
    if card.excluded_revision_ids:
        lines.append(
            "Revisions excluded at/after the effective cutoff (IDs): "
            + ", ".join(map(str, card.excluded_revision_ids))
            + ". Their history is preserved."
        )
    if card.scoring_facts_corrected:
        lines.append(
            "Scoring facts corrected — score and final selection use the latest audited actual value and effective time."
        )
    return tuple(lines)
