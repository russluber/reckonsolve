import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest

from reckonsolve.application.errors import (
    ConcurrentForecastUpdateError,
    ForecastRevisionNotAllowedError,
    ForecastUnchangedError,
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
REVISED = datetime(2026, 8, 13, 20, 45, 12, 3456, tzinfo=UTC)


def _create(database: Database, probability: int = 60):
    return PredictionOperations(database, FixedClock(CREATED)).create_prediction(
        "Will it happen?",
        probability,
    )


def _revise(
    operations: PredictionOperations,
    detail,
    probability: int,
    rationale: str | None = None,
):
    return operations.revise_forecast(
        detail.prediction_id,
        probability,
        rationale=rationale,
        expected_revision_id=detail.current_revision_id,
        expected_metadata_version=detail.metadata_version,
    )


def test_complete_creation_persists_every_optional_value_without_history(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(CREATED))

    created = operations.create_prediction(
        "  Will it happen?  ",
        37,
        rationale="  Initial reasons  ",
        background="  Background  ",
        resolution_criteria="  Official result  ",
        forecast_deadline=date(2026, 8, 12),
        expected_resolution=date(2026, 8, 1),
        tags=(" Science ", "science", "Personal"),
    )
    revisions = operations.list_forecast_revisions(created.prediction_id)

    assert created.question == "Will it happen?"
    assert created.probability_percent == 37
    assert created.current_revision_sequence == 1
    assert created.current_rationale == "Initial reasons"
    assert created.background == "Background"
    assert created.resolution_criteria == "Official result"
    assert created.forecast_deadline == date(2026, 8, 12)
    assert created.expected_resolution == date(2026, 8, 1)
    assert created.tags == ("Personal", "Science")
    assert created.status is PredictionStatus.OPEN
    assert created.metadata_version == 1
    assert created.updated_at == CREATED
    assert len(revisions) == 1
    assert revisions[0].revision_id == created.current_revision_id
    assert revisions[0].rationale == "Initial reasons"
    assert operations.list_definition_changes(created.prediction_id) == ()
    database.close()


def test_complete_creation_uses_one_instant_for_all_system_timestamps(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    clock = CountingClock(CREATED)

    detail = PredictionOperations(database, clock).create_prediction(
        "One instant?",
        50,
        rationale="Because",
        background="Context",
        tags=("Time",),
    )

    assert clock.calls == 1
    assert detail.created_at == CREATED
    assert detail.updated_at == CREATED
    with database.transaction() as connection:
        revision_time = connection.execute(
            "SELECT created_at FROM forecast_revisions"
        ).fetchone()[0]
    assert revision_time == "2026-08-12T19:30:00.000000Z"
    database.close()


def test_past_initial_deadline_is_rejected_but_today_is_valid_in_local_time(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    pacific = timezone(-timedelta(hours=7))
    instant = datetime(2026, 8, 13, 2, tzinfo=UTC)  # Aug 12 locally
    operations = PredictionOperations(database, FixedClock(instant), pacific)

    today = operations.create_prediction(
        "Deadline is inclusive?",
        50,
        forecast_deadline=date(2026, 8, 12),
    )
    with pytest.raises(ValidationError) as error_info:
        operations.create_prediction(
            "Already locked?",
            50,
            forecast_deadline=date(2026, 8, 11),
        )

    assert today.status is PredictionStatus.OPEN
    assert error_info.value.field == "forecast_deadline"
    with database.transaction() as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM predictions),
                (SELECT COUNT(*) FROM forecast_revisions)
            """
        ).fetchone()
    assert tuple(counts) == (1, 1)
    database.close()


def test_creation_rolls_back_prediction_revision_tags_and_history_on_tag_failure(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_initial_tag_failure
            BEFORE INSERT ON prediction_tags
            BEGIN
                SELECT RAISE(ABORT, 'forced tag failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced tag failure"):
        PredictionOperations(database, FixedClock(CREATED)).create_prediction(
            "Roll back all initial state?",
            60,
            rationale="Reasons",
            background="Context",
            resolution_criteria="Criterion",
            tags=("Atomic",),
        )

    with database.transaction() as connection:
        counts = tuple(
            connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM predictions),
                    (SELECT COUNT(*) FROM forecast_revisions),
                    (SELECT COUNT(*) FROM tags),
                    (SELECT COUNT(*) FROM prediction_tags),
                    (SELECT COUNT(*) FROM prediction_definition_changes)
                """
            ).fetchone()
        )
    assert counts == (0, 0, 0, 0, 0)
    database.close()


