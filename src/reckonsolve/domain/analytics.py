"""Canonical resolved-forecast facts supplied to scoring analytics."""

from dataclasses import dataclass
from datetime import datetime

from .predictions import BinaryOutcome, FixedPrecisionValue


@dataclass(frozen=True, slots=True)
class ScoringObservation:
    """One resolved Prediction paired with its captured scoring revision."""

    prediction_id: int
    question: str
    resolution_id: int
    resolved_at: datetime
    scoring_revision_id: int
    probability_percent: int
    outcome: BinaryOutcome
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalyticsSource:
    """Canonical scoring observations and the tags represented among them."""

    observations: tuple[ScoringObservation, ...]
    available_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NumericScoringObservation:
    """One resolved Numeric Prediction and its captured scoring interval."""

    prediction_id: int
    question: str
    resolution_id: int
    resolved_at: datetime
    scoring_revision_id: int
    unit: str
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    actual_value: FixedPrecisionValue
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NumericAnalyticsSource:
    """Canonical Numeric scoring observations and represented filters."""

    observations: tuple[NumericScoringObservation, ...]
    available_tags: tuple[str, ...]
    available_units: tuple[str, ...]
