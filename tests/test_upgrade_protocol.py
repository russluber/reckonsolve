"""Native SQLite capabilities required before the redesign upgrade is enabled.

These disposable protocol tests do not apply a production migration. They prove
the snapshot/lock and stale-client primitives before the migration uses them.
"""

import sqlite3
import subprocess
import sys

import pytest
from legacy_saved_view_fixture import add_legacy_saved_view, count_legacy_saved_views

from reckonsolve.data.database import Database
from reckonsolve.data.journal_migration import build_journal_statements
from reckonsolve.data.migrations import (
    MIGRATIONS,
    Migration,
    MigrationError,
    apply_migrations,
)
from reckonsolve.data.upgrade import UpgradeCancelledError, UpgradeReviewRequiredError

JOURNAL_MIGRATIONS = MIGRATIONS[:20] + (
    Migration(
        21,
        "retire Saved Views and record One-Shot action provenance",
        build_journal_statements(
            tuple(
                statement
                for migration in MIGRATIONS[:20]
                for statement in migration.statements
            )
        ),
    ),
)


@pytest.mark.parametrize("journal_mode", ("delete", "wal"))
def test_exclusive_snapshot_and_atomic_guards_exclude_already_open_writer(
    tmp_path, journal_mode
):
    path = tmp_path / "source.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:20])
    database.close()
    source = sqlite3.connect(path, autocommit=True, timeout=0)
    older = sqlite3.connect(path, autocommit=True, timeout=0)
    try:
        source.execute(f"PRAGMA journal_mode = {journal_mode}")
        older.execute("UPDATE app_settings SET stale_threshold_days = ?", (23,))
        source.execute("BEGIN EXCLUSIVE")
        image = source.serialize()
        recovery_path = tmp_path / "verified-recovery.sqlite3"
        recovery_path.write_bytes(image)
        recovery = sqlite3.connect(recovery_path, autocommit=True)
        try:
            assert recovery.execute("PRAGMA quick_check").fetchone() == ("ok",)
            assert recovery.execute("PRAGMA foreign_key_check").fetchall() == []
            assert recovery.execute(
                "SELECT stale_threshold_days FROM app_settings"
            ).fetchone() == (23,)
            assert recovery.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone() == (20,)
        finally:
            recovery.close()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            older.execute("UPDATE app_settings SET stale_threshold_days = ?", (24,))

        source.create_function("reckonsolve_writer_version", 0, lambda: 21)
        # The missing connection-local capability fails closed in a cached
        # baseline statement too: SQLite reparses after the schema changes.
        source.execute("""CREATE TRIGGER upgrade_writer_probe
            BEFORE UPDATE ON app_settings
            WHEN reckonsolve_writer_version() < 21
            BEGIN SELECT RAISE(ABORT, 'Unsupported writer'); END""")
        source.execute("COMMIT")
        with pytest.raises(
            sqlite3.OperationalError, match="reckonsolve_writer_version"
        ):
            older.execute("UPDATE app_settings SET stale_threshold_days = ?", (24,))
        source.execute("UPDATE app_settings SET stale_threshold_days = ?", (25,))
        assert source.execute(
            "SELECT stale_threshold_days FROM app_settings"
        ).fetchone() == (25,)
        assert recovery_path.read_bytes() == image
    finally:
        if source.in_transaction:
            source.execute("ROLLBACK")
        source.close()
        older.close()


def test_cancelled_upgrade_rolls_back_guards_and_preserves_older_writer(tmp_path):
    path = tmp_path / "cancel.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:20])
    database.close()
    source = sqlite3.connect(path, autocommit=True)
    older = sqlite3.connect(path, autocommit=True)
    original = path.read_bytes()
    try:
        source.execute("BEGIN EXCLUSIVE")
        source.create_function("reckonsolve_writer_version", 0, lambda: 21)
        source.execute("""CREATE TRIGGER cancelled_writer_probe
            BEFORE UPDATE ON app_settings
            WHEN reckonsolve_writer_version() < 21
            BEGIN SELECT RAISE(ABORT, 'Unsupported writer'); END""")
        source.execute("ROLLBACK")
        assert path.read_bytes() == original
        older.execute("UPDATE app_settings SET stale_threshold_days = 27")
        assert older.execute(
            "SELECT stale_threshold_days FROM app_settings"
        ).fetchone() == (27,)
    finally:
        source.close()
        older.close()


