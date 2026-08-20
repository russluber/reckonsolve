import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from reckonsolve.application.errors import (
    ConcurrentLifecycleUpdateError,
    LifecycleTransitionNotAllowedError,
    PredictionDeletionConfirmationRequired,
    PredictionDeletionNotAllowedError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome, PredictionStatus

CREATED = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
TERMINATED = datetime(2026, 8, 20, 18, 45, 12, 3456, tzinfo=UTC)


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


def _create(database: Database, **kwargs):
    return PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Will the lifecycle work?",
        60,
        **kwargs,
    )


def _resolve(operations: PredictionOperations, detail, **kwargs):
    return operations.resolve_prediction(
        detail.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=detail.current_revision_id,
        expected_metadata_version=detail.metadata_version,
        **kwargs,
    )


def _invalidate(operations: PredictionOperations, detail, **kwargs):
    return operations.invalidate_prediction(
        detail.prediction_id,
        expected_revision_id=detail.current_revision_id,
        expected_metadata_version=detail.metadata_version,
        **kwargs,
    )


def test_resolution_captures_one_current_scoring_revision_and_optional_text(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    revisions = PredictionOperations(database, FixedClock(CREATED))
    revised = revisions.revise_forecast(
        created.prediction_id,
        35,
        rationale="Latest evidence",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    clock = CountingClock(TERMINATED)

    resolved = _resolve(
        PredictionOperations(database, clock),
        revised,
        resolution_notes="  Certified result  ",
        postmortem="  I updated too slowly.  ",
    )

    assert clock.calls == 1
    assert resolved.status is PredictionStatus.RESOLVED
    assert resolved.deletion_allowed is False
    assert resolved.resolution is not None
    assert resolved.invalidation is None
    assert resolved.resolution.outcome is BinaryOutcome.YES
    assert resolved.resolution.resolved_at == TERMINATED
    assert resolved.resolution.scoring_revision_id == revised.current_revision_id
    assert resolved.resolution.scoring_revision_sequence == 2
    assert resolved.resolution.scoring_probability_percent == 35
    assert resolved.resolution.resolution_notes == "Certified result"
    assert resolved.resolution.postmortem == "I updated too slowly."
    assert len(revisions.list_forecast_revisions(created.prediction_id)) == 2
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?",
                (created.prediction_id,),
            ).fetchone()[0]
            == "resolved"
        )
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 1
    database.close()


def test_locked_prediction_can_resolve_and_uses_its_final_revision(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database, forecast_deadline=date(2026, 8, 12))
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    locked = operations.get_prediction(created.prediction_id)

    assert locked.status is PredictionStatus.LOCKED
    resolved = _resolve(operations, locked)
    assert resolved.status is PredictionStatus.RESOLVED
    assert resolved.resolution is not None
    assert resolved.resolution.scoring_revision_id == created.current_revision_id
    database.close()


def test_invalidation_preserves_reason_and_excludes_resolution(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)

    invalid = _invalidate(
        PredictionOperations(database, FixedClock(TERMINATED)),
        created,
        reason="  The event was cancelled.  ",
    )

    assert invalid.status is PredictionStatus.INVALID
    assert invalid.resolution is None
    assert invalid.invalidation is not None
    assert invalid.invalidation.invalidated_at == TERMINATED
    assert invalid.invalidation.reason == "The event was cancelled."
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM prediction_invalidations"
            ).fetchone()[0]
            == 1
        )
    database.close()


@pytest.mark.parametrize(
    ("operation", "kwargs", "field"),
    [
        ("resolve", {"outcome": "yes"}, "outcome"),
        (
            "resolve",
            {"outcome": BinaryOutcome.YES, "postmortem": "bad\x00text"},
            "postmortem",
        ),
        ("invalidate", {"reason": "bad\x00text"}, "reason"),
    ],
)
def test_terminal_input_validation_writes_nothing_and_does_not_read_clock(
    tmp_path,
    operation: str,
    kwargs: dict[str, object],
    field: str,
) -> None:
    database = Database.open(tmp_path / f"{operation}.sqlite3")
    created = _create(database)
    clock = CountingClock(TERMINATED)
    operations = PredictionOperations(database, clock)

    with pytest.raises(ValidationError) as error_info:
        if operation == "resolve":
            operations.resolve_prediction(
                created.prediction_id,
                kwargs.pop("outcome"),
                expected_revision_id=created.current_revision_id,
                expected_metadata_version=created.metadata_version,
                **kwargs,
            )
        else:
            operations.invalidate_prediction(
                created.prediction_id,
                expected_revision_id=created.current_revision_id,
                expected_metadata_version=created.metadata_version,
                **kwargs,
            )

    assert error_info.value.field == field
    assert clock.calls == 0
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM prediction_invalidations"
            ).fetchone()[0]
            == 0
        )
    database.close()


