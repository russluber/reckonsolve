import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.errors import (
    ConcurrentLifecycleUpdateError,
    JournalEntryNotAllowedError,
    LifecycleTransitionNotAllowedError,
    PredictionDeletionConfirmationRequired,
    PredictionDeletionNotAllowedError,
    PredictionNotFoundError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import PredictionStatus

CREATED = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
TERMINATED = datetime(2026, 8, 23, 18, 45, 12, 3456, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


def _create(database: Database, **kwargs):
    return PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_numeric_prediction(
        "How many days will the response take?",
        "days",
        1,
        "3.0",
        "7.0",
        "21.0",
        80,
        **kwargs,
    )


def _resolve(operations: PredictionOperations, prediction, actual="40.5", **kwargs):
    return operations.resolve_numeric_prediction(
        prediction.prediction_id,
        actual,
        expected_revision_id=prediction.current_revision.revision_id,
        expected_metadata_version=prediction.metadata_version,
        **kwargs,
    )


def test_numeric_resolution_accepts_outside_value_and_captures_final_revision(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    revision_ops = PredictionOperations(database, FixedClock(CREATED), UTC)
    revised = revision_ops.revise_numeric_forecast(
        created.prediction_id,
        "4.0",
        "8.0",
        "24.0",
        90,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )

    resolved = _resolve(
        PredictionOperations(database, FixedClock(TERMINATED), UTC),
        revised,
        resolution_notes="Published result",
        postmortem="The upper tail was too narrow.",
    )

    assert resolved.status is PredictionStatus.RESOLVED
    assert resolved.resolution is not None
    assert str(resolved.resolution.actual_value) == "40.5"
    assert (
        resolved.resolution.scoring_revision_id == revised.current_revision.revision_id
    )
    assert resolved.resolution.scoring_revision_sequence == 2
    assert resolved.resolution.resolution_notes == "Published result"
    assert resolved.resolution.postmortem == "The upper tail was too narrow."
    assert resolved.invalidation is None
    assert not resolved.deletion_allowed
    assert len(revision_ops.list_numeric_forecast_revisions(created.prediction_id)) == 2
    database.close()


def test_locked_numeric_prediction_resolves_but_rejects_revisions(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database, forecast_deadline=CREATED.date())
    later = PredictionOperations(database, FixedClock(CREATED + timedelta(days=1)), UTC)
    locked = later.get_numeric_prediction(created.prediction_id)

    assert locked.status is PredictionStatus.LOCKED
    resolved = _resolve(later, locked, actual="7.0")
    assert resolved.status is PredictionStatus.RESOLVED
    database.close()


def test_numeric_invalidation_is_terminal_and_unscored(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)

    invalid = operations.invalidate_numeric_prediction(
        created.prediction_id,
        reason="The quantity became undefined.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )

    assert invalid.status is PredictionStatus.INVALID
    assert invalid.resolution is None
    assert invalid.invalidation is not None
    assert invalid.invalidation.reason == "The quantity became undefined."
    with pytest.raises(LifecycleTransitionNotAllowedError):
        _resolve(operations, invalid, actual="7.0")
    database.close()


def test_numeric_terminal_state_rejects_new_journal_but_allows_correction(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)
    journal = operations.add_numeric_journal_entry(
        created.prediction_id,
        "Initial wording.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    resolved = _resolve(operations, created, actual="7.0")

    with pytest.raises(JournalEntryNotAllowedError):
        operations.add_numeric_journal_entry(
            created.prediction_id,
            "A late assertion.",
            expected_revision_id=resolved.current_revision.revision_id,
            expected_metadata_version=resolved.metadata_version,
        )
    corrected = operations.correct_numeric_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "Corrected wording.",
        expected_correction_id=None,
    )
    assert corrected.body == "Corrected wording."
    assert len(operations.list_numeric_forecast_revisions(created.prediction_id)) == 1
    database.close()


def test_numeric_resolution_validation_and_stale_context_write_nothing(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)

    with pytest.raises(ValidationError):
        _resolve(operations, created, actual="7.01")
    operations.revise_numeric_forecast(
        created.prediction_id,
        "4.0",
        "8.0",
        "22.0",
        80,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    with pytest.raises(ConcurrentLifecycleUpdateError):
        _resolve(operations, created, actual="7.0")
    with database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
    database.close()


def test_failed_numeric_resolution_rolls_back_record_and_status(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_numeric_resolution_failure
            AFTER INSERT ON numeric_resolutions
            BEGIN SELECT RAISE(ABORT, 'forced numeric resolution failure'); END
            """
        )

    with pytest.raises(
        sqlite3.IntegrityError, match="forced numeric resolution failure"
    ):
        _resolve(PredictionOperations(database, FixedClock(TERMINATED), UTC), created)
    with database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?", (created.prediction_id,)
            ).fetchone()[0]
            == "open"
        )
    database.close()


def test_numeric_resolution_rechecks_context_across_two_connections(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    competing_database = Database.open(path)
    reviewed = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)
    competing = PredictionOperations(
        competing_database,
        FixedClock(TERMINATED),
        UTC,
    )
    original_resolve = operations._numeric_repository.resolve_prediction

    def race(*args, **kwargs):
        competing.revise_numeric_forecast(
            reviewed.prediction_id,
            "4.0",
            "8.0",
            "22.0",
            80,
            expected_revision_id=reviewed.current_revision.revision_id,
            expected_metadata_version=reviewed.metadata_version,
        )
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(operations._numeric_repository, "resolve_prediction", race)
    with pytest.raises(ConcurrentLifecycleUpdateError):
        _resolve(operations, reviewed, actual="7.0")
    with competing_database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
    competing_database.close()
    database.close()


def test_numeric_delete_requires_confirmation_and_untouched_open_history(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)
    created = _create(database)
    with pytest.raises(PredictionDeletionConfirmationRequired):
        operations.delete_numeric_prediction(
            created.prediction_id,
            expected_revision_id=created.current_revision.revision_id,
            expected_metadata_version=created.metadata_version,
        )
    operations.add_numeric_journal_entry(
        created.prediction_id,
        "Meaningful context.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    current = operations.get_numeric_prediction(created.prediction_id)
    assert not current.deletion_allowed
    with pytest.raises(PredictionDeletionNotAllowedError):
        operations.delete_numeric_prediction(
            created.prediction_id,
            expected_revision_id=current.current_revision.revision_id,
            expected_metadata_version=current.metadata_version,
            confirm_permanent_deletion=True,
        )

    disposable = _create(database)
    assert (
        operations.delete_numeric_prediction(
            disposable.prediction_id,
            expected_revision_id=disposable.current_revision.revision_id,
            expected_metadata_version=disposable.metadata_version,
            confirm_permanent_deletion=True,
        )
        is not None
    )
    with pytest.raises(PredictionNotFoundError):
        operations.get_numeric_prediction(disposable.prediction_id)
    database.close()


def test_numeric_terminal_record_survives_restart_and_rejects_rewrite(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    created = _create(database)
    resolved = _resolve(
        PredictionOperations(database, FixedClock(TERMINATED), UTC),
        created,
        actual="-2.5",
    )
    assert resolved.resolution is not None
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE numeric_resolutions SET actual_scaled = 0 WHERE id = ?",
            (resolved.resolution.resolution_id,),
        )
    database.close()

    reopened = Database.open(path)
    recovered = PredictionOperations(
        reopened, FixedClock(TERMINATED), UTC
    ).get_numeric_prediction(created.prediction_id)
    assert recovered.status is PredictionStatus.RESOLVED
    assert recovered.resolution is not None
    assert str(recovered.resolution.actual_value) == "-2.5"
    reopened.close()


def test_numeric_resolution_schema_guards_scoring_identity_and_parent_cascade(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED), UTC)
    revised = operations.revise_numeric_forecast(
        created.prediction_id,
        "4.0",
        "8.0",
        "22.0",
        80,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    with (
        pytest.raises(sqlite3.IntegrityError, match="current forecast revision"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO numeric_resolutions (
                prediction_id, actual_scaled, resolved_at, scoring_revision_id
            ) VALUES (?, 70, ?, ?)
            """,
            (
                created.prediction_id,
                "2026-08-23T18:45:12.003456Z",
                created.current_revision.revision_id,
            ),
        )

    resolved = _resolve(operations, revised, actual="7.0")
    assert resolved.resolution is not None
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT OR REPLACE INTO numeric_resolutions (
                id, prediction_id, actual_scaled, resolved_at, scoring_revision_id
            ) VALUES (?, ?, 80, ?, ?)
            """,
            (
                resolved.resolution.resolution_id,
                resolved.prediction_id,
                "2026-08-23T18:45:12.003456Z",
                revised.current_revision.revision_id,
            ),
        )

    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM predictions WHERE id = ?",
            (resolved.prediction_id,),
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
    database.close()
