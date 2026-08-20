"""PyInstaller entry point for the private Reckonsolve onedir build."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

_PRIVATE_SMOKE_ARGUMENT = "--private-build-smoke"


def _main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == _PRIVATE_SMOKE_ARGUMENT:
        database_path = Path(sys.argv[2])
        backup_path = Path(sys.argv[3])
        try:
            if not getattr(sys, "frozen", False):
                raise RuntimeError(
                    "The private build smoke must run from a frozen app."
                )
            from reckonsolve.private_build_smoke import run_private_build_smoke

            run_private_build_smoke(database_path, backup_path)
        except Exception:  # noqa: BLE001 - frozen smoke failures need diagnostics
            diagnostic_path = database_path.with_suffix(".error.txt")
            diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
            diagnostic_path.write_text(traceback.format_exc(), encoding="utf-8")
            return 1
        return 0

    from reckonsolve.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(_main())
