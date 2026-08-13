import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


def test_migration_three_preserves_v2_prediction_and_revision(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    v2 = Database.open(database_path, migrations=MIGRATIONS[:2])
    timestamp = "2026-08-12T19:30:00.000000Z"
    with v2.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Preserved?', 'binary', 'open', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 60, ?, 1)
            """,
            (prediction_id, timestamp),
        )
    v2.close()

    upgraded = Database.open(database_path, migrations=MIGRATIONS[:3])

    assert upgraded.schema_version == 3
    with upgraded.transaction() as connection:
        row = connection.execute(
            """
            SELECT question, metadata_version, background, resolution_criteria,
                   forecast_deadline, expected_resolution
            FROM predictions
            """
        ).fetchone()
        probability = connection.execute(
            "SELECT probability_percent FROM forecast_revisions"
        ).fetchone()[0]
    assert tuple(row) == ("Preserved?", 1, None, None, None, None)
    assert probability == 60
    upgraded.close()


def test_failing_migration_three_rolls_back_the_entire_v2_upgrade(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    v2 = Database.open(database_path, migrations=MIGRATIONS[:2])
    with v2.transaction() as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL) STRICT")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    v2.close()
    failing_v3 = Migration(
        version=3,
        name=MIGRATIONS[2].name,
        statements=(
            *MIGRATIONS[2].statements,
            "INSERT INTO table_that_does_not_exist DEFAULT VALUES",
        ),
    )

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        Database.open(
            database_path,
            migrations=(*MIGRATIONS[:2], failing_v3),
        )

    reopened_v2 = Database.open(database_path, migrations=MIGRATIONS[:2])
    with reopened_v2.transaction() as connection:
        schema_version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        prediction_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(predictions)")
        }
        sentinel_value = connection.execute("SELECT value FROM sentinel").fetchone()[0]
        v3_table = connection.execute(
            """
            SELECT 1
            FROM sqlite_schema
            WHERE name = 'prediction_definition_changes'
            """
        ).fetchone()

    assert schema_version == 2
    assert "metadata_version" not in prediction_columns
    assert sentinel_value == "preserved"
    assert v3_table is None
    reopened_v2.close()


@pytest.mark.parametrize("invalid_version", [0, -1, 1.5, "two"])
def test_metadata_version_constraint_rejects_invalid_values(
    tmp_path,
    invalid_version,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    timestamp = "2026-08-12T19:30:00.000000Z"

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at,
                metadata_version
            ) VALUES ('Question?', 'binary', 'open', ?, ?, ?)
            """,
            (timestamp, timestamp, invalid_version),
        )
    database.close()


@pytest.mark.parametrize(
    ("column", "invalid_value"),
    [
        ("forecast_deadline", "1752-09-13"),
        ("expected_resolution", "1752-09-13"),
    ],
)
def test_prediction_metadata_dates_fit_the_supported_editor_range(
    tmp_path,
    column: str,
    invalid_value: str,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    timestamp = "2026-08-12T19:30:00.000000Z"

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            f"""
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at, {column}
            ) VALUES ('Question?', 'binary', 'open', ?, ?, ?)
            """,
            (timestamp, timestamp, invalid_value),
        )

    database.close()


@pytest.mark.parametrize("invalid_tag", ["policy,macro", "line\nbreak"])
def test_tag_constraints_match_the_comma_separated_editor(
    tmp_path,
    invalid_tag: str,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            "INSERT INTO tags (display_name, normalized_name) VALUES (?, ?)",
            (invalid_tag, invalid_tag.casefold()),
        )

    database.close()


@pytest.mark.parametrize(
    "bad_values",
    [
        (" ", "Question", None, None, None, None),
        ("Question", "Question", " ", None, None, None),
        ("Question", "Question", None, None, "2026-02-30", None),
    ],
)
def test_definition_history_rejects_noncanonical_snapshots(
    tmp_path,
    bad_values,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    timestamp = "2026-08-12T19:30:00.000000Z"
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question', 'binary', 'open', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO prediction_definition_changes (
                prediction_id, changed_at,
                old_question, new_question,
                old_resolution_criteria, new_resolution_criteria,
                old_forecast_deadline, new_forecast_deadline
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (prediction_id, timestamp, *bad_values),
        )
    database.close()


def test_definition_history_requires_a_real_protected_difference(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    timestamp = "2026-08-12T19:30:00.000000Z"
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Question', 'binary', 'open', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO prediction_definition_changes (
                prediction_id, changed_at,
                old_question, new_question,
                old_resolution_criteria, new_resolution_criteria,
                old_forecast_deadline, new_forecast_deadline
            ) VALUES (?, ?, 'Question', 'Question', NULL, NULL, NULL, NULL)
            """,
            (prediction_id, timestamp),
        )
    database.close()
