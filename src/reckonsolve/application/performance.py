"""One checked report read, four independent existing analytical populations."""

from dataclasses import dataclass
from enum import StrEnum

from reckonsolve.analytics.one_shot_aggregate import (
    OneShotBinaryAnalytics,
    OneShotNumericAnalytics,
    summarize_one_shot_analytics,
)
from reckonsolve.analytics.quantile_aggregate import (
    Proportion,
    QuantileAnalyticsSnapshot,
    summarize_quantile_analytics,
)
from reckonsolve.analytics.trajectory_aggregate import (
    TrajectoryAnalyticsSnapshot,
    summarize_trajectory_analytics,
)
from reckonsolve.data.analytics import AnalyticsRepository
from reckonsolve.data.database import Database
from reckonsolve.domain.analytics import (
    OneShotAnalyticsSource,
    QuantileAnalyticsSource,
    TrajectoryAnalyticsSource,
)
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.domain.tags import TagLibraryItem

from .errors import ApplicationError, ValidationError
from .read_errors import expected_database_read


class Section(StrEnum):
    ADAPTIVE_BINARY = "adaptiveBinary"
    ADAPTIVE_NUMERIC = "adaptiveNumeric"
    ONE_SHOT_BINARY = "oneShotBinary"
    ONE_SHOT_NUMERIC = "oneShotNumeric"


@dataclass(frozen=True, slots=True)
class PerformanceRequest:
    tag_id: int | None = None
    adaptive_unit: str | None = None
    one_shot_unit: str | None = None

    def __post_init__(self) -> None:
        if self.tag_id is not None and (
            type(self.tag_id) is not int or self.tag_id <= 0
        ):
            raise ValidationError("Choose a current tag.", field="tag")
        for unit in (self.adaptive_unit, self.one_shot_unit):
            if unit is not None and (not isinstance(unit, str) or not unit.strip()):
                raise ValidationError(
                    "Choose an exact unit or All units.", field="unit"
                )


PerformanceData = (
    TrajectoryAnalyticsSnapshot
    | QuantileAnalyticsSnapshot
    | OneShotBinaryAnalytics
    | OneShotNumericAnalytics
)


@dataclass(frozen=True, slots=True)
class SectionResult:
    section: Section
    data: PerformanceData | None = None
    error: str | None = None
    observed_yes: tuple[Proportion, ...] = ()


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    request: PerformanceRequest
    tags: tuple[TagLibraryItem, ...]
    effective_tag_id: int | None
    adaptive_units: tuple[str, ...]
    one_shot_units: tuple[str, ...]
    sections: tuple[SectionResult, ...]
    notice: str = ""


class PerformanceOperations:
    """No presentation cache or writes; use the canonical shared pure scorers."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.repository = AnalyticsRepository(database)

    @expected_database_read
    def query_independently(self, request: PerformanceRequest) -> PerformanceReport:
        reader = Database.open_readonly(
            self.database.path, migrations=self.database.migrations
        )
        try:
            return PerformanceOperations(reader).query(request)
        finally:
            reader.close()

    @expected_database_read
    def query(self, request: PerformanceRequest) -> PerformanceReport:
        return summarize_performance(
            request, *self.repository.get_performance_sources()
        )


def summarize_performance(
    request: PerformanceRequest,
    trajectory: TrajectoryAnalyticsSource,
    quantiles: QuantileAnalyticsSource,
    one_shots: OneShotAnalyticsSource,
    tags: tuple[TagLibraryItem, ...],
) -> PerformanceReport:
    """Compose derived sections from one already admitted source snapshot."""
    selected = next((tag for tag in tags if tag.tag_id == request.tag_id), None)
    effective_tag_id = selected.tag_id if selected is not None else None
    tag = selected.display_name if selected is not None else None
    adaptive_units = tuple(sorted({r.definition.unit for r in quantiles.records}))
    one_shot_units = tuple(
        sorted(
            {
                r.record.definition.unit
                for r in one_shots.records
                if r.record.definition is not None
            }
        )
    )
    calculations = {
        Section.ADAPTIVE_BINARY: lambda: summarize_trajectory_analytics(
            trajectory, tag=tag
        ),
        Section.ADAPTIVE_NUMERIC: lambda: summarize_quantile_analytics(
            quantiles, tag=tag, unit=request.adaptive_unit
        ),
        Section.ONE_SHOT_BINARY: lambda: (
            summarize_one_shot_analytics(
                one_shots, prediction_type=PredictionType.BINARY, tag=tag
            ).binary
        ),
        Section.ONE_SHOT_NUMERIC: lambda: (
            summarize_one_shot_analytics(
                one_shots,
                prediction_type=PredictionType.NUMERIC,
                tag=tag,
                unit=request.one_shot_unit,
            ).numeric
        ),
    }
    results = []
    for section, calculate in calculations.items():
        unit, available = (
            (request.adaptive_unit, adaptive_units)
            if section is Section.ADAPTIVE_NUMERIC
            else (request.one_shot_unit, one_shot_units)
            if section is Section.ONE_SHOT_NUMERIC
            else (None, ())
        )
        if unit is not None and unit not in available:
            results.append(
                SectionResult(
                    section,
                    error="The selected unit is unavailable. Its scope has been retained. Refresh or choose All units explicitly.",
                )
            )
            continue
        try:
            data = calculate()
        except ApplicationError as error:
            # Canonical admission already happened for the entire archive.
            # An identified analytical failure belongs to this section;
            # unexpected bugs still propagate across the worker boundary.
            results.append(SectionResult(section, error=str(error)))
            continue
        observed = ()
        if isinstance(data, TrajectoryAnalyticsSnapshot):
            observed = tuple(
                Proportion(
                    sum(
                        item.scorecard.outcome is BinaryOutcome.YES
                        for item in data.scored_predictions
                        if band.lower_percent
                        <= item.final_probability_percent
                        <= band.upper_percent
                    ),
                    band.count,
                )
                for band in data.final_calibration_bins
            )
        elif isinstance(data, OneShotBinaryAnalytics):
            observed = data.observed_yes
        results.append(SectionResult(section, data, observed_yes=observed))
    return PerformanceReport(
        request,
        tags,
        effective_tag_id,
        adaptive_units,
        one_shot_units,
        tuple(results),
        "The selected tag was deleted. Showing All tags; other report choices are retained."
        if request.tag_id is not None and selected is None
        else "",
    )