@pytest.mark.parametrize("first_action", ["resolve", "invalidate"])
def test_terminal_decisions_are_one_way_and_mutually_exclusive(
    tmp_path,
    first_action: str,
) -> None:
    database = Database.open(tmp_path / f"{first_action}.sqlite3")
    created = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    terminal = (
        _resolve(operations, created)
        if first_action == "resolve"
        else _invalidate(operations, created)
    )

    with pytest.raises(LifecycleTransitionNotAllowedError):
        if first_action == "resolve":
            _invalidate(operations, terminal)
        else:
            _resolve(operations, terminal)

    reopened = operations.get_prediction(created.prediction_id)
    assert reopened.status is terminal.status
    assert (reopened.resolution is not None) is (first_action == "resolve")
    assert (reopened.invalidation is not None) is (first_action == "invalidate")
    database.close()


def test_stale_terminal_form_is_rejected_without_record(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    stale = _create(database)
    operations.revise_forecast(
        stale.prediction_id,
        40,
        expected_revision_id=stale.current_revision_id,
        expected_metadata_version=stale.metadata_version,
    )

    with pytest.raises(ConcurrentLifecycleUpdateError):
        _resolve(operations, stale)

    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?",
                (stale.prediction_id,),
            ).fetchone()[0]
            == "open"
        )
    database.close()


