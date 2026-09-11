from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations_with_replacement

import pytest

from reckonsolve.analytics.quantiles import (
    interval_score,
    quantile_score,
    quantile_scorecard,
    select_final_revision,
    weighted_interval_score,
)
from reckonsolve.domain.forecast_contracts import (
    EffectiveResolutionTime,
    ForecastContractValidationError,
    ForecastDeadline,
    ResolutionTiming,
    legacy_contract,
    prospective_contract,
)
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    PredictionType,
    PredictionValidationError,
)
from reckonsolve.domain.quantiles import (
    QUANTILE_LEVELS,
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
    QuantileRevision,
)

T0 = datetime(2026, 9, 11, 10, tzinfo=UTC)
DEADLINE = ForecastDeadline(T0 + timedelta(hours=2))
CONTRACT = prospective_contract(PredictionType.NUMERIC, DEADLINE)
DEFINITION = QuantileDefinition("days", 2, NumericValueConstraint.CONTINUOUS)


def values(items=(-2, -1, 0, 1, 2), precision=2):
    return FiveQuantiles.from_values(
        dict(zip(QUANTILE_LEVELS, items, strict=True)), precision
    )


def actual(value, precision=2):
    return FixedPrecisionValue.from_value(value, precision)


@pytest.mark.parametrize(
    "mapping",
    [
        {5: 1},
        {5: 0, 25: 1, 50: 2, 75: 3, 95: 4, 99: 5},
        {5.0: 0, 25: 1, 50: 2, 75: 3, 95: 4},
    ],
)
def test_exact_required_levels(mapping):
    with pytest.raises(PredictionValidationError, match="exactly"):
        FiveQuantiles.from_values(mapping, 2)


@pytest.mark.parametrize(
    "bad",
    [True, 0.1, "NaN", "Infinity", Decimal("NaN"), "1e3", "0.001", "10000000000000000"],
)
def test_quantiles_reject_nonexact_nonfinite_or_unsupported_values(bad):
    with pytest.raises(PredictionValidationError):
        values((bad,) * 5)


def test_order_equal_fixed_precision_and_whole_number_rules():
    repeated = values((1,) * 5)
    DEFINITION.validate_quantiles(repeated)
    with pytest.raises(PredictionValidationError, match="q05"):
        values((0, 2, 1, 3, 4))
    with pytest.raises(PredictionValidationError, match="precision"):
        replace(repeated, q05=actual(1, 1))
    whole = replace(DEFINITION, value_constraint=NumericValueConstraint.WHOLE_NUMBER)
    whole.validate_quantiles(values((-3, -2, 0, 1, 1)))
    whole.validate_value(
        actual("2.00")
    )  # integral semantics, not a zero-precision alias
    with pytest.raises(PredictionValidationError, match="integral"):
        whole.validate_quantiles(values((0, 0, "0.5", 1, 1)))
    with pytest.raises(PredictionValidationError, match="integral"):
        whole.validate_value(actual("2.01"))
    with pytest.raises(PredictionValidationError, match="precision"):
        whole.validate_quantiles(values(precision=1))
    with pytest.raises(PredictionValidationError, match="Forecast Review"):
        whole.validate_replacement(repeated, repeated)
    whole.validate_replacement(repeated, values((1, 1, 1, 1, 2)))


@pytest.mark.parametrize("y", [-3, -2, -1, 0, 1, 2, 3])
def test_wis_equivalence_and_decomposition_over_ordered_tied_quantiles(y):
    # Includes zero-width inner/outer intervals, signed values and every endpoint.
    for anchors in combinations_with_replacement((-2, 0, 2), 5):
        forecast, outcome = values(anchors), actual(y)
        score = weighted_interval_score(DEFINITION, forecast, outcome)
        equivalent = (
            sum(
                (
                    quantile_score(v, outcome, level)
                    for level, v in zip(QUANTILE_LEVELS, forecast.values, strict=True)
                ),
                Fraction(),
            )
            / 5
        )
        assert score.wis == equivalent
        assert (
            score.wis == score.dispersion + score.underprediction + score.overprediction
        )
        assert (
            score.wis
            == score.median_contribution
            + score.interval_50_contribution
            + score.interval_90_contribution
        )
        assert score.wis >= 0


def test_hand_calculated_wis_and_miss_directions():
    # q=(0,1,2,3,4), y=6: IS50=14, IS90=44; WIS=(2+3.5+2.2)/2.5=3.08
    score = weighted_interval_score(DEFINITION, values((0, 1, 2, 3, 4)), actual(6))
    assert score.wis == Fraction(77, 25)
    assert score.interval_50.score == 14
    assert score.interval_90.score == 44
    assert score.interval_90.outcome_location == "above"
    assert score.interval_90.miss_distance == 2
    assert score.signed_median_miss == 4
    assert score.overprediction == 0
    other = weighted_interval_score(DEFINITION, values((0, 1, 2, 3, 4)), actual(-2))
    assert other.wis == score.wis
    assert other.underprediction == 0
    assert other.interval_90.outcome_location == "below"
    assert other.signed_median_miss == -4
    for endpoint in (0, 4):
        interval = interval_score(
            actual(0), actual(4), actual(endpoint), Fraction(1, 10)
        )
        assert interval.score == interval.width == 4
        assert interval.miss_distance == 0
        assert interval.outcome_location == "inside"


