from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from reckonsolve.analytics import (
    NumericAnalyticsSource,
    NumericScoringObservation,
    score_numeric_observation,
    summarize_forecast_analytics,
    summarize_numeric_analytics,
)
from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import format_utc
from reckonsolve.data.database import Database
from reckonsolve.domain.analytics import AnalyticsSource
from reckonsolve.domain.predictions import FixedPrecisionValue, PredictionType


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("actual", "contained", "median_error", "width", "interval_score"),
    [
        ("3", True, "4", "18", "18"),
        ("21", True, "14", "18", "18"),
        ("1", False, "6", "18", "38"),
        ("24", False, "17", "18", "48"),
    ],
)
def test_numeric_scores_include_boundaries_and_penalize_each_miss_side(
    actual,
    contained,
    median_error,
    width,
    interval_score,
) -> None:
    scored = score_numeric_observation(
        _observation(1, lower="3", median="7", upper="21", actual=actual, confidence=80)
    )

    assert scored.contained is contained
    assert scored.median_absolute_error == Decimal(median_error)
    assert scored.interval_width == Decimal(width)
    assert scored.interval_score == Decimal(interval_score)


def test_numeric_scores_preserve_signed_fixed_precision_values() -> None:
    scored = score_numeric_observation(
        _observation(
            1,
            lower="-1.25",
            median="0.50",
            upper="2.75",
            actual="3.25",
            confidence=90,
            decimal_places=2,
        )
    )

    assert scored.contained is False
    assert scored.median_absolute_error == Decimal("2.75")
    assert scored.interval_width == Decimal("4.00")
    assert scored.interval_score == Decimal("14.00")


def test_confidence_extremes_have_finite_proper_scores_and_fixed_bins() -> None:
    low = _observation(
        1,
        lower="0",
        median="5",
        upper="10",
        actual="11",
        confidence=1,
    )
    high = _observation(
        2,
        lower="0",
        median="5",
        upper="10",
        actual="11",
        confidence=99,
    )

    snapshot = summarize_numeric_analytics(
        NumericAnalyticsSource(
            observations=(low, high),
            available_tags=(),
            available_units=("days",),
        )
    )

    with localcontext() as context:
        context.prec = 50
        expected_low_score = Decimal(10) + Decimal(200) / Decimal(99)
    assert score_numeric_observation(low).interval_score == expected_low_score
    assert score_numeric_observation(high).interval_score == Decimal(210)
    assert tuple(item.label for item in snapshot.calibration_bins) == (
        "0-9%",
        "10-19%",
        "20-29%",
        "30-39%",
        "40-49%",
        "50-59%",
        "60-69%",
        "70-79%",
        "80-89%",
        "90-100%",
    )
    assert snapshot.calibration_bins[0].count == 1
    assert snapshot.calibration_bins[-1].count == 1
    assert sum(item.count for item in snapshot.calibration_bins) == 2


def test_containment_calibration_combines_units_but_raw_summary_requires_one_unit() -> (
    None
):
    source = NumericAnalyticsSource(
        observations=(
            _observation(
                1,
                lower="0",
                median="5",
                upper="10",
                actual="5",
                confidence=80,
                unit="days",
                tags=("Work",),
            ),
            _observation(
                2,
                lower="100",
                median="150",
                upper="200",
                actual="250",
                confidence=80,
                unit="USD",
                tags=("Work",),
            ),
        ),
        available_tags=("Work",),
        available_units=("days", "USD"),
    )

    all_units = summarize_numeric_analytics(source, tag="work")
    days = summarize_numeric_analytics(source, tag="WORK", unit="days")

    occupied = all_units.calibration_bins[8]
    assert occupied.count == 2
    assert occupied.mean_confidence_percent == Decimal(80)
    assert occupied.observed_containment_percent == Decimal(50)
    assert all_units.unit_summary is None
    assert days.scored_prediction_count == 1
    assert days.calibration_bins[8].observed_containment_percent == Decimal(100)
    assert days.unit_summary is not None
    assert days.unit_summary.unit == "days"
    assert days.unit_summary.mean_median_absolute_error == Decimal(0)
    assert days.unit_summary.mean_interval_width == Decimal(10)
    assert days.unit_summary.mean_interval_score == Decimal(10)


