"""One-Shot scoring has one effective forecast and answer, with no time inputs."""

from fractions import Fraction

from reckonsolve.domain.forecast_contracts import ForecastCohort, ForecastContract
from reckonsolve.domain.one_shot import OneShotValues
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.domain.quantiles import QuantileDefinition

from .quantiles import WISScore, weighted_interval_score
from .scoring import exact_brier_score


def one_shot_score(
    contract: ForecastContract,
    status: PredictionStatus,
    values: OneShotValues,
    definition: QuantileDefinition | None = None,
) -> Fraction | WISScore | None:
    """Return one exact score, or none for an unanswered/Invalid Prediction."""
    values.validate_contract(contract, definition)
    if not isinstance(status, PredictionStatus):
        raise TypeError("A recognized Prediction status is required.")
    if status is not PredictionStatus.RESOLVED or values.answer is None:
        return None
    if contract.cohort is ForecastCohort.ONE_SHOT_BINARY:
        return exact_brier_score(values.probability_percent, values.answer)
    return weighted_interval_score(definition, values.quantiles, values.answer)
