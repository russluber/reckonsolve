"""M48 exact scoring, honest terminal history, and compatibility boundaries."""

import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, tzinfo
from fractions import Fraction

import pytest

from reckonsolve.analytics.trajectory import trajectory_scorecard
from reckonsolve.application.errors import (
    ConcurrentLifecycleUpdateError,
    ConcurrentTerminalCorrectionError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS
from reckonsolve.data.search_index import SearchIndexRepairRequiredError
from reckonsolve.domain.predictions import BinaryOutcome

START = datetime(2026, 9, 10, 12, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = START

    def now(self):
        return self.instant


@pytest.fixture
def active(tmp_path):
    database = Database.open(tmp_path / "trajectory.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    yield database, clock, operations
    database.close()


def context(prediction):
    return {
        "expected_revision_id": prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


@pytest.mark.parametrize(
    "hours, expected, neutral",
    [(2, Fraction(23, 80), 2), (4, Fraction(67, 400), 0), (8, Fraction(67, 400), 0)],
)
def test_exact_segments_early_deadline_and_late_resolution(
    active, hours, expected, neutral
):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Window?", 20, forecast_deadline=START + timedelta(hours=4)
    )
    clock.instant += timedelta(hours=1)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 90, **context(prediction)
    )
    clock.instant = START + timedelta(hours=9)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START + timedelta(hours=hours),
        **context(prediction),
    )
    card = operations.get_prediction_scorecard(prediction.prediction_id)
    # Early: (.64 * 1h + .01 * 1h + .25 * 2h) / 4h = .2875.
    assert card.trajectory_brier == expected
    assert card.neutral_microseconds == neutral * 3600 * 1_000_000
    assert card.final_brier == Fraction(1, 100)
    assert card.initial_brier == Fraction(16, 25)
    assert card.updating_gain == card.hold_initial_brier - card.trajectory_brier
    assert card.active_forecast_fraction == Fraction(min(hours, 4), 4)
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 2
    assert not operations.get_analytics().scored_predictions


def test_time_correction_reselects_without_erasing_post_effective_revisions(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Delayed entry?", 20, forecast_deadline=START + timedelta(hours=4)
    )
    initial = prediction.current_revision_id
    clock.instant += timedelta(hours=1)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 90, **context(prediction)
    )
    latest = prediction.current_revision_id
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START + timedelta(hours=1),
        **context(prediction),
    )
    before = operations.get_prediction_scorecard(prediction.prediction_id)
    assert [s.revision_id for s in before.segments] == [initial]
    assert before.excluded_revision_ids == (latest,)
    original = operations.get_binary_resolution_history(
        prediction.prediction_id
    ).original
    history = operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.NO,
        effective_resolution_at=START + timedelta(hours=2),
        resolution_notes="Verified source",
        postmortem="Reflection",
        correction_reason="Corrected source chronology",
        expected_correction_id=None,
    )
    after = operations.get_prediction_scorecard(prediction.prediction_id)
    assert len(after.segments) == 2
    assert not after.excluded_revision_ids
    assert after.scoring_facts_corrected
    assert history.original == original
    assert history.effective.resolved_at == original.resolved_at
    assert operations.search_predictions("chronology").hits
    assert operations.search_predictions("Reflection").hits
    assert not operations.get_dashboard().needs_postmortem_predictions
    with pytest.raises(ConcurrentTerminalCorrectionError):
        operations.correct_binary_resolution(
            prediction.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="stale",
            postmortem=None,
            expected_correction_id=None,
        )


@pytest.mark.parametrize("offset", [-1, 0])
def test_outcome_fixed_at_or_before_creation_is_unscored(active, offset):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Already fixed?", 50, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(minutes=5)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START + timedelta(microseconds=offset),
        **context(prediction),
    )
    card = operations.get_prediction_scorecard(prediction.prediction_id)
    assert card.trajectory_brier is None
    assert card.unscored_reason
    assert not card.segments


def test_effective_time_validation_and_explanation_are_atomic(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Times?", 50, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(minutes=5)
    for invalid in (
        None,
        clock.instant + timedelta(seconds=1),
        clock.instant.replace(tzinfo=None),
    ):
        with pytest.raises(ValidationError):
            operations.resolve_prediction(
                prediction.prediction_id,
                BinaryOutcome.YES,
                effective_resolution_at=invalid,
                **context(prediction),
            )
    assert operations.get_prediction(prediction.prediction_id).resolution is None
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **context(prediction),
    )
    for invalid, reason in (
        (START + timedelta(minutes=1), None),
        (clock.instant + timedelta(minutes=1), "future"),
    ):
        with pytest.raises(ValidationError):
            operations.correct_binary_resolution(
                prediction.prediction_id,
                BinaryOutcome.YES,
                effective_resolution_at=invalid,
                resolution_notes=None,
                postmortem=None,
                correction_reason=reason,
                expected_correction_id=None,
            )
    assert not operations.get_binary_resolution_history(
        prediction.prediction_id
    ).corrections