def legacy_view(path):
    """Use the genuine historical schema, not a stripped migration substitute."""
    from supported_fixtures import create_binary

    from reckonsolve.application.predictions import PredictionOperations

    database = Database.open(path, migrations=MIGRATIONS[:20])
    try:
        operations = PredictionOperations(database)
        prediction = create_binary(
            operations, "Supported history must survive", 67, tags=("History",)
        )
        add_legacy_saved_view(database, tags=("History",))
        return prediction
    finally:
        database.close()


@pytest.mark.parametrize("journal_mode", ("delete", "wal"))
def test_real_upgrade_has_verified_recovery_and_blocks_cached_old_writes(
    tmp_path, journal_mode
):
    path = tmp_path / "supported.sqlite3"
    prediction = legacy_view(path)
    older = sqlite3.connect(path, autocommit=True, timeout=0)
    older.execute(f"PRAGMA journal_mode = {journal_mode}")
    older.execute("UPDATE app_settings SET stale_threshold_days = ?", (23,))
    reviews = []

    def confirm(review):
        assert review.saved_view_count == 1
        recovery = Database.open(review.recovery, migrations=MIGRATIONS[:20])
        try:
            from reckonsolve.application.predictions import PredictionOperations

            old = PredictionOperations(recovery)
            assert count_legacy_saved_views(recovery) == 1
            assert old.get_prediction(prediction.prediction_id) == prediction
        finally:
            recovery.close()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            older.execute("UPDATE app_settings SET stale_threshold_days = ?", (24,))
        reviews.append(review)
        return True

    upgraded = None
    try:
        upgraded = Database.open(
            path, migrations=JOURNAL_MIGRATIONS, confirm_upgrade=confirm
        )
        assert upgraded.schema_version == 21
        with pytest.raises(
            sqlite3.OperationalError, match="reckonsolve_writer_version"
        ):
            older.execute("UPDATE app_settings SET stale_threshold_days = ?", (24,))
        with upgraded.transaction() as connection:
            assert (
                connection.execute("SELECT question FROM predictions").fetchone()[0]
                == prediction.question
            )
            assert (
                connection.execute("SELECT COUNT(*) FROM prediction_tags").fetchone()[0]
                == 1
            )
            assert (
                connection.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name = 'saved_views'"
                ).fetchone()
                is None
            )
            connection.execute("UPDATE app_settings SET stale_threshold_days = 25")
        assert len(reviews) == 1
        assert reviews[0].recovery.exists()
    finally:
        if upgraded is not None:
            upgraded.close()
        older.close()


def test_ordinary_open_and_direct_migration_cannot_silently_retire_views(tmp_path):
    path = tmp_path / "review.sqlite3"
    legacy_view(path)
    original = path.read_bytes()
    with pytest.raises(UpgradeReviewRequiredError):
        Database.open(path, migrations=JOURNAL_MIGRATIONS)
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.pre-upgrade-*.sqlite3")) == []
    raw = sqlite3.connect(path, autocommit=True)
    try:
        with pytest.raises(MigrationError, match="recovery-backed"):
            apply_migrations(raw, JOURNAL_MIGRATIONS)
    finally:
        raw.close()
    assert path.read_bytes() == original


@pytest.mark.parametrize("decision", ("cancel", "exception"))
def test_cancel_or_failed_review_preserves_active_schema_and_protected_copy(
    tmp_path, decision
):
    path = tmp_path / "cancel-review.sqlite3"
    legacy_view(path)
    original = path.read_bytes()
    recovery_paths = []

    def review(details):
        recovery_paths.append(details.recovery)
        if decision == "exception":
            raise RuntimeError("Injected review failure")
        return False

    error = UpgradeCancelledError if decision == "cancel" else RuntimeError
    with pytest.raises(error):
        Database.open(path, migrations=JOURNAL_MIGRATIONS, confirm_upgrade=review)
    assert path.read_bytes() == original
    assert len(recovery_paths) == 1
    assert recovery_paths[0].exists()


