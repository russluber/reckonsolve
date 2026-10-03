"""Canonical resolved-forecast facts supplied to scoring analytics."""

from dataclasses import dataclass

from .forecast_contracts import ForecastContract
from .one_shot import OneShotRecord
from .predictions import (
    BinaryResolutionHistory,
    ForecastRevision,
    NumericResolutionHistory,
)
from .quantiles import QuantileDefinition, QuantileRevision


@dataclass(frozen=True, slots=True)
class TrajectoryScoringRecord:
    """One resolved trajectory Binary Prediction and its complete score source."""

    question: str
    contract: ForecastContract
    revisions: tuple[ForecastRevision, ...]
    resolution_history: BinaryResolutionHistory
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrajectoryAnalyticsSource:
    """Resolved trajectory Binary histories supplied to pure analytics."""

    records: tuple[TrajectoryScoringRecord, ...]


@dataclass(frozen=True, slots=True)
class QuantileScoringRecord:
    """Complete canonical input for one resolved five-quantile Prediction."""

    question: str
    contract: ForecastContract
    definition: QuantileDefinition
    revisions: tuple[QuantileRevision, ...]
    resolution_history: NumericResolutionHistory
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuantileAnalyticsSource:
    records: tuple[QuantileScoringRecord, ...]


@dataclass(frozen=True, slots=True)
class OneShotScoringRecord:
    """One canonical One-Shot history, with current tags for filtering."""

    question: str
    record: OneShotRecord
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OneShotAnalyticsSource:
    records: tuple[OneShotScoringRecord, ...]