@pytest.mark.parametrize(
    "probability, outcome, loss",
    [
        (0, BinaryOutcome.YES, 1),
        (100, BinaryOutcome.YES, 0),
        (0, BinaryOutcome.NO, 0),
        (100, BinaryOutcome.NO, 1),
    ],
)
def test_single_forecast_has_no_updating_gain(active, probability, outcome, loss):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Endpoint?", probability, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id, outcome, use_recorded_time=True, **context(prediction)
    )
    card = operations.get_prediction_scorecard(prediction.prediction_id)
    assert card.trajectory_brier == card.initial_brier == card.final_brier == loss
    assert card.updating_gain == 0
    assert card.active_forecast_fraction == 1


def test_microsecond_segments_and_repeated_probabilities_are_exact(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Tiny window?", 0, forecast_deadline=START + timedelta(microseconds=10)
    )
    clock.instant += timedelta(microseconds=1)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 100, **context(prediction)
    )
    clock.instant += timedelta(microseconds=2)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 0, **context(prediction)
    )
    clock.instant += timedelta(microseconds=3)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction),
    )
    card = operations.get_prediction_scorecard(prediction.prediction_id)
    assert [s.duration_microseconds for s in card.segments] == [1, 2, 3]
    assert card.neutral_microseconds == 4
    assert card.trajectory_brier == Fraction(1, 2)
    assert card.hold_initial_brier == Fraction(7, 10)
    assert card.updating_gain == Fraction(1, 5)
    assert card.active_forecast_fraction == Fraction(3, 5)


def test_pure_segments_normalize_dst_offsets_before_subtracting(active):
    _, clock, operations = active
    # Los Angeles repeats 01:30 during this interval; real elapsed time is one hour.
    clock.instant = datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    start = clock.instant
    prediction = operations.create_prediction(
        "Repeated hour?", 0, forecast_deadline=start + timedelta(hours=2)
    )
    clock.instant += timedelta(hours=1)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 100, **context(prediction)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction),
    )

    class RepeatedHour(tzinfo):
        def utcoffset(self, dt):
            return timedelta(hours=-8 if dt.fold else -7)

        def dst(self, dt):
            return timedelta(0)

    zone = RepeatedHour()
    revisions = tuple(
        replace(r, created_at=datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=index))
        for index, r in enumerate(
            operations.list_forecast_revisions(prediction.prediction_id)
        )
    )
    card = trajectory_scorecard(
        prediction.forecast_contract,
        revisions,
        operations.get_binary_resolution_history(prediction.prediction_id),
    )
    assert card.trajectory_brier == Fraction(1, 2)
    assert [s.duration_microseconds for s in card.segments] == [3_600_000_000] * 2


def test_recording_clock_is_acquired_under_transaction_and_stale_context_fails(active):
    database, clock, operations = active
    initial = operations.create_prediction(
        "Stale?", 40, forecast_deadline=START + timedelta(hours=4)
    )
    clock.instant += timedelta(minutes=1)
    latest = operations.revise_forecast(initial.prediction_id, 60, **context(initial))
    with pytest.raises(ConcurrentLifecycleUpdateError):
        operations.resolve_prediction(
            initial.prediction_id,
            BinaryOutcome.YES,
            use_recorded_time=True,
            **context(initial),
        )
    outside = START + timedelta(minutes=2)
    inside = outside + timedelta(seconds=1)

    class TransactionClock:
        def now(self):
            return inside if database._connection.in_transaction else outside

    resolved = PredictionOperations(
        database, TransactionClock(), UTC
    ).resolve_prediction(
        latest.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(latest),
    )
    assert (
        resolved.resolution.resolved_at
        == resolved.resolution.effective_resolution_at
        == inside
    )


