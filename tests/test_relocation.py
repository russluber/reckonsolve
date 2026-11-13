"""Native location/legacy-handle and complete-copy safety on disposable roots."""

import os
import runpy
import sqlite3
import stat
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from reckonsolve.application.relocation import RelocationService
from reckonsolve.data.database import Database
from reckonsolve.data.journal_location import (
    DATABASE_NAME,
    MoveRecoveryRequired,
    open_location,
)
from reckonsolve.data.location_native import (
    FileFence,
    LocationBusyError,
    LocationError,
    RuntimeLease,
)
from reckonsolve.data.relocation_snapshot import snapshot

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Native Windows relocation proof"
)


@pytest.fixture
def relocation(tmp_path):
    root = tmp_path / "Reckonsolve"
    root.mkdir()
    source = root / DATABASE_NAME
    seed = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/run_visual_review.py")
    )["_seed_performance_database"]
    seed(source, per_cohort=2)
    session = open_location(root, "Reckonsolve")
    session.store.mark_initialized()
    store = session.store
    session.close()
    destination = tmp_path / "Journal data"
    destination.mkdir()
    yield store, destination
    # Restore permissions only on this test's known disposable artifacts so
    # pytest can remove them; never clean up a real application's notices.
    for file in tmp_path.rglob("*"):
        assert file.resolve().is_relative_to(tmp_path.resolve())
        if file.is_file() and file.stat().st_file_attributes & 1:
            file.chmod(stat.S_IWRITE | stat.S_IREAD)


def test_complete_move_retains_exact_history_and_legacy_path_refuses_sqlite(relocation):
    store, folder = relocation
    expected = snapshot(store.default)
    service = RelocationService(store)
    review = service.preview(folder)
    result = service.execute(review)
    assert snapshot(result.destination) == expected
    assert snapshot(result.recovery) == expected
    assert store.default.read_bytes().startswith(b"RECKONSOLVE JOURNAL MOVED")
    assert store.default.stat().st_file_attributes & 1
    with pytest.raises(sqlite3.DatabaseError):
        Database.open(store.default)
    session = open_location(store.root, store.identity)
    assert session.database_path == result.destination
    assert session.presentation_path.parent == store.root
    session.close()


def test_shared_runtimes_and_exclusive_move_are_distinct(relocation):
    store, folder = relocation
    first = open_location(store.root, store.identity)
    second = open_location(store.root, store.identity)
    with pytest.raises(LocationBusyError), RuntimeLease(store.root, exclusive=True):
        pass
    service = RelocationService(store)
    review = service.preview(folder)
    with pytest.raises(LocationBusyError):
        service.execute(review)
    assert not (folder / DATABASE_NAME).exists()
    second.close()
    first.close()
    service.execute(review)


def test_existing_uncoordinated_writer_refuses_move_without_losing_authority(
    relocation,
):
    store, folder = relocation
    old = sqlite3.connect(store.default)
    original = snapshot(store.default)
    service = RelocationService(store)
    review = service.preview(folder)
    try:
        with pytest.raises(LocationBusyError):
            service.execute(review)
        assert snapshot(store.default) == original
        assert store.resolve() == store.default
        assert not (folder / DATABASE_NAME).exists()
    finally:
        old.close()
    service.execute(review)


@pytest.mark.parametrize(
    "phase",
    [
        "preparing",
        "recovery_verified",
        "copies_verified",
        "source_protected",
        "notice_written",
        "locator_installed",
    ],
)
def test_interrupted_phase_has_explicit_safe_recovery(relocation, phase):
    store, folder = relocation
    expected = snapshot(store.default)

    class Interrupted(BaseException):
        pass

    def interrupt(at):
        if at == phase:
            raise Interrupted()

    service = RelocationService(store, checkpoint=interrupt)
    review = service.preview(folder)
    with pytest.raises(Interrupted):
        service.execute(review)
    if phase in {"preparing", "recovery_verified", "copies_verified"}:
        # In-process failure before protection can safely retain source authority.
        assert store.resolve() == store.default
        assert snapshot(store.default) == expected
        return
    with pytest.raises(MoveRecoveryRequired):
        open_location(store.root, store.identity)
    # Process-independent protection survives without our native handle.
    legacy = sqlite3.connect(store.default)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            legacy.execute("CREATE TABLE divergent_copy(value)")
    finally:
        legacy.close()
    recovery = RelocationService(store)
    assert recovery.recovery_action() == "finish"
    result = recovery.recover("finish")
    assert snapshot(result.destination) == expected
    assert snapshot(result.recovery) == expected
    assert store.resolve() == review.destination