def test_all_application_tables_refuse_a_stale_connection_after_upgrade(tmp_path):
    path = tmp_path / "guards.sqlite3"
    legacy_view(path)
    older = sqlite3.connect(path, autocommit=True)
    upgraded = Database.open(
        path, migrations=JOURNAL_MIGRATIONS, confirm_upgrade=lambda _review: True
    )
    try:
        tables = [
            row[1]
            for row in older.execute("PRAGMA main.table_list")
            if row[2] == "table" and not row[1].startswith("sqlite_")
        ]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            column = older.execute(f"PRAGMA table_info({quoted})").fetchone()[1]
            quoted_column = '"' + column.replace('"', '""') + '"'
            for statement in (
                f"INSERT INTO {quoted} DEFAULT VALUES",
                f"UPDATE {quoted} SET {quoted_column} = {quoted_column} WHERE 0",
                f"DELETE FROM {quoted} WHERE 0",
            ):
                with pytest.raises(
                    sqlite3.OperationalError, match="reckonsolve_writer_version"
                ):
                    older.execute(statement)
        from reckonsolve.data.search_index import rebuild_search_index

        older.row_factory = sqlite3.Row
        older.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(
                sqlite3.OperationalError, match="reckonsolve_writer_version"
            ):
                rebuild_search_index(older)
        finally:
            older.execute("ROLLBACK")
        upgraded.check_search_index()
    finally:
        older.close()
        upgraded.close()


def test_existing_reader_can_prevent_exclusion_without_creating_a_backup(tmp_path):
    path = tmp_path / "active.sqlite3"
    legacy_view(path)
    reader = sqlite3.connect(path, autocommit=True)
    source = sqlite3.connect(path, autocommit=True, timeout=0)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM predictions").fetchone()
        from reckonsolve.data.upgrade import upgrade_with_recovery

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            upgrade_with_recovery(
                source, path, JOURNAL_MIGRATIONS, lambda _review: True
            )
        assert list(tmp_path.glob("*.pre-upgrade-*.sqlite3")) == []
        assert source.in_transaction is False
    finally:
        reader.execute("ROLLBACK")
        reader.close()
        source.close()