def test_type_aware_summary_keeps_binary_and_numeric_views_separate() -> None:
    numeric_source = NumericAnalyticsSource(
        observations=(_observation(1, tags=("Shared",)),),
        available_tags=("Shared",),
        available_units=("days",),
    )

    all_types = summarize_forecast_analytics(
        AnalyticsSource(observations=(), available_tags=("Binary only",)),
        numeric_source,
    )
    numeric = summarize_forecast_analytics(
        AnalyticsSource(observations=(), available_tags=("Binary only",)),
        numeric_source,
        prediction_type=PredictionType.NUMERIC,
        unit="days",
    )

    assert all_types.available_tags == ("Binary only", "Shared")
    assert all_types.numeric.scored_prediction_count == 1
    assert all_types.numeric.unit_summary is None
    assert numeric.available_tags == ("Shared",)
    assert numeric.numeric.unit_summary is not None
    with pytest.raises(ValueError, match="Choose Numeric"):
        summarize_forecast_analytics(
            AnalyticsSource(observations=(), available_tags=()),
            numeric_source,
            unit="days",
        )


def test_numeric_analytics_rejects_duplicate_and_malformed_observations() -> None:
    observation = _observation(1)
    source = NumericAnalyticsSource(
        observations=(observation, observation),
        available_tags=(),
        available_units=("days",),
    )

    with pytest.raises(ValueError, match="Numeric Prediction.*exactly once"):
        summarize_numeric_analytics(source)
    with pytest.raises(ValueError, match="whole percent"):
        score_numeric_observation(replace(observation, confidence_percent=True))
    with pytest.raises(ValueError, match="one fixed precision"):
        score_numeric_observation(
            replace(
                observation,
                actual_value=FixedPrecisionValue.from_value("7.0", 1),
            )
        )


def test_repository_uses_captured_numeric_revision_once_and_excludes_other_states(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(NOW)).create_numeric_prediction(
        "How many days will the task take?",
        "days",
        0,
        3,
        7,
        21,
        80,
        tags=("Work",),
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=1)),
    ).revise_numeric_forecast(
        created.prediction_id,
        4,
        8,
        20,
        90,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=2)),
    ).resolve_numeric_prediction(
        revised.prediction_id,
        20,
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO numeric_forecast_revisions (
                prediction_id, lower_scaled, median_scaled, upper_scaled,
                confidence_percent, created_at, sequence, rationale
            ) VALUES (?, 0, 0, 0, 50, ?, 3, 'Adversarial post-resolution row')
            """,
            (created.prediction_id, format_utc(NOW + timedelta(hours=3))),
        )
    PredictionOperations(database, FixedClock(NOW)).create_numeric_prediction(
        "How many unresolved items?",
        "items",
        0,
        0,
        1,
        2,
        50,
        tags=("Unresolved",),
    )
    invalid_operations = PredictionOperations(database, FixedClock(NOW))
    invalid = invalid_operations.create_numeric_prediction(
        "How many invalid items?",
        "items",
        0,
        0,
        1,
        2,
        50,
        tags=("Invalid",),
    )
    invalid_operations.invalidate_numeric_prediction(
        invalid.prediction_id,
        expected_revision_id=invalid.current_revision.revision_id,
        expected_metadata_version=invalid.metadata_version,
    )

    snapshot = PredictionOperations(database, FixedClock(NOW)).get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC,
        unit="days",
    )

    assert snapshot.numeric.scored_prediction_count == 1
    scored = snapshot.numeric.scored_predictions[0]
    assert (
        scored.observation.scoring_revision_id == revised.current_revision.revision_id
    )
    assert scored.observation.confidence_percent == 90
    assert scored.observation.actual_value.decimal_value == Decimal(20)
    assert scored.contained is True
    assert snapshot.numeric.available_tags == ("Work",)
    assert snapshot.numeric.available_units == ("days",)
    database.close()


def test_application_rejects_unit_filter_outside_numeric_view(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW))

    with pytest.raises(ValidationError) as error_info:
        operations.get_forecast_analytics(unit="days")

    assert error_info.value.field == "unit"
    database.close()


def _observation(
    identifier: int,
    *,
    lower: str = "3",
    median: str = "7",
    upper: str = "21",
    actual: str = "7",
    confidence: int = 80,
    unit: str = "days",
    tags: tuple[str, ...] = (),
    decimal_places: int = 0,
) -> NumericScoringObservation:
    return NumericScoringObservation(
        prediction_id=identifier,
        question=f"Numeric Prediction {identifier}",
        resolution_id=identifier,
        resolved_at=NOW + timedelta(minutes=identifier),
        scoring_revision_id=identifier,
        unit=unit,
        lower_bound=FixedPrecisionValue.from_value(lower, decimal_places),
        median_estimate=FixedPrecisionValue.from_value(median, decimal_places),
        upper_bound=FixedPrecisionValue.from_value(upper, decimal_places),
        confidence_percent=confidence,
        actual_value=FixedPrecisionValue.from_value(actual, decimal_places),
        tags=tags,
    )
