"""Recovery-backed, reviewed upgrades under one SQLite exclusion boundary."""

import os
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .migrations import (
    Migration,
    MigrationError,
    _apply_migrations_in_transaction,
    validate_migration_source,
)


class UpgradeReviewRequiredError(MigrationError):
    """A desktop retirement review is needed before opening this old journal."""


class UpgradeCancelledError(MigrationError):
    """The user retained the original active schema/configurations."""


@dataclass(frozen=True, slots=True)
class UpgradeReview:
    source: Path
    recovery: Path
    saved_view_count: int
    original_version: int
    target_version: int


def upgrade_with_recovery(
    connection: sqlite3.Connection,
    path: Path,
    migrations: Sequence[Migration],
    confirm: Callable[[UpgradeReview], bool] | None,
) -> None:
    """Protect and upgrade a supported journal; never commit on cancellation.

    EXCLUSIVE excludes other writers during snapshot/review/DDL in both rollback
    and WAL modes. Schema-21 guards then exclude already-open older writers
    after commit. Serialization captures the connection's complete SQLite image,
    including committed WAL pages; copying the live file would not suffice.
    """
    # An already-current journal needs ordinary read admission, not an upgrade
    # exclusion window. Pending work is revalidated after acquiring exclusion.
    connection.execute("BEGIN")
    try:
        applied = validate_migration_source(connection, migrations)
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    if applied >= migrations[-1].version:
        return
    connection.execute("BEGIN EXCLUSIVE")
    try:
        applied = validate_migration_source(connection, migrations)
        target = migrations[-1].version
        if applied >= target:
            connection.execute("COMMIT")
            return
        views_exist = connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = 'saved_views' AND type = 'table'"
        ).fetchone()
        count = (
            connection.execute("SELECT COUNT(*) FROM saved_views").fetchone()[0]
            if views_exist
            else 0
        )
        if count and confirm is None:
            raise UpgradeReviewRequiredError(
                "This journal contains Saved Views, which are retired. Open the "
                "updated desktop app to review the verified recovery backup and "
                "confirm retirement. No upgrade was performed."
            )
        if applied:
            recovery = _protect_snapshot(connection, path, migrations, applied)
            if count and not confirm(
                UpgradeReview(path, recovery, count, applied, target)
            ):
                raise UpgradeCancelledError(
                    f"Upgrade cancelled. The original journal is unchanged. Recovery: {recovery}"
                )
        _apply_migrations_in_transaction(connection, migrations)
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _protect_snapshot(
    connection: sqlite3.Connection,
    path: Path,
    migrations: Sequence[Migration],
    applied: int,
) -> Path:
    image = connection.serialize()
    recovery = path.with_name(f"{path.stem}.pre-upgrade-{uuid4().hex}.sqlite3")
    created = False
    try:
        with recovery.open("xb") as stream:
            created = True
            stream.write(image)
            stream.flush()
            os.fsync(stream.fileno())
        snapshot = sqlite3.connect(recovery, autocommit=True)
        snapshot.row_factory = sqlite3.Row
        try:
            if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise MigrationError("The recovery copy failed its integrity check.")
            if snapshot.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise MigrationError("The recovery copy failed its foreign-key check.")
            if validate_migration_source(snapshot, migrations) != applied:
                raise MigrationError(
                    "The recovery copy has different migration history."
                )
        finally:
            snapshot.close()
        if recovery.read_bytes() != image:
            raise MigrationError("The recovery copy differs from the protected image.")
        return recovery
    except BaseException:
        # Only this unique, incomplete artifact is ours to remove. A verified
        # recovery returned above is retained after cancellation or later failure.
        if created:
            recovery.unlink(missing_ok=True)
        raise
