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
    "BrierTrendPoint",
    "CalibrationBin",
    "ContainmentCalibrationBin",
    "ForecastAnalyticsSnapshot",
    "NumericAnalyticsSnapshot",
    "NumericAnalyticsSource",
    "NumericScoredPrediction",
    "NumericScoringObservation",
    "NumericUnitSummary",
    "ScoredPrediction",
    "ScoringObservation",
    "brier_score",
    "score_numeric_observation",
    "summarize_analytics",
    "summarize_forecast_analytics",
    "summarize_numeric_analytics",
]
