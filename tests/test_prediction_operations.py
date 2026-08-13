import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.errors import ApplicationError, ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import format_utc
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import PredictionStatus


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class CountingClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.instant


NOW = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)


def test_create_prediction_persists_initial_revision_and_returns_detail(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))

    detail = operations.create_prediction("  Will the test pass?  ", 37)

    assert detail.prediction_id > 0
    assert detail.question == "Will the test pass?"
    assert detail.probability_percent == 37
    assert detail.status is PredictionStatus.OPEN
    assert detail.created_at == NOW
    with database.transaction() as connection:
        prediction = connection.execute(
            """
            SELECT question, prediction_type, status, created_at, updated_at
            FROM predictions
            """
        ).fetchone()
        revision = connection.execute(
            """
            SELECT prediction_id, probability_percent, sequence, created_at
            FROM forecast_revisions
            """
        ).fetchone()
        prediction_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(predictions)").fetchall()
        }

    assert tuple(prediction) == (
        "Will the test pass?",
        "binary",
        "open",
        "2026-08-12T19:30:00.000000Z",
        "2026-08-12T19:30:00.000000Z",
    )
    assert tuple(revision) == (
        detail.prediction_id,
        37,
        1,
        "2026-08-12T19:30:00.000000Z",
    )
    assert "probability_percent" not in prediction_columns
    database.close()


def test_creation_reads_clock_once_for_all_initial_timestamps(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    clock = CountingClock(NOW)

    PredictionOperations(database, clock).create_prediction("One instant?", 50)

    assert clock.calls == 1
    database.close()


def test_nonzero_microseconds_persist_and_reopen(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    instant = datetime(2026, 8, 12, 23, 59, 59, 999999, tzinfo=UTC)
    first_database = Database.open(database_path)

    created = PredictionOperations(
        first_database, FixedClock(instant)
    ).create_prediction(
        "Are precise instants reopenable?",
        50,
    )
    first_database.close()
    second_database = Database.open(database_path)
    loaded = PredictionOperations(
        second_database, FixedClock(NOW)
    ).get_latest_prediction()

    assert created.created_at == instant
    assert loaded == created
    second_database.close()


@pytest.mark.parametrize("probability", [0, 100])
def test_create_prediction_persists_absolute_probability_endpoints(
    tmp_path,
    probability: int,
) -> None:
    database = Database.open(tmp_path / f"{probability}.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))

    assert (
        operations.create_prediction(
            "Endpoint forecast?", probability
        ).probability_percent
        == probability
    )
    database.close()


def test_validation_errors_are_expected_application_errors_and_write_nothing(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))

    with pytest.raises(ApplicationError) as error_info:
        operations.create_prediction("   ", 50)

    assert isinstance(error_info.value, ValidationError)
    assert error_info.value.field == "question"
    with database.transaction() as connection:
        prediction_count = connection.execute(
            "SELECT COUNT(*) FROM predictions"
        ).fetchone()[0]
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM forecast_revisions"
        ).fetchone()[0]
    assert (prediction_count, revision_count) == (0, 0)
    database.close()


def test_nul_question_is_an_expected_application_error(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))

    with pytest.raises(ValidationError) as error_info:
        operations.create_prediction("Will this\x00 persist?", 50)

    assert error_info.value.field == "question"
    database.close()


def test_initial_revision_failure_rolls_back_prediction(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_initial_revision_failure
            BEFORE INSERT ON forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'forced test failure');
            END
            """
        )
    operations = PredictionOperations(database, FixedClock(NOW))

    with pytest.raises(sqlite3.IntegrityError, match="forced test failure"):
        operations.create_prediction("Will roll back?", 60)

    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions),
                (SELECT COUNT(*) FROM forecast_revisions)
            """
        ).fetchone()
    assert tuple(counts) == (0, 0)
    database.close()


def test_latest_prediction_is_none_for_an_empty_database(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    assert (
        PredictionOperations(database, FixedClock(NOW)).get_latest_prediction() is None
    )
    database.close()


def test_prediction_and_current_revision_survive_reopen(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(database_path)
    created = PredictionOperations(first_database, FixedClock(NOW)).create_prediction(
        "Will it survive restart?",
        60,
    )
    first_database.close()

    second_database = Database.open(database_path)
    loaded = PredictionOperations(
        second_database, FixedClock(NOW)
    ).get_latest_prediction()

    assert loaded == created
    second_database.close()


def test_creating_another_prediction_preserves_both_histories(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    first_instant = NOW - timedelta(hours=1)
    first = PredictionOperations(
        database,
        FixedClock(first_instant),
    ).create_prediction("Will the first prediction remain?", 25)
    second = PredictionOperations(database, FixedClock(NOW)).create_prediction(
        "Will the newest prediction be displayed?",
        75,
    )

    latest = PredictionOperations(database, FixedClock(NOW)).get_latest_prediction()
    with database.transaction() as connection:
        predictions = connection.execute(
            "SELECT id, question FROM predictions ORDER BY id"
        ).fetchall()
        revisions = connection.execute(
            """
            SELECT prediction_id, probability_percent, sequence
            FROM forecast_revisions
            ORDER BY prediction_id
            """
        ).fetchall()

    assert latest == second
    assert [tuple(row) for row in predictions] == [
        (first.prediction_id, first.question),
        (second.prediction_id, second.question),
    ]
    assert [tuple(row) for row in revisions] == [
        (first.prediction_id, 25, 1),
        (second.prediction_id, 75, 1),
    ]
    database.close()


def test_current_probability_is_derived_from_latest_revision_sequence(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))
    created = operations.create_prediction("Will belief change?", 40)
    deliberately_earlier = NOW - timedelta(days=1)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, ?, ?, ?)
            """,
            (
                created.prediction_id,
                65,
                format_utc(deliberately_earlier),
                2,
            ),
        )

    loaded = operations.get_latest_prediction()

    assert loaded is not None
    assert loaded.probability_percent == 65
    database.close()
