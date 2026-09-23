import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.numeric_predictions import NumericPredictionRepository
from reckonsolve.data.quantiles import QuantilePredictionRepository
from reckonsolve.domain.forecast_contracts import ForecastDeadline
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NewQuantilePrediction,
    NumericValueConstraint,
    QuantileDefinition,
)

CREATED_AT = datetime(2026, 8, 20, 19, 30, 45, 123456, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> datetime:
        return CREATED_AT


def numeric_prediction() -> NewQuantilePrediction:
    return NewQuantilePrediction(
        question="How many days will the response take?",
        definition=QuantileDefinition("days", 6, NumericValueConstraint.CONTINUOUS),
        quantiles=FiveQuantiles.from_values(
            {
                5: "-12.345600",
                25: "-1.000001",
                50: "0.000001",
                75: "10.123456",
                95: "987.654321",
            },
            6,
        ),
        forecast_deadline=ForecastDeadline(CREATED_AT + timedelta(days=30)),
        rationale="Initial quantiles",
    )


def test_numeric_prediction_and_revision_round_trip_exactly_after_restart(tmp_path):
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    repository = QuantilePredictionRepository(database, FixedClock())
    created = repository.create_detail(numeric_prediction())
    assert created.status is PredictionStatus.OPEN
    assert created.unit == "days"
    assert created.decimal_places == 6
    assert tuple(map(str, created.current_revision.quantiles.values)) == (
        "-12.345600",
        "-1.000001",
        "0.000001",
        "10.123456",
        "987.654321",
    )
    assert created.current_revision.rationale == "Initial quantiles"
    assert repository.list_revisions(created.prediction_id) == (
        created.current_revision,
    )
    database.close()

    reopened_database = Database.open(path)
    assert (
        NumericPredictionRepository(reopened_database).get_prediction(
            created.prediction_id
        )
        == created
    )
    reopened_database.close()


def test_numeric_creation_rolls_back_parent_when_first_revision_fails(tmp_path):
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    repository = QuantilePredictionRepository(database, FixedClock())
    with database.transaction() as connection:
        connection.execute("""
            CREATE TRIGGER test_reject_numeric_revision
            BEFORE INSERT ON numeric_quantile_revisions
            BEGIN SELECT RAISE(ABORT, 'forced numeric revision failure'); END
        """)
    with pytest.raises(sqlite3.IntegrityError, match="forced numeric revision failure"):
        repository.create_detail(numeric_prediction())
    with database.transaction() as connection:
        for table in (
            "predictions",
            "prediction_forecast_contracts",
            "numeric_quantile_definitions",
            "numeric_quantile_revisions",
        ):
            assert (
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
            )
    database.close()


def test_numeric_repository_does_not_treat_a_binary_prediction_as_numeric(tmp_path):
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    binary = PredictionOperations(database, FixedClock()).create_prediction(
        "Will this remain binary?", 60, forecast_deadline=CREATED_AT + timedelta(days=1)
    )
    repository = NumericPredictionRepository(database)
    assert repository.get_prediction(binary.prediction_id) is None
    assert repository.get_latest_prediction() is None
    database.close()
