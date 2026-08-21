import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.settings import SettingsRepository


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 20, 18, 30, tzinfo=UTC)


def test_v8_upgrade_preserves_data_and_starts_without_a_backup_time(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old_database = Database.open(path, migrations=MIGRATIONS[:7])
    created = PredictionOperations(old_database, FixedClock()).create_prediction(
        "Will this v7 prediction survive the backup-setting migration?",
        64,
    )
    SettingsRepository(old_database).set_stale_threshold_days(21)
    old_database.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:8])

    assert upgraded.schema_version == 8
    reopened = PredictionOperations(upgraded, FixedClock()).get_prediction(
        created.prediction_id
    )
    assert reopened.question == created.question
    settings = SettingsRepository(upgraded)
    assert settings.get_stale_threshold_days() == 21
    assert settings.get_last_successful_backup_at() is None
    upgraded.close()


def test_v8_backup_timestamp_constraint_and_round_trip(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    settings = SettingsRepository(database)
    instant = datetime(2026, 8, 20, 18, 30, 45, 123456, tzinfo=UTC)

    assert settings.set_last_successful_backup_at(instant) == instant
    assert settings.get_last_successful_backup_at() == instant

    for invalid in (
        "2026-08-20 18:30:45",
        "2026-02-30T18:30:45.000000Z",
        "2026-08-20T24:00:00.000000Z",
    ):
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as connection,
        ):
            connection.execute(
                """
                UPDATE app_settings
                SET last_successful_backup_at = ?
                WHERE singleton = 1
                """,
                (invalid,),
            )

    assert settings.get_last_successful_backup_at() == instant
    database.close()


def test_failing_v8_rolls_back_column_and_migration_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:7]).close()
    broken_v8 = Migration(
        version=8,
        name="broken backup setting",
        statements=(
            "ALTER TABLE app_settings ADD COLUMN last_successful_backup_at TEXT",
            "THIS IS NOT SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:7], broken_v8))

    connection = sqlite3.connect(path)
    try:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(app_settings)")
        )
    finally:
        connection.close()
    assert version == 7
    assert columns == ("singleton", "stale_threshold_days")
