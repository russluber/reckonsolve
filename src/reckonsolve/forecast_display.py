"""Shared plain-text contract context for desktop and terminal presentations."""

from datetime import datetime

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
