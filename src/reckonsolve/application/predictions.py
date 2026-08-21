"""Application operations for binary predictions."""

import csv
import sqlite3
from dataclasses import replace
from datetime import date, datetime, tzinfo
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile

from reckonsolve.analytics import AnalyticsSnapshot, summarize_analytics
from reckonsolve.clock import Clock, SystemClock, as_utc
from reckonsolve.data.analytics import AnalyticsRepository
from reckonsolve.data.database import Database
from reckonsolve.data.numeric_predictions import (
    NumericForecastRevisionUnchangedError,
    NumericPredictionRepository,
)
from reckonsolve.data.predictions import (
    ForecastContextChangedError,
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
from reckonsolve.data.settings import SettingsRepository
from reckonsolve.data.transfer import DataTransferRepository
from reckonsolve.domain.attention import (
    AttentionValidationError,
    DashboardPrediction,
    DashboardSnapshot,
    needs_attention,
    ready_to_resolve,
    validate_stale_threshold_days,
)
from reckonsolve.domain.browser import PredictionBrowserSnapshot
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    DefinitionChange,
    FixedPrecisionValue,
    ForecastRevision,
    JournalTimelineEvent,
    NewForecastRevision,
    NewInvalidation,
    NewJournalCorrection,
    NewJournalEntry,
    NewNumericForecastRevision,
    NewNumericPrediction,
    NewNumericResolution,
    NewPrediction,
    NewResolution,
    NumericForecastRevision,
    NumericJournalTimelineEvent,
    NumericPrediction,
    NumericTimelineEvent,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionStatus,
    PredictionValidationError,
    TimelineEvent,
    changed_definition_fields,
    display_status,
    metadata_would_change,
)
from reckonsolve.domain.transfer import (
    BackupResult,
    CsvExportResult,
    DataManagementStatus,
)

from .errors import (
    BackupError,
    ConcurrentForecastUpdateError,
    ConcurrentJournalCorrectionError,
    ConcurrentJournalUpdateError,
    ConcurrentLifecycleUpdateError,
    ConcurrentPredictionUpdateError,
    CsvExportError,
    ForecastRevisionNotAllowedError,
    ForecastUnchangedError,
    JournalEntryNotAllowedError,
    JournalEntryNotFoundError,
    LifecycleTransitionNotAllowedError,
    MeaningChangeConfirmationRequired,
    NumericForecastUnchangedError,
    PredictionDeletionConfirmationRequired,
    PredictionDeletionNotAllowedError,
    PredictionNotFoundError,
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
        self._transfer_repository = DataTransferRepository(database)
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
                    prediction.latest_revision_at,
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
                    prediction.latest_revision_at,
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
        )

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
    ) -> PredictionBrowserSnapshot:
        """Search and filter current prediction summaries for the archive."""

        if not isinstance(question_text, str):
            raise ValidationError(
                "Question search text must be text.",
                field="question_text",
            )
        if status is not None and not isinstance(status, PredictionStatus):
            raise ValidationError(
                "The prediction status filter is invalid.",
                field="status",
            )
        if tag is not None and not isinstance(tag, str):
            raise ValidationError(
                "The prediction tag filter is invalid.",
                field="tag",
            )

        search_key = question_text.strip().casefold()
        tag_key = None if tag is None else tag.strip().casefold() or None
        now = as_utc(self._clock.now())
        current_date = now.astimezone(self._local_timezone).date()
        snapshot = self._repository.list_browser_predictions()
        predictions = tuple(
            replace(
                prediction,
                status=display_status(
                    prediction.status,
                    prediction.forecast_deadline,
                    current_date,
                ),
            )
            for prediction in snapshot.predictions
        )
        return replace(
            snapshot,
            predictions=tuple(
                prediction
                for prediction in predictions
                if (not search_key or search_key in prediction.question.casefold())
                and (status is None or prediction.status is status)
                and (
                    tag_key is None
                    or tag_key in {item.casefold() for item in prediction.tags}
                )
            ),
        )

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
                prediction.latest_revision_at,
                now,
                stale_threshold_days,
            ),
            ready_to_resolve=ready_to_resolve(
                status,
                prediction.expected_resolution,
                current_date,
            ),
        )

    @staticmethod
    def _validate_positive_token(value: object, field: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValidationError(
                "The forecast revision context is invalid.",
                field=field,
            )
