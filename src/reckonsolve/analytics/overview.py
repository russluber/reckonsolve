"""Composition of the two supported forecasting models; never pooled scores."""

from dataclasses import dataclass

from reckonsolve.domain.analytics import (
    QuantileAnalyticsSource,
    TrajectoryAnalyticsSource,
)
from reckonsolve.domain.predictions import PredictionType

from .quantile_aggregate import QuantileAnalyticsSnapshot, summarize_quantile_analytics
from .trajectory_aggregate import (
    TrajectoryAnalyticsSnapshot,
    summarize_trajectory_analytics,
)


@dataclass(frozen=True, slots=True)
class ForecastAnalyticsSnapshot:
    """Separate model-specific metrics sharing one forecast-type/tag subset."""

    trajectory_binary: TrajectoryAnalyticsSnapshot
    quantile_numeric: QuantileAnalyticsSnapshot
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]
    selected_type: PredictionType | None = None
    selected_tag: str | None = None
    selected_unit: str | None = None


def summarize_forecast_analytics(
    trajectory_source: TrajectoryAnalyticsSource,
    quantile_source: QuantileAnalyticsSource,
    *,
    prediction_type: PredictionType | None = None,
    tag: str | None = None,
    unit: str | None = None,
) -> ForecastAnalyticsSnapshot:
    """Calculate model-specific metrics without pooling scores or raw units."""

    if prediction_type is not PredictionType.NUMERIC and unit is not None:
        raise ValueError("Choose Numeric analytics before filtering by unit.")

    include_binary = prediction_type in (None, PredictionType.BINARY)
    include_numeric = prediction_type in (None, PredictionType.NUMERIC)
    quantile = summarize_quantile_analytics(
        quantile_source if include_numeric else QuantileAnalyticsSource(records=()),
        tag=tag,
        unit=unit,
    )
    trajectory = summarize_trajectory_analytics(
        trajectory_source if include_binary else TrajectoryAnalyticsSource(records=()),
        tag=tag,
    )
    return ForecastAnalyticsSnapshot(
        trajectory_binary=trajectory,
        quantile_numeric=quantile,
        available_tags=_unique_labels(
            trajectory.available_tags + quantile.available_tags
        ),
        available_units=tuple(
            sorted({r.definition.unit for r in quantile_source.records})
        ),
        selected_type=prediction_type,
        selected_tag=tag,
        selected_unit=unit,
    )


def _unique_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for label in labels:
        by_key.setdefault(label.casefold(), label)
    return tuple(by_key[key] for key in sorted(by_key))
