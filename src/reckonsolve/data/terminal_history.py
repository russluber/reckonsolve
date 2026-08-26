"""Append-only terminal correction persistence and effective-value derivation."""

import sqlite3
from datetime import datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    FixedPrecisionValue,
    Invalidation,
    InvalidationHistory,
    InvalidationReasonCorrection,
    NewInvalidationReasonCorrection,
    NewNumericResolutionCorrection,
    NewResolutionCorrection,
    NumericResolution,
    NumericResolutionCorrection,
    NumericResolutionHistory,
    PostmortemCompletion,
    PredictionStatus,
    PredictionType,
    Resolution,
    ResolutionCorrection,
    changed_numeric_resolution_fields,
    changed_resolution_fields,
)

from .database import Database


class TerminalCorrectionContextChangedError(RuntimeError):
    """A correction chain changed after the caller reviewed it."""


class TerminalCorrectionUnchangedError(RuntimeError):
    """A proposed correction changes no effective terminal value."""


class OutcomeCorrectionReasonRequiredError(RuntimeError):
    """A score-affecting outcome correction omitted its explanation."""


class PostmortemCompletionDisallowedError(RuntimeError):
    """A Postmortem cannot be skipped for the current terminal history."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TerminalHistoryRepository:
    """Persist and read immutable terminal correction chains."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_binary_resolution_history(
        self,
        prediction_id: int,
    ) -> BinaryResolutionHistory | None:
        with self._database.transaction() as connection:
            return _select_binary_resolution_history(connection, prediction_id)

    def get_numeric_resolution_history(
        self,
        prediction_id: int,
    ) -> NumericResolutionHistory | None:
        with self._database.transaction() as connection:
            return _select_numeric_resolution_history(connection, prediction_id)

    def get_invalidation_history(
        self,
        prediction_id: int,
    ) -> InvalidationHistory | None:
        with self._database.transaction() as connection:
            return _select_invalidation_history(connection, prediction_id)

    def append_binary_resolution_correction(
        self,
        prediction_id: int,
        proposed: NewResolutionCorrection,
        *,
        expected_correction_id: int | None,
        corrected_at: datetime,
    ) -> BinaryResolutionHistory | None:
        with self._database.transaction() as connection:
            history = _select_binary_resolution_history(connection, prediction_id)
            if history is None:
                return None
            _require_current_token(
                history.current_correction_id, expected_correction_id
            )
            current = history.effective
            changed_fields = changed_resolution_fields(current, proposed)
            if not changed_fields:
                raise TerminalCorrectionUnchangedError
            if "outcome" in changed_fields and proposed.correction_reason is None:
                raise OutcomeCorrectionReasonRequiredError

            cursor = connection.execute(
                """
                INSERT INTO resolution_corrections (
                    prediction_id, resolution_id, sequence,
                    old_outcome, new_outcome,
                    old_resolution_notes, new_resolution_notes,
                    old_postmortem, new_postmortem,
                    outcome_changed, resolution_notes_changed,
                    postmortem_changed, correction_reason, corrected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    current.resolution_id,
                    len(history.corrections) + 1,
                    current.outcome.value,
                    proposed.outcome.value,
                    current.resolution_notes,
                    proposed.resolution_notes,
                    current.postmortem,
                    proposed.postmortem,
                    int("outcome" in changed_fields),
                    int("resolution_notes" in changed_fields),
                    int("postmortem" in changed_fields),
                    proposed.correction_reason,
                    format_utc(corrected_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return a Resolution correction ID."
                )
            updated = _select_binary_resolution_history(connection, prediction_id)
            if updated is None:
                raise sqlite3.DatabaseError(
                    "The corrected Binary Resolution could not be loaded."
                )
            return updated

    def append_numeric_resolution_correction(
        self,
        prediction_id: int,
        proposed: NewNumericResolutionCorrection,
        *,
        expected_correction_id: int | None,
        corrected_at: datetime,
    ) -> NumericResolutionHistory | None:
        with self._database.transaction() as connection:
            history = _select_numeric_resolution_history(connection, prediction_id)
            if history is None:
                return None
            _require_current_token(
                history.current_correction_id, expected_correction_id
            )
            current = history.effective
            changed_fields = changed_numeric_resolution_fields(current, proposed)
            if not changed_fields:
                raise TerminalCorrectionUnchangedError
            if "actual_value" in changed_fields and proposed.correction_reason is None:
                raise OutcomeCorrectionReasonRequiredError

            cursor = connection.execute(
                """
                INSERT INTO numeric_resolution_corrections (
                    prediction_id, numeric_resolution_id, sequence,
                    old_actual_scaled, new_actual_scaled,
                    old_resolution_notes, new_resolution_notes,
                    old_postmortem, new_postmortem,
                    actual_value_changed, resolution_notes_changed,
                    postmortem_changed, correction_reason, corrected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    current.resolution_id,
                    len(history.corrections) + 1,
                    current.actual_value.scaled_value,
                    proposed.actual_value.scaled_value,
                    current.resolution_notes,
                    proposed.resolution_notes,
                    current.postmortem,
                    proposed.postmortem,
                    int("actual_value" in changed_fields),
                    int("resolution_notes" in changed_fields),
                    int("postmortem" in changed_fields),
                    proposed.correction_reason,
                    format_utc(corrected_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return a Numeric Resolution correction ID."
                )
            updated = _select_numeric_resolution_history(connection, prediction_id)
            if updated is None:
                raise sqlite3.DatabaseError(
                    "The corrected Numeric Resolution could not be loaded."
                )
            return updated

    def append_invalidation_reason_correction(
        self,
        prediction_id: int,
        proposed: NewInvalidationReasonCorrection,
        *,
        expected_correction_id: int | None,
        corrected_at: datetime,
    ) -> InvalidationHistory | None:
        with self._database.transaction() as connection:
            history = _select_invalidation_history(connection, prediction_id)
            if history is None:
                return None
            _require_current_token(
                history.current_correction_id, expected_correction_id
            )
            current = history.effective
            if current.reason == proposed.reason:
                raise TerminalCorrectionUnchangedError

            cursor = connection.execute(
                """
                INSERT INTO invalidation_reason_corrections (
                    prediction_id, invalidation_id, sequence,
                    old_reason, new_reason, corrected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    current.invalidation_id,
                    len(history.corrections) + 1,
                    current.reason,
                    proposed.reason,
                    format_utc(corrected_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return an Invalidation correction ID."
                )
            updated = _select_invalidation_history(connection, prediction_id)
            if updated is None:
                raise sqlite3.DatabaseError(
                    "The corrected Invalidation could not be loaded."
                )
            return updated

    def record_postmortem_completion(
        self,
        prediction_id: int,
        *,
        expected_correction_id: int | None,
        completed_at: datetime,
    ) -> PostmortemCompletion | None:
        with self._database.transaction() as connection:
            prediction = connection.execute(
                """
                SELECT prediction_type, status
                FROM predictions
                WHERE id = ?
                """,
                (prediction_id,),
            ).fetchone()
            if prediction is None:
                return None
            if PredictionStatus(prediction["status"]) is not PredictionStatus.RESOLVED:
                raise PostmortemCompletionDisallowedError("not_resolved")

            prediction_type = PredictionType(prediction["prediction_type"])
            if prediction_type is PredictionType.BINARY:
                history = _select_binary_resolution_history(connection, prediction_id)
            else:
                history = _select_numeric_resolution_history(connection, prediction_id)
            if history is None:
                raise sqlite3.DatabaseError(
                    "The resolved Prediction has no type-appropriate Resolution."
                )
            _require_current_token(
                history.current_correction_id, expected_correction_id
            )
            if history.postmortem_completion is not None:
                raise PostmortemCompletionDisallowedError("already_completed")
            if history.effective.postmortem is not None:
                raise PostmortemCompletionDisallowedError("has_postmortem")

            cursor = connection.execute(
                """
                INSERT INTO postmortem_completions (prediction_id, completed_at)
                VALUES (?, ?)
                """,
                (prediction_id, format_utc(completed_at)),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return a Postmortem completion ID."
                )
            return PostmortemCompletion(
                completion_id=int(cursor.lastrowid),
                prediction_id=prediction_id,
                completed_at=completed_at,
            )


def _require_current_token(
    current_correction_id: int | None,
    expected_correction_id: int | None,
) -> None:
    if current_correction_id != expected_correction_id:
        raise TerminalCorrectionContextChangedError


def _select_binary_resolution_history(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> BinaryResolutionHistory | None:
    original_row = connection.execute(
        """
        SELECT
            resolution.id AS resolution_id,
            resolution.prediction_id,
            resolution.outcome,
            resolution.resolved_at,
            resolution.scoring_revision_id,
            resolution.resolution_notes,
            resolution.postmortem,
            revision.sequence AS scoring_revision_sequence,
            revision.probability_percent AS scoring_probability_percent
        FROM resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'binary'
            AND prediction.status = 'resolved'
        JOIN forecast_revisions AS revision
            ON revision.prediction_id = resolution.prediction_id
            AND revision.id = resolution.scoring_revision_id
        WHERE resolution.prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if original_row is None:
        return None
    original = Resolution(
        resolution_id=int(original_row["resolution_id"]),
        prediction_id=int(original_row["prediction_id"]),
        outcome=BinaryOutcome(original_row["outcome"]),
        resolved_at=parse_utc(str(original_row["resolved_at"])),
        scoring_revision_id=int(original_row["scoring_revision_id"]),
        scoring_revision_sequence=int(original_row["scoring_revision_sequence"]),
        scoring_probability_percent=int(original_row["scoring_probability_percent"]),
        resolution_notes=_optional_string(original_row["resolution_notes"]),
        postmortem=_optional_string(original_row["postmortem"]),
    )
    rows = connection.execute(
        """
        SELECT *
        FROM resolution_corrections
        WHERE resolution_id = ?
        ORDER BY sequence
        """,
        (original.resolution_id,),
    ).fetchall()
    corrections = tuple(_map_binary_correction(row) for row in rows)
    return BinaryResolutionHistory(
        original=original,
        corrections=corrections,
        postmortem_completion=_select_postmortem_completion(
            connection,
            prediction_id,
        ),
    )


def _select_numeric_resolution_history(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> NumericResolutionHistory | None:
    original_row = connection.execute(
        """
        SELECT
            resolution.id AS resolution_id,
            resolution.prediction_id,
            resolution.actual_scaled,
            resolution.resolved_at,
            resolution.scoring_revision_id,
            resolution.resolution_notes,
            resolution.postmortem,
            revision.sequence AS scoring_revision_sequence,
            prediction.numeric_precision
        FROM numeric_resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'numeric'
            AND prediction.status = 'resolved'
        JOIN numeric_forecast_revisions AS revision
            ON revision.prediction_id = resolution.prediction_id
            AND revision.id = resolution.scoring_revision_id
        WHERE resolution.prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if original_row is None:
        return None
    decimal_places = int(original_row["numeric_precision"])
    original = NumericResolution(
        resolution_id=int(original_row["resolution_id"]),
        prediction_id=int(original_row["prediction_id"]),
        actual_value=FixedPrecisionValue(
            int(original_row["actual_scaled"]),
            decimal_places,
        ),
        resolved_at=parse_utc(str(original_row["resolved_at"])),
        scoring_revision_id=int(original_row["scoring_revision_id"]),
        scoring_revision_sequence=int(original_row["scoring_revision_sequence"]),
        resolution_notes=_optional_string(original_row["resolution_notes"]),
        postmortem=_optional_string(original_row["postmortem"]),
    )
    rows = connection.execute(
        """
        SELECT *
        FROM numeric_resolution_corrections
        WHERE numeric_resolution_id = ?
        ORDER BY sequence
        """,
        (original.resolution_id,),
    ).fetchall()
    corrections = tuple(_map_numeric_correction(row, decimal_places) for row in rows)
    return NumericResolutionHistory(
        original=original,
        corrections=corrections,
        postmortem_completion=_select_postmortem_completion(
            connection,
            prediction_id,
        ),
    )


def _select_invalidation_history(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> InvalidationHistory | None:
    original_row = connection.execute(
        """
        SELECT invalidation.id AS invalidation_id,
               invalidation.prediction_id,
               invalidation.invalidated_at,
               invalidation.reason
        FROM prediction_invalidations AS invalidation
        JOIN predictions AS prediction
            ON prediction.id = invalidation.prediction_id
            AND prediction.status = 'invalid'
        WHERE invalidation.prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if original_row is None:
        return None
    original = Invalidation(
        invalidation_id=int(original_row["invalidation_id"]),
        prediction_id=int(original_row["prediction_id"]),
        invalidated_at=parse_utc(str(original_row["invalidated_at"])),
        reason=_optional_string(original_row["reason"]),
    )
    rows = connection.execute(
        """
        SELECT *
        FROM invalidation_reason_corrections
        WHERE invalidation_id = ?
        ORDER BY sequence
        """,
        (original.invalidation_id,),
    ).fetchall()
    return InvalidationHistory(
        original=original,
        corrections=tuple(_map_invalidation_correction(row) for row in rows),
    )


def _map_binary_correction(row: sqlite3.Row) -> ResolutionCorrection:
    changed_fields = tuple(
        field
        for field, column in (
            ("outcome", "outcome_changed"),
            ("resolution_notes", "resolution_notes_changed"),
            ("postmortem", "postmortem_changed"),
        )
        if bool(row[column])
    )
    return ResolutionCorrection(
        correction_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        resolution_id=int(row["resolution_id"]),
        sequence=int(row["sequence"]),
        corrected_at=parse_utc(str(row["corrected_at"])),
        old_outcome=BinaryOutcome(row["old_outcome"]),
        new_outcome=BinaryOutcome(row["new_outcome"]),
        old_resolution_notes=_optional_string(row["old_resolution_notes"]),
        new_resolution_notes=_optional_string(row["new_resolution_notes"]),
        old_postmortem=_optional_string(row["old_postmortem"]),
        new_postmortem=_optional_string(row["new_postmortem"]),
        changed_fields=changed_fields,
        correction_reason=_optional_string(row["correction_reason"]),
    )


def _map_numeric_correction(
    row: sqlite3.Row,
    decimal_places: int,
) -> NumericResolutionCorrection:
    changed_fields = tuple(
        field
        for field, column in (
            ("actual_value", "actual_value_changed"),
            ("resolution_notes", "resolution_notes_changed"),
            ("postmortem", "postmortem_changed"),
        )
        if bool(row[column])
    )
    return NumericResolutionCorrection(
        correction_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        resolution_id=int(row["numeric_resolution_id"]),
        sequence=int(row["sequence"]),
        corrected_at=parse_utc(str(row["corrected_at"])),
        old_actual_value=FixedPrecisionValue(
            int(row["old_actual_scaled"]),
            decimal_places,
        ),
        new_actual_value=FixedPrecisionValue(
            int(row["new_actual_scaled"]),
            decimal_places,
        ),
        old_resolution_notes=_optional_string(row["old_resolution_notes"]),
        new_resolution_notes=_optional_string(row["new_resolution_notes"]),
        old_postmortem=_optional_string(row["old_postmortem"]),
        new_postmortem=_optional_string(row["new_postmortem"]),
        changed_fields=changed_fields,
        correction_reason=_optional_string(row["correction_reason"]),
    )


def _map_invalidation_correction(
    row: sqlite3.Row,
) -> InvalidationReasonCorrection:
    return InvalidationReasonCorrection(
        correction_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        invalidation_id=int(row["invalidation_id"]),
        sequence=int(row["sequence"]),
        corrected_at=parse_utc(str(row["corrected_at"])),
        old_reason=_optional_string(row["old_reason"]),
        new_reason=_optional_string(row["new_reason"]),
    )


def _select_postmortem_completion(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> PostmortemCompletion | None:
    row = connection.execute(
        """
        SELECT id, prediction_id, completed_at
        FROM postmortem_completions
        WHERE prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if row is None:
        return None
    return PostmortemCompletion(
        completion_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        completed_at=parse_utc(str(row["completed_at"])),
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
