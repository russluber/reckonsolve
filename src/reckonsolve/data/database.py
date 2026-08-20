"""SQLite connection and transaction ownership."""

import os
import sqlite3
import tempfile
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

    def backup_to(self, destination: Path) -> Path:
        """Create and verify an atomically installed SQLite recovery snapshot."""

        source = self._require_connection()
        if source.in_transaction:
            raise NestedTransactionError(
                "A backup cannot start inside another database transaction."
            )

        destination_path = Path(destination)
        parent = destination_path.parent.resolve(strict=True)
        if not parent.is_dir():
            raise NotADirectoryError(f"Backup destination is not a folder: {parent}")
        resolved_destination = (parent / destination_path.name).resolve(strict=False)
        resolved_source = self._path.resolve(strict=True)
        if resolved_destination == resolved_source or (
            resolved_destination.exists()
            and os.path.samefile(resolved_destination, resolved_source)
        ):
            raise ValueError("The live Reckonsolve database cannot be its own backup.")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination_path.name}.",
            suffix=".tmp",
            dir=parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        installed = False
        try:
            target = sqlite3.connect(temporary_path, autocommit=True, timeout=5.0)
            target.row_factory = sqlite3.Row
            try:
                source.backup(target, pages=256, sleep=0.05)
                quick_check = target.execute("PRAGMA quick_check").fetchone()
                if quick_check is None or quick_check[0] != "ok":
                    raise sqlite3.DatabaseError(
                        "The completed backup failed SQLite's integrity check."
                    )
                if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise sqlite3.DatabaseError(
                        "The completed backup failed its foreign-key check."
                    )
                if current_schema_version(target) != current_schema_version(source):
                    raise sqlite3.DatabaseError(
                        "The completed backup has an unexpected schema version."
                    )
            finally:
                target.close()
            os.replace(temporary_path, resolved_destination)
            installed = True
            return resolved_destination
        finally:
            if not installed and temporary_path.exists():
                temporary_path.unlink()

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DatabaseClosedError("The database is closed.")
        return self._connection
