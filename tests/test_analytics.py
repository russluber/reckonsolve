"""Shared Brier mathematics; current aggregates are tested with canonical trajectories."""

import pytest

from reckonsolve.analytics import brier_score
from reckonsolve.domain.predictions import BinaryOutcome


@pytest.mark.parametrize(
    ("probability", "outcome", "expected"),
    [
        (0, BinaryOutcome.NO, 0.0),
        (0, BinaryOutcome.YES, 1.0),
        (30, BinaryOutcome.NO, 0.09),
        (70, BinaryOutcome.YES, 0.09),
        (100, BinaryOutcome.YES, 0.0),
        (100, BinaryOutcome.NO, 1.0),
    ],
)
def test_binary_brier_score(probability, outcome, expected) -> None:
    assert brier_score(probability, outcome) == pytest.approx(expected)


@pytest.mark.parametrize("probability", [-1, 101, 50.5, True])
def test_brier_score_rejects_invalid_probability(probability) -> None:
    with pytest.raises(ValueError, match="whole number"):
        brier_score(probability, BinaryOutcome.YES)
