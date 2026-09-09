from datetime import UTC, datetime, timedelta, timezone

import pytest

from reckonsolve.domain.forecast_contracts import (
    EffectiveResolutionTime,
    ForecastCohort,
    ForecastContract,
    ForecastContractValidationError,
    ForecastDeadline,
    ForecastingWindow,
    ForecastModel,
    ResolutionTiming,
    ScoringContract,
    dispatch_forecast_contract,
    legacy_contract,
    prospective_contract,
)
from reckonsolve.domain.predictions import PredictionType

T0 = datetime(2026, 9, 9, 16, tzinfo=UTC)
DEADLINE = ForecastDeadline(T0 + timedelta(days=7))


@pytest.mark.parametrize(
    ("prediction_type", "cohort", "model", "scoring"),
    (
        (
            PredictionType.BINARY,
            ForecastCohort.LEGACY_BINARY,
            ForecastModel.BINARY_FINAL_V1,
            ScoringContract.BINARY_FINAL_BRIER_V1,
        ),
        (
            PredictionType.NUMERIC,
            ForecastCohort.LEGACY_NUMERIC,
            ForecastModel.NUMERIC_INTERVAL_V1,
            ScoringContract.NUMERIC_INTERVAL_SCORE_V1,
        ),
    ),
)
def test_legacy_contracts_are_explicit_and_have_no_exact_deadline(
    prediction_type,
    cohort,
    model,
    scoring,
) -> None:
    contract = legacy_contract(prediction_type)

    assert contract.cohort is cohort
    assert contract.forecast_model is model
    assert contract.scoring_contract is scoring
    assert contract.forecast_deadline is None
    assert contract.is_legacy


def test_prospective_contract_dispatch_uses_durable_identity() -> None:
    contract = prospective_contract(PredictionType.BINARY, DEADLINE)

    assert contract.cohort is ForecastCohort.TRAJECTORY_BINARY
    assert not contract.is_legacy
    assert (
        dispatch_forecast_contract(
            contract,
            legacy_binary="legacy Binary",
            trajectory_binary="trajectory Binary",
            legacy_numeric="legacy Numeric",
            quantile_numeric="quantile Numeric",
        )
        == "trajectory Binary"
    )


def test_unknown_or_crossed_contract_identity_is_rejected() -> None:
    with pytest.raises(
        ForecastContractValidationError,
        match="do not match",
    ):
        ForecastContract(
            PredictionType.BINARY,
            ForecastModel.BINARY_FINAL_V1,
            ScoringContract.NUMERIC_INTERVAL_SCORE_V1,
        )


def test_exact_values_normalize_timezone_aware_instants_to_utc() -> None:
    pacific = timezone(timedelta(hours=-7))
    deadline = ForecastDeadline(datetime(2026, 9, 9, 10, 30, tzinfo=pacific))
    effective = EffectiveResolutionTime(datetime(2026, 9, 9, 9, 45, tzinfo=pacific))

    assert deadline.instant == datetime(2026, 9, 9, 17, 30, tzinfo=UTC)
    assert effective.instant == datetime(2026, 9, 9, 16, 45, tzinfo=UTC)

    with pytest.raises(ForecastContractValidationError, match="time zone"):
        ForecastDeadline(T0.replace(tzinfo=None))


def test_forecasting_window_requires_deadline_strictly_after_initial_commit() -> None:
    with pytest.raises(ForecastContractValidationError, match="later"):
        ForecastingWindow(T0, ForecastDeadline(T0))


def test_revision_time_must_advance_and_remain_before_deadline() -> None:
    window = ForecastingWindow(T0, DEADLINE)
    previous = T0 + timedelta(hours=2)

    assert window.validate_revision(
        previous_revision_at=previous,
        proposed_revision_at=previous + timedelta(microseconds=1),
    ) == previous + timedelta(microseconds=1)

    with pytest.raises(ForecastContractValidationError, match="clock must advance"):
        window.validate_revision(
            previous_revision_at=previous,
            proposed_revision_at=previous,
        )
    with pytest.raises(ForecastContractValidationError, match="before"):
        window.validate_revision(
            previous_revision_at=previous,
            proposed_revision_at=DEADLINE.instant,
        )


def test_resolution_timing_and_cutoff_preserve_effective_and_recorded_instants() -> (
    None
):
    window = ForecastingWindow(T0, DEADLINE)
    early = EffectiveResolutionTime(T0 + timedelta(days=2))
    late = EffectiveResolutionTime(T0 + timedelta(days=9))

    timing = ResolutionTiming(early, T0 + timedelta(days=3))
    assert timing.effective is early
    assert window.scoring_cutoff(early) == early.instant
    assert window.scoring_cutoff(late) == DEADLINE.instant

    with pytest.raises(ForecastContractValidationError, match="later than recorded"):
        ResolutionTiming(late, T0 + timedelta(days=8))