def test_repository_rechecks_terminal_context_across_two_connections(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    competing_database = Database.open(path)
    reviewed = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    competing = PredictionOperations(competing_database, FixedClock(TERMINATED))
    original_resolve = operations._repository.resolve_prediction

    def race(*args, **kwargs):
        competing.revise_forecast(
            reviewed.prediction_id,
            45,
            expected_revision_id=reviewed.current_revision_id,
            expected_metadata_version=reviewed.metadata_version,
        )
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(operations._repository, "resolve_prediction", race)
    with pytest.raises(ConcurrentLifecycleUpdateError):
        _resolve(operations, reviewed)

    assert len(competing.list_forecast_revisions(reviewed.prediction_id)) == 2
    with competing_database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 0
    competing_database.close()
    database.close()


@pytest.mark.parametrize("action", ["resolve", "invalidate"])
def test_failed_terminal_insert_rolls_back_record_and_status(
    tmp_path,
    action: str,
) -> None:
    database = Database.open(tmp_path / f"{action}.sqlite3")
    created = _create(database)
    table = "resolutions" if action == "resolve" else "prediction_invalidations"
    with database.transaction() as connection:
        connection.execute(
            f"""
            CREATE TRIGGER force_{action}_failure
            AFTER INSERT ON {table}
            BEGIN
                SELECT RAISE(ABORT, 'forced terminal failure');
            END
            """
        )

    operations = PredictionOperations(database, FixedClock(TERMINATED))
    with pytest.raises(sqlite3.IntegrityError, match="forced terminal failure"):
        if action == "resolve":
            _resolve(operations, created)
        else:
            _invalidate(operations, created)

    with database.transaction() as connection:
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        row = connection.execute(
            "SELECT status, updated_at FROM predictions WHERE id = ?",
            (created.prediction_id,),
        ).fetchone()
        assert tuple(row) == ("open", "2026-08-12T19:30:00.000000Z")
    database.close()


def test_unconfirmed_or_meaningful_prediction_cannot_be_deleted(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    created = _create(database)

    with pytest.raises(PredictionDeletionConfirmationRequired):
        operations.delete_prediction(
            created.prediction_id,
            expected_revision_id=created.current_revision_id,
            expected_metadata_version=created.metadata_version,
        )

    revised = operations.revise_forecast(
        created.prediction_id,
        40,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    assert operations.get_prediction(created.prediction_id).deletion_allowed is False
    with pytest.raises(PredictionDeletionNotAllowedError):
        operations.delete_prediction(
            revised.prediction_id,
            expected_revision_id=revised.current_revision_id,
            expected_metadata_version=revised.metadata_version,
            confirm_permanent_deletion=True,
        )
    assert operations.get_prediction(created.prediction_id).question
    database.close()


def test_delete_rechecks_history_across_two_connections(tmp_path, monkeypatch) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    competing_database = Database.open(path)
    reviewed = _create(database)
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    competing = PredictionOperations(competing_database, FixedClock(TERMINATED))
    original_delete = operations._repository.delete_prediction

    def race(*args, **kwargs):
        competing.add_journal_entry(
            reviewed.prediction_id,
            "New evidence",
            expected_revision_id=reviewed.current_revision_id,
            expected_metadata_version=reviewed.metadata_version,
        )
        return original_delete(*args, **kwargs)

    monkeypatch.setattr(operations._repository, "delete_prediction", race)
    with pytest.raises(PredictionDeletionNotAllowedError):
        operations.delete_prediction(
            reviewed.prediction_id,
            expected_revision_id=reviewed.current_revision_id,
            expected_metadata_version=reviewed.metadata_version,
            confirm_permanent_deletion=True,
        )

    assert competing.get_prediction(reviewed.prediction_id).question
    assert len(competing.list_timeline(reviewed.prediction_id)) == 2
    competing_database.close()
    database.close()


@pytest.mark.parametrize("history_kind", ["metadata", "journal", "locked"])
def test_every_approved_meaningful_history_boundary_blocks_delete(
    tmp_path,
    history_kind: str,
) -> None:
    database = Database.open(tmp_path / f"{history_kind}.sqlite3")
    created = _create(
        database,
        **(
            {"forecast_deadline": date(2026, 8, 12)} if history_kind == "locked" else {}
        ),
    )
    operations = PredictionOperations(database, FixedClock(TERMINATED))
    current = created
    if history_kind == "metadata":
        current = operations.update_metadata(
            created.prediction_id,
            question=created.question,
            background="Context",
            resolution_criteria=None,
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
            expected_metadata_version=created.metadata_version,
        )
    elif history_kind == "journal":
        operations.add_journal_entry(
            created.prediction_id,
            "Evidence",
            expected_revision_id=created.current_revision_id,
            expected_metadata_version=created.metadata_version,
        )
        current = operations.get_prediction(created.prediction_id)
    else:
        current = operations.get_prediction(created.prediction_id)
        assert current.status is PredictionStatus.LOCKED

    assert current.deletion_allowed is False
    with pytest.raises(PredictionDeletionNotAllowedError):
        operations.delete_prediction(
            current.prediction_id,
            expected_revision_id=current.current_revision_id,
            expected_metadata_version=current.metadata_version,
            confirm_permanent_deletion=True,
        )
    database.close()


def test_confirmed_untouched_open_delete_cascades_and_returns_previous_latest(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    first = _create(database, tags=("keep",))
    second = PredictionOperations(database, FixedClock(TERMINATED)).create_prediction(
        "Delete this duplicate",
        25,
        rationale="Accidental duplicate",
        tags=("temporary",),
    )
    operations = PredictionOperations(database, FixedClock(TERMINATED))

    assert operations.get_prediction(second.prediction_id).deletion_allowed
    latest = operations.delete_prediction(
        second.prediction_id,
        expected_revision_id=second.current_revision_id,
        expected_metadata_version=second.metadata_version,
        confirm_permanent_deletion=True,
    )

    assert latest is not None
    assert latest.prediction_id == first.prediction_id
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM predictions WHERE id = ?",
                (second.prediction_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM forecast_revisions WHERE prediction_id = ?",
                (second.prediction_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM prediction_tags WHERE prediction_id = ?",
                (second.prediction_id,),
            ).fetchone()[0]
            == 0
        )
    database.close()


def test_terminal_records_survive_restart_and_reject_direct_rewrite(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    created = _create(database)
    resolved = _resolve(
        PredictionOperations(database, FixedClock(TERMINATED)),
        created,
        resolution_notes="Source",
    )
    assert resolved.resolution is not None
    resolution_id = resolved.resolution.resolution_id

    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE resolutions SET outcome = 'no' WHERE id = ?",
            (resolution_id,),
        )
    database.close()

    reopened_database = Database.open(path)
    reopened = PredictionOperations(
        reopened_database,
        FixedClock(TERMINATED),
    ).get_prediction(created.prediction_id)
    assert reopened.status is PredictionStatus.RESOLVED
    assert reopened.resolution is not None
    assert reopened.resolution.outcome is BinaryOutcome.YES
    assert reopened.resolution.resolution_notes == "Source"
    reopened_database.close()
