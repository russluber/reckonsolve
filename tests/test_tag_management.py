import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO

import pytest

from reckonsolve.application.errors import (
    ConcurrentPredictionUpdateError,
    ConcurrentTagLibraryUpdateError,
    DuplicateTagNameError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import run as run_cli
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import ArchiveQuery
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode

NOW = datetime(2026, 8, 29, 18, 30, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = NOW

    def now(self) -> datetime:
        return self.instant


def _saved_view_configuration(tags: tuple[str, ...]) -> SavedViewConfiguration:
    return SavedViewConfiguration(
        search_text="",
        match_mode=SearchMatchMode.ALL,
        include_superseded=False,
        archive_query=ArchiveQuery(tags=tags),
    )


def _tag_id(operations: PredictionOperations, name: str) -> int:
    return next(
        tag.tag_id
        for tag in operations.list_tags()
        if tag.normalized_name == name.casefold()
    )


def test_global_tag_rename_retains_identity_relationships_and_history(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    prediction = operations.create_prediction(
        "Will the first task finish?",
        55,
        tags=("Work",),
    )
    operations.create_prediction(
        "Will the personal task finish?", 45, tags=("Personal",)
    )
    saved = operations.create_saved_view(
        "Work view",
        _saved_view_configuration(("Work",)),
    )
    work_id = _tag_id(operations, "Work")
    revision_count = len(operations.list_forecast_revisions(prediction.prediction_id))

    preview = operations.preview_tag_rename(work_id, "Career")

    assert preview.context.item.display_name == "Work"
    assert preview.prediction_count == 1
    operations.rename_tag(preview)

    renamed = next(tag for tag in operations.list_tags() if tag.tag_id == work_id)
    assert renamed.display_name == "Career"
    assert renamed.prediction_count == 1
    updated = operations.get_prediction(prediction.prediction_id)
    assert updated.tags == ("Career",)
    assert updated.metadata_version == prediction.metadata_version + 1
    assert not updated.deletion_allowed
    assert (
        len(operations.list_forecast_revisions(prediction.prediction_id))
        == revision_count
    )
    assert operations.list_definition_changes(prediction.prediction_id) == ()
    retained_view = operations.list_saved_views()[0]
    assert retained_view.saved_view_id == saved.saved_view_id
    assert retained_view.configuration.archive_query.tags == ("Career",)
    assert retained_view.tags[0].tag_id == work_id
    assert [
        hit.prediction.prediction_id
        for hit in operations.search_predictions("Career").hits
    ] == [prediction.prediction_id]
    assert operations.search_predictions("Work").hits == ()

    with pytest.raises(DuplicateTagNameError, match="Merge Tags"):
        operations.preview_tag_rename(work_id, "personal")

    capitalization = operations.preview_tag_rename(work_id, "CAREER")
    operations.rename_tag(capitalization)
    assert next(
        tag for tag in operations.list_tags() if tag.tag_id == work_id
    ).display_name == ("CAREER")
    database.close()


def test_tag_merge_unions_and_deduplicates_predictions_and_saved_views(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock(), UTC)
    first = operations.create_prediction(
        "Will alpha finish?", 50, tags=("Source A", "Target")
    )
    second = operations.create_numeric_prediction(
        "How many items will beta finish?",
        "items",
        0,
        1,
        2,
        3,
        80,
        tags=("Source B",),
    )
    target_only = operations.create_prediction(
        "Will gamma finish?", 50, tags=("Target",)
    )
    operations.create_saved_view(
        "Merged work",
        _saved_view_configuration(("Source A", "Source B", "Target")),
    )
    source_ids = (_tag_id(operations, "Source A"), _tag_id(operations, "Source B"))
    target_id = _tag_id(operations, "Target")

    preview = operations.preview_tag_merge(source_ids, target_id)
    observer_database = Database.open(path)
    observer_operations = PredictionOperations(observer_database, FixedClock(), UTC)

    assert preview.prediction_count == 2
    assert preview.saved_view_count == 1
    operations.merge_tags(preview)

    assert {tag.normalized_name for tag in operations.list_tags()} == {"target"}
    assert operations.get_prediction(first.prediction_id).tags == ("Target",)
    assert operations.get_numeric_prediction(second.prediction_id).tags == ("Target",)
    assert operations.get_prediction(target_only.prediction_id).metadata_version == (
        target_only.metadata_version
    )
    assert operations.get_prediction(first.prediction_id).metadata_version == 2
    assert operations.get_numeric_prediction(second.prediction_id).metadata_version == 2
    merged_view = operations.list_saved_views()[0]
    assert merged_view.configuration.archive_query.tags == ("Target",)
    assert merged_view.tags[0].tag_id == target_id
    assert operations.search_predictions('"Source A"').hits == ()
    assert operations.search_predictions('"Source B"').hits == ()
    assert {
        hit.prediction.prediction_id
        for hit in operations.search_predictions("Target").hits
    } == {first.prediction_id, second.prediction_id, target_only.prediction_id}
    assert [tag.display_name for tag in observer_operations.list_tags()] == ["Target"]
    assert observer_operations.get_numeric_prediction(second.prediction_id).tags == (
        "Target",
    )
    cli_output = StringIO()
    assert (
        run_cli(
            ["show", str(first.prediction_id)],
            database_path=path,
            stdout=cli_output,
            stderr=StringIO(),
        )
        == 0
    )
    assert "Tags: Target" in cli_output.getvalue()
    assert "Source A" not in cli_output.getvalue()
    database.check_search_index()
    backup_path = tmp_path / "tag-management-backup.sqlite3"
    operations.create_backup(backup_path)
    observer_database.close()
    database.close()

    reopened = Database.open(path)
    reopened_operations = PredictionOperations(reopened, FixedClock(), UTC)
    assert [tag.display_name for tag in reopened_operations.list_tags()] == ["Target"]
    assert reopened_operations.list_saved_views()[0].tags[0].tag_id == target_id
    reopened.close()

    backup = Database.open(backup_path)
    backup_operations = PredictionOperations(backup, FixedClock(), UTC)
    assert [tag.display_name for tag in backup_operations.list_tags()] == ["Target"]
    assert backup_operations.list_saved_views()[0].tags[0].tag_id == target_id
    backup.close()


def test_tag_delete_removes_current_relationships_and_rejects_stale_metadata(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    prediction = operations.create_prediction(
        "Will this task finish?",
        60,
        tags=("Delete Me", "Keep"),
    )
    operations.create_saved_view(
        "Disposable condition",
        _saved_view_configuration(("Delete Me",)),
    )
    reviewed = operations.get_prediction(prediction.prediction_id)
    preview = operations.preview_tag_delete(_tag_id(operations, "Delete Me"))

    assert preview.prediction_count == 1
    assert preview.saved_view_count == 1
    operations.delete_tag(preview)

    updated = operations.get_prediction(prediction.prediction_id)
    assert updated.tags == ("Keep",)
    assert updated.metadata_version == 2
    assert not updated.deletion_allowed
    assert operations.list_saved_views()[0].configuration.archive_query.tags == ()
    assert operations.search_predictions('"Delete Me"').hits == ()
    assert operations.list_definition_changes(prediction.prediction_id) == ()
    with pytest.raises(ConcurrentPredictionUpdateError):
        operations.update_metadata(
            prediction.prediction_id,
            question=reviewed.question,
            background="Stale edit",
            resolution_criteria=reviewed.resolution_criteria,
            forecast_deadline=reviewed.forecast_deadline,
            expected_resolution=reviewed.expected_resolution,
            tags=reviewed.tags,
            expected_metadata_version=reviewed.metadata_version,
        )
    database.close()


def test_tag_management_context_and_transaction_failure_leave_state_unchanged(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    prediction = operations.create_prediction(
        "Will rollback preserve this?",
        50,
        tags=("Source", "Target"),
    )
    source_id = _tag_id(operations, "Source")
    target_id = _tag_id(operations, "Target")
    stale_preview = operations.preview_tag_rename(source_id, "Renamed")
    current_preview = operations.preview_tag_rename(source_id, "Current")
    operations.rename_tag(current_preview)

    with pytest.raises(ConcurrentTagLibraryUpdateError):
        operations.rename_tag(stale_preview)

    current_source_id = _tag_id(operations, "Current")
    merge_preview = operations.preview_tag_merge((current_source_id,), target_id)
    with database.transaction() as connection:
        connection.execute(
            f"""
            CREATE TRIGGER fail_test_tag_delete
            BEFORE DELETE ON tags
            WHEN OLD.id = {current_source_id}
            BEGIN
                SELECT RAISE(ABORT, 'simulated tag merge failure');
            END
            """
        )

    before = operations.get_prediction(prediction.prediction_id)
    with pytest.raises(sqlite3.IntegrityError, match="simulated tag merge failure"):
        operations.merge_tags(merge_preview)

    after = operations.get_prediction(prediction.prediction_id)
    assert after.tags == before.tags == ("Current", "Target")
    assert after.metadata_version == before.metadata_version
    assert {tag.display_name for tag in operations.list_tags()} == {
        "Current",
        "Target",
    }
    database.check_search_index()
    database.close()


def test_tag_library_filter_includes_retained_unassociated_tags(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    prediction = operations.create_prediction(
        "Will this temporary label be retained?", 50, tags=("Temporary",)
    )
    operations.update_metadata(
        prediction.prediction_id,
        question=prediction.question,
        background=prediction.background,
        resolution_criteria=prediction.resolution_criteria,
        forecast_deadline=prediction.forecast_deadline,
        expected_resolution=prediction.expected_resolution,
        tags=(),
        expected_metadata_version=prediction.metadata_version,
    )

    filtered = operations.list_tags("EMPOR")

    assert len(filtered) == 1
    assert filtered[0].display_name == "Temporary"
    assert filtered[0].prediction_count == 0
    assert filtered[0].saved_view_count == 0
    database.close()
