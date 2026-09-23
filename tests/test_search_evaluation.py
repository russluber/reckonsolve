"""The disposable search corpus uses supported forecast contracts."""

import os
import subprocess
import sys
from pathlib import Path


def test_search_evaluation_uses_current_model(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)}
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "tools" / "evaluate_search.py"),
            "--size",
            "100",
            "--repetitions",
            "1",
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    report = result.stdout
    assert "Predictions: 100" in report
    assert "Derived search documents: 300" in report
    assert "100 complete results" in report
