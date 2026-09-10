"""Prospective forecast-model identities and exact-time rules."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from .predictions import PredictionStatus, PredictionType, display_status


class ForecastContractValidationError(ValueError):
    """Raised when a model identity or exact forecasting instant is invalid."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class ForecastModel(StrEnum):
    """Immutable forecast representation selected when a Prediction is created."""

    BINARY_FINAL_V1 = "binary-final-v1"
    BINARY_TRAJECTORY_V1 = "binary-trajectory-v1"
    NUMERIC_INTERVAL_V1 = "numeric-interval-v1"
    NUMERIC_QUANTILES_5_V2 = "numeric-quantiles-5-v2"


class ScoringContract(StrEnum):
    """Immutable scoring semantics paired with one forecast model."""

    BINARY_FINAL_BRIER_V1 = "binary-final-brier-v1"
    BINARY_TRAJECTORY_BRIER_V1 = "binary-trajectory-brier-v1"
    NUMERIC_INTERVAL_SCORE_V1 = "numeric-interval-score-v1"
    NUMERIC_WIS_V1 = "numeric-wis-v1"


class ForecastCohort(StrEnum):
    """Closed dispatch set for legacy and prospective forecast behavior."""

    LEGACY_BINARY = "legacy-binary"
    TRAJECTORY_BINARY = "trajectory-binary"
    LEGACY_NUMERIC = "legacy-numeric"
    QUANTILE_NUMERIC = "quantile-numeric"


_CONTRACTS = {
    ForecastCohort.LEGACY_BINARY: (
        PredictionType.BINARY,
        ForecastModel.BINARY_FINAL_V1,
        ScoringContract.BINARY_FINAL_BRIER_V1,
        False,
    ),
    ForecastCohort.TRAJECTORY_BINARY: (
        PredictionType.BINARY,
        ForecastModel.BINARY_TRAJECTORY_V1,
        ScoringContract.BINARY_TRAJECTORY_BRIER_V1,
        True,
    ),
    ForecastCohort.LEGACY_NUMERIC: (
        PredictionType.NUMERIC,
        ForecastModel.NUMERIC_INTERVAL_V1,
        ScoringContract.NUMERIC_INTERVAL_SCORE_V1,
        False,
    ),
    ForecastCohort.QUANTILE_NUMERIC: (
        PredictionType.NUMERIC,
        ForecastModel.NUMERIC_QUANTILES_5_V2,
        ScoringContract.NUMERIC_WIS_V1,
        True,
    ),
}


@dataclass(frozen=True, slots=True)
class ForecastContract:
    """One validated, immutable forecast-model and scoring-contract pairing."""

    prediction_type: PredictionType
    forecast_model: ForecastModel
    scoring_contract: ScoringContract
    forecast_deadline: "ForecastDeadline | None" = None

    def __post_init__(self) -> None:
        if not isinstance(self.prediction_type, PredictionType):
            raise ForecastContractValidationError(
                "Prediction type is not recognized.", field="prediction_type"
            )
        if not isinstance(self.forecast_model, ForecastModel):
            raise ForecastContractValidationError(
                "Forecast model identity is not recognized.", field="forecast_model"
            )
        if not isinstance(self.scoring_contract, ScoringContract):
            raise ForecastContractValidationError(
                "Scoring contract identity is not recognized.",
                field="scoring_contract",
            )
        if self.forecast_deadline is not None and not isinstance(
            self.forecast_deadline, ForecastDeadline
        ):
            raise ForecastContractValidationError(
                "Forecast Deadline is not an exact deadline value.",
                field="forecast_deadline",
            )

        _, _, _, requires_deadline = _CONTRACTS[self.cohort]
        if requires_deadline and self.forecast_deadline is None:
            raise ForecastContractValidationError(
                "This forecast model requires an exact Forecast Deadline.",
                field="forecast_deadline",
            )
        if not requires_deadline and self.forecast_deadline is not None:
            raise ForecastContractValidationError(
                "Legacy forecast models do not have a prospective exact Deadline.",
                field="forecast_deadline",
            )

    @property
    def cohort(self) -> ForecastCohort:
        """Return the only behavior cohort matching all stored identities."""

        for cohort, values in _CONTRACTS.items():
            prediction_type, forecast_model, scoring_contract, _ = values
            if (
                prediction_type is self.prediction_type
                and forecast_model is self.forecast_model
                and scoring_contract is self.scoring_contract
            ):
                return cohort
        raise ForecastContractValidationError(
            "Forecast model and scoring contract identities do not match.",
            field="scoring_contract",
        )

    @property
    def is_legacy(self) -> bool:
        return self.cohort in {
            ForecastCohort.LEGACY_BINARY,
            ForecastCohort.LEGACY_NUMERIC,
        }


def legacy_contract(prediction_type: PredictionType) -> ForecastContract:
    """Return the explicit legacy contract for a creation-era forecast type."""

    if prediction_type is PredictionType.BINARY:
        cohort = ForecastCohort.LEGACY_BINARY
    elif prediction_type is PredictionType.NUMERIC:
        cohort = ForecastCohort.LEGACY_NUMERIC
    else:
        raise ForecastContractValidationError(
            "Prediction type is not recognized.", field="prediction_type"
        )
    stored_type, model, scoring, _ = _CONTRACTS[cohort]
    return ForecastContract(stored_type, model, scoring)


