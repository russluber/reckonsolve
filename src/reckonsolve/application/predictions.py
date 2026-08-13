"""Application operations for binary predictions."""

from datetime import date, datetime, tzinfo

from reckonsolve.clock import Clock, SystemClock, as_utc
from reckonsolve.data.database import Database
from reckonsolve.data.predictions import (
    ForecastContextChangedError,
    ForecastRevisionDisallowedError,
    ForecastRevisionUnchangedError,
    JournalContextChangedError,
    JournalCorrectionContextChangedError,
    JournalEntryDisallowedError,
    PredictionChangedError,
    PredictionRepository,
)
from reckonsolve.domain.predictions import (
    DefinitionChange,
    ForecastRevision,
    JournalTimelineEvent,
    NewForecastRevision,
    NewJournalCorrection,
    NewJournalEntry,
    NewPrediction,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionStatus,
    PredictionValidationError,
    TimelineEvent,
    changed_definition_fields,
    display_status,
    metadata_would_change,
)

from .errors import (
    ConcurrentForecastUpdateError,
    ConcurrentJournalCorrectionError,
    ConcurrentJournalUpdateError,
    ConcurrentPredictionUpdateError,
    ForecastRevisionNotAllowedError,
    ForecastUnchangedError,
    JournalEntryNotAllowedError,
    JournalEntryNotFoundError,
    MeaningChangeConfirmationRequired,
    PredictionNotFoundError,
    ValidationError,
)


class PredictionOperations:
    """Coordinate complete prediction-creation and current-detail use cases."""

    def __init__(
        self,
        database: Database,
        clock: Clock | None = None,
        local_timezone: tzinfo | None = None,
    ) -> None:
        self._repository = PredictionRepository(database)
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

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[ForecastRevision, ...]:
        """Return one prediction's immutable revisions in sequence order."""

        revisions = self._repository.list_forecast_revisions(prediction_id)
        if revisions is None:
            raise PredictionNotFoundError(prediction_id)
        return revisions

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

    def get_prediction(self, prediction_id: int) -> PredictionDetail:
        """Return one prediction with current forecast and complete metadata."""

        detail = self._repository.get_prediction(prediction_id)
        if detail is None:
            raise PredictionNotFoundError(prediction_id)
        return self._with_derived_status(detail, as_utc(self._clock.now()))

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
        return PredictionDetail(
            prediction_id=detail.prediction_id,
            question=detail.question,
            probability_percent=detail.probability_percent,
            status=display_status(
                detail.status,
                detail.forecast_deadline,
                local_date,
            ),
            created_at=detail.created_at,
            current_revision_id=detail.current_revision_id,
            current_revision_sequence=detail.current_revision_sequence,
            current_rationale=detail.current_rationale,
            background=detail.background,
            resolution_criteria=detail.resolution_criteria,
            forecast_deadline=detail.forecast_deadline,
            expected_resolution=detail.expected_resolution,
            tags=detail.tags,
            updated_at=detail.updated_at,
            metadata_version=detail.metadata_version,
        )

    @staticmethod
    def _validate_positive_token(value: object, field: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValidationError(
                "The forecast revision context is invalid.",
                field=field,
            )
