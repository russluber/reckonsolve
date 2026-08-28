from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from reckonsolve.application.errors import (
    DuplicateSavedViewNameError,
    SavedViewNotFoundError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveQuery,
    ArchiveSort,
    ArchiveTagMatchMode,
)
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = datetime(2026, 8, 28, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.instant


def _configuration(*, tags: tuple[str, ...] = ("Work",)) -> SavedViewConfiguration:
    return SavedViewConfiguration(
        search_text="evidence",
        match_mode=SearchMatchMode.ANY,
        include_superseded=True,
        archive_query=ArchiveQuery(
            status=PredictionStatus.LOCKED,
            prediction_type=PredictionType.BINARY,
            tags=tags,
            tag_match_mode=ArchiveTagMatchMode.ANY,
            attention=ArchiveAttention.NEEDS_ATTENTION,
            date_meaning=ArchiveDateMeaning.EXPECTED_RESOLUTION,
            date_start=date(2026, 8, 1),
            date_end=date(2026, 8, 31),
            sort=ArchiveSort.FORECAST_CONSIDERED_OLDEST,
        ),
    )


def test_saved_views_retain_dynamic_configuration_and_stable_tag_references(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock(), UTC)
    operations.create_prediction("Will evidence remain searchable?", 50, tags=("Work",))

    created = operations.create_saved_view("  Work evidence  ", _configuration())

    assert created.name == "Work evidence"
    assert created.normalized_name == "work evidence"
    assert created.configuration.match_mode is SearchMatchMode.ANY
    assert created.configuration.include_superseded is True
    assert created.configuration.archive_query.status is PredictionStatus.LOCKED
    assert created.configuration.archive_query.tags == ("Work",)
    assert created.tags[0].display_name == "Work"
    assert operations.list_saved_views() == (created,)

    updated = operations.update_saved_view(
        created.saved_view_id,
        _configuration(tags=()),
    )
    renamed = operations.rename_saved_view(updated.saved_view_id, "Evidence archive")
    assert renamed.name == "Evidence archive"
    assert renamed.tags == ()
    database.close()

    reopened_database = Database.open(path)
    reopened = PredictionOperations(reopened_database, FixedClock(), UTC)
    assert reopened.list_saved_views() == (renamed,)
    reopened_database.close()


def test_saved_view_configuration_reruns_against_current_prediction_membership(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    first = operations.create_prediction(
        "Will the first task finish?", 50, tags=("Work",)
    )
    saved = operations.create_saved_view(
        "Current work",
        SavedViewConfiguration(
            search_text="",
            match_mode=SearchMatchMode.ALL,
            include_superseded=False,
            archive_query=ArchiveQuery(tags=("Work",)),
        ),
    )

    def matching_ids() -> tuple[int, ...]:
        query = saved.configuration.archive_query
        return tuple(
            item.prediction_id
            for item in operations.browse_predictions(
                tags=query.tags,
                tag_match_mode=query.tag_match_mode,
                attention=query.attention,
                date_meaning=query.date_meaning,
                date_start=query.date_start,
                date_end=query.date_end,
                sort=query.sort,
            ).predictions
        )

    assert matching_ids() == (first.prediction_id,)
    second = operations.create_prediction(
        "Will the second task finish?", 50, tags=("Work",)
    )
    assert set(matching_ids()) == {first.prediction_id, second.prediction_id}
    database.close()


def test_saved_view_names_are_case_insensitive_and_deletion_has_no_history_effect(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    first = operations.create_saved_view("Focus", _configuration(tags=()))

    with pytest.raises(DuplicateSavedViewNameError):
        operations.create_saved_view(" focus ", _configuration(tags=()))

    operations.delete_saved_view(first.saved_view_id)

    assert operations.list_saved_views() == ()
    with pytest.raises(SavedViewNotFoundError):
        operations.delete_saved_view(first.saved_view_id)
    database.close()


def test_saved_views_are_recoverable_in_sqlite_backups_and_database_isolated(
    tmp_path,
) -> None:
    first_path = tmp_path / "first.sqlite3"
    first_database = Database.open(first_path)
    first = PredictionOperations(first_database, FixedClock(), UTC)
    first.create_saved_view("Backup view", _configuration(tags=()))
    backup_path = tmp_path / "saved-view-backup.sqlite3"
    first_database.backup_to(backup_path)
    first_database.close()

    recovered_database = Database.open(backup_path)
    recovered = PredictionOperations(recovered_database, FixedClock(), UTC)
    assert [view.name for view in recovered.list_saved_views()] == ["Backup view"]
    recovered_database.close()

    isolated_database = Database.open(tmp_path / "isolated.sqlite3")
    isolated = PredictionOperations(isolated_database, FixedClock(), UTC)
    assert isolated.list_saved_views() == ()
    isolated_database.close()
