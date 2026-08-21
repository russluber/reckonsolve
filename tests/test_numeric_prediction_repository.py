import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.numeric_predictions import NumericPredictionRepository
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    NewNumericForecastRevision,
    NewNumericPrediction,
    PredictionStatus,
)

CREATED_AT = datetime(2026, 8, 20, 19, 30, 45, 123456, tzinfo=UTC)


def numeric_prediction() -> NewNumericPrediction:
    decimal_places = 6
    return NewNumericPrediction(
        question="How many days will the response take?",
        unit="days",
        decimal_places=decimal_places,
        initial_revision=NewNumericForecastRevision(
            lower_bound=FixedPrecisionValue.from_value("-12.345600", decimal_places),
            median_estimate=FixedPrecisionValue.from_value("0.000001", decimal_places),
            upper_bound=FixedPrecisionValue.from_value("987.654321", decimal_places),
            confidence_percent=99,
            rationale="Initial interval",
        ),
    )


def test_numeric_prediction_and_revision_round_trip_exactly_after_restart(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    repository = NumericPredictionRepository(database)

    created = repository.create_prediction(numeric_prediction(), CREATED_AT)

    assert created.status is PredictionStatus.OPEN
    assert created.unit == "days"
    assert created.decimal_places == 6
    assert str(created.current_revision.lower_bound) == "-12.345600"
    assert str(created.current_revision.median_estimate) == "0.000001"
    assert str(created.current_revision.upper_bound) == "987.654321"
    assert created.current_revision.confidence_percent == 99
    assert created.current_revision.rationale == "Initial interval"
    assert repository.list_forecast_revisions(created.prediction_id) == (
        created.current_revision,
    )
    database.close()

    reopened_database = Database.open(path)
    reopened = NumericPredictionRepository(reopened_database).get_prediction(
        created.prediction_id
    )

    assert reopened == created
    reopened_database.close()


def test_numeric_creation_rolls_back_parent_when_first_revision_fails(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    repository = NumericPredictionRepository(database)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER test_reject_numeric_revision
            BEFORE INSERT ON numeric_forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'forced numeric revision failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced numeric revision failure"):
        repository.create_prediction(numeric_prediction(), CREATED_AT)

    with database.transaction() as connection:
        prediction_count = connection.execute(
            "SELECT COUNT(*) FROM predictions WHERE prediction_type = 'numeric'"
        ).fetchone()[0]
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM numeric_forecast_revisions"
        ).fetchone()[0]
    assert prediction_count == 0
    assert revision_count == 0
    database.close()


def test_numeric_repository_does_not_treat_a_binary_prediction_as_numeric(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO predictions (
                question,
                prediction_type,
                status,
                created_at,
                updated_at
            )
            VALUES (
                'Will this remain binary?',
                'binary',
                'open',
                '2026-08-20T19:30:45.123456Z',
                '2026-08-20T19:30:45.123456Z'
            )
            """
        )
        prediction_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id,
                probability_percent,
                created_at,
                sequence,
                rationale
            )
            VALUES (?, 60, '2026-08-20T19:30:45.123456Z', 1, NULL)
            """,
            (prediction_id,),
        )

    repository = NumericPredictionRepository(database)

    assert repository.get_prediction(prediction_id) is None
    assert repository.list_forecast_revisions(prediction_id) is None
    database.close()
