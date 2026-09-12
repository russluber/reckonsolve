"""Active five-quantile operations; shared by desktop and CLI presentation."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal

from reckonsolve.data.predictions import (
    ForecastContextChangedError,
    ForecastReviewContextChangedError,
    ForecastReviewDisallowedError,
    ForecastRevisionDisallowedError,
    JournalContextChangedError,
    JournalCorrectionContextChangedError,
    JournalEntryDisallowedError,
    LifecycleContextChangedError,
    LifecycleTransitionDisallowedError,
    PredictionDeletionDisallowedError,
)
from reckonsolve.data.quantiles import QuantilePredictionRepository
from reckonsolve.domain.forecast_contracts import (
    ForecastContractValidationError,
    ForecastDeadline,
)
from reckonsolve.domain.predictions import NumericPrediction, PredictionValidationError
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NewQuantilePrediction,
    NumericValueConstraint,
    QuantileDefinition,
    QuantileTimelineEvent,
)

from .errors import (
    ConcurrentForecastReviewError,
    ConcurrentForecastUpdateError,
    ConcurrentJournalCorrectionError,
    ConcurrentJournalUpdateError,
    ConcurrentLifecycleUpdateError,
    ForecastReviewNotAllowedError,
    ForecastRevisionNotAllowedError,
    JournalEntryNotAllowedError,
    JournalEntryNotFoundError,
    LifecycleTransitionNotAllowedError,
    PredictionDeletionNotAllowedError,
    ValidationError,
)


class QuantileOperations:
    """Small composed boundary for the new model, not a second transaction layer."""

    def __init__(self, repository: QuantilePredictionRepository) -> None:
        self.repository = repository

    def create(
        self,
        question: str,
        unit: str,
        decimal_places: int,
        quantiles: Mapping[int, Decimal | int | str],
        *,
        value_constraint: NumericValueConstraint,
        forecast_deadline: datetime,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> NumericPrediction:
        try:
            new = NewQuantilePrediction(
                question,
                QuantileDefinition(unit, decimal_places, value_constraint),
                FiveQuantiles.from_values(quantiles, decimal_places),
                ForecastDeadline(forecast_deadline),
                rationale,
                background,
                resolution_criteria,
                expected_resolution,
                tags,
            )
            created = self.repository.create_detail(new)
        except (PredictionValidationError, ForecastContractValidationError) as error:
            raise ValidationError(str(error), field=error.field) from error
        return created

    def revise(
        self,
        prediction_id: int,
        values: Mapping[int, Decimal | int | str],
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        rationale: str | None = None,
    ) -> NumericPrediction:
        try:
            current = self.repository.get_prediction(prediction_id)
            quantiles = FiveQuantiles.from_values(values, current.decimal_places)
            saved = self.repository.revise_prediction(
                prediction_id,
                quantiles,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                rationale=rationale,
            )
        except (PredictionValidationError, ForecastContractValidationError) as error:
            raise ValidationError(str(error), field=error.field) from error
        except ForecastContextChangedError as error:
            raise ConcurrentForecastUpdateError(prediction_id) from error
        except ForecastRevisionDisallowedError as error:
            raise ForecastRevisionNotAllowedError(error.status) from error
        return saved

    def note(
        self,
        prediction_id: int,
        body: str | None,
        *,
        review: bool,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> QuantileTimelineEvent:
        try:
            return self.repository.add_note(
                prediction_id,
                body=body,
                review=review,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        except (PredictionValidationError, ForecastContractValidationError) as error:
            raise ValidationError(str(error), field=error.field) from error
        except ForecastReviewContextChangedError as error:
            raise ConcurrentForecastReviewError(prediction_id) from error
        except ForecastReviewDisallowedError as error:
            raise ForecastReviewNotAllowedError(error.status) from error
        except JournalContextChangedError as error:
            raise ConcurrentJournalUpdateError(prediction_id) from error
        except JournalEntryDisallowedError as error:
            raise JournalEntryNotAllowedError(error.status) from error

    def correct_journal(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> QuantileTimelineEvent:
        try:
            event = self.repository.correct_journal(
                prediction_id,
                entry_id,
                body,
                expected_correction_id=expected_correction_id,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        except JournalCorrectionContextChangedError as error:
            raise ConcurrentJournalCorrectionError(entry_id) from error
        if event is None:
            raise JournalEntryNotFoundError(entry_id)
        return event

    def invalidate_or_delete(
        self,
        prediction_id: int,
        *,
        delete: bool,
        reason: str | None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> None:
        try:
            self.repository.invalidate_or_delete(
                prediction_id,
                delete=delete,
                reason=reason,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        except PredictionValidationError as error:
            raise ValidationError(str(error), field=error.field) from error
        except LifecycleContextChangedError as error:
            raise ConcurrentLifecycleUpdateError(prediction_id) from error
        except LifecycleTransitionDisallowedError as error:
            raise LifecycleTransitionNotAllowedError(
                "marked Invalid", error.status
            ) from error
        except PredictionDeletionDisallowedError as error:
            raise PredictionDeletionNotAllowedError(error.reason) from error
