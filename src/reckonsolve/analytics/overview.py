"""Type-aware composition of Binary and Numeric analytics views."""

from dataclasses import dataclass

from reckonsolve.domain.analytics import AnalyticsSource, NumericAnalyticsSource
from reckonsolve.domain.predictions import PredictionType

from .numeric import NumericAnalyticsSnapshot, summarize_numeric_analytics
from .scoring import AnalyticsSnapshot, summarize_analytics


@dataclass(frozen=True, slots=True)
class ForecastAnalyticsSnapshot:
    """Separate type-specific metrics sharing one forecast-type/tag subset."""

    binary: AnalyticsSnapshot
    numeric: NumericAnalyticsSnapshot
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]
    selected_type: PredictionType | None = None
    selected_tag: str | None = None
    selected_unit: str | None = None


def summarize_forecast_analytics(
    binary_source: AnalyticsSource,
    numeric_source: NumericAnalyticsSource,
    *,
    prediction_type: PredictionType | None = None,
    tag: str | None = None,
    unit: str | None = None,
) -> ForecastAnalyticsSnapshot:
    """Calculate separate metrics without mixing forecast types or raw units."""

    if prediction_type is PredictionType.BINARY and unit is not None:
        raise ValueError("A unit filter applies only to Numeric analytics.")
    if prediction_type is None and unit is not None:
        raise ValueError("Choose Numeric analytics before filtering by unit.")

    include_binary = prediction_type in (None, PredictionType.BINARY)
    include_numeric = prediction_type in (None, PredictionType.NUMERIC)
    binary = summarize_analytics(
        binary_source
        if include_binary
        else AnalyticsSource(observations=(), available_tags=()),
        tag=tag,
    )
    numeric = summarize_numeric_analytics(
        numeric_source
        if include_numeric
        else NumericAnalyticsSource(
            observations=(),
            available_tags=(),
            available_units=numeric_source.available_units,
        ),
        tag=tag,
        unit=unit,
    )
    tag_sources = (binary_source.available_tags if include_binary else ()) + (
        numeric_source.available_tags if include_numeric else ()
    )
    return ForecastAnalyticsSnapshot(
        binary=binary,
        numeric=numeric,
        available_tags=_unique_labels(tag_sources),
        available_units=numeric_source.available_units,
        selected_type=prediction_type,
        selected_tag=tag,
        selected_unit=unit,
    )


def _unique_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    by_key: dict[str, str] = {}
    for label in labels:
        by_key.setdefault(label.casefold(), label)
    return tuple(by_key[key] for key in sorted(by_key))
