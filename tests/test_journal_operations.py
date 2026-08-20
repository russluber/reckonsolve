import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from reckonsolve.application.errors import (
    ConcurrentJournalCorrectionError,
    ConcurrentJournalUpdateError,
    JournalEntryNotAllowedError,
    JournalEntryNotFoundError,
    PredictionNotFoundError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    ForecastTimelineEvent,
    JournalTimelineEvent,
    PredictionStatus,
)


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
JOURNALED = datetime(2026, 8, 13, 20, 45, tzinfo=UTC)
CORRECTED = datetime(2026, 8, 14, 21, 15, tzinfo=UTC)


def _create(database: Database, **kwargs):
    return PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Will it happen?",
        60,
        **kwargs,
    )


def _add(operations: PredictionOperations, detail, body: str = "New evidence"):
    return operations.add_journal_entry(
        detail.prediction_id,
        body,
        expected_revision_id=detail.current_revision_id,
        expected_metadata_version=detail.metadata_version,
    )


def test_add_journal_entry_normalizes_body_and_changes_no_forecast_state(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    clock = CountingClock(JOURNALED)
    operations = PredictionOperations(database, clock)

    entry = _add(operations, created, "  New evidence, still 60%.  ")
    after = operations.get_prediction(created.prediction_id)

    assert clock.calls == 2  # one Journal write and one detail read
    assert entry.body == "New evidence, still 60%."
    assert entry.original_body == entry.body
    assert entry.forecast_revision_id == created.current_revision_id
    assert entry.forecast_revision_sequence == 1
    assert entry.forecast_probability_percent == 60
    assert entry.created_at == JOURNALED
    assert entry.current_correction_id is None
    assert entry.corrections == ()
    assert after.probability_percent == created.probability_percent
    assert after.current_revision_id == created.current_revision_id
    assert after.metadata_version == created.metadata_version
    assert after.updated_at == created.updated_at
    assert len(operations.list_forecast_revisions(created.prediction_id)) == 1
    database.close()


@pytest.mark.parametrize("body", ["", "  ", "bad\x00body", None, 3])
def test_journal_validation_is_expected_and_writes_nothing(tmp_path, body) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    clock = CountingClock(JOURNALED)

    with pytest.raises(ValidationError) as error_info:
        _add(PredictionOperations(database, clock), created, body)

    assert error_info.value.field == "body"
    assert clock.calls == 0
    with database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
            == 0
        )
    database.close()


def test_locked_prediction_accepts_journal_but_terminal_predictions_reject_new(
    tmp_path,
) -> None:
    locked_database = Database.open(tmp_path / "locked.sqlite3")
    created = _create(locked_database, forecast_deadline=date(2026, 8, 12))
    locked_operations = PredictionOperations(locked_database, FixedClock(JOURNALED))
    assert (
        locked_operations.get_prediction(created.prediction_id).status
        is PredictionStatus.LOCKED
    )
    assert _add(locked_operations, created).body == "New evidence"
    locked_database.close()

    for status in ("resolved", "invalid"):
        database = Database.open(tmp_path / f"{status}.sqlite3")
        detail = _create(database)
        terminal_operations = PredictionOperations(database, FixedClock(JOURNALED))
        if status == "resolved":
            terminal_operations.resolve_prediction(
                detail.prediction_id,
                BinaryOutcome.YES,
                expected_revision_id=detail.current_revision_id,
                expected_metadata_version=detail.metadata_version,
            )
        else:
            terminal_operations.invalidate_prediction(
                detail.prediction_id,
                expected_revision_id=detail.current_revision_id,
                expected_metadata_version=detail.metadata_version,
            )
        with pytest.raises(JournalEntryNotAllowedError) as error_info:
            _add(PredictionOperations(database, FixedClock(JOURNALED)), detail)
        assert error_info.value.status is PredictionStatus(status)
        database.close()


def test_stale_revision_and_metadata_tokens_reject_without_entry(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(JOURNALED))
    stale = _create(database)
    revised = operations.revise_forecast(
        stale.prediction_id,
        40,
        expected_revision_id=stale.current_revision_id,
        expected_metadata_version=stale.metadata_version,
    )
    with pytest.raises(ConcurrentJournalUpdateError):
        _add(operations, stale)

    current = operations.update_metadata(
        revised.prediction_id,
        question=revised.question,
        background="Changed",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=revised.metadata_version,
    )
    with pytest.raises(ConcurrentJournalUpdateError):
        _add(operations, revised)
    assert current.metadata_version == 2
    assert all(
        not isinstance(event, JournalTimelineEvent)
        for event in operations.list_timeline(stale.prediction_id)
    )
    database.close()


