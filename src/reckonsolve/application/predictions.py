"""Application operations for Binary and Numeric Predictions."""

import csv
import sqlite3
from dataclasses import replace
from datetime import date, datetime, tzinfo
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile

from reckonsolve.analytics import (
    AnalyticsSnapshot,
    ForecastAnalyticsSnapshot,
    PredictionScorecard,
    binary_scorecard,
    numeric_scorecard,
    summarize_analytics,
    summarize_forecast_analytics,
)
from reckonsolve.clock import Clock, SystemClock, as_utc
from reckonsolve.data.analytics import AnalyticsRepository
from reckonsolve.data.database import Database
from reckonsolve.data.numeric_predictions import (
    NumericForecastRevisionUnchangedError,
    NumericPredictionRepository,
)
from reckonsolve.data.predictions import (
    ForecastContextChangedError,
    ForecastReviewContextChangedError,
    ForecastReviewDisallowedError,
    ForecastRevisionDisallowedError,
    ForecastRevisionUnchangedError,
    JournalContextChangedError,
    JournalCorrectionContextChangedError,
    JournalEntryDisallowedError,
    LifecycleContextChangedError,
    LifecycleTransitionDisallowedError,
    PredictionChangedError,
    PredictionDeletionDisallowedError,
    PredictionRepository,
)
from reckonsolve.data.search import SearchRepository
from reckonsolve.data.search_index import SearchIndexBusyError, SearchIndexError
from reckonsolve.data.settings import SettingsRepository
from reckonsolve.data.terminal_history import (
    OutcomeCorrectionReasonRequiredError,
    PostmortemCompletionDisallowedError,
    TerminalCorrectionContextChangedError,
    TerminalHistoryRepository,
)
from reckonsolve.data.terminal_history import (
    TerminalCorrectionUnchangedError as RepositoryTerminalCorrectionUnchangedError,
)
from reckonsolve.data.transfer import DataTransferRepository
from reckonsolve.domain.attention import (
    AttentionValidationError,
    DashboardPrediction,
    DashboardSnapshot,
    needs_attention,
    ready_to_resolve,
    validate_stale_threshold_days,
)
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveQuery,
    ArchiveQueryValidationError,
    ArchiveSort,
    ArchiveTagMatchMode,
    PredictionBrowserSnapshot,
    classify_archive_items,
    matches_archive_query,
    sort_archive_items,
    validate_archive_query,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    DefinitionChange,
    FixedPrecisionValue,
    ForecastReviewTimelineEvent,
    ForecastRevision,
    InvalidationHistory,
    JournalTimelineEvent,
    NewForecastReview,
    NewForecastRevision,
    NewInvalidation,
    NewInvalidationReasonCorrection,
    NewJournalCorrection,
    NewJournalEntry,
    NewNumericForecastRevision,
    NewNumericPrediction,
    NewNumericResolution,
    NewNumericResolutionCorrection,
    NewPrediction,
    NewResolution,
    NewResolutionCorrection,
    NumericForecastReviewTimelineEvent,
    NumericForecastRevision,
    NumericJournalTimelineEvent,
    NumericPrediction,
    NumericResolutionHistory,
    NumericTimelineEvent,
    PostmortemCompletion,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
    TimelineEvent,
    changed_definition_fields,
    changed_numeric_resolution_fields,
    changed_resolution_fields,
    display_status,
    metadata_would_change,
)
from reckonsolve.domain.search import (
    PredictionSearchResults,
    SearchMatchMode,
    SearchQuery,
    SearchValidationError,
    parse_search_text,
    rank_search_candidates,
)
from reckonsolve.domain.transfer import (
    BackupResult,
    CsvExportResult,
    DataManagementStatus,
)

from .errors import (
    BackupError,
    ConcurrentForecastReviewError,
    ConcurrentForecastUpdateError,
    ConcurrentJournalCorrectionError,
    ConcurrentJournalUpdateError,
    ConcurrentLifecycleUpdateError,
    ConcurrentPredictionUpdateError,
    ConcurrentTerminalCorrectionError,
    CsvExportError,
    ForecastReviewNotAllowedError,
    ForecastRevisionNotAllowedError,
    ForecastUnchangedError,
    JournalEntryNotAllowedError,
    JournalEntryNotFoundError,
    LifecycleTransitionNotAllowedError,
    MeaningChangeConfirmationRequired,
    NumericForecastUnchangedError,
    PostmortemCompletionNotAllowedError,
    PredictionDeletionConfirmationRequired,
    PredictionDeletionNotAllowedError,
    PredictionNotFoundError,
    SearchUnavailableError,
    TerminalCorrectionNotAllowedError,
    TerminalCorrectionUnchangedError,
    ValidationError,
)


