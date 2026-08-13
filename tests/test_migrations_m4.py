import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration

TIMESTAMP = "2026-08-12T19:30:00.000000Z"


def _insert_v3_prediction(database: Database) -> tuple[int, int]:
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at,
                background
            ) VALUES ('Preserved?', 'binary', 'open', ?, ?, 'Context')
            """,
            (TIMESTAMP, TIMESTAMP),
        ).lastrowid
        assert prediction_id is not None
        revision_id = connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 60, ?, 1)
            """,
            (prediction_id, TIMESTAMP),
        ).lastrowid
        assert revision_id is not None
    return prediction_id, revision_id


def test_migration_four_preserves_v3_predictions_and_revisions(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    v3 = Database.open(database_path, migrations=MIGRATIONS[:3])
    prediction_id, revision_id = _insert_v3_prediction(v3)
    v3.close()

    upgraded = Database.open(database_path)

    assert upgraded.schema_version == 4
    with upgraded.transaction() as connection:
        prediction = connection.execute(
            "SELECT question, background, metadata_version FROM predictions"
        ).fetchone()
        revision = connection.execute(
            """
            SELECT id, prediction_id, probability_percent, sequence, rationale
            FROM forecast_revisions
            """
        ).fetchone()
    assert tuple(prediction) == ("Preserved?", "Context", 1)
    assert tuple(revision) == (revision_id, prediction_id, 60, 1, None)
    upgraded.close()


def test_failing_migration_four_rolls_back_the_entire_v3_upgrade(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    v3 = Database.open(database_path, migrations=MIGRATIONS[:3])
    _insert_v3_prediction(v3)
    v3.close()
    failing_v4 = Migration(
        version=4,
        name=MIGRATIONS[3].name,
        statements=(
            *MIGRATIONS[3].statements,
            "INSERT INTO table_that_does_not_exist DEFAULT VALUES",
        ),
    )

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        Database.open(
            database_path,
            migrations=(*MIGRATIONS[:3], failing_v4),
        )

    reopened_v3 = Database.open(database_path, migrations=MIGRATIONS[:3])
    with reopened_v3.transaction() as connection:
        schema_version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        revision_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(forecast_revisions)")
        }
        v4_triggers = connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE type = 'trigger' AND name LIKE 'forecast_revisions_reject_%'
            """
        ).fetchall()
    assert schema_version == 3
    assert "rationale" not in revision_columns
    assert v4_triggers == []
    reopened_v3.close()


@pytest.mark.parametrize("invalid_rationale", ["", "  ", " padded ", "nul\x00text"])
def test_revision_rationale_must_be_canonical_or_null(
    tmp_path,
    invalid_rationale: str,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, _ = _insert_v3_prediction(database)

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence, rationale
            ) VALUES (?, 40, ?, 2, ?)
            """,
            (prediction_id, TIMESTAMP, invalid_rationale),
        )
    database.close()


def test_revision_history_rejects_update_delete_and_replace_but_parent_cascades(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_v3_prediction(database)

    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE forecast_revisions SET probability_percent = 70 WHERE id = ?",
            (revision_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "DELETE FROM forecast_revisions WHERE id = ?",
            (revision_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT OR REPLACE INTO forecast_revisions (
                id, prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, ?, 80, ?, 2)
            """,
            (revision_id, prediction_id, TIMESTAMP),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT OR REPLACE INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 80, ?, 1)
            """,
            (prediction_id, TIMESTAMP),
        )

    with database.transaction() as connection:
        original = connection.execute(
            "SELECT probability_percent, sequence FROM forecast_revisions"
        ).fetchone()
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        count = connection.execute(
            "SELECT COUNT(*) FROM forecast_revisions"
        ).fetchone()[0]
    assert tuple(original) == (60, 1)
    assert count == 0
    database.close()
