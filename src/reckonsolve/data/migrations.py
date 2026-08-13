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
    Migration(
        version=2,
        name="add binary predictions and forecast revisions",
        statements=(
            """
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY,
                question TEXT NOT NULL
                    CHECK (length(question) > 0 AND question = trim(question)),
                prediction_type TEXT NOT NULL DEFAULT 'binary'
                    CHECK (prediction_type = 'binary'),
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved', 'invalid')),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                updated_at TEXT NOT NULL
                    CHECK (
                        length(updated_at) = 27
                        AND updated_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(updated_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(updated_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(updated_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(updated_at, 1, 10),
                            0
                        )
                    )
            ) STRICT
            """,
            """
            CREATE TABLE forecast_revisions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                probability_percent INTEGER NOT NULL
                    CHECK (
                        typeof(probability_percent) = 'integer'
                        AND probability_percent BETWEEN 0 AND 100
                ),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                UNIQUE (prediction_id, sequence)
            ) STRICT
            """,
            """
            CREATE INDEX forecast_revisions_latest_by_prediction
            ON forecast_revisions (prediction_id, sequence DESC)
            """,
            """
            CREATE TRIGGER forecast_revisions_are_immutable
            BEFORE UPDATE ON forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'saved forecast revisions are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=3,
        name="add prediction metadata and definition history",
        statements=(
            """
            ALTER TABLE predictions ADD COLUMN metadata_version INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    typeof(metadata_version) = 'integer'
                    AND metadata_version >= 1
                )
            """,
            """
            ALTER TABLE predictions ADD COLUMN background TEXT
                CHECK (background IS NULL OR (
                    length(background) > 0 AND background = trim(background)
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN resolution_criteria TEXT
                CHECK (resolution_criteria IS NULL OR (
                    length(resolution_criteria) > 0
                    AND resolution_criteria = trim(resolution_criteria)
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN forecast_deadline TEXT
                CHECK (forecast_deadline IS NULL OR (
                    length(forecast_deadline) = 10
                    AND forecast_deadline GLOB
                        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                    AND forecast_deadline BETWEEN '1752-09-14' AND '9999-12-31'
                    AND COALESCE(
                        date(forecast_deadline || 'T00:00:00Z', '+0 days')
                            = forecast_deadline,
                        0
                    )
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN expected_resolution TEXT
                CHECK (expected_resolution IS NULL OR (
                    length(expected_resolution) = 10
                    AND expected_resolution GLOB
                        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                    AND expected_resolution BETWEEN '1752-09-14' AND '9999-12-31'
                    AND COALESCE(
                        date(expected_resolution || 'T00:00:00Z', '+0 days')
                            = expected_resolution,
                        0
                    )
                ))
            """,
            """
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL
                    CHECK (
                        length(display_name) > 0
                        AND display_name = trim(display_name)
                        AND instr(display_name, ',') = 0
                        AND instr(display_name, char(10)) = 0
                        AND instr(display_name, char(13)) = 0
                    ),
                normalized_name TEXT NOT NULL UNIQUE
                    CHECK (
                        length(normalized_name) > 0
                        AND normalized_name = trim(normalized_name)
                        AND instr(normalized_name, ',') = 0
                        AND instr(normalized_name, char(10)) = 0
                        AND instr(normalized_name, char(13)) = 0
                    )
            ) STRICT
            """,
            """
            CREATE TABLE prediction_tags (
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
                PRIMARY KEY (prediction_id, tag_id)
            ) WITHOUT ROWID, STRICT
            """,
            """
            CREATE INDEX prediction_tags_by_tag
            ON prediction_tags (tag_id, prediction_id)
            """,
            """
            CREATE TABLE prediction_definition_changes (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                changed_at TEXT NOT NULL
                    CHECK (
                        length(changed_at) = 27
                        AND changed_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(changed_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(changed_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(changed_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(changed_at, 1, 10),
                            0
                        )
                    ),
                old_question TEXT NOT NULL
                    CHECK (
                        length(old_question) > 0
                        AND old_question = trim(old_question)
                    ),
                new_question TEXT NOT NULL
                    CHECK (
                        length(new_question) > 0
                        AND new_question = trim(new_question)
                    ),
                old_resolution_criteria TEXT
                    CHECK (old_resolution_criteria IS NULL OR (
                        length(old_resolution_criteria) > 0
                        AND old_resolution_criteria = trim(old_resolution_criteria)
                    )),
                new_resolution_criteria TEXT
                    CHECK (new_resolution_criteria IS NULL OR (
                        length(new_resolution_criteria) > 0
                        AND new_resolution_criteria = trim(new_resolution_criteria)
                    )),
                old_forecast_deadline TEXT
                    CHECK (old_forecast_deadline IS NULL OR (
                        length(old_forecast_deadline) = 10
                        AND old_forecast_deadline GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                        AND old_forecast_deadline
                            BETWEEN '1752-09-14' AND '9999-12-31'
                        AND COALESCE(
                            date(
                                old_forecast_deadline || 'T00:00:00Z',
                                '+0 days'
                            ) = old_forecast_deadline,
                            0
                        )
                    )),
                new_forecast_deadline TEXT
                    CHECK (new_forecast_deadline IS NULL OR (
                        length(new_forecast_deadline) = 10
                        AND new_forecast_deadline GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                        AND new_forecast_deadline
                            BETWEEN '1752-09-14' AND '9999-12-31'
                        AND COALESCE(
                            date(
                                new_forecast_deadline || 'T00:00:00Z',
                                '+0 days'
                            ) = new_forecast_deadline,
                            0
                        )
                    )),
                CHECK (
                    old_question IS NOT new_question
                    OR old_resolution_criteria IS NOT new_resolution_criteria
                    OR old_forecast_deadline IS NOT new_forecast_deadline
                )
            ) STRICT
            """,
            """
            CREATE INDEX prediction_definition_changes_by_prediction
            ON prediction_definition_changes (prediction_id, id)
            """,
            """
            CREATE TRIGGER prediction_definition_changes_are_immutable
            BEFORE UPDATE ON prediction_definition_changes
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_definition_changes_reject_id_reuse
            BEFORE INSERT ON prediction_definition_changes
            WHEN EXISTS (
                SELECT 1
                FROM prediction_definition_changes
                WHERE id = NEW.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_definition_changes_reject_direct_delete
            BEFORE DELETE ON prediction_definition_changes
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
        ),
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
