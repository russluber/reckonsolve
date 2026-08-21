from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from reckonsolve.domain.predictions import (
    MAX_NUMERIC_SCALED_VALUE,
    FixedPrecisionValue,
    NewNumericForecastRevision,
    NewNumericPrediction,
    NewNumericResolution,
    NumericResolution,
    PredictionValidationError,
)


def value(raw: Decimal | int | str, decimal_places: int = 2) -> FixedPrecisionValue:
    return FixedPrecisionValue.from_value(raw, decimal_places)


@pytest.mark.parametrize(
    ("raw", "decimal_places", "scaled", "display"),
    [
        ("-12.345600", 6, -12_345_600, "-12.345600"),
        (0, 0, 0, "0"),
        ("+7", 3, 7_000, "7.000"),
        (Decimal("1.2300"), 2, 123, "1.23"),
    ],
)
def test_fixed_precision_values_round_trip_exactly(
    raw: Decimal | int | str,
    decimal_places: int,
    scaled: int,
    display: str,
) -> None:
    exact = FixedPrecisionValue.from_value(raw, decimal_places)

    assert exact.scaled_value == scaled
    assert str(exact) == display
    assert FixedPrecisionValue(exact.scaled_value, decimal_places) == exact


@pytest.mark.parametrize("decimal_places", [0, 1, 6])
def test_supported_decimal_precision_is_zero_through_six(
    decimal_places: int,
) -> None:
    assert value("1", decimal_places).decimal_places == decimal_places


@pytest.mark.parametrize("decimal_places", [-1, 7, 1.5, True, None])
def test_invalid_decimal_precision_is_rejected(decimal_places: object) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        FixedPrecisionValue.from_value("1", decimal_places)  # type: ignore[arg-type]

    assert error_info.value.field == "decimal_places"


@pytest.mark.parametrize(
    "raw",
    ["1.001", "", "1e3", "NaN", "Infinity", 1.25, True, object()],
)
def test_non_exact_or_overprecise_numeric_input_is_rejected(raw: object) -> None:
    with pytest.raises(PredictionValidationError):
        FixedPrecisionValue.from_value(raw, 2)  # type: ignore[arg-type]


def test_scaled_integer_range_is_bounded_inside_sqlite_integer_capacity() -> None:
    assert FixedPrecisionValue(MAX_NUMERIC_SCALED_VALUE, 6).scaled_value == (
        MAX_NUMERIC_SCALED_VALUE
    )

    with pytest.raises(PredictionValidationError):
        FixedPrecisionValue(MAX_NUMERIC_SCALED_VALUE + 1, 6)


@pytest.mark.parametrize("confidence", [1, 5, 50, 95, 99])
def test_numeric_interval_accepts_inclusive_bounds_and_confidence_endpoints(
    confidence: int,
) -> None:
    revision = NewNumericForecastRevision(
        lower_bound=value("-3.00"),
        median_estimate=value("-3.00"),
        upper_bound=value("9.50"),
        confidence_percent=confidence,
        rationale="  Current evidence  ",
    )

    assert revision.lower_bound == revision.median_estimate
    assert revision.confidence_percent == confidence
    assert revision.rationale == "Current evidence"


@pytest.mark.parametrize("confidence", [0, 100, 50.5, True, None])
def test_numeric_interval_rejects_invalid_confidence(confidence: object) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewNumericForecastRevision(
            value(1),
            value(2),
            value(3),
            confidence,  # type: ignore[arg-type]
        )

    assert error_info.value.field == "confidence_percent"


@pytest.mark.parametrize(
    ("lower", "median", "upper"),
    [(3, 2, 4), (1, 5, 4)],
)
def test_numeric_interval_requires_ordered_bounds(
    lower: int,
    median: int,
    upper: int,
) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewNumericForecastRevision(
            value(lower),
            value(median),
            value(upper),
            80,
        )

    assert error_info.value.field == "interval"


def test_numeric_interval_requires_one_fixed_precision() -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        NewNumericForecastRevision(
            value(1, 0),
            value(2, 1),
            value(3, 0),
            80,
        )

    assert error_info.value.field == "interval"


def test_numeric_prediction_normalizes_definition_and_requires_matching_precision() -> (
    None
):
    revision = NewNumericForecastRevision(value(1), value(2), value(3), 80)
    prediction = NewNumericPrediction(
        "  How many days?  ",
        "  days  ",
        2,
        revision,
    )

    assert prediction.question == "How many days?"
    assert prediction.unit == "days"

    with pytest.raises(PredictionValidationError) as error_info:
        NewNumericPrediction("How many?", "days", 3, revision)

    assert error_info.value.field == "decimal_places"


@pytest.mark.parametrize("unit", ["", "  ", "bad\x00unit", None])
def test_numeric_prediction_requires_a_valid_unit(unit: object) -> None:
    revision = NewNumericForecastRevision(value(1), value(2), value(3), 80)

    with pytest.raises(PredictionValidationError) as error_info:
        NewNumericPrediction("How many?", unit, 2, revision)  # type: ignore[arg-type]

    assert error_info.value.field == "unit"


def test_numeric_resolution_preserves_exact_actual_value_and_normalizes_notes() -> None:
    resolution = NewNumericResolution(
        actual_value=value("123.40"),
        resolution_notes="  Official count  ",
        postmortem="  Too narrow  ",
    )

    assert str(resolution.actual_value) == "123.40"
    assert resolution.resolution_notes == "Official count"
    assert resolution.postmortem == "Too narrow"


def test_persisted_numeric_resolution_is_an_independent_exact_value() -> None:
    resolution = NumericResolution(
        resolution_id=7,
        prediction_id=3,
        actual_value=value("123.40"),
        resolved_at=datetime(2026, 8, 20, 12, tzinfo=UTC),
        scoring_revision_id=11,
        scoring_revision_sequence=2,
        resolution_notes="Official count",
    )

    assert str(resolution.actual_value) == "123.40"
    assert resolution.scoring_revision_sequence == 2

    with pytest.raises(FrozenInstanceError):
        resolution.actual_value = value("124.00")  # type: ignore[misc]


def test_numeric_values_and_revisions_are_immutable() -> None:
    exact = value(1)
    revision = NewNumericForecastRevision(exact, exact, exact, 50)

    with pytest.raises(FrozenInstanceError):
        exact.scaled_value = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        revision.confidence_percent = 60  # type: ignore[misc]
