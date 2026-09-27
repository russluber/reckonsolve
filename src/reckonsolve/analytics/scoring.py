"""Shared binary Brier mathematics and final-probability calibration bins."""

from dataclasses import dataclass
from fractions import Fraction

from reckonsolve.domain.predictions import BinaryOutcome


def exact_brier_score(probability_percent: int, outcome: BinaryOutcome) -> Fraction:
    """Shared exact Brier loss for trajectory and One-Shot contracts."""
    if type(probability_percent) is not int or not 0 <= probability_percent <= 100:
        raise ValueError("Probability must be a whole number from 0 through 100.")
    if not isinstance(outcome, BinaryOutcome):
        raise TypeError("Outcome must be Yes or No.")
    return (Fraction(probability_percent, 100) - int(outcome is BinaryOutcome.YES)) ** 2


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One fixed calibration band, occupied or empty."""

    lower_percent: int
    upper_percent: int
    count: int
    mean_forecast_percent: float | None
    observed_yes_percent: float | None

    @property
    def label(self) -> str:
        """Return the exact inclusive whole-number range shown to the user."""

        return f"{self.lower_percent}-{self.upper_percent}%"


def brier_score(probability_percent: int, outcome: BinaryOutcome) -> float:
    """Calculate binary Brier loss on the 0-through-1 scale."""

    if (
        isinstance(probability_percent, bool)
        or not isinstance(probability_percent, int)
        or not 0 <= probability_percent <= 100
    ):
        raise ValueError("Probability must be a whole number from 0 through 100.")
    if not isinstance(outcome, BinaryOutcome):
        raise TypeError("Outcome must be Yes or No.")
    probability = probability_percent / 100
    observed = 1.0 if outcome is BinaryOutcome.YES else 0.0
    return (probability - observed) ** 2
