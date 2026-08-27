"""Scoring and calibration calculations for resolved predictions."""

from reckonsolve.domain.analytics import (
    AnalyticsSource,
    NumericAnalyticsSource,
    NumericScoringObservation,
    ScoringObservation,
)

from .numeric import (
    ContainmentCalibrationBin,
    NumericAnalyticsSnapshot,
    NumericScoredPrediction,
    NumericUnitSummary,
    score_numeric_observation,
    summarize_numeric_analytics,
)
from .overview import ForecastAnalyticsSnapshot, summarize_forecast_analytics
from .scorecards import (
    BinaryScorecard,
    NumericScorecard,
    PredictionScorecard,
    binary_scorecard,
    numeric_scorecard,
)
from .scoring import (
    AnalyticsSnapshot,
    BrierTrendPoint,
    CalibrationBin,
    ScoredPrediction,
    brier_score,
    summarize_analytics,
)

__all__ = [
    "AnalyticsSnapshot",
    "AnalyticsSource",
    "BinaryScorecard",
    "BrierTrendPoint",
    "CalibrationBin",
    "ContainmentCalibrationBin",
    "ForecastAnalyticsSnapshot",
    "NumericAnalyticsSnapshot",
    "NumericAnalyticsSource",
    "NumericScorecard",
    "NumericScoredPrediction",
    "NumericScoringObservation",
    "NumericUnitSummary",
    "PredictionScorecard",
    "ScoredPrediction",
    "ScoringObservation",
    "binary_scorecard",
    "brier_score",
    "numeric_scorecard",
    "score_numeric_observation",
    "summarize_analytics",
    "summarize_forecast_analytics",
    "summarize_numeric_analytics",
]