@pytest.mark.parametrize(
    "phase",
    [
        "preparing",
        "recovery_verified",
        "copies_verified",
        "source_protected",
        "notice_written",
        "locator_installed",
        "complete",
    ],
)
def test_process_exit_releases_handles_but_not_location_safety(relocation, phase):
    store, folder = relocation
    expected = snapshot(store.default)
    program = """
import os,sys
from pathlib import Path
from reckonsolve.data.journal_location import LocationStore
from reckonsolve.application.relocation import RelocationService
store=LocationStore(Path(sys.argv[1]),'Reckonsolve')
def stop(phase):
    if phase==sys.argv[3]: os._exit(86)
service=RelocationService(store,checkpoint=stop)
service.execute(service.preview(Path(sys.argv[2])))
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(store.root), str(folder), phase],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 86, result.stderr
    if phase == "complete":
        assert snapshot(store.resolve()) == expected
        return
    with pytest.raises(MoveRecoveryRequired):
        open_location(store.root, store.identity)
    service = RelocationService(store)
    action = service.recovery_action()
    service.recover(action)
    assert snapshot(store.resolve()) == expected
    assert action == (
        "keep"
        if phase in {"preparing", "recovery_verified", "copies_verified"}
        else "finish"
    )


def test_committed_wal_survives_protection_and_recovery(relocation):
    store, folder = relocation
    writer = Database.open(store.default)
    connection = writer._require_connection()
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    old_reader = sqlite3.connect(
        store.default.as_uri() + "?mode=ro", uri=True, autocommit=True
    )
    old_reader.execute("BEGIN")
    old_reader.execute("SELECT count(*) FROM tags").fetchone()
    with writer.transaction() as sql:
        sql.execute(
            "INSERT INTO tags(display_name, normalized_name) VALUES ('WAL committed', 'wal committed')"
        )
    writer.close()
    expected = snapshot(store.default)
    assert Path(str(store.default) + "-wal").stat().st_size > 0

    def interrupted(phase):
        if phase == "source_protected":
            raise RuntimeError("Interrupted after persistent protection")

    service = RelocationService(store, checkpoint=interrupted)
    try:
        with pytest.raises(RuntimeError, match="Interrupted"):
            service.execute(service.preview(folder))
        legacy = sqlite3.connect(store.default)
        try:
            with pytest.raises(sqlite3.DatabaseError):
                legacy.execute("CREATE TABLE forbidden_fork(a)")
        finally:
            legacy.close()
        result = RelocationService(store).recover("finish")
        assert snapshot(result.destination) == expected
        assert snapshot(result.recovery) == expected
    finally:
        old_reader.close()


def test_torn_notice_is_recoverable(relocation, monkeypatch):
    store, folder = relocation
    expected = snapshot(store.default)
    original = FileFence.write_notice

    def partial(self, data):
        original(self, data[:11])
        raise OSError("Interrupted notice write")

    monkeypatch.setattr(FileFence, "write_notice", partial)
    service = RelocationService(store)
    review = service.preview(folder)
    with pytest.raises(OSError, match="Interrupted"):
        service.execute(review)
    # The partially overwritten source remains read-only, with a verified copy.
    result = RelocationService(store).recover("finish")
    assert snapshot(result.destination) == expected


def test_configured_target_and_locator_loss_never_create_empty_fallback(relocation):
    store, folder = relocation
    service = RelocationService(store)
    result = service.execute(service.preview(folder))
    hidden = result.destination.with_name("unavailable.sqlite3")
    result.destination.rename(hidden)
    with pytest.raises(LocationError, match="unavailable"):
        open_location(store.root, store.identity)
    assert not result.destination.exists()
    hidden.rename(result.destination)
    store.locator_file.rename(store.root / "retained-location.json")
    with pytest.raises(LocationError, match="record is missing"):
        open_location(store.root, store.identity)
    assert store.default.read_bytes().startswith(b"RECKONSOLVE JOURNAL MOVED")


def test_conflicts_other_identity_and_existing_notices_are_not_overwritten(relocation):
    store, folder = relocation
    service = RelocationService(store)
    unrelated = folder / "keep.txt"
    unrelated.write_text("Unrelated file", encoding="utf-8")
    conflict = folder / DATABASE_NAME
    conflict.write_bytes(b"not a destination journal")
    with pytest.raises(LocationError, match="unused folder"):
        service.preview(folder)
    assert conflict.read_bytes() == b"not a destination journal"
    assert unrelated.read_text() == "Unrelated file"
    other = store.root.parent / "Reckonsolve Dev"
    other.mkdir()
    with pytest.raises(LocationError, match="settings folders"):
        service.preview(other)


@pytest.mark.parametrize("revision", ["bad5a09", "336abb5"])
def test_historical_gui_cli_entry_points_refuse_old_path_without_recreation(
    relocation, tmp_path, revision
):
    store, folder = relocation
    service = RelocationService(store)
    service.execute(service.preview(folder))
    before = store.default.read_bytes()
    available = subprocess.run(
        ["git", "cat-file", "-e", revision], capture_output=True, check=False
    )
    if available.returncode:
        pytest.skip(
            "Historical source is absent in this shallow checkout; native VFS refusal remains covered."
        )
    archive = subprocess.run(
        ["git", "archive", "--format=zip", revision, "src/reckonsolve"],
        capture_output=True,
        check=True,
    ).stdout
    legacy = tmp_path / revision
    with ZipFile(BytesIO(archive)) as zipped:
        assert all(not name.startswith(("/", "..")) for name in zipped.namelist())
        zipped.extractall(legacy)
    program = """
