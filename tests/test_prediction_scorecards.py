from datetime import UTC, datetime
from decimal import Decimal

import pytest

from reckonsolve.analytics import binary_scorecard, numeric_scorecard
from reckonsolve.domain.analytics import NumericScoringObservation, ScoringObservation
from reckonsolve.domain.predictions import BinaryOutcome, FixedPrecisionValue

RESOLVED = datetime(2026, 8, 26, 12, tzinfo=UTC)


def test_binary_scorecard_uses_effective_corrected_outcome_once() -> None:
    scorecard = binary_scorecard(
        ScoringObservation(
            prediction_id=8,
            question="Will the final result be Yes?",
            resolution_id=14,
            resolved_at=RESOLVED,
            scoring_revision_id=11,
            probability_percent=80,
            outcome=BinaryOutcome.NO,
            outcome_corrected=True,
        )
    )

    assert scorecard.scoring_revision_id == 11
    assert scorecard.probability_percent == 80
    assert scorecard.outcome is BinaryOutcome.NO
    assert scorecard.brier_score == pytest.approx(0.64)
    assert scorecard.outcome_corrected is True


def test_numeric_scorecard_treats_interval_endpoints_as_contained() -> None:
    scorecard = numeric_scorecard(
        _numeric_observation(actual_scaled=100, actual_value_corrected=True)
    )

    assert str(scorecard.lower_bound) == "1.00"
    assert str(scorecard.upper_bound) == "3.00"
    assert str(scorecard.actual_value) == "1.00"
    assert scorecard.contained is True
    assert scorecard.median_absolute_error == Decimal("1.00")
    assert scorecard.interval_width == Decimal("2.00")
    assert scorecard.interval_score == Decimal("2.00")
    assert scorecard.actual_value_corrected is True


def test_numeric_scorecard_exposes_missed_outcome_metrics_in_exact_unit() -> None:
    scorecard = numeric_scorecard(_numeric_observation(actual_scaled=400))

    assert scorecard.contained is False
    assert scorecard.median_absolute_error == Decimal("2.00")
    assert scorecard.interval_width == Decimal("2.00")
    assert scorecard.interval_score == Decimal("12.00")
    assert scorecard.unit == "hours"


def _numeric_observation(
    *,
    actual_scaled: int,
    actual_value_corrected: bool = False,
) -> NumericScoringObservation:
    return NumericScoringObservation(
        prediction_id=8,
        question="How many hours?",
        resolution_id=14,
        resolved_at=RESOLVED,
        scoring_revision_id=11,
        unit="hours",
        lower_bound=FixedPrecisionValue(100, 2),
        median_estimate=FixedPrecisionValue(200, 2),
        upper_bound=FixedPrecisionValue(300, 2),
        confidence_percent=80,
        actual_value=FixedPrecisionValue(actual_scaled, 2),
        actual_value_corrected=actual_value_corrected,
    )
