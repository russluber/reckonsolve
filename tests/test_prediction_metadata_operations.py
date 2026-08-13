import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from reckonsolve.application.errors import (
    ApplicationError,
    ConcurrentPredictionUpdateError,
    MeaningChangeConfirmationRequired,
    PredictionNotFoundError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import PredictionStatus


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class CountingClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.instant


CREATED = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
CHANGED = datetime(2026, 8, 13, 20, 45, 12, 3456, tzinfo=UTC)


def _create_operations(tmp_path) -> tuple[Database, PredictionOperations, int]:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Will it happen?",
        60,
    )
    return (
        database,
        PredictionOperations(database, FixedClock(CHANGED)),
        created.prediction_id,
    )


def test_normal_metadata_and_tags_update_without_definition_history(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)

    updated = operations.update_metadata(
        prediction_id,
        question="Will it happen?",
        background="  Useful context  ",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=date(2027, 1, 3),
        tags=("Science", " science ", "Personal"),
        expected_metadata_version=1,
    )

    assert updated.background == "Useful context"
    assert updated.expected_resolution == date(2027, 1, 3)
    assert updated.tags == ("Personal", "Science")
    assert updated.updated_at == CHANGED
    assert updated.metadata_version == 2
    assert operations.list_definition_changes(prediction_id) == ()
    database.close()


def test_meaning_change_requires_confirmation_before_any_write(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)

    with pytest.raises(MeaningChangeConfirmationRequired) as error_info:
        operations.update_metadata(
            prediction_id,
            question="Will it definitely happen?",
            background="This must not sneak through",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("Blocked",),
            expected_metadata_version=1,
        )

    assert error_info.value.changed_fields == ("question",)
    unchanged = operations.get_prediction(prediction_id)
    assert unchanged.question == "Will it happen?"
    assert unchanged.background is None
    assert unchanged.tags == ()
    assert operations.list_definition_changes(prediction_id) == ()
    database.close()


def test_confirmation_required_does_not_acquire_a_change_timestamp(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Will it happen?",
        60,
    )
    clock = CountingClock(CHANGED)
    operations = PredictionOperations(database, clock)

    with pytest.raises(MeaningChangeConfirmationRequired):
        operations.update_metadata(
            created.prediction_id,
            question="Changed question?",
            background=None,
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=1,
        )

    assert clock.calls == 0
    database.close()


@pytest.mark.parametrize(
    ("changed_fields", "included", "excluded"),
    [
        (
            ("question",),
            ("may change what this prediction means", "create a new prediction"),
            ("become locked",),
        ),
        (
            ("forecast_deadline",),
            ("Forecast Deadline", "become locked"),
            ("may change what this prediction means", "create a new prediction"),
        ),
        (
            ("resolution_criteria", "forecast_deadline"),
            (
                "may change what this prediction means",
                "create a new prediction",
                "become locked",
            ),
            (),
        ),
    ],
)
def test_confirmation_error_explains_each_kind_of_consequence(
    changed_fields: tuple[str, ...],
    included: tuple[str, ...],
    excluded: tuple[str, ...],
) -> None:
    message = str(MeaningChangeConfirmationRequired(changed_fields))

    assert all(text in message for text in included)
    assert all(text not in message for text in excluded)