import sys,sqlite3
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from reckonsolve import app,cli,paths
paths.QStandardPaths.writableLocation=lambda kind:sys.argv[2]
assert cli.run(['list'])==1
try: app.create_runtime()
except sqlite3.DatabaseError: pass
else: raise AssertionError('Older GUI accepted the retired location')
"""
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-c", program, str(legacy / "src"), str(store.root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert store.default.read_bytes() == before


@pytest.mark.parametrize("which", ["identity", "locator", "state", "target_owner"])
def test_malformed_metadata_blocks_without_empty_fallback(relocation, which):
    store, folder = relocation
    service = RelocationService(store)
    result = service.execute(service.preview(folder))
    files = {
        "identity": store.identity_file,
        "locator": store.locator_file,
        "state": store.move_file,
        "target_owner": folder / "reckonsolve-journal.json",
    }
    files[which].write_text('{"version":true,"status":{}}', encoding="utf-8")
    with pytest.raises(LocationError):
        open_location(store.root, store.identity)
    assert store.default.read_bytes().startswith(b"RECKONSOLVE JOURNAL MOVED")
    assert result.destination.stat().st_size > 0


def test_changed_destination_stops_recovery_without_selecting_a_copy(relocation):
    store, folder = relocation

    def fail(phase):
        if phase == "source_protected":
            raise OSError("Interrupted")

    service = RelocationService(store, checkpoint=fail)
    review = service.preview(folder)
    with pytest.raises(OSError):
        service.execute(review)
    with review.destination.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(LocationError, match="could not be verified"):
        RelocationService(store).recover("finish")
    with pytest.raises(MoveRecoveryRequired):
        open_location(store.root, store.identity)


def test_hardlink_and_junction_aliases_are_refused(relocation):
    store, folder = relocation
    alias = store.root.parent / "hardlink.sqlite3"
    os.link(store.default, alias)
    with pytest.raises(LocationError, match="hard-linked"):
        RelocationService(store).preview(folder)
    alias.unlink()
    junction = store.root.parent / "Folder alias"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(folder)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(LocationError, match="without links"):
        RelocationService(store).preview(junction)


def test_insufficient_space_and_copy_failure_leave_source_authoritative(
    relocation, monkeypatch
):
    store, folder = relocation
    service = RelocationService(store)
    before = snapshot(store.default)
    from collections import namedtuple

    usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        "reckonsolve.application.relocation.shutil.disk_usage",
        lambda path: usage(100, 99, 1),
    )
    with pytest.raises(LocationError, match="free space"):
        service.preview(folder)
    monkeypatch.undo()
    review = service.preview(folder)

    def fail(path, image):
        raise PermissionError("Destination is not writable")

    monkeypatch.setattr("reckonsolve.application.relocation.write_image", fail)
    with pytest.raises(PermissionError, match="not writable"):
        service.execute(review)
    assert store.resolve() == store.default and snapshot(store.default) == before


def test_unsupported_archive_is_refused_before_move_artifacts(relocation):
    from test_legacy_retirement import historical_database, insert_retired

    from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
    from reckonsolve.data.migrations import MigrationError

    store, folder = relocation
    old = store.root.parent / "unsupported.sqlite3"
    historical_database(old, 20)
    insert_retired(old)
    # This fixture replacement is deliberate, confined to this disposable root.
    store.default.write_bytes(old.read_bytes())
    before = store.default.read_bytes()
    with pytest.raises((ForecastContractIntegrityError, MigrationError)):
        RelocationService(store).preview(folder)
    assert store.default.read_bytes() == before
    assert not store.move_file.exists() and not list(folder.iterdir())


def test_empty_configured_file_is_refused_without_initializing_a_new_journal(
    relocation,
):
    from reckonsolve.cli import create_runtime
    from reckonsolve.data.migrations import MigrationError
    from reckonsolve.identity import STABLE_APPLICATION

    store, folder = relocation
    service = RelocationService(store)
    result = service.execute(service.preview(folder))
    result.destination.write_bytes(b"")
    opened = None
    try:
        with pytest.raises(MigrationError, match="existing journal"):
            opened = create_runtime(
                identity=STABLE_APPLICATION, bootstrap_directory=store.root
            )
    finally:
        if opened is not None:
            opened.close()
    assert result.destination.read_bytes() == b""


def test_target_owner_generation_must_match_locator(relocation):
    from uuid import uuid4

    from reckonsolve.data.journal_location import read_json
    from reckonsolve.data.location_native import atomic_json

    store, folder = relocation
    service = RelocationService(store)
    service.execute(service.preview(folder))
    path = folder / "reckonsolve-journal.json"
    atomic_json(path, {**read_json(path), "move_id": str(uuid4())})
    with pytest.raises(LocationError, match="different move"):
        open_location(store.root, store.identity)


def test_supported_older_backup_still_upgrades_at_configured_location(relocation):
    from test_legacy_retirement import historical_database

    from reckonsolve.cli import create_runtime
    from reckonsolve.identity import STABLE_APPLICATION

    store, folder = relocation
    service = RelocationService(store)
    result = service.execute(service.preview(folder))
    backup = store.root.parent / "supported-schema20.sqlite3"
    historical_database(backup, 20)
    result.destination.write_bytes(backup.read_bytes())
    restored = create_runtime(
        identity=STABLE_APPLICATION, bootstrap_directory=store.root
    )
    try:
        assert restored.database.path == result.destination
        assert restored.database.schema_version == 21
        assert list(folder.glob("*.pre-upgrade-*.sqlite3"))
    finally:
        restored.close()


def test_inaccessible_move_metadata_is_not_treated_as_absent(relocation, monkeypatch):
    store, _folder = relocation
    store.save_state(store.base_state("idle"))
    original = Path.lstat

    def denied(path, *args, **kwargs):
        if path == store.move_file:
            raise PermissionError("Move record denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", denied)
    with pytest.raises(LocationError, match="inaccessible"):
        open_location(store.root, store.identity)
