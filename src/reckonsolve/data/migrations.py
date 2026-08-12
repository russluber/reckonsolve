"""Ordered, transactional SQLite schema migrations."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass


class MigrationError(RuntimeError):
    """Base class for migration failures detected by Reckonsolve."""


class MigrationConfigurationError(MigrationError):
    """Raised when the migrations bundled with the application are invalid."""


class InvalidMigrationHistoryError(MigrationError):
    """Raised when recorded migration history is missing or inconsistent."""


class UnrecognizedDatabaseError(MigrationError):
    """Raised when a SQLite database does not belong to Reckonsolve."""


class UnsupportedSchemaVersionError(MigrationError):
    """Raised when a database was created by a newer application version."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable schema migration, applied statement by statement."""

    version: int
    name: str
    statements: tuple[str, ...]


MIGRATION_TABLE_SQL = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version >= 1),
    name TEXT NOT NULL UNIQUE
) STRICT
"""


MIGRATIONS = (
    Migration(
        version=1,
        name="initialize migration tracking",
        statements=(MIGRATION_TABLE_SQL,),
    ),
)


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration] = MIGRATIONS,
) -> None:
    """Apply every pending migration in a single SQLite transaction."""

    ordered_migrations = tuple(migrations)
    _validate_registry(ordered_migrations)

    if connection.in_transaction:
        raise MigrationError("Migrations cannot run inside another transaction.")

    connection.execute("BEGIN IMMEDIATE")
    try:
        applied_count = _validated_applied_count(connection, ordered_migrations)
        for migration in ordered_migrations[applied_count:]:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name),
            )

        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_violations:
            raise MigrationError("A migration introduced a foreign-key violation.")
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def current_schema_version(connection: sqlite3.Connection) -> int:
    """Return the latest recorded schema version for an initialized database."""

    row = connection.execute(
        "SELECT MAX(version) AS version FROM schema_migrations"
    ).fetchone()
    if row is None or row[0] is None:
        raise InvalidMigrationHistoryError("The migration history is empty.")
    return int(row[0])


def _validate_registry(migrations: tuple[Migration, ...]) -> None:
    if not migrations:
        raise MigrationConfigurationError("At least one migration is required.")

    expected_versions = tuple(range(1, len(migrations) + 1))
    actual_versions = tuple(migration.version for migration in migrations)
    if actual_versions != expected_versions:
        raise MigrationConfigurationError(
            "Migration versions must be unique, ordered, and contiguous from 1."
        )

    names = tuple(migration.name for migration in migrations)
    if any(not name.strip() for name in names) or len(set(names)) != len(names):
        raise MigrationConfigurationError(
            "Migration names must be non-empty and unique."
        )


def _validated_applied_count(
    connection: sqlite3.Connection,
    migrations: tuple[Migration, ...],
) -> int:
    objects = connection.execute(
        """
        SELECT name, type
        FROM sqlite_schema
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    tracking_objects = [row for row in objects if row[0] == "schema_migrations"]

    if not tracking_objects:
        if objects:
            raise UnrecognizedDatabaseError(
                "The selected database contains data but no Reckonsolve migration history."
            )
        return 0

    if len(tracking_objects) != 1 or tracking_objects[0][1] != "table":
        raise InvalidMigrationHistoryError(
            "The schema_migrations object is not a valid table."
        )

    schema_row = connection.execute(
        """
        SELECT sql
        FROM sqlite_schema
        WHERE name = 'schema_migrations' AND type = 'table'
        """
    ).fetchone()
    if (
        schema_row is None
        or schema_row[0] is None
        or _normalize_sql(schema_row[0]) != _normalize_sql(MIGRATION_TABLE_SQL)
    ):
        raise InvalidMigrationHistoryError(
            "The migration history table does not match the required schema."
        )

    try:
        history = connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
    except sqlite3.Error as error:
        raise InvalidMigrationHistoryError(
            "The migration history table has an invalid structure."
        ) from error

    if not history:
        raise InvalidMigrationHistoryError("The migration history is empty.")

    for expected_version, row in enumerate(history, start=1):
        recorded_version = row[0]
        if recorded_version != expected_version:
            raise InvalidMigrationHistoryError(
                "Recorded migration versions must be contiguous from 1."
            )
        if recorded_version > len(migrations):
            raise UnsupportedSchemaVersionError(
                "The database schema is newer than this Reckonsolve version."
            )
        expected_name = migrations[recorded_version - 1].name
        if row[1] != expected_name:
            raise InvalidMigrationHistoryError(
                f"Migration {recorded_version} does not match this application build."
            )

    return len(history)


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.rstrip("; ").split()).casefold()
