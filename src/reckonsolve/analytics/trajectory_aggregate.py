"""Equal-Prediction aggregate analytics for trajectory Binary forecasts."""

from dataclasses import dataclass
from fractions import Fraction

from reckonsolve.domain.analytics import TrajectoryAnalyticsSource
from reckonsolve.domain.predictions import BinaryOutcome

from .scoring import CalibrationBin
from .trajectory import TrajectoryScorecard, trajectory_scorecard


@dataclass(frozen=True, slots=True)
class TrajectoryScoredPrediction:
    """One equally weighted, eligible trajectory Binary contribution."""

    question: str
    tags: tuple[str, ...]
    scorecard: TrajectoryScorecard
    final_probability_percent: int


@dataclass(frozen=True, slots=True)
class TrajectoryAnalyticsSnapshot:
    """Primary trajectory aggregate, timing facts, and separate diagnostics."""

    scored_predictions: tuple[TrajectoryScoredPrediction, ...]
    resolved_candidate_count: int
    unscored_prediction_count: int
    mean_trajectory_brier: Fraction | None
    mean_initial_brier: Fraction | None
    mean_final_brier: Fraction | None
    mean_hold_initial_brier: Fraction | None
    mean_updating_gain: Fraction | None
    mean_active_forecast_fraction: Fraction | None
    early_resolution_count: int
    reached_deadline_count: int
    positive_updating_gain_count: int
    equal_updating_gain_count: int
    negative_updating_gain_count: int
    final_calibration_bins: tuple[CalibrationBin, ...]
    available_tags: tuple[str, ...]
    selected_tag: str | None = None

    @property
    def scored_prediction_count(self) -> int:
        return len(self.scored_predictions)


def summarize_trajectory_analytics(
    source: TrajectoryAnalyticsSource,
    *,
    tag: str | None = None,
) -> TrajectoryAnalyticsSnapshot:
    """Score each eligible Prediction once; never weight one Prediction by another's duration."""

    tag_key = None if tag is None else tag.strip().casefold() or None
    available_tags = _unique_tags(
        item for record in source.records for item in record.tags
    )
    records = tuple(
        record
        for record in source.records
        if tag_key is None or tag_key in {item.casefold() for item in record.tags}
    )
    cards = tuple(
        (
            record,
            trajectory_scorecard(
                record.contract,
                record.revisions,
                record.resolution_history,
            ),
        )
        for record in records
    )
    prediction_ids = tuple(card.prediction_id for _record, card in cards)
    resolution_ids = tuple(card.resolution_id for _record, card in cards)
    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("Each trajectory Prediction must contribute at most once.")
    if len(set(resolution_ids)) != len(resolution_ids):
        raise ValueError("Each trajectory Resolution must contribute at most once.")
    scored = tuple(
        TrajectoryScoredPrediction(
            question=record.question,
            tags=record.tags,
            scorecard=card,
            final_probability_percent=card.segments[-1].probability_percent,
        )
        for record, card in cards
        if card.trajectory_brier is not None
    )
    gains = tuple(item.scorecard.updating_gain for item in scored)
    assert all(gain is not None for gain in gains)
    return TrajectoryAnalyticsSnapshot(
        scored_predictions=scored,
        resolved_candidate_count=len(records),
        unscored_prediction_count=len(records) - len(scored),
        mean_trajectory_brier=_mean(item.scorecard.trajectory_brier for item in scored),
        mean_initial_brier=_mean(item.scorecard.initial_brier for item in scored),
        mean_final_brier=_mean(item.scorecard.final_brier for item in scored),
        mean_hold_initial_brier=_mean(
            item.scorecard.hold_initial_brier for item in scored
        ),
        mean_updating_gain=_mean(gains),
        mean_active_forecast_fraction=_mean(
            item.scorecard.active_forecast_fraction for item in scored
        ),
        early_resolution_count=sum(
            item.scorecard.effective_resolution_at < item.scorecard.deadline
            for item in scored
        ),
        reached_deadline_count=sum(
            item.scorecard.effective_resolution_at >= item.scorecard.deadline
            for item in scored
        ),
        positive_updating_gain_count=sum(gain > 0 for gain in gains),
        equal_updating_gain_count=sum(gain == 0 for gain in gains),
        negative_updating_gain_count=sum(gain < 0 for gain in gains),
        final_calibration_bins=_final_calibration_bins(scored),
        available_tags=available_tags,
        selected_tag=tag,
    )


def _mean(values) -> Fraction | None:
    present = tuple(value for value in values if value is not None)
    return None if not present else sum(present, Fraction()) / len(present)


def _unique_tags(tags) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for tag in tags:
        by_key.setdefault(tag.casefold(), tag)
    return tuple(by_key[key] for key in sorted(by_key))


def _final_calibration_bins(
    scored: tuple[TrajectoryScoredPrediction, ...],
) -> tuple[CalibrationBin, ...]:
    members: list[list[TrajectoryScoredPrediction]] = [[] for _index in range(10)]
    for item in scored:
        members[min(item.final_probability_percent // 10, 9)].append(item)
    bins: list[CalibrationBin] = []
    for index, bin_members in enumerate(members):
        lower = index * 10
        upper = 100 if index == 9 else lower + 9
        count = len(bin_members)
        bins.append(
            CalibrationBin(
                lower_percent=lower,
                upper_percent=upper,
                count=count,
                mean_forecast_percent=(
                    None
                    if not count
                    else sum(item.final_probability_percent for item in bin_members)
                    / count
                ),
                observed_yes_percent=(
                    None
                    if not count
                    else 100
                    * sum(
                        item.scorecard.outcome is BinaryOutcome.YES
                        for item in bin_members
                    )
                    / count
                ),
            )
        )
    return tuple(bins)
