"""M52 terminal workflows use effective time, never the recorded revision anchor."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from reckonsolve.application.errors import (
    ConcurrentLifecycleUpdateError,
    ConcurrentTerminalCorrectionError,
    LifecycleTransitionNotAllowedError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.search_index import SearchIndexRepairRequiredError
from reckonsolve.domain.quantiles import NumericValueConstraint

START = datetime(2026, 9, 12, 12, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = START

    def now(self):
        return self.instant


@pytest.fixture
def active(tmp_path):
    db = Database.open(tmp_path / "quantile.sqlite3")
    clock = Clock()
    ops = PredictionOperations(db, clock, UTC)
    yield db, clock, ops
    db.close()


def create(ops, constraint=NumericValueConstraint.CONTINUOUS, precision=0):
    return ops.create_numeric_prediction(
        "How many units?",
        "units",
        precision,
        {5: -10, 25: -5, 50: 0, 75: 5, 95: 10},
        value_constraint=constraint,
        forecast_deadline=START + timedelta(hours=4),
    )


def context(p):
    return {
        "expected_revision_id": p.current_revision.revision_id,
        "expected_metadata_version": p.metadata_version,
    }


@pytest.mark.parametrize("hours", [2, 4, 8])
def test_resolution_and_correction_reselection(active, hours):
    _db, clock, ops = active
    p = create(ops)
    first = p.current_revision
    clock.instant += timedelta(hours=1)
    p = ops.revise_quantile_forecast(
        p.prediction_id, {5: 0, 25: 5, 50: 10, 75: 15, 95: 20}, **context(p)
    )
    clock.instant = START + timedelta(hours=9)
    saved = ops.resolve_numeric_prediction(
        p.prediction_id,
        10,
        effective_resolution_at=START + timedelta(hours=hours),
        **context(p),
    )
    card = ops.get_prediction_scorecard(p.prediction_id)
    assert card.final_revision_id == p.current_revision.revision_id
    assert card.final.wis == Fraction(7, 5)
    assert saved.resolution.resolved_at == clock.instant
    original = ops.get_numeric_resolution_history(p.prediction_id).original
    history = ops.correct_numeric_resolution(
        p.prediction_id,
        10,
        effective_resolution_at=START + timedelta(hours=1),
        resolution_notes="source correction",
        postmortem=None,
        correction_reason="Timing evidence",
        expected_correction_id=None,
    )
    card = ops.get_prediction_scorecard(p.prediction_id)
    assert card.final_revision_id == first.revision_id
    assert card.excluded_revision_ids == (p.current_revision.revision_id,)
    assert card.delta_wis == 0
    assert card.scoring_facts_corrected
    assert history.original == original
    assert history.effective.resolved_at == original.resolved_at
    assert ops.search_predictions("Timing evidence").hits
    assert ops.search_predictions("source correction").hits
    assert ops.get_dashboard().needs_postmortem_predictions
    with pytest.raises(ConcurrentTerminalCorrectionError):
        ops.correct_numeric_resolution(
            p.prediction_id,
            10,
            resolution_notes="stale",
            postmortem=None,
            expected_correction_id=None,
        )
    history = ops.correct_numeric_resolution(
        p.prediction_id,
        10,
        resolution_notes="new source",
        postmortem="reflection",
        expected_correction_id=history.current_correction_id,
    )
    assert not ops.get_dashboard().needs_postmortem_predictions
    assert not ops.search_predictions("source correction").hits
    assert (
        ops.get_numeric_prediction(p.prediction_id).resolution.postmortem
        == "reflection"
    )


@pytest.mark.parametrize("hours", [-1, 0])
def test_no_score_before_initial_and_correct_back(active, hours):
    _, clock, ops = active
    p = create(ops)
    clock.instant += timedelta(hours=2)
    ops.resolve_numeric_prediction(
        p.prediction_id,
        0,
        effective_resolution_at=START + timedelta(hours=hours),
        **context(p),
    )
    card = ops.get_prediction_scorecard(p.prediction_id)
    assert card.final is None and card.unscored_reason
    ops.correct_numeric_resolution(
        p.prediction_id,
        0,
        effective_resolution_at=START + timedelta(hours=1),
        resolution_notes=None,
        postmortem=None,
        correction_reason="Found source time",
        expected_correction_id=None,
    )
    assert ops.get_prediction_scorecard(p.prediction_id).final is not None


def test_whole_numbers_and_required_time_are_enforced(active):
    _, clock, ops = active
    p = create(ops, NumericValueConstraint.WHOLE_NUMBER, 2)
    clock.instant += timedelta(hours=1)
    for kwargs in (
        {},
        {"use_recorded_time": True, "effective_resolution_at": START},
        {"effective_resolution_at": clock.instant + timedelta(seconds=1)},
    ):
        with pytest.raises(ValidationError):
            ops.resolve_numeric_prediction(p.prediction_id, 0, **kwargs, **context(p))
    with pytest.raises(ValidationError):
        ops.resolve_numeric_prediction(
            p.prediction_id, "1.25", use_recorded_time=True, **context(p)
        )
    resolved = ops.resolve_numeric_prediction(
        p.prediction_id, "1.00", use_recorded_time=True, **context(p)
    )
    assert (
        resolved.resolution.effective_resolution_at
        == resolved.resolution.resolved_at
        == clock.instant
    )
    with pytest.raises(ValidationError):
        ops.correct_numeric_resolution(
            p.prediction_id,
            "1.25",
            resolution_notes=None,
            postmortem=None,
            correction_reason="change",
            expected_correction_id=None,
        )


@pytest.mark.parametrize(
    "actual,expected",
    [("-1.25", 0), ("-1.00", Fraction(1, 4)), ("-1.50", Fraction(1, 4))],
)
def test_tied_zero_width_signed_decimal_resolution(active, actual, expected):
    _, clock, ops = active
    p = ops.create_numeric_prediction(
        "Ties?",
        "units",
        2,
        {level: "-1.25" for level in (5, 25, 50, 75, 95)},
        value_constraint=NumericValueConstraint.CONTINUOUS,
        forecast_deadline=START + timedelta(hours=1),
    )
    clock.instant += timedelta(minutes=1)
    ops.resolve_numeric_prediction(
        p.prediction_id, actual, use_recorded_time=True, **context(p)
    )
    card = ops.get_prediction_scorecard(p.prediction_id)
    assert card.final.wis == expected
    assert card.delta_wis == 0
    assert card.final.interval_50.width == card.final.interval_90.width == 0
    assert (
        card.final.wis
        == card.final.median_contribution
        + card.final.interval_50_contribution
        + card.final.interval_90_contribution
    )


def test_transaction_clock_staleness_regression_and_one_way_terminal(active):
    db, clock, ops = active
    initial = create(ops)
    clock.instant += timedelta(minutes=1)
    p = ops.revise_quantile_forecast(
        initial.prediction_id,
        {5: -10, 25: -5, 50: 1, 75: 5, 95: 10},
        **context(initial),
    )
    with pytest.raises(ConcurrentLifecycleUpdateError):
        ops.resolve_numeric_prediction(
            p.prediction_id, 1, use_recorded_time=True, **context(initial)
        )
    clock.instant = START
    with pytest.raises(ValidationError):
        ops.resolve_numeric_prediction(
            p.prediction_id, 1, use_recorded_time=True, **context(p)
        )
    outside, inside = START + timedelta(minutes=2), START + timedelta(minutes=3)

    class TransactionClock:
        def now(self):
            return inside if db._connection.in_transaction else outside

    transaction_ops = PredictionOperations(db, TransactionClock(), UTC)
    saved = transaction_ops.resolve_numeric_prediction(
        p.prediction_id, 1, use_recorded_time=True, **context(p)
    )
    assert (
        saved.resolution.resolved_at
        == saved.resolution.effective_resolution_at
        == inside
    )
    history = transaction_ops.correct_numeric_resolution(
        p.prediction_id,
        1,
        resolution_notes="Text only",
        postmortem=None,
        expected_correction_id=None,
    )
    assert history.corrections[0].corrected_at == inside
    assert not transaction_ops.get_prediction_scorecard(
        p.prediction_id
    ).scoring_facts_corrected
    with pytest.raises(LifecycleTransitionNotAllowedError, match="resolved"):
        ops.resolve_numeric_prediction(
            p.prediction_id, 1, use_recorded_time=True, **context(p)
        )


def test_correction_reason_and_original_recorded_time_limit(active):
    _, clock, ops = active
    p = create(ops)
    clock.instant += timedelta(hours=1)
    ops.resolve_numeric_prediction(
        p.prediction_id, 0, use_recorded_time=True, **context(p)
    )
    original = ops.get_numeric_resolution_history(p.prediction_id)
    clock.instant += timedelta(hours=2)
    for actual, time, reason in (
        (10, original.original.effective_resolution_at, None),
        (0, START, None),
        (0, START + timedelta(hours=2), "Cannot exceed original recorded-at"),
        (0, START.replace(tzinfo=None), "Naive time"),
    ):
        with pytest.raises(ValidationError):
            ops.correct_numeric_resolution(
                p.prediction_id,
                actual,
                effective_resolution_at=time,
                resolution_notes=None,
                postmortem=None,
                correction_reason=reason,
                expected_correction_id=None,
            )
        assert ops.get_numeric_resolution_history(p.prediction_id) == original


def test_concurrent_write_after_preflight_is_rechecked(active, monkeypatch):
    db, clock, ops = active
    p = create(ops)
    other_db = Database.open(db.path)
    other = PredictionOperations(other_db, clock, UTC)
    try:
        resolve = ops._quantiles.repository.resolve_prediction

        def concurrent_revision(*args, **kwargs):
            clock.instant += timedelta(minutes=1)
            other.revise_quantile_forecast(
                p.prediction_id, {5: -10, 25: -5, 50: 1, 75: 5, 95: 10}, **context(p)
            )
            return resolve(*args, **kwargs)

        monkeypatch.setattr(
            ops._quantiles.repository, "resolve_prediction", concurrent_revision
        )
        with pytest.raises(ConcurrentLifecycleUpdateError):
            ops.resolve_numeric_prediction(
                p.prediction_id, 0, use_recorded_time=True, **context(p)
            )
        p = other.get_numeric_prediction(p.prediction_id)
        assert p.resolution is None
        clock.instant += timedelta(minutes=1)
        other.resolve_numeric_prediction(
            p.prediction_id, 0, use_recorded_time=True, **context(p)
        )
        correct = ops._terminal_history_repository.append_numeric_resolution_correction

        def concurrent_correction(*args, **kwargs):
            other.correct_numeric_resolution(
                p.prediction_id,
                0,
                resolution_notes="Other interface",
                postmortem=None,
                expected_correction_id=None,
            )
            return correct(*args, **kwargs)

        monkeypatch.setattr(
            ops._terminal_history_repository,
            "append_numeric_resolution_correction",
            concurrent_correction,
        )
        with pytest.raises(ConcurrentTerminalCorrectionError):
            ops.correct_numeric_resolution(
                p.prediction_id,
                10,
                correction_reason="Stale actual",
                resolution_notes=None,
                postmortem=None,
                expected_correction_id=None,
            )
        history = other.get_numeric_resolution_history(p.prediction_id)
        assert len(history.corrections) == 1
        assert history.effective.actual_value.scaled_value == 0
        assert history.effective.resolution_notes == "Other interface"
    finally:
        other_db.close()


@pytest.mark.parametrize("correct", [False, True])
def test_search_failure_rolls_back_terminal_write(active, monkeypatch, correct):
    db, clock, ops = active
    p = create(ops)
    clock.instant += timedelta(hours=1)
    if correct:
        ops.resolve_numeric_prediction(
            p.prediction_id, 0, use_recorded_time=True, **context(p)
        )
    before = ops.get_prediction_scorecard(p.prediction_id)

    def fail(*_args):
        raise sqlite3.OperationalError("injected projection failure")

    monkeypatch.setattr("reckonsolve.data.search_index._insert_documents", fail)
    with pytest.raises(SearchIndexRepairRequiredError):
        if correct:
            ops.correct_numeric_resolution(
                p.prediction_id,
                10,
                resolution_notes="Changed source",
                postmortem=None,
                correction_reason="Typo",
                expected_correction_id=None,
            )
        else:
            ops.resolve_numeric_prediction(
                p.prediction_id,
                0,
                use_recorded_time=True,
                resolution_notes="Source",
                **context(p),
            )
    assert ops.get_prediction_scorecard(p.prediction_id) == before
    if correct:
        assert not ops.get_numeric_resolution_history(p.prediction_id).corrections
    else:
        assert ops.get_numeric_prediction(p.prediction_id).resolution is None
    db.check_search_index()


def test_corrected_postmortem_skip_backup_restart(active, tmp_path):
    db, clock, ops = active
    p = create(ops)
    clock.instant += timedelta(hours=2)
    ops.resolve_numeric_prediction(
        p.prediction_id,
        0,
        use_recorded_time=True,
        postmortem="Original reflection",
        **context(p),
    )
    history = ops.correct_numeric_resolution(
        p.prediction_id,
        10,
        resolution_notes="amended source",
        postmortem=None,
        correction_reason="Correct actual",
        expected_correction_id=None,
    )
    queued = ops.get_dashboard().needs_postmortem_predictions
    assert (
        next(
            q for q in queued if q.prediction_id == p.prediction_id
        ).numeric_actual_value.scaled_value
        == 10
    )
    assert (
        ops.search_predictions("How many")
        .hits[0]
        .prediction.numeric_actual_value.scaled_value
        == 10
    )
    ops.record_postmortem_skip(
        p.prediction_id, expected_correction_id=history.current_correction_id
    )
    assert p.prediction_id not in [
        q.prediction_id for q in ops.get_dashboard().needs_postmortem_predictions
    ]
    assert not ops.search_predictions("Original reflection").hits
    card = ops.get_prediction_scorecard(p.prediction_id)
    assert len(ops._analytics_repository.get_forecast_sources()[1].records) == 1
    path = tmp_path / "backup.sqlite3"
    ops.create_backup(path)
    db.close()
    for source in (db.path, path):
        restored = Database.open(source)
        try:
            recovered = PredictionOperations(restored, clock, UTC)
            assert recovered.get_prediction_scorecard(p.prediction_id) == card
            assert recovered.get_numeric_resolution_history(
                p.prediction_id
            ).postmortem_completion
            assert recovered.get_numeric_prediction(
                p.prediction_id
            ).resolution.effective_resolution_at == START + timedelta(hours=2)
            restored.check_search_index()
        finally:
            restored.close()
