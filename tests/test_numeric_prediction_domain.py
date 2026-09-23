from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from reckonsolve.domain.predictions import (
    MAX_NUMERIC_SCALED_VALUE,
    FixedPrecisionValue,
    NewNumericResolution,
    NumericResolution,
    PredictionValidationError,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
    QuantileRevision,
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


def test_numeric_definition_normalizes_unit_and_requires_matching_precision() -> None:
    definition = QuantileDefinition("  days  ", 2, NumericValueConstraint.CONTINUOUS)
    assert definition.unit == "days"
    with pytest.raises(PredictionValidationError):
        definition.validate_quantiles(
            FiveQuantiles.from_values({5: 1, 25: 2, 50: 3, 75: 4, 95: 5}, 3)
        )


@pytest.mark.parametrize("unit", ["", "  ", "bad\x00unit", None])
def test_numeric_definition_requires_a_valid_unit(unit: object) -> None:
    with pytest.raises(PredictionValidationError) as error_info:
        QuantileDefinition(unit, 2, NumericValueConstraint.CONTINUOUS)
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
    revision = QuantileRevision(
        1,
        1,
        FiveQuantiles(exact, exact, exact, exact, exact),
        1,
        datetime(2026, 8, 20, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        exact.scaled_value = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        revision.sequence = 2  # type: ignore[misc]
