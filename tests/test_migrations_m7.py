import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 20, 18, 30, tzinfo=UTC)


def test_v7_upgrade_of_empty_archive_preserves_schema_path(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:6])
    with old.transaction() as connection:
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    old.close()
    upgraded = Database.open(path, migrations=MIGRATIONS[:7])
    assert upgraded.schema_version == 7
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT value FROM sentinel").fetchone()[0]
            == "preserved"
        )
        assert tuple(
            connection.execute(
                "SELECT singleton, stale_threshold_days FROM app_settings"
            ).fetchone()
        ) == (1, 14)
    upgraded.close()


def test_v7_setting_constraints_reject_invalid_rows(tmp_path) -> None:
    database = Database.open(
        tmp_path / "reckonsolve.sqlite3",
        migrations=MIGRATIONS[:7],
    )

    with pytest.raises(sqlite3.IntegrityError), database.transaction() as connection:
        connection.execute(
            "UPDATE app_settings SET stale_threshold_days = 0 WHERE singleton = 1"
        )
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as connection:
        connection.execute("INSERT INTO app_settings VALUES (2, 14)")

    database.close()


def test_failing_v7_rolls_back_settings_table_and_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:6]).close()
    broken_v7 = Migration(
        version=7,
        name="broken attention settings",
        statements=(
            "CREATE TABLE app_settings (value INTEGER) STRICT",
            "THIS IS NOT SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:6], broken_v7))

    connection = sqlite3.connect(path)
    try:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        table = connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'app_settings'"
        ).fetchone()
    finally:
        connection.close()
    assert version == 6
    assert table is None
