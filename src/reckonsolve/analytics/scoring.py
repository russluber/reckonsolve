"""Pure binary Brier, calibration, and cumulative-trend calculations."""

from dataclasses import dataclass
from datetime import datetime

from reckonsolve.domain.analytics import AnalyticsSource, ScoringObservation
from reckonsolve.domain.predictions import BinaryOutcome


@dataclass(frozen=True, slots=True)
class ScoredPrediction:
    """One exactly-once Brier contribution."""

    observation: ScoringObservation
    brier_score: float


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One fixed calibration band, occupied or empty."""

    lower_percent: int
    upper_percent: int
    count: int
    mean_forecast_percent: float | None
    observed_yes_percent: float | None

    @property
    def label(self) -> str:
        """Return the exact inclusive whole-number range shown to the user."""

        return f"{self.lower_percent}-{self.upper_percent}%"


@dataclass(frozen=True, slots=True)
class BrierTrendPoint:
    """Cumulative mean after one more prediction resolves."""

    resolution_id: int
    prediction_id: int
    resolved_at: datetime
    scored_count: int
    individual_brier: float
    cumulative_mean_brier: float


@dataclass(frozen=True, slots=True)
class AnalyticsSnapshot:
    """All three analytics views for one common scored subset."""

    scored_predictions: tuple[ScoredPrediction, ...]
    mean_brier: float | None
    calibration_bins: tuple[CalibrationBin, ...]
    brier_trend: tuple[BrierTrendPoint, ...]
    available_tags: tuple[str, ...]
    selected_tag: str | None = None

    @property
    def scored_prediction_count(self) -> int:
        """Return the number of resolved Predictions counted exactly once."""

        return len(self.scored_predictions)


def brier_score(probability_percent: int, outcome: BinaryOutcome) -> float:
    """Calculate binary Brier loss on the 0-through-1 scale."""

    if (
        isinstance(probability_percent, bool)
        or not isinstance(probability_percent, int)
        or not 0 <= probability_percent <= 100
    ):
        raise ValueError("Probability must be a whole number from 0 through 100.")
    if not isinstance(outcome, BinaryOutcome):
        raise TypeError("Outcome must be Yes or No.")
    probability = probability_percent / 100
    observed = 1.0 if outcome is BinaryOutcome.YES else 0.0
    return (probability - observed) ** 2


def summarize_analytics(
    source: AnalyticsSource,
    *,
    tag: str | None = None,
) -> AnalyticsSnapshot:
    """Build Brier, calibration, and cumulative views from one scored set."""

    _validate_scoring_observations(source.observations)
    tag_key = None if tag is None else tag.strip().casefold() or None
    observations = tuple(
        sorted(
            (
                observation
                for observation in source.observations
                if tag_key is None
                or tag_key in {item.casefold() for item in observation.tags}
            ),
            key=lambda observation: (
                observation.resolved_at,
                observation.resolution_id,
            ),
        )
    )
    scored = tuple(
        ScoredPrediction(
            observation=observation,
            brier_score=brier_score(
                observation.probability_percent,
                observation.outcome,
            ),
        )
        for observation in observations
    )
    mean_brier = (
        None if not scored else sum(item.brier_score for item in scored) / len(scored)
    )
    return AnalyticsSnapshot(
        scored_predictions=scored,
        mean_brier=mean_brier,
        calibration_bins=_calibration_bins(observations),
        brier_trend=_brier_trend(scored),
        available_tags=source.available_tags,
        selected_tag=tag,
    )


def _calibration_bins(
    observations: tuple[ScoringObservation, ...],
) -> tuple[CalibrationBin, ...]:
    members: list[list[ScoringObservation]] = [[] for _index in range(10)]
    for observation in observations:
        members[min(observation.probability_percent // 10, 9)].append(observation)

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
                    else sum(item.probability_percent for item in bin_members) / count
                ),
                observed_yes_percent=(
                    None
                    if not count
                    else 100
                    * sum(item.outcome is BinaryOutcome.YES for item in bin_members)
                    / count
                ),
            )
        )
    return tuple(bins)


def _brier_trend(
    scored: tuple[ScoredPrediction, ...],
) -> tuple[BrierTrendPoint, ...]:
    cumulative_total = 0.0
    points: list[BrierTrendPoint] = []
    for count, item in enumerate(scored, start=1):
        cumulative_total += item.brier_score
        observation = item.observation
        points.append(
            BrierTrendPoint(
                resolution_id=observation.resolution_id,
                prediction_id=observation.prediction_id,
                resolved_at=observation.resolved_at,
                scored_count=count,
                individual_brier=item.brier_score,
                cumulative_mean_brier=cumulative_total / count,
            )
        )
    return tuple(points)


def _validate_scoring_observations(
    observations: tuple[ScoringObservation, ...],
) -> None:
    prediction_ids = tuple(item.prediction_id for item in observations)
    resolution_ids = tuple(item.resolution_id for item in observations)
    if len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("Each resolved prediction must contribute exactly once.")
    if len(set(resolution_ids)) != len(resolution_ids):
        raise ValueError("Each Resolution must contribute exactly once.")
    for observation in observations:
        if (
            observation.resolved_at.tzinfo is None
            or observation.resolved_at.utcoffset() is None
        ):
            raise ValueError("Resolution timestamps must be timezone-aware.")
