import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 21, 19, 30, tzinfo=UTC)


def test_v10_upgrade_of_empty_archive_preserves_schema_path(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:9])
    with old.transaction() as connection:
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    old.close()
    upgraded = Database.open(path, migrations=MIGRATIONS[:10])
    assert upgraded.schema_version == 10
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT value FROM sentinel").fetchone()[0]
            == "preserved"
        )
        assert "numeric_forecast_revision_id" in {
            row[1] for row in connection.execute("PRAGMA table_info(journal_entries)")
        }
    upgraded.close()


def test_failing_v10_rolls_back_rebuilt_journal_schema_and_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:9]).close()
    broken_v10 = Migration(
        version=10,
        name="broken type-aware journal migration",
        statements=(
            "ALTER TABLE journal_entries RENAME TO journal_entries_v9",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:9], broken_v10))

    recovered = Database.open(path, migrations=MIGRATIONS[:9])
    assert recovered.schema_version == 9
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'journal_entries'"
            ).fetchone()
            is not None
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'journal_entries_v9'"
            ).fetchone()
            is None
        )
    recovered.close()
