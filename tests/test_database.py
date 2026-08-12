import sqlite3

import pytest

from reckonsolve.data.database import Database, DatabaseClosedError
from reckonsolve.data.migrations import (
    MIGRATIONS,
    InvalidMigrationHistoryError,
    Migration,
    UnrecognizedDatabaseError,
    UnsupportedSchemaVersionError,
)


def test_fresh_database_initializes_and_reopens(tmp_path) -> None:
    database_path = tmp_path / "nested" / "reckonsolve.sqlite3"

    first_database = Database.open(database_path)
    assert first_database.path == database_path
    assert first_database.schema_version == 1
    assert first_database.foreign_keys_enabled
    with first_database.transaction() as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    first_database.close()

    second_database = Database.open(database_path)
    assert second_database.schema_version == 1
    with second_database.transaction() as connection:
        row = connection.execute("SELECT value FROM sentinel").fetchone()
    assert row["value"] == "preserved"
    second_database.close()


def test_transaction_rolls_back_on_failure(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        connection.execute("CREATE TABLE events (value TEXT NOT NULL)")

    with (
        pytest.raises(RuntimeError, match="stop"),
        database.transaction() as connection,
    ):
        connection.execute("INSERT INTO events VALUES ('not committed')")
        raise RuntimeError("stop")

    with database.transaction() as connection:
        count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 0
    database.close()


def test_closed_database_rejects_operations(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    database.close()
    database.close()

    with pytest.raises(DatabaseClosedError, match="closed"):
        _ = database.schema_version
    with pytest.raises(DatabaseClosedError, match="closed"), database.transaction():
        pass


def test_pending_migration_preserves_existing_data(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    with database.transaction() as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    database.close()

    migrations = (
        *MIGRATIONS,
        Migration(
            version=2,
            name="add example table",
            statements=("CREATE TABLE example (identifier INTEGER PRIMARY KEY)",),
        ),
    )
    upgraded_database = Database.open(database_path, migrations=migrations)

    assert upgraded_database.schema_version == 2
    with upgraded_database.transaction() as connection:
        value = connection.execute("SELECT value FROM sentinel").fetchone()[0]
    assert value == "preserved"
    upgraded_database.close()


def test_failing_migration_rolls_back_entire_upgrade(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    Database.open(database_path).close()
    failing_migrations = (
        *MIGRATIONS,
        Migration(
            version=2,
            name="failing example",
            statements=(
                "CREATE TABLE should_be_rolled_back (value TEXT)",
                "THIS IS NOT SQL",
            ),
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(database_path, migrations=failing_migrations)

    connection = sqlite3.connect(database_path)
    try:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        table = connection.execute(
            "SELECT name FROM sqlite_schema WHERE name = 'should_be_rolled_back'"
        ).fetchone()
    finally:
        connection.close()
    assert versions == [(1,)]
    assert table is None


def test_database_from_newer_application_is_rejected(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    migrations = (
        *MIGRATIONS,
        Migration(version=2, name="future schema", statements=()),
    )
    Database.open(database_path, migrations=migrations).close()

    with pytest.raises(UnsupportedSchemaVersionError, match="newer"):
        Database.open(database_path)


def test_changed_migration_history_is_rejected_without_repair(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    Database.open(database_path).close()
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE schema_migrations SET name = 'changed' WHERE version = 1"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(InvalidMigrationHistoryError, match="does not match"):
        Database.open(database_path)

    connection = sqlite3.connect(database_path)
    try:
        name = connection.execute(
            "SELECT name FROM schema_migrations WHERE version = 1"
        ).fetchone()[0]
    finally:
        connection.close()
    assert name == "changed"


def test_malformed_migration_table_is_rejected(tmp_path) -> None:
    database_path = tmp_path / "malformed.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER, name TEXT)"
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, 'initialize migration tracking')"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(InvalidMigrationHistoryError, match="required schema"):
        Database.open(database_path)


def test_schema_version_reader_does_not_require_row_factory(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    Database.open(database_path).close()
    connection = sqlite3.connect(database_path)
    try:
        from reckonsolve.data.migrations import current_schema_version

        assert current_schema_version(connection) == 1
    finally:
        connection.close()


def test_unrecognized_sqlite_database_is_preserved(tmp_path) -> None:
    database_path = tmp_path / "other.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE unrelated (value TEXT NOT NULL)")
        connection.execute("INSERT INTO unrelated VALUES ('keep me')")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(UnrecognizedDatabaseError, match="no Reckonsolve"):
        Database.open(database_path)

    connection = sqlite3.connect(database_path)
    try:
        value = connection.execute("SELECT value FROM unrelated").fetchone()[0]
    finally:
        connection.close()
    assert value == "keep me"


def test_non_sqlite_file_is_not_replaced(tmp_path) -> None:
    database_path = tmp_path / "not-a-database.sqlite3"
    original_bytes = b"this is not sqlite"
    database_path.write_bytes(original_bytes)

    with pytest.raises(sqlite3.DatabaseError):
        Database.open(database_path)

    assert database_path.read_bytes() == original_bytes