def test_exact_six_decimals_and_scores_ignore_decimal_context():
    definition = replace(DEFINITION, decimal_places=6)
    forecast = values(
        ("-999.123456", "-0.000001", "0.000001", "0.000002", "888.654321"), 6
    )
    outcome = actual("123.456789", 6)
    expected = weighted_interval_score(definition, forecast, outcome)
    with localcontext() as ctx:
        ctx.prec = 3
        assert weighted_interval_score(definition, forecast, outcome) == expected
    zero_width = weighted_interval_score(
        definition, values(("0.000001",) * 5, 6), actual("0.000001", 6)
    )
    assert zero_width.wis == 0


def revisions():
    return tuple(
        QuantileRevision(
            i + 1, 123, values((i,) * 5), i + 1, T0 + timedelta(minutes=30 * i)
        )
        for i in range(3)
    )


@pytest.mark.parametrize(
    ("effective_minutes", "final_id"),
    [(15, 1), (30, 1), (31, 2), (60, 2), (119, 3), (120, 3), (180, 3)],
)
def test_strict_effective_cutoff_and_deadline(effective_minutes, final_id):
    timing = ResolutionTiming(
        EffectiveResolutionTime(T0 + timedelta(minutes=effective_minutes)),
        T0 + timedelta(hours=4),
    )
    history = revisions()
    score = quantile_scorecard(CONTRACT, DEFINITION, history, timing, actual(2))
    assert score.final_revision_id == final_id
    assert score.initial == weighted_interval_score(
        DEFINITION, history[0].quantiles, actual(2)
    )
    assert score.final == weighted_interval_score(
        DEFINITION, history[final_id - 1].quantiles, actual(2)
    )
    assert score.delta_wis == score.initial.wis - score.final.wis
    assert score.excluded_revision_ids == tuple(range(final_id + 1, 4))


@pytest.mark.parametrize("offset", [-1, 0])
def test_effective_at_or_before_initial_is_explicitly_unscored(offset):
    timing = ResolutionTiming(
        EffectiveResolutionTime(T0 + timedelta(microseconds=offset)),
        T0 + timedelta(hours=4),
    )
    score = quantile_scorecard(CONTRACT, DEFINITION, revisions(), timing, actual(2))
    assert (
        score.final_revision_id
        is score.final
        is score.initial
        is score.delta_wis
        is None
    )
    assert score.excluded_revision_ids == (1, 2, 3)
    assert "No WIS" in score.unscored_reason


def test_timezone_equivalence_single_revision_and_improvement_signs():
    pacific = timezone(timedelta(hours=-7))
    first = revisions()[0]
    history = (replace(first, created_at=first.created_at.astimezone(pacific)),)
    timing = ResolutionTiming(
        EffectiveResolutionTime(T0 + timedelta(hours=3)), T0 + timedelta(hours=4)
    )
    assert (
        quantile_scorecard(CONTRACT, DEFINITION, history, timing, actual(0)).delta_wis
        == 0
    )
    assert (
        quantile_scorecard(
            CONTRACT, DEFINITION, revisions(), timing, actual(0)
        ).delta_wis
        < 0
    )
    assert (
        quantile_scorecard(
            CONTRACT, DEFINITION, revisions(), timing, actual(2)
        ).delta_wis
        > 0
    )


def test_selection_rejects_legacy_cross_question_and_invalid_history():
    history = revisions()
    timing = ResolutionTiming(
        EffectiveResolutionTime(T0 + timedelta(hours=3)), T0 + timedelta(hours=4)
    )
    with pytest.raises(ValueError, match="five-quantile"):
        select_final_revision(
            legacy_contract(PredictionType.NUMERIC), DEFINITION, history, timing
        )
    for bad in (
        (history[1],),
        history[::-1],
        (history[0], replace(history[1], prediction_id=456)),
        (history[0], replace(history[1], revision_id=1)),
        (history[0], replace(history[1], created_at=T0)),
        (history[0], replace(history[1], created_at=DEADLINE.instant)),
        (history[0], replace(history[1], quantiles=history[0].quantiles)),
    ):
        with pytest.raises(
            (ValueError, ForecastContractValidationError, PredictionValidationError)
        ):
            select_final_revision(CONTRACT, DEFINITION, bad, timing)