def test_repository_rechecks_journal_context_inside_transaction(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database, FixedClock(JOURNALED))
    reviewed = _create(database)
    competing_database = Database.open(database_path)
    competing = PredictionOperations(competing_database, FixedClock(JOURNALED))
    original_add = operations._repository.add_journal_entry

    def race(*args, **kwargs):
        competing.revise_forecast(
            reviewed.prediction_id,
            40,
            expected_revision_id=reviewed.current_revision_id,
            expected_metadata_version=reviewed.metadata_version,
        )
        return original_add(*args, **kwargs)

    monkeypatch.setattr(operations._repository, "add_journal_entry", race)
    with pytest.raises(ConcurrentJournalUpdateError):
        _add(operations, reviewed)
    assert len(competing.list_forecast_revisions(reviewed.prediction_id)) == 2
    competing_database.close()
    database.close()


@pytest.mark.parametrize("status", ["resolved", "invalid"])
def test_corrections_append_versions_keep_anchor_and_allow_terminal_state(
    tmp_path,
    status: str,
) -> None:
    database = Database.open(tmp_path / f"{status}.sqlite3")
    detail = _create(database)
    entry = _add(
        PredictionOperations(database, FixedClock(JOURNALED)), detail, "Typo bodi"
    )
    terminal_operations = PredictionOperations(database, FixedClock(CORRECTED))
    if status == "resolved":
        terminal_operations.resolve_prediction(
            detail.prediction_id,
            BinaryOutcome.YES,
            expected_revision_id=detail.current_revision_id,
            expected_metadata_version=detail.metadata_version,
        )
    else:
        terminal_operations.invalidate_prediction(
            detail.prediction_id,
            expected_revision_id=detail.current_revision_id,
            expected_metadata_version=detail.metadata_version,
        )
    operations = PredictionOperations(database, FixedClock(CORRECTED))

    first = operations.correct_journal_entry(
        detail.prediction_id,
        entry.entry_id,
        "Typo body",
        expected_correction_id=None,
    )
    second = operations.correct_journal_entry(
        detail.prediction_id,
        entry.entry_id,
        "Clean body",
        expected_correction_id=first.current_correction_id,
    )

    assert second.created_at == JOURNALED
    assert second.original_body == "Typo bodi"
    assert second.body == "Clean body"
    assert second.forecast_revision_id == detail.current_revision_id
    assert second.forecast_probability_percent == 60
    assert [item.body for item in second.corrections] == ["Typo body", "Clean body"]
    assert all(item.corrected_at == CORRECTED for item in second.corrections)
    database.close()