def test_confirmed_save_creates_one_complete_immutable_definition_record(
    tmp_path,
) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)

    updated = operations.update_metadata(
        prediction_id,
        question="Will it happen by 2027?",
        background="Context",
        resolution_criteria="Official result",
        forecast_deadline=date(2027, 1, 2),
        expected_resolution=date(2027, 1, 3),
        tags=("Time",),
        expected_metadata_version=1,
        confirm_meaning_change=True,
    )
    history = operations.list_definition_changes(prediction_id)

    assert updated.question == "Will it happen by 2027?"
    assert updated.metadata_version == 2
    assert len(history) == 1
    change = history[0]
    assert change.changed_fields == (
        "question",
        "resolution_criteria",
        "forecast_deadline",
    )
    assert change.old_question == "Will it happen?"
    assert change.new_question == "Will it happen by 2027?"
    assert change.old_resolution_criteria is None
    assert change.new_resolution_criteria == "Official result"
    assert change.old_forecast_deadline is None
    assert change.new_forecast_deadline == date(2027, 1, 2)
    assert change.changed_at == CHANGED
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE prediction_definition_changes SET new_question = 'Rewrite'"
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute("DELETE FROM prediction_definition_changes")
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT OR REPLACE INTO prediction_definition_changes (
                id,
                prediction_id,
                changed_at,
                old_question,
                new_question,
                old_resolution_criteria,
                new_resolution_criteria,
                old_forecast_deadline,
                new_forecast_deadline
            )
            SELECT
                id,
                prediction_id,
                changed_at,
                old_question,
                'Rewritten question',
                old_resolution_criteria,
                new_resolution_criteria,
                old_forecast_deadline,
                new_forecast_deadline
            FROM prediction_definition_changes
            """
        )
    with database.transaction() as connection:
        connection.execute("DELETE FROM predictions WHERE id = ?", (prediction_id,))
        history_count = connection.execute(
            "SELECT COUNT(*) FROM prediction_definition_changes"
        ).fetchone()[0]
    assert history_count == 0
    database.close()


def test_confirmed_update_and_definition_record_roll_back_together(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_definition_failure
            BEFORE INSERT ON prediction_definition_changes
            BEGIN
                SELECT RAISE(ABORT, 'forced definition failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced definition failure"):
        operations.update_metadata(
            prediction_id,
            question="Changed question?",
            background="Would otherwise change",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("WouldRollback",),
            expected_metadata_version=1,
            confirm_meaning_change=True,
        )

    unchanged = operations.get_prediction(prediction_id)
    assert unchanged.question == "Will it happen?"
    assert unchanged.background is None
    assert unchanged.tags == ()
    database.close()


def test_tag_failure_rolls_back_metadata_version_and_new_tag(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_tag_association_failure
            BEFORE INSERT ON prediction_tags
            BEGIN
                SELECT RAISE(ABORT, 'forced tag failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced tag failure"):
        operations.update_metadata(
            prediction_id,
            question="Will it happen?",
            background="Must roll back",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("Rollback",),
            expected_metadata_version=1,
        )

    unchanged = operations.get_prediction(prediction_id)
    assert unchanged.background is None
    assert unchanged.tags == ()
    assert unchanged.metadata_version == 1
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
    database.close()


def test_confirmation_retry_rejects_intervening_metadata_change(
    tmp_path,
    monkeypatch,
) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)
    original_update = operations._repository.update_metadata

    def update_after_intervening_write(*args, **kwargs):
        with database.transaction() as connection:
            connection.execute(
                """
                UPDATE predictions
                SET background = 'Intervening edit',
                    updated_at = '2026-08-13T20:45:13.003456Z'
                WHERE id = ?
                """,
                (prediction_id,),
            )
        return original_update(*args, **kwargs)

    monkeypatch.setattr(
        operations._repository,
        "update_metadata",
        update_after_intervening_write,
    )

    with pytest.raises(ConcurrentPredictionUpdateError):
        operations.update_metadata(
            prediction_id,
            question="Changed question?",
            background=None,
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=1,
            confirm_meaning_change=True,
        )

    assert operations.list_definition_changes(prediction_id) == ()
    database.close()


def test_effective_noop_writes_nothing_and_creates_no_history(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)
    first = operations.update_metadata(
        prediction_id,
        question="Will it happen?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=("Science", "Personal"),
        expected_metadata_version=1,
    )

    noop = operations.update_metadata(
        prediction_id,
        question="  Will it happen? ",
        background="   ",
        resolution_criteria="",
        forecast_deadline=None,
        expected_resolution=None,
        tags=("personal", "SCIENCE", "science"),
        expected_metadata_version=first.metadata_version,
    )

    assert noop.updated_at == first.updated_at
    assert noop.metadata_version == first.metadata_version == 2
    assert noop.tags == first.tags
    assert operations.list_definition_changes(prediction_id) == ()
    database.close()


def test_stale_unprotected_edit_cannot_erase_newer_metadata(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(database_path)
    second_database = Database.open(database_path)
    first_operations = PredictionOperations(first_database, FixedClock(CREATED))
    prediction_id = first_operations.create_prediction("Concurrent?", 50).prediction_id
    original = first_operations.get_prediction(prediction_id)
    second_operations = PredictionOperations(second_database, FixedClock(CHANGED))
    newer = second_operations.update_metadata(
        prediction_id,
        question=original.question,
        background="Newer background",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=("Newer",),
        expected_metadata_version=original.metadata_version,
    )

    with pytest.raises(ConcurrentPredictionUpdateError):
        first_operations.update_metadata(
            prediction_id,
            question=original.question,
            background=original.background,
            resolution_criteria=original.resolution_criteria,
            forecast_deadline=original.forecast_deadline,
            expected_resolution=date(2027, 1, 1),
            tags=original.tags,
            expected_metadata_version=original.metadata_version,
        )

    persisted = first_operations.get_prediction(prediction_id)
    assert persisted.background == "Newer background"
    assert persisted.expected_resolution is None
    assert persisted.tags == ("Newer",)
    assert persisted.metadata_version == newer.metadata_version == 2
    second_database.close()
    first_database.close()


def test_change_during_confirmation_pause_rejects_confirmed_retry(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(database_path)
    second_database = Database.open(database_path)
    first_operations = PredictionOperations(first_database, FixedClock(CREATED))
    prediction_id = first_operations.create_prediction("Original?", 50).prediction_id
    original = first_operations.get_prediction(prediction_id)

    with pytest.raises(MeaningChangeConfirmationRequired):
        first_operations.update_metadata(
            prediction_id,
            question="Clarified?",
            background=None,
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=original.metadata_version,
        )

    PredictionOperations(second_database, FixedClock(CHANGED)).update_metadata(
        prediction_id,
        question="Original?",
        background="Intervening edit",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=original.metadata_version,
    )

    with pytest.raises(ConcurrentPredictionUpdateError):
        first_operations.update_metadata(
            prediction_id,
            question="Clarified?",
            background=None,
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=original.metadata_version,
            confirm_meaning_change=True,
        )

    assert first_operations.get_prediction(prediction_id).question == "Original?"
    assert first_operations.list_definition_changes(prediction_id) == ()
    second_database.close()
    first_database.close()


def test_tags_reuse_first_display_spelling_case_insensitively(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    first_operations = PredictionOperations(database, FixedClock(CREATED))
    first_id = first_operations.create_prediction("First?", 50).prediction_id
    first_operations.update_metadata(
        first_id,
        question="First?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=("Straße",),
        expected_metadata_version=1,
    )
    first_operations.update_metadata(
        first_id,
        question="First?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=2,
    )
    second_id = first_operations.create_prediction("Second?", 50).prediction_id

    second = first_operations.update_metadata(
        second_id,
        question="Second?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=("STRASSE",),
        expected_metadata_version=1,
    )

    assert second.tags == ("Straße",)
    with database.transaction() as connection:
        tag_count = connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert tag_count == 1
    database.close()


def test_metadata_tags_and_definition_history_survive_reopen(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(database_path)
    first_operations = PredictionOperations(first_database, FixedClock(CREATED))
    prediction_id = first_operations.create_prediction("Original?", 45).prediction_id
    expected = PredictionOperations(
        first_database,
        FixedClock(CHANGED),
    ).update_metadata(
        prediction_id,
        question="Clarified?",
        background="Context",
        resolution_criteria="Official result",
        forecast_deadline=date(2027, 1, 2),
        expected_resolution=date(2027, 1, 3),
        tags=("Science", "Personal"),
        expected_metadata_version=1,
        confirm_meaning_change=True,
    )
    first_database.close()

    second_database = Database.open(database_path)
    reopened_operations = PredictionOperations(second_database, FixedClock(CHANGED))

    assert reopened_operations.get_prediction(prediction_id) == expected
    history = reopened_operations.list_definition_changes(prediction_id)
    assert len(history) == 1
    assert history[0].changed_fields == (
        "question",
        "resolution_criteria",
        "forecast_deadline",
    )
    second_database.close()


def test_past_deadline_displays_locked_but_deadline_day_is_open(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Deadline?",
        50,
    )
    deadline = date(2026, 8, 12)
    on_deadline = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 12, 23, tzinfo=UTC)),
    ).update_metadata(
        created.prediction_id,
        question="Deadline?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=deadline,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=1,
        confirm_meaning_change=True,
    )
    after_deadline = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 14, tzinfo=UTC)),
    ).get_prediction(created.prediction_id)

    assert on_deadline.status is PredictionStatus.OPEN
    assert after_deadline.status is PredictionStatus.LOCKED
    with database.transaction() as connection:
        persisted = connection.execute(
            "SELECT status FROM predictions WHERE id = ?",
            (created.prediction_id,),
        ).fetchone()[0]
    assert persisted == "open"
    database.close()


def test_deadline_uses_injected_local_calendar_date_across_utc_midnight(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    pacific = timezone(-timedelta(hours=7))
    operations = PredictionOperations(database, FixedClock(CREATED), pacific)
    created = operations.create_prediction("Local date?", 50)
    operations.update_metadata(
        created.prediction_id,
        question="Local date?",
        background=None,
        resolution_criteria=None,
        forecast_deadline=date(2026, 8, 12),
        expected_resolution=None,
        tags=(),
        expected_metadata_version=1,
        confirm_meaning_change=True,
    )

    still_deadline_day = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 13, 2, tzinfo=UTC)),
        pacific,
    ).get_prediction(created.prediction_id)
    next_local_day = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 13, 8, tzinfo=UTC)),
        pacific,
    ).get_prediction(created.prediction_id)

    assert still_deadline_day.status is PredictionStatus.OPEN
    assert next_local_day.status is PredictionStatus.LOCKED
    database.close()


def test_invalid_input_and_missing_prediction_are_application_errors(tmp_path) -> None:
    database, operations, prediction_id = _create_operations(tmp_path)

    with pytest.raises(ApplicationError) as error_info:
        operations.update_metadata(
            prediction_id,
            question="   ",
            background=None,
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=1,
        )
    assert isinstance(error_info.value, ValidationError)
    assert error_info.value.field == "question"
    with pytest.raises(PredictionNotFoundError):
        operations.get_prediction(999)
    with pytest.raises(PredictionNotFoundError):
        operations.list_definition_changes(999)
    database.close()
