"""Application operations for binary predictions."""

from datetime import date, datetime, tzinfo

from reckonsolve.clock import Clock, SystemClock, as_utc
from reckonsolve.data.database import Database
from reckonsolve.data.predictions import PredictionChangedError, PredictionRepository
from reckonsolve.domain.predictions import (
    DefinitionChange,
    NewPrediction,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionValidationError,
    changed_definition_fields,
    display_status,
    metadata_would_change,
)

from .errors import (
    ConcurrentPredictionUpdateError,
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
    ) -> PredictionDetail:
        """Create a prediction and its initial forecast as one atomic operation."""

        try:
            new_prediction = NewPrediction(question, probability_percent)
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error

        created_at = as_utc(self._clock.now())
        return self._with_derived_status(
            self._repository.create_prediction(new_prediction, created_at),
            created_at,
        )

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
            background=detail.background,
            resolution_criteria=detail.resolution_criteria,
            forecast_deadline=detail.forecast_deadline,
            expected_resolution=detail.expected_resolution,
            tags=detail.tags,
            updated_at=detail.updated_at,
            metadata_version=detail.metadata_version,
        )
