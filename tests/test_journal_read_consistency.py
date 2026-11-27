"""Cross-surface Journal prerequisites on disposable, controlled-clock data."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from supported_fixtures import create_binary, create_numeric

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.quantiles import QuantilePredictionRepository
from reckonsolve.domain.browser import ArchiveAttention
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType


@dataclass
class Clock:
    instant: datetime = datetime(2026, 11, 1, 10, tzinfo=UTC)

    def now(self) -> datetime:
        return self.instant


def test_metadata_response_construction_failure_rolls_back_history_and_search(
    storage, monkeypatch
):
    _database, _clock, operations = storage
    prediction = create_binary(operations, "Atomic response construction", 60)

    def fail(*args):
        raise RuntimeError("Injected response construction failure")

    monkeypatch.setattr(
        "reckonsolve.application.predictions.read_metadata_snapshot", fail
    )
    with pytest.raises(RuntimeError, match="response construction"):
        operations.update_metadata(
            prediction.prediction_id,
            question=prediction.question,
            background="Must never commit this text",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=prediction.metadata_version,
        )
    assert operations.get_prediction(prediction.prediction_id) == prediction
    assert operations.search_predictions("never commit").hits == ()


@pytest.fixture
def storage(tmp_path):
    database = Database.open(tmp_path / "journal.sqlite3")
    clock = Clock()
    yield database, clock, PredictionOperations(database, clock, UTC)
    database.close()


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_cleared_reflection_agrees_between_queue_browse_search_and_restart(
    storage, kind
):
    database, clock, operations = storage
    if kind is PredictionType.BINARY:
        prediction = create_binary(operations, "Reflection consistency marker", 60)
        context = {"expected_revision_id": prediction.current_revision_id}
    else:
        prediction = create_numeric(
            operations,
            "Reflection consistency marker",
            "units",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
        )
        context = {"expected_revision_id": prediction.current_revision.revision_id}
    context["expected_metadata_version"] = prediction.metadata_version
    clock.instant += timedelta(days=1)
    resolve = (
        operations.resolve_prediction
        if kind is PredictionType.BINARY
        else operations.resolve_numeric_prediction
    )
    actual = BinaryOutcome.YES if kind is PredictionType.BINARY else 0
    resolve(
        prediction.prediction_id,
        actual,
        postmortem="Original reflection preserved in history",
        use_recorded_time=True,
        **context,
    )
    score_before = operations.get_prediction_scorecard(prediction.prediction_id)
    clock.instant += timedelta(days=1)
    correct = (
        operations.correct_binary_resolution
        if kind is PredictionType.BINARY
        else operations.correct_numeric_resolution
    )
    correct(
        prediction.prediction_id,
        actual,
        resolution_notes=None,
        postmortem=None,
        expected_correction_id=None,
    )

    def check_surfaces(reader):
        assert [
            row.prediction_id
            for row in reader.get_dashboard().needs_postmortem_predictions
        ] == [prediction.prediction_id]
        query = {"attention": ArchiveAttention.NEEDS_POSTMORTEM}
        assert [
            row.prediction_id for row in reader.browse_predictions(**query).predictions
        ] == [prediction.prediction_id]
        assert [
            hit.prediction.prediction_id
            for hit in reader.search_predictions("consistency marker", **query).hits
        ] == [prediction.prediction_id]
        history = (
            reader.get_binary_resolution_history(prediction.prediction_id)
            if kind is PredictionType.BINARY
            else reader.get_numeric_resolution_history(prediction.prediction_id)
        )
        assert history.effective.postmortem is None
        assert history.original.postmortem == "Original reflection preserved in history"
        assert reader.get_prediction_scorecard(prediction.prediction_id) == score_before

    check_surfaces(operations)
    separate = Database.open(database.path)
    try:
        check_surfaces(PredictionOperations(separate, clock, UTC))
    finally:
        separate.close()
    path = database.path
    database.close()
    restarted = Database.open(path)
    try:
        check_surfaces(PredictionOperations(restarted, clock, UTC))
    finally:
        restarted.close()


def test_numeric_journal_correction_returns_without_another_database_read(
    storage, monkeypatch
):
    _database, clock, operations = storage
    prediction = create_numeric(
        operations,
        "Read response atomically",
        "units",
        0,
        {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
    )
    clock.instant += timedelta(minutes=1)
    entry = operations.add_numeric_journal_entry(
        prediction.prediction_id,
        "Original entry",
        expected_revision_id=prediction.current_revision.revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    clock.instant += timedelta(minutes=1)

    def unavailable_read(*_args):
        raise sqlite3.OperationalError("database is locked during subsequent read")

    monkeypatch.setattr(QuantilePredictionRepository, "list_timeline", unavailable_read)
    saved = operations.correct_numeric_journal_entry(
        prediction.prediction_id,
        entry.entry_id,
        "Corrected entry",
        expected_correction_id=None,
    )
    assert saved.body == "Corrected entry"
    assert saved.original_body == "Original entry"
    assert len(saved.corrections) == 1
    monkeypatch.undo()
    assert operations.list_numeric_timeline(prediction.prediction_id)[-1] == saved


@pytest.mark.parametrize(
    "operation", ("browse_predictions", "get_stale_threshold_days")
)
def test_busy_archive_read_is_an_expected_application_failure(storage, operation):
    database, _clock, operations = storage
    database._require_connection().execute("PRAGMA busy_timeout = 0")
    competing = sqlite3.connect(database.path, autocommit=True, timeout=0)
    try:
        competing.execute("BEGIN EXCLUSIVE")
        with pytest.raises(ApplicationError, match="busy"):
            getattr(operations, operation)()
    finally:
        competing.execute("ROLLBACK")
        competing.close()


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_metadata_success_survives_a_writer_starting_immediately_after_commit(
    storage, monkeypatch, kind
):
    database, _clock, operations = storage
    prediction = (
        create_binary(operations, "Metadata response marker", 60)
        if kind is PredictionType.BINARY
        else create_numeric(
            operations,
            "Metadata response marker",
            "units",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
        )
    )
    database._require_connection().execute("PRAGMA busy_timeout = 0")
    competing = sqlite3.connect(database.path, autocommit=True, timeout=0)
    original = operations._repository.update_metadata

    def acquire_after_commit(*args, **kwargs):
        result = original(*args, **kwargs)
        competing.execute("BEGIN EXCLUSIVE")
        return result

    monkeypatch.setattr(operations._repository, "update_metadata", acquire_after_commit)
    try:
        saved = operations.update_metadata(
            prediction.prediction_id,
            question=prediction.question,
            background="New background",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=prediction.metadata_version,
        )
        assert saved.background == "New background"
        assert saved.metadata_version == prediction.metadata_version + 1
    finally:
        if competing.in_transaction:
            competing.execute("ROLLBACK")
        competing.close()


def test_numeric_invalidation_success_does_not_require_a_post_commit_read(
    storage, monkeypatch
):
    database, _clock, operations = storage
    prediction = create_numeric(
        operations,
        "Invalidation response marker",
        "units",
        0,
        {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
    )
    database._require_connection().execute("PRAGMA busy_timeout = 0")
    competing = sqlite3.connect(database.path, autocommit=True, timeout=0)
    original = operations._quantiles.invalidate_or_delete

    def acquire_after_commit(*args, **kwargs):
        result = original(*args, **kwargs)
        competing.execute("BEGIN EXCLUSIVE")
        return result

    monkeypatch.setattr(
        operations._quantiles, "invalidate_or_delete", acquire_after_commit
    )
    try:
        saved = operations.invalidate_numeric_prediction(
            prediction.prediction_id,
            reason="The question is inadmissible",
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        assert saved.invalidation.reason == "The question is inadmissible"
    finally:
        if competing.in_transaction:
            competing.execute("ROLLBACK")
        competing.close()
