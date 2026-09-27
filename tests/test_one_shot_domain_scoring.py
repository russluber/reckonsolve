# Reported wall-clock minutes intentionally have no timezone.
# ruff: noqa: DTZ001
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from itertools import product

import pytest

from reckonsolve.analytics.one_shot import one_shot_score
from reckonsolve.analytics.quantiles import quantile_score
from reckonsolve.domain.forecast_contracts import (
    ForecastCohort,
    ForecastContract,
    ForecastContractValidationError,
    ForecastDeadline,
    ForecastModel,
    ScoringContract,
    contract_status,
    dispatch_forecast_contract,
    one_shot_contract,
    prospective_contract,
)
from reckonsolve.domain.one_shot import OneShotValues, ReportedTime
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)


def quantiles():
    return FiveQuantiles.from_values({5: -2, 25: -1, 50: 0, 75: 1, 95: 2}, 2)


def test_closed_pairs_deadline_rule_and_explicit_dispatch():
    for kind in PredictionType:
        contract = one_shot_contract(kind)
        assert contract.forecast_deadline is None
        assert (
            contract_status(PredictionStatus.OPEN, contract, None)
            is PredictionStatus.OPEN
        )
        assert dispatch_forecast_contract(
            contract,
            trajectory_binary=1,
            quantile_numeric=2,
            one_shot_binary=3,
            one_shot_numeric=4,
        ) == (3 if kind is PredictionType.BINARY else 4)
        with pytest.raises(ForecastContractValidationError, match="does not support"):
            dispatch_forecast_contract(
                contract, trajectory_binary=1, quantile_numeric=2
            )
        with pytest.raises(ForecastContractValidationError, match="cannot have"):
            replace(
                contract,
                forecast_deadline=ForecastDeadline(datetime(2026, 1, 1, tzinfo=UTC)),
            )
    accepted = set()
    for kind, model, scoring in product(PredictionType, ForecastModel, ScoringContract):
        try:
            contract = ForecastContract(kind, model, scoring)
        except ForecastContractValidationError:
            continue
        accepted.add(contract.cohort)
    assert accepted == {ForecastCohort.ONE_SHOT_BINARY, ForecastCohort.ONE_SHOT_NUMERIC}


@pytest.mark.parametrize(
    "probability,outcome,expected",
    [
        (0, BinaryOutcome.NO, 0),
        (100, BinaryOutcome.YES, 0),
        (0, BinaryOutcome.YES, 1),
        (100, BinaryOutcome.NO, 1),
        (80, BinaryOutcome.YES, Fraction(1, 25)),
    ],
)
def test_exact_one_probability_brier(probability, outcome, expected):
    assert (
        one_shot_score(
            one_shot_contract(PredictionType.BINARY),
            PredictionStatus.RESOLVED,
            OneShotValues(probability_percent=probability, answer=outcome),
        )
        == expected
    )


@pytest.mark.parametrize(
    "forecast,reveal",
    [
        (None, None),
        (
            ReportedTime(datetime(2026, 9, 26, 12, 5), True),
            ReportedTime(datetime(2026, 9, 26, 12, 5), True),
        ),
        (
            ReportedTime(datetime(1995, 1, 1, 12), True, -420),
            ReportedTime(datetime(1994, 1, 1, 12), False, 330),
        ),
        (None, ReportedTime(datetime(2099, 1, 1, 12))),
    ],
)
def test_documentary_times_never_select_or_disqualify_a_score(forecast, reveal):
    binary = OneShotValues(
        probability_percent=80,
        answer=BinaryOutcome.YES,
        forecast_reported=forecast,
        reveal_reported=reveal,
    )
    assert one_shot_score(
        one_shot_contract(PredictionType.BINARY), PredictionStatus.RESOLVED, binary
    ) == Fraction(1, 25)
    definition = QuantileDefinition("m", 2, NumericValueConstraint.CONTINUOUS)
    numeric = OneShotValues(
        quantiles=quantiles(),
        answer=FixedPrecisionValue(0, 2),
        forecast_reported=forecast,
        reveal_reported=reveal,
    )
    score = one_shot_score(
        one_shot_contract(PredictionType.NUMERIC),
        PredictionStatus.RESOLVED,
        numeric,
        definition,
    )
    assert score.wis == Fraction(7, 25)
    assert (
        score.wis
        == sum(
            quantile_score(v, numeric.answer, level)
            for v, level in zip(
                numeric.quantiles.values, (5, 25, 50, 75, 95), strict=True
            )
        )
        / 5
    )


@pytest.mark.parametrize("status", [PredictionStatus.OPEN, PredictionStatus.INVALID])
def test_no_answer_and_invalid_have_no_score(status):
    contract = one_shot_contract(PredictionType.BINARY)
    assert (
        one_shot_score(contract, status, OneShotValues(probability_percent=50)) is None
    )
    assert (
        one_shot_score(
            contract,
            status,
            OneShotValues(probability_percent=50, answer=BinaryOutcome.YES),
        )
        is None
    )


def test_reuse_precision_and_integrality_checks_and_reject_wrong_cohorts():
    definition = QuantileDefinition("trees", 2, NumericValueConstraint.WHOLE_NUMBER)
    contract = one_shot_contract(PredictionType.NUMERIC)
    values = OneShotValues(quantiles=quantiles(), answer=FixedPrecisionValue(0, 2))
    assert one_shot_score(
        contract, PredictionStatus.RESOLVED, values, definition
    ).wis == Fraction(7, 25)
    for answer in (FixedPrecisionValue(1, 2), FixedPrecisionValue(0, 0)):
        with pytest.raises(PredictionValidationError):
            one_shot_score(
                contract,
                PredictionStatus.RESOLVED,
                replace(values, answer=answer),
                definition,
            )
    with pytest.raises(PredictionValidationError):
        one_shot_score(
            prospective_contract(
                PredictionType.NUMERIC,
                ForecastDeadline(datetime(2026, 9, 26, tzinfo=UTC) + timedelta(days=1)),
            ),
            PredictionStatus.RESOLVED,
            values,
            definition,
        )


@pytest.mark.parametrize(
    "wall", [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 0, 0, 1)]
)
def test_reported_time_does_not_silently_normalize_or_invent_precision(wall):
    with pytest.raises(PredictionValidationError):
        ReportedTime(wall)


def test_quantile_ties_zero_width_negative_values_and_misses():
    definition = QuantileDefinition("units", 2, NumericValueConstraint.WHOLE_NUMBER)
    q = FiveQuantiles.from_values(dict.fromkeys((5, 25, 50, 75, 95), -2), 2)
    for actual, expected in [(-2, 0), (-3, 1), (0, 2)]:
        values = OneShotValues(
            quantiles=q, answer=FixedPrecisionValue.from_value(actual, 2)
        )
        assert (
            one_shot_score(
                one_shot_contract(PredictionType.NUMERIC),
                PredictionStatus.RESOLVED,
                values,
                definition,
            ).wis
            == expected
        )
