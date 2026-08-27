"""Pure per-Prediction scorecards built from captured scoring observations."""

from dataclasses import dataclass
from decimal import Decimal

from reckonsolve.domain.analytics import (
    NumericScoringObservation,
    ScoringObservation,
)
from reckonsolve.domain.predictions import BinaryOutcome, FixedPrecisionValue

from .numeric import score_numeric_observation
from .scoring import brier_score


@dataclass(frozen=True, slots=True)
class BinaryScorecard:
    """One Binary Resolution's immutable scoring forecast and effective result."""

    prediction_id: int
    resolution_id: int
    scoring_revision_id: int
    probability_percent: int
    outcome: BinaryOutcome
    brier_score: float
    outcome_corrected: bool


@dataclass(frozen=True, slots=True)
class NumericScorecard:
    """One Numeric Resolution's immutable interval and effective exact result."""

    prediction_id: int
    resolution_id: int
    scoring_revision_id: int
    unit: str
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    actual_value: FixedPrecisionValue
    contained: bool
    median_absolute_error: Decimal
    interval_width: Decimal
    interval_score: Decimal
    actual_value_corrected: bool


PredictionScorecard = BinaryScorecard | NumericScorecard


def binary_scorecard(observation: ScoringObservation) -> BinaryScorecard:
    """Build a Binary scorecard from exactly one captured scoring observation."""

    return BinaryScorecard(
        prediction_id=observation.prediction_id,
        resolution_id=observation.resolution_id,
        scoring_revision_id=observation.scoring_revision_id,
        probability_percent=observation.probability_percent,
        outcome=observation.outcome,
        brier_score=brier_score(observation.probability_percent, observation.outcome),
        outcome_corrected=observation.outcome_corrected,
    )


def numeric_scorecard(observation: NumericScoringObservation) -> NumericScorecard:
    """Build a Numeric scorecard from exactly one captured scoring observation."""

    scored = score_numeric_observation(observation)
    return NumericScorecard(
        prediction_id=observation.prediction_id,
        resolution_id=observation.resolution_id,
        scoring_revision_id=observation.scoring_revision_id,
        unit=observation.unit,
        lower_bound=observation.lower_bound,
        median_estimate=observation.median_estimate,
        upper_bound=observation.upper_bound,
        confidence_percent=observation.confidence_percent,
        actual_value=observation.actual_value,
        contained=scored.contained,
        median_absolute_error=scored.median_absolute_error,
        interval_width=scored.interval_width,
        interval_score=scored.interval_score,
        actual_value_corrected=observation.actual_value_corrected,
    )