def test_process_interruption_during_upgrade_restores_the_old_active_journal(tmp_path):
    path = tmp_path / "interrupted.sqlite3"
    prediction = legacy_view(path)
    script = """
import os, sqlite3, sys
from pathlib import Path
from reckonsolve.data.journal_migration import build_journal_statements
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.upgrade import upgrade_with_recovery
from reckonsolve.data.writer_contract import register_writer
path = Path(sys.argv[1])
baseline = MIGRATIONS[:20]
statements = build_journal_statements(tuple(s for m in baseline for s in m.statements))
interrupted = statements[:1] + ('SELECT interrupt_upgrade()',) + statements[1:]
connection = sqlite3.connect(path, autocommit=True)
connection.row_factory = sqlite3.Row
register_writer(connection)
connection.create_function('interrupt_upgrade', 0, lambda: os._exit(87))
upgrade_with_recovery(connection, path, baseline + (Migration(21, 'interrupted proof', interrupted),), lambda review: True)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 87, result.stderr
    recovered = Database.open(path, migrations=MIGRATIONS[:20])
    try:
        from reckonsolve.application.predictions import PredictionOperations

        operations = PredictionOperations(recovered)
        assert recovered.schema_version == 20
        assert operations.get_prediction(prediction.prediction_id) == prediction
        assert count_legacy_saved_views(recovered) == 1
        with recovered.transaction() as connection:
            assert "source_action" not in [
                row[1]
                for row in connection.execute("PRAGMA table_info(one_shot_corrections)")
            ]
    finally:
        recovered.close()
    copies = list(tmp_path.glob("*.pre-upgrade-*.sqlite3"))
    assert len(copies) == 1
    backup = Database.open(copies[0], migrations=MIGRATIONS[:20])
    backup.close()


@pytest.mark.parametrize("version", (19, 20))
def test_upgrade_preserves_complete_four_contract_histories_and_old_recovery(
    tmp_path, version
):
    from dataclasses import replace
    from datetime import timedelta

    from journal_corpus import populate_mixed_corpus

    from reckonsolve.domain.predictions import PredictionStatus

    path = tmp_path / "mixed-history.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:version])
    operations, clock = populate_mixed_corpus(old, copies=1)
    for item in operations.browse_predictions().predictions:
        if (
            item.forecast_contract.is_one_shot
            and item.status is PredictionStatus.RESOLVED
        ):
            detail = operations.one_shots.get(item.prediction_id)
            clock.instant += timedelta(minutes=1)
            operations.one_shots.correct(
                detail,
                replace(
                    detail.record.effective,
                    postmortem="Historical transcription reflection",
                ),
            )
    add_legacy_saved_view(old, tags=("Research",))
    with old.read_snapshot() as connection:
        before = {}
        for (table,) in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
        ).fetchall():
            if table.startswith(
                ("sqlite_", "search_", "prediction_search")
            ) or table in ("schema_migrations", "saved_views", "saved_view_tags"):
                continue
            columns = tuple(
                row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
            )
            order = ",".join(str(index + 1) for index in range(len(columns)))
            before[table] = (
                columns,
                tuple(
                    tuple(row)
                    for row in connection.execute(
                        f'SELECT * FROM "{table}" ORDER BY {order}'
                    )
                ),
            )
    old.close()
    reviews = []

    def confirm(review):
        reviews.append(review)
        return True

    upgraded = Database.open(path, confirm_upgrade=confirm)
    try:
        assert upgraded.schema_version == 21 and len(reviews) == 1
        with upgraded.read_snapshot() as connection:
            assert (
                connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
                == 8
            )
            for table, (columns, rows) in before.items():
                quoted = ", ".join(f'"{column}"' for column in columns)
                order = ",".join(str(index + 1) for index in range(len(columns)))
                assert (
                    tuple(
                        tuple(row)
                        for row in connection.execute(
                            f'SELECT {quoted} FROM "{table}" ORDER BY {order}'
                        )
                    )
                    == rows
                ), table
            assert [
                row[0]
                for row in connection.execute(
                    "SELECT source_action FROM one_shot_corrections"
                )
            ] == ["transcription", "transcription"]
            assert not connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name IN ('saved_views','saved_view_tags')"
            ).fetchall()
    finally:
        upgraded.close()
    recovery = Database.open(reviews[0].recovery, migrations=MIGRATIONS[:version])
    try:
        assert count_legacy_saved_views(recovery) == 1
        assert recovery.schema_version == version
    finally:
        recovery.close()


@pytest.mark.parametrize("failure", ("backup", "ddl"))
def test_protection_or_migration_failure_preserves_source_and_old_writer(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "protected.sqlite3"
    legacy_view(path)
    original = path.read_bytes()
    callback = []
    migrations = JOURNAL_MIGRATIONS
    if failure == "backup":
        from pathlib import Path

        ordinary_open = Path.open

        def fail_backup(target, *args, **kwargs):
            if ".pre-upgrade-" in target.name:
                raise OSError("Injected recovery write failure")
            return ordinary_open(target, *args, **kwargs)

        monkeypatch.setattr(Path, "open", fail_backup)
        expected = OSError
    else:
        from dataclasses import replace

        migrations = (
            *JOURNAL_MIGRATIONS[:-1],
            replace(
                JOURNAL_MIGRATIONS[-1],
                statements=(*JOURNAL_MIGRATIONS[-1].statements, "INVALID SQL"),
            ),
        )
        expected = sqlite3.Error
    with pytest.raises(expected):
        Database.open(
            path,
            migrations=migrations,
            confirm_upgrade=lambda review: callback.append(review) or True,
        )
    assert path.read_bytes() == original
    if failure == "backup":
        assert callback == [] and not list(tmp_path.glob("*.pre-upgrade-*.sqlite3"))
    else:
        assert len(callback) == 1 and callback[0].recovery.is_file()
    older = sqlite3.connect(path, autocommit=True)
    try:
        older.execute("UPDATE app_settings SET stale_threshold_days=19")
    finally:
        older.close()


def test_current_archive_upgrade_boundary_does_not_take_exclusion_again(tmp_path):
    from reckonsolve.data.upgrade import upgrade_with_recovery

    path = tmp_path / "current.sqlite3"
    Database.open(path).close()
    reader = sqlite3.connect(path, autocommit=True)
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM app_settings").fetchall()
    try:
        current = sqlite3.connect(path, autocommit=True, timeout=0)
        current.row_factory = sqlite3.Row
        try:
            upgrade_with_recovery(current, path, MIGRATIONS, None)
            assert not current.in_transaction
        finally:
            current.close()
    finally:
        reader.execute("ROLLBACK")
        reader.close()
