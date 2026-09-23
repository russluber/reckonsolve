"""Supported forecast scoring and calibration calculations."""

from .overview import ForecastAnalyticsSnapshot, summarize_forecast_analytics
from .quantiles import QuantileScorecard
from .scoring import CalibrationBin, brier_score
from .trajectory import TrajectoryScorecard
from .trajectory_aggregate import (
    TrajectoryAnalyticsSnapshot,
    TrajectoryScoredPrediction,
    summarize_trajectory_analytics,
)

PredictionScorecard = TrajectoryScorecard | QuantileScorecard

__all__ = [
    "CalibrationBin",
    "ForecastAnalyticsSnapshot",
    "PredictionScorecard",
    "QuantileScorecard",
    "TrajectoryAnalyticsSnapshot",
    "TrajectoryScorecard",
    "TrajectoryScoredPrediction",
    "brier_score",
    "summarize_forecast_analytics",
    "summarize_trajectory_analytics",
]