class PredictionOperations:
    """Coordinate completed Binary workflows and staged Numeric workflows."""

    def __init__(
        self,
        database: Database,
        clock: Clock | None = None,
        local_timezone: tzinfo | None = None,
    ) -> None:
        self._repository = PredictionRepository(database)
        self._numeric_repository = NumericPredictionRepository(database)
        self._analytics_repository = AnalyticsRepository(database)
        self._settings_repository = SettingsRepository(database)
        self._terminal_history_repository = TerminalHistoryRepository(database)
        self._transfer_repository = DataTransferRepository(database)
        self._search_repository = SearchRepository(database)
        self._database = database
        self._clock = SystemClock() if clock is None else clock
        self._local_timezone = local_timezone

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
    ) -> PredictionDetail:
        """Create complete initial state and sequence-one forecast atomically."""

        try:
            new_prediction = NewPrediction(
                question=question,
                probability_percent=probability_percent,
                rationale=rationale,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error

        created_at = as_utc(self._clock.now())
        current_date = created_at.astimezone(self._local_timezone).date()
        if (
            new_prediction.forecast_deadline is not None
            and new_prediction.forecast_deadline < current_date
        ):
            raise ValidationError(
                "Forecast Deadline cannot be earlier than today when creating a "
                "prediction.",
                field="forecast_deadline",
            )
        return self._with_derived_status(
            self._repository.create_prediction(new_prediction, created_at),
            created_at,
        )

    def create_numeric_prediction(
        self,
        question: str,
        unit: str,
        decimal_places: int,
        lower_bound: Decimal | int | str,
        median_estimate: Decimal | int | str,
        upper_bound: Decimal | int | str,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> NumericPrediction:
        """Create a complete Numeric Prediction and first interval atomically."""

        try:
            revision = NewNumericForecastRevision(
                lower_bound=FixedPrecisionValue.from_value(
                    lower_bound,
                    decimal_places,
                    field="lower_bound",
                ),
                median_estimate=FixedPrecisionValue.from_value(
                    median_estimate,
                    decimal_places,
                    field="median_estimate",
                ),
                upper_bound=FixedPrecisionValue.from_value(
                    upper_bound,
                    decimal_places,
                    field="upper_bound",
                ),
                confidence_percent=confidence_percent,
                rationale=rationale,
            )
            new_prediction = NewNumericPrediction(
                question=question,
                unit=unit,
                decimal_places=decimal_places,
                initial_revision=revision,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error

        created_at = as_utc(self._clock.now())
        current_date = created_at.astimezone(self._local_timezone).date()
        if (
            new_prediction.forecast_deadline is not None
            and new_prediction.forecast_deadline < current_date
        ):
            raise ValidationError(
                "Forecast Deadline cannot be earlier than today when creating a "
                "prediction.",
                field="forecast_deadline",
            )
        return self._with_derived_numeric_status(
            self._numeric_repository.create_prediction(new_prediction, created_at),
            created_at,
        )

    def revise_forecast(
        self,
        prediction_id: int,
        probability_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionDetail:
        """Append a changed forecast after rechecking the reviewed context."""

        try:
            new_revision = NewForecastRevision(probability_percent, rationale)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentForecastUpdateError(prediction_id)
        if current.probability_percent == new_revision.probability_percent:
            raise ForecastUnchangedError(new_revision.probability_percent)

        revised_at = as_utc(self._clock.now())
        current_date = revised_at.astimezone(self._local_timezone).date()
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            current_date,
        )
        if effective_status is not PredictionStatus.OPEN:
            raise ForecastRevisionNotAllowedError(effective_status)

        try:
            updated = self._repository.append_forecast_revision(
                prediction_id,
                new_revision,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=revised_at,
                current_date=current_date,
            )
        except ForecastContextChangedError as error:
            raise ConcurrentForecastUpdateError(prediction_id) from error
        except ForecastRevisionUnchangedError as error:
            raise ForecastUnchangedError(new_revision.probability_percent) from error
        except ForecastRevisionDisallowedError as error:
            raise ForecastRevisionNotAllowedError(error.status) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(updated, revised_at)

    def revise_numeric_forecast(
        self,
        prediction_id: int,
        lower_bound: Decimal | int | str,
        median_estimate: Decimal | int | str,
        upper_bound: Decimal | int | str,
        confidence_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPrediction:
        """Append a changed Numeric interval after rechecking reviewed context."""

        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._numeric_repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        try:
            new_revision = NewNumericForecastRevision(
                FixedPrecisionValue.from_value(
                    lower_bound,
                    current.decimal_places,
                    field="lower_bound",
                ),
                FixedPrecisionValue.from_value(
                    median_estimate,
                    current.decimal_places,
                    field="median_estimate",
                ),
                FixedPrecisionValue.from_value(
                    upper_bound,
                    current.decimal_places,
                    field="upper_bound",
                ),
                confidence_percent,
                rationale,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentForecastUpdateError(prediction_id)

        revised_at = as_utc(self._clock.now())
        current_date = revised_at.astimezone(self._local_timezone).date()
        try:
            updated = self._numeric_repository.append_forecast_revision(
                prediction_id,
                new_revision,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=revised_at,
                current_date=current_date,
            )
        except ForecastContextChangedError as error:
            raise ConcurrentForecastUpdateError(prediction_id) from error
        except NumericForecastRevisionUnchangedError as error:
            raise NumericForecastUnchangedError() from error
        except ForecastRevisionDisallowedError as error:
            raise ForecastRevisionNotAllowedError(error.status) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_numeric_status(updated, revised_at)

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[ForecastRevision, ...]:
        """Return one prediction's immutable revisions in sequence order."""

        revisions = self._repository.list_forecast_revisions(prediction_id)
        if revisions is None:
            raise PredictionNotFoundError(prediction_id)
        return revisions

    def list_numeric_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[NumericForecastRevision, ...]:
        """Return one Numeric Prediction's immutable revisions in sequence order."""

        revisions = self._numeric_repository.list_forecast_revisions(prediction_id)
        if revisions is None:
            raise PredictionNotFoundError(prediction_id)
        return revisions

    def add_numeric_forecast_review(
        self,
        prediction_id: int,
        *,
        note: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericForecastReviewTimelineEvent:
        """Record that the current Numeric interval was deliberately retained."""

        try:
            review = NewForecastReview(note)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._numeric_repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentForecastReviewError(prediction_id)
        now = as_utc(self._clock.now())
        current_date = now.astimezone(self._local_timezone).date()
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            current_date,
        )
        if effective_status is not PredictionStatus.OPEN:
            raise ForecastReviewNotAllowedError(effective_status)
        try:
            event = self._numeric_repository.add_forecast_review(
                prediction_id,
                review,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=now,
                current_date=current_date,
            )
        except ForecastReviewContextChangedError as error:
            raise ConcurrentForecastReviewError(prediction_id) from error
        except ForecastReviewDisallowedError as error:
            raise ForecastReviewNotAllowedError(error.status) from error
        if event is None:
            raise PredictionNotFoundError(prediction_id)
        return event

    def add_numeric_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericJournalTimelineEvent:
        """Append reasoning tied to the reviewed current Numeric interval."""

        try:
            entry = NewJournalEntry(body)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._numeric_repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentJournalUpdateError(prediction_id)
        now = as_utc(self._clock.now())
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            now.astimezone(self._local_timezone).date(),
        )
        if effective_status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            raise JournalEntryNotAllowedError(effective_status)
        try:
            event = self._numeric_repository.add_journal_entry(
                prediction_id,
                entry,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=now,
                current_date=now.astimezone(self._local_timezone).date(),
            )
        except JournalContextChangedError as error:
            raise ConcurrentJournalUpdateError(prediction_id) from error
        except JournalEntryDisallowedError as error:
            raise JournalEntryNotAllowedError(error.status) from error
        if event is None:
            raise PredictionNotFoundError(prediction_id)
        return event

    def correct_numeric_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> NumericJournalTimelineEvent:
        """Append a transparent correction to a Numeric Journal entry."""

        try:
            correction = NewJournalCorrection(body)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(entry_id, "entry_id")
        if expected_correction_id is not None:
            self._validate_positive_token(
                expected_correction_id,
                "expected_correction_id",
            )
        current = self._numeric_repository.get_journal_entry(prediction_id, entry_id)
        if current is None:
            raise JournalEntryNotFoundError(entry_id)
        if current.body == correction.body:
            return current
        corrected_at = as_utc(self._clock.now())
        try:
            updated = self._numeric_repository.append_journal_correction(
                prediction_id,
                entry_id,
                correction,
                expected_correction_id=expected_correction_id,
                corrected_at=corrected_at,
            )
        except JournalCorrectionContextChangedError as error:
            raise ConcurrentJournalCorrectionError(entry_id) from error
        if updated is None:
            raise JournalEntryNotFoundError(entry_id)
        return updated

    def list_numeric_timeline(
        self,
        prediction_id: int,
    ) -> tuple[NumericTimelineEvent, ...]:
        """Return Numeric revisions and anchored Journal entries causally."""

        timeline = self._numeric_repository.list_timeline(prediction_id)
        if timeline is None:
            raise PredictionNotFoundError(prediction_id)
        return timeline

    def resolve_numeric_prediction(
        self,
        prediction_id: int,
        actual_value: Decimal | int | str,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPrediction:
        """Resolve a Numeric Prediction and capture its exact scoring interval."""

        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._numeric_repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        try:
            resolution = NewNumericResolution(
                actual_value=FixedPrecisionValue.from_value(
                    actual_value,
                    current.decimal_places,
                    field="actual_value",
                ),
                resolution_notes=resolution_notes,
                postmortem=postmortem,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)
        now = as_utc(self._clock.now())
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            now.astimezone(self._local_timezone).date(),
        )
        if effective_status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            raise LifecycleTransitionNotAllowedError("resolved", effective_status)
        try:
            updated = self._numeric_repository.resolve_prediction(
                prediction_id,
                resolution,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                resolved_at=now,
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except LifecycleTransitionDisallowedError as error:
            raise LifecycleTransitionNotAllowedError(
                "resolved", error.status
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_numeric_status(updated, now)

    def invalidate_numeric_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> NumericPrediction:
        """Mark a Numeric Prediction terminal Invalid and outside scoring."""

        try:
            invalidation = NewInvalidation(reason)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._numeric_repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)
        now = as_utc(self._clock.now())
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            now.astimezone(self._local_timezone).date(),
        )
        if effective_status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            raise LifecycleTransitionNotAllowedError(
                "marked Invalid",
                effective_status,
            )
        try:
            updated = self._numeric_repository.invalidate_prediction(
                prediction_id,
                invalidation,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                invalidated_at=now,
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except LifecycleTransitionDisallowedError as error:
            raise LifecycleTransitionNotAllowedError(
                "marked Invalid",
                error.status,
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_numeric_status(updated, now)

    def delete_numeric_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> NumericPrediction | None:
        """Permanently delete only an explicitly confirmed untouched Numeric row."""

        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        if confirm_permanent_deletion is not True:
            raise PredictionDeletionConfirmationRequired
        current = self.get_numeric_prediction(prediction_id)
        if (
            current.current_revision.revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)
        if not current.deletion_allowed:
            reason = (
                current.status.value
                if current.status is not PredictionStatus.OPEN
                else "meaningful_history"
            )
            raise PredictionDeletionNotAllowedError(reason)
        now = as_utc(self._clock.now())
        try:
            deleted = self._numeric_repository.delete_prediction(
                prediction_id,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                current_date=now.astimezone(self._local_timezone).date(),
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except PredictionDeletionDisallowedError as error:
            raise PredictionDeletionNotAllowedError(error.reason) from error
        if not deleted:
            raise PredictionNotFoundError(prediction_id)
        latest = self._numeric_repository.get_latest_prediction()
        return (
            None if latest is None else self._with_derived_numeric_status(latest, now)
        )

    def add_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> JournalTimelineEvent:
        """Append reasoning tied to the exact forecast and definition reviewed."""

        try:
            new_entry = NewJournalEntry(body)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentJournalUpdateError(prediction_id)
        if current.status is not PredictionStatus.OPEN:
            raise JournalEntryNotAllowedError(current.status)

        created_at = as_utc(self._clock.now())
        try:
            entry = self._repository.add_journal_entry(
                prediction_id,
                new_entry,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=created_at,
            )
        except JournalContextChangedError as error:
            raise ConcurrentJournalUpdateError(prediction_id) from error
        except JournalEntryDisallowedError as error:
            raise JournalEntryNotAllowedError(error.status) from error
        if entry is None:
            raise PredictionNotFoundError(prediction_id)
        return entry

    def add_forecast_review(
        self,
        prediction_id: int,
        *,
        note: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> ForecastReviewTimelineEvent:
        """Record that the current Binary probability was deliberately retained."""

        try:
            review = NewForecastReview(note)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentForecastReviewError(prediction_id)
        now = as_utc(self._clock.now())
        current_date = now.astimezone(self._local_timezone).date()
        effective_status = display_status(
            current.status,
            current.forecast_deadline,
            current_date,
        )
        if effective_status is not PredictionStatus.OPEN:
            raise ForecastReviewNotAllowedError(effective_status)
        try:
            event = self._repository.add_forecast_review(
                prediction_id,
                review,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                created_at=now,
                current_date=current_date,
            )
        except ForecastReviewContextChangedError as error:
            raise ConcurrentForecastReviewError(prediction_id) from error
        except ForecastReviewDisallowedError as error:
            raise ForecastReviewNotAllowedError(error.status) from error
        if event is None:
            raise PredictionNotFoundError(prediction_id)
        return event

    def correct_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> JournalTimelineEvent:
        """Append an audited body correction without changing entry context."""

        try:
            correction = NewJournalCorrection(body)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(entry_id, "entry_id")
        if expected_correction_id is not None:
            self._validate_positive_token(
                expected_correction_id,
                "expected_correction_id",
            )

        if self._repository.get_prediction(prediction_id) is None:
            raise PredictionNotFoundError(prediction_id)
        current = self._repository.get_journal_entry(prediction_id, entry_id)
        if current is None:
            raise JournalEntryNotFoundError(entry_id)
        if current.current_correction_id != expected_correction_id:
            raise ConcurrentJournalCorrectionError(entry_id)

        corrected_at = None
        if current.body != correction.body:
            corrected_at = as_utc(self._clock.now())
        try:
            updated = self._repository.append_journal_correction(
                prediction_id,
                entry_id,
                correction,
                expected_correction_id=expected_correction_id,
                corrected_at=corrected_at,
            )
        except JournalCorrectionContextChangedError as error:
            raise ConcurrentJournalCorrectionError(entry_id) from error
        if updated is None:
            raise JournalEntryNotFoundError(entry_id)
        return updated

    def resolve_prediction(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionDetail:
        """Persist one immutable outcome and its exact scoring revision."""

        try:
            resolution = NewResolution(
                outcome=outcome,
                resolution_notes=resolution_notes,
                postmortem=postmortem,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)
        if current.status is not PredictionStatus.OPEN:
            raise LifecycleTransitionNotAllowedError("resolved", current.status)

        resolved_at = as_utc(self._clock.now())
        try:
            updated = self._repository.resolve_prediction(
                prediction_id,
                resolution,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                resolved_at=resolved_at,
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except LifecycleTransitionDisallowedError as error:
            raise LifecycleTransitionNotAllowedError(
                "resolved",
                error.status,
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(updated, resolved_at)

    def invalidate_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> PredictionDetail:
        """Persist one immutable Invalid decision outside scoring."""

        try:
            invalidation = NewInvalidation(reason=reason)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)
        if current.status is not PredictionStatus.OPEN:
            raise LifecycleTransitionNotAllowedError("marked Invalid", current.status)

        invalidated_at = as_utc(self._clock.now())
        try:
            updated = self._repository.invalidate_prediction(
                prediction_id,
                invalidation,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                invalidated_at=invalidated_at,
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except LifecycleTransitionDisallowedError as error:
            raise LifecycleTransitionNotAllowedError(
                "marked Invalid",
                error.status,
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(updated, invalidated_at)

    def get_binary_resolution_history(
        self,
        prediction_id: int,
    ) -> BinaryResolutionHistory:
        """Return the original Binary Resolution and every correction."""

        history = self._terminal_history_repository.get_binary_resolution_history(
            prediction_id
        )
        if history is None:
            self._raise_missing_terminal_record(prediction_id, "Binary Resolution")
        assert history is not None
        return history

    def get_numeric_resolution_history(
        self,
        prediction_id: int,
    ) -> NumericResolutionHistory:
        """Return the original Numeric Resolution and every correction."""

        history = self._terminal_history_repository.get_numeric_resolution_history(
            prediction_id
        )
        if history is None:
            self._raise_missing_terminal_record(prediction_id, "Numeric Resolution")
        assert history is not None
        return history

    def get_invalidation_history(self, prediction_id: int) -> InvalidationHistory:
        """Return the original Invalidation and every reason correction."""

        history = self._terminal_history_repository.get_invalidation_history(
            prediction_id
        )
        if history is None:
            self._raise_missing_terminal_record(prediction_id, "Invalidation")
        assert history is not None
        return history

    def correct_binary_resolution(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None,
        postmortem: str | None,
        correction_reason: str | None = None,
        expected_correction_id: int | None,
    ) -> BinaryResolutionHistory:
        """Append one complete Binary Resolution correction snapshot."""

        try:
            proposed = NewResolutionCorrection(
                outcome=outcome,
                resolution_notes=resolution_notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_optional_positive_token(
            expected_correction_id,
            "expected_correction_id",
        )
        history = self.get_binary_resolution_history(prediction_id)
        self._validate_terminal_correction_proposal(
            prediction_id,
            history.current_correction_id,
            expected_correction_id,
            changed_resolution_fields(history.effective, proposed),
            proposed.correction_reason,
            outcome_field="outcome",
        )
        corrected_at = as_utc(self._clock.now())
        try:
            updated = (
                self._terminal_history_repository.append_binary_resolution_correction(
                    prediction_id,
                    proposed,
                    expected_correction_id=expected_correction_id,
                    corrected_at=corrected_at,
                )
            )
        except TerminalCorrectionContextChangedError as error:
            raise ConcurrentTerminalCorrectionError(prediction_id) from error
        except RepositoryTerminalCorrectionUnchangedError as error:
            raise TerminalCorrectionUnchangedError from error
        except OutcomeCorrectionReasonRequiredError as error:
            raise ValidationError(
                "Explain why the recorded outcome is being corrected.",
                field="correction_reason",
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return updated

    def correct_numeric_resolution(
        self,
        prediction_id: int,
        actual_value: Decimal | int | str,
        *,
        resolution_notes: str | None,
        postmortem: str | None,
        correction_reason: str | None = None,
        expected_correction_id: int | None,
    ) -> NumericResolutionHistory:
        """Append one complete exact Numeric Resolution correction snapshot."""

        history = self.get_numeric_resolution_history(prediction_id)
        try:
            proposed = NewNumericResolutionCorrection(
                actual_value=FixedPrecisionValue.from_value(
                    actual_value,
                    history.original.actual_value.decimal_places,
                    field="actual_value",
                ),
                resolution_notes=resolution_notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_optional_positive_token(
            expected_correction_id,
            "expected_correction_id",
        )
        self._validate_terminal_correction_proposal(
            prediction_id,
            history.current_correction_id,
            expected_correction_id,
            changed_numeric_resolution_fields(history.effective, proposed),
            proposed.correction_reason,
            outcome_field="actual_value",
        )
        corrected_at = as_utc(self._clock.now())
        try:
            updated = (
                self._terminal_history_repository.append_numeric_resolution_correction(
                    prediction_id,
                    proposed,
                    expected_correction_id=expected_correction_id,
                    corrected_at=corrected_at,
                )
            )
        except TerminalCorrectionContextChangedError as error:
            raise ConcurrentTerminalCorrectionError(prediction_id) from error
        except RepositoryTerminalCorrectionUnchangedError as error:
            raise TerminalCorrectionUnchangedError from error
        except OutcomeCorrectionReasonRequiredError as error:
            raise ValidationError(
                "Explain why the recorded actual value is being corrected.",
                field="correction_reason",
            ) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return updated

    def correct_invalidation_reason(
        self,
        prediction_id: int,
        reason: str | None,
        *,
        expected_correction_id: int | None,
    ) -> InvalidationHistory:
        """Append one complete Invalidation reason correction snapshot."""

        try:
            proposed = NewInvalidationReasonCorrection(reason)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        self._validate_optional_positive_token(
            expected_correction_id,
            "expected_correction_id",
        )
        history = self.get_invalidation_history(prediction_id)
        if history.current_correction_id != expected_correction_id:
            raise ConcurrentTerminalCorrectionError(prediction_id)
        if history.effective.reason == proposed.reason:
            raise TerminalCorrectionUnchangedError
        corrected_at = as_utc(self._clock.now())
        try:
            updated = (
                self._terminal_history_repository.append_invalidation_reason_correction(
                    prediction_id,
                    proposed,
                    expected_correction_id=expected_correction_id,
                    corrected_at=corrected_at,
                )
            )
        except TerminalCorrectionContextChangedError as error:
            raise ConcurrentTerminalCorrectionError(prediction_id) from error
        except RepositoryTerminalCorrectionUnchangedError as error:
            raise TerminalCorrectionUnchangedError from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return updated

    def record_postmortem_skip(
        self,
        prediction_id: int,
        *,
        expected_correction_id: int | None,
    ) -> PostmortemCompletion:
        """Record that a blank Resolved Postmortem was deliberately skipped."""

        self._validate_optional_positive_token(
            expected_correction_id,
            "expected_correction_id",
        )
        history = self._get_resolution_history(prediction_id)
        if history.current_correction_id != expected_correction_id:
            raise ConcurrentTerminalCorrectionError(prediction_id)
        if history.postmortem_completion is not None:
            raise PostmortemCompletionNotAllowedError("already_completed")
        if history.effective.postmortem is not None:
            raise PostmortemCompletionNotAllowedError("has_postmortem")
        completed_at = as_utc(self._clock.now())
        try:
            completion = self._terminal_history_repository.record_postmortem_completion(
                prediction_id,
                expected_correction_id=expected_correction_id,
                completed_at=completed_at,
            )
        except TerminalCorrectionContextChangedError as error:
            raise ConcurrentTerminalCorrectionError(prediction_id) from error
        except PostmortemCompletionDisallowedError as error:
            raise PostmortemCompletionNotAllowedError(error.reason) from error
        if completion is None:
            raise PredictionNotFoundError(prediction_id)
        return completion

    def delete_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> PredictionDetail | None:
        """Permanently delete only explicitly confirmed untouched Open junk."""

        self._validate_positive_token(expected_revision_id, "expected_revision_id")
        self._validate_positive_token(
            expected_metadata_version,
            "expected_metadata_version",
        )
        if confirm_permanent_deletion is not True:
            raise PredictionDeletionConfirmationRequired

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if (
            current.current_revision_id != expected_revision_id
            or current.metadata_version != expected_metadata_version
        ):
            raise ConcurrentLifecycleUpdateError(prediction_id)

        now = as_utc(self._clock.now())
        displayed = self._with_derived_status(current, now)
        if not displayed.deletion_allowed:
            reason = (
                displayed.status.value
                if displayed.status is not PredictionStatus.OPEN
                else "meaningful_history"
            )
            raise PredictionDeletionNotAllowedError(reason)

        try:
            deleted = self._repository.delete_prediction(
                prediction_id,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                current_date=now.astimezone(self._local_timezone).date(),
            )
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except PredictionDeletionDisallowedError as error:
            raise PredictionDeletionNotAllowedError(error.reason) from error
        if not deleted:
            raise PredictionNotFoundError(prediction_id)

        latest = self._repository.get_latest_prediction()
        return None if latest is None else self._with_derived_status(latest, now)

    def list_timeline(self, prediction_id: int) -> tuple[TimelineEvent, ...]:
        """Return Forecast and Journal events in deterministic causal order."""

        events = self._repository.list_timeline(prediction_id)
        if events is None:
            raise PredictionNotFoundError(prediction_id)
        return events

    def get_latest_prediction(self) -> PredictionDetail | None:
        """Return the most recently created prediction with its current forecast."""

        detail = self._repository.get_latest_prediction()
        if detail is None:
            return None
        now = as_utc(self._clock.now())
        return self._with_derived_status(detail, now)

    def get_latest_numeric_prediction(self) -> NumericPrediction | None:
        """Return the most recently created Numeric Prediction, if one exists."""

        detail = self._numeric_repository.get_latest_prediction()
        if detail is None:
            return None
        now = as_utc(self._clock.now())
        return self._with_derived_numeric_status(detail, now)

    def get_dashboard(self) -> DashboardSnapshot:
        """Return deterministic overlapping action buckets for nonterminal work."""

        now = as_utc(self._clock.now())
        current_date = now.astimezone(self._local_timezone).date()
        stale_threshold_days = self.get_stale_threshold_days()
        predictions = tuple(
            self._classify_dashboard_prediction(
                prediction,
                now=now,
                current_date=current_date,
                stale_threshold_days=stale_threshold_days,
            )
            for prediction in self._repository.list_dashboard_predictions()
        )

        open_predictions = tuple(
            sorted(
                (
                    prediction
                    for prediction in predictions
                    if prediction.status is PredictionStatus.OPEN
                ),
                key=lambda prediction: (
                    prediction.attention_reference_at,
                    prediction.prediction_id,
                ),
                reverse=True,
            )
        )
        needs_attention_predictions = tuple(
            sorted(
                (
                    prediction
                    for prediction in predictions
                    if prediction.needs_attention
                ),
                key=lambda prediction: (
                    prediction.attention_reference_at,
                    prediction.prediction_id,
                ),
            )
        )
        ready_to_resolve_predictions = tuple(
            sorted(
                (
                    prediction
                    for prediction in predictions
                    if prediction.ready_to_resolve
                ),
                key=lambda prediction: (
                    prediction.expected_resolution or date.max,
                    prediction.prediction_id,
                ),
            )
        )
        locked_predictions = tuple(
            sorted(
                (
                    prediction
                    for prediction in predictions
                    if prediction.status is PredictionStatus.LOCKED
                ),
                key=lambda prediction: (
                    prediction.forecast_deadline or date.max,
                    prediction.prediction_id,
                ),
            )
        )
        return DashboardSnapshot(
            stale_threshold_days=stale_threshold_days,
            open_predictions=open_predictions,
            needs_attention_predictions=needs_attention_predictions,
            ready_to_resolve_predictions=ready_to_resolve_predictions,
            locked_predictions=locked_predictions,
            needs_postmortem_predictions=(
                self._repository.list_needs_postmortem_predictions()
            ),
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
        """Search and filter current prediction summaries for the archive."""

        if not isinstance(question_text, str):
            raise ValidationError(
                "Question search text must be text.",
                field="question_text",
            )
        search_key = question_text.strip().casefold()
        archive_query = self._archive_query(
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
            text_active=bool(search_key),
        )
        now = as_utc(self._clock.now())
        current_date = now.astimezone(self._local_timezone).date()
        stale_threshold_days = self.get_stale_threshold_days()
        snapshot = self._repository.list_browser_predictions()
        predictions = classify_archive_items(
            snapshot.predictions,
            current_date=current_date,
        )
        return replace(
            snapshot,
            predictions=sort_archive_items(
                (
                    prediction
                    for prediction in predictions
                    if (not search_key or search_key in prediction.question.casefold())
                    and matches_archive_query(
                        prediction,
                        archive_query,
                        now=now,
                        current_date=current_date,
                        stale_threshold_days=stale_threshold_days,
                        local_timezone=self._local_timezone,
                    )
                ),
                archive_query.sort,
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
        """Search canonical Prediction text through the rebuildable projection."""

        try:
            query = SearchQuery(
                text=text,
                match_mode=match_mode,
                include_superseded=include_superseded,
            )
            parsed_text = parse_search_text(query.text)
        except SearchValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        if parsed_text.is_blank:
            return PredictionSearchResults(
                query=query, parsed_text=parsed_text, hits=()
            )
        archive_query = self._archive_query(
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
            text_active=True,
        )

        try:
            predictions, candidates, available_tags = (
                self._search_repository.find_candidates(
                    parsed_text,
                    include_superseded=query.include_superseded,
                )
            )
            now = as_utc(self._clock.now())
            current_date = now.astimezone(self._local_timezone).date()
            stale_threshold_days = self.get_stale_threshold_days()
            classified_predictions = classify_archive_items(
                predictions.values(),
                current_date=current_date,
            )
            effective_predictions = {
                prediction.prediction_id: prediction
                for prediction in classified_predictions
                if matches_archive_query(
                    prediction,
                    archive_query,
                    now=now,
                    current_date=current_date,
                    stale_threshold_days=stale_threshold_days,
                    local_timezone=self._local_timezone,
                )
            }
            hits = rank_search_candidates(
                parsed_text,
                query.match_mode,
                effective_predictions,
                candidates,
            )
            if archive_query.sort is not ArchiveSort.RELEVANCE:
                hits_by_prediction_id = {
                    hit.prediction.prediction_id: hit for hit in hits
                }
                hits = tuple(
                    hits_by_prediction_id[prediction.prediction_id]
                    for prediction in sort_archive_items(
                        (hit.prediction for hit in hits),
                        archive_query.sort,
                    )
                )
            any_word_available = (
                query.match_mode is SearchMatchMode.ALL
                and not hits
                and bool(
                    rank_search_candidates(
                        parsed_text,
                        SearchMatchMode.ANY,
                        effective_predictions,
                        candidates,
                    )
                )
            )
            suggestion = None
            if not hits:
                suggestion = self._search_repository.suggest_spelling(
                    parsed_text,
                    include_superseded=query.include_superseded,
                )
        except SearchIndexBusyError as error:
            raise SearchUnavailableError(
                "The local database is busy with another Reckonsolve action. "
                "Wait a moment and search again."
            ) from error
        except SearchIndexError as error:
            raise SearchUnavailableError(
                "The local search index is unavailable. Run the search-index repair "
                "before searching again."
            ) from error

        return PredictionSearchResults(
            query=query,
            parsed_text=parsed_text,
            hits=hits,
            any_word_available=any_word_available,
            suggestion=suggestion,
            available_tags=available_tags,
        )

    @staticmethod
    def _archive_query(
        *,
        status: PredictionStatus | None,
        tag: str | None,
        prediction_type: PredictionType | None,
        tags: tuple[str, ...],
        tag_match_mode: ArchiveTagMatchMode,
        attention: ArchiveAttention | None,
        date_meaning: ArchiveDateMeaning,
        date_start: date | None,
        date_end: date | None,
        sort: ArchiveSort,
        text_active: bool,
    ) -> ArchiveQuery:
        """Normalize legacy single-tag input into one rich archive request."""

        if status is not None and not isinstance(status, PredictionStatus):
            raise ValidationError(
                "The prediction status filter is invalid.", field="status"
            )
        if tag is not None and not isinstance(tag, str):
            raise ValidationError("The prediction tag filter is invalid.", field="tag")
        if prediction_type is not None and not isinstance(
            prediction_type, PredictionType
        ):
            raise ValidationError(
                "The forecast type filter is invalid.", field="prediction_type"
            )
        if not isinstance(tags, tuple):
            raise ValidationError("Selected tags must be text labels.", field="tags")
        selected_tags = tags if tag is None else (*tags, tag)
        request = ArchiveQuery(
            status=status,
            prediction_type=prediction_type,
            tags=selected_tags,
            tag_match_mode=tag_match_mode,
            attention=attention,
            date_meaning=date_meaning,
            date_start=date_start,
            date_end=date_end,
            sort=sort,
        )
        try:
            validate_archive_query(request, text_active=text_active)
        except ArchiveQueryValidationError as error:
            raise ValidationError(str(error), field="archive_query") from error
        return request

    def repair_search_index(self) -> None:
        """Rebuild the derived local search projection from canonical history."""

        try:
            self._database.rebuild_search_index()
        except SearchIndexError as error:
            raise SearchUnavailableError(
                "The local search index could not be rebuilt from Prediction history."
            ) from error

    def get_analytics(self, *, tag: str | None = None) -> AnalyticsSnapshot:
        """Return exactly-once scoring analytics for all or one tag subset."""

        if tag is not None and not isinstance(tag, str):
            raise ValidationError(
                "The analytics tag filter is invalid.",
                field="tag",
            )
        return summarize_analytics(
            self._analytics_repository.get_source(),
            tag=tag,
        )

    def get_prediction_scorecard(
        self,
        prediction_id: int,
    ) -> PredictionScorecard | None:
        """Return one resolved Prediction's type-aware derived scorecard.

        The card is derived only from the immutable scoring ForecastRevision and
        the effective current terminal value supplied by analytics data access.
        Unresolved and Invalid Predictions intentionally have no scorecard.
        """

        self._validate_positive_token(prediction_id, "prediction_id")
        binary_source, numeric_source = self._analytics_repository.get_sources()
        binary_observation = next(
            (
                observation
                for observation in binary_source.observations
                if observation.prediction_id == prediction_id
            ),
            None,
        )
        if binary_observation is not None:
            return binary_scorecard(binary_observation)
        numeric_observation = next(
            (
                observation
                for observation in numeric_source.observations
                if observation.prediction_id == prediction_id
            ),
            None,
        )
        return (
            None
            if numeric_observation is None
            else numeric_scorecard(numeric_observation)
        )

    def get_forecast_analytics(
        self,
        *,
        prediction_type: PredictionType | None = None,
        tag: str | None = None,
        unit: str | None = None,
    ) -> ForecastAnalyticsSnapshot:
        """Return separate Binary and Numeric metrics for one filter subset."""

        if prediction_type is not None and not isinstance(
            prediction_type,
            PredictionType,
        ):
            raise ValidationError(
                "The analytics forecast-type filter is invalid.",
                field="prediction_type",
            )
        if tag is not None and not isinstance(tag, str):
            raise ValidationError(
                "The analytics tag filter is invalid.",
                field="tag",
            )
        if unit is not None and not isinstance(unit, str):
            raise ValidationError(
                "The analytics unit filter is invalid.",
                field="unit",
            )
        normalized_unit = None if unit is None else unit.strip() or None
        if (
            normalized_unit is not None
            and prediction_type is not PredictionType.NUMERIC
        ):
            raise ValidationError(
                "Choose Numeric analytics before filtering by unit.",
                field="unit",
            )
        binary_source, numeric_source = self._analytics_repository.get_sources()
        return summarize_forecast_analytics(
            binary_source,
            numeric_source,
            prediction_type=prediction_type,
            tag=tag,
            unit=normalized_unit,
        )

    def get_data_management_status(self) -> DataManagementStatus:
        """Return recovery status and suggested timestamped artifact names."""

        instant = as_utc(self._clock.now())
        local_instant = instant.astimezone(self._local_timezone)
        suffix = local_instant.strftime("%Y%m%d-%H%M%S")
        try:
            last_successful_backup_at = (
                self._settings_repository.get_last_successful_backup_at()
            )
        except sqlite3.Error as error:
            raise BackupError(f"Backup status could not be loaded. {error}") from error
        return DataManagementStatus(
            database_path=self._transfer_repository.database_path,
            last_successful_backup_at=last_successful_backup_at,
            suggested_backup_filename=f"reckonsolve-backup-{suffix}.sqlite3",
            suggested_export_filename=f"reckonsolve-export-{suffix}.zip",
        )

    def create_backup(self, destination: Path) -> BackupResult:
        """Create a verified SQLite recovery file and record its success time."""

        try:
            created_destination = self._transfer_repository.create_backup(destination)
        except (OSError, sqlite3.Error, ValueError) as error:
            raise BackupError(f"The backup could not be created. {error}") from error

        completed_at = as_utc(self._clock.now())
        recorded = True
        try:
            self._settings_repository.set_last_successful_backup_at(completed_at)
        except sqlite3.Error:
            recorded = False
        return BackupResult(
            destination=created_destination,
            completed_at=completed_at,
            last_successful_time_recorded=recorded,
        )

    def export_csv_bundle(self, destination: Path) -> CsvExportResult:
        """Create one documented relational CSV ZIP without mutating app data."""

        exported_at = as_utc(self._clock.now())
        try:
            created_destination, csv_file_count = (
                self._transfer_repository.export_csv_bundle(
                    destination,
                    exported_at=exported_at,
                )
            )
        except (BadZipFile, OSError, sqlite3.Error, csv.Error, ValueError) as error:
            raise CsvExportError(
                f"The CSV export could not be created. {error}"
            ) from error
        return CsvExportResult(
            destination=created_destination,
            exported_at=exported_at,
            csv_file_count=csv_file_count,
        )

    def get_stale_threshold_days(self) -> int:
        """Return the persisted Needs Attention threshold."""

        value = self._settings_repository.get_stale_threshold_days()
        try:
            return validate_stale_threshold_days(value)
        except AttentionValidationError as error:
            raise ValidationError(str(error), field="stale_threshold_days") from error

    def set_stale_threshold_days(self, value: int) -> int:
        """Validate and persist the Needs Attention threshold."""

        try:
            threshold = validate_stale_threshold_days(value)
        except AttentionValidationError as error:
            raise ValidationError(str(error), field="stale_threshold_days") from error
        return self._settings_repository.set_stale_threshold_days(threshold)

    def get_prediction(self, prediction_id: int) -> PredictionDetail:
        """Return one prediction with current forecast and complete metadata."""

        detail = self._repository.get_prediction(prediction_id)
        if detail is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(detail, as_utc(self._clock.now()))

    def get_numeric_prediction(self, prediction_id: int) -> NumericPrediction:
        """Return one Numeric Prediction with current interval and metadata."""

        detail = self._numeric_repository.get_prediction(prediction_id)
        if detail is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_numeric_status(detail, as_utc(self._clock.now()))

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> PredictionDetail | NumericPrediction:
        """Load one current Prediction of either forecast type for Detail routing."""

        detail = self._repository.get_prediction(prediction_id)
        if detail is not None:
            return self._with_derived_status(detail, as_utc(self._clock.now()))
        numeric_detail = self._numeric_repository.get_prediction(prediction_id)
        if numeric_detail is not None:
            return self._with_derived_numeric_status(
                numeric_detail,
                as_utc(self._clock.now()),
            )
        raise PredictionNotFoundError(prediction_id)

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
    ) -> PredictionDetail:
        """Validate and atomically replace editable prediction metadata."""

        try:
            update = PredictionMetadataUpdate(
                question=question,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error

        if (
            isinstance(expected_metadata_version, bool)
            or not isinstance(expected_metadata_version, int)
            or expected_metadata_version < 1
        ):
            raise ValidationError(
                "The prediction edit version is invalid.",
                field="expected_metadata_version",
            )

        current = self._repository.get_prediction(prediction_id)
        if current is None:
            raise PredictionNotFoundError(prediction_id)
        if current.metadata_version != expected_metadata_version:
            raise ConcurrentPredictionUpdateError(prediction_id)
        if not metadata_would_change(current, update):
            return self._with_derived_status(current, as_utc(self._clock.now()))

        changed_fields = changed_definition_fields(current, update)
        if changed_fields and not confirm_meaning_change:
            raise MeaningChangeConfirmationRequired(changed_fields)

        changed_at = as_utc(self._clock.now())
        try:
            updated = self._repository.update_metadata(
                prediction_id,
                update,
                expected=current,
                expected_metadata_version=expected_metadata_version,
                changed_at=changed_at,
            )
        except PredictionChangedError as error:
            raise ConcurrentPredictionUpdateError(prediction_id) from error
        if updated is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(updated, changed_at)

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...]:
        """Return the prediction's immutable definition history."""

        changes = self._repository.list_definition_changes(prediction_id)
        if changes is None:
            raise PredictionNotFoundError(prediction_id)
        return changes

    def _with_derived_status(
        self,
        detail: PredictionDetail,
        now: datetime,
    ) -> PredictionDetail:
        local_date = now.astimezone(self._local_timezone).date()
        status = display_status(
            detail.status,
            detail.forecast_deadline,
            local_date,
        )
        return replace(
            detail,
            status=status,
            deletion_allowed=(
                detail.deletion_allowed and status is PredictionStatus.OPEN
            ),
        )

    def _with_derived_numeric_status(
        self,
        detail: NumericPrediction,
        now: datetime,
    ) -> NumericPrediction:
        status = display_status(
            detail.status,
            detail.forecast_deadline,
            now.astimezone(self._local_timezone).date(),
        )
        return replace(
            detail,
            status=status,
            deletion_allowed=(
                detail.deletion_allowed and status is PredictionStatus.OPEN
            ),
        )

    def _classify_dashboard_prediction(
        self,
        prediction: DashboardPrediction,
        *,
        now: datetime,
        current_date: date,
        stale_threshold_days: int,
    ) -> DashboardPrediction:
        status = display_status(
            prediction.status,
            prediction.forecast_deadline,
            current_date,
        )
        return replace(
            prediction,
            status=status,
            needs_attention=needs_attention(
                status,
                prediction.attention_reference_at,
                now,
                stale_threshold_days,
            ),
            ready_to_resolve=ready_to_resolve(
                status,
                prediction.expected_resolution,
                current_date,
            ),
        )

    def _raise_missing_terminal_record(
        self,
        prediction_id: int,
        record_name: str,
    ) -> None:
        binary = self._repository.get_prediction(prediction_id)
        numeric = (
            None
            if binary is not None
            else self._numeric_repository.get_prediction(prediction_id)
        )
        if binary is None and numeric is None:
            raise PredictionNotFoundError(prediction_id)
        raise TerminalCorrectionNotAllowedError(prediction_id, record_name)

    def _get_resolution_history(
        self,
        prediction_id: int,
    ) -> BinaryResolutionHistory | NumericResolutionHistory:
        binary = self._terminal_history_repository.get_binary_resolution_history(
            prediction_id
        )
        if binary is not None:
            return binary
        numeric = self._terminal_history_repository.get_numeric_resolution_history(
            prediction_id
        )
        if numeric is not None:
            return numeric
        self._raise_missing_terminal_record(prediction_id, "Resolution")
        raise AssertionError("missing terminal record helper must raise")

    @staticmethod
    def _validate_terminal_correction_proposal(
        prediction_id: int,
        current_correction_id: int | None,
        expected_correction_id: int | None,
        changed_fields: tuple[str, ...],
        correction_reason: str | None,
        *,
        outcome_field: str,
    ) -> None:
        if current_correction_id != expected_correction_id:
            raise ConcurrentTerminalCorrectionError(prediction_id)
        if not changed_fields:
            raise TerminalCorrectionUnchangedError
        if outcome_field in changed_fields and correction_reason is None:
            label = "outcome" if outcome_field == "outcome" else "actual value"
            raise ValidationError(
                f"Explain why the recorded {label} is being corrected.",
                field="correction_reason",
            )

    @staticmethod
    def _validate_positive_token(value: object, field: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValidationError(
                "The forecast revision context is invalid.",
                field=field,
            )

    @staticmethod
    def _validate_optional_positive_token(value: object, field: str) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValidationError(
                "The terminal correction context is invalid.",
                field=field,
            )
