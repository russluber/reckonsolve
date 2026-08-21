"""Purpose-specific SQLite access for the M13 numeric foundation."""

import sqlite3
from datetime import date, datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    NewNumericPrediction,
    NumericForecastRevision,
    NumericPrediction,
    PredictionStatus,
)

from .database import Database
from .predictions import replace_tags, select_tags


class NumericPredictionRepository:
    """Persist and read Numeric Prediction creation state and intervals."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_prediction(
        self,
        new_prediction: NewNumericPrediction,
        created_at: datetime,
    ) -> NumericPrediction:
        """Insert a numeric Prediction and its first revision atomically."""

        timestamp = format_utc(created_at)
        revision = new_prediction.initial_revision
        with self._database.transaction() as connection:
            prediction_cursor = connection.execute(
                """
                INSERT INTO predictions (
                    question,
                    prediction_type,
                    status,
                    created_at,
                    updated_at,
                    numeric_unit,
                    numeric_precision,
                    background,
                    resolution_criteria,
                    forecast_deadline,
                    expected_resolution
                )
                VALUES (?, 'numeric', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_prediction.question,
                    PredictionStatus.OPEN.value,
                    timestamp,
                    timestamp,
                    new_prediction.unit,
                    new_prediction.decimal_places,
                    new_prediction.background,
                    new_prediction.resolution_criteria,
                    _format_date(new_prediction.forecast_deadline),
                    _format_date(new_prediction.expected_resolution),
                ),
            )
            prediction_id = prediction_cursor.lastrowid
            if prediction_id is None:
                raise sqlite3.DatabaseError("SQLite did not return a prediction ID.")
            replace_tags(connection, prediction_id, new_prediction.tags)

            revision_cursor = connection.execute(
                """
                INSERT INTO numeric_forecast_revisions (
                    prediction_id,
                    lower_scaled,
                    median_scaled,
                    upper_scaled,
                    confidence_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    prediction_id,
                    revision.lower_bound.scaled_value,
                    revision.median_estimate.scaled_value,
                    revision.upper_bound.scaled_value,
                    revision.confidence_percent,
                    timestamp,
                    revision.rationale,
                ),
            )
            if revision_cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a revision ID.")

            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                raise sqlite3.DatabaseError(
                    "The created numeric prediction could not be loaded."
                )
            created = _map_numeric_prediction(
                row,
                select_tags(connection, prediction_id),
            )

        return created

    def get_prediction(self, prediction_id: int) -> NumericPrediction | None:
        """Load one numeric Prediction and its current revision."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            tags = () if row is None else select_tags(connection, prediction_id)
        return None if row is None else _map_numeric_prediction(row, tags)

    def get_latest_prediction(self) -> NumericPrediction | None:
        """Load the newest numeric Prediction and its current revision."""

        with self._database.transaction() as connection:
            prediction_row = connection.execute(
                """
                SELECT id
                FROM predictions
                WHERE prediction_type = 'numeric'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            row = (
                None
                if prediction_row is None
                else _select_numeric_prediction(connection, int(prediction_row["id"]))
            )
            tags = (
                ()
                if row is None
                else select_tags(connection, int(row["prediction_id"]))
            )
        return None if row is None else _map_numeric_prediction(row, tags)

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[NumericForecastRevision, ...] | None:
        """Load numeric revisions in immutable sequence order."""

        with self._database.transaction() as connection:
            prediction_row = connection.execute(
                """
                SELECT numeric_precision
                FROM predictions
                WHERE id = ? AND prediction_type = 'numeric'
                """,
                (prediction_id,),
            ).fetchone()
            if prediction_row is None:
                return None
            decimal_places = int(prediction_row["numeric_precision"])
            rows = connection.execute(
                """
                SELECT
                    id AS revision_id,
                    prediction_id,
                    lower_scaled,
                    median_scaled,
                    upper_scaled,
                    confidence_percent,
                    sequence,
                    created_at AS revision_created_at,
                    rationale
                FROM numeric_forecast_revisions
                WHERE prediction_id = ?
                ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_numeric_revision(row, decimal_places) for row in rows)


_NUMERIC_PREDICTION_SELECT = """
SELECT
    prediction.id AS prediction_id,
    prediction.question,
    prediction.status,
    prediction.created_at,
    prediction.updated_at,
    prediction.numeric_unit,
    prediction.numeric_precision,
    prediction.metadata_version,
    prediction.background,
    prediction.resolution_criteria,
    prediction.forecast_deadline,
    prediction.expected_resolution,
    current_revision.id AS revision_id,
    current_revision.lower_scaled,
    current_revision.median_scaled,
    current_revision.upper_scaled,
    current_revision.confidence_percent,
    current_revision.sequence,
    current_revision.created_at AS revision_created_at,
    current_revision.rationale
FROM predictions AS prediction
JOIN numeric_forecast_revisions AS current_revision
    ON current_revision.id = (
        SELECT candidate.id
        FROM numeric_forecast_revisions AS candidate
        WHERE candidate.prediction_id = prediction.id
        ORDER BY candidate.sequence DESC
        LIMIT 1
    )
WHERE prediction.id = ? AND prediction.prediction_type = 'numeric'
"""


def _select_numeric_prediction(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        _NUMERIC_PREDICTION_SELECT,
        (prediction_id,),
    ).fetchone()


def _map_numeric_prediction(
    row: sqlite3.Row,
    tags: tuple[str, ...] = (),
) -> NumericPrediction:
    decimal_places = int(row["numeric_precision"])
    return NumericPrediction(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        unit=str(row["numeric_unit"]),
        decimal_places=decimal_places,
        status=PredictionStatus(row["status"]),
        created_at=parse_utc(str(row["created_at"])),
        updated_at=parse_utc(str(row["updated_at"])),
        current_revision=_map_numeric_revision(row, decimal_places),
        background=_optional_string(row["background"]),
        resolution_criteria=_optional_string(row["resolution_criteria"]),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        expected_resolution=_parse_date(row["expected_resolution"]),
        tags=tags,
        metadata_version=int(row["metadata_version"]),
    )


def _map_numeric_revision(
    row: sqlite3.Row,
    decimal_places: int,
) -> NumericForecastRevision:
    return NumericForecastRevision(
        revision_id=int(row["revision_id"]),
        prediction_id=int(row["prediction_id"]),
        lower_bound=FixedPrecisionValue(
            int(row["lower_scaled"]),
            decimal_places,
        ),
        median_estimate=FixedPrecisionValue(
            int(row["median_scaled"]),
            decimal_places,
        ),
        upper_bound=FixedPrecisionValue(
            int(row["upper_scaled"]),
            decimal_places,
        ),
        confidence_percent=int(row["confidence_percent"]),
        sequence=int(row["sequence"]),
        created_at=parse_utc(str(row["revision_created_at"])),
        rationale=None if row["rationale"] is None else str(row["rationale"]),
    )


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
