"""Read access to supported five-quantile Numeric Predictions.

Mutations and immutable history live in QuantilePredictionRepository. Historical
interval-v1 tables remain migration/storage infrastructure, not a second editor.
"""

from reckonsolve.domain.predictions import NumericPrediction

from .database import Database
from .quantiles import read_prediction as read_quantile_prediction


class NumericPredictionRepository:
    """Load current Numeric detail through the supported-model database gate."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_prediction(self, prediction_id: int) -> NumericPrediction | None:
        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ? AND prediction_type = 'numeric'",
                (prediction_id,),
            ).fetchone()
            return (
                None
                if exists is None
                else read_quantile_prediction(connection, prediction_id)
            )

    def get_latest_prediction(self) -> NumericPrediction | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """SELECT id FROM predictions WHERE prediction_type = 'numeric'
                ORDER BY created_at DESC, id DESC LIMIT 1"""
            ).fetchone()
            return (
                None
                if row is None
                else read_quantile_prediction(connection, int(row[0]))
            )