def test_creation_rolls_back_initial_tags_when_revision_insert_fails(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_initial_revision_failure_with_details
            BEFORE INSERT ON forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'forced revision failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced revision failure"):
        PredictionOperations(database, FixedClock(CREATED)).create_prediction(
            "Roll back tags too?",
            60,
            rationale="Reasons",
            background="Context",
            tags=("Atomic",),
        )

    with database.transaction() as connection:
        counts = tuple(
            connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM predictions),
                    (SELECT COUNT(*) FROM forecast_revisions),
                    (SELECT COUNT(*) FROM tags),
                    (SELECT COUNT(*) FROM prediction_tags)
                """
            ).fetchone()
        )
    assert counts == (0, 0, 0, 0)
    database.close()


def test_revision_appends_in_sequence_and_never_changes_prediction_metadata(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    clock = CountingClock(REVISED)

    revised = _revise(
        PredictionOperations(database, clock),
        created,
        40,
        "  New evidence  ",
    )
    revisions = PredictionOperations(
        database, FixedClock(REVISED)
    ).list_forecast_revisions(created.prediction_id)

    assert clock.calls == 1
    assert revised.probability_percent == 40
    assert revised.current_revision_sequence == 2
    assert revised.current_revision_id != created.current_revision_id
    assert revised.current_rationale == "New evidence"
    assert revised.updated_at == created.updated_at
    assert revised.metadata_version == created.metadata_version
    assert [
        (item.sequence, item.probability_percent, item.rationale) for item in revisions
    ] == [
        (1, 60, None),
        (2, 40, "New evidence"),
    ]
    assert revisions[0].created_at == CREATED
    assert revisions[1].created_at == REVISED
    database.close()


def test_failed_revision_insert_rolls_back_without_touching_history(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER force_later_revision_failure
            BEFORE INSERT ON forecast_revisions
            WHEN NEW.sequence > 1
            BEGIN
                SELECT RAISE(ABORT, 'forced append failure');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced append failure"):
        _revise(
            PredictionOperations(database, FixedClock(REVISED)),
            created,
            40,
            "Unsaved",
        )

    operations = PredictionOperations(database, FixedClock(REVISED))
    assert operations.get_prediction(created.prediction_id) == created
    revisions = operations.list_forecast_revisions(created.prediction_id)
    assert len(revisions) == 1
    assert revisions[0].probability_percent == 60
    assert revisions[0].rationale is None
    database.close()


def test_equal_current_probability_rejects_without_clock_or_write(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)
    clock = CountingClock(REVISED)
    operations = PredictionOperations(database, clock)

    with pytest.raises(ForecastUnchangedError) as error_info:
        _revise(operations, created, 60, "Reasoning without a change")

    assert clock.calls == 0
    assert "Journal entry" in str(error_info.value)
    revisions = operations.list_forecast_revisions(created.prediction_id)
    assert len(revisions) == 1
    assert revisions[0].rationale is None
    database.close()


def test_nonconsecutive_repeated_probability_and_endpoints_are_valid(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(REVISED))
    current = _create(database, 60)

    current = _revise(operations, current, 0)
    current = _revise(operations, current, 100)
    current = _revise(operations, current, 60)

    assert current.probability_percent == 60
    assert [
        revision.probability_percent
        for revision in operations.list_forecast_revisions(current.prediction_id)
    ] == [60, 0, 100, 60]
    database.close()


@pytest.mark.parametrize("probability", [-1, 101, 37.5, "40", True])
def test_revision_validation_is_expected_and_writes_nothing(
    tmp_path,
    probability: Any,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database)

    with pytest.raises(ValidationError) as error_info:
        _revise(
            PredictionOperations(database, FixedClock(REVISED)), created, probability
        )

    assert error_info.value.field == "probability_percent"
    assert (
        len(
            PredictionOperations(database, FixedClock(REVISED)).list_forecast_revisions(
                created.prediction_id
            )
        )
        == 1
    )
    database.close()


def test_deadline_day_accepts_revision_and_next_local_day_rejects(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    pacific = timezone(-timedelta(hours=7))
    created = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 13, 2, tzinfo=UTC)),
        pacific,
    ).create_prediction(
        "Inclusive deadline?",
        60,
        forecast_deadline=date(2026, 8, 12),
    )
    on_deadline = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 13, 6, tzinfo=UTC)),
        pacific,
    )
    revised = _revise(on_deadline, created, 40)

    next_day = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 13, 8, tzinfo=UTC)),
        pacific,
    )
    with pytest.raises(ForecastRevisionNotAllowedError) as error_info:
        _revise(next_day, revised, 30)

    assert error_info.value.status is PredictionStatus.LOCKED
    assert len(next_day.list_forecast_revisions(created.prediction_id)) == 2
    database.close()


@pytest.mark.parametrize(
    ("persisted_status", "expected_status"),
    [("resolved", PredictionStatus.RESOLVED), ("invalid", PredictionStatus.INVALID)],
)
def test_terminal_states_reject_revisions(
    tmp_path,
    persisted_status: str,
    expected_status: PredictionStatus,
) -> None:
    database = Database.open(tmp_path / f"{persisted_status}.sqlite3")
    created = _create(database)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE predictions SET status = ? WHERE id = ?",
            (persisted_status, created.prediction_id),
        )

    with pytest.raises(ForecastRevisionNotAllowedError) as error_info:
        _revise(PredictionOperations(database, FixedClock(REVISED)), created, 40)

    assert error_info.value.status is expected_status
    assert (
        len(
            PredictionOperations(database, FixedClock(REVISED)).list_forecast_revisions(
                created.prediction_id
            )
        )
        == 1
    )
    database.close()


def test_stale_revision_and_metadata_tokens_reject_without_append(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(REVISED))
    stale = _create(database)
    current = _revise(operations, stale, 40)

    with pytest.raises(ConcurrentForecastUpdateError):
        _revise(operations, stale, 30)

    metadata_updated = operations.update_metadata(
        current.prediction_id,
        question=current.question,
        background="New context",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=current.metadata_version,
    )
    with pytest.raises(ConcurrentForecastUpdateError):
        _revise(operations, current, 30)

    assert metadata_updated.metadata_version == 2
    assert len(operations.list_forecast_revisions(current.prediction_id)) == 2
    database.close()


@pytest.mark.parametrize(
    ("field", "expected_revision_id", "expected_metadata_version"),
    [
        ("expected_revision_id", 0, 1),
        ("expected_revision_id", True, 1),
        ("expected_metadata_version", 1, 0),
        ("expected_metadata_version", 1, False),
    ],
)
def test_invalid_revision_context_tokens_are_expected_validation_errors(
    tmp_path,
    field: str,
    expected_revision_id: Any,
    expected_metadata_version: Any,
) -> None:
    database = Database.open(tmp_path / f"{field}-{expected_revision_id}.sqlite3")
    created = _create(database)

    with pytest.raises(ValidationError) as error_info:
        PredictionOperations(database, FixedClock(REVISED)).revise_forecast(
            created.prediction_id,
            40,
            expected_revision_id=expected_revision_id,
            expected_metadata_version=expected_metadata_version,
        )

    assert error_info.value.field == field
    database.close()


def test_revising_a_missing_prediction_is_an_expected_error(tmp_path) -> None:
    database = Database.open(tmp_path / "missing.sqlite3")

    with pytest.raises(PredictionNotFoundError):
        PredictionOperations(database, FixedClock(REVISED)).revise_forecast(
            999,
            40,
            expected_revision_id=1,
            expected_metadata_version=1,
        )

    database.close()


def test_repository_rechecks_context_inside_append_transaction(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(REVISED))
    competing = PredictionOperations(database, FixedClock(REVISED))
    reviewed = _create(database)
    original_append = operations._repository.append_forecast_revision

    def race(*args, **kwargs):
        _revise(competing, reviewed, 40)
        return original_append(*args, **kwargs)

    monkeypatch.setattr(operations._repository, "append_forecast_revision", race)

    with pytest.raises(ConcurrentForecastUpdateError):
        _revise(operations, reviewed, 30)

    assert [
        revision.probability_percent
        for revision in competing.list_forecast_revisions(reviewed.prediction_id)
    ] == [60, 40]
    database.close()


def test_revision_history_survives_restart_and_missing_prediction_is_expected(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    first_operations = PredictionOperations(first_database, FixedClock(REVISED))
    current = _revise(first_operations, _create(first_database), 40, "Changed")
    expected = first_operations.list_forecast_revisions(current.prediction_id)
    first_database.close()

    second_database = Database.open(path)
    second_operations = PredictionOperations(second_database, FixedClock(REVISED))

    assert second_operations.get_prediction(current.prediction_id) == current
    assert second_operations.list_forecast_revisions(current.prediction_id) == expected
    with pytest.raises(PredictionNotFoundError):
        second_operations.list_forecast_revisions(999)
    second_database.close()
