"""Read models for browsing the prediction archive."""

from dataclasses import dataclass
from datetime import date, datetime

from .predictions import PredictionStatus


@dataclass(frozen=True, slots=True)
class PredictionBrowserItem:
    """One current prediction summary shown in the archive browser."""

    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus
    created_at: datetime
    latest_revision_at: datetime
    forecast_deadline: date | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PredictionBrowserSnapshot:
    """Filtered prediction summaries plus all currently associated tags."""

    predictions: tuple[PredictionBrowserItem, ...]
    available_tags: tuple[str, ...]
