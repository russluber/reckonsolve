"""Application operations for binary predictions."""

from reckonsolve.clock import Clock, SystemClock, as_utc
from reckonsolve.data.database import Database
from reckonsolve.data.predictions import PredictionRepository
from reckonsolve.domain.predictions import (
    NewPrediction,
    PredictionDetail,
    PredictionValidationError,
)

from .errors import ValidationError


class PredictionOperations:
    """Coordinate complete prediction-creation and current-detail use cases."""

    def __init__(self, database: Database, clock: Clock | None = None) -> None:
        self._repository = PredictionRepository(database)
        self._clock = SystemClock() if clock is None else clock

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
        return self._repository.create_prediction(new_prediction, created_at)

    def get_latest_prediction(self) -> PredictionDetail | None:
        """Return the most recently created prediction with its current forecast."""

        return self._repository.get_latest_prediction()
