from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QDate, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.analytics import (
    AnalyticsSnapshot,
    AnalyticsSource,
    ForecastAnalyticsSnapshot,
    NumericAnalyticsSource,
    NumericScoringObservation,
    ScoringObservation,
    summarize_analytics,
    summarize_forecast_analytics,
)
from reckonsolve.application.errors import (
    ApplicationError,
    ConcurrentPredictionUpdateError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.attention import DashboardPrediction, DashboardSnapshot
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveQuery,
    ArchiveSort,
    ArchiveTagMatchMode,
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
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
from reckonsolve.ui import MainWindow
from reckonsolve.ui.analytics_charts import (
    BrierTrendChart,
    CalibrationChart,
    ContainmentCalibrationChart,
)
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.presentation_settings import (
    MemoryPresentationSettings,
    WindowPresentationState,
)
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart
from reckonsolve.ui.tag_manager import TagManagerDialog
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    BADGE_TONE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    NAVIGATION_ACTIVE_PROPERTY,
    NAVIGATION_COMPACT_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    ActionRole,
    Radius,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    semantic_colors,
)

EXPECTED_SCREEN_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)
EXPECTED_NAVIGATION_NAMES = (
    "Dashboard",
    "Predictions",
    "Analytics",
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


@dataclass(frozen=True, slots=True)
class FakeForecastRevision:
    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class FakeNumericRevision:
    revision_id: int
    prediction_id: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None


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
class FakeNumericForecastTimelineEvent:
    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    previous_lower_bound: FixedPrecisionValue | None
    previous_median_estimate: FixedPrecisionValue | None
    previous_upper_bound: FixedPrecisionValue | None
    previous_confidence_percent: int | None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class FakeNumericJournalTimelineEvent:
    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    numeric_forecast_revision_id: int
    forecast_revision_sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    current_correction_id: int | None = None
    corrections: tuple[FakeJournalCorrection, ...] = ()


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
class CreateNumericPredictionCall:
    question: str
    unit: str
    decimal_places: int
    lower_bound: str
    median_estimate: str
    upper_bound: str
    confidence_percent: int
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
        self.numeric_journal_entries: list[FakeNumericJournalTimelineEvent] = []
        self.numeric_revision_error: ApplicationError | None = None
        self.numeric_timeline_error: ApplicationError | None = None
        self.numeric_create_calls: list[CreateNumericPredictionCall] = []
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
        self.analytics_source = AnalyticsSource(observations=(), available_tags=())
        self.numeric_analytics_source = NumericAnalyticsSource(
            observations=(),
            available_tags=(),
            available_units=(),
        )
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

    def create_numeric_prediction(
        self,
        question: str,
        unit: str,
        decimal_places: int,
        lower_bound: object,
        median_estimate: object,
        upper_bound: object,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> FakeNumericPrediction:
        self.numeric_create_calls.append(
            CreateNumericPredictionCall(
                question=question,
                unit=unit,
                decimal_places=decimal_places,
                lower_bound=str(lower_bound),
                median_estimate=str(median_estimate),
                upper_bound=str(upper_bound),
                confidence_percent=confidence_percent,
                rationale=rationale,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        )
        if self.numeric_create_error is not None:
            raise self.numeric_create_error
        revision = FakeNumericRevision(
            revision_id=1,
            prediction_id=99,
            lower_bound=FixedPrecisionValue.from_value(lower_bound, decimal_places),
            median_estimate=FixedPrecisionValue.from_value(
                median_estimate,
                decimal_places,
            ),
            upper_bound=FixedPrecisionValue.from_value(upper_bound, decimal_places),
            confidence_percent=confidence_percent,
            sequence=1,
            created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            rationale=(rationale or "").strip() or None,
        )
        prediction = FakeNumericPrediction(
            prediction_id=99,
            question=question.strip(),
            unit=unit.strip(),
            decimal_places=decimal_places,
            status=PredictionStatus.OPEN,
            created_at=revision.created_at,
            updated_at=revision.created_at,
            current_revision=revision,
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        self.numeric_latest = prediction
        self.numeric_revisions = [revision]
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

    def revise_numeric_forecast(
        self,
        prediction_id: int,
        lower_bound: object,
        median_estimate: object,
        upper_bound: object,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeNumericPrediction:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        if self.numeric_revision_error is not None:
            raise self.numeric_revision_error
        current = self.numeric_latest.current_revision
        revision = FakeNumericRevision(
            revision_id=current.revision_id + 1,
            prediction_id=prediction_id,
            lower_bound=FixedPrecisionValue.from_value(
                lower_bound, self.numeric_latest.decimal_places
            ),
            median_estimate=FixedPrecisionValue.from_value(
                median_estimate, self.numeric_latest.decimal_places
            ),
            upper_bound=FixedPrecisionValue.from_value(
                upper_bound, self.numeric_latest.decimal_places
            ),
            confidence_percent=confidence_percent,
            sequence=current.sequence + 1,
            created_at=datetime(2026, 8, 21, 19, 30, tzinfo=UTC),
            rationale=(rationale or "").strip() or None,
        )
        self.numeric_revisions.append(revision)
        self.numeric_latest = replace(self.numeric_latest, current_revision=revision)
        self.numeric_latest = replace(self.numeric_latest, deletion_allowed=False)
        return self.numeric_latest

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
        self.numeric_journal_entries = [
            entry
            for entry in self.numeric_journal_entries
            if entry.prediction_id != prediction_id
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

    def add_numeric_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeNumericJournalTimelineEvent:
        if (
            self.numeric_latest is None
            or self.numeric_latest.prediction_id != prediction_id
        ):
            raise ApplicationError("Numeric Prediction not found.")
        current = self.numeric_latest.current_revision
        entry = FakeNumericJournalTimelineEvent(
            entry_id=len(self.numeric_journal_entries) + 1,
            prediction_id=prediction_id,
            created_at=datetime(2026, 8, 21, 19, 30, tzinfo=UTC),
            body=body.strip(),
            original_body=body.strip(),
            numeric_forecast_revision_id=current.revision_id,
            forecast_revision_sequence=current.sequence,
            lower_bound=current.lower_bound,
            median_estimate=current.median_estimate,
            upper_bound=current.upper_bound,
            confidence_percent=current.confidence_percent,
        )
        self.numeric_journal_entries.append(entry)
        self.numeric_latest = replace(self.numeric_latest, deletion_allowed=False)
        return entry

    def correct_numeric_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> FakeNumericJournalTimelineEvent:
        for index, entry in enumerate(self.numeric_journal_entries):
            if entry.prediction_id == prediction_id and entry.entry_id == entry_id:
                correction_id = len(entry.corrections) + 1
                correction = FakeJournalCorrection(
                    correction_id=correction_id,
                    body=body.strip(),
                    corrected_at=datetime(2026, 8, 22, 19, 30, tzinfo=UTC),
                )
                updated = replace(
                    entry,
                    body=correction.body,
                    current_correction_id=correction_id,
                    corrections=(*entry.corrections, correction),
                )
                self.numeric_journal_entries[index] = updated
                return updated
        raise ApplicationError("Journal entry not found.")

    def list_numeric_timeline(
        self,
        prediction_id: int,
    ) -> tuple[FakeNumericForecastTimelineEvent | FakeNumericJournalTimelineEvent, ...]:
        if self.numeric_timeline_error is not None:
            raise self.numeric_timeline_error
        previous: FakeNumericRevision | None = None
        events: list[
            FakeNumericForecastTimelineEvent | FakeNumericJournalTimelineEvent
        ] = []
        for revision in self.numeric_revisions:
            if revision.prediction_id != prediction_id:
                continue
            events.append(
                FakeNumericForecastTimelineEvent(
                    revision_id=revision.revision_id,
                    prediction_id=prediction_id,
                    created_at=revision.created_at,
                    sequence=revision.sequence,
                    lower_bound=revision.lower_bound,
                    median_estimate=revision.median_estimate,
                    upper_bound=revision.upper_bound,
                    confidence_percent=revision.confidence_percent,
                    previous_lower_bound=None
                    if previous is None
                    else previous.lower_bound,
                    previous_median_estimate=None
                    if previous is None
                    else previous.median_estimate,
                    previous_upper_bound=None
                    if previous is None
                    else previous.upper_bound,
                    previous_confidence_percent=None
                    if previous is None
                    else previous.confidence_percent,
                    rationale=revision.rationale,
                )
            )
            previous = revision
        events.extend(
            entry
            for entry in self.numeric_journal_entries
            if entry.prediction_id == prediction_id
        )
        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.sequence
                    if isinstance(event, FakeNumericForecastTimelineEvent)
                    else event.forecast_revision_sequence,
                    0 if isinstance(event, FakeNumericForecastTimelineEvent) else 1,
                    event.revision_id
                    if isinstance(event, FakeNumericForecastTimelineEvent)
                    else event.entry_id,
                ),
            )
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
    ) -> FakePrediction:
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
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        if self.latest.metadata_version != expected_metadata_version:
            raise ConcurrentPredictionUpdateError(prediction_id)
        updated = replace(
            self.latest,
            question=question.strip(),
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        if updated != self.latest:
            self.mutation_count += 1
            updated = replace(
                updated,
                metadata_version=self.latest.metadata_version + 1,
                deletion_allowed=False,
            )
        self.latest = updated
        return self.latest

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
                    numeric_lower_bound=item.numeric_lower_bound,
                    numeric_median_estimate=item.numeric_median_estimate,
                    numeric_upper_bound=item.numeric_upper_bound,
                    numeric_confidence_percent=item.numeric_confidence_percent,
                    numeric_unit=item.numeric_unit,
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

    def get_analytics(self, *, tag: str | None = None) -> AnalyticsSnapshot:
        self.analytics_calls.append(tag)
        if self.analytics_error is not None:
            raise self.analytics_error
        return summarize_analytics(self.analytics_source, tag=tag)

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


@pytest.fixture
def operations() -> FakePredictionOperations:
    return FakePredictionOperations()


@pytest.fixture
def window(
    qtbot: QtBot,
    operations: FakePredictionOperations,
) -> MainWindow:
    main_window = MainWindow(operations)
    qtbot.addWidget(main_window)
    return main_window


def test_main_window_has_expected_navigation(window: MainWindow) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    sidebar = _required_child(window, QFrame, "applicationSidebar")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")

    assert window.windowTitle() == "Reckonsolve"
    assert sidebar.minimumWidth() == 240
    assert sidebar.maximumWidth() == 240
    assert window.screen_names == EXPECTED_SCREEN_NAMES
    assert window.navigation_names == EXPECTED_NAVIGATION_NAMES
    assert (
        tuple(navigation.item(index).text() for index in range(navigation.count()))
        == EXPECTED_NAVIGATION_NAMES
    )
    assert "Prediction Detail" not in tuple(
        navigation.item(index).text() for index in range(navigation.count())
    )
    assert new_prediction.text() == "New Prediction"
    assert new_prediction.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert settings.text() == "Settings"
    assert toggle.accessibleName() == "Collapse sidebar"
    assert window.current_screen_name == "Dashboard"
    assert navigation.currentRow() == 0
    assert navigation.property(NAVIGATION_COMPACT_PROPERTY) is False
    assert all(
        not navigation.item(index).icon().isNull()
        for index in range(navigation.count())
    )


def test_primary_navigation_never_scrolls_or_clips_a_destination(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    window.show()
    qtbot.waitUntil(lambda: navigation.viewport().height() > 0)

    for row in range(navigation.count()):
        navigation.setCurrentRow(row)
        item_rectangle = navigation.visualItemRect(navigation.item(row))
        assert navigation.viewport().rect().contains(item_rectangle)
        assert navigation.verticalScrollBar().value() == 0

    assert navigation.verticalScrollBar().maximum() == 0
    assert navigation.visualItemRect(navigation.item(0)).top() >= 0
    assert (
        navigation.visualItemRect(navigation.item(navigation.count() - 1)).bottom()
        <= navigation.viewport().rect().bottom()
    )


def test_sidebar_compact_mode_is_complete_accessible_and_remembered(
    qtbot: QtBot,
) -> None:
    settings = MemoryPresentationSettings()
    first = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=(QRect(0, 0, 1920, 1080),),
    )
    qtbot.addWidget(first)
    first.show()
    sidebar = _required_child(first, QFrame, "applicationSidebar")
    navigation = _required_child(first, QListWidget, "primaryNavigation")
    new_prediction = _required_child(
        first,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings_button = _required_child(first, QPushButton, "settingsNavigationButton")
    identity = _required_child(first, QLabel, "sidebarIdentity")
    toggle = _required_child(first, QPushButton, "sidebarModeToggle")

    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)

    assert first.sidebar_compact
    assert navigation.property(NAVIGATION_COMPACT_PROPERTY) is True
    assert sidebar.minimumWidth() == 68
    assert sidebar.maximumWidth() == 68
    assert identity.isHidden()
    assert new_prediction.text() == ""
    assert new_prediction.accessibleName() == "New Prediction"
    assert new_prediction.toolTip() == "Create a new prediction"
    assert settings_button.text() == ""
    assert settings_button.accessibleName() == "Settings"
    assert toggle.accessibleName() == "Expand sidebar"
    for index, screen_name in enumerate(EXPECTED_NAVIGATION_NAMES):
        item = navigation.item(index)
        assert item.text() == ""
        assert item.data(Qt.ItemDataRole.AccessibleTextRole) == screen_name
        assert item.toolTip() == screen_name
        assert not item.icon().isNull()
        item_rectangle = navigation.visualItemRect(item)
        assert item_rectangle.width() > item_rectangle.height()
        assert (
            abs(item_rectangle.center().x() - navigation.viewport().rect().center().x())
            <= 1
        )
    assert settings.state.sidebar_compact

    first.close()
    reopened = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=(QRect(0, 0, 1920, 1080),),
    )
    qtbot.addWidget(reopened)

    assert reopened.sidebar_compact
    assert (
        _required_child(
            reopened,
            QFrame,
            "applicationSidebar",
        ).width()
        == 68
    )


def test_compact_navigation_paints_each_icon_in_the_center_of_its_tile(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")
    window.show()
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    navigation.setCurrentRow(0)
    test_icon_color = QColor("#ff00ff")
    test_icon_pixmap = QPixmap(navigation.iconSize())
    test_icon_pixmap.fill(test_icon_color)
    test_icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected):
        test_icon.addPixmap(test_icon_pixmap, mode, QIcon.State.Off)
    navigation.item(0).setIcon(test_icon)
    image = navigation.viewport().grab().toImage()
    tile = navigation.visualItemRect(navigation.item(0))
    icon_pixels = tuple(
        QPoint(x, y)
        for y in range(tile.top(), tile.bottom() + 1)
        for x in range(tile.left(), tile.right() + 1)
        if image.pixelColor(x, y) == test_icon_color
    )

    assert icon_pixels
    painted_icon = QRect(
        QPoint(
            min(point.x() for point in icon_pixels),
            min(point.y() for point in icon_pixels),
        ),
        QPoint(
            max(point.x() for point in icon_pixels),
            max(point.y() for point in icon_pixels),
        ),
    )
    assert painted_icon.size() == navigation.iconSize()
    assert abs(painted_icon.center().x() - tile.center().x()) <= 1
    assert abs(painted_icon.center().y() - tile.center().y()) <= 1


def test_window_geometry_and_maximized_state_restore_without_minimized_state(
    qtbot: QtBot,
) -> None:
    screens = (QRect(0, 0, 1920, 1080),)
    settings = MemoryPresentationSettings(
        WindowPresentationState(
            normal_geometry=(140, 90, 1100, 720),
            maximized=True,
        )
    )
    first = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=screens,
    )
    qtbot.addWidget(first)

    assert first.windowState() & Qt.WindowState.WindowMaximized
    assert not first.windowState() & Qt.WindowState.WindowMinimized
    first.close()

    reopened = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=screens,
    )
    qtbot.addWidget(reopened)

    assert reopened.windowState() & Qt.WindowState.WindowMaximized
    assert not reopened.windowState() & Qt.WindowState.WindowMinimized
    assert reopened.normalGeometry() == QRect(140, 90, 1100, 720)


def test_shell_distinguishes_action_primary_and_bottom_utility_routes(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    sidebar = _required_child(window, QFrame, "applicationSidebar")
    sidebar_layout = sidebar.layout()
    assert sidebar_layout is not None
    assert sidebar_layout.itemAt(sidebar_layout.count() - 2).spacerItem() is not None
    assert sidebar_layout.itemAt(sidebar_layout.count() - 1).widget() is settings

    qtbot.mouseClick(new_prediction, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "New Prediction"
    assert navigation.currentRow() == -1
    assert new_prediction.property(NAVIGATION_ACTIVE_PROPERTY) is True
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is False

    qtbot.mouseClick(settings, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "Settings"
    assert navigation.currentRow() == -1
    assert new_prediction.property(NAVIGATION_ACTIVE_PROPERTY) is False
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is True

    navigation.setCurrentRow(1)
    assert window.current_screen_name == "Predictions"
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is False


def test_shell_navigation_remains_keyboard_operable_in_compact_mode(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    qtbot.keyClick(toggle, Qt.Key.Key_Space)
    assert window.sidebar_compact

    navigation.setFocus()
    qtbot.keyClick(navigation, Qt.Key.Key_Down)
    assert window.current_screen_name == "Predictions"
    qtbot.keyClick(navigation, Qt.Key.Key_Down)
    assert window.current_screen_name == "Analytics"

    new_prediction.setFocus()
    qtbot.keyClick(new_prediction, Qt.Key.Key_Space)
    assert window.current_screen_name == "New Prediction"

    settings.setFocus()
    qtbot.keyClick(settings, Qt.Key.Key_Space)
    assert window.current_screen_name == "Settings"


def test_main_window_applies_foundational_semantic_roles(window: MainWindow) -> None:
    title = _required_child(window, QLabel, "newPredictionScreenTitle")
    create = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")
    delete = _required_child(window, QPushButton, "deletePredictionButton")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert create.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert create.accessibleName() == "Create prediction"
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert error.accessibleName() == "Prediction form error"
    assert delete.property(ACTION_ROLE_PROPERTY) == ActionRole.DESTRUCTIVE.value


def test_palette_change_refreshes_semantic_colors_and_navigation_icons(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    notification = _required_child(window, NotificationHost, "notificationHost")
    notification.show_message("Palette-safe acknowledgment.")
    light = QPalette(window.palette())
    dark = QPalette(window.palette())
    for palette, background, base, text, mid in (
        (light, "#f4f5f4", "#ffffff", "#1c211f", "#c7ceca"),
        (dark, "#171a18", "#202421", "#edf3ef", "#505852"),
    ):
        for role, value in (
            (QPalette.ColorRole.Window, background),
            (QPalette.ColorRole.Base, base),
            (QPalette.ColorRole.AlternateBase, background),
            (QPalette.ColorRole.WindowText, text),
            (QPalette.ColorRole.Text, text),
            (QPalette.ColorRole.ButtonText, text),
            (QPalette.ColorRole.HighlightedText, text),
            (QPalette.ColorRole.PlaceholderText, text),
            (QPalette.ColorRole.Mid, mid),
        ):
            palette.setColor(role, QColor(value))

    window.setPalette(light)
    light_colors = semantic_colors(light)
    qtbot.waitUntil(lambda: light_colors.accent in window.styleSheet())
    light_icon_key = navigation.item(0).icon().cacheKey()

    window.setPalette(dark)
    dark_colors = semantic_colors(dark)
    qtbot.waitUntil(lambda: dark_colors.accent in window.styleSheet())
    dark_icon_key = navigation.item(0).icon().cacheKey()

    assert light_colors.is_dark is False
    assert dark_colors.is_dark is True
    assert light_colors.accent != dark_colors.accent
    assert light_icon_key != dark_icon_key
    assert notification.current_message == "Palette-safe acknowledgment."
    assert not notification.isHidden()


def test_high_value_actions_keep_text_icons_and_accessible_names(
    window: MainWindow,
) -> None:
    expected_actions = {
        "createPredictionButton": "Create Prediction",
        "editPredictionDetailsButton": "Edit Details",
        "reviseForecastButton": "Revise Forecast",
        "addJournalEntryButton": "Add Journal Entry",
        "resolvePredictionButton": "Resolve",
        "markInvalidButton": "Mark Invalid",
        "deletePredictionButton": "Delete",
        "applyPredictionFiltersButton": "Apply filters",
        "clearPredictionFiltersButton": "Clear filters",
        "openSelectedPredictionButton": "Open selected",
        "refreshAnalyticsButton": "Refresh",
        "saveStaleThresholdButton": "Save threshold",
        "backUpNowButton": "Back Up Now",
        "exportCsvBundleButton": "Export CSV Bundle",
        "repairSearchIndexButton": "Repair Search Index",
    }

    for object_name, text in expected_actions.items():
        button = _required_child(window, QPushButton, object_name)
        assert button.text() == text
        assert not button.icon().isNull()
        assert button.accessibleName()


def test_main_window_navigates_to_each_primary_screen(window: MainWindow) -> None:
    screen_stack = _required_child(window, QStackedWidget, "screenStack")

    for expected_index, screen_name in enumerate(EXPECTED_SCREEN_NAMES):
        window.navigate_to(screen_name)

        assert window.current_screen_name == screen_name
        assert screen_stack.currentIndex() == expected_index


def test_analytics_screen_replaces_the_placeholder(window: MainWindow) -> None:
    window.navigate_to("Analytics")

    assert _required_child(window, QWidget, "analyticsScreen").objectName() == (
        "analyticsScreen"
    )
    assert window.findChild(QLabel, "analyticsScreenPlaceholder") is None


def test_analytics_empty_state_is_honest_for_a_new_database(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Analytics")

    assert _required_child(window, QLabel, "analyticsScoredCount").text() == (
        "Scored predictions: 0"
    )
    assert _required_child(window, QLabel, "analyticsMeanBrier").text() == (
        "Mean Brier: Not available"
    )
    assert _required_child(window, QLabel, "analyticsEmpty").text() == (
        "No scored predictions yet. Resolve a prediction to begin analytics."
    )
    assert _required_child(window, QWidget, "analyticsScrollArea").isHidden()


def test_analytics_renders_summary_bins_counts_and_cumulative_series(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.analytics_source = AnalyticsSource(
        observations=(
            _scoring_observation(1, 20, BinaryOutcome.NO, tags=("Work",)),
            _scoring_observation(
                2,
                80,
                BinaryOutcome.YES,
                resolved_at=datetime(2026, 8, 21, 19, 30, tzinfo=UTC),
                tags=("Personal",),
            ),
            _scoring_observation(
                3,
                90,
                BinaryOutcome.NO,
                resolved_at=datetime(2026, 8, 22, 19, 30, tzinfo=UTC),
                tags=("Work",),
            ),
        ),
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Analytics")

    assert _required_child(window, QLabel, "analyticsScoredCount").text() == (
        "Scored predictions: 3"
    )
    assert _required_child(window, QLabel, "analyticsMeanBrier").text() == (
        "Mean Brier: 0.297"
    )
    tag_filter = _required_child(window, QComboBox, "analyticsTagFilter")
    assert [tag_filter.itemText(index) for index in range(tag_filter.count())] == [
        "All tags",
        "Personal",
        "Work",
    ]
    calibration = _required_child(window, CalibrationChart, "calibrationChart")
    trend = _required_child(window, BrierTrendChart, "brierTrendChart")
    table = _required_child(window, QTableWidget, "calibrationBinTable")
    assert sum(item.count for item in calibration.bins) == 3
    assert [point.scored_count for point in trend.points] == [1, 2, 3]
    assert table.item(2, 0).text() == "20-29%"
    assert table.item(2, 1).text() == "1"
    assert table.item(2, 2).text() == "20%"
    assert table.item(2, 3).text() == "0%"
    assert table.item(4, 1).text() == "0"
    assert table.item(4, 2).text() == "Not available"
    assert not _required_child(window, QWidget, "analyticsScrollArea").isHidden()


def test_analytics_tag_filter_recomputes_all_views_from_one_subset(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.analytics_source = AnalyticsSource(
        observations=(
            _scoring_observation(1, 20, BinaryOutcome.NO, tags=("Work",)),
            _scoring_observation(2, 80, BinaryOutcome.YES, tags=("Personal",)),
            _scoring_observation(3, 20, BinaryOutcome.YES, tags=("Work",)),
        ),
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Analytics")
    tag_filter = _required_child(window, QComboBox, "analyticsTagFilter")

    tag_filter.setCurrentIndex(tag_filter.findData("Work"))

    assert operations.analytics_calls[-1] == "Work"
    assert _required_child(window, QLabel, "analyticsScoredCount").text() == (
        "Scored predictions: 2"
    )
    assert _required_child(window, QLabel, "analyticsMeanBrier").text() == (
        "Mean Brier: 0.340"
    )
    calibration = _required_child(window, CalibrationChart, "calibrationChart")
    trend = _required_child(window, BrierTrendChart, "brierTrendChart")
    assert sum(item.count for item in calibration.bins) == 2
    assert len(trend.points) == 2


def test_analytics_reports_initial_and_stale_refresh_errors(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.analytics_error = ApplicationError("Scores could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Analytics")
    error = _required_child(window, QLabel, "analyticsError")
    assert error.text() == "Analytics unavailable. Scores could not be loaded."
    assert _required_child(window, QWidget, "analyticsBrierSummary").isHidden()

    operations.analytics_error = None
    operations.analytics_source = AnalyticsSource(
        observations=(_scoring_observation(1, 60, BinaryOutcome.YES),),
        available_tags=(),
    )
    window.navigate_to("New Prediction")
    window.navigate_to("Analytics")
    assert _required_child(window, QLabel, "analyticsScoredCount").text() == (
        "Scored predictions: 1"
    )
    operations.analytics_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Analytics")

    assert error.text() == (
        "Analytics could not refresh; showing the last loaded results. Refresh failed."
    )
    assert _required_child(window, QLabel, "analyticsMeanBrier").text() == (
        "Mean Brier: 0.160"
    )


def test_analytics_renders_unitless_numeric_containment_without_mixing_raw_units(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.numeric_analytics_source = NumericAnalyticsSource(
        observations=(
            _numeric_scoring_observation(
                1,
                lower=0,
                median=5,
                upper=10,
                actual=10,
                confidence=80,
                unit="days",
                tags=("Work",),
            ),
            _numeric_scoring_observation(
                2,
                lower=100,
                median=150,
                upper=200,
                actual=250,
                confidence=80,
                unit="USD",
                tags=("Money",),
            ),
        ),
        available_tags=("Money", "Work"),
        available_units=("days", "USD"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Analytics")

    assert _required_child(window, QLabel, "numericAnalyticsScoredCount").text() == (
        "Scored Numeric Predictions: 2"
    )
    assert _required_child(window, QLabel, "numericAnalyticsContainment").text() == (
        "Contained outcomes: 1 of 2 (50%)"
    )
    raw_scope = _required_child(window, QLabel, "numericAnalyticsRawScope")
    assert "will not average unlike units" in raw_scope.text()
    assert _required_child(window, QLabel, "numericMeanIntervalScore").text() == (
        "Mean interval score: Not available"
    )
    table = _required_child(window, QTableWidget, "containmentCalibrationBinTable")
    assert table.item(8, 0).text() == "80-89%"
    assert table.item(8, 1).text() == "2"
    assert table.item(8, 2).text() == "80%"
    assert table.item(8, 3).text() == "50%"
    chart = _required_child(
        window,
        ContainmentCalibrationChart,
        "containmentCalibrationChart",
    )
    assert sum(item.count for item in chart.bins) == 2
    unit_filter = _required_child(window, QComboBox, "analyticsUnitFilter")
    assert not unit_filter.isEnabled()


def test_numeric_type_and_exact_unit_filter_every_numeric_view(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.numeric_analytics_source = NumericAnalyticsSource(
        observations=(
            _numeric_scoring_observation(
                1,
                lower=0,
                median=5,
                upper=10,
                actual=8,
                confidence=80,
                unit="days",
                tags=("Work",),
            ),
            _numeric_scoring_observation(
                2,
                lower=100,
                median=150,
                upper=200,
                actual=250,
                confidence=80,
                unit="USD",
                tags=("Work",),
            ),
        ),
        available_tags=("Work",),
        available_units=("days", "USD"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Analytics")
    type_filter = _required_child(window, QComboBox, "analyticsTypeFilter")
    unit_filter = _required_child(window, QComboBox, "analyticsUnitFilter")

    type_filter.setCurrentIndex(type_filter.findData(PredictionType.NUMERIC))
    unit_filter.setCurrentIndex(unit_filter.findData("days"))

    assert unit_filter.isEnabled()
    assert operations.forecast_analytics_calls[-1] == (
        PredictionType.NUMERIC,
        None,
        "days",
    )
    assert _required_child(window, QWidget, "analyticsBrierSummary").isHidden()
    assert not _required_child(window, QWidget, "numericAnalyticsSummary").isHidden()
    assert _required_child(window, QLabel, "numericAnalyticsScoredCount").text() == (
        "Scored Numeric Predictions: 1"
    )
    assert _required_child(window, QLabel, "numericMeanMedianAbsoluteError").text() == (
        "Mean median absolute error: 3 days"
    )
    assert _required_child(window, QLabel, "numericMeanIntervalWidth").text() == (
        "Mean interval width: 10 days"
    )
    assert _required_child(window, QLabel, "numericMeanIntervalScore").text() == (
        "Mean interval score: 10 days"
    )
    table = _required_child(window, QTableWidget, "containmentCalibrationBinTable")
    assert table.item(8, 1).text() == "1"
    assert table.item(8, 3).text() == "100%"

    type_filter.setCurrentIndex(type_filter.findData(PredictionType.BINARY))
    assert not unit_filter.isEnabled()
    assert unit_filter.currentData() is None
    assert operations.forecast_analytics_calls[-1] == (
        PredictionType.BINARY,
        None,
        None,
    )


def test_prediction_browser_renders_all_results_and_filter_choices(
    qtbot: QtBot,
) -> None:
    first = PredictionBrowserItem(
        prediction_id=1,
        question="Will the archive remain calm?",
        probability_percent=35,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
        tags=("Work",),
    )
    second = PredictionBrowserItem(
        prediction_id=2,
        question="<b>Will literal markup stay literal?</b>",
        probability_percent=80,
        status=PredictionStatus.RESOLVED,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 20, 30, tzinfo=UTC),
        tags=("Personal", "Work"),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(second, first),
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Predictions")

    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, QListWidget, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert [
        status_filter.itemText(index) for index in range(status_filter.count())
    ] == [
        "All",
        "Open",
        "Locked",
        "Resolved",
        "Invalid",
    ]
    assert [tag_filter.item(index).text() for index in range(tag_filter.count())] == [
        "Personal",
        "Work",
    ]
    assert results.count() == 2
    assert "<b>Will literal markup stay literal?</b>" in results.item(0).text()
    assert "80%  |  RESOLVED" in results.item(0).text()
    assert "Tags: Personal, Work" in results.item(0).text()
    assert _required_child(window, QLabel, "predictionBrowserResultCount").text() == (
        "2 predictions"
    )
    open_button = _required_child(window, QPushButton, "openSelectedPredictionButton")
    assert results.currentRow() == -1
    assert results.selectedItems() == []
    assert not open_button.isEnabled()

    qtbot.keyPress(results, Qt.Key.Key_Down)

    assert results.currentRow() == 0
    assert open_button.isEnabled()


def test_prediction_browser_combines_filters_and_clear_restores_archive(
    qtbot: QtBot,
) -> None:
    items = (
        PredictionBrowserItem(
            prediction_id=3,
            question="Will policy pass this year?",
            probability_percent=70,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            tags=("Work",),
        ),
        PredictionBrowserItem(
            prediction_id=2,
            question="Will policy pass next year?",
            probability_percent=40,
            status=PredictionStatus.OPEN,
            created_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            tags=("Work",),
        ),
        PredictionBrowserItem(
            prediction_id=1,
            question="Will another issue resolve?",
            probability_percent=20,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            tags=("Personal",),
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=items,
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, QListWidget, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    search.setText("THIS YEAR")
    status_filter.setCurrentIndex(status_filter.findData("resolved"))
    tag_filter.item(1).setSelected(True)
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert results.count() == 1
    assert "Will policy pass this year?" in results.item(0).text()
    assert operations.browser_calls[-1] == (
        "THIS YEAR",
        PredictionStatus.RESOLVED,
        None,
    )
    assert operations.archive_calls[-1][0] == ("Work",)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert search.text() == ""
    assert status_filter.currentData() is None
    assert tag_filter.selectedItems() == []
    assert results.count() == 3
    assert operations.browser_calls[-1] == ("", None, None)


def test_prediction_browser_clears_a_filter_when_its_last_tag_is_removed(
    qtbot: QtBot,
) -> None:
    tagged = PredictionBrowserItem(
        prediction_id=1,
        question="Will an external edit remove this tag?",
        probability_percent=50,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        tags=("Temporary",),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(tagged,),
        available_tags=("Temporary",),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    tag_filter = _required_child(window, QListWidget, "predictionTagFilter")
    tag_filter.item(0).setSelected(True)

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(replace(tagged, tags=()),),
        available_tags=(),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert tag_filter.selectedItems() == []
    assert results.count() == 1
    assert operations.browser_calls[-2:] == [("", None, None), ("", None, None)]
    assert [call[0] for call in operations.archive_calls[-2:]] == [
        ("Temporary",),
        (),
    ]


def test_prediction_browser_sends_rich_archive_filters_and_resets_defaults(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will the rich archive controls remain clear?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=instant,
                latest_revision_at=instant,
                tags=("Blue", "Red"),
            ),
        ),
        available_tags=("Blue", "Green", "Red"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    tag_filter = _required_child(window, QListWidget, "predictionTagFilter")
    tag_filter.item(0).setSelected(True)
    tag_filter.item(2).setSelected(True)
    tag_mode = _required_child(window, QComboBox, "predictionTagMatchMode")
    tag_mode.setCurrentIndex(tag_mode.findData(ArchiveTagMatchMode.ANY.value))
    attention = _required_child(window, QComboBox, "predictionAttentionFilter")
    attention.setCurrentIndex(
        attention.findData(ArchiveAttention.NEEDS_ATTENTION.value)
    )
    date_meaning = _required_child(window, QComboBox, "predictionDateMeaning")
    date_meaning.setCurrentIndex(
        date_meaning.findData(ArchiveDateMeaning.EXPECTED_RESOLUTION.value)
    )
    date_start_enabled = _required_child(
        window, QCheckBox, "predictionDateStartEnabled"
    )
    date_start_enabled.setChecked(True)
    date_start = _required_child(window, QDateEdit, "predictionDateStart")
    date_start.setDate(QDate(2026, 8, 1))
    date_end_enabled = _required_child(window, QCheckBox, "predictionDateEndEnabled")
    date_end_enabled.setChecked(True)
    date_end = _required_child(window, QDateEdit, "predictionDateEnd")
    date_end.setDate(QDate(2026, 8, 31))
    sort = _required_child(window, QComboBox, "predictionSort")
    sort.setCurrentIndex(sort.findData(ArchiveSort.QUESTION_A_TO_Z.value))
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.archive_calls[-1] == (
        ("Blue", "Red"),
        ArchiveTagMatchMode.ANY,
        ArchiveAttention.NEEDS_ATTENTION,
        ArchiveDateMeaning.EXPECTED_RESOLUTION,
        date(2026, 8, 1),
        date(2026, 8, 31),
        ArchiveSort.QUESTION_A_TO_Z,
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert tag_filter.selectedItems() == []
    assert tag_mode.currentData() == ArchiveTagMatchMode.ALL.value
    assert attention.currentData() is None
    assert date_meaning.currentData() == ArchiveDateMeaning.CREATED.value
    assert not date_start_enabled.isChecked()
    assert not date_end_enabled.isChecked()
    assert sort.currentData() == ArchiveSort.CREATED_NEWEST.value

    _required_child(window, QLineEdit, "predictionSearchInput").setText("rich")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )
    assert operations.archive_calls[-1][-1] is ArchiveSort.RELEVANCE


def test_prediction_browser_applies_and_explicitly_updates_dynamic_saved_views(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    configuration = SavedViewConfiguration(
        search_text="evidence",
        match_mode=SearchMatchMode.ANY,
        include_superseded=True,
        archive_query=ArchiveQuery(
            status=PredictionStatus.OPEN,
            prediction_type=PredictionType.BINARY,
            tags=("Work",),
            tag_match_mode=ArchiveTagMatchMode.ALL,
            attention=None,
            date_meaning=ArchiveDateMeaning.EXPECTED_RESOLUTION,
            date_start=date(2026, 8, 1),
            date_end=date(2026, 8, 31),
            sort=ArchiveSort.RELEVANCE,
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will evidence remain in a dynamic Saved View?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=instant,
                latest_revision_at=instant,
                expected_resolution=date(2026, 8, 15),
                tags=("Work",),
            ),
        ),
        available_tags=("Work",),
    )
    operations.saved_views = [
        SavedView(
            saved_view_id=7,
            name="Evidence",
            normalized_name="evidence",
            configuration=configuration,
            tags=(),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    picker = _required_child(window, QComboBox, "savedViewPicker")
    picker.setCurrentIndex(picker.findData(7))

    assert _required_child(window, QLineEdit, "predictionSearchInput").text() == (
        "evidence"
    )
    assert _required_child(
        window, QComboBox, "predictionSearchMatchMode"
    ).currentData() == (SearchMatchMode.ANY.value)
    assert _required_child(
        window, QCheckBox, "predictionSearchIncludeHistory"
    ).isChecked()
    assert _required_child(
        window, QComboBox, "predictionStatusFilter"
    ).currentData() == (PredictionStatus.OPEN.value)
    assert _required_child(
        window, QComboBox, "predictionDateMeaning"
    ).currentData() == (ArchiveDateMeaning.EXPECTED_RESOLUTION.value)
    assert _required_child(window, QLabel, "savedViewState").text() == "Evidence: Saved"

    status = _required_child(window, QComboBox, "predictionStatusFilter")
    status.setCurrentIndex(status.findData(PredictionStatus.RESOLVED.value))
    update = _required_child(window, QPushButton, "updateSavedViewButton")
    assert update.isEnabled()
    assert _required_child(window, QLabel, "savedViewState").text() == (
        "Evidence: Modified"
    )

    qtbot.mouseClick(update, Qt.MouseButton.LeftButton)

    assert operations.saved_views[0].configuration.archive_query.status is (
        PredictionStatus.RESOLVED
    )
    assert _required_child(window, QLabel, "savedViewState").text() == "Evidence: Saved"


def test_prediction_browser_saved_view_creation_rename_delete_and_cancel(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Focus", True),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveCurrentViewButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [view.name for view in operations.saved_views] == ["Focus"]
    assert _required_child(window, QLabel, "savedViewState").text() == "Focus: Saved"

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Renamed", True),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "renameSavedViewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [view.name for view in operations.saved_views] == ["Renamed"]

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Ignored", False),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveViewAsNewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [view.name for view in operations.saved_views] == ["Renamed"]

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "deleteSavedViewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert operations.saved_views == []
    assert _required_child(window, QLabel, "savedViewState").text() == (
        "No Saved View selected"
    )


def test_prediction_browser_opens_secondary_tag_manager(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    opened: list[FakePredictionOperations] = []

    class FakeTagDialog:
        changed = False

        def __init__(self, supplied_operations, _parent) -> None:
            opened.append(supplied_operations)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.TagManagerDialog",
        FakeTagDialog,
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "manageTagsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert opened == [operations]


def test_tag_manager_filters_and_confirms_rename_merge_and_delete(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    operations.tag_library = [
        TagLibraryItem(1, "Work", "work", 2, 1),
        TagLibraryItem(2, "Personal", "personal", 1, 0),
        TagLibraryItem(3, "Old", "old", 1, 2),
    ]
    dialog = TagManagerDialog(operations)
    qtbot.addWidget(dialog)
    table = _required_child(dialog, QTableWidget, "tagManagerTable")
    filter_input = _required_child(dialog, QLineEdit, "tagManagerFilter")

    assert table.rowCount() == 3
    filter_input.setText("pers")
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Personal"
    filter_input.clear()

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Career", True),
    )
    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    _select_tag_rows(table, "Work")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "renameTagButton"),
        Qt.MouseButton.LeftButton,
    )
    assert {tag.display_name for tag in operations.tag_library} == {
        "Career",
        "Personal",
        "Old",
    }

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getItem",
        lambda *_args, **_kwargs: ("Career", True),
    )
    _select_tag_rows(table, "Career", "Personal")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "mergeTagsButton"),
        Qt.MouseButton.LeftButton,
    )
    assert {tag.display_name for tag in operations.tag_library} == {
        "Career",
        "Old",
    }

    confirmations: list[str] = []

    def confirm_delete(*args, **_kwargs):
        confirmations.append(str(args[2]))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QMessageBox.question",
        confirm_delete,
    )
    _select_tag_rows(table, "Old")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "deleteTagButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [tag.display_name for tag in operations.tag_library] == ["Career"]
    assert "may return a broader set of Predictions" in confirmations[-1]
    assert dialog.changed


def test_tag_manager_cancellation_leaves_library_unchanged(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    original = TagLibraryItem(1, "Work", "work", 2, 1)
    operations.tag_library = [original]
    dialog = TagManagerDialog(operations)
    qtbot.addWidget(dialog)
    table = _required_child(dialog, QTableWidget, "tagManagerTable")
    _select_tag_rows(table, "Work")
    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Career", False),
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "renameTagButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.tag_library == [original]
    assert not dialog.changed


def test_type_aware_dashboard_and_browser_render_and_open_numeric_detail(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    numeric_revision = FakeNumericRevision(
        revision_id=20,
        prediction_id=2,
        lower_bound=FixedPrecisionValue(20, 1),
        median_estimate=FixedPrecisionValue(40, 1),
        upper_bound=FixedPrecisionValue(80, 1),
        confidence_percent=80,
        sequence=1,
        created_at=instant,
    )
    numeric = FakeNumericPrediction(
        prediction_id=2,
        question="How many Numeric days?",
        unit="days",
        decimal_places=1,
        status=PredictionStatus.OPEN,
        created_at=instant,
        updated_at=instant,
        current_revision=numeric_revision,
        tags=("Numbers",),
    )
    binary = PredictionBrowserItem(
        prediction_id=1,
        question="Will Binary remain visible?",
        probability_percent=60,
        status=PredictionStatus.OPEN,
        created_at=instant,
        latest_revision_at=instant,
    )
    numeric_item = PredictionBrowserItem(
        prediction_id=numeric.prediction_id,
        question=numeric.question,
        probability_percent=None,
        status=numeric.status,
        created_at=instant,
        latest_revision_at=instant,
        tags=numeric.tags,
        prediction_type=PredictionType.NUMERIC,
        numeric_lower_bound=numeric_revision.lower_bound,
        numeric_median_estimate=numeric_revision.median_estimate,
        numeric_upper_bound=numeric_revision.upper_bound,
        numeric_confidence_percent=numeric_revision.confidence_percent,
        numeric_unit=numeric.unit,
    )
    operations = FakePredictionOperations()
    operations.numeric_latest = numeric
    operations.dashboard_snapshot = DashboardSnapshot(
        stale_threshold_days=14,
        open_predictions=(
            DashboardPrediction(
                prediction_id=numeric.prediction_id,
                question=numeric.question,
                probability_percent=None,
                status=numeric.status,
                latest_revision_at=instant,
                prediction_type=PredictionType.NUMERIC,
                numeric_lower_bound=numeric_revision.lower_bound,
                numeric_median_estimate=numeric_revision.median_estimate,
                numeric_upper_bound=numeric_revision.upper_bound,
                numeric_confidence_percent=numeric_revision.confidence_percent,
                numeric_unit=numeric.unit,
            ),
        ),
        needs_attention_predictions=(),
        ready_to_resolve_predictions=(),
        locked_predictions=(),
    )
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(binary, numeric_item),
        available_tags=("Numbers",),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dashboard_row = _required_child(window, QPushButton, "dashboardOpenPrediction2")
    assert "NUMERIC" in dashboard_row.text()
    assert "80% interval: 2.0–8.0 days; median: 4.0 days" in dashboard_row.text()
    qtbot.mouseClick(dashboard_row, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        numeric.question
    )

    window.navigate_to("Predictions")
    type_filter = _required_child(window, QComboBox, "predictionTypeFilter")
    type_filter.setCurrentIndex(type_filter.findData(PredictionType.NUMERIC.value))
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1
    assert "NUMERIC" in results.item(0).text()
    assert "80% interval: 2.0–8.0 days; median: 4.0 days" in results.item(0).text()
    assert operations.browser_type_calls[-1] is PredictionType.NUMERIC

    results.itemActivated.emit(results.item(0))
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        numeric.question
    )

    window.navigate_to("Predictions")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )
    assert type_filter.currentData() is None
    assert _required_child(window, QListWidget, "predictionBrowserResults").count() == 2
    assert operations.browser_type_calls[-1] is None


def test_prediction_browser_distinguishes_new_database_and_no_matches(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    empty = _required_child(window, QLabel, "predictionBrowserEmpty")

    assert empty.text() == "No predictions yet. Create one from New Prediction."

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will something happen?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
                latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            ),
        ),
        available_tags=(),
    )
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    search.setText("absent")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    assert empty.text() == "No predictions match the current search and filters."
    assert _required_child(window, QListWidget, "predictionBrowserResults").isHidden()


def test_prediction_browser_opens_fresh_detail_from_keyboard_activation(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Open this from the Predictions archive",
        62,
        tags=("Archive",),
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    results.itemActivated.emit(results.item(0))

    assert operations.get_calls[-1] == latest.prediction_id
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_prediction_result_rows_are_inset_from_the_rounded_frame(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    window.show()
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    results.setFocus()
    qtbot.waitUntil(lambda: results.viewport().width() > 0)

    viewport = results.viewport().geometry()
    inset = int(Radius.SMALL)
    assert viewport.left() >= inset
    assert viewport.top() >= inset
    assert results.width() - viewport.right() - 1 >= inset
    assert results.height() - viewport.bottom() - 1 >= inset


def test_prediction_search_renders_safe_explainable_rows_and_shared_controls(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will <evidence> remain literal?",
        62,
        tags=("Research",),
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("evidence")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1
    assert results.currentRow() == -1
    assert results.selectedItems() == []
    assert operations.search_calls[-1][:3] == (
        "evidence",
        SearchMatchMode.ALL,
        False,
    )
    source = _required_child(window, QLabel, "predictionSearchResultSource7")
    snippet = _required_child(window, QLabel, "predictionSearchResultSnippet7")
    assert source.text() == "Question match"
    assert snippet.text() == "Will &lt;<b>evidence</b>&gt; remain literal?"
    assert "Question match" in str(
        results.item(0).data(Qt.ItemDataRole.AccessibleDescriptionRole)
    )

    history = _required_child(window, QCheckBox, "predictionSearchIncludeHistory")
    history.setChecked(True)
    assert operations.search_calls[-1][2] is True
    mode = _required_child(window, QComboBox, "predictionSearchMatchMode")
    mode.setCurrentIndex(mode.findData(SearchMatchMode.ANY.value))
    assert operations.search_calls[-1][1] is SearchMatchMode.ANY


def test_prediction_search_offers_deliberate_any_word_and_spelling_actions(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the archive remain searchable?", 50)
    )
    operations.search_any_word_available = True
    operations.search_suggestion = "archive"
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("archive absentword")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    any_word = _required_child(window, QPushButton, "predictionSearchAnyWordButton")
    suggestion = _required_child(
        window, QPushButton, "predictionSearchSuggestionButton"
    )
    assert not any_word.isHidden()
    assert not suggestion.isHidden()
    assert "archive" in suggestion.text()

    qtbot.mouseClick(any_word, Qt.MouseButton.LeftButton)
    assert operations.search_calls[-1][1] is SearchMatchMode.ANY
    qtbot.mouseClick(suggestion, Qt.MouseButton.LeftButton)
    assert search.text() == "archive"
    assert operations.search_calls[-1][0] == "archive"


def test_historical_journal_search_opens_the_exact_detail_context(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(7, "Will remembered evidence matter?", 62)
    operations = FakePredictionOperations(latest)
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=8,
            prediction_id=7,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
            body="Corrected Journal evidence",
            original_body="Superseded remembered wording",
            forecast_revision_id=latest.current_revision_id,
            forecast_revision_sequence=latest.current_revision_sequence,
            forecast_probability_percent=latest.probability_percent,
            current_correction_id=11,
            corrections=(
                FakeJournalCorrection(
                    correction_id=11,
                    body="Corrected Journal evidence",
                    corrected_at=datetime(2026, 8, 14, 19, 30, tzinfo=UTC),
                ),
            ),
        )
    ]
    operations.search_document = SearchDocument(
        prediction_id=7,
        source_kind=SearchSourceKind.JOURNAL,
        source_record_id=8,
        source_version_id=None,
        source_sequence=None,
        occurred_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
        is_superseded=True,
        text="Superseded remembered wording",
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    _required_child(window, QCheckBox, "predictionSearchIncludeHistory").setChecked(
        True
    )
    search.setText("remembered")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    results.itemActivated.emit(results.item(0))

    assert window.current_screen_name == "Prediction Detail"
    history = _required_child(window, QGroupBox, "journalEntryEditHistory8")
    original = _required_child(window, QLabel, "journalEntryOriginalBody8")
    assert history.isChecked()
    assert original.property("searchMatchEmphasis") is True


def test_prediction_search_failure_retains_the_last_successful_rows(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will archive search remain visible?", 50)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    search.setText("archive")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1

    operations.browser_error = ApplicationError("Search is temporarily busy.")
    search.setText("different")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    assert results.count() == 1
    assert "archive search" in results.item(0).text()
    assert _required_child(window, QLabel, "predictionBrowserError").text() == (
        "Predictions could not refresh; showing the last loaded results. "
        "Search is temporarily busy."
    )


def test_prediction_search_controls_do_not_shift_when_results_become_empty(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will wow remain searchable?", 50)
    )
    window = MainWindow(operations)
    window.resize(960, 720)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("wow")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    qtbot.waitUntil(
        lambda: (
            _required_child(window, QListWidget, "predictionBrowserResults").count()
            == 1
        )
    )
    populated_top = search.mapTo(window, search.rect().topLeft()).y()

    search.setText("sdsfs")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    empty = _required_child(window, QLabel, "predictionBrowserEmpty")
    qtbot.waitUntil(lambda: not empty.isHidden())

    assert search.mapTo(window, search.rect().topLeft()).y() == populated_top


def test_prediction_browser_refreshes_and_reports_initial_or_stale_errors(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.browser_error = ApplicationError("Archive could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    error = _required_child(window, QLabel, "predictionBrowserError")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    assert error.text() == "Predictions unavailable. Archive could not be loaded."
    assert results.isHidden()

    operations.browser_error = None
    operations.latest = FakePrediction(9, "Appeared after retry", 48)
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")
    assert results.count() == 1
    operations.browser_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")

    assert error.text() == (
        "Predictions could not refresh; showing the last loaded results. "
        "Refresh failed."
    )
    assert not results.isHidden()
    assert "Appeared after retry" in results.item(0).text()


def test_prediction_browser_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    timer = window.findChild(QTimer, "predictionBrowserRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(10, "Appeared at the lock boundary", 33)
    timer.timeout.emit()
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert "Appeared at the lock boundary" in results.item(0).text()

    window.navigate_to("New Prediction")
    assert not timer.isActive()


def test_dashboard_renders_overlapping_buckets_without_losing_classifications(
    qtbot: QtBot,
) -> None:
    open_prediction = DashboardPrediction(
        prediction_id=1,
        question="Fresh open forecast",
        probability_percent=45,
        status=PredictionStatus.OPEN,
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
    )
    overlap = DashboardPrediction(
        prediction_id=7,
        question="<b>Literal locked forecast</b>",
        probability_percent=70,
        status=PredictionStatus.LOCKED,
        latest_revision_at=datetime(2026, 8, 1, 19, 30, tzinfo=UTC),
        forecast_deadline=date(2026, 8, 10),
        expected_resolution=date(2026, 8, 15),
        needs_attention=True,
        ready_to_resolve=True,
    )
    operations = FakePredictionOperations()
    operations.dashboard_snapshot = DashboardSnapshot(
        stale_threshold_days=14,
        open_predictions=(open_prediction,),
        needs_attention_predictions=(overlap,),
        ready_to_resolve_predictions=(overlap,),
        locked_predictions=(overlap,),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name, title in (
        ("dashboardOpenSection", "Open"),
        ("dashboardNeedsAttentionSection", "Needs Attention"),
        ("dashboardReadyToResolveSection", "Ready to Resolve"),
        ("dashboardLockedSection", "Locked"),
    ):
        panel = _required_child(window, ContentPanel, object_name)
        assert panel.title_label.text() == title
        assert panel.count_badge.text() == "1"
    for object_name in (
        "dashboardNeedsAttentionPrediction7",
        "dashboardReadyToResolvePrediction7",
        "dashboardLockedPrediction7",
    ):
        row = _required_child(window, QPushButton, object_name)
        assert "<b>Literal locked forecast</b>" in row.text()
        assert "70%" in row.text()
        assert "needs attention" in row.accessibleDescription()
        assert "ready to resolve" in row.accessibleDescription()
        question = _required_child(row, QLabel, "dashboardRowQuestion")
        assert question.textFormat() is Qt.TextFormat.PlainText
        assert question.wordWrap()
        badges = {badge.text() for badge in row.findChildren(QLabel) if badge.text()}
        assert "LOCKED" in badges
        assert "NEEDS ATTENTION" in badges
        assert "READY TO RESOLVE" in badges
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 14 days"
    )
    assert (
        "one Prediction may appear in more than one section"
        in _required_child(
            window,
            QLabel,
            "dashboardIntroduction",
        ).text()
    )


def test_dashboard_row_opens_fresh_prediction_detail(qtbot: QtBot) -> None:
    latest = FakePrediction(7, "Open this from Dashboard", 55)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)

    row = _required_child(window, QPushButton, "dashboardOpenPrediction7")
    qtbot.mouseClick(row, Qt.MouseButton.LeftButton)

    assert operations.get_calls[-1] == 7
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_contextual_detail_returns_to_dashboard_without_a_fake_destination(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(7, "Return this to Dashboard", 55)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    dashboard_calls = operations.dashboard_calls

    qtbot.mouseClick(
        _required_child(window, QPushButton, "dashboardOpenPrediction7"),
        Qt.MouseButton.LeftButton,
    )

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Dashboard"
    assert navigation.currentRow() == 0
    assert all(
        navigation.item(index).data(Qt.ItemDataRole.UserRole) != "Prediction Detail"
        for index in range(navigation.count())
    )

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Dashboard"
    assert operations.dashboard_calls == dashboard_calls


def test_contextual_detail_preserves_prediction_search_state_without_refresh(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(30, "Archive context item 30", 64)
    operations = FakePredictionOperations(latest)
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=tuple(
            PredictionBrowserItem(
                prediction_id=index,
                question=f"Archive context item {index}",
                probability_percent=64,
                status=PredictionStatus.OPEN,
                created_at=datetime(2026, 8, 20, 19, index, tzinfo=UTC),
                latest_revision_at=datetime(2026, 8, 20, 19, index, tzinfo=UTC),
            )
            for index in range(1, 31)
        ),
        available_tags=(),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    status = _required_child(window, QComboBox, "predictionStatusFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    search.setText("archive context")
    status.setCurrentIndex(status.findData(PredictionStatus.OPEN.value))
    _required_child(window, QPushButton, "applyPredictionFiltersButton").click()
    assert results.count() == 30
    results.setCurrentRow(29)
    results.verticalScrollBar().setValue(results.verticalScrollBar().maximum())
    scroll_position = results.verticalScrollBar().value()
    assert scroll_position > 0
    search_call_count = len(operations.search_calls)
    browser_call_count = len(operations.browser_calls)

    results.itemActivated.emit(results.item(29))

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Predictions"
    assert _required_child(window, QListWidget, "primaryNavigation").currentRow() == 1

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Predictions"
    assert search.text() == "archive context"
    assert status.currentData() == PredictionStatus.OPEN.value
    assert results.count() == 30
    assert results.currentRow() == 29
    assert results.verticalScrollBar().value() == scroll_position
    assert len(operations.search_calls) == search_call_count
    assert len(operations.browser_calls) == browser_call_count


def test_created_prediction_detail_returns_to_last_primary_destination(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(12, "Return creation to Analytics", 50)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Analytics")
    window.navigate_to("New Prediction")

    window._new_prediction_screen.prediction_created.emit(latest)

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Analytics"
    assert _required_child(window, QListWidget, "primaryNavigation").currentRow() == 2

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Analytics"


def test_dashboard_refreshes_when_reentered(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    initial_calls = operations.dashboard_calls
    first_empty = _required_child(window, QLabel, "dashboardOpenEmpty")
    assert first_empty.text() == "No open predictions."

    operations.latest = FakePrediction(8, "Appeared while away", 35)
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")

    assert operations.dashboard_calls == initial_calls + 1
    assert (
        "Appeared while away"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction8",
        ).text()
    )


def test_dashboard_refresh_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    timer = window.findChild(QTimer, "dashboardRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(9, "Appeared at a time boundary", 48)
    timer.timeout.emit()
    assert (
        "Appeared at a time boundary"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction9",
        ).text()
    )

    window.navigate_to("New Prediction")
    assert not timer.isActive()
    window.navigate_to("Dashboard")
    assert timer.isActive()


def test_settings_persists_threshold_and_refreshes_dashboard(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dashboard_calls = operations.dashboard_calls

    window.navigate_to("Settings")
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    save = _required_child(window, QPushButton, "saveStaleThresholdButton")
    assert threshold.value() == 14
    assert threshold.minimum() == 1
    assert threshold.maximum() == 9999

    threshold.setValue(30)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    assert operations.threshold_set_calls == [30]
    assert operations.stale_threshold_days == 30
    assert operations.dashboard_calls == dashboard_calls + 1
    assert _required_child(window, QLabel, "staleThresholdStatus").isHidden()
    notification = _required_child(window, NotificationHost, "notificationHost")
    assert notification.current_message == (
        "Needs Attention threshold saved at 30 days."
    )
    assert not notification.isHidden()
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 30 days"
    )


def test_settings_displays_database_and_persisted_backup_status(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.data_management_status = replace(
        operations.data_management_status,
        last_successful_backup_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Settings")

    assert _required_child(window, QLabel, "databaseLocation").text() == (
        f"Database: {Path('test-data/reckonsolve.sqlite3')}"
    )
    expected_local = (
        datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
        .astimezone()
        .strftime("%b %d, %Y, %I:%M %p")
        .replace(" 0", " ")
    )
    assert _required_child(window, QLabel, "lastSuccessfulBackup").text() == (
        f"Last successful backup: {expected_local}"
    )
    for panel_name in ("attentionSettingsPanel", "dataManagementPanel"):
        panel = _required_child(window, ContentPanel, panel_name)
        assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert (
        _required_child(
            window,
            QPushButton,
            "saveStaleThresholdButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "backUpNowButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "exportCsvBundleButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.SECONDARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "repairSearchIndexButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.QUIET.value
    )
    database_path = _required_child(window, QLabel, "databaseLocation")
    assert database_path.textInteractionFlags() & (
        Qt.TextInteractionFlag.TextSelectableByKeyboard
    )


def test_settings_creates_backup_and_csv_bundle_from_selected_destinations(
    qtbot: QtBot,
    monkeypatch,
    tmp_path,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    selected_paths = iter(
        (
            str(tmp_path / "chosen-backup"),
            str(tmp_path / "chosen-export"),
        )
    )
    suggested_paths: list[str] = []

    def choose_file(_parent, _title, suggested, _file_filter):
        suggested_paths.append(suggested)
        return next(selected_paths), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_file)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )

    expected_backup = tmp_path / "chosen-backup.sqlite3"
    assert operations.backup_calls == [expected_backup]
    assert _required_child(window, QLabel, "dataManagementStatus").text() == (
        f"Backup created: {expected_backup}"
    )
    assert (
        _required_child(
            window,
            QLabel,
            "dataManagementStatus",
        ).property(MESSAGE_TONE_PROPERTY)
        == StatusTone.SUCCESS.value
    )
    assert (
        "Not yet"
        not in _required_child(
            window,
            QLabel,
            "lastSuccessfulBackup",
        ).text()
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )

    expected_export = tmp_path / "chosen-export.zip"
    assert operations.export_calls == [expected_export]
    assert _required_child(window, QLabel, "dataManagementStatus").text() == (
        f"Exported 16 CSV files: {expected_export}"
    )
    assert suggested_paths[0].endswith("reckonsolve-backup-20260820-123000.sqlite3")
    assert suggested_paths[1].endswith("reckonsolve-export-20260820-123000.zip")


def test_cancelling_data_destination_dialogs_has_no_side_effect(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_arguments: ("", ""),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.backup_calls == []
    assert operations.export_calls == []
    assert _required_child(window, QLabel, "dataManagementStatus").isHidden()


def test_settings_repairs_search_index_and_reports_expected_failure(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    button = _required_child(window, QPushButton, "repairSearchIndexButton")
    status = _required_child(window, QLabel, "dataManagementStatus")

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert operations.search_repair_calls == 1
    assert status.text() == ("Search index repaired from canonical Prediction history.")

    operations.search_repair_error = ApplicationError(
        "Search repair could not complete."
    )
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert operations.search_repair_calls == 2
    assert status.text() == "Search repair could not complete."


def test_settings_shows_expected_backup_export_and_status_errors(
    qtbot: QtBot,
    monkeypatch,
    tmp_path,
) -> None:
    operations = FakePredictionOperations()
    operations.data_management_error = ApplicationError("Backup status unavailable.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    status = _required_child(window, QLabel, "dataManagementStatus")
    assert status.text() == "Backup status unavailable."

    operations.data_management_error = None
    operations.backup_error = ApplicationError("Backup destination is locked.")
    operations.export_error = ApplicationError("Export destination is locked.")
    selected_paths = iter(
        (str(tmp_path / "backup.sqlite3"), str(tmp_path / "export.zip"))
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_arguments: (next(selected_paths), ""),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )
    assert status.text() == "Backup destination is locked."
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )
    assert status.text() == "Export destination is locked."
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value


def test_routine_notification_survives_navigation_without_reflow(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Settings")
    stack = _required_child(window, QStackedWidget, "screenStack")
    geometry_before = stack.geometry()
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    threshold.setValue(21)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveStaleThresholdButton"),
        Qt.MouseButton.LeftButton,
    )
    notification = _required_child(window, NotificationHost, "notificationHost")
    window.navigate_to("Dashboard")

    assert notification.isVisible()
    assert notification.current_message == (
        "Needs Attention threshold saved at 21 days."
    )
    assert stack.geometry() == geometry_before


def test_notification_failure_cannot_roll_back_a_saved_setting(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    threshold.setValue(22)
    notification = _required_child(window, NotificationHost, "notificationHost")
    monkeypatch.setattr(
        notification,
        "show_message",
        lambda _message: (_ for _ in ()).throw(RuntimeError("paint failed")),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveStaleThresholdButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.threshold_set_calls == [22]
    assert operations.stale_threshold_days == 22
    assert _required_child(window, QLabel, "staleThresholdStatus").isHidden()


def test_dashboard_and_settings_show_expected_read_errors(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.dashboard_error = ApplicationError("Dashboard could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard unavailable. Dashboard could not be loaded."
    )
    assert _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.dashboard_error = None
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    operations.dashboard_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard could not refresh; showing the last loaded results. Refresh failed."
    )
    assert not _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.threshold_error = ApplicationError("Setting could not be loaded.")
    window.navigate_to("Settings")
    assert _required_child(window, QLabel, "staleThresholdStatus").text() == (
        "Setting could not be loaded."
    )
    assert not _required_child(window, QSpinBox, "staleThresholdInput").isEnabled()
    assert not _required_child(
        window,
        QPushButton,
        "saveStaleThresholdButton",
    ).isEnabled()
    assert operations.data_management_calls > 0
    assert _required_child(window, QLabel, "databaseLocation").text() == (
        f"Database: {Path('test-data/reckonsolve.sqlite3')}"
    )


def test_new_prediction_form_has_integer_probability_bounds_and_focus(
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")

    assert window.focusWidget() is question
    assert probability.minimum() == 0
    assert probability.maximum() == 100
    assert probability.value() == 50
    assert probability.suffix() == "%"

    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details_content = _required_child(
        window,
        QWidget,
        "newPredictionMoreDetailsContent",
    )
    assert not more_details.isChecked()
    assert more_details_content.isHidden()


def test_m42_creation_form_uses_shared_hierarchy_and_type_aware_guidance(
    window: MainWindow,
) -> None:
    window.navigate_to("New Prediction")

    title = _required_child(window, QLabel, "newPredictionScreenTitle")
    supporting = _required_child(
        window,
        QLabel,
        "newPredictionScreenSupportingText",
    )
    panel = _required_child(window, ContentPanel, "newPredictionForecastPanel")
    create = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert supporting.property(TEXT_ROLE_PROPERTY) == TextRole.SECONDARY.value
    assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert panel.supporting_label.text() == (
        "Binary forecasts need only a Question and Probability."
    )
    assert create.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value

    prediction_type = _required_child(window, QComboBox, "predictionTypeInput")
    prediction_type.setCurrentIndex(
        prediction_type.findData(PredictionType.NUMERIC.value)
    )

    assert panel.supporting_label.text() == (
        "Numeric forecasts need a Question, unit, precision, interval, median, "
        "and confidence."
    )


def test_m42_binary_detail_separates_identity_common_and_lifecycle_actions(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        42,
        "Will this long question remain fully legible in the refreshed detail view?",
        65,
        tags=("presentation", "long-context"),
    )
    window = MainWindow(FakePredictionOperations(prediction))
    qtbot.addWidget(window)
    window.resize(800, 640)
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.waitUntil(window.isVisible)

    question = _required_child(window, QLabel, "predictionDetailQuestion")
    forecast_type = _required_child(window, QLabel, "predictionDetailType")
    status = _required_child(window, QLabel, "predictionDetailStatus")
    summary = _required_child(window, QFrame, "predictionDetailSummaryPanel")
    action_panel = _required_child(window, QFrame, "predictionDetailActionPanel")
    action_help = _required_child(window, QLabel, "predictionDetailActionHelp")
    action_container = _required_child(
        window,
        QWidget,
        "futurePredictionActions",
    )
    action_grid = action_container.layout()
    assert isinstance(action_grid, QGridLayout)

    assert question.text() == prediction.question
    assert question.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert (
        question.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    )
    assert forecast_type.text() == "BINARY"
    assert status.property(BADGE_TONE_PROPERTY) == StatusTone.ACCENT.value
    assert summary.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert action_panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert window.findChild(QLabel, "predictionDetailLifecycleHeading") is None
    assert action_help.property(TEXT_ROLE_PROPERTY) == TextRole.LABEL.value
    assert action_help.contentsMargins().bottom() == int(Spacing.CONTROL)
    assert (
        _required_child(window, QPushButton, "reviseForecastButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(window, QPushButton, "deletePredictionButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.DESTRUCTIVE.value
    )
    edit = _required_child(window, QPushButton, "editPredictionDetailsButton")
    invalid = _required_child(window, QPushButton, "markInvalidButton")
    delete = _required_child(window, QPushButton, "deletePredictionButton")
    journal = _required_child(window, QPushButton, "addJournalEntryButton")
    revise = _required_child(window, QPushButton, "reviseForecastButton")
    review = _required_child(window, QPushButton, "reviewForecastButton")
    resolve = _required_child(window, QPushButton, "resolvePredictionButton")
    assert edit.property(ACTION_ROLE_PROPERTY) == ActionRole.SECONDARY.value
    assert invalid.property(ACTION_ROLE_PROPERTY) == ActionRole.SECONDARY.value
    assert action_grid.getItemPosition(action_grid.indexOf(journal)) == (0, 1, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(revise)) == (0, 2, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(review)) == (0, 3, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(edit)) == (1, 1, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(resolve)) == (1, 2, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(invalid)) == (1, 3, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(delete)) == (2, 2, 1, 1)
    action_buttons = (
        revise,
        journal,
        review,
        edit,
        resolve,
        invalid,
        delete,
    )
    assert all(button.width() <= 210 for button in action_buttons)
    assert len({button.width() for button in action_buttons}) == 1


def test_m42_dialogs_share_heading_context_error_and_action_roles(
    qtbot: QtBot,
) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(7, "Will this dialog stay clear?", 60))
    )
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    title = _required_child(dialog, QLabel, "reviseForecastTitle")
    context = _required_child(dialog, QLabel, "reviseCurrentProbability")
    error = _required_child(dialog, QLabel, "reviseForecastError")
    save = _required_child(dialog, QPushButton, "saveForecastRevisionButton")
    cancel = _required_child(dialog, QPushButton, "cancelForecastRevisionButton")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.SECTION_TITLE.value
    assert context.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.SELECTED.value
    assert context.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert save.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert cancel.property(ACTION_ROLE_PROPERTY) == ActionRole.SECONDARY.value
    assert dialog.focusWidget() is _required_child(
        dialog,
        QSpinBox,
        "revisionProbabilityInput",
    )


def test_numeric_creation_switches_the_forecast_form_and_displays_complete_detail(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    prediction_type = _required_child(window, QComboBox, "predictionTypeInput")
    binary_fields = _required_child(window, QWidget, "binaryForecastFields")
    numeric_fields = _required_child(window, QWidget, "numericForecastFields")

    assert prediction_type.currentData() == PredictionType.BINARY.value
    assert not binary_fields.isHidden()
    assert numeric_fields.isHidden()
    prediction_type.setCurrentIndex(
        prediction_type.findData(PredictionType.NUMERIC.value)
    )
    assert binary_fields.isHidden()
    assert not numeric_fields.isHidden()

    _required_child(window, QLineEdit, "questionInput").setText(
        "How many days until the signed offer receives a response?"
    )
    _required_child(window, QLineEdit, "numericUnitInput").setText("days")
    _required_child(window, QSpinBox, "numericPrecisionInput").setValue(1)
    _required_child(window, QLineEdit, "numericLowerBoundInput").setText("3.0")
    _required_child(window, QLineEdit, "numericMedianEstimateInput").setText("7.5")
    _required_child(window, QLineEdit, "numericUpperBoundInput").setText("21.0")
    confidence = _required_child(window, QSpinBox, "numericConfidenceInput")
    assert confidence.minimum() == 1
    assert confidence.maximum() == 99
    qtbot.mouseClick(
        _required_child(window, QPushButton, "numericConfidenceShortcut90"),
        Qt.MouseButton.LeftButton,
    )

    _required_child(window, QGroupBox, "newPredictionMoreDetailsGroup").setChecked(True)
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "The normal response window is two weeks."
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "The offer was sent this morning."
    )
    _required_child(
        window,
        QPlainTextEdit,
        "initialResolutionCriteriaInput",
    ).setPlainText("Count complete calendar days before the first reply.")
    _required_child(window, QCheckBox, "initialForecastDeadlineToggle").setChecked(True)
    _required_child(window, QDateEdit, "initialForecastDeadlineInput").setDate(
        QDate(2026, 8, 31)
    )
    _required_child(window, QCheckBox, "initialExpectedResolutionToggle").setChecked(
        True
    )
    _required_child(window, QDateEdit, "initialExpectedResolutionInput").setDate(
        QDate(2026, 9, 20)
    )
    _required_child(window, QLineEdit, "initialTagsInput").setText("offer, timing")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.numeric_create_calls == [
        CreateNumericPredictionCall(
            question="How many days until the signed offer receives a response?",
            unit="days",
            decimal_places=1,
            lower_bound="3.0",
            median_estimate="7.5",
            upper_bound="21.0",
            confidence_percent=90,
            rationale="The normal response window is two weeks.",
            background="The offer was sent this morning.",
            resolution_criteria="Count complete calendar days before the first reply.",
            forecast_deadline=date(2026, 8, 31),
            expected_resolution=date(2026, 9, 20),
            tags=("offer", "timing"),
        )
    ]
    assert operations.create_calls == []
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        "How many days until the signed offer receives a response?"
    )
    assert _required_child(window, QLabel, "numericCurrentInterval").text() == (
        "90% interval: 3.0 to 21.0 days"
    )
    assert _required_child(window, QLabel, "numericCurrentMedian").text() == (
        "Median estimate: 7.5 days"
    )
    numeric_actions = _required_child(
        window,
        QWidget,
        "numericPredictionActions",
    ).layout()
    assert isinstance(numeric_actions, QGridLayout)
    numeric_delete = _required_child(
        window,
        QPushButton,
        "deleteNumericPredictionButton",
    )
    assert numeric_actions.getItemPosition(numeric_actions.indexOf(numeric_delete)) == (
        2,
        2,
        1,
        1,
    )
    assert window.findChild(QLabel, "numericPredictionLifecycleHeading") is None
    assert (
        _required_child(
            window,
            QPushButton,
            "markNumericPredictionInvalidButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.SECONDARY.value
    )
    assert _required_child(window, QLabel, "numericPredictionStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "numericForecastDeadlineValue").text() == (
        "Aug 31, 2026"
    )
    assert _required_child(window, QLabel, "numericExpectedResolutionValue").text() == (
        "Sep 20, 2026"
    )
    assert _required_child(window, QLabel, "numericInitialRationaleValue").text() == (
        "The normal response window is two weeks."
    )
    assert (
        "later v0.2 milestones"
        in _required_child(
            window,
            QLabel,
            "numericPredictionNextSteps",
        ).text()
    )

    window.navigate_to("New Prediction")
    assert prediction_type.currentData() == PredictionType.BINARY.value
    assert _required_child(window, QLineEdit, "numericUnitInput").text() == ""
    assert _required_child(window, QSpinBox, "numericConfidenceInput").value() == 80


def test_numeric_creation_failure_keeps_the_form_values_for_correction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.numeric_create_error = ApplicationError(
        "Numeric forecasts require lower bound <= median <= upper bound."
    )
    window.navigate_to("New Prediction")
    prediction_type = _required_child(window, QComboBox, "predictionTypeInput")
    prediction_type.setCurrentIndex(
        prediction_type.findData(PredictionType.NUMERIC.value)
    )
    _required_child(window, QLineEdit, "questionInput").setText("How many days?")
    _required_child(window, QLineEdit, "numericUnitInput").setText("days")
    _required_child(window, QLineEdit, "numericLowerBoundInput").setText("8")
    _required_child(window, QLineEdit, "numericMedianEstimateInput").setText("3")
    _required_child(window, QLineEdit, "numericUpperBoundInput").setText("10")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.current_screen_name == "New Prediction"
    assert _required_child(window, QLabel, "predictionFormError").text() == (
        "Numeric forecasts require lower bound <= median <= upper bound."
    )
    assert (
        _required_child(window, QLineEdit, "numericMedianEstimateInput").text() == "3"
    )
    assert _required_child(window, QLineEdit, "numericUnitInput").text() == "days"


def test_prediction_detail_prefers_the_newer_numeric_prediction_when_times_tie(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Binary first?", 60))
    numeric = operations.create_numeric_prediction(
        "Numeric later?",
        "days",
        0,
        1,
        2,
        3,
        80,
    )
    operations.numeric_latest = replace(
        numeric,
        created_at=operations.latest.created_at,
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        "Numeric later?"
    )


def test_more_details_date_controls_are_visually_unset_until_enabled(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline = _required_child(
        window,
        QDateEdit,
        "initialForecastDeadlineInput",
    )

    assert not deadline_toggle.isChecked()
    assert deadline.isHidden()
    qtbot.mouseClick(deadline_toggle, Qt.MouseButton.LeftButton)
    assert deadline.isVisible()
    assert deadline.date() == QDate.currentDate()


def test_complete_creation_submits_all_optional_details_once_and_resets(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will all initial details persist?"
    )
    _required_child(window, QSpinBox, "probabilityInput").setValue(73)
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Initial evidence"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Relevant background"
    )
    _required_child(
        window,
        QPlainTextEdit,
        "initialResolutionCriteriaInput",
    ).setPlainText("A published result counts.")
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialForecastDeadlineInput").setDate(
        QDate(2026, 9, 1)
    )
    expected_toggle = _required_child(
        window,
        QCheckBox,
        "initialExpectedResolutionToggle",
    )
    expected_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialExpectedResolutionInput").setDate(
        QDate(2026, 9, 15)
    )
    _required_child(window, QLineEdit, "initialTagsInput").setText(" release, desktop ")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will all initial details persist?",
            probability_percent=73,
            rationale="Initial evidence",
            background="Relevant background",
            resolution_criteria="A published result counts.",
            forecast_deadline=date(2026, 9, 1),
            expected_resolution=date(2026, 9, 15),
            tags=("release", "desktop"),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert (
        _required_child(window, QLabel, "forecastRevisionRationale1").text()
        == "Initial evidence"
    )

    window.navigate_to("New Prediction")
    assert _required_child(window, QLineEdit, "questionInput").text() == ""
    assert _required_child(window, QSpinBox, "probabilityInput").value() == 50
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == ""
    )
    assert not deadline_toggle.isChecked()
    assert _required_child(
        window,
        QDateEdit,
        "initialForecastDeadlineInput",
    ).isHidden()
    assert not expected_toggle.isChecked()
    assert _required_child(window, QLineEdit, "initialTagsInput").text() == ""
    assert not _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).isChecked()


def test_collapsing_more_details_preserves_entered_values_for_creation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will collapsed details remain part of the prediction?"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Keep this context"
    )
    more_details.setChecked(False)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls[0].background == "Keep this context"


def test_creation_failure_keeps_optional_details_for_correction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError(
        "Forecast Deadline cannot be before today."
    )
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will this invalid deadline remain editable?"
    )
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Keep me"
    )
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialForecastDeadlineInput").setDate(
        QDate(2020, 1, 1)
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.current_screen_name == "New Prediction"
    assert more_details.isChecked()
    assert deadline_toggle.isChecked()
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == "Keep me"
    )
    error = _required_child(window, QLabel, "predictionFormError")
    assert "before today" in error.text()
    assert not error.isHidden()


def test_probability_shortcuts_are_exactly_ten_through_ninety(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    shortcuts = _required_child(window, QWidget, "probabilityShortcuts")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    buttons = shortcuts.findChildren(QPushButton)

    assert tuple(button.text() for button in buttons) == tuple(
        str(value) for value in range(10, 100, 10)
    )
    for expected, button in zip(range(10, 100, 10), buttons, strict=True):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert probability.value() == expected


@pytest.mark.parametrize("endpoint", [0, 100])
def test_probability_endpoint_note_only_appears_for_absolute_certainty(
    window: MainWindow,
    endpoint: int,
) -> None:
    probability = _required_child(window, QSpinBox, "probabilityInput")
    note = _required_child(window, QLabel, "probabilityEndpointNote")

    for ordinary_probability in (1, 50, 99):
        probability.setValue(ordinary_probability)
        assert note.isHidden()

    probability.setValue(endpoint)
    assert not note.isHidden()
    assert "absolute certainty" in note.text()


def test_missing_question_is_shown_inline_without_calling_operation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert not error.isHidden()
    assert "Enter a question" in error.text()
    assert operations.create_calls == []
    assert window.current_screen_name == "New Prediction"


def test_expected_application_failure_is_shown_inline(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError("That prediction could not be saved.")
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")
    question.setText("Will this remain on the form?")

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert error.text() == "That prediction could not be saved."
    assert not error.isHidden()
    assert question.text() == "Will this remain on the form?"
    assert window.current_screen_name == "New Prediction"


@pytest.mark.parametrize("probability_percent", [0, 50, 100])
def test_successful_creation_accepts_probability_bounds_and_opens_detail(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
    probability_percent: int,
) -> None:
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    question.setText("  Will the UI preserve history?  ")
    probability.setValue(probability_percent)

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will the UI preserve history?",
            probability_percent=probability_percent,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Will the UI preserve history?"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{probability_percent}%"
    )
    assert question.text() == ""
    assert probability.value() == 50


def test_enter_submits_new_prediction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    question.setText("Will Enter submit this prediction?")

    qtbot.keyPress(question, Qt.Key.Key_Return)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will Enter submit this prediction?",
            probability_percent=50,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"


def test_prediction_detail_loads_latest_prediction_at_construction(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will this survive a restart?",
        probability_percent=60,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "60%"
    )
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden() is (
        False
    )
    assert _required_child(window, QLabel, "predictionDetailEmptyState").isHidden()


def test_prediction_detail_renders_locked_status(qtbot: QtBot) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Has this prediction passed its forecast deadline?",
        probability_percent=60,
        status=PredictionStatus.LOCKED,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"


def test_returning_to_prediction_detail_refreshes_external_changes(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Original question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.get_calls.clear()
    operations.latest = replace(
        original,
        question="Externally refreshed question",
        probability_percent=45,
        status=PredictionStatus.LOCKED,
        background="Fresh context",
        metadata_version=2,
        current_revision_id=2,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=2,
            prediction_id=42,
            probability_percent=45,
            sequence=2,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
        )
    )
    operations.revision_read_calls.clear()

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert operations.get_calls == [42]
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally refreshed question"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "Fresh context"
    )
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 2
    assert [sample.probability_percent for sample in chart.samples] == [60, 45]
    assert operations.revision_read_calls == [42]


def test_prediction_detail_refresh_failure_retains_last_visible_data(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Still-visible question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.latest = None

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Still-visible question"
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert not error.isHidden()


def test_prediction_detail_shows_present_metadata_and_hides_missing_sections(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will the release ship?",
        probability_percent=65,
        background="The implementation is nearly complete.",
        resolution_criteria="Yes if the installer is published.",
        forecast_deadline=date(2026, 9, 1),
        expected_resolution=None,
        tags=("release", "desktop"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#release  #desktop"
    )
    deadline = _required_child(window, QLabel, "predictionDetailForecastDeadline")
    assert "2026" in deadline.text()
    assert not _required_child(
        window,
        QWidget,
        "predictionDetailForecastDeadlineRow",
    ).isHidden()
    assert _required_child(
        window,
        QWidget,
        "predictionDetailExpectedResolutionRow",
    ).isHidden()
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        latest.background
    )
    assert (
        _required_child(
            window,
            QLabel,
            "predictionDetailResolutionCriteria",
        ).text()
        == latest.resolution_criteria
    )


def test_prediction_detail_hides_all_empty_optional_metadata(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(42, "Will the view stay calm?", 65))
    )
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailTags",
        "predictionDetailForecastDeadlineRow",
        "predictionDetailExpectedResolutionRow",
        "predictionDetailBackgroundSection",
        "predictionDetailResolutionCriteriaSection",
        "definitionHistoryGroup",
    ):
        assert _required_child(window, QWidget, object_name).isHidden()


def test_prediction_detail_enables_open_lifecycle_actions(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(1, "Will this stay in scope?", 50)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    revise = _required_child(window, QPushButton, "reviseForecastButton")
    assert revise.isEnabled()
    assert "preserving" in revise.toolTip()

    journal = _required_child(window, QPushButton, "addJournalEntryButton")
    assert journal.isEnabled()
    assert "without changing" in journal.toolTip()

    for object_name in (
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        button = _required_child(window, QPushButton, object_name)
        assert button.isEnabled()
        assert button.toolTip()
    assert _required_child(window, QLabel, "timelinePlaceholder").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    assert not chart.isHidden()
    assert _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    ).isHidden()


def test_probability_history_empty_and_load_failure_states_are_honest(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing chart read be described honestly?", 60)
    )
    operations.revisions.clear()
    window = MainWindow(operations)
    qtbot.addWidget(window)

    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 0
    assert chart.samples == ()
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "No forecast revisions" in placeholder.text()

    operations.revision_read_error = ApplicationError("Revision read failed.")
    window.navigate_to("Prediction Detail")

    assert chart.revision_count == 0
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "could not be loaded" in placeholder.text()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "Revision read failed" in error.text()
    assert not error.isHidden()


def test_probability_history_refresh_failure_retains_matching_loaded_chart(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a transient read preserve visible history?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    retained_samples = chart.samples

    operations.revision_read_error = ApplicationError("Temporary read failure.")
    window.navigate_to("Prediction Detail")

    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 1
    assert chart.samples == retained_samples
    assert not chart.isHidden()
    assert not placeholder.isHidden()
    assert "last loaded chart remains visible" in placeholder.text()
    assert (
        "Temporary read failure"
        in _required_child(
            window,
            QLabel,
            "predictionDetailError",
        ).text()
    )


def test_probability_history_accessibility_reports_timeline_read_failure(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the nonvisual equivalent stay truthful?", 60)
    )
    operations.timeline_error = ApplicationError("Timeline read failed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )

    assert chart.revision_count == 1
    assert "currently unavailable" in chart.accessibleDescription()

    operations.timeline_error = None
    window.navigate_to("Prediction Detail")

    assert "listed in the Timeline" in chart.accessibleDescription()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.LOCKED, PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_prediction_detail_disables_revision_for_ineligible_lifecycle(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can this forecast be revised?", 60, status=status)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    button = _required_child(window, QPushButton, "reviseForecastButton")
    assert not button.isEnabled()
    assert status.value in button.toolTip()


def test_opening_and_cancelling_revision_dialog_appends_nothing(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Will opening the editor preserve history?",
            60,
            current_revision_id=11,
            current_revision_sequence=3,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "60%"
    assert _required_child(dialog, QSpinBox, "revisionProbabilityInput").value() == 60
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == []
    assert len(operations.revisions) == 1


def test_opening_revision_refreshes_probability_and_concurrency_tokens(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will the revision editor use fresh state?",
        60,
        metadata_version=1,
        current_revision_id=11,
        current_revision_sequence=1,
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        probability_percent=70,
        metadata_version=2,
        current_revision_id=12,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            12,
            7,
            70,
            2,
            datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_revision_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "70%"
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(45)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=45,
            rationale="",
            expected_revision_id=12,
            expected_metadata_version=2,
        )
    ]


def test_revision_refresh_that_finds_locked_state_opens_no_dialog(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Will this lock before the dialog opens?", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    operations.latest = replace(original, status=PredictionStatus.LOCKED)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.findChild(QDialog, "reviseForecastDialog") is None
    assert operations.revise_calls == []
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "locked" in error.text()
    assert not error.isHidden()


def test_same_probability_revision_error_stays_inline_and_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will an unchanged forecast be rejected?", 60)
    )
    operations.revise_error = ApplicationError(
        "The new forecast matches the current 60%. Add a journal entry instead."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "reviseForecastError")
    assert "matches the current" in error.text()
    assert not error.isHidden()
    assert len(operations.revisions) == 1


def test_revision_rationale_helper_explains_when_to_use_journal(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will revision guidance clarify the Journal?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dialog = _open_revision_dialog(qtbot, window)

    helper = _required_child(dialog, QLabel, "revisionRationaleHelper")
    assert helper.text() == (
        "This explanation stays attached to the new forecast. To record a thought "
        "without changing probability, add a Journal entry."
    )
    assert helper.textFormat() is Qt.TextFormat.PlainText
    assert helper.wordWrap()
    rationale = _required_child(dialog, QPlainTextEdit, "revisionRationaleInput")
    assert rationale.accessibleDescription() == helper.text()
    layout = dialog.layout()
    assert layout.indexOf(rationale) < layout.indexOf(helper)
    assert layout.indexOf(helper) < layout.indexOf(
        _required_child(dialog, QLabel, "reviseForecastError")
    )


@pytest.mark.parametrize("new_probability", [0, 37, 100])
def test_revision_appends_with_tokens_and_refreshes_forecast_history(
    qtbot: QtBot,
    new_probability: int,
) -> None:
    original = FakePrediction(
        7,
        "Will a revision append honestly?",
        60,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
        current_rationale="Initial <b>reason</b>",
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_revision_dialog(qtbot, window)
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(
        new_probability
    )
    _required_child(dialog, QPlainTextEdit, "revisionRationaleInput").setPlainText(
        "New <i>evidence</i>"
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=new_probability,
            rationale="New <i>evidence</i>",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{new_probability}%"
    )
    assert (
        _required_child(window, QLabel, "forecastRevisionProbability12").text()
        == f"FORECAST  60% \N{RIGHTWARDS ARROW} {new_probability}%"
    )
    rationale = _required_child(window, QLabel, "forecastRevisionRationale12")
    assert rationale.text() == "New <i>evidence</i>"
    assert rationale.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 2
    assert [sample.sequence for sample in chart.samples] == [3, 4]
    assert [sample.probability_percent for sample in chart.samples] == [
        60,
        new_probability,
    ]


def test_forecast_history_uses_previous_revision_for_nonconsecutive_return(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will the forecast return to its starting value?",
        60,
        current_revision_id=3,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    operations.revisions = [
        FakeForecastRevision(1, 7, 60, 1, datetime(2026, 8, 10, tzinfo=UTC)),
        FakeForecastRevision(2, 7, 40, 2, datetime(2026, 8, 11, tzinfo=UTC)),
        FakeForecastRevision(3, 7, 60, 3, datetime(2026, 8, 12, tzinfo=UTC)),
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert (
        _required_child(
            window,
            QLabel,
            "forecastRevisionProbability3",
        ).text()
        == "FORECAST  40% \N{RIGHTWARDS ARROW} 60%"
    )


def test_add_journal_entry_refreshes_context_and_cancel_has_no_effect(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will a cancelled Journal form leave history alone?",
        60,
        metadata_version=1,
        current_revision_id=11,
        current_revision_sequence=1,
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        probability_percent=70,
        metadata_version=2,
        current_revision_id=12,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=12,
            prediction_id=7,
            probability_percent=70,
            sequence=2,
            created_at=datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_journal_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "journalForecastAtTime").text() == "70%"
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPlainTextEdit,
        "journalEntryBodyInput",
    )
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.journal_calls == []
    assert operations.journal_entries == []


def test_blank_journal_entry_stays_inline_without_calling_operation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will blank Journal entries be rejected?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("  \n ")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "Write a journal entry" in error.text()
    assert not error.isHidden()
    assert operations.journal_calls == []


def test_journal_expected_error_keeps_multiline_body_and_dialog_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will stale Journal context be rejected?", 60)
    )
    operations.journal_error = ApplicationError(
        "This prediction changed before the Journal entry could be saved."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("First line\nSecond line")

    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert dialog.isVisible()
    assert body.toPlainText() == "First line\nSecond line"
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert len(operations.journal_calls) == 1


def test_enter_adds_newline_and_ctrl_enter_saves_journal_with_tokens(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will keyboard entry remain comfortable?",
        65,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")

    qtbot.keyClicks(body, "Evidence one")
    qtbot.keyPress(body, Qt.Key.Key_Return)
    qtbot.keyClicks(body, "Evidence two")
    assert body.toPlainText() == "Evidence one\nEvidence two"
    qtbot.keyPress(body, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPushButton,
        "saveJournalEntryButton",
    )
    body.setFocus()
    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert operations.journal_calls == [
        AddJournalEntryCall(
            prediction_id=7,
            body="Evidence one\nEvidence two",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert not dialog.isVisible()
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "65%"
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody1").text()
        == "Evidence one\nEvidence two"
    )
    assert (
        _required_child(window, QLabel, "journalEntryForecastAtTime1").text()
        == "Forecast at the time: 65%"
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


@pytest.mark.parametrize("status", [PredictionStatus.OPEN, PredictionStatus.LOCKED])
def test_journal_creation_is_enabled_for_nonterminal_statuses(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(7, "Can this accept a Journal entry?", 60, status=status)
        )
    )
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_terminal_predictions_disable_new_journals_but_allow_corrections(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can terminal history be corrected?", 60, status=status)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Original Journal text",
            original_body="Original Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    add_button = _required_child(window, QPushButton, "addJournalEntryButton")
    assert not add_button.isEnabled()
    correct_button = _required_child(
        window,
        QPushButton,
        "correctJournalEntryButton4",
    )
    assert correct_button.isEnabled()


def test_unified_timeline_renders_forecasts_and_journals_as_plain_text(
    qtbot: QtBot,
) -> None:
    markup = "<b>Literal Journal evidence</b>"
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the timeline be historically honest?", 40)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=8,
            prediction_id=7,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
            body=markup,
            original_body=markup,
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=40,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "timelineHeading").text() == "TIMELINE"
    body = _required_child(window, QLabel, "journalEntryBody8")
    assert body.text() == markup
    assert body.textFormat() is Qt.TextFormat.PlainText
    timestamp = _required_child(window, QLabel, "journalEntryTimestamp8")
    assert timestamp.text() == (
        datetime(2026, 8, 13, 19, 30, tzinfo=UTC)
        .astimezone()
        .strftime("%b %d, %Y at %H:%M %Z")
        .strip()
    )


def test_correction_cancel_and_expected_error_preserve_current_body(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction failures remain safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Latest text",
            original_body="Original text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=3,
            corrections=(
                FakeJournalCorrection(
                    3,
                    "Latest text",
                    datetime(2026, 8, 13, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "Latest text"
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    assert operations.correction_calls == []

    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("Corrected text")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )
    assert dialog.isVisible()
    assert body.toPlainText() == "Corrected text"
    assert (
        "changed before"
        in _required_child(
            dialog,
            QLabel,
            "correctJournalEntryError",
        ).text()
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


def test_correction_dialog_refreshes_external_edits_and_recovers_after_stale_save(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction retries use the latest text?", 60)
    )
    original = FakeJournalTimelineEvent(
        entry_id=4,
        prediction_id=7,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        body="Original text",
        original_body="Original text",
        forecast_revision_id=1,
        forecast_revision_sequence=1,
        forecast_probability_percent=60,
    )
    operations.journal_entries = [original]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    first_external_correction = FakeJournalCorrection(
        1,
        "First external correction",
        datetime(2026, 8, 13, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        original,
        body=first_external_correction.body,
        current_correction_id=first_external_correction.correction_id,
        corrections=(first_external_correction,),
    )

    dialog = _click_correction_button(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "First external correction"

    second_external_correction = FakeJournalCorrection(
        2,
        "Second external correction",
        datetime(2026, 8, 14, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        operations.journal_entries[0],
        body=second_external_correction.body,
        current_correction_id=second_external_correction.correction_id,
        corrections=(first_external_correction, second_external_correction),
    )
    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    body.setPlainText("Correction from the stale dialog")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert operations.correction_calls[-1].expected_correction_id == 1
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    operations.correction_error = None

    retry_dialog = _click_correction_button(qtbot, window, entry_id=4)
    retry_body = _required_child(
        retry_dialog,
        QPlainTextEdit,
        "correctJournalEntryBodyInput",
    )
    assert retry_body.toPlainText() == "Second external correction"
    retry_body.setPlainText("Recovered correction")
    qtbot.mouseClick(
        _required_child(retry_dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls[-1] == CorrectJournalEntryCall(
        prediction_id=7,
        entry_id=4,
        body="Recovered correction",
        expected_correction_id=2,
    )


def test_correction_refresh_error_is_visible_and_does_not_open_dialog(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a failed refresh stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.timeline_error = ApplicationError("The timeline is temporarily busy.")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert "temporarily busy" in error.text()
    assert not error.isHidden()


def test_missing_journal_during_correction_refresh_is_reported_safely(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing entry stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.journal_entries.clear()

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be found" in error.text()
    assert not error.isHidden()


def test_correction_displays_edited_marker_and_collapsed_plain_text_history(
    qtbot: QtBot,
) -> None:
    original_time = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(
        FakePrediction(7, "Will corrections retain every prior body?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=original_time,
            body="First corrected body",
            original_body="<b>Original body</b>",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=1,
            corrections=(
                FakeJournalCorrection(
                    correction_id=1,
                    body="First corrected body",
                    corrected_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("<i>Corrected body</i>")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls == [
        CorrectJournalEntryCall(
            prediction_id=7,
            entry_id=4,
            body="<i>Corrected body</i>",
            expected_correction_id=1,
        )
    ]
    assert (
        _required_child(
            window,
            QLabel,
            "journalEntryEdited4",
        )
        .text()
        .startswith("Edited ")
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody4").text()
        == "<i>Corrected body</i>"
    )
    history = _required_child(window, QGroupBox, "journalEntryEditHistory4")
    content = _required_child(window, QWidget, "journalEntryEditHistoryContent4")
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    original = _required_child(window, QLabel, "journalEntryOriginalBody4")
    correction = _required_child(window, QLabel, "journalCorrectionBody1")
    assert original.text() == "<b>Original body</b>"
    assert correction.text() == "First corrected body"
    assert original.textFormat() is Qt.TextFormat.PlainText
    assert correction.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 1
    assert (
        _required_child(window, QLabel, "journalCorrectionHeading1")
        .text()
        .startswith("Correction 1 ·")
    )


def test_edit_details_dialog_prefills_values_and_optional_date_controls(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=7,
        question="Will this dialog be prefilled?",
        probability_percent=55,
        background="Context",
        resolution_criteria="A public release counts.",
        forecast_deadline=date(2026, 9, 2),
        tags=("ui", "m3"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        latest.question
    )
    assert _required_child(
        dialog, QPlainTextEdit, "editBackgroundInput"
    ).toPlainText() == ("Context")
    assert _required_child(dialog, QLineEdit, "editTagsInput").text() == "ui, m3"
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_input = _required_child(
        dialog,
        QDateEdit,
        "editForecastDeadlineInput",
    )
    assert deadline_toggle.isChecked()
    assert deadline_input.isEnabled()
    assert deadline_input.isVisible()
    assert deadline_input.date() == QDate(2026, 9, 2)
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    assert not expected_toggle.isChecked()
    assert not expected_input.isEnabled()
    assert expected_input.isHidden()
    assert deadline_input.minimumDate() == QDate(1752, 9, 14)
    assert deadline_input.maximumDate() == QDate(9999, 12, 31)


def test_unset_optional_date_is_revealed_only_when_enabled(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(7, "Will dates stay optional?", 55))
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_input = _required_child(
        dialog,
        QDateEdit,
        "editForecastDeadlineInput",
    )

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert deadline_toggle.isChecked()
    assert deadline_input.isEnabled()
    assert deadline_input.isVisible()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()


def test_edit_details_dialog_preserves_earliest_supported_date(
    qtbot: QtBot,
) -> None:
    earliest = date(1752, 9, 14)
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(
                7, "Earliest supported deadline?", 55, forecast_deadline=earliest
            )
        )
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    deadline = _required_child(dialog, QDateEdit, "editForecastDeadlineInput")
    assert deadline.date() == QDate(1752, 9, 14)
    assert deadline.isVisible()


def test_user_definition_text_is_always_rendered_as_plain_text(qtbot: QtBot) -> None:
    markup = "<b>Literal forecast wording</b>"
    operations = FakePredictionOperations(
        FakePrediction(
            prediction_id=7,
            question=markup,
            probability_percent=55,
            background="<i>Literal background</i>",
            resolution_criteria="<a href='x'>Literal criteria</a>",
            tags=("<u>tag</u>",),
        )
    )
    operations.definition_changes = (
        DefinitionChange(
            change_id=4,
            prediction_id=7,
            changed_at=datetime(2026, 8, 12, 19, 30, tzinfo=UTC),
            changed_fields=("question",),
            old_question="<em>Old literal</em>",
            new_question=markup,
            old_resolution_criteria=None,
            new_resolution_criteria=None,
            old_forecast_deadline=None,
            new_forecast_deadline=None,
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailQuestion",
        "predictionDetailTags",
        "predictionDetailBackground",
        "predictionDetailResolutionCriteria",
        "definitionChange4Question",
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == markup
    assert (
        "<em>Old literal</em>"
        in _required_child(
            window,
            QLabel,
            "definitionChange4Question",
        ).text()
    )


def test_open_edit_details_refreshes_externally_changed_prediction(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Original question", 55)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        question="Externally changed question",
        background="Newer context",
        metadata_version=2,
    )

    dialog = _open_edit_dialog(qtbot, window)

    assert operations.get_calls == [7, 7]
    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        "Externally changed question"
    )
    assert (
        _required_child(
            dialog,
            QPlainTextEdit,
            "editBackgroundInput",
        ).toPlainText()
        == "Newer context"
    )
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally changed question"
    )


def test_cancel_edit_details_does_not_call_update(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Unsaved edit")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == []
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_repeated_cancel_deletes_finished_edit_dialogs(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for _attempt in range(3):
        dialog = _open_edit_dialog(qtbot, window)
        qtbot.mouseClick(
            _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
            Qt.MouseButton.LeftButton,
        )
        qtbot.waitUntil(lambda current=dialog: not current.isVisible())
        qtbot.waitUntil(
            lambda: (
                not window.findChildren(
                    QDialog,
                    "editPredictionDetailsDialog",
                )
            )
        )

    remaining = [
        dialog
        for dialog in window.findChildren(QDialog)
        if dialog.objectName() == "editPredictionDetailsDialog"
    ]
    assert remaining == []
    assert operations.update_calls == []


def test_noop_edit_closes_without_mutation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_unprotected_edit_saves_without_warning_and_refreshes_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "editBackgroundInput").setPlainText(
        "New background"
    )
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    expected_toggle.setChecked(True)
    expected_input.setDate(QDate(2026, 10, 20))
    _required_child(dialog, QLineEdit, "editTagsInput").setText("launch, ui")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == [
        MetadataUpdateCall(
            prediction_id=7,
            question="Original question",
            background="New background",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=date(2026, 10, 20),
            tags=("launch", "ui"),
            expected_metadata_version=1,
            confirm_meaning_change=False,
        )
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "New background"
    )
    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#launch  #ui"
    )
    assert (
        "2026"
        in _required_child(
            window,
            QLabel,
            "predictionDetailExpectedResolution",
        ).text()
    )


def test_expected_resolution_only_saves_without_warning(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    qtbot.mouseClick(expected_toggle, Qt.MouseButton.LeftButton)
    expected_input.setDate(QDate(2026, 10, 20))

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.update_calls[0].expected_resolution == date(2026, 10, 20)
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 1
    assert not dialog.isVisible()


def test_expected_edit_failure_is_shown_inline(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.update_error = ApplicationError("Those details could not be saved.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    error = _required_child(dialog, QLabel, "editDetailsError")
    assert error.text() == "Those details could not be saved."
    assert not error.isHidden()
    assert dialog.isVisible()
    assert operations.mutation_count == 0


def test_deadline_only_warning_explains_locking_without_proposition_guidance(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("forecast_deadline",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def decline_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", decline_warning)
    dialog = _open_edit_dialog(qtbot, window)
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    qtbot.mouseClick(deadline_toggle, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.mutation_count == 0
    assert dialog.isVisible()
    assert warnings[0][0] == "Confirm forecast deadline change"
    assert "forecast revisions become locked" in warnings[0][1]
    assert "Definition history" in warnings[0][1]
    assert "what this prediction means" not in warnings[0][1]
    assert "new prediction" not in warnings[0][1]


def test_semantic_change_warning_decline_does_not_retry_or_mutate(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def decline_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", decline_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert dialog.isVisible()
    assert warnings[0][0] == "Confirm definition change"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" not in warnings[0][1]


def test_meaning_change_confirmation_retries_and_refreshes_returned_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question", "forecast_deadline")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def accept_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", accept_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(dialog, QDateEdit, "editForecastDeadlineInput").setDate(
        QDate(2026, 9, 30)
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.confirm_meaning_change for call in operations.update_calls] == [
        False,
        True,
    ]
    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Changed question"
    )
    assert warnings[0][0] == "Confirm definition and deadline changes"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" in warnings[0][1]
    assert "Definition history" in warnings[0][1]
    assert not dialog.isVisible()
    assert operations.definition_change_calls == [7, 7, 7, 7]


def test_stale_confirmation_retry_stays_inline_without_mutating(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    def make_stale(*args, **kwargs) -> QMessageBox.StandardButton:
        assert operations.latest is not None
        operations.latest = replace(
            operations.latest,
            background="Intervening edit",
            metadata_version=2,
        )
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", make_stale)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert operations.latest.background == "Intervening edit"
    error = _required_child(dialog, QLabel, "editDetailsError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert dialog.isVisible()


def test_definition_history_is_collapsed_and_shows_snapshot_in_local_time(
    qtbot: QtBot,
) -> None:
    changed_at = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(FakePrediction(7, "Changed question", 55))
    operations.definition_changes = (
        DefinitionChange(
            change_id=3,
            prediction_id=7,
            changed_at=changed_at,
            changed_fields=(
                "question",
                "resolution_criteria",
                "forecast_deadline",
            ),
            old_question="Original question",
            new_question="Changed question",
            old_resolution_criteria=None,
            new_resolution_criteria="A public release counts.",
            old_forecast_deadline=None,
            new_forecast_deadline=date(2026, 9, 30),
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    history = _required_child(window, QGroupBox, "definitionHistoryGroup")
    content = _required_child(window, QWidget, "definitionHistoryContent")
    assert not history.isHidden()
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    expected_timestamp = (
        changed_at.astimezone().strftime("%b %d, %Y at %H:%M %Z").strip()
    )
    assert (
        _required_child(
            history,
            QLabel,
            "definitionChangeTimestamp3",
        ).text()
        == expected_timestamp
    )
    assert (
        "Original question"
        in _required_child(
            history,
            QLabel,
            "definitionChange3Question",
        ).text()
    )
    assert (
        "Not set"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ResolutionCriteria",
        ).text()
    )
    assert (
        "2026"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ForecastDeadline",
        ).text()
    )


def test_prediction_detail_has_helpful_empty_state(window: MainWindow) -> None:
    window.navigate_to("Prediction Detail")

    empty_state = _required_child(window, QLabel, "predictionDetailEmptyState")
    assert not empty_state.isHidden()
    assert "Create one" in empty_state.text()
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 0
    assert chart.isHidden()


def test_resolve_dialog_is_side_effect_free_until_an_outcome_is_saved(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)

    explanation = _required_child(dialog, QLabel, "resolvePredictionExplanation")
    save = _required_child(dialog, QPushButton, "confirmResolvePredictionButton")
    assert "cannot be reopened" in explanation.text()
    assert explanation.textFormat() is Qt.TextFormat.PlainText
    assert not save.isEnabled()
    assert operations.resolve_calls == []

    dialog.reject()
    assert operations.resolve_calls == []


def test_resolve_yes_saves_reviewed_context_and_renders_terminal_facts(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Will it resolve?",
        35,
        current_revision_id=9,
        current_revision_sequence=3,
        metadata_version=4,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeYes").setChecked(True)
    _required_child(dialog, QPlainTextEdit, "resolutionNotesInput").setPlainText(
        "Certified result"
    )
    _required_child(dialog, QPlainTextEdit, "resolutionPostmortemInput").setPlainText(
        "I updated too slowly."
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.resolve_calls == [
        ResolvePredictionCall(
            prediction_id=7,
            outcome=BinaryOutcome.YES,
            resolution_notes="Certified result",
            postmortem="I updated too slowly.",
            expected_revision_id=9,
            expected_metadata_version=4,
        )
    ]
    assert (
        _required_child(window, QLabel, "predictionDetailStatus").text() == "RESOLVED"
    )
    section = _required_child(window, QGroupBox, "predictionResolutionSection")
    assert not section.isHidden()
    assert (
        "Yes"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionOutcome",
        ).text()
    )
    assert (
        "35%"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionScoringForecast",
        ).text()
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionResolutionNotes",
        ).text()
        == "Certified result"
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionPostmortem",
        ).text()
        == "I updated too slowly."
    )
    for object_name in (
        "reviseForecastButton",
        "addJournalEntryButton",
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        assert not _required_child(window, QPushButton, object_name).isEnabled()


def test_resolve_expected_error_keeps_dialog_and_inputs_for_retry(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    operations.resolve_error = ApplicationError("The prediction changed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeNo").setChecked(True)
    notes = _required_child(dialog, QPlainTextEdit, "resolutionNotesInput")
    notes.setPlainText("Keep this source")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert notes.toPlainText() == "Keep this source"
    error = _required_child(dialog, QLabel, "resolvePredictionError")
    assert "changed" in error.text()
    assert not error.isHidden()


def test_mark_invalid_saves_optional_reason_and_renders_preserved_state(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Was this cancelled?",
        55,
        current_revision_id=4,
        metadata_version=2,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    explanation = _required_child(dialog, QLabel, "markInvalidExplanation")
    assert "excludes it from scoring" in explanation.text()
    reason = _required_child(dialog, QPlainTextEdit, "invalidationReasonInput")
    reason.setPlainText("The event was cancelled.")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmMarkInvalidButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.invalidate_calls == [
        InvalidatePredictionCall(
            prediction_id=7,
            reason="The event was cancelled.",
            expected_revision_id=4,
            expected_metadata_version=2,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "INVALID"
    section = _required_child(window, QGroupBox, "predictionInvalidationSection")
    assert not section.isHidden()
    assert (
        _required_child(
            section,
            QLabel,
            "predictionInvalidationReason",
        ).text()
        == "The event was cancelled."
    )
    assert not _required_child(
        window, QPushButton, "deletePredictionButton"
    ).isEnabled()


def test_mark_invalid_cancel_writes_nothing(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Keep this Open?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "invalidationReasonInput").setPlainText(
        "Do not save this"
    )

    dialog.reject()

    assert operations.invalidate_calls == []
    assert operations.latest is not None
    assert operations.latest.status is PredictionStatus.OPEN


def test_locked_prediction_can_resolve_or_invalidate_but_not_revise_or_delete(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Locked question?",
            55,
            status=PredictionStatus.LOCKED,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "resolvePredictionButton").isEnabled()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()
    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()


def test_terminal_user_text_is_rendered_as_plain_text(qtbot: QtBot) -> None:
    resolution = FakeResolution(
        resolution_id=1,
        prediction_id=7,
        outcome=BinaryOutcome.NO,
        resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        scoring_revision_id=1,
        scoring_revision_sequence=1,
        scoring_probability_percent=60,
        resolution_notes="<b>literal source</b>",
        postmortem="<i>literal reflection</i>",
    )
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Question?",
            60,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name, expected in (
        ("predictionResolutionNotes", "<b>literal source</b>"),
        ("predictionPostmortem", "<i>literal reflection</i>"),
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
        assert label.text() == expected


def test_delete_cancel_is_side_effect_free_and_confirm_clears_detail(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Duplicate?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    delete = _required_child(window, QPushButton, "deletePredictionButton")

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert operations.delete_calls == []

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        # PySide may return an equal integral button value rather than the
        # identical Python enum object used in this test process.
        lambda *_args: int(QMessageBox.StandardButton.Yes),
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)

    assert operations.delete_calls == [
        DeletePredictionCall(
            prediction_id=7,
            expected_revision_id=1,
            expected_metadata_version=1,
            confirm_permanent_deletion=True,
        )
    ]
    assert not _required_child(
        window,
        QLabel,
        "predictionDetailEmptyState",
    ).isHidden()


def test_meaningful_open_prediction_disables_delete_and_guides_invalid(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Meaningful?", 55, deletion_allowed=False)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()


def _required_child[WidgetType: QWidget](
    parent: QWidget,
    widget_type: type[WidgetType],
    object_name: str,
) -> WidgetType:
    child = parent.findChild(widget_type, object_name)
    assert child is not None
    return child


def _select_tag_rows(table: QTableWidget, *display_names: str) -> None:
    table.clearSelection()
    wanted = set(display_names)
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() in wanted:
            item.setSelected(True)


def _scoring_observation(
    identifier: int,
    probability_percent: int,
    outcome: BinaryOutcome,
    *,
    resolved_at: datetime = datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
    tags: tuple[str, ...] = (),
) -> ScoringObservation:
    return ScoringObservation(
        prediction_id=identifier,
        question=f"Prediction {identifier}",
        resolution_id=identifier,
        resolved_at=resolved_at,
        scoring_revision_id=identifier,
        probability_percent=probability_percent,
        outcome=outcome,
        tags=tags,
    )


def _numeric_scoring_observation(
    identifier: int,
    *,
    lower: int,
    median: int,
    upper: int,
    actual: int,
    confidence: int,
    unit: str,
    tags: tuple[str, ...] = (),
) -> NumericScoringObservation:
    return NumericScoringObservation(
        prediction_id=identifier,
        question=f"Numeric Prediction {identifier}",
        resolution_id=identifier,
        resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        scoring_revision_id=identifier,
        unit=unit,
        lower_bound=FixedPrecisionValue(lower, 0),
        median_estimate=FixedPrecisionValue(median, 0),
        upper_bound=FixedPrecisionValue(upper, 0),
        confidence_percent=confidence,
        actual_value=FixedPrecisionValue(actual, 0),
        tags=tags,
    )


def _open_edit_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "editPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "editPredictionDetailsDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_revision_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "reviseForecastDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_journal_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "addJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "addJournalEntryDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_resolution_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "resolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "resolvePredictionDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_invalidation_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "markInvalidButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "markInvalidDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_correction_dialog(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    return _click_correction_button(qtbot, window, entry_id=entry_id)


def _click_correction_button(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    qtbot.mouseClick(
        _required_child(
            window,
            QPushButton,
            f"correctJournalEntryButton{entry_id}",
        ),
        Qt.MouseButton.LeftButton,
    )
    dialogs = window.findChildren(QDialog, "correctJournalEntryDialog")
    dialog = next(
        (candidate for candidate in reversed(dialogs) if candidate.isVisible()),
        None,
    )
    assert dialog is not None
    return dialog
