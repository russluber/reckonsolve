"""Journal home uses faithful canonical facts across all four contracts."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from supported_fixtures import create_binary, create_numeric, journal_migrations

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import ArchiveMode, ArchiveQuery, ArchiveSort
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.journal import JournalRequest, JournalView
from reckonsolve.domain.one_shot import NewOneShotPrediction, OneShotValues
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)

VALUES = {5: -2, 25: -1, 50: 0, 75: 1, 95: 2}


@dataclass
class Clock:
    instant: datetime = datetime(2026, 11, 1, 10, tzinfo=UTC)

    def now(self):
        return self.instant


@pytest.fixture
def storage(tmp_path):
    database = Database.open(
        tmp_path / "journal.sqlite3", migrations=journal_migrations()
    )
    clock = Clock()
    try:
        yield database, clock, PredictionOperations(database, clock, UTC)
    finally:
        database.close()


def create(operations, kind, *, one_shot=False, answered=False):
    question = f"{kind.value} {'one shot' if one_shot else 'adaptive'} marker"
    if not one_shot:
        return (
            create_binary(operations, question, 60)
            if kind is PredictionType.BINARY
            else create_numeric(operations, question, "units", 0, VALUES)
        )
    numeric = kind is PredictionType.NUMERIC
    return operations.one_shots.create(
        NewOneShotPrediction(
            question,
            one_shot_contract(kind),
            OneShotValues(
                probability_percent=None if numeric else 60,
                quantiles=FiveQuantiles.from_values(VALUES, 0) if numeric else None,
                answer=(FixedPrecisionValue(1, 0) if numeric else BinaryOutcome.YES)
                if answered
                else None,
            ),
            QuantileDefinition("units", 0, NumericValueConstraint.WHOLE_NUMBER)
            if numeric
            else None,
        )
    )


def test_four_contracts_share_one_recent_activity_order_and_explicit_scope(storage):
    _database, _clock, operations = storage
    created = [
        create(operations, kind, one_shot=mode)
        for mode in (False, True)
        for kind in PredictionType
    ]
    query = operations.journal.query
    page = query(JournalRequest())
    assert [row.prediction.prediction_id for row in page.rows] == [
        p.prediction_id for p in reversed(created)
    ]
    assert page.total == 4
    assert page.request.show_count is False
    assert query(JournalRequest(view=JournalView.UNRESOLVED)).total == 4
    scope = ArchiveQuery(
        mode=ArchiveMode.ONE_SHOT, prediction_type=PredictionType.NUMERIC
    )
    narrowed = query(JournalRequest(text="marker", filters=scope))
    assert [row.prediction.prediction_id for row in narrowed.rows] == [
        created[-1].prediction_id
    ]
    assert narrowed.request.show_count is True
    assert query(JournalRequest(text="missing", filters=scope)).total == 0
    assert narrowed.request.filters == scope


def test_journal_entries_advance_activity_without_becoming_reviews(storage):
    _database, clock, operations = storage
    older = create(operations, PredictionType.BINARY)
    clock.instant += timedelta(minutes=1)
    newer = create(operations, PredictionType.NUMERIC)
    clock.instant += timedelta(minutes=1)
    operations.add_journal_entry(
        older.prediction_id,
        "New reasoning passage",
        expected_revision_id=older.current_revision_id,
        expected_metadata_version=older.metadata_version,
    )
    page = operations.journal.query(JournalRequest())
    assert [row.prediction.prediction_id for row in page.rows] == [
        older.prediction_id,
        newer.prediction_id,
    ]
    assert page.rows[0].last_active == clock.instant
    assert page.rows[0].prediction.latest_review_at is None
    assert page.rows[0].prediction.latest_revision_at == older.created_at
    clock.instant += timedelta(minutes=1)
    operations.update_metadata(
        newer.prediction_id,
        question=newer.question,
        background="Metadata repair does not create activity",
        resolution_criteria=None,
        forecast_deadline=None,
        expected_resolution=None,
        tags=(),
        expected_metadata_version=newer.metadata_version,
    )
    assert (
        operations.journal.query(JournalRequest()).rows[0].prediction.prediction_id
        == older.prediction_id
    )


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_resolved_row_uses_strictly_eligible_forecast_not_latest_revision(
    storage, kind
):
    _database, clock, operations = storage
    prediction = create(operations, kind)
    first_instant = clock.instant
    clock.instant += timedelta(hours=1)
    if kind is PredictionType.BINARY:
        revised = operations.revise_forecast(
            prediction.prediction_id,
            80,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        context = {"expected_revision_id": revised.current_revision_id}
    else:
        revised = operations.revise_quantile_forecast(
            prediction.prediction_id,
            VALUES | {95: 5},
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        context = {"expected_revision_id": revised.current_revision.revision_id}
    clock.instant += timedelta(hours=1)
    resolve = (
        operations.resolve_prediction
        if kind is PredictionType.BINARY
        else operations.resolve_numeric_prediction
    )
    resolve(
        prediction.prediction_id,
        BinaryOutcome.YES if kind is PredictionType.BINARY else 1,
        effective_resolution_at=first_instant + timedelta(minutes=30),
        expected_metadata_version=revised.metadata_version,
        **context,
    )
    row = operations.journal.query(JournalRequest()).rows[0]
    assert row.forecast_label == "Last scoring-eligible forecast"
    assert row.excluded_later_forecast
    assert row.contextual_label == "Outcome known"
    assert row.contextual_at == first_instant + timedelta(minutes=30)
    if kind is PredictionType.BINARY:
        assert row.probability_percent == 60
        assert row.actual is BinaryOutcome.YES
    else:
        assert row.quantiles.q95.scaled_value == 2
        assert row.actual.scaled_value == 1


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_only_dedicated_new_one_shot_reflection_advances_activity(storage, kind):
    _database, clock, operations = storage
    original = create(operations, kind, one_shot=True, answered=True)
    first_instant = clock.instant
    clock.instant += timedelta(minutes=1)
    repaired = operations.one_shots.correct(
        original, replace(original.record.effective, postmortem="Repaired prose")
    )
    assert (
        operations.journal.query(JournalRequest()).rows[0].last_active == first_instant
    )
    clock.instant += timedelta(minutes=1)
    cleared = operations.one_shots.save_postmortem(repaired, None, confirm_clear=True)
    assert (
        operations.journal.query(JournalRequest()).rows[0].last_active == first_instant
    )
    clock.instant += timedelta(minutes=1)
    written = operations.one_shots.save_postmortem(cleared, "New standalone reflection")
    written_instant = clock.instant
    clock.instant += timedelta(minutes=1)
    operations.one_shots.save_postmortem(written, "An edit")
    row = operations.journal.query(JournalRequest()).rows[0]
    assert row.last_active == written_instant
    assert row.correction_label is None
    assert row.contextual_at is None
    assert (
        operations.journal.query(
            JournalRequest(view=JournalView.NEEDS_POSTMORTEM)
        ).total
        == 0
    )


def test_counts_are_prediction_counts_even_with_bounded_rows_and_multiple_matches(
    storage,
):
    _database, clock, operations = storage
    for index in range(3):
        clock.instant += timedelta(minutes=1)
        prediction = create(operations, PredictionType.BINARY)
        operations.add_journal_entry(
            prediction.prediction_id,
            "Another marker passage",
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    page = operations.journal.query(JournalRequest(text="marker", limit=1))
    assert page.total == 3
    assert len(page.rows) == 1
    assert page.has_more
    assert len(page.rows[0].matches) >= 2
    oldest = operations.journal.query(
        JournalRequest(manual_sort=ArchiveSort.CREATED_OLDEST)
    )
    assert oldest.rows[0].prediction.prediction_id == 1
