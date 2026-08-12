import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS


def test_migration_two_upgrades_baseline_and_preserves_existing_data(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    baseline = Database.open(database_path, migrations=MIGRATIONS[:1])
    with baseline.transaction() as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    baseline.close()

    upgraded = Database.open(database_path)

    assert upgraded.schema_version == 2
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT value FROM sentinel").fetchone()[0]
            == "preserved"
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            ).fetchall()
        }
    assert {"predictions", "forecast_revisions"} <= tables
    upgraded.close()


def test_forecast_revision_constraints_protect_integrity(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question?', 'binary', 'open', ?, ?)
            """,
            ("2026-08-12T19:30:00.000000Z", "2026-08-12T19:30:00.000000Z"),
        ).lastrowid

    assert prediction_id is not None
    for invalid_probability in (-1, 101, 37.5):
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as connection,
        ):
            connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id, probability_percent, created_at, sequence
                ) VALUES (?, ?, ?, 1)
                """,
                (
                    prediction_id,
                    invalid_probability,
                    "2026-08-12T19:30:00.000000Z",
                ),
            )

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (999, 50, '2026-08-12T19:30:00.000000Z', 1)
            """
        )

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 50, 'not-a-timeZ', 1)
            """,
            (prediction_id,),
        )
    database.close()


def test_saved_revision_cannot_be_updated_but_parent_deletion_can_cascade(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question?', 'binary', 'open', ?, ?)
            """,
            ("2026-08-12T19:30:00.000000Z", "2026-08-12T19:30:00.000000Z"),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 50, '2026-08-12T19:30:00.000000Z', 1)
            """,
            (prediction_id,),
        )

    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute("UPDATE forecast_revisions SET probability_percent = 70")

    with database.transaction() as connection:
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM forecast_revisions"
        ).fetchone()[0]
    assert revision_count == 0
    database.close()


def test_revision_sequence_is_unique_within_each_prediction(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    timestamp = "2026-08-12T19:30:00.000000Z"
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question?', 'binary', 'open', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 50, ?, 1)
            """,
            (prediction_id, timestamp),
        )

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 60, ?, 1)
            """,
            (prediction_id, timestamp),
        )
    database.close()


@pytest.mark.parametrize(
    "invalid_timestamp",
    [
        "2026-02-30T00:00:00.000000Z",
        "2026-13-01T00:00:00.000000Z",
        "2026-01-00T00:00:00.000000Z",
        "2026-08-12T24:00:00.000000Z",
        "0000-01-01T00:00:00.000000Z",
        "2026-08-12T19:30:00Z",
        "2026-08-12 19:30:00.000000Z",
    ],
)
def test_prediction_timestamp_requires_parseable_canonical_utc(
    tmp_path,
    invalid_timestamp: str,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question?', 'binary', 'open', ?, ?)
            """,
            (invalid_timestamp, invalid_timestamp),
        )

    database.close()
