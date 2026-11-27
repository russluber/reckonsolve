"""Reflection-only commands preserve every other effective terminal fact."""

from __future__ import annotations

from typing import TYPE_CHECKING

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.one_shot import OneShotDetail
from reckonsolve.domain.predictions import (
    BinaryResolutionHistory,
    NumericResolutionHistory,
)

if TYPE_CHECKING:
    from reckonsolve.application.predictions import PredictionOperations


def save_postmortem(
    operations: PredictionOperations,
    expected: BinaryResolutionHistory | NumericResolutionHistory | OneShotDetail,
    body: str | None,
    *,
    confirm_clear: bool = False,
    correction_reason: str | None = None,
) -> BinaryResolutionHistory | NumericResolutionHistory | OneShotDetail:
    """Delegate atomic revalidation; never infer a new forecast or legacy intent."""
    body = body.strip() if body is not None and body.strip() else None
    current = (
        expected.record.effective
        if isinstance(expected, OneShotDetail)
        else expected.effective
    )
    if body == current.postmortem:
        raise ApplicationError("The Postmortem is unchanged.")
    if body is None and not confirm_clear:
        raise ApplicationError("Confirm clearing the Postmortem before saving.")
    if isinstance(expected, OneShotDetail):
        return operations.one_shots.save_postmortem(
            expected, body, confirm_clear=confirm_clear, note=correction_reason
        )
    arguments = {
        "resolution_notes": current.resolution_notes,
        "postmortem": body,
        "effective_resolution_at": current.effective_resolution_at,
        "expected_correction_id": expected.current_correction_id,
        "correction_reason": correction_reason,
    }
    if isinstance(expected, BinaryResolutionHistory):
        return operations.correct_binary_resolution(
            current.prediction_id, current.outcome, **arguments
        )
    return operations.correct_numeric_resolution(
        current.prediction_id, str(current.actual_value), **arguments
    )
