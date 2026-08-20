import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration

TIMESTAMP = "2026-08-12T19:30:00.000000Z"


def _insert_prediction(
    database: Database, *, question: str = "Preserved?"
) -> tuple[int, int]:
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES (?, 'binary', 'open', ?, ?)
            """,
            (question, TIMESTAMP, TIMESTAMP),
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


def test_migration_five_preserves_v4_history_and_adds_empty_journal_tables(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v4 = Database.open(path, migrations=MIGRATIONS[:4])
    prediction_id, revision_id = _insert_prediction(v4)
    v4.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:5])

    assert upgraded.schema_version == 5
    with upgraded.transaction() as connection:
        revision = connection.execute(
            "SELECT id, prediction_id, probability_percent FROM forecast_revisions"
        ).fetchone()
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM journal_entries),
                (SELECT COUNT(*) FROM journal_entry_corrections)
            """
        ).fetchone()
    assert tuple(revision) == (revision_id, prediction_id, 60)
    assert tuple(counts) == (0, 0)
    upgraded.close()


def test_failing_migration_five_rolls_back_the_entire_v4_upgrade(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v4 = Database.open(path, migrations=MIGRATIONS[:4])
    _insert_prediction(v4)
    v4.close()
    failing_v5 = Migration(
        version=5,
        name=MIGRATIONS[4].name,
        statements=(
            *MIGRATIONS[4].statements,
            "INSERT INTO table_that_does_not_exist DEFAULT VALUES",
        ),
    )

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        Database.open(path, migrations=(*MIGRATIONS[:4], failing_v5))

    reopened = Database.open(path, migrations=MIGRATIONS[:4])
    with reopened.transaction() as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        journal_tables = connection.execute(
            """
            SELECT name FROM sqlite_schema
            WHERE type = 'table' AND name LIKE 'journal_%'
            """
        ).fetchall()
    assert version == 4
    assert journal_tables == []
    reopened.close()


@pytest.mark.parametrize(
    "invalid_body",
    ["", "  ", "\t", "\n", "\r\n", "\ttext", "text\n", " padded ", "nul\x00text"],
)
def test_journal_bodies_must_be_canonical(tmp_path, invalid_body: str) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_prediction(database)

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (prediction_id, revision_id, invalid_body, TIMESTAMP),
        )
    database.close()


def test_journal_anchor_must_belong_to_prediction_and_be_current(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    first_prediction, first_revision = _insert_prediction(database, question="First?")
    second_prediction, second_revision = _insert_prediction(
        database, question="Second?"
    )
    with database.transaction() as connection:
        current_revision = connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 40, ?, 2)
            """,
            (first_prediction, TIMESTAMP),
        ).lastrowid
        assert current_revision is not None

    with (
        pytest.raises(sqlite3.IntegrityError),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Wrong owner', ?)
            """,
            (first_prediction, second_revision, TIMESTAMP),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="current"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Old anchor', ?)
            """,
            (first_prediction, first_revision, TIMESTAMP),
        )
    assert second_prediction != first_prediction
    database.close()


def test_terminal_predictions_reject_raw_new_entries_but_accept_corrections(
    tmp_path,
) -> None:
    database = Database.open(
        tmp_path / "reckonsolve.sqlite3",
        migrations=MIGRATIONS[:5],
    )
    prediction_id, revision_id = _insert_prediction(database)
    with database.transaction() as connection:
        entry_id = connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Original', ?)
            """,
            (prediction_id, revision_id, TIMESTAMP),
        ).lastrowid
        assert entry_id is not None
        connection.execute(
            "UPDATE predictions SET status = 'resolved' WHERE id = ?",
            (prediction_id,),
        )

    with (
        pytest.raises(sqlite3.IntegrityError, match="open or locked"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Too late', ?)
            """,
            (prediction_id, revision_id, TIMESTAMP),
        )
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO journal_entry_corrections (
                prediction_id, journal_entry_id, sequence, body, corrected_at
            ) VALUES (?, ?, 1, 'Corrected', ?)
            """,
            (prediction_id, entry_id, TIMESTAMP),
        )
    database.close()


def test_journal_and_correction_history_is_immutable_but_parent_cascades(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_prediction(database)
    with database.transaction() as connection:
        entry_id = connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Original', ?)
            """,
            (prediction_id, revision_id, TIMESTAMP),
        ).lastrowid
        assert entry_id is not None
        correction_id = connection.execute(
            """
            INSERT INTO journal_entry_corrections (
                prediction_id, journal_entry_id, sequence, body, corrected_at
            ) VALUES (?, ?, 1, 'Corrected', ?)
            """,
            (prediction_id, entry_id, TIMESTAMP),
        ).lastrowid
        assert correction_id is not None

    statements = (
        ("UPDATE journal_entries SET body = 'Rewrite' WHERE id = ?", (entry_id,)),
        ("DELETE FROM journal_entries WHERE id = ?", (entry_id,)),
        (
            (
                "INSERT OR REPLACE INTO journal_entries "
                "(id, prediction_id, forecast_revision_id, body, created_at) "
                "VALUES (?, ?, ?, 'Rewrite', ?)"
            ),
            (entry_id, prediction_id, revision_id, TIMESTAMP),
        ),
        (
            "UPDATE journal_entry_corrections SET body = 'Rewrite' WHERE id = ?",
            (correction_id,),
        ),
        ("DELETE FROM journal_entry_corrections WHERE id = ?", (correction_id,)),
        (
            (
                "INSERT OR REPLACE INTO journal_entry_corrections "
                "(id, prediction_id, journal_entry_id, sequence, body, "
                "corrected_at) VALUES (?, ?, ?, 2, 'Rewrite', ?)"
            ),
            (correction_id, prediction_id, entry_id, TIMESTAMP),
        ),
    )
    for sql, parameters in statements:
        with (
            pytest.raises(sqlite3.IntegrityError, match="immutable"),
            database.transaction() as connection,
        ):
            connection.execute(sql, parameters)

    with database.transaction() as connection:
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM journal_entries),
                (SELECT COUNT(*) FROM journal_entry_corrections)
            """
        ).fetchone()
    assert tuple(counts) == (0, 0)
    database.close()


def test_raw_correction_sequence_must_be_contiguous_and_change_body(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction_id, revision_id = _insert_prediction(database)
    with database.transaction() as connection:
        entry_id = connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, forecast_revision_id, body, created_at
            ) VALUES (?, ?, 'Original', ?)
            """,
            (prediction_id, revision_id, TIMESTAMP),
        ).lastrowid
        assert entry_id is not None

    with (
        pytest.raises(sqlite3.IntegrityError, match="contiguous"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entry_corrections (
                prediction_id, journal_entry_id, sequence, body, corrected_at
            ) VALUES (?, ?, 99, 'Skipped', ?)
            """,
            (prediction_id, entry_id, TIMESTAMP),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="change"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO journal_entry_corrections (
                prediction_id, journal_entry_id, sequence, body, corrected_at
            ) VALUES (?, ?, 1, 'Original', ?)
            """,
            (prediction_id, entry_id, TIMESTAMP),
        )
    database.close()
