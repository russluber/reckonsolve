import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from reckonsolve.application.errors import PredictionNotFoundError, ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import PredictionStatus


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 20, 19, 30, 45, 123456, tzinfo=UTC)


def test_create_numeric_prediction_persists_complete_initial_state_atomically(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)

    created = operations.create_numeric_prediction(
        "  How many days will the response take?  ",
        "  days  ",
        2,
        "-3.25",
        "7",
        "21.50",
        80,
        rationale="  Initial evidence  ",
        background="  Waiting on a written offer.  ",
        resolution_criteria="  Count complete calendar days.  ",
        forecast_deadline=date(2026, 8, 20),
        expected_resolution=date(2026, 9, 5),
        tags=("Work", "Timing", "work"),
    )

    assert created.question == "How many days will the response take?"
    assert created.unit == "days"
    assert created.decimal_places == 2
    assert created.status is PredictionStatus.OPEN
    assert str(created.current_revision.lower_bound) == "-3.25"
    assert str(created.current_revision.median_estimate) == "7.00"
    assert str(created.current_revision.upper_bound) == "21.50"
    assert created.current_revision.confidence_percent == 80
    assert created.current_revision.rationale == "Initial evidence"
    assert created.background == "Waiting on a written offer."
    assert created.resolution_criteria == "Count complete calendar days."
    assert created.forecast_deadline == date(2026, 8, 20)
    assert created.expected_resolution == date(2026, 9, 5)
    assert created.tags == ("Timing", "Work")

    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions WHERE prediction_type = 'numeric'),
                (SELECT COUNT(*) FROM numeric_forecast_revisions),
                (SELECT COUNT(*) FROM prediction_tags)
            """
        ).fetchone()
    assert tuple(counts) == (1, 1, 2)
    database.close()


def test_numeric_prediction_round_trips_through_restart_with_metadata_and_tags(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    created = PredictionOperations(
        first_database, FixedClock(NOW), UTC
    ).create_numeric_prediction(
        "How much will it cost?",
        "USD",
        2,
        "0.01",
        "50.00",
        "125.75",
        95,
        background="Quote pending.",
        tags=("Budget",),
    )
    first_database.close()

    reopened_database = Database.open(path)
    reopened_operations = PredictionOperations(reopened_database, FixedClock(NOW), UTC)

    assert reopened_operations.get_numeric_prediction(created.prediction_id) == created
    assert reopened_operations.get_latest_numeric_prediction() == created
    reopened_database.close()


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("unit", {"unit": " "}),
        ("lower_bound", {"lower_bound": "1.001"}),
        ("interval", {"lower_bound": "4", "median_estimate": "3"}),
        ("confidence_percent", {"confidence_percent": 100}),
    ],
)
def test_numeric_creation_surfaces_expected_validation_errors_without_writes(
    tmp_path,
    field: str,
    kwargs: dict[str, object],
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    values: dict[str, object] = {
        "question": "How many?",
        "unit": "days",
        "decimal_places": 2,
        "lower_bound": "1.00",
        "median_estimate": "2.00",
        "upper_bound": "3.00",
        "confidence_percent": 80,
    }
    values.update(kwargs)

    with pytest.raises(ValidationError) as error_info:
        operations.create_numeric_prediction(**values)  # type: ignore[arg-type]

    assert error_info.value.field == field
    with database.transaction() as connection:
        count = connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert count == 0
    database.close()


def test_numeric_creation_rejects_an_initial_deadline_that_has_already_passed(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)

    with pytest.raises(ValidationError) as error_info:
        operations.create_numeric_prediction(
            "How many?",
            "days",
            0,
            1,
            2,
            3,
            80,
            forecast_deadline=(NOW - timedelta(days=1)).date(),
        )

    assert error_info.value.field == "forecast_deadline"
    database.close()


def test_numeric_creation_rolls_back_metadata_and_tags_with_a_failed_initial_revision(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_numeric_creation_rollback
            BEFORE INSERT ON numeric_forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'forced numeric creation failure');
            END
            """
        )
    operations = PredictionOperations(database, FixedClock(NOW), UTC)

    with pytest.raises(sqlite3.IntegrityError, match="forced numeric creation failure"):
        operations.create_numeric_prediction(
            "How many?",
            "days",
            0,
            1,
            2,
            3,
            80,
            background="Must roll back.",
            tags=("Rollback",),
        )

    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions),
                (SELECT COUNT(*) FROM numeric_forecast_revisions),
                (SELECT COUNT(*) FROM prediction_tags),
                (SELECT COUNT(*) FROM tags)
            """
        ).fetchone()
    assert tuple(counts) == (0, 0, 0, 0)
    database.close()


def test_numeric_read_does_not_treat_a_binary_prediction_as_numeric(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    binary = operations.create_prediction("Will this stay binary?", 60)

    with pytest.raises(PredictionNotFoundError):
        operations.get_numeric_prediction(binary.prediction_id)
    assert operations.get_latest_numeric_prediction() is None
    database.close()
