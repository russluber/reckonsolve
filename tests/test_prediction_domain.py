from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from reckonsolve.domain.predictions import (
    NewPrediction,
    PredictionDetail,
    PredictionStatus,
    PredictionValidationError,
)


@pytest.mark.parametrize("probability", [0, 1, 37, 99, 100])
def test_new_prediction_accepts_any_whole_percent_including_endpoints(
    probability: int,
) -> None:
    prediction = NewPrediction("  Will this happen?  ", probability)

    assert prediction.question == "Will this happen?"
    assert prediction.probability_percent == probability


@pytest.mark.parametrize("question", ["", "  \t\n  ", None])
def test_new_prediction_requires_nonblank_question(question: Any) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewPrediction(question, 50)

    assert error_info.value.field == "question"
    assert str(error_info.value) == "Question is required."


@pytest.mark.parametrize("probability", [-1, 101, 37.5, "50", True, False, None])
def test_new_prediction_rejects_non_whole_or_out_of_range_probability(
    probability: Any,
) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewPrediction("Will this happen?", probability)

    assert error_info.value.field == "probability_percent"


def test_prediction_detail_is_immutable() -> None:
    detail = PredictionDetail(
        prediction_id=1,
        question="Will this happen?",
        probability_percent=50,
        status=PredictionStatus.OPEN,
        created_at=datetime.now(UTC),
    )

    with pytest.raises(FrozenInstanceError):
        detail.question = "Rewritten"  # type: ignore[misc]
