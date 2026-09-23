import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = datetime(2026, 8, 23, 19, 30, tzinfo=UTC)

    def now(self) -> datetime:
        return self.instant


def test_v11_upgrade_of_empty_archive_preserves_schema_path(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:10])
    with old.transaction() as connection:
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    old.close()
    upgraded = Database.open(path, migrations=MIGRATIONS[:11])
    assert upgraded.schema_version == 11
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT value FROM sentinel").fetchone()[0]
            == "preserved"
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
    upgraded.close()


def test_failing_v11_rolls_back_table_and_trigger_changes(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:10]).close()
    broken = Migration(
        version=11,
        name="broken numeric lifecycle migration",
        statements=(
            "DROP TRIGGER predictions_status_requires_terminal_record",
            "CREATE TABLE numeric_resolutions (id INTEGER PRIMARY KEY) STRICT",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:10], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:10])
    assert recovered.schema_version == 10
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'numeric_resolutions'"
            ).fetchone()
            is None
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name = 'predictions_status_requires_terminal_record'"
            ).fetchone()
            is not None
        )
    recovered.close()
