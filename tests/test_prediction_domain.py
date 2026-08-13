from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from typing import Any

import pytest

from reckonsolve.domain.predictions import (
    NewForecastRevision,
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


def test_new_prediction_rejects_nul_in_question() -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewPrediction("Will this\x00 happen?", 50)

    assert error_info.value.field == "question"


def test_new_prediction_normalizes_complete_initial_state() -> None:
    prediction = NewPrediction(
        question="  Will this happen?  ",
        probability_percent=50,
        rationale="  Initial case  ",
        background="  Context  ",
        resolution_criteria="  Official result  ",
        forecast_deadline=date(2027, 1, 1),
        expected_resolution=date(2027, 1, 2),
        tags=(" Science ", "science", "Personal"),
    )

    assert prediction.rationale == "Initial case"
    assert prediction.background == "Context"
    assert prediction.resolution_criteria == "Official result"
    assert prediction.tags == ("Science", "Personal")


@pytest.mark.parametrize("probability", [0, 37, 100])
def test_new_forecast_revision_accepts_whole_percent_and_normalizes_rationale(
    probability: int,
) -> None:
    revision = NewForecastRevision(probability, "  New evidence  ")

    assert revision.probability_percent == probability
    assert revision.rationale == "New evidence"


def test_new_forecast_revision_normalizes_blank_rationale_and_rejects_nul() -> None:
    assert NewForecastRevision(40, "  ").rationale is None

    with pytest.raises(PredictionValidationError) as error_info:
        NewForecastRevision(40, "evidence\x00")

    assert error_info.value.field == "rationale"


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
        current_revision_id=1,
        current_revision_sequence=1,
    )

    with pytest.raises(FrozenInstanceError):
        detail.question = "Rewritten"  # type: ignore[misc]
