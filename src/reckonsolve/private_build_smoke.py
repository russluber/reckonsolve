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

    previous_database = Database.open(database_path, migrations=MIGRATIONS[:12])
    try:
        previous_prediction = PredictionOperations(previous_database).create_prediction(
            "M31 v0.3 prediction survives the frozen migration?",
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
            "M31 private frozen-build Binary prediction?",
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
        operations.record_postmortem_skip(
            binary_prediction.prediction_id,
            expected_correction_id=None,
        )
        binary_history = operations.correct_binary_resolution(
            binary_prediction.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="Frozen corrected Binary facts survive.",
            postmortem="Frozen later Binary Postmortem survives.",
            correction_reason="Frozen smoke corrects the certified outcome.",
            expected_correction_id=None,
        )
        numeric_prediction = operations.create_numeric_prediction(
            "M31 private frozen-build Numeric prediction?",
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
        numeric_history = operations.correct_numeric_resolution(
            numeric_prediction.prediction_id,
            "8.5",
            resolution_notes="Frozen corrected Numeric facts survive.",
            postmortem="Frozen later Numeric Postmortem survives.",
            correction_reason="Frozen smoke corrects the exact observed value.",
            expected_correction_id=None,
        )
        needs_postmortem = operations.create_prediction(
            "M31 frozen Needs Postmortem prediction?",
            50,
            tags=("private-smoke",),
        )
        needs_postmortem = operations.resolve_prediction(
            needs_postmortem.prediction_id,
            BinaryOutcome.YES,
            expected_revision_id=needs_postmortem.current_revision_id,
            expected_metadata_version=needs_postmortem.metadata_version,
        )
        if binary_history.effective.outcome is not BinaryOutcome.NO:
            raise RuntimeError("The frozen Binary correction was not effective.")
        if numeric_history.effective.actual_value.decimal_value != Decimal("8.5"):
            raise RuntimeError("The frozen Numeric correction was not effective.")
        if operations.get_prediction_scorecard(binary_prediction.prediction_id) is None:
            raise RuntimeError("The frozen Binary scorecard was not available.")
        if (
            operations.get_prediction_scorecard(numeric_prediction.prediction_id)
            is None
        ):
            raise RuntimeError("The frozen Numeric scorecard was not available.")
        analytics = operations.get_forecast_analytics()
        if (
            analytics.binary_updates.paired_count != 1
            or analytics.numeric_updates.paired_count != 1
        ):
            raise RuntimeError("The frozen update analytics were incomplete.")
        queued_ids = {
            item.prediction_id
            for item in operations.get_dashboard().needs_postmortem_predictions
        }
        if queued_ids != {needs_postmortem.prediction_id}:
            raise RuntimeError("The frozen Needs Postmortem queue was incorrect.")
        operations.create_backup(backup_path)
        binary_prediction_id = binary_prediction.prediction_id
        numeric_prediction_id = numeric_prediction.prediction_id
        needs_postmortem_id = needs_postmortem.prediction_id
    finally:
        runtime.close()

    _verify_smoke_database(
        database_path,
        binary_prediction_id,
        numeric_prediction_id,
        previous_prediction_id,
        needs_postmortem_id,
    )
    _verify_smoke_database(
        backup_path,
        binary_prediction_id,
        numeric_prediction_id,
        previous_prediction_id,
        needs_postmortem_id,
    )


def _verify_smoke_database(
    database_path: Path,
    binary_prediction_id: int,
    numeric_prediction_id: int,
    previous_prediction_id: int,
    needs_postmortem_id: int,
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
        binary_history = operations.get_binary_resolution_history(binary_prediction_id)
        if (
            binary_history.original.outcome is not BinaryOutcome.YES
            or binary_history.effective.outcome is not BinaryOutcome.NO
            or len(binary_history.corrections) != 1
            or binary_history.postmortem_completion is None
            or binary_history.effective.postmortem
            != "Frozen later Binary Postmortem survives."
        ):
            raise RuntimeError("The frozen Binary terminal history did not survive.")
        if len(binary_revisions) != 2 or len(binary_timeline) != 4:
            raise RuntimeError("The frozen Binary history did not survive restart.")
        if (
            numeric_prediction.current_revision.lower_bound.decimal_value
            != Decimal("0.0")
            or numeric_prediction.current_revision.upper_bound.decimal_value
            != Decimal("9.0")
            or numeric_prediction.resolution is None
        ):
            raise RuntimeError("The frozen Numeric forecast did not survive restart.")
        numeric_history = operations.get_numeric_resolution_history(
            numeric_prediction_id
        )
        if (
            numeric_history.original.actual_value.decimal_value != Decimal("9.5")
            or numeric_history.effective.actual_value.decimal_value != Decimal("8.5")
            or len(numeric_history.corrections) != 1
            or numeric_history.effective.postmortem
            != "Frozen later Numeric Postmortem survives."
        ):
            raise RuntimeError("The frozen Numeric terminal history did not survive.")
        if len(numeric_revisions) != 2 or len(numeric_timeline) != 3:
            raise RuntimeError("The frozen Numeric history did not survive restart.")
        if operations.get_prediction_scorecard(binary_prediction_id) is None:
            raise RuntimeError("The frozen Binary scorecard did not survive restart.")
        if operations.get_prediction_scorecard(numeric_prediction_id) is None:
            raise RuntimeError("The frozen Numeric scorecard did not survive restart.")
        analytics = operations.get_forecast_analytics()
        if (
            analytics.binary_updates.paired_count != 1
            or analytics.numeric_updates.paired_count != 1
        ):
            raise RuntimeError("The frozen update analytics did not survive restart.")
        queued_ids = {
            item.prediction_id
            for item in operations.get_dashboard().needs_postmortem_predictions
        }
        if queued_ids != {needs_postmortem_id}:
            raise RuntimeError("The frozen Needs Postmortem queue did not survive.")
    finally:
        database.close()


__all__ = ["run_private_build_smoke"]
