from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from reckonsolve.private_build_smoke import run_private_build_smoke


def test_private_build_smoke_covers_restart_and_verified_backup(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "source" / "smoke.sqlite3"
    backup_path = tmp_path / "backup" / "smoke-backup.sqlite3"

    run_private_build_smoke(database_path, backup_path)

    assert database_path.is_file()
    assert backup_path.is_file()


def test_private_build_smoke_refuses_existing_or_shared_paths(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    existing_path = tmp_path / "existing.sqlite3"
    existing_path.write_bytes(b"preserve me")

    with pytest.raises(FileExistsError, match="already exists"):
        run_private_build_smoke(existing_path, tmp_path / "backup.sqlite3")
    with pytest.raises(ValueError, match="must differ"):
        run_private_build_smoke(tmp_path / "same.sqlite3", tmp_path / "same.sqlite3")

    assert existing_path.read_bytes() == b"preserve me"