def test_unchanged_correction_is_a_noop_without_clock_or_write(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    detail = _create(database)
    entry = _add(
        PredictionOperations(database, FixedClock(JOURNALED)), detail, "Clean body"
    )
    clock = CountingClock(CORRECTED)

    unchanged = PredictionOperations(database, clock).correct_journal_entry(
        detail.prediction_id,
        entry.entry_id,
        "  Clean body  ",
        expected_correction_id=None,
    )

    assert unchanged == entry
    assert clock.calls == 0
    assert unchanged.corrections == ()
    database.close()


def test_stale_correction_token_rejects_and_repository_rechecks_in_transaction(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    detail = _create(database)
    entry = _add(PredictionOperations(database, FixedClock(JOURNALED)), detail)
    operations = PredictionOperations(database, FixedClock(CORRECTED))
    first = operations.correct_journal_entry(
        detail.prediction_id,
        entry.entry_id,
        "First correction",
        expected_correction_id=None,
    )
    with pytest.raises(ConcurrentJournalCorrectionError):
        operations.correct_journal_entry(
            detail.prediction_id,
            entry.entry_id,
            "Stale correction",
            expected_correction_id=None,
        )

    original_append = operations._repository.append_journal_correction
    competing_database = Database.open(database_path)
    competing = PredictionOperations(competing_database, FixedClock(CORRECTED))

    def race(*args, **kwargs):
        competing.correct_journal_entry(
            detail.prediction_id,
            entry.entry_id,
            "Competing correction",
            expected_correction_id=first.current_correction_id,
        )
        return original_append(*args, **kwargs)

    monkeypatch.setattr(operations._repository, "append_journal_correction", race)
    with pytest.raises(ConcurrentJournalCorrectionError):
        operations.correct_journal_entry(
            detail.prediction_id,
            entry.entry_id,
            "Losing correction",
            expected_correction_id=first.current_correction_id,
        )
    competing_database.close()
    database.close()


def test_timeline_uses_revision_anchor_and_ids_for_causal_order(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(CREATED))
    current = _create(database)
    first_entry = _add(operations, current, "First note")
    current = operations.revise_forecast(
        current.prediction_id,
        40,
        rationale="Changed",
        expected_revision_id=current.current_revision_id,
        expected_metadata_version=current.metadata_version,
    )
    second_entry = _add(operations, current, "Second note")

    events = operations.list_timeline(current.prediction_id)

    assert [type(event) for event in events] == [
        ForecastTimelineEvent,
        JournalTimelineEvent,
        ForecastTimelineEvent,
        JournalTimelineEvent,
    ]
    assert [
        event.entry_id for event in events if isinstance(event, JournalTimelineEvent)
    ] == [first_entry.entry_id, second_entry.entry_id]
    forecast_events = [
        event for event in events if isinstance(event, ForecastTimelineEvent)
    ]
    assert forecast_events[0].previous_probability_percent is None
    assert forecast_events[1].previous_probability_percent == 60
    database.close()


def test_journals_on_one_anchor_remain_in_save_order_when_clock_regresses(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    detail = _create(database)
    later = _add(
        PredictionOperations(database, FixedClock(JOURNALED)),
        detail,
        "Saved first",
    )
    earlier_instant = datetime(2026, 8, 12, 20, 45, tzinfo=UTC)
    earlier = _add(
        PredictionOperations(database, FixedClock(earlier_instant)),
        detail,
        "Saved second after the clock moved backward",
    )

    journals = [
        event
        for event in PredictionOperations(
            database, FixedClock(CORRECTED)
        ).list_timeline(detail.prediction_id)
        if isinstance(event, JournalTimelineEvent)
    ]

    assert [entry.entry_id for entry in journals] == [later.entry_id, earlier.entry_id]
    assert journals[0].created_at > journals[1].created_at
    database.close()


def test_journal_timeline_and_corrections_survive_restart(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    detail = _create(first_database)
    first_operations = PredictionOperations(first_database, FixedClock(JOURNALED))
    entry = _add(first_operations, detail, "Typo")
    corrected = first_operations.correct_journal_entry(
        detail.prediction_id,
        entry.entry_id,
        "Corrected",
        expected_correction_id=None,
    )
    expected = first_operations.list_timeline(detail.prediction_id)
    first_database.close()

    second_database = Database.open(path)
    second_operations = PredictionOperations(second_database, FixedClock(CORRECTED))
    assert second_operations.list_timeline(detail.prediction_id) == expected
    assert corrected in expected
    with pytest.raises(PredictionNotFoundError):
        second_operations.list_timeline(999)
    with pytest.raises(JournalEntryNotFoundError):
        second_operations.correct_journal_entry(
            detail.prediction_id,
            999,
            "Missing",
            expected_correction_id=None,
        )
    second_database.close()


def test_failed_journal_or_correction_insert_rolls_back_history(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    detail = _create(database)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_journal_failure
            BEFORE INSERT ON journal_entries
            BEGIN SELECT RAISE(ABORT, 'forced journal failure'); END
            """
        )
    with pytest.raises(sqlite3.IntegrityError, match="forced journal failure"):
        _add(PredictionOperations(database, FixedClock(JOURNALED)), detail)
    with database.transaction() as connection:
        connection.execute("DROP TRIGGER force_journal_failure")
    entry = _add(PredictionOperations(database, FixedClock(JOURNALED)), detail)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_correction_failure
            BEFORE INSERT ON journal_entry_corrections
            BEGIN SELECT RAISE(ABORT, 'forced correction failure'); END
            """
        )
    with pytest.raises(sqlite3.IntegrityError, match="forced correction failure"):
        PredictionOperations(database, FixedClock(CORRECTED)).correct_journal_entry(
            detail.prediction_id,
            entry.entry_id,
            "Correction",
            expected_correction_id=None,
        )
    timeline = PredictionOperations(database, FixedClock(CORRECTED)).list_timeline(
        detail.prediction_id
    )
    journals = [event for event in timeline if isinstance(event, JournalTimelineEvent)]
    assert len(journals) == 1
    assert journals[0].corrections == ()
    database.close()
