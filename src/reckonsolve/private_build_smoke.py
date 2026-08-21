"""Private frozen-build verification against disposable data paths."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from reckonsolve.app import create_runtime
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS
from reckonsolve.domain.predictions import BinaryOutcome


def run_private_build_smoke(database_path: Path, backup_path: Path) -> None:
    """Exercise frozen migration, both forecast types, backup, and restart."""

    database_path = database_path.resolve()
    backup_path = backup_path.resolve()
    if database_path == backup_path:
        raise ValueError("Smoke database and backup paths must differ.")
    for path in (database_path, backup_path):
        if path.exists():
            raise FileExistsError(f"Private build smoke path already exists: {path}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    previous_database = Database.open(database_path, migrations=MIGRATIONS[:8])
    try:
        previous_prediction = PredictionOperations(previous_database).create_prediction(
            "M20 v0.1 prediction survives the frozen migration?",
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
        binary_prediction = operations.create_prediction(
            "M20 private frozen-build Binary prediction?",
            60,
            rationale="Initial Binary smoke forecast.",
            tags=("private-smoke",),
        )
        binary_prediction = operations.revise_forecast(
            binary_prediction.prediction_id,
            70,
            rationale="Frozen revision path works.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        operations.add_journal_entry(
            binary_prediction.prediction_id,
            "Frozen journal path works without changing probability.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        operations.add_forecast_review(
            binary_prediction.prediction_id,
            note="Frozen Binary review path works.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        binary_prediction = operations.resolve_prediction(
            binary_prediction.prediction_id,
            BinaryOutcome.YES,
            resolution_notes="Frozen Binary resolution path works.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        numeric_prediction = operations.create_numeric_prediction(
            "M20 private frozen-build Numeric prediction?",
            "days",
            1,
            "-1.5",
            "2.0",
            "7.0",
            80,
            rationale="Initial Numeric smoke forecast.",
            tags=("private-smoke",),
        )
        operations.add_numeric_forecast_review(
            numeric_prediction.prediction_id,
            note="Frozen Numeric review path works.",
            expected_revision_id=numeric_prediction.current_revision.revision_id,
            expected_metadata_version=numeric_prediction.metadata_version,
        )
        numeric_prediction = operations.revise_numeric_forecast(
            numeric_prediction.prediction_id,
            "0.0",
            "4.5",
            "9.0",
            80,
            rationale="Frozen Numeric revision path works.",
            expected_revision_id=numeric_prediction.current_revision.revision_id,
            expected_metadata_version=numeric_prediction.metadata_version,
        )
        numeric_prediction = operations.resolve_numeric_prediction(
            numeric_prediction.prediction_id,
            "9.5",
            resolution_notes="Frozen Numeric resolution path works.",
            expected_revision_id=numeric_prediction.current_revision.revision_id,
            expected_metadata_version=numeric_prediction.metadata_version,
        )
        operations.create_backup(backup_path)
        binary_prediction_id = binary_prediction.prediction_id
        numeric_prediction_id = numeric_prediction.prediction_id
    finally:
        runtime.close()

    _verify_smoke_database(
        database_path,
        binary_prediction_id,
        numeric_prediction_id,
        previous_prediction_id,
    )
    _verify_smoke_database(
        backup_path,
        binary_prediction_id,
        numeric_prediction_id,
        previous_prediction_id,
    )


def _verify_smoke_database(
    database_path: Path,
    binary_prediction_id: int,
    numeric_prediction_id: int,
    previous_prediction_id: int,
) -> None:
    database = Database.open(database_path)
    try:
        operations = PredictionOperations(database)
        previous_prediction = operations.get_prediction(previous_prediction_id)
        binary_prediction = operations.get_prediction(binary_prediction_id)
        numeric_prediction = operations.get_numeric_prediction(numeric_prediction_id)
        binary_revisions = operations.list_forecast_revisions(binary_prediction_id)
        binary_timeline = operations.list_timeline(binary_prediction_id)
        numeric_revisions = operations.list_numeric_forecast_revisions(
            numeric_prediction_id
        )
        numeric_timeline = operations.list_numeric_timeline(numeric_prediction_id)
        if binary_prediction.probability_percent != 70:
            raise RuntimeError("The frozen smoke forecast did not survive restart.")
        if previous_prediction.probability_percent != 55:
            raise RuntimeError("The pre-upgrade forecast did not survive restart.")
        if binary_prediction.resolution is None:
            raise RuntimeError("The frozen Binary resolution did not survive restart.")
        if len(binary_revisions) != 2 or len(binary_timeline) != 4:
            raise RuntimeError("The frozen Binary history did not survive restart.")
        if (
            numeric_prediction.current_revision.lower_bound.decimal_value
            != Decimal("0.0")
            or numeric_prediction.current_revision.upper_bound.decimal_value
            != Decimal("9.0")
            or numeric_prediction.resolution is None
            or numeric_prediction.resolution.actual_value.decimal_value
            != Decimal("9.5")
        ):
            raise RuntimeError("The frozen Numeric forecast did not survive restart.")
        if len(numeric_revisions) != 2 or len(numeric_timeline) != 3:
            raise RuntimeError("The frozen Numeric history did not survive restart.")
    finally:
        database.close()


__all__ = ["run_private_build_smoke"]
