"""Purpose-specific SQLite access for binary predictions."""

import sqlite3
from datetime import datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.predictions import (
    NewPrediction,
    PredictionDetail,
    PredictionStatus,
)

from .database import Database


class PredictionRepository:
    """Persist and query predictions without exposing table-level CRUD."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_prediction(
        self,
        new_prediction: NewPrediction,
        created_at: datetime,
    ) -> PredictionDetail:
        """Insert a prediction and sequence-one revision in one transaction."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            prediction_cursor = connection.execute(
                """
                INSERT INTO predictions (
                    question,
                    prediction_type,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, 'binary', ?, ?, ?)
                """,
                (
                    new_prediction.question,
                    PredictionStatus.OPEN.value,
                    timestamp,
                    timestamp,
                ),
            )
            prediction_id = prediction_cursor.lastrowid
            if prediction_id is None:
                raise sqlite3.DatabaseError("SQLite did not return a prediction ID.")

            connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id,
                    probability_percent,
                    created_at,
                    sequence
                )
                VALUES (?, ?, ?, 1)
                """,
                (
                    prediction_id,
                    new_prediction.probability_percent,
                    timestamp,
                ),
            )
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                raise sqlite3.DatabaseError(
                    "The created prediction could not be loaded."
                )
            detail = _map_prediction_detail(row)

        return detail

    def get_latest_prediction(self) -> PredictionDetail | None:
        """Load the newest prediction and derive its current revision."""

        with self._database.transaction() as connection:
            row = connection.execute(
                f"""
                {_PREDICTION_DETAIL_SELECT}
                ORDER BY prediction.created_at DESC, prediction.id DESC
                LIMIT 1
                """
            ).fetchone()

        return None if row is None else _map_prediction_detail(row)


_PREDICTION_DETAIL_SELECT = """
SELECT
    prediction.id AS prediction_id,
    prediction.question,
    prediction.status,
    prediction.created_at,
    current_revision.probability_percent
FROM predictions AS prediction
JOIN forecast_revisions AS current_revision
    ON current_revision.id = (
        SELECT candidate.id
        FROM forecast_revisions AS candidate
        WHERE candidate.prediction_id = prediction.id
        ORDER BY candidate.sequence DESC
        LIMIT 1
    )
"""


def _select_prediction_detail(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        {_PREDICTION_DETAIL_SELECT}
        WHERE prediction.id = ?
        """,
        (prediction_id,),
    ).fetchone()


def _map_prediction_detail(row: sqlite3.Row) -> PredictionDetail:
    status = PredictionStatus(row["status"])
    return PredictionDetail(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        probability_percent=int(row["probability_percent"]),
        status=status,
        created_at=parse_utc(str(row["created_at"])),
    )
