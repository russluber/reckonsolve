from datetime import UTC, datetime

import pytest

from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    Invalidation,
    InvalidationReasonCorrection,
    NumericResolution,
    NumericResolutionCorrection,
    Resolution,
    ResolutionCorrection,
    TerminalHistoryIntegrityError,
    derive_effective_invalidation,
    derive_effective_numeric_resolution,
    derive_effective_resolution,
)

ORIGINAL_AT = datetime(2026, 8, 20, 12, tzinfo=UTC)
CORRECTED_AT = datetime(2026, 8, 26, 18, tzinfo=UTC)


def test_binary_correction_derives_effective_values_without_rewriting_origin() -> None:
    original = Resolution(
        resolution_id=4,
        prediction_id=2,
        outcome=BinaryOutcome.NO,
        resolved_at=ORIGINAL_AT,
        scoring_revision_id=8,
        scoring_revision_sequence=2,
        scoring_probability_percent=65,
        resolution_notes="Original source",
    )
    correction = ResolutionCorrection(
        correction_id=6,
        prediction_id=2,
        resolution_id=4,
        sequence=1,
        corrected_at=CORRECTED_AT,
        old_outcome=BinaryOutcome.NO,
        new_outcome=BinaryOutcome.YES,
        old_resolution_notes="Original source",
        new_resolution_notes="Correct source",
        old_postmortem=None,
        new_postmortem="I misread the result.",
        changed_fields=("outcome", "resolution_notes", "postmortem"),
        correction_reason="The certified result was Yes.",
    )

    effective = derive_effective_resolution(original, (correction,))

    assert original.outcome is BinaryOutcome.NO
    assert original.resolution_notes == "Original source"
    assert original.postmortem is None
    assert effective.outcome is BinaryOutcome.YES
    assert effective.resolution_notes == "Correct source"
    assert effective.postmortem == "I misread the result."
    assert effective.resolved_at == ORIGINAL_AT
    assert effective.scoring_revision_id == 8


def test_numeric_correction_replays_exact_values_and_multiple_snapshots() -> None:
    original = NumericResolution(
        resolution_id=3,
        prediction_id=9,
        actual_value=FixedPrecisionValue(125, 2),
        resolved_at=ORIGINAL_AT,
        scoring_revision_id=10,
        scoring_revision_sequence=3,
    )
    first = NumericResolutionCorrection(
        correction_id=1,
        prediction_id=9,
        resolution_id=3,
        sequence=1,
        corrected_at=CORRECTED_AT,
        old_actual_value=FixedPrecisionValue(125, 2),
        new_actual_value=FixedPrecisionValue(-250, 2),
        old_resolution_notes=None,
        new_resolution_notes="Measured directly",
        old_postmortem=None,
        new_postmortem=None,
        changed_fields=("actual_value", "resolution_notes"),
        correction_reason="The sign was transcribed incorrectly.",
    )
    second = NumericResolutionCorrection(
        correction_id=2,
        prediction_id=9,
        resolution_id=3,
        sequence=2,
        corrected_at=CORRECTED_AT,
        old_actual_value=FixedPrecisionValue(-250, 2),
        new_actual_value=FixedPrecisionValue(-250, 2),
        old_resolution_notes="Measured directly",
        new_resolution_notes="Measured from the final report",
        old_postmortem=None,
        new_postmortem="My interval missed the lower tail.",
        changed_fields=("resolution_notes", "postmortem"),
    )

    effective = derive_effective_numeric_resolution(original, (first, second))

    assert str(original.actual_value) == "1.25"
    assert str(effective.actual_value) == "-2.50"
    assert effective.resolution_notes == "Measured from the final report"
    assert effective.postmortem == "My interval missed the lower tail."
    assert effective.resolved_at == ORIGINAL_AT
    assert effective.scoring_revision_id == 10


def test_invalidation_reason_corrections_preserve_original_terminal_time() -> None:
    original = Invalidation(5, 4, ORIGINAL_AT, "Wrong wording")
    correction = InvalidationReasonCorrection(
        correction_id=8,
        prediction_id=4,
        invalidation_id=5,
        sequence=1,
        corrected_at=CORRECTED_AT,
        old_reason="Wrong wording",
        new_reason="The quantity became undefined.",
    )

    effective = derive_effective_invalidation(original, (correction,))

    assert original.reason == "Wrong wording"
    assert effective.reason == "The quantity became undefined."
    assert effective.invalidated_at == ORIGINAL_AT


def test_derivation_rejects_a_gap_or_snapshot_that_rewrites_history() -> None:
    original = Resolution(
        resolution_id=4,
        prediction_id=2,
        outcome=BinaryOutcome.NO,
        resolved_at=ORIGINAL_AT,
        scoring_revision_id=8,
        scoring_revision_sequence=2,
        scoring_probability_percent=65,
    )
    inconsistent = ResolutionCorrection(
        correction_id=6,
        prediction_id=2,
        resolution_id=4,
        sequence=2,
        corrected_at=CORRECTED_AT,
        old_outcome=BinaryOutcome.YES,
        new_outcome=BinaryOutcome.NO,
        old_resolution_notes=None,
        new_resolution_notes=None,
        old_postmortem=None,
        new_postmortem=None,
        changed_fields=("outcome",),
        correction_reason="Bad chain",
    )

    with pytest.raises(TerminalHistoryIntegrityError, match="inconsistent"):
        derive_effective_resolution(original, (inconsistent,))
