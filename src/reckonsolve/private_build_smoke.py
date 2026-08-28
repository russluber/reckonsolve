"""Private frozen-build verification against disposable data paths."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from reckonsolve.app import create_runtime
from reckonsolve.application.errors import SearchUnavailableError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS
from reckonsolve.domain.browser import ArchiveQuery, ArchiveTagMatchMode
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.domain.saved_views import SavedView, SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode


@dataclass(frozen=True, slots=True)
class _SmokeState:
    previous_prediction_id: int
    binary_prediction_id: int
    numeric_prediction_id: int
    needs_postmortem_id: int
    saved_view_id: int


def run_private_build_smoke(database_path: Path, backup_path: Path) -> None:
    """Exercise frozen v0.5 migration, search, backup, repair, and restart."""

    database_path = database_path.resolve()
    backup_path = backup_path.resolve()
    if database_path == backup_path:
        raise ValueError("Smoke database and backup paths must differ.")
    for path in (database_path, backup_path):
        if path.exists():
            raise FileExistsError(f"Private build smoke path already exists: {path}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    previous_database = Database.open(database_path, migrations=MIGRATIONS[:13])
    try:
        previous_operations = PredictionOperations(previous_database)
        previous_prediction = previous_operations.create_prediction(
            "M38 v0.4 prediction survives the frozen migration?",
            55,
        )
        previous_prediction = previous_operations.resolve_prediction(
            previous_prediction.prediction_id,
            BinaryOutcome.YES,
            resolution_notes="Original v0.4 terminal fact.",
            expected_revision_id=previous_prediction.current_revision_id,
            expected_metadata_version=previous_prediction.metadata_version,
        )
        previous_operations.correct_binary_resolution(
            previous_prediction.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="Effective v0.4 terminal fact.",
            postmortem="Migrated v0.4 Postmortem.",
            correction_reason="The v0.4 smoke fixture corrects its outcome.",
            expected_correction_id=None,
        )
        previous_prediction_id = previous_prediction.prediction_id
        if previous_database.schema_version != 13:
            raise RuntimeError("The frozen smoke fixture was not a v0.4 database.")
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
        previous_history = operations.get_binary_resolution_history(
            previous_prediction_id
        )
        if (
            previous_history.original.outcome is not BinaryOutcome.YES
            or previous_history.effective.outcome is not BinaryOutcome.NO
            or len(previous_history.corrections) != 1
        ):
            raise RuntimeError("The frozen migration did not preserve v0.4 history.")
        runtime.database.check_search_index()
        binary_prediction = operations.create_prediction(
            "M38 private frozen-build Binary prediction?",
            60,
            rationale="Initial Binary smoke forecast.",
            tags=(
                "private-smoke",
                "Rename Source",
                "Merge Source",
                "Delete Source",
            ),
        )
        binary_prediction = operations.revise_forecast(
            binary_prediction.prediction_id,
            70,
            rationale="Frozen revision path works.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        journal = operations.add_journal_entry(
            binary_prediction.prediction_id,
            "Preliminary weather wording is superseded.",
            expected_revision_id=binary_prediction.current_revision_id,
            expected_metadata_version=binary_prediction.metadata_version,
        )
        operations.correct_journal_entry(
            binary_prediction.prediction_id,
            journal.entry_id,
            "Confirmed weather wording is effective.",
            expected_correction_id=None,
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
            "M38 frozen Needs Postmortem prediction?",
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

        saved_view = operations.create_saved_view(
            "Frozen weather view",
            SavedViewConfiguration(
                search_text="confirmed weather",
                match_mode=SearchMatchMode.ALL,
                include_superseded=False,
                archive_query=ArchiveQuery(
                    tags=("Rename Source", "Merge Source", "Delete Source"),
                    tag_match_mode=ArchiveTagMatchMode.ANY,
                ),
            ),
        )
        tag_ids = {tag.display_name: tag.tag_id for tag in operations.list_tags()}
        operations.rename_tag(
            operations.preview_tag_rename(tag_ids["Rename Source"], "Renamed Source")
        )
        operations.merge_tags(
            operations.preview_tag_merge(
                (tag_ids["Merge Source"],),
                tag_ids["private-smoke"],
            )
        )
        operations.delete_tag(operations.preview_tag_delete(tag_ids["Delete Source"]))
        if _saved_view_prediction_ids(operations, saved_view.saved_view_id) != (
            binary_prediction.prediction_id,
        ):
            raise RuntimeError("The frozen Saved View did not rerun dynamically.")
        if _search_prediction_ids(operations, "renamed source") != (
            binary_prediction.prediction_id,
        ):
            raise RuntimeError("The frozen tag rename did not refresh search.")
        if operations.search_predictions("preliminary weather").hits:
            raise RuntimeError("Superseded frozen text leaked into effective search.")
        if _search_prediction_ids(
            operations,
            "preliminary weather",
            include_superseded=True,
        ) != (binary_prediction.prediction_id,):
            raise RuntimeError("The frozen historical search omitted superseded text.")

        observer = Database.open(database_path)
        try:
            observer_ids = _search_prediction_ids(
                PredictionOperations(observer),
                "confirmed weather",
            )
        finally:
            observer.close()
        if observer_ids != (binary_prediction.prediction_id,):
            raise RuntimeError("An independent CLI-compatible read did not agree.")

        with runtime.database.transaction() as connection:
            connection.execute(
                "DELETE FROM prediction_search WHERE prediction_id = ?",
                (binary_prediction.prediction_id,),
            )
        try:
            operations.search_predictions("confirmed weather")
        except SearchUnavailableError:
            pass
        else:
            raise RuntimeError("A broken frozen search index appeared empty or usable.")
        operations.repair_search_index()
        if _search_prediction_ids(operations, "confirmed weather") != (
            binary_prediction.prediction_id,
        ):
            raise RuntimeError("The frozen search repair lost canonical text.")
        runtime.database.check_search_index()

        operations.create_backup(backup_path)
        state = _SmokeState(
            previous_prediction_id=previous_prediction_id,
            binary_prediction_id=binary_prediction.prediction_id,
            numeric_prediction_id=numeric_prediction.prediction_id,
            needs_postmortem_id=needs_postmortem.prediction_id,
            saved_view_id=saved_view.saved_view_id,
        )
    finally:
        runtime.close()

    _verify_smoke_database(database_path, state)
    _verify_smoke_database(backup_path, state)


def _verify_smoke_database(
    database_path: Path,
    state: _SmokeState,
) -> None:
    database = Database.open(database_path)
    try:
        operations = PredictionOperations(database)
        database.check_search_index()
        previous_prediction = operations.get_prediction(state.previous_prediction_id)
        binary_prediction = operations.get_prediction(state.binary_prediction_id)
        numeric_prediction = operations.get_numeric_prediction(
            state.numeric_prediction_id
        )
        binary_revisions = operations.list_forecast_revisions(
            state.binary_prediction_id
        )
        binary_timeline = operations.list_timeline(state.binary_prediction_id)
        numeric_revisions = operations.list_numeric_forecast_revisions(
            state.numeric_prediction_id
        )
        numeric_timeline = operations.list_numeric_timeline(state.numeric_prediction_id)
        if binary_prediction.probability_percent != 70:
            raise RuntimeError("The frozen smoke forecast did not survive restart.")
        if previous_prediction.probability_percent != 55:
            raise RuntimeError("The pre-upgrade forecast did not survive restart.")
        previous_history = operations.get_binary_resolution_history(
            state.previous_prediction_id
        )
        if (
            previous_history.original.outcome is not BinaryOutcome.YES
            or previous_history.effective.outcome is not BinaryOutcome.NO
            or previous_history.effective.postmortem != "Migrated v0.4 Postmortem."
        ):
            raise RuntimeError("The migrated v0.4 terminal history did not survive.")
        if binary_prediction.resolution is None:
            raise RuntimeError("The frozen Binary resolution did not survive restart.")
        binary_history = operations.get_binary_resolution_history(
            state.binary_prediction_id
        )
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
            state.numeric_prediction_id
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
        if operations.get_prediction_scorecard(state.binary_prediction_id) is None:
            raise RuntimeError("The frozen Binary scorecard did not survive restart.")
        if operations.get_prediction_scorecard(state.numeric_prediction_id) is None:
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
        if queued_ids != {state.needs_postmortem_id}:
            raise RuntimeError("The frozen Needs Postmortem queue did not survive.")
        tag_names = {tag.display_name for tag in operations.list_tags()}
        if not {"private-smoke", "Renamed Source"}.issubset(tag_names):
            raise RuntimeError("The frozen tag-library changes did not survive.")
        if {"Rename Source", "Merge Source", "Delete Source"} & tag_names:
            raise RuntimeError("A removed frozen tag unexpectedly survived.")
        if _saved_view_prediction_ids(operations, state.saved_view_id) != (
            state.binary_prediction_id,
        ):
            raise RuntimeError("The frozen Saved View did not survive restart.")
        if _search_prediction_ids(operations, "confirmed weather") != (
            state.binary_prediction_id,
        ):
            raise RuntimeError("Effective frozen search did not survive restart.")
        if operations.search_predictions("preliminary weather").hits:
            raise RuntimeError("Superseded text became effective after restart.")
        if _search_prediction_ids(
            operations,
            "preliminary weather",
            include_superseded=True,
        ) != (state.binary_prediction_id,):
            raise RuntimeError("Historical frozen search did not survive restart.")
    finally:
        database.close()


def _search_prediction_ids(
    operations: PredictionOperations,
    text: str,
    *,
    include_superseded: bool = False,
) -> tuple[int, ...]:
    return tuple(
        hit.prediction.prediction_id
        for hit in operations.search_predictions(
            text,
            include_superseded=include_superseded,
        ).hits
    )


def _saved_view_prediction_ids(
    operations: PredictionOperations,
    saved_view_id: int,
) -> tuple[int, ...]:
    view: SavedView | None = next(
        (
            candidate
            for candidate in operations.list_saved_views()
            if candidate.saved_view_id == saved_view_id
        ),
        None,
    )
    if view is None:
        raise RuntimeError("The frozen Saved View is missing.")
    configuration = view.configuration
    query = configuration.archive_query
    return tuple(
        hit.prediction.prediction_id
        for hit in operations.search_predictions(
            configuration.search_text,
            match_mode=configuration.match_mode,
            include_superseded=configuration.include_superseded,
            status=query.status,
            prediction_type=query.prediction_type,
            tags=query.tags,
            tag_match_mode=query.tag_match_mode,
            attention=query.attention,
            date_meaning=query.date_meaning,
            date_start=query.date_start,
            date_end=query.date_end,
            sort=query.sort,
        ).hits
    )


__all__ = ["run_private_build_smoke"]
