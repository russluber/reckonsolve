import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from reckonsolve.application.errors import (
    ConcurrentPredictionUpdateError,
    MeaningChangeConfirmationRequired,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    NumericPrediction,
    PredictionStatus,
    PredictionType,
)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


CREATED = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
CHANGED = datetime(2026, 8, 22, 20, 45, tzinfo=UTC)


def _create_numeric(
    database: Database,
    *,
    question: str = "How many days will this take?",
    forecast_deadline: date | None = None,
) -> tuple[PredictionOperations, NumericPrediction]:
    operations = PredictionOperations(database, FixedClock(CREATED), UTC)
    created = operations.create_numeric_prediction(
        question,
        "days",
        2,
        "-1.25",
        "3.50",
        "10.75",
        80,
        rationale="Initial numeric rationale",
        forecast_deadline=forecast_deadline,
        tags=("Original",),
    )
    return operations, created


def test_numeric_ordinary_metadata_edit_preserves_forecast_and_refreshes_search(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    _, created = _create_numeric(database)
    operations = PredictionOperations(database, FixedClock(CHANGED), UTC)
    revisions_before = operations.list_numeric_forecast_revisions(created.prediction_id)

    updated = operations.update_metadata(
        created.prediction_id,
        question=created.question,
        background="A searchable numeric background token",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=date(2026, 9, 3),
        tags=("Planning", "planning"),
        expected_metadata_version=created.metadata_version,
    )

    assert isinstance(updated, NumericPrediction)
    assert updated.background == "A searchable numeric background token"
    assert updated.expected_resolution == date(2026, 9, 3)
    assert updated.tags == ("Planning",)
    assert updated.metadata_version == 2
    assert updated.unit == created.unit
    assert updated.decimal_places == created.decimal_places
    assert updated.current_revision == created.current_revision
    assert (
        operations.list_numeric_forecast_revisions(created.prediction_id)
        == revisions_before
    )
    assert operations.list_definition_changes(created.prediction_id) == ()
    results = operations.search_predictions(
        "searchable numeric background",
        prediction_type=PredictionType.NUMERIC,
    )
    assert [hit.prediction.prediction_id for hit in results.hits] == [
        created.prediction_id
    ]
    database.close()

    reopened_database = Database.open(path)
    reopened = PredictionOperations(
        reopened_database,
        FixedClock(CHANGED),
        UTC,
    ).get_numeric_prediction(created.prediction_id)
    assert reopened == updated
    reopened_database.close()


def test_numeric_protected_edit_requires_confirmation_and_appends_definition(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    _, created = _create_numeric(database, question="Original numeric question?")
    operations = PredictionOperations(database, FixedClock(CHANGED), UTC)

    with pytest.raises(MeaningChangeConfirmationRequired) as error_info:
        operations.update_metadata(
            created.prediction_id,
            question="Clarified numeric question?",
            background="Must wait for confirmation",
            resolution_criteria="Use the certified numeric result.",
            forecast_deadline=CREATED.date(),
            expected_resolution=None,
            tags=("Confirmed",),
            expected_metadata_version=created.metadata_version,
        )

    assert error_info.value.changed_fields == (
        "question",
        "resolution_criteria",
        "forecast_deadline",
    )
    unchanged = operations.get_numeric_prediction(created.prediction_id)
    assert unchanged.question == created.question
    assert unchanged.background is None
    assert unchanged.tags == created.tags
    assert operations.list_definition_changes(created.prediction_id) == ()

    updated = operations.update_metadata(
        created.prediction_id,
        question="Clarified numeric question?",
        background="Confirmed context",
        resolution_criteria="Use the certified numeric result.",
        forecast_deadline=CREATED.date(),
        expected_resolution=None,
        tags=("Confirmed",),
        expected_metadata_version=created.metadata_version,
        confirm_meaning_change=True,
    )

    assert isinstance(updated, NumericPrediction)
    assert updated.status is PredictionStatus.LOCKED
    assert updated.unit == "days"
    assert updated.decimal_places == 2
    assert updated.current_revision == created.current_revision
    history = operations.list_definition_changes(created.prediction_id)
    assert len(history) == 1
    assert history[0].changed_fields == error_info.value.changed_fields
    assert history[0].old_question == "Original numeric question?"
    assert history[0].new_question == "Clarified numeric question?"
    assert history[0].old_forecast_deadline is None
    assert history[0].new_forecast_deadline == CREATED.date()
    assert operations.search_predictions("original numeric question").hits == ()
    historical = operations.search_predictions(
        "original numeric question",
        include_superseded=True,
    )
    assert [hit.prediction.prediction_id for hit in historical.hits] == [
        created.prediction_id
    ]
    database.close()


def test_numeric_effective_noop_and_validation_failure_write_nothing(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    _, created = _create_numeric(database)
    operations = PredictionOperations(database, FixedClock(CHANGED), UTC)

    noop = operations.update_metadata(
        created.prediction_id,
        question=f"  {created.question}  ",
        background="   ",
        resolution_criteria="",
        forecast_deadline=None,
        expected_resolution=None,
        tags=("original", "ORIGINAL"),
        expected_metadata_version=created.metadata_version,
    )

    assert isinstance(noop, NumericPrediction)
    assert noop.updated_at == created.updated_at
    assert noop.metadata_version == created.metadata_version
    assert noop.current_revision == created.current_revision
    assert operations.list_definition_changes(created.prediction_id) == ()

    with pytest.raises(ValidationError, match="Question is required"):
        operations.update_metadata(
            created.prediction_id,
            question="   ",
            background="Should not save",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("Blocked",),
            expected_metadata_version=created.metadata_version,
        )

    unchanged = operations.get_numeric_prediction(created.prediction_id)
    assert unchanged == created
    assert operations.list_definition_changes(created.prediction_id) == ()
    database.close()


def test_numeric_metadata_edit_rejects_stale_cross_connection_context(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    second_database = Database.open(path)
    first_operations, created = _create_numeric(first_database)
    second_operations = PredictionOperations(
        second_database,
        FixedClock(CHANGED),
        UTC,
    )
    newer = second_operations.update_metadata(
        created.prediction_id,
        question=created.question,
        background="Newer Numeric context",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=("Newer",),
        expected_metadata_version=created.metadata_version,
    )

    with pytest.raises(ConcurrentPredictionUpdateError):
        first_operations.update_metadata(
            created.prediction_id,
            question=created.question,
            background="Stale context",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("Stale",),
            expected_metadata_version=created.metadata_version,
        )

    persisted = first_operations.get_numeric_prediction(created.prediction_id)
    assert persisted.background == "Newer Numeric context"
    assert persisted.tags == ("Newer",)
    assert persisted.metadata_version == newer.metadata_version == 2
    second_database.close()
    first_database.close()


@pytest.mark.parametrize("lifecycle", ["open", "locked", "resolved", "invalid"])
def test_numeric_metadata_edit_is_available_in_every_lifecycle(
    tmp_path,
    lifecycle: str,
) -> None:
    database = Database.open(tmp_path / f"{lifecycle}.sqlite3")
    initial_deadline = CREATED.date() if lifecycle == "locked" else None
    _, created = _create_numeric(database, forecast_deadline=initial_deadline)
    operations = PredictionOperations(database, FixedClock(CHANGED), UTC)
    current = operations.get_numeric_prediction(created.prediction_id)
    if lifecycle == "resolved":
        current = operations.resolve_numeric_prediction(
            created.prediction_id,
            "4.25",
            expected_revision_id=current.current_revision.revision_id,
            expected_metadata_version=current.metadata_version,
        )
    elif lifecycle == "invalid":
        current = operations.invalidate_numeric_prediction(
            created.prediction_id,
            reason="No longer resolvable",
            expected_revision_id=current.current_revision.revision_id,
            expected_metadata_version=current.metadata_version,
        )

    original_revision = current.current_revision
    original_resolution = current.resolution
    original_invalidation = current.invalidation
    updated = operations.update_metadata(
        created.prediction_id,
        question=current.question,
        background=f"Edited while {lifecycle}",
        resolution_criteria=current.resolution_criteria,
        forecast_deadline=current.forecast_deadline,
        expected_resolution=current.expected_resolution,
        tags=current.tags,
        expected_metadata_version=current.metadata_version,
    )

    assert isinstance(updated, NumericPrediction)
    assert updated.status.value == lifecycle
    assert updated.background == f"Edited while {lifecycle}"
    assert updated.current_revision == original_revision
    assert updated.resolution == original_resolution
    assert updated.invalidation == original_invalidation
    database.close()


def test_numeric_definition_failure_rolls_back_metadata_tags_and_search(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    _, created = _create_numeric(database, question="Original searchable quantity?")
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_numeric_definition_failure
            BEFORE INSERT ON prediction_definition_changes
            BEGIN
                SELECT RAISE(ABORT, 'forced numeric definition failure');
            END
            """
        )
    operations = PredictionOperations(database, FixedClock(CHANGED), UTC)

    with pytest.raises(sqlite3.IntegrityError, match="forced numeric definition"):
        operations.update_metadata(
            created.prediction_id,
            question="Replacement searchable quantity?",
            background="Rollback-only background",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=("RollbackOnly",),
            expected_metadata_version=created.metadata_version,
            confirm_meaning_change=True,
        )

    unchanged = operations.get_numeric_prediction(created.prediction_id)
    assert unchanged.question == created.question
    assert unchanged.background is None
    assert unchanged.tags == created.tags
    assert unchanged.metadata_version == created.metadata_version
    assert operations.list_definition_changes(created.prediction_id) == ()
    assert operations.search_predictions("replacement").hits == ()
    database.close()
