"""SQLite connection and transaction ownership."""

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .migrations import (
    MIGRATIONS,
    Migration,
    apply_migrations,
    current_schema_version,
)


class DatabaseClosedError(RuntimeError):
    """Raised when an operation is attempted after the database is closed."""


class NestedTransactionError(RuntimeError):
    """Raised when code attempts to nest database transactions."""


class Database:
    """Own one configured SQLite connection for the application lifetime."""

    def __init__(
        self,
        path: Path,
        connection: sqlite3.Connection,
    ) -> None:
        self._path = path
        self._connection: sqlite3.Connection | None = connection

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        migrations: Sequence[Migration] = MIGRATIONS,
    ) -> "Database":
        """Open, configure, and migrate the database at an explicit path."""

        database_path = Path(path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                database_path,
                autocommit=True,
                timeout=5.0,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise sqlite3.DatabaseError(
                    "SQLite foreign-key enforcement could not be enabled."
                )
            connection.execute("PRAGMA busy_timeout = 5000")
            apply_migrations(connection, migrations)
        except BaseException:
            if connection is not None:
                connection.close()
            raise

        return cls(database_path, connection)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    @property
    def schema_version(self) -> int:
        return current_schema_version(self._require_connection())

    @property
    def foreign_keys_enabled(self) -> bool:
        row = self._require_connection().execute("PRAGMA foreign_keys").fetchone()
        return row[0] == 1

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a non-nested transaction and roll it back on any failure."""

        connection = self._require_connection()
        if connection.in_transaction:
            raise NestedTransactionError("Nested transactions are not supported.")

        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the connection. Calling close more than once is safe."""

        connection = self._connection
        if connection is None:
            return
        self._connection = None
        connection.close()

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DatabaseClosedError("The database is closed.")
        return self._connection
