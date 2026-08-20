"""SQLite access for the small set of persisted application settings."""

import sqlite3
from datetime import datetime

from reckonsolve.clock import format_utc, parse_utc

from .database import Database


class SettingsRepository:
    """Read and update the singleton v0.1 application settings row."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_stale_threshold_days(self) -> int:
        """Return the persisted Needs Attention threshold."""

        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT stale_threshold_days
                FROM app_settings
                WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("The application settings row is missing.")
        return int(row["stale_threshold_days"])

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist and return the Needs Attention threshold."""

        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE app_settings
                SET stale_threshold_days = ?
                WHERE singleton = 1
                """,
                (value,),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise sqlite3.DatabaseError("The application settings row is missing.")
        return value

    def get_last_successful_backup_at(self) -> datetime | None:
        """Return the persisted successful-backup instant, when one exists."""

        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT last_successful_backup_at
                FROM app_settings
                WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("The application settings row is missing.")
        value = row["last_successful_backup_at"]
        return None if value is None else parse_utc(str(value))

    def set_last_successful_backup_at(self, value: datetime) -> datetime:
        """Persist and return the canonical successful-backup instant."""

        with self._database.transaction() as connection:
            connection.execute(
                """
                UPDATE app_settings
                SET last_successful_backup_at = ?
                WHERE singleton = 1
                """,
                (format_utc(value),),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise sqlite3.DatabaseError("The application settings row is missing.")
        return value
