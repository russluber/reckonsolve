"""Shared MainWindow fakes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

from reckonsolve.analytics import (
    ForecastAnalyticsSnapshot,
    summarize_forecast_analytics,
)
from reckonsolve.application.errors import (
    ApplicationError,
    ConcurrentPredictionUpdateError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.analytics import (
    QuantileAnalyticsSource,
    TrajectoryAnalyticsSource,
)
from reckonsolve.domain.attention import DashboardPrediction, DashboardSnapshot
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveMode,
    ArchiveSort,
    ArchiveTagMatchMode,
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.forecast_contracts import ForecastDeadline, prospective_contract
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    DefinitionChange,
    FixedPrecisionValue,
    Invalidation,
    InvalidationHistory,
    NumericResolution,
    NumericResolutionHistory,
    PredictionStatus,
    PredictionType,
    Resolution,
)
from reckonsolve.domain.quantiles import (
    NumericValueConstraint,
    QuantileRevision,
    QuantileTimelineEvent,
)
from reckonsolve.domain.saved_views import SavedView, SavedViewConfiguration
from reckonsolve.domain.search import (
    PredictionSearchHit,
    PredictionSearchResults,
    SearchDocument,
    SearchFragmentHit,
    SearchMatchMode,
    SearchPrediction,
    SearchQuery,
    SearchSourceKind,
    parse_search_text,
)
from reckonsolve.domain.tags import (
    TagDeletePreview,
    TagLibraryItem,
    TagManagementContext,
    TagMergePreview,
    TagRenamePreview,
)
from reckonsolve.domain.transfer import (
    BackupResult,
    CsvExportResult,
    DataManagementStatus,
)


@dataclass(frozen=True, slots=True)
class FakeResolution:
    resolution_id: int
    prediction_id: int
    outcome: BinaryOutcome
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    scoring_probability_percent: int
    resolution_notes: str | None = None
    postmortem: str | None = None
    effective_resolution_at: datetime | None = None

    def __post_init__(self):
        if self.effective_resolution_at is None:
            object.__setattr__(self, "effective_resolution_at", self.resolved_at)


@dataclass(frozen=True, slots=True)
class FakeInvalidation:
    invalidation_id: int
    prediction_id: int
    invalidated_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FakePrediction:
    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus = PredictionStatus.OPEN
    created_at: datetime = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()
    updated_at: datetime | None = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    metadata_version: int = 1
    current_revision_id: int = 1
    current_revision_sequence: int = 1
    current_rationale: str | None = None
    resolution: FakeResolution | None = None
    invalidation: FakeInvalidation | None = None
    deletion_allowed: bool = True
    forecast_contract: object = prospective_contract(
        PredictionType.BINARY,
        ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
    )


@dataclass(frozen=True, slots=True)
class FakeForecastRevision:
    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None


FakeNumericRevision = QuantileRevision


@dataclass(frozen=True, slots=True)
class FakeNumericPrediction:
    prediction_id: int
    question: str
    unit: str
    decimal_places: int
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime
    current_revision: FakeNumericRevision
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()
    metadata_version: int = 1
    resolution: FakeNumericResolution | None = None
    invalidation: FakeInvalidation | None = None
    deletion_allowed: bool = True
    forecast_contract: object = prospective_contract(
        PredictionType.NUMERIC, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
    )
    value_constraint: object = NumericValueConstraint.CONTINUOUS


@dataclass(frozen=True, slots=True)
class FakeNumericResolution:
    resolution_id: int
    prediction_id: int
    actual_value: FixedPrecisionValue
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    resolution_notes: str | None = None
    postmortem: str | None = None


@dataclass(frozen=True, slots=True)
class FakeJournalCorrection:
    correction_id: int
    body: str
    corrected_at: datetime


@dataclass(frozen=True, slots=True)
class FakeForecastTimelineEvent:
    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    probability_percent: int
    previous_probability_percent: int | None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class FakeJournalTimelineEvent:
    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    current_correction_id: int | None = None
    corrections: tuple[FakeJournalCorrection, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatePredictionCall:
    question: str
    probability_percent: int
    rationale: str | None
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviseForecastCall:
    prediction_id: int
    probability_percent: int
    rationale: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class AddJournalEntryCall:
    prediction_id: int
    body: str
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class CorrectJournalEntryCall:
    prediction_id: int
    entry_id: int
    body: str
    expected_correction_id: int | None


@dataclass(frozen=True, slots=True)
class MetadataUpdateCall:
    prediction_id: int
    question: str
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    expected_metadata_version: int
    confirm_meaning_change: bool


@dataclass(frozen=True, slots=True)
class ResolvePredictionCall:
    prediction_id: int
    outcome: BinaryOutcome
    resolution_notes: str | None
    postmortem: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class InvalidatePredictionCall:
    prediction_id: int
    reason: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class DeletePredictionCall:
    prediction_id: int
    expected_revision_id: int
    expected_metadata_version: int
    confirm_permanent_deletion: bool


class FakePredictionOperations:
    def __init__(self, latest: FakePrediction | None = None) -> None:
        self.latest = latest
        self.create_calls: list[CreatePredictionCall] = []
        self.create_error: ApplicationError | None = None
        self.numeric_latest: FakeNumericPrediction | None = None
        self.numeric_revisions: list[FakeNumericRevision] = []
        self.numeric_revision_error: ApplicationError | None = None
        self.numeric_timeline_error: ApplicationError | None = None
        self.numeric_create_error: ApplicationError | None = None
        self.revise_calls: list[ReviseForecastCall] = []
        self.revise_error: ApplicationError | None = None
        self.revisions: list[FakeForecastRevision] = []
        self.revision_read_calls: list[int] = []
        self.revision_read_error: ApplicationError | None = None
        if latest is not None:
            self.revisions.append(
                FakeForecastRevision(
                    revision_id=latest.current_revision_id,
                    prediction_id=latest.prediction_id,
                    probability_percent=latest.probability_percent,
                    sequence=latest.current_revision_sequence,
                    created_at=latest.created_at,
                    rationale=latest.current_rationale,
                )
            )
        self.journal_calls: list[AddJournalEntryCall] = []
        self.journal_error: ApplicationError | None = None
        self.journal_entries: list[FakeJournalTimelineEvent] = []
        self.correction_calls: list[CorrectJournalEntryCall] = []
        self.correction_error: ApplicationError | None = None
        self.timeline_error: ApplicationError | None = None
        self.get_calls: list[int] = []
        self.update_calls: list[MetadataUpdateCall] = []
        self.update_error: ApplicationError | None = None
        self.confirmation_fields: tuple[str, ...] | None = None
        self.definition_changes: tuple[DefinitionChange, ...] = ()
        self.definition_change_error: ApplicationError | None = None
        self.definition_change_calls: list[int] = []
        self.resolve_calls: list[ResolvePredictionCall] = []
        self.resolve_error: ApplicationError | None = None
        self.invalidate_calls: list[InvalidatePredictionCall] = []
        self.invalidate_error: ApplicationError | None = None
        self.delete_calls: list[DeletePredictionCall] = []
        self.delete_error: ApplicationError | None = None
        self.dashboard_snapshot: DashboardSnapshot | None = None
        self.dashboard_error: ApplicationError | None = None
        self.dashboard_calls = 0
        self.browser_snapshot: PredictionBrowserSnapshot | None = None
        self.browser_error: ApplicationError | None = None
        self.browser_calls: list[tuple[str, PredictionStatus | None, str | None]] = []
        self.browser_type_calls: list[PredictionType | None] = []
        self.archive_calls: list[
            tuple[
                tuple[str, ...],
                ArchiveTagMatchMode,
                ArchiveAttention | None,
                ArchiveDateMeaning,
                date | None,
                date | None,
                ArchiveSort,
            ]
        ] = []
        self.search_calls: list[
            tuple[
                str,
                SearchMatchMode,
                bool,
                PredictionStatus | None,
                str | None,
                PredictionType | None,
            ]
        ] = []
        self.search_document: SearchDocument | None = None
        self.search_any_word_available = False
        self.search_suggestion: str | None = None
        self.saved_views: list[SavedView] = []
        self.saved_view_error: ApplicationError | None = None
        self.saved_view_next_id = 1
        self.tag_library: list[TagLibraryItem] = []
        self.tag_library_error: ApplicationError | None = None
        self.analytics_source = TrajectoryAnalyticsSource(records=())
        self.numeric_analytics_source = QuantileAnalyticsSource(records=())
        self.analytics_error: ApplicationError | None = None
        self.analytics_calls: list[str | None] = []
        self.forecast_analytics_calls: list[
            tuple[PredictionType | None, str | None, str | None]
        ] = []
        self.stale_threshold_days = 14
        self.threshold_get_calls = 0
        self.threshold_set_calls: list[int] = []
        self.threshold_error: ApplicationError | None = None
        self.data_management_status = DataManagementStatus(
            database_path=Path("test-data/reckonsolve.sqlite3"),
            last_successful_backup_at=None,
            suggested_backup_filename="reckonsolve-backup-20260820-123000.sqlite3",
            suggested_export_filename="reckonsolve-export-20260820-123000.zip",
        )
        self.data_management_calls = 0
        self.data_management_error: ApplicationError | None = None
        self.backup_calls: list[Path] = []
        self.backup_error: ApplicationError | None = None
        self.export_calls: list[Path] = []
        self.export_error: ApplicationError | None = None
        self.search_repair_calls = 0
        self.search_repair_error: ApplicationError | None = None
        self.mutation_count = 0

    def create_prediction(
        self,
        question: str,
        probability_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> FakePrediction:
        self.create_calls.append(
            CreatePredictionCall(
                question=question,
                probability_percent=probability_percent,
                rationale=rationale,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        )
        if self.create_error is not None:
            raise self.create_error
        prediction = FakePrediction(
            prediction_id=1,
            question=question,
            probability_percent=probability_percent,
            current_rationale=(rationale or "").strip() or None,
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        self.latest = prediction
        self.revisions = [
            FakeForecastRevision(
                revision_id=1,
                prediction_id=1,
                probability_percent=probability_percent,
                sequence=1,
                created_at=prediction.created_at,
                rationale=prediction.current_rationale,
            )
        ]
        return prediction

    def revise_forecast(
        self,
        prediction_id: int,
        probability_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.revise_calls.append(
            ReviseForecastCall(
                prediction_id=prediction_id,
                probability_percent=probability_percent,
                rationale=rationale,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.revise_error is not None:
            raise self.revise_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        new_revision_id = self.latest.current_revision_id + 1
        new_sequence = self.latest.current_revision_sequence + 1
        normalized_rationale = (rationale or "").strip() or None
        self.latest = replace(
            self.latest,
            probability_percent=probability_percent,
            current_revision_id=new_revision_id,
            current_revision_sequence=new_sequence,
            current_rationale=normalized_rationale,
            deletion_allowed=False,
        )
        self.revisions.append(
            FakeForecastRevision(
                revision_id=new_revision_id,
                prediction_id=prediction_id,
                probability_percent=probability_percent,
                sequence=new_sequence,
                created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
                rationale=normalized_rationale,
            )
        )
        return self.latest

    def resolve_numeric_prediction(
        self,
        prediction_id: int,
        actual_value: object,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeNumericPrediction:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        resolution = FakeNumericResolution(
            resolution_id=1,
            prediction_id=prediction_id,
            actual_value=FixedPrecisionValue.from_value(
                actual_value,
                self.numeric_latest.decimal_places,
            ),
            resolved_at=datetime(2026, 8, 23, 19, 30, tzinfo=UTC),
            scoring_revision_id=self.numeric_latest.current_revision.revision_id,
            scoring_revision_sequence=self.numeric_latest.current_revision.sequence,
            resolution_notes=(resolution_notes or "").strip() or None,
            postmortem=(postmortem or "").strip() or None,
        )
        self.numeric_latest = replace(
            self.numeric_latest,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
        return self.numeric_latest

    def invalidate_numeric_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeNumericPrediction:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        self.numeric_latest = replace(
            self.numeric_latest,
            status=PredictionStatus.INVALID,
            invalidation=FakeInvalidation(
                invalidation_id=1,
                prediction_id=prediction_id,
                invalidated_at=datetime(2026, 8, 23, 19, 30, tzinfo=UTC),
                reason=(reason or "").strip() or None,
            ),
            deletion_allowed=False,
        )
        return self.numeric_latest

    def delete_numeric_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> FakeNumericPrediction | None:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        self.numeric_revisions = [
            revision
            for revision in self.numeric_revisions
            if revision.prediction_id != prediction_id
        ]
        self.numeric_latest = None
        return None

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[FakeForecastRevision, ...]:
        self.revision_read_calls.append(prediction_id)
        if self.revision_read_error is not None:
            raise self.revision_read_error
        return tuple(
            revision
            for revision in self.revisions
            if revision.prediction_id == prediction_id
        )

    def list_numeric_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[FakeNumericRevision, ...]:
        if self.numeric_revision_error is not None:
            raise self.numeric_revision_error
        return tuple(
            revision
            for revision in self.numeric_revisions
            if revision.prediction_id == prediction_id
        )

    def list_numeric_timeline(
        self, prediction_id: int
    ) -> tuple[QuantileTimelineEvent, ...]:
        if self.numeric_timeline_error is not None:
            raise self.numeric_timeline_error
        return tuple(
            QuantileTimelineEvent(
                "forecast",
                revision.revision_id,
                revision,
                revision.created_at,
                revision.rationale,
            )
            for revision in self.numeric_revisions
            if revision.prediction_id == prediction_id
        )

    def add_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeJournalTimelineEvent:
        self.journal_calls.append(
            AddJournalEntryCall(
                prediction_id=prediction_id,
                body=body,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.journal_error is not None:
            raise self.journal_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        entry = FakeJournalTimelineEvent(
            entry_id=len(self.journal_entries) + 1,
            prediction_id=prediction_id,
            created_at=datetime(2026, 8, 14, 19, 30, tzinfo=UTC),
            body=body.strip(),
            original_body=body.strip(),
            forecast_revision_id=self.latest.current_revision_id,
            forecast_revision_sequence=self.latest.current_revision_sequence,
            forecast_probability_percent=self.latest.probability_percent,
        )
        self.journal_entries.append(entry)
        self.latest = replace(self.latest, deletion_allowed=False)
        return entry

    def correct_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> FakeJournalTimelineEvent:
        self.correction_calls.append(
            CorrectJournalEntryCall(
                prediction_id=prediction_id,
                entry_id=entry_id,
                body=body,
                expected_correction_id=expected_correction_id,
            )
        )
        if self.correction_error is not None:
            raise self.correction_error
        for index, entry in enumerate(self.journal_entries):
            if entry.prediction_id == prediction_id and entry.entry_id == entry_id:
                correction_id = (
                    sum(len(existing.corrections) for existing in self.journal_entries)
                    + 1
                )
                correction = FakeJournalCorrection(
                    correction_id=correction_id,
                    body=body.strip(),
                    corrected_at=datetime(2026, 8, 15, 19, 30, tzinfo=UTC),
                )
                updated = replace(
                    entry,
                    body=correction.body,
                    current_correction_id=correction_id,
                    corrections=(*entry.corrections, correction),
                )
                self.journal_entries[index] = updated
                return updated
        raise ApplicationError("Journal entry not found.")

    def resolve_prediction(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        effective_resolution_at: datetime | None = None,
        use_recorded_time: bool = False,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.resolve_calls.append(
            ResolvePredictionCall(
                prediction_id=prediction_id,
                outcome=outcome,
                resolution_notes=resolution_notes,
                postmortem=postmortem,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.resolve_error is not None:
            raise self.resolve_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        resolution = FakeResolution(
            resolution_id=1,
            prediction_id=prediction_id,
            outcome=outcome,
            resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            scoring_revision_id=self.latest.current_revision_id,
            scoring_revision_sequence=self.latest.current_revision_sequence,
            scoring_probability_percent=self.latest.probability_percent,
            resolution_notes=(resolution_notes or "").strip() or None,
            postmortem=(postmortem or "").strip() or None,
            effective_resolution_at=effective_resolution_at,
        )
        self.latest = replace(
            self.latest,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
        return self.latest

    def invalidate_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.invalidate_calls.append(
            InvalidatePredictionCall(
                prediction_id=prediction_id,
                reason=reason,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.invalidate_error is not None:
            raise self.invalidate_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        invalidation = FakeInvalidation(
            invalidation_id=1,
            prediction_id=prediction_id,
            invalidated_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            reason=(reason or "").strip() or None,
        )
        self.latest = replace(
            self.latest,
            status=PredictionStatus.INVALID,
            invalidation=invalidation,
            deletion_allowed=False,
        )
        return self.latest

    def delete_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> FakePrediction | None:
        self.delete_calls.append(
            DeletePredictionCall(
                prediction_id=prediction_id,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                confirm_permanent_deletion=confirm_permanent_deletion,
            )
        )
        if self.delete_error is not None:
            raise self.delete_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        self.revisions = [
            item for item in self.revisions if item.prediction_id != prediction_id
        ]
        self.journal_entries = [
            item for item in self.journal_entries if item.prediction_id != prediction_id
        ]
        self.latest = None
        return None

    def list_timeline(
        self,
        prediction_id: int,
    ) -> tuple[FakeForecastTimelineEvent | FakeJournalTimelineEvent, ...]:
        if self.timeline_error is not None:
            raise self.timeline_error
        revisions = [
            revision
            for revision in self.revisions
            if revision.prediction_id == prediction_id
        ]
        forecast_events: list[FakeForecastTimelineEvent] = []
        previous_probability: int | None = None
        for revision in revisions:
            forecast_events.append(
                FakeForecastTimelineEvent(
                    revision_id=revision.revision_id,
                    prediction_id=revision.prediction_id,
                    created_at=revision.created_at,
                    sequence=revision.sequence,
                    probability_percent=revision.probability_percent,
                    previous_probability_percent=previous_probability,
                    rationale=revision.rationale,
                )
            )
            previous_probability = revision.probability_percent
        journal_events = [
            entry
            for entry in self.journal_entries
            if entry.prediction_id == prediction_id
        ]
        events: list[FakeForecastTimelineEvent | FakeJournalTimelineEvent] = [
            *forecast_events,
            *journal_events,
        ]
        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.forecast_revision_sequence
                    if isinstance(event, FakeJournalTimelineEvent)
                    else event.sequence,
                    1 if isinstance(event, FakeJournalTimelineEvent) else 0,
                    event.created_at,
                    event.entry_id
                    if isinstance(event, FakeJournalTimelineEvent)
                    else event.revision_id,
                ),
            )
        )

    def get_latest_prediction(self) -> FakePrediction | None:
        return self.latest

    def get_latest_numeric_prediction(self) -> FakeNumericPrediction | None:
        return self.numeric_latest

    def get_prediction(self, prediction_id: int) -> FakePrediction:
        self.get_calls.append(prediction_id)
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        return self.latest

    def get_numeric_prediction(self, prediction_id: int) -> FakeNumericPrediction:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        return self.numeric_latest

    def get_binary_resolution_history(
        self,
        prediction_id: int,
    ) -> BinaryResolutionHistory:
        prediction = self.get_prediction(prediction_id)
        if prediction.resolution is None:
            raise ApplicationError("Binary Resolution not found.")
        resolution = prediction.resolution
        return BinaryResolutionHistory(
            original=Resolution(
                resolution_id=resolution.resolution_id,
                prediction_id=resolution.prediction_id,
                outcome=resolution.outcome,
                resolved_at=resolution.resolved_at,
                scoring_revision_id=resolution.scoring_revision_id,
                scoring_revision_sequence=resolution.scoring_revision_sequence,
                scoring_probability_percent=resolution.scoring_probability_percent,
                resolution_notes=resolution.resolution_notes,
                postmortem=resolution.postmortem,
                effective_resolution_at=resolution.effective_resolution_at,
            )
        )

    def get_numeric_resolution_history(
        self,
        prediction_id: int,
    ) -> NumericResolutionHistory:
        prediction = self.get_numeric_prediction(prediction_id)
        if prediction.resolution is None:
            raise ApplicationError("Numeric Resolution not found.")
        resolution = prediction.resolution
        return NumericResolutionHistory(
            original=NumericResolution(
                resolution_id=resolution.resolution_id,
                prediction_id=resolution.prediction_id,
                actual_value=resolution.actual_value,
                resolved_at=resolution.resolved_at,
                scoring_revision_id=resolution.scoring_revision_id,
                scoring_revision_sequence=resolution.scoring_revision_sequence,
                resolution_notes=resolution.resolution_notes,
                postmortem=resolution.postmortem,
            )
        )

    def get_invalidation_history(self, prediction_id: int) -> InvalidationHistory:
        if self.latest is not None and self.latest.prediction_id == prediction_id:
            invalidation = self.latest.invalidation
        elif (
            self.numeric_latest is not None
            and self.numeric_latest.prediction_id == prediction_id
        ):
            invalidation = self.numeric_latest.invalidation
        else:
            raise ApplicationError("Prediction not found.")
        if invalidation is None:
            raise ApplicationError("Invalidation not found.")
        return InvalidationHistory(
            original=Invalidation(
                invalidation_id=invalidation.invalidation_id,
                prediction_id=invalidation.prediction_id,
                invalidated_at=invalidation.invalidated_at,
                reason=invalidation.reason,
            )
        )

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> FakePrediction | FakeNumericPrediction:
        if self.latest is not None and self.latest.prediction_id == prediction_id:
            return self.get_prediction(prediction_id)
        return self.get_numeric_prediction(prediction_id)

    def update_metadata(
        self,
        prediction_id: int,
        *,
        question: str,
        background: str | None,
        resolution_criteria: str | None,
        forecast_deadline: date | None,
        expected_resolution: date | None,
        tags: tuple[str, ...],
        expected_metadata_version: int,
        confirm_meaning_change: bool = False,
    ) -> FakePrediction | FakeNumericPrediction:
        self.update_calls.append(
            MetadataUpdateCall(
                prediction_id=prediction_id,
                question=question,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
                expected_metadata_version=expected_metadata_version,
                confirm_meaning_change=confirm_meaning_change,
            )
        )
        if self.update_error is not None:
            raise self.update_error
        if self.confirmation_fields is not None and not confirm_meaning_change:
            raise MeaningChangeConfirmationRequired(self.confirmation_fields)
        target: FakePrediction | FakeNumericPrediction | None = None
        if self.latest is not None and self.latest.prediction_id == prediction_id:
            target = self.latest
        elif (
            self.numeric_latest is not None
            and self.numeric_latest.prediction_id == prediction_id
        ):
            target = self.numeric_latest
        if target is None:
            raise ApplicationError("Prediction not found.")
        if target.metadata_version != expected_metadata_version:
            raise ConcurrentPredictionUpdateError(prediction_id)
        updated = replace(
            target,
            question=question.strip(),
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        if updated != target:
            self.mutation_count += 1
            updated = replace(
                updated,
                metadata_version=target.metadata_version + 1,
                deletion_allowed=False,
            )
        if isinstance(updated, FakeNumericPrediction):
            self.numeric_latest = updated
            return updated
        self.latest = updated
        return updated

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...]:
        self.definition_change_calls.append(prediction_id)
        if self.definition_change_error is not None:
            raise self.definition_change_error
        return self.definition_changes

    def get_dashboard(self) -> DashboardSnapshot:
        self.dashboard_calls += 1
        if self.dashboard_error is not None:
            raise self.dashboard_error
        if self.dashboard_snapshot is not None:
            return self.dashboard_snapshot
        if self.latest is None or self.latest.status in (
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        ):
            open_predictions: tuple[DashboardPrediction, ...] = ()
            locked_predictions: tuple[DashboardPrediction, ...] = ()
        else:
            prediction = DashboardPrediction(
                prediction_id=self.latest.prediction_id,
                question=self.latest.question,
                probability_percent=self.latest.probability_percent,
                status=self.latest.status,
                latest_revision_at=self.latest.created_at,
                forecast_deadline=self.latest.forecast_deadline,
                expected_resolution=self.latest.expected_resolution,
                forecast_contract=prospective_contract(
                    PredictionType.BINARY,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            )
            open_predictions = (
                (prediction,) if self.latest.status is PredictionStatus.OPEN else ()
            )
            locked_predictions = (
                (prediction,) if self.latest.status is PredictionStatus.LOCKED else ()
            )
        return DashboardSnapshot(
            stale_threshold_days=self.stale_threshold_days,
            open_predictions=open_predictions,
            needs_attention_predictions=(),
            ready_to_resolve_predictions=(),
            locked_predictions=locked_predictions,
        )

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
        prediction_type: PredictionType | None = None,
        mode: ArchiveMode | None = None,
        tags: tuple[str, ...] = (),
        tag_match_mode: ArchiveTagMatchMode = ArchiveTagMatchMode.ALL,
        attention: ArchiveAttention | None = None,
        date_meaning: ArchiveDateMeaning = ArchiveDateMeaning.CREATED,
        date_start: date | None = None,
        date_end: date | None = None,
        sort: ArchiveSort = ArchiveSort.CREATED_NEWEST,
    ) -> PredictionBrowserSnapshot:
        self.browser_calls.append((question_text, status, tag))
        self.browser_type_calls.append(prediction_type)
        self.archive_calls.append(
            (tags, tag_match_mode, attention, date_meaning, date_start, date_end, sort)
        )
        if self.browser_error is not None:
            raise self.browser_error
        if self.browser_snapshot is not None:
            source = self.browser_snapshot
        elif self.latest is None:
            source = PredictionBrowserSnapshot(predictions=(), available_tags=())
        else:
            source = PredictionBrowserSnapshot(
                predictions=(
                    PredictionBrowserItem(
                        prediction_id=self.latest.prediction_id,
                        question=self.latest.question,
                        probability_percent=self.latest.probability_percent,
                        status=self.latest.status,
                        created_at=self.latest.created_at,
                        latest_revision_at=self.latest.created_at,
                        forecast_deadline=self.latest.forecast_deadline,
                        tags=self.latest.tags,
                        forecast_contract=prospective_contract(
                            PredictionType.BINARY,
                            ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                        ),
                    ),
                ),
                available_tags=tuple(
                    sorted(self.latest.tags, key=lambda item: item.casefold())
                ),
            )
        search_key = question_text.strip().casefold()
        tag_key = None if tag is None else tag.casefold()
        tag_keys = {item.casefold() for item in tags}
        return replace(
            source,
            predictions=tuple(
                prediction
                for prediction in source.predictions
                if (not search_key or search_key in prediction.question.casefold())
                and (status is None or prediction.status is status)
                and (
                    prediction_type is None
                    or prediction.prediction_type is prediction_type
                )
                and (
                    mode is None
                    or (
                        bool(
                            prediction.forecast_contract
                            and prediction.forecast_contract.is_one_shot
                        )
                        == (mode is ArchiveMode.ONE_SHOT)
                    )
                )
                and (
                    tag_key is None
                    or tag_key in {item.casefold() for item in prediction.tags}
                )
                and (
                    not tag_keys
                    or (
                        tag_keys.issubset({item.casefold() for item in prediction.tags})
                        if tag_match_mode is ArchiveTagMatchMode.ALL
                        else bool(
                            tag_keys & {item.casefold() for item in prediction.tags}
                        )
                    )
                )
            ),
        )

    def search_predictions(
        self,
        text: str,
        *,
        match_mode: SearchMatchMode = SearchMatchMode.ALL,
        include_superseded: bool = False,
        status: PredictionStatus | None = None,
        tag: str | None = None,
        prediction_type: PredictionType | None = None,
        mode: ArchiveMode | None = None,
        tags: tuple[str, ...] = (),
        tag_match_mode: ArchiveTagMatchMode = ArchiveTagMatchMode.ALL,
        attention: ArchiveAttention | None = None,
        date_meaning: ArchiveDateMeaning = ArchiveDateMeaning.CREATED,
        date_start: date | None = None,
        date_end: date | None = None,
        sort: ArchiveSort = ArchiveSort.RELEVANCE,
    ) -> PredictionSearchResults:
        self.search_calls.append(
            (text, match_mode, include_superseded, status, tag, prediction_type)
        )
        source = self.browse_predictions(
            "" if self.search_document is not None else text,
            status=status,
            tag=tag,
            prediction_type=prediction_type,
            mode=mode,
            tags=tags,
            tag_match_mode=tag_match_mode,
            attention=attention,
            date_meaning=date_meaning,
            date_start=date_start,
            date_end=date_end,
            sort=sort,
        )
        parsed = parse_search_text(text)
        hits = tuple(
            PredictionSearchHit(
                prediction=SearchPrediction(
                    prediction_id=item.prediction_id,
                    question=item.question,
                    prediction_type=item.prediction_type,
                    status=item.status,
                    created_at=item.created_at,
                    forecast_deadline=item.forecast_deadline,
                    expected_resolution=item.expected_resolution,
                    tags=item.tags,
                    latest_revision_at=item.latest_revision_at,
                    latest_review_at=item.latest_review_at,
                    terminal_decision_at=item.terminal_decision_at,
                    needs_postmortem=item.needs_postmortem,
                    probability_percent=item.probability_percent,
                    numeric_quantiles=item.numeric_quantiles,
                    numeric_unit=item.numeric_unit,
                    forecast_contract=prospective_contract(
                        item.prediction_type,
                        ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                    ),
                ),
                best_match=SearchFragmentHit(
                    document=(
                        self.search_document
                        if self.search_document is not None
                        else SearchDocument(
                            prediction_id=item.prediction_id,
                            source_kind=SearchSourceKind.QUESTION,
                            source_record_id=item.prediction_id,
                            source_version_id=None,
                            source_sequence=None,
                            occurred_at=item.created_at,
                            is_superseded=False,
                            text=item.question,
                        )
                    ),
                    matched_clause_indexes=frozenset(range(len(parsed.clauses))),
                    literal_match=True,
                    exact_text_match=False,
                ),
                additional_match_count=0,
            )
            for item in source.predictions
        )
        return PredictionSearchResults(
            query=SearchQuery(text, match_mode, include_superseded),
            parsed_text=parsed,
            hits=hits,
            any_word_available=self.search_any_word_available and not hits,
            suggestion=self.search_suggestion if not hits else None,
            available_tags=source.available_tags,
        )

    def list_saved_views(self) -> tuple[SavedView, ...]:
        if self.saved_view_error is not None:
            raise self.saved_view_error
        return tuple(self.saved_views)

    def create_saved_view(
        self,
        name: str,
        configuration: SavedViewConfiguration,
    ) -> SavedView:
        if self.saved_view_error is not None:
            raise self.saved_view_error
        view = SavedView(
            saved_view_id=self.saved_view_next_id,
            name=name.strip(),
            normalized_name=name.strip().casefold(),
            configuration=configuration,
            tags=(),
        )
        self.saved_view_next_id += 1
        self.saved_views.append(view)
        return view

    def update_saved_view(
        self,
        saved_view_id: int,
        configuration: SavedViewConfiguration,
    ) -> SavedView:
        for index, view in enumerate(self.saved_views):
            if view.saved_view_id == saved_view_id:
                updated = replace(view, configuration=configuration)
                self.saved_views[index] = updated
                return updated
        raise RuntimeError("Saved View missing from fake operations.")

    def rename_saved_view(self, saved_view_id: int, name: str) -> SavedView:
        for index, view in enumerate(self.saved_views):
            if view.saved_view_id == saved_view_id:
                renamed = replace(
                    view,
                    name=name.strip(),
                    normalized_name=name.strip().casefold(),
                )
                self.saved_views[index] = renamed
                return renamed
        raise RuntimeError("Saved View missing from fake operations.")

    def delete_saved_view(self, saved_view_id: int) -> None:
        self.saved_views = [
            view for view in self.saved_views if view.saved_view_id != saved_view_id
        ]

    def list_tags(self, name_filter: str = "") -> tuple[TagLibraryItem, ...]:
        if self.tag_library_error is not None:
            raise self.tag_library_error
        key = name_filter.strip().casefold()
        return tuple(
            tag for tag in self.tag_library if not key or key in tag.normalized_name
        )

    def preview_tag_rename(self, tag_id: int, name: str) -> TagRenamePreview:
        tag = next(item for item in self.tag_library if item.tag_id == tag_id)
        return TagRenamePreview(
            context=self._tag_context(tag),
            proposed_display_name=name.strip(),
            proposed_normalized_name=name.strip().casefold(),
        )

    def rename_tag(self, preview: TagRenamePreview) -> None:
        self.tag_library = [
            replace(
                tag,
                display_name=preview.proposed_display_name,
                normalized_name=preview.proposed_normalized_name,
            )
            if tag.tag_id == preview.context.item.tag_id
            else tag
            for tag in self.tag_library
        ]

    def preview_tag_merge(
        self,
        source_tag_ids: tuple[int, ...],
        target_tag_id: int,
    ) -> TagMergePreview:
        source_contexts = tuple(
            self._tag_context(
                next(tag for tag in self.tag_library if tag.tag_id == source_id)
            )
            for source_id in source_tag_ids
        )
        target = self._tag_context(
            next(tag for tag in self.tag_library if tag.tag_id == target_tag_id)
        )
        return TagMergePreview(
            source_contexts=source_contexts,
            target_context=target,
            affected_prediction_ids=tuple(
                sorted(
                    {
                        prediction_id
                        for context in source_contexts
                        for prediction_id in context.prediction_ids
                    }
                )
            ),
            affected_saved_view_ids=tuple(
                sorted(
                    {
                        saved_view_id
                        for context in source_contexts
                        for saved_view_id in context.saved_view_ids
                    }
                )
            ),
        )

    def merge_tags(self, preview: TagMergePreview) -> None:
        source_ids = {tag.tag_id for tag in preview.source_tags}
        target_id = preview.target_tag.tag_id
        self.tag_library = [
            replace(
                tag,
                prediction_count=(
                    len(
                        set(preview.target_context.prediction_ids)
                        | set(preview.affected_prediction_ids)
                    )
                ),
                saved_view_count=(
                    len(
                        set(preview.target_context.saved_view_ids)
                        | set(preview.affected_saved_view_ids)
                    )
                ),
            )
            if tag.tag_id == target_id
            else tag
            for tag in self.tag_library
            if tag.tag_id not in source_ids
        ]

    def preview_tag_delete(self, tag_id: int) -> TagDeletePreview:
        tag = next(item for item in self.tag_library if item.tag_id == tag_id)
        return TagDeletePreview(self._tag_context(tag))

    def delete_tag(self, preview: TagDeletePreview) -> None:
        self.tag_library = [
            tag for tag in self.tag_library if tag.tag_id != preview.tag.tag_id
        ]

    @staticmethod
    def _tag_context(tag: TagLibraryItem) -> TagManagementContext:
        return TagManagementContext(
            item=tag,
            prediction_ids=tuple(
                tag.tag_id * 100 + index for index in range(tag.prediction_count)
            ),
            saved_view_ids=tuple(
                tag.tag_id * 100 + index for index in range(tag.saved_view_count)
            ),
        )

    def get_prediction_scorecard(self, prediction_id: int) -> object | None:
        return None

    def get_forecast_analytics(
        self,
        *,
        prediction_type: PredictionType | None = None,
        tag: str | None = None,
        unit: str | None = None,
    ) -> ForecastAnalyticsSnapshot:
        self.forecast_analytics_calls.append((prediction_type, tag, unit))
        self.analytics_calls.append(tag)
        if self.analytics_error is not None:
            raise self.analytics_error
        return summarize_forecast_analytics(
            self.analytics_source,
            self.numeric_analytics_source,
            prediction_type=prediction_type,
            tag=tag,
            unit=unit,
        )

    def get_stale_threshold_days(self) -> int:
        self.threshold_get_calls += 1
        if self.threshold_error is not None:
            raise self.threshold_error
        return self.stale_threshold_days

    def set_stale_threshold_days(self, value: int) -> int:
        self.threshold_set_calls.append(value)
        if self.threshold_error is not None:
            raise self.threshold_error
        self.stale_threshold_days = value
        return value

    def get_data_management_status(self) -> DataManagementStatus:
        self.data_management_calls += 1
        if self.data_management_error is not None:
            raise self.data_management_error
        return self.data_management_status

    def create_backup(self, destination: Path) -> BackupResult:
        self.backup_calls.append(destination)
        if self.backup_error is not None:
            raise self.backup_error
        completed_at = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
        self.data_management_status = replace(
            self.data_management_status,
            last_successful_backup_at=completed_at,
        )
        return BackupResult(destination=destination, completed_at=completed_at)

    def export_csv_bundle(self, destination: Path) -> CsvExportResult:
        self.export_calls.append(destination)
        if self.export_error is not None:
            raise self.export_error
        return CsvExportResult(
            destination=destination,
            exported_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            csv_file_count=16,
        )

    def repair_search_index(self) -> None:
        self.search_repair_calls += 1
        if self.search_repair_error is not None:
            raise self.search_repair_error
