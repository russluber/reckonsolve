import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration

TIMESTAMP = "2026-08-20T18:45:12.003456Z"


def _insert_v5_prediction(database: Database) -> tuple[int, int]:
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES ('Preserved?', 'binary', 'open', ?, ?)
            """,
            (TIMESTAMP, TIMESTAMP),
        ).lastrowid
        assert prediction_id is not None
        revision_id = connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence, rationale
            ) VALUES (?, 65, ?, 1, 'Initial')
            """,
            (prediction_id, TIMESTAMP),
        ).lastrowid
        assert revision_id is not None
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Evidence', ?)
            """,
            (prediction_id, revision_id, TIMESTAMP),
        )
    return prediction_id, revision_id


def test_v5_upgrade_preserves_history_and_adds_terminal_tables(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v5 = Database.open(path, migrations=MIGRATIONS[:5])
    prediction_id, revision_id = _insert_v5_prediction(v5)
    v5.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:6])

    assert upgraded.schema_version == 6
    with upgraded.transaction() as connection:
        prediction = connection.execute(
            "SELECT question, status FROM predictions WHERE id = ?",
            (prediction_id,),
        ).fetchone()
        revision = connection.execute(
            "SELECT probability_percent FROM forecast_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        journal_count = connection.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone()[0]
        terminal_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE type = 'table'
                    AND name IN ('resolutions', 'prediction_invalidations')
                """
            ).fetchall()
        }
    assert tuple(prediction) == ("Preserved?", "open")
    assert revision[0] == 65
    assert journal_count == 1
    assert terminal_tables == {"resolutions", "prediction_invalidations"}
    upgraded.close()


def test_failed_v6_upgrade_rolls_back_every_schema_statement(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v5 = Database.open(path, migrations=MIGRATIONS[:5])
    prediction_id, _ = _insert_v5_prediction(v5)
    v5.close()
    broken_v6 = Migration(
        version=6,
        name=MIGRATIONS[5].name,
        statements=(*MIGRATIONS[5].statements[:6], "THIS IS NOT SQL"),
    )

    with pytest.raises(sqlite3.OperationalError):
        Database.open(path, migrations=(*MIGRATIONS[:5], broken_v6))

    reopened = Database.open(path, migrations=MIGRATIONS[:5])
    assert reopened.schema_version == 5
    with reopened.transaction() as connection:
        assert (
            connection.execute(
                "SELECT question FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()[0]
            == "Preserved?"
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name = 'resolutions'"
            ).fetchone()
            is None
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name = 'prediction_invalidations'"
            ).fetchone()
            is None
        )
    reopened.close()


@pytest.mark.parametrize("legacy_status", ["resolved", "invalid"])
def test_v6_refuses_legacy_terminal_status_without_inventing_missing_facts(
    tmp_path,
    legacy_status: str,
) -> None:
    path = tmp_path / f"{legacy_status}.sqlite3"
    v5 = Database.open(path, migrations=MIGRATIONS[:5])
    prediction_id, _ = _insert_v5_prediction(v5)
    with v5.transaction() as connection:
        connection.execute(
            "UPDATE predictions SET status = ? WHERE id = ?",
            (legacy_status, prediction_id),
        )
    v5.close()

    with pytest.raises(sqlite3.IntegrityError):
        Database.open(path)

    unchanged = Database.open(path, migrations=MIGRATIONS[:5])
    assert unchanged.schema_version == 5
    with unchanged.transaction() as connection:
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()[0]
            == legacy_status
        )
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name = 'resolutions'"
            ).fetchone()
            is None
        )
    unchanged.close()


def test_resolution_requires_current_owned_revision_and_sets_terminal_status(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_v5_prediction(database)
    other_prediction, other_revision = _insert_v5_prediction(database)

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO resolutions (
                prediction_id, outcome, resolved_at, scoring_revision_id
            ) VALUES (?, 'yes', ?, ?)
            """,
            (prediction_id, TIMESTAMP, other_revision),
        )

    with database.transaction() as connection:
        resolution_id = connection.execute(
            """
            INSERT INTO resolutions (
                prediction_id, outcome, resolved_at, scoring_revision_id
            ) VALUES (?, 'no', ?, ?)
            """,
            (prediction_id, TIMESTAMP, revision_id),
        ).lastrowid
        status = connection.execute(
            "SELECT status, updated_at FROM predictions WHERE id = ?",
            (prediction_id,),
        ).fetchone()
    assert resolution_id is not None
    assert tuple(status) == ("resolved", TIMESTAMP)
    assert other_prediction != prediction_id
    database.close()


def test_terminal_rows_and_status_are_immutable_but_parent_delete_cascades(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_v5_prediction(database)
    with database.transaction() as connection:
        resolution_id = connection.execute(
            """
            INSERT INTO resolutions (
                prediction_id, outcome, resolved_at, scoring_revision_id,
                resolution_notes
            ) VALUES (?, 'yes', ?, ?, 'Source')
            """,
            (prediction_id, TIMESTAMP, revision_id),
        ).lastrowid
        assert resolution_id is not None

    for statement in (
        "UPDATE resolutions SET outcome = 'no' WHERE id = ?",
        "DELETE FROM resolutions WHERE id = ?",
        "UPDATE predictions SET status = 'open' WHERE id = ?",
    ):
        with (
            pytest.raises(sqlite3.IntegrityError, match="immutable"),
            database.transaction() as connection,
        ):
            connection.execute(
                statement,
                (resolution_id if "resolutions" in statement else prediction_id,),
            )

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT OR REPLACE INTO resolutions (
                id, prediction_id, outcome, resolved_at, scoring_revision_id
            ) VALUES (?, ?, 'no', ?, ?)
            """,
            (resolution_id, prediction_id, TIMESTAMP, revision_id),
        )

    with database.transaction() as connection:
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM resolutions WHERE prediction_id = ?",
                (prediction_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM forecast_revisions WHERE prediction_id = ?",
                (prediction_id,),
            ).fetchone()[0]
            == 0
        )
    database.close()


@pytest.mark.parametrize("status", ["resolved", "invalid"])
def test_terminal_status_cannot_be_set_without_its_record(
    tmp_path, status: str
) -> None:
    database = Database.open(tmp_path / f"{status}.sqlite3")
    prediction_id, _ = _insert_v5_prediction(database)

    with (
        pytest.raises(sqlite3.IntegrityError, match="requires"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE predictions SET status = ? WHERE id = ?",
            (status, prediction_id),
        )
    database.close()


def test_invalidation_is_mutually_exclusive_with_resolution(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_v5_prediction(database)
    with database.transaction() as connection:
        invalidation_id = connection.execute(
            """
            INSERT INTO prediction_invalidations (
                prediction_id, invalidated_at, reason
            ) VALUES (?, ?, 'Cancelled')
            """,
            (prediction_id, TIMESTAMP),
        ).lastrowid
        assert invalidation_id is not None

    with (
        pytest.raises(sqlite3.IntegrityError, match="open or locked"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO resolutions (
                prediction_id, outcome, resolved_at, scoring_revision_id
            ) VALUES (?, 'yes', ?, ?)
            """,
            (prediction_id, TIMESTAMP, revision_id),
        )
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()[0]
            == "invalid"
        )
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 0
    database.close()
