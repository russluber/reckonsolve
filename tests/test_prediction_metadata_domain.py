from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from reckonsolve.domain.forecast_contracts import (
    ForecastDeadline,
    contract_status,
    prospective_contract,
)
from reckonsolve.domain.predictions import (
    PredictionMetadataUpdate,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
)


def test_metadata_update_normalizes_optional_text_and_tags() -> None:
    update = PredictionMetadataUpdate(
        question="  Will it happen?  ",
        background="   ",
        resolution_criteria="  Certified result  ",
        tags=(" Science ", "science", "SCIENCE", "", "Personal"),
    )

    assert update.question == "Will it happen?"
    assert update.background is None
    assert update.resolution_criteria == "Certified result"
    assert update.tags == ("Science", "Personal")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("forecast_deadline", datetime(2027, 1, 1, tzinfo=UTC)),
        ("expected_resolution", "2027-01-01"),
        ("forecast_deadline", date(1752, 9, 13)),
    ],
)
def test_metadata_update_rejects_invalid_date_values(field: str, value: Any) -> None:
    values = {"forecast_deadline": None, "expected_resolution": None, field: value}

    with pytest.raises(PredictionValidationError) as error_info:
        PredictionMetadataUpdate(question="Question?", **values)

    assert error_info.value.field == field


def test_metadata_update_accepts_the_supported_date_boundaries() -> None:
    update = PredictionMetadataUpdate(
        question="Question?",
        forecast_deadline=date(1752, 9, 14),
        expected_resolution=date(9999, 12, 31),
    )

    assert update.forecast_deadline == date(1752, 9, 14)
    assert update.expected_resolution == date(9999, 12, 31)


@pytest.mark.parametrize("tag", ["policy,macro", "line\nbreak", "line\rbreak"])
def test_metadata_update_rejects_tag_delimiters_it_cannot_round_trip(tag: str) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        PredictionMetadataUpdate(question="Question?", tags=(tag,))

    assert error_info.value.field == "tags"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", "Question\x00?"),
        ("background", "Context\x00"),
        ("resolution_criteria", "Criterion\x00"),
        ("tags", ("tag\x00",)),
    ],
)
def test_metadata_update_rejects_nul_text(field: str, value: Any) -> None:
    values: dict[str, Any] = {
        "question": "Question?",
        "background": None,
        "resolution_criteria": None,
        "tags": (),
    }
    values[field] = value

    with pytest.raises(PredictionValidationError) as error_info:
        PredictionMetadataUpdate(**values)

    assert error_info.value.field == field


def test_exact_deadline_locks_at_the_instant_without_changing_terminal_status() -> None:
    deadline = datetime(2027, 1, 2, 12, tzinfo=UTC)
    contract = prospective_contract(PredictionType.BINARY, ForecastDeadline(deadline))
    for status, instant, expected in (
        (
            PredictionStatus.OPEN,
            deadline - timedelta(microseconds=1),
            PredictionStatus.OPEN,
        ),
        (PredictionStatus.OPEN, deadline, PredictionStatus.LOCKED),
        (PredictionStatus.RESOLVED, deadline, PredictionStatus.RESOLVED),
    ):
        assert contract_status(status, contract, instant) is expected