def test_time_correction_can_remove_and_restore_score_and_text_only_does_not(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Honest correction?", 80, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction),
    )
    original = operations.get_binary_resolution_history(
        prediction.prediction_id
    ).original
    before = operations.get_prediction_scorecard(prediction.prediction_id)
    history = operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Typos fixed",
        postmortem=None,
        expected_correction_id=None,
    )
    assert operations.get_prediction_scorecard(prediction.prediction_id) == before
    history = operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START,
        resolution_notes=history.effective.resolution_notes,
        postmortem=None,
        correction_reason="Source was already public",
        expected_correction_id=history.current_correction_id,
    )
    assert operations.get_prediction_scorecard(prediction.prediction_id).unscored_reason
    history = operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        resolution_notes=None,
        postmortem=None,
        correction_reason="Correct source publication time",
        expected_correction_id=history.current_correction_id,
    )
    assert (
        operations.get_prediction_scorecard(prediction.prediction_id).trajectory_brier
        == before.trajectory_brier
    )
    assert history.original == original
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 1


def test_search_failure_rolls_back_correction_and_effective_score(active, monkeypatch):
    database, clock, operations = active
    prediction = operations.create_prediction(
        "Atomic correction?", 70, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction),
    )
    before = operations.get_prediction_scorecard(prediction.prediction_id)

    def fail_insert(connection, documents):
        assert (
            connection.execute(
                "SELECT count(*) FROM binary_trajectory_resolution_corrections"
            ).fetchone()[0]
            == 1
        )
        raise sqlite3.OperationalError("injected search failure")

    monkeypatch.setattr("reckonsolve.data.search_index._insert_documents", fail_insert)
    with pytest.raises(SearchIndexRepairRequiredError):
        operations.correct_binary_resolution(
            prediction.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="New finding",
            postmortem=None,
            correction_reason="New source",
            expected_correction_id=None,
        )
    assert not operations.get_binary_resolution_history(
        prediction.prediction_id
    ).corrections
    assert operations.get_prediction_scorecard(prediction.prediction_id) == before
    database.check_search_index()


def test_corrected_postmortem_clear_skip_and_backup_survive_restart(active, tmp_path):
    database, clock, operations = active
    prediction = operations.create_prediction(
        "Recovery?",
        70,
        forecast_deadline=START + timedelta(hours=1),
        tags=("trajectory only",),
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        postmortem="Original reflection",
        use_recorded_time=True,
        **context(prediction),
    )
    history = operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Source amended",
        postmortem=None,
        correction_reason="Wrong outcome",
        expected_correction_id=None,
    )
    assert (
        operations.get_dashboard().needs_postmortem_predictions[0].prediction_id
        == prediction.prediction_id
    )
    operations.record_postmortem_skip(
        prediction.prediction_id, expected_correction_id=history.current_correction_id
    )
    assert not operations.get_dashboard().needs_postmortem_predictions
    assert not operations.get_analytics().available_tags
    assert operations.search_predictions("amended").hits
    assert not operations.search_predictions("reflection").hits
    card = operations.get_prediction_scorecard(prediction.prediction_id)
    path = tmp_path / "recovery.sqlite3"
    operations.create_backup(path)
    database.close()
    for reopen_path in (database.path, path):
        restored = Database.open(reopen_path)
        try:
            recovered = PredictionOperations(restored, clock, UTC)
            assert recovered.get_prediction_scorecard(prediction.prediction_id) == card
            assert recovered.get_binary_resolution_history(
                prediction.prediction_id
            ).postmortem_completion
            restored.check_search_index()
        finally:
            restored.close()


def test_schema17_integrates_existing_trajectory_corrections_without_rewriting_history(
    tmp_path,
):
    path = tmp_path / "upgrade.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:16])
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    prediction = operations.create_prediction(
        "Migration?", 75, forecast_deadline=START + timedelta(hours=1)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        **context(prediction),
    )
    operations.correct_binary_resolution(
        prediction.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Migrated source",
        postmortem="Migration reflection",
        correction_reason="Misread",
        expected_correction_id=None,
    )
    before = operations.get_binary_resolution_history(prediction.prediction_id)
    database.close()
    # A failed migration must leave both version and DDL untouched.
    broken = replace(
        MIGRATIONS[16],
        statements=(
            *MIGRATIONS[16].statements,
            "SELECT missing_m48_column FROM predictions",
        ),
    )
    with pytest.raises(sqlite3.OperationalError):
        Database.open(path, migrations=(*MIGRATIONS[:16], broken))
    with sqlite3.connect(path) as raw:
        assert not raw.execute(
            "SELECT name FROM sqlite_master WHERE name = 'binary_resolution_history_rows'"
        ).fetchall()
    database = Database.open(path)
    try:
        recovered = PredictionOperations(database, clock, UTC)
        assert database.schema_version == 17
        assert (
            recovered.get_binary_resolution_history(prediction.prediction_id) == before
        )
        assert recovered.search_predictions("Migrated").hits
        assert not recovered.get_dashboard().needs_postmortem_predictions
        database.check_search_index()
    finally:
        database.close()
