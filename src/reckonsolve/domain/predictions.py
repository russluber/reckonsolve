"""Binary-prediction values and validation rules."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PredictionValidationError(ValueError):
    """Raised when prediction input violates a domain rule."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class PredictionStatus(StrEnum):
    """Persisted prediction states; Locked is derived rather than persisted."""

    OPEN = "open"
    RESOLVED = "resolved"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class NewPrediction:
    """Validated input for a binary prediction and its initial forecast."""

    question: str
    probability_percent: int

    def __post_init__(self) -> None:
        if not isinstance(self.question, str):
            raise PredictionValidationError(
                "Question is required.",
                field="question",
            )

        normalized_question = self.question.strip()
        if not normalized_question:
            raise PredictionValidationError(
                "Question is required.",
                field="question",
            )
        object.__setattr__(self, "question", normalized_question)

        probability = self.probability_percent
        if isinstance(probability, bool) or not isinstance(probability, int):
            raise PredictionValidationError(
                "Probability must be a whole percentage from 0 to 100.",
                field="probability_percent",
            )
        if not 0 <= probability <= 100:
            raise PredictionValidationError(
                "Probability must be between 0 and 100.",
                field="probability_percent",
            )


@dataclass(frozen=True, slots=True)
class Prediction:
    """The stable identity and lifecycle facts of a binary prediction."""

    prediction_id: int
    question: str
    status: PredictionStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ForecastRevision:
    """One immutable statement of probability."""

    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PredictionDetail:
    """Current display data derived from a prediction and its latest revision."""

    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus
    created_at: datetime
