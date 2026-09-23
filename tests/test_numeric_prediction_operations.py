import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from supported_fixtures import create_binary, create_numeric

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

    created = create_numeric(
        operations,
        "  How many days will the response take?  ",
        "  days  ",
        2,
        {5: "-3.25", 25: "2.00", 50: "7", 75: "14.00", 95: "21.50"},
        rationale="  Initial evidence  ",
        background="  Waiting on a written offer.  ",
        resolution_criteria="  Count complete calendar days.  ",
        forecast_deadline=NOW + timedelta(hours=1),
        expected_resolution=date(2026, 9, 5),
        tags=("Work", "Timing", "work"),
    )

    assert created.question == "How many days will the response take?"
    assert created.unit == "days"
    assert created.decimal_places == 2
    assert created.status is PredictionStatus.OPEN
    assert str(created.current_revision.quantiles.q05) == "-3.25"
    assert str(created.current_revision.quantiles.q50) == "7.00"
    assert str(created.current_revision.quantiles.q95) == "21.50"
    assert created.current_revision.rationale == "Initial evidence"
    assert created.background == "Waiting on a written offer."
    assert created.resolution_criteria == "Count complete calendar days."
    assert created.forecast_contract.forecast_deadline.instant == NOW + timedelta(
        hours=1
    )
    assert created.expected_resolution == date(2026, 9, 5)
    assert created.tags == ("Timing", "Work")

    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions WHERE prediction_type = 'numeric'),
                (SELECT COUNT(*) FROM numeric_quantile_revisions),
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
    created = create_numeric(
        PredictionOperations(first_database, FixedClock(NOW), UTC),
        "How much will it cost?",
        "USD",
        2,
        {5: "0.01", 25: "25.00", 50: "50.00", 75: "90.00", 95: "125.75"},
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
        ("q05", {"quantiles": {5: "1.001", 25: 2, 50: 3, 75: 4, 95: 5}}),
        ("quantiles", {"quantiles": {5: 4, 25: 2, 50: 3, 75: 4, 95: 5}}),
        ("quantiles", {"quantiles": {5: 1, 50: 3, 95: 5}}),
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
        "precision": 2,
        "quantiles": {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
    }
    values.update(kwargs)

    with pytest.raises(ValidationError) as error_info:
        create_numeric(operations, **values)  # type: ignore[arg-type]

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
        create_numeric(
            operations,
            "How many?",
            "days",
            0,
            {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
            forecast_deadline=NOW - timedelta(days=1),
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
            BEFORE INSERT ON numeric_quantile_revisions
            BEGIN
                SELECT RAISE(ABORT, 'forced numeric creation failure');
            END
            """
        )
    operations = PredictionOperations(database, FixedClock(NOW), UTC)

    with pytest.raises(sqlite3.IntegrityError, match="forced numeric creation failure"):
        create_numeric(
            operations,
            "How many?",
            "days",
            0,
            {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
            background="Must roll back.",
            tags=("Rollback",),
        )

    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions),
                (SELECT COUNT(*) FROM numeric_quantile_revisions),
                (SELECT COUNT(*) FROM prediction_tags),
                (SELECT COUNT(*) FROM tags)
            """
        ).fetchone()
    assert tuple(counts) == (0, 0, 0, 0)
    database.close()


def test_numeric_read_does_not_treat_a_binary_prediction_as_numeric(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    binary = create_binary(operations, "Will this stay binary?", 60)

    with pytest.raises(PredictionNotFoundError):
        operations.get_numeric_prediction(binary.prediction_id)
    assert operations.get_latest_numeric_prediction() is None
    database.close()
