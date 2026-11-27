"""Read shared metadata save responses inside the caller's write transaction."""

import sqlite3

from reckonsolve.domain.one_shot import OneShotDetail
from reckonsolve.domain.predictions import (
    NumericPrediction,
    PredictionDetail,
    PredictionType,
)

from .forecast_contracts import select_supported_contract
from .one_shot import OneShotRepository
from .one_shot_facts import read_one_shot
from .predictions import _map_prediction_detail, _select_prediction_detail, select_tags
from .quantiles import read_prediction as read_numeric_prediction


def read_metadata_snapshot(
    connection: sqlite3.Connection, prediction_id: int
) -> PredictionDetail | NumericPrediction | OneShotDetail:
    """Dispatch by stored identity without opening another transaction.

    Keeping this composition outside the individual repositories avoids circular
    dependencies between Binary, Numeric and One-Shot persistence modules.
    """
    contract = select_supported_contract(connection, prediction_id)
    if contract.is_one_shot:
        return OneShotRepository._detail(
            connection, read_one_shot(connection, prediction_id, contract)
        )
    if contract.prediction_type is PredictionType.NUMERIC:
        return read_numeric_prediction(connection, prediction_id)
    row = _select_prediction_detail(connection, prediction_id)
    if row is None:
        raise sqlite3.DatabaseError("The saved Prediction could not be loaded.")
    return _map_prediction_detail(row, select_tags(connection, prediction_id))
