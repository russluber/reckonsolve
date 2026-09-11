"""Exact Binary standing-path scoring, independent of SQLite and Qt."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from fractions import Fraction

from reckonsolve.clock import as_utc
from reckonsolve.domain.forecast_contracts import (
    EffectiveResolutionTime,
    ForecastCohort,
    ForecastContract,
    ForecastingWindow,
    ResolutionTiming,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    ForecastRevision,
)


@dataclass(frozen=True, slots=True)
class StandingSegment:
    revision_id: int
    starts_at: datetime
    ends_at: datetime
    probability_percent: int
    duration_microseconds: int
    brier: Fraction


@dataclass(frozen=True, slots=True)
class TrajectoryScorecard:
    prediction_id: int
    resolution_id: int
    outcome: BinaryOutcome
    effective_resolution_at: datetime
    recorded_at: datetime
    deadline: datetime
    segments: tuple[StandingSegment, ...]
    neutral_microseconds: int
    excluded_revision_ids: tuple[int, ...]
    trajectory_brier: Fraction | None
    initial_brier: Fraction | None
    final_brier: Fraction | None
    hold_initial_brier: Fraction | None
    updating_gain: Fraction | None
    active_forecast_fraction: Fraction | None
    scoring_facts_corrected: bool
    unscored_reason: str | None = None


def _microseconds(duration: timedelta) -> int:
    return (
        (duration.days * 86400 + duration.seconds) * 1_000_000
    ) + duration.microseconds


def _loss(probability: int, outcome: BinaryOutcome) -> Fraction:
    if not 0 <= probability <= 100:
        raise ValueError("Binary probability must be between 0 and 100.")
    return (Fraction(probability, 100) - int(outcome is BinaryOutcome.YES)) ** 2


def trajectory_scorecard(
    contract: ForecastContract,
    revisions: tuple[ForecastRevision, ...],
    history: BinaryResolutionHistory,
) -> TrajectoryScorecard:
    """Score exactly one compatible Resolution; never manufacture a neutral revision."""
    if contract.cohort is not ForecastCohort.TRAJECTORY_BINARY or not revisions:
        raise ValueError("Trajectory scoring requires a trajectory Binary history.")
    assert contract.forecast_deadline is not None
    revisions = tuple(
        replace(revision, created_at=as_utc(revision.created_at))
        for revision in revisions
    )
    effective = history.effective
    timing = ResolutionTiming(
        EffectiveResolutionTime(effective.effective_resolution_at),
        effective.resolved_at,
    )
    window = ForecastingWindow(revisions[0].created_at, contract.forecast_deadline)
    for index, revision in enumerate(revisions):
        if (
            revision.prediction_id != effective.prediction_id
            or revision.sequence != index + 1
        ):
            raise ValueError(
                "Trajectory revisions must form one ordered Prediction history."
            )
        if index:
            window.validate_revision(
                previous_revision_at=revisions[index - 1].created_at,
                proposed_revision_at=revision.created_at,
            )
    cutoff = window.scoring_cutoff(timing.effective)
    eligible = tuple(revision for revision in revisions if revision.created_at < cutoff)
    excluded = tuple(
        revision.revision_id for revision in revisions if revision.created_at >= cutoff
    )
    common = {
        "prediction_id": effective.prediction_id,
        "resolution_id": effective.resolution_id,
        "outcome": effective.outcome,
        "effective_resolution_at": timing.effective.instant,
        "recorded_at": timing.recorded_at,
        "deadline": window.deadline.instant,
        "excluded_revision_ids": excluded,
        "scoring_facts_corrected": any(
            {"outcome", "effective_resolution_at"}.intersection(c.changed_fields)
            for c in history.corrections
        ),
    }
    if cutoff <= window.initial_revision_at:
        return TrajectoryScorecard(
            **common,
            segments=(),
            neutral_microseconds=0,
            trajectory_brier=None,
            initial_brier=None,
            final_brier=None,
            hold_initial_brier=None,
            updating_gain=None,
            active_forecast_fraction=None,
            unscored_reason="The outcome was already fixed at or before the first forecast. No score or calibration observation is produced.",
        )
    segments = tuple(
        StandingSegment(
            revision.revision_id,
            revision.created_at,
            eligible[index + 1].created_at if index + 1 < len(eligible) else cutoff,
            revision.probability_percent,
            _microseconds(
                (
                    eligible[index + 1].created_at
                    if index + 1 < len(eligible)
                    else cutoff
                )
                - revision.created_at
            ),
            _loss(revision.probability_percent, effective.outcome),
        )
        for index, revision in enumerate(eligible)
    )
    total = _microseconds(window.deadline.instant - window.initial_revision_at)
    neutral = _microseconds(window.deadline.instant - cutoff)
    weighted_loss = sum(
        (segment.duration_microseconds * segment.brier for segment in segments),
        Fraction(),
    )
    score = (weighted_loss + Fraction(neutral, 4)) / total
    initial = _loss(revisions[0].probability_percent, effective.outcome)
    hold = ((total - neutral) * initial + Fraction(neutral, 4)) / total
    return TrajectoryScorecard(
        **common,
        segments=segments,
        neutral_microseconds=neutral,
        trajectory_brier=score,
        initial_brier=initial,
        final_brier=segments[-1].brier,
        hold_initial_brier=hold,
        updating_gain=hold - score,
        active_forecast_fraction=Fraction(total - neutral, total),
    )
