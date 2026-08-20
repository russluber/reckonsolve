"""Private frozen-build verification against disposable data paths."""

from __future__ import annotations

from pathlib import Path

from reckonsolve.app import create_runtime
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS


def run_private_build_smoke(database_path: Path, backup_path: Path) -> None:
    """Exercise the frozen UI, core journal loop, backup, and restart persistence."""

    database_path = database_path.resolve()
    backup_path = backup_path.resolve()
    if database_path == backup_path:
        raise ValueError("Smoke database and backup paths must differ.")
    for path in (database_path, backup_path):
        if path.exists():
            raise FileExistsError(f"Private build smoke path already exists: {path}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    previous_database = Database.open(database_path, migrations=MIGRATIONS[:-1])
    try:
        previous_prediction = PredictionOperations(previous_database).create_prediction(
            "M12 pre-upgrade prediction survives the frozen migration?",
            55,
        )
        previous_prediction_id = previous_prediction.prediction_id
    finally:
        previous_database.close()

    runtime = create_runtime(
        argv=["Reckonsolve.exe", "--private-build-smoke"],
        database_path=database_path,
    )
    try:
        runtime.window.show()
        runtime.qt_app.processEvents()
        if not runtime.window.isVisible():
            raise RuntimeError("The private frozen main window did not become visible.")

        operations = PredictionOperations(runtime.database)
        if runtime.database.schema_version != MIGRATIONS[-1].version:
            raise RuntimeError("The frozen app did not apply its pending migration.")
        if operations.get_prediction(previous_prediction_id).probability_percent != 55:
            raise RuntimeError("The frozen migration did not preserve prior data.")
        prediction = operations.create_prediction(
            "M12 private frozen-build smoke prediction?",
            60,
            rationale="Initial smoke forecast.",
            tags=("private-smoke",),
        )
        prediction = operations.revise_forecast(
            prediction.prediction_id,
            70,
            rationale="Frozen revision path works.",
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        operations.add_journal_entry(
            prediction.prediction_id,
            "Frozen journal path works without changing probability.",
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        operations.create_backup(backup_path)
        prediction_id = prediction.prediction_id
    finally:
        runtime.close()

    _verify_smoke_database(database_path, prediction_id, previous_prediction_id)
    _verify_smoke_database(backup_path, prediction_id, previous_prediction_id)


def _verify_smoke_database(
    database_path: Path,
    prediction_id: int,
    previous_prediction_id: int,
) -> None:
    database = Database.open(database_path)
    try:
        operations = PredictionOperations(database)
        previous_prediction = operations.get_prediction(previous_prediction_id)
        prediction = operations.get_prediction(prediction_id)
        revisions = operations.list_forecast_revisions(prediction_id)
        timeline = operations.list_timeline(prediction_id)
        if prediction.probability_percent != 70:
            raise RuntimeError("The frozen smoke forecast did not survive restart.")
        if previous_prediction.probability_percent != 55:
            raise RuntimeError("The pre-upgrade forecast did not survive restart.")
        if len(revisions) != 2 or len(timeline) != 3:
            raise RuntimeError("The frozen smoke history did not survive restart.")
    finally:
        database.close()


__all__ = ["run_private_build_smoke"]
