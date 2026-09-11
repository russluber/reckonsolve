"""Shared plain-text contract context for desktop and terminal presentations."""

from datetime import datetime

from reckonsolve.analytics.trajectory import TrajectoryScorecard
from reckonsolve.domain.forecast_contracts import ForecastContract


def format_local_deadline(value: datetime) -> str:
    """Show date and minute with an offset; retain exact instants in storage."""
    return value.astimezone().isoformat(sep=" ", timespec="minutes")


def binary_contract_summary(contract: ForecastContract | None) -> str:
    if contract is None or contract.is_legacy:
        return "Legacy Binary"
    assert contract.forecast_deadline is not None
    deadline = format_local_deadline(contract.forecast_deadline.instant)
    return f"Trajectory Binary; Deadline {deadline} (permanent)"


def trajectory_diagnostics(card: TrajectoryScorecard) -> tuple[str, ...]:
    """Format shared derived diagnostics; no scoring rules live in either UI."""
    if card.unscored_reason:
        return (card.unscored_reason,)
    return (
        f"Initial Brier: {float(card.initial_brier):.4f}",
        f"Final Brier: {float(card.final_brier):.4f}",
        f"Hold-initial Trajectory Brier: {float(card.hold_initial_brier):.4f}",
        f"Updating Gain: {float(card.updating_gain):+.4f}",
        f"Active Forecast Fraction: {float(card.active_forecast_fraction):.1%}",
        "Updating Gain is mechanical hindsight, not proof of forecasting skill.",
        "Early resolution gives the remaining planned window neutral loss 0.25; no forecast is added.",
    )
