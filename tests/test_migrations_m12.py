import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


def test_v12_upgrade_preserves_v11_data_and_adds_review_table(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:11])
    with old.transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO predictions (question, status, created_at, updated_at)
            VALUES ('Preserved?', 'open', ?, ?)
            """,
            ("2026-08-20T18:00:00.000000Z",) * 2,
        )
        prediction_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, sequence, created_at
            ) VALUES (?, 60, 1, ?)
            """,
            (prediction_id, "2026-08-20T18:00:00.000000Z"),
        )
    old.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:12])
    assert upgraded.schema_version == 12
    with upgraded.transaction() as connection:
        assert (
            connection.execute(
                "SELECT question FROM predictions WHERE id = ?", (prediction_id,)
            ).fetchone()[0]
            == "Preserved?"
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM forecast_reviews").fetchone()[0]
            == 0
        )
    upgraded.close()


def test_failing_v12_rolls_back_review_schema(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:11]).close()
    broken = Migration(
        version=12,
        name="broken forecast review migration",
        statements=(
            "CREATE TABLE forecast_reviews (id INTEGER PRIMARY KEY) STRICT",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:11], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:11])
    assert recovered.schema_version == 11
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'forecast_reviews'"
            ).fetchone()
            is None
        )
    recovered.close()


def test_review_history_is_immutable_and_parent_cascade_remains_available(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO predictions (question, status, created_at, updated_at)
            VALUES ('Review integrity?', 'open', ?, ?)
            """,
            ("2026-08-20T18:00:00.000000Z",) * 2,
        )
        prediction_id = int(cursor.lastrowid)
        revision = connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, sequence, created_at
            ) VALUES (?, 60, 1, ?)
            """,
            (prediction_id, "2026-08-20T18:00:00.000000Z"),
        )
        review_id = int(
            connection.execute(
                """
                INSERT INTO forecast_reviews (
                    prediction_id, forecast_revision_id, created_at, note
                ) VALUES (?, ?, ?, 'Retain it')
                """,
                (
                    prediction_id,
                    int(revision.lastrowid),
                    "2026-08-20T19:00:00.000000Z",
                ),
            ).lastrowid
        )

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE forecast_reviews SET note = 'Rewrite' WHERE id = ?",
            (review_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute("DELETE FROM forecast_reviews WHERE id = ?", (review_id,))

    with database.transaction() as connection:
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        assert (
            connection.execute(
                "SELECT 1 FROM forecast_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            is None
        )
    database.close()