def prospective_contract(
    prediction_type: PredictionType,
    forecast_deadline: "ForecastDeadline",
) -> ForecastContract:
    """Return the approved v0.7 contract for a future complete creation flow."""

    if not isinstance(forecast_deadline, ForecastDeadline):
        raise ForecastContractValidationError(
            "An exact Forecast Deadline is required.", field="forecast_deadline"
        )
    if prediction_type is PredictionType.BINARY:
        cohort = ForecastCohort.TRAJECTORY_BINARY
    elif prediction_type is PredictionType.NUMERIC:
        cohort = ForecastCohort.QUANTILE_NUMERIC
    else:
        raise ForecastContractValidationError(
            "Prediction type is not recognized.", field="prediction_type"
        )
    stored_type, model, scoring, _ = _CONTRACTS[cohort]
    return ForecastContract(stored_type, model, scoring, forecast_deadline)


@dataclass(frozen=True, slots=True)
class ForecastDeadline:
    """One exact, timezone-aware Forecast Deadline normalized to UTC."""

    instant: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instant",
            _exact_utc(self.instant, field="forecast_deadline"),
        )


@dataclass(frozen=True, slots=True)
class EffectiveResolutionTime:
    """The earliest defensible exact resolution instant, normalized to UTC."""

    instant: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instant",
            _exact_utc(self.instant, field="effective_resolution_at"),
        )


@dataclass(frozen=True, slots=True)
class ForecastingWindow:
    """The immutable initial-commit-to-Deadline window for a new model."""

    initial_revision_at: datetime
    deadline: ForecastDeadline

    def __post_init__(self) -> None:
        initial_revision_at = _exact_utc(
            self.initial_revision_at, field="initial_revision_at"
        )
        object.__setattr__(self, "initial_revision_at", initial_revision_at)
        if not isinstance(self.deadline, ForecastDeadline):
            raise ForecastContractValidationError(
                "An exact Forecast Deadline is required.",
                field="forecast_deadline",
            )
        if self.deadline.instant <= initial_revision_at:
            raise ForecastContractValidationError(
                "Forecast Deadline must be later than the initial forecast.",
                field="forecast_deadline",
            )

    def validate_revision(
        self,
        *,
        previous_revision_at: datetime,
        proposed_revision_at: datetime,
    ) -> datetime:
        """Return normalized commit time after enforcing strict ordering and cutoff."""

        previous = _exact_utc(previous_revision_at, field="previous_revision_at")
        proposed = _exact_utc(proposed_revision_at, field="created_at")
        if proposed <= previous:
            raise ForecastContractValidationError(
                "The forecast clock must advance before another revision can be saved.",
                field="created_at",
            )
        if proposed >= self.deadline.instant:
            raise ForecastContractValidationError(
                "Forecast revisions must be saved before the Forecast Deadline.",
                field="forecast_deadline",
            )
        return proposed

    def scoring_cutoff(self, effective_resolution: EffectiveResolutionTime) -> datetime:
        """Derive C = min(R, T) without altering either source instant."""

        if not isinstance(effective_resolution, EffectiveResolutionTime):
            raise ForecastContractValidationError(
                "An exact effective resolution time is required.",
                field="effective_resolution_at",
            )
        return min(effective_resolution.instant, self.deadline.instant)


@dataclass(frozen=True, slots=True)
class ResolutionTiming:
    """Distinct effective and immutable recorded Resolution instants."""

    effective: EffectiveResolutionTime
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.effective, EffectiveResolutionTime):
            raise ForecastContractValidationError(
                "An exact effective resolution time is required.",
                field="effective_resolution_at",
            )
        recorded_at = _exact_utc(self.recorded_at, field="recorded_at")
        object.__setattr__(self, "recorded_at", recorded_at)
        if self.effective.instant > recorded_at:
            raise ForecastContractValidationError(
                "Effective resolution time cannot be later than recorded-at.",
                field="effective_resolution_at",
            )


def dispatch_forecast_contract[T](
    contract: ForecastContract,
    *,
    legacy_binary: T,
    trajectory_binary: T,
    legacy_numeric: T,
    quantile_numeric: T,
) -> T:
    """Select behavior only from an already validated durable model identity."""

    choices = {
        ForecastCohort.LEGACY_BINARY: legacy_binary,
        ForecastCohort.TRAJECTORY_BINARY: trajectory_binary,
        ForecastCohort.LEGACY_NUMERIC: legacy_numeric,
        ForecastCohort.QUANTILE_NUMERIC: quantile_numeric,
    }
    return choices[contract.cohort]


def contract_status(
    status: PredictionStatus,
    legacy_deadline: date | None,
    current_date: date,
    contract: ForecastContract | None,
    now: datetime | None,
) -> PredictionStatus:
    """Apply the stored cohort's cutoff to a nonterminal Prediction."""
    if contract is None or contract.is_legacy:
        return display_status(status, legacy_deadline, current_date)
    if now is None:
        raise ForecastContractValidationError(
            "An exact current time is required.", field="created_at"
        )
    assert contract.forecast_deadline is not None
    if (
        status is PredictionStatus.OPEN
        and _exact_utc(now, field="created_at") >= contract.forecast_deadline.instant
    ):
        return PredictionStatus.LOCKED
    return status


def _exact_utc(value: datetime, *, field: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ForecastContractValidationError(
            "Exact forecast times must include a time zone.", field=field
        )
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as error:
        raise ForecastContractValidationError(
            "Exact forecast time is outside the supported range.", field=field
        ) from error
