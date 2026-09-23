"""Small exact-contract fixtures shared by persistence invariant tests."""

from datetime import UTC, datetime, timedelta

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import parse_utc
from reckonsolve.data.forecast_contracts import insert_prospective_contract
from reckonsolve.domain.forecast_contracts import ForecastDeadline, prospective_contract
from reckonsolve.domain.predictions import PredictionType
from reckonsolve.domain.quantiles import NumericValueConstraint


def create_binary(
    operations: PredictionOperations, question: str, probability: int, **metadata
):
    """A current-model fixture with an explicit distant commitment.

    Use only for tests of shared archive/history behavior, not Deadline validation.
    Tests of clock boundaries must provide their own exact Deadline.
    """
    metadata.setdefault("forecast_deadline", datetime(2099, 1, 1, tzinfo=UTC))
    return operations.create_prediction(question, probability, **metadata)


def create_numeric(
    operations: PredictionOperations,
    question: str,
    unit: str,
    precision: int,
    quantiles: dict[int, object],
    **metadata,
):
    """An explicitly elicited five-quantile fixture for shared behavior tests."""
    metadata.setdefault("forecast_deadline", datetime(2099, 1, 1, tzinfo=UTC))
    metadata.setdefault("value_constraint", NumericValueConstraint.CONTINUOUS)
    return operations.create_numeric_prediction(
        question, unit, precision, quantiles, **metadata
    )


def insert_binary_contract(connection, prediction_id, initial_timestamp):
    insert_prospective_contract(
        connection,
        prediction_id,
        prospective_contract(
            PredictionType.BINARY,
            ForecastDeadline(parse_utc(initial_timestamp) + timedelta(days=30)),
        ),
    )
