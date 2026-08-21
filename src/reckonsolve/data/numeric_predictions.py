"""Purpose-specific SQLite access for the M13 numeric foundation."""

import sqlite3
from datetime import date, datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    Invalidation,
    JournalCorrection,
    NewInvalidation,
    NewJournalCorrection,
    NewJournalEntry,
    NewNumericForecastRevision,
    NewNumericPrediction,
    NewNumericResolution,
    NumericForecastRevision,
    NumericForecastTimelineEvent,
    NumericJournalTimelineEvent,
    NumericPrediction,
    NumericResolution,
    NumericTimelineEvent,
    PredictionStatus,
    display_status,
)

from .database import Database
from .predictions import (
    ForecastContextChangedError,
    ForecastRevisionDisallowedError,
    JournalContextChangedError,
    JournalCorrectionContextChangedError,
    JournalEntryDisallowedError,
    LifecycleContextChangedError,
    LifecycleTransitionDisallowedError,
    PredictionDeletionDisallowedError,
    replace_tags,
    select_tags,
)


class NumericForecastRevisionUnchangedError(RuntimeError):
    """Raised when a normal Numeric revision repeats every current value."""


class NumericPredictionRepository:
    """Persist and read Numeric Prediction creation state and intervals."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_prediction(
        self,
        new_prediction: NewNumericPrediction,
        created_at: datetime,
    ) -> NumericPrediction:
        """Insert a numeric Prediction and its first revision atomically."""

        timestamp = format_utc(created_at)
        revision = new_prediction.initial_revision
        with self._database.transaction() as connection:
            prediction_cursor = connection.execute(
                """
                INSERT INTO predictions (
                    question,
                    prediction_type,
                    status,
                    created_at,
                    updated_at,
                    numeric_unit,
                    numeric_precision,
                    background,
                    resolution_criteria,
                    forecast_deadline,
                    expected_resolution
                )
                VALUES (?, 'numeric', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_prediction.question,
                    PredictionStatus.OPEN.value,
                    timestamp,
                    timestamp,
                    new_prediction.unit,
                    new_prediction.decimal_places,
                    new_prediction.background,
                    new_prediction.resolution_criteria,
                    _format_date(new_prediction.forecast_deadline),
                    _format_date(new_prediction.expected_resolution),
                ),
            )
            prediction_id = prediction_cursor.lastrowid
            if prediction_id is None:
                raise sqlite3.DatabaseError("SQLite did not return a prediction ID.")
            replace_tags(connection, prediction_id, new_prediction.tags)

            revision_cursor = connection.execute(
                """
                INSERT INTO numeric_forecast_revisions (
                    prediction_id,
                    lower_scaled,
                    median_scaled,
                    upper_scaled,
                    confidence_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    prediction_id,
                    revision.lower_bound.scaled_value,
                    revision.median_estimate.scaled_value,
                    revision.upper_bound.scaled_value,
                    revision.confidence_percent,
                    timestamp,
                    revision.rationale,
                ),
            )
            if revision_cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a revision ID.")

            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                raise sqlite3.DatabaseError(
                    "The created numeric prediction could not be loaded."
                )
            created = _map_numeric_prediction(
                row,
                select_tags(connection, prediction_id),
            )

        return created

    def get_prediction(self, prediction_id: int) -> NumericPrediction | None:
        """Load one numeric Prediction and its current revision."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            tags = () if row is None else select_tags(connection, prediction_id)
        return None if row is None else _map_numeric_prediction(row, tags)

    def get_latest_prediction(self) -> NumericPrediction | None:
        """Load the newest numeric Prediction and its current revision."""

        with self._database.transaction() as connection:
            prediction_row = connection.execute(
                """
                SELECT id
                FROM predictions
                WHERE prediction_type = 'numeric'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            row = (
                None
                if prediction_row is None
                else _select_numeric_prediction(connection, int(prediction_row["id"]))
            )
            tags = (
                ()
                if row is None
                else select_tags(connection, int(row["prediction_id"]))
            )
        return None if row is None else _map_numeric_prediction(row, tags)

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[NumericForecastRevision, ...] | None:
        """Load numeric revisions in immutable sequence order."""

        with self._database.transaction() as connection:
            prediction_row = connection.execute(
                """
                SELECT numeric_precision
                FROM predictions
                WHERE id = ? AND prediction_type = 'numeric'
                """,
                (prediction_id,),
            ).fetchone()
            if prediction_row is None:
                return None
            decimal_places = int(prediction_row["numeric_precision"])
            rows = connection.execute(
                """
                SELECT
                    id AS revision_id,
                    prediction_id,
                    lower_scaled,
                    median_scaled,
                    upper_scaled,
                    confidence_percent,
                    sequence,
                    created_at AS revision_created_at,
                    rationale
                FROM numeric_forecast_revisions
                WHERE prediction_id = ?
                ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_numeric_revision(row, decimal_places) for row in rows)

    def append_forecast_revision(
        self,
        prediction_id: int,
        new_revision: NewNumericForecastRevision,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        created_at: datetime,
        current_date: date,
    ) -> NumericPrediction | None:
        """Recheck Numeric context and append one changed immutable interval."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                return None
            current = _map_numeric_prediction(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise ForecastContextChangedError
            effective_status = display_status(
                current.status,
                current.forecast_deadline,
                current_date,
            )
            if effective_status is not PredictionStatus.OPEN:
                raise ForecastRevisionDisallowedError(effective_status)
            if _numeric_revisions_equal(current.current_revision, new_revision):
                raise NumericForecastRevisionUnchangedError

            cursor = connection.execute(
                """
                INSERT INTO numeric_forecast_revisions (
                    prediction_id, lower_scaled, median_scaled, upper_scaled,
                    confidence_percent, created_at, sequence, rationale
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    new_revision.lower_bound.scaled_value,
                    new_revision.median_estimate.scaled_value,
                    new_revision.upper_bound.scaled_value,
                    new_revision.confidence_percent,
                    timestamp,
                    current.current_revision.sequence + 1,
                    new_revision.rationale,
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a revision ID.")
            updated_row = _select_numeric_prediction(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError("The revised Numeric Prediction was lost.")
            updated = _map_numeric_prediction(
                updated_row,
                select_tags(connection, prediction_id),
            )
        return updated

    def add_journal_entry(
        self,
        prediction_id: int,
        new_entry: NewJournalEntry,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        created_at: datetime,
        current_date: date,
    ) -> NumericJournalTimelineEvent | None:
        """Append a Numeric Journal entry anchored to the current interval."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                return None
            current = _map_numeric_prediction(row)
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise JournalContextChangedError
            effective_status = display_status(
                current.status,
                current.forecast_deadline,
                current_date,
            )
            if effective_status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
                raise JournalEntryDisallowedError(effective_status)
            cursor = connection.execute(
                """
                INSERT INTO journal_entries (
                    prediction_id, numeric_forecast_revision_id, body, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    current.current_revision.revision_id,
                    new_entry.body,
                    format_utc(created_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a Journal entry ID.")
            event = _select_numeric_journal_event(
                connection,
                prediction_id,
                int(cursor.lastrowid),
                current.decimal_places,
            )
            if event is None:
                raise sqlite3.DatabaseError(
                    "The created Journal entry could not be loaded."
                )
        return event

    def append_journal_correction(
        self,
        prediction_id: int,
        entry_id: int,
        correction: NewJournalCorrection,
        *,
        expected_correction_id: int | None,
        corrected_at: datetime | None,
    ) -> NumericJournalTimelineEvent | None:
        """Append a transparent correction to a Numeric Journal entry."""

        with self._database.transaction() as connection:
            precision_row = connection.execute(
                "SELECT numeric_precision FROM predictions WHERE id = ? AND prediction_type = 'numeric'",
                (prediction_id,),
            ).fetchone()
            if precision_row is None:
                return None
            event = _select_numeric_journal_event(
                connection,
                prediction_id,
                entry_id,
                int(precision_row["numeric_precision"]),
            )
            if event is None:
                return None
            if event.current_correction_id != expected_correction_id:
                raise JournalCorrectionContextChangedError
            if event.body == correction.body:
                return event
            if corrected_at is None:
                raise sqlite3.DatabaseError(
                    "A changed Journal correction needs a timestamp."
                )
            cursor = connection.execute(
                """
                INSERT INTO journal_entry_corrections (
                    prediction_id, journal_entry_id, sequence, body, corrected_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    entry_id,
                    len(event.corrections) + 1,
                    correction.body,
                    format_utc(corrected_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a correction ID.")
            updated = _select_numeric_journal_event(
                connection,
                prediction_id,
                entry_id,
                int(precision_row["numeric_precision"]),
            )
            if updated is None:
                raise sqlite3.DatabaseError(
                    "The corrected Journal entry could not be loaded."
                )
        return updated

    def get_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
    ) -> NumericJournalTimelineEvent | None:
        """Load one Numeric Journal entry and its immutable corrections."""

        with self._database.transaction() as connection:
            precision_row = connection.execute(
                "SELECT numeric_precision FROM predictions WHERE id = ? AND prediction_type = 'numeric'",
                (prediction_id,),
            ).fetchone()
            if precision_row is None:
                return None
            return _select_numeric_journal_event(
                connection,
                prediction_id,
                entry_id,
                int(precision_row["numeric_precision"]),
            )

    def list_timeline(
        self, prediction_id: int
    ) -> tuple[NumericTimelineEvent, ...] | None:
        """Load Numeric revisions and anchored Journal entries in causal order."""

        with self._database.transaction() as connection:
            precision_row = connection.execute(
                "SELECT numeric_precision FROM predictions WHERE id = ? AND prediction_type = 'numeric'",
                (prediction_id,),
            ).fetchone()
            if precision_row is None:
                return None
            precision = int(precision_row["numeric_precision"])
            revision_rows = connection.execute(
                """
                SELECT id AS revision_id, prediction_id, lower_scaled, median_scaled,
                       upper_scaled, confidence_percent, sequence,
                       created_at AS revision_created_at, rationale
                FROM numeric_forecast_revisions WHERE prediction_id = ? ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()
            journal_rows = connection.execute(
                """
                SELECT journal.id AS entry_id, journal.prediction_id, journal.created_at,
                       journal.body AS original_body,
                       revision.id AS numeric_forecast_revision_id,
                       revision.sequence AS forecast_revision_sequence,
                       revision.lower_scaled, revision.median_scaled,
                       revision.upper_scaled, revision.confidence_percent
                FROM journal_entries AS journal
                JOIN numeric_forecast_revisions AS revision
                  ON revision.id = journal.numeric_forecast_revision_id
                 AND revision.prediction_id = journal.prediction_id
                WHERE journal.prediction_id = ?
                """,
                (prediction_id,),
            ).fetchall()
            correction_rows = connection.execute(
                """
                SELECT id, journal_entry_id, body, corrected_at
                FROM journal_entry_corrections WHERE prediction_id = ?
                ORDER BY journal_entry_id, sequence
                """,
                (prediction_id,),
            ).fetchall()

        corrections_by_entry: dict[int, list[JournalCorrection]] = {}
        for row in correction_rows:
            corrections_by_entry.setdefault(int(row["journal_entry_id"]), []).append(
                JournalCorrection(
                    correction_id=int(row["id"]),
                    body=str(row["body"]),
                    corrected_at=parse_utc(str(row["corrected_at"])),
                )
            )
        events: list[NumericTimelineEvent] = []
        previous: NumericForecastRevision | None = None
        for row in revision_rows:
            revision = _map_numeric_revision(row, precision)
            events.append(
                NumericForecastTimelineEvent(
                    revision_id=revision.revision_id,
                    prediction_id=revision.prediction_id,
                    created_at=revision.created_at,
                    sequence=revision.sequence,
                    lower_bound=revision.lower_bound,
                    median_estimate=revision.median_estimate,
                    upper_bound=revision.upper_bound,
                    confidence_percent=revision.confidence_percent,
                    previous_lower_bound=None
                    if previous is None
                    else previous.lower_bound,
                    previous_median_estimate=None
                    if previous is None
                    else previous.median_estimate,
                    previous_upper_bound=None
                    if previous is None
                    else previous.upper_bound,
                    previous_confidence_percent=(
                        None if previous is None else previous.confidence_percent
                    ),
                    rationale=revision.rationale,
                )
            )
            previous = revision
        for row in journal_rows:
            entry_id = int(row["entry_id"])
            events.append(
                _map_numeric_journal_event(
                    row,
                    precision,
                    tuple(corrections_by_entry.get(entry_id, ())),
                )
            )
        return tuple(sorted(events, key=_numeric_timeline_sort_key))

    def resolve_prediction(
        self,
        prediction_id: int,
        resolution: NewNumericResolution,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        resolved_at: datetime,
    ) -> NumericPrediction | None:
        """Record an exact realized value and transaction-current interval."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                return None
            current = _map_numeric_prediction(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            if current.status is not PredictionStatus.OPEN:
                raise LifecycleTransitionDisallowedError(current.status)
            cursor = connection.execute(
                """
                INSERT INTO numeric_resolutions (
                    prediction_id, actual_scaled, resolved_at,
                    scoring_revision_id, resolution_notes, postmortem
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    resolution.actual_value.scaled_value,
                    format_utc(resolved_at),
                    current.current_revision.revision_id,
                    resolution.resolution_notes,
                    resolution.postmortem,
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return a Numeric Resolution ID."
                )
            updated_row = _select_numeric_prediction(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The resolved Numeric Prediction could not be loaded."
                )
            updated = _map_numeric_prediction(
                updated_row,
                select_tags(connection, prediction_id),
            )
        return updated

    def invalidate_prediction(
        self,
        prediction_id: int,
        invalidation: NewInvalidation,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        invalidated_at: datetime,
    ) -> NumericPrediction | None:
        """Preserve an immutable, non-scored Numeric terminal decision."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                return None
            current = _map_numeric_prediction(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            if current.status is not PredictionStatus.OPEN:
                raise LifecycleTransitionDisallowedError(current.status)
            cursor = connection.execute(
                """
                INSERT INTO prediction_invalidations (
                    prediction_id, invalidated_at, reason
                ) VALUES (?, ?, ?)
                """,
                (
                    prediction_id,
                    format_utc(invalidated_at),
                    invalidation.reason,
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return an invalidation ID.")
            updated_row = _select_numeric_prediction(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The invalid Numeric Prediction could not be loaded."
                )
            updated = _map_numeric_prediction(
                updated_row,
                select_tags(connection, prediction_id),
            )
        return updated

    def delete_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        current_date: date,
    ) -> bool:
        """Delete only a transaction-current untouched Open Numeric Prediction."""

        with self._database.transaction() as connection:
            row = _select_numeric_prediction(connection, prediction_id)
            if row is None:
                return False
            current = _map_numeric_prediction(row)
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            effective_status = display_status(
                current.status,
                current.forecast_deadline,
                current_date,
            )
            if effective_status is not PredictionStatus.OPEN:
                raise PredictionDeletionDisallowedError(effective_status.value)
            if not current.deletion_allowed:
                raise PredictionDeletionDisallowedError("meaningful_history")
            connection.execute(
                "DELETE FROM predictions WHERE id = ? AND prediction_type = 'numeric'",
                (prediction_id,),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise LifecycleContextChangedError
        return True


_NUMERIC_PREDICTION_SELECT = """
SELECT
    prediction.id AS prediction_id,
    prediction.question,
    prediction.status,
    prediction.created_at,
    prediction.updated_at,
    prediction.numeric_unit,
    prediction.numeric_precision,
    prediction.metadata_version,
    prediction.background,
    prediction.resolution_criteria,
    prediction.forecast_deadline,
    prediction.expected_resolution,
    current_revision.id AS revision_id,
    current_revision.lower_scaled,
    current_revision.median_scaled,
    current_revision.upper_scaled,
    current_revision.confidence_percent,
    current_revision.sequence,
    current_revision.created_at AS revision_created_at,
    current_revision.rationale
    , numeric_resolution.id AS numeric_resolution_id
    , numeric_resolution.actual_scaled AS resolution_actual_scaled
    , numeric_resolution.resolved_at
    , numeric_resolution.scoring_revision_id
    , numeric_resolution.resolution_notes
    , numeric_resolution.postmortem
    , scoring_revision.sequence AS scoring_revision_sequence
    , invalidation.id AS invalidation_id
    , invalidation.invalidated_at
    , invalidation.reason AS invalidation_reason
    , (
        prediction.status = 'open'
        AND prediction.metadata_version = 1
        AND current_revision.sequence = 1
        AND NOT EXISTS (
            SELECT 1 FROM journal_entries WHERE prediction_id = prediction.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM prediction_definition_changes
            WHERE prediction_id = prediction.id
        )
    ) AS deletion_allowed
FROM predictions AS prediction
JOIN numeric_forecast_revisions AS current_revision
    ON current_revision.id = (
        SELECT candidate.id
        FROM numeric_forecast_revisions AS candidate
        WHERE candidate.prediction_id = prediction.id
        ORDER BY candidate.sequence DESC
        LIMIT 1
    )
LEFT JOIN numeric_resolutions AS numeric_resolution
    ON numeric_resolution.prediction_id = prediction.id
LEFT JOIN numeric_forecast_revisions AS scoring_revision
    ON scoring_revision.prediction_id = numeric_resolution.prediction_id
    AND scoring_revision.id = numeric_resolution.scoring_revision_id
LEFT JOIN prediction_invalidations AS invalidation
    ON invalidation.prediction_id = prediction.id
WHERE prediction.id = ? AND prediction.prediction_type = 'numeric'
"""


def _select_numeric_prediction(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        _NUMERIC_PREDICTION_SELECT,
        (prediction_id,),
    ).fetchone()


def _map_numeric_prediction(
    row: sqlite3.Row,
    tags: tuple[str, ...] = (),
) -> NumericPrediction:
    decimal_places = int(row["numeric_precision"])
    return NumericPrediction(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        unit=str(row["numeric_unit"]),
        decimal_places=decimal_places,
        status=PredictionStatus(row["status"]),
        created_at=parse_utc(str(row["created_at"])),
        updated_at=parse_utc(str(row["updated_at"])),
        current_revision=_map_numeric_revision(row, decimal_places),
        background=_optional_string(row["background"]),
        resolution_criteria=_optional_string(row["resolution_criteria"]),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        expected_resolution=_parse_date(row["expected_resolution"]),
        tags=tags,
        metadata_version=int(row["metadata_version"]),
        resolution=_map_numeric_resolution(row, decimal_places),
        invalidation=_map_invalidation(row),
        deletion_allowed=bool(row["deletion_allowed"]),
    )


def _map_numeric_revision(
    row: sqlite3.Row,
    decimal_places: int,
) -> NumericForecastRevision:
    return NumericForecastRevision(
        revision_id=int(row["revision_id"]),
        prediction_id=int(row["prediction_id"]),
        lower_bound=FixedPrecisionValue(
            int(row["lower_scaled"]),
            decimal_places,
        ),
        median_estimate=FixedPrecisionValue(
            int(row["median_scaled"]),
            decimal_places,
        ),
        upper_bound=FixedPrecisionValue(
            int(row["upper_scaled"]),
            decimal_places,
        ),
        confidence_percent=int(row["confidence_percent"]),
        sequence=int(row["sequence"]),
        created_at=parse_utc(str(row["revision_created_at"])),
        rationale=None if row["rationale"] is None else str(row["rationale"]),
    )


def _map_numeric_resolution(
    row: sqlite3.Row,
    decimal_places: int,
) -> NumericResolution | None:
    if row["numeric_resolution_id"] is None:
        return None
    return NumericResolution(
        resolution_id=int(row["numeric_resolution_id"]),
        prediction_id=int(row["prediction_id"]),
        actual_value=FixedPrecisionValue(
            int(row["resolution_actual_scaled"]),
            decimal_places,
        ),
        resolved_at=parse_utc(str(row["resolved_at"])),
        scoring_revision_id=int(row["scoring_revision_id"]),
        scoring_revision_sequence=int(row["scoring_revision_sequence"]),
        resolution_notes=_optional_string(row["resolution_notes"]),
        postmortem=_optional_string(row["postmortem"]),
    )


def _map_invalidation(row: sqlite3.Row) -> Invalidation | None:
    if row["invalidation_id"] is None:
        return None
    return Invalidation(
        invalidation_id=int(row["invalidation_id"]),
        prediction_id=int(row["prediction_id"]),
        invalidated_at=parse_utc(str(row["invalidated_at"])),
        reason=_optional_string(row["invalidation_reason"]),
    )


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _numeric_revisions_equal(
    current: NumericForecastRevision,
    proposed: NewNumericForecastRevision,
) -> bool:
    return (
        current.lower_bound == proposed.lower_bound
        and current.median_estimate == proposed.median_estimate
        and current.upper_bound == proposed.upper_bound
        and current.confidence_percent == proposed.confidence_percent
    )


def _select_numeric_journal_event(
    connection: sqlite3.Connection,
    prediction_id: int,
    entry_id: int,
    decimal_places: int,
) -> NumericJournalTimelineEvent | None:
    row = connection.execute(
        """
        SELECT journal.id AS entry_id, journal.prediction_id, journal.created_at,
               journal.body AS original_body,
               revision.id AS numeric_forecast_revision_id,
               revision.sequence AS forecast_revision_sequence,
               revision.lower_scaled, revision.median_scaled,
               revision.upper_scaled, revision.confidence_percent
        FROM journal_entries AS journal
        JOIN numeric_forecast_revisions AS revision
          ON revision.id = journal.numeric_forecast_revision_id
         AND revision.prediction_id = journal.prediction_id
        WHERE journal.prediction_id = ? AND journal.id = ?
        """,
        (prediction_id, entry_id),
    ).fetchone()
    if row is None:
        return None
    correction_rows = connection.execute(
        """
        SELECT id, body, corrected_at FROM journal_entry_corrections
        WHERE prediction_id = ? AND journal_entry_id = ? ORDER BY sequence
        """,
        (prediction_id, entry_id),
    ).fetchall()
    corrections = tuple(
        JournalCorrection(
            correction_id=int(correction["id"]),
            body=str(correction["body"]),
            corrected_at=parse_utc(str(correction["corrected_at"])),
        )
        for correction in correction_rows
    )
    return _map_numeric_journal_event(row, decimal_places, corrections)


def _map_numeric_journal_event(
    row: sqlite3.Row,
    decimal_places: int,
    corrections: tuple[JournalCorrection, ...],
) -> NumericJournalTimelineEvent:
    return NumericJournalTimelineEvent(
        entry_id=int(row["entry_id"]),
        prediction_id=int(row["prediction_id"]),
        created_at=parse_utc(str(row["created_at"])),
        body=corrections[-1].body if corrections else str(row["original_body"]),
        original_body=str(row["original_body"]),
        numeric_forecast_revision_id=int(row["numeric_forecast_revision_id"]),
        forecast_revision_sequence=int(row["forecast_revision_sequence"]),
        lower_bound=FixedPrecisionValue(int(row["lower_scaled"]), decimal_places),
        median_estimate=FixedPrecisionValue(int(row["median_scaled"]), decimal_places),
        upper_bound=FixedPrecisionValue(int(row["upper_scaled"]), decimal_places),
        confidence_percent=int(row["confidence_percent"]),
        current_correction_id=None
        if not corrections
        else corrections[-1].correction_id,
        corrections=corrections,
    )


def _numeric_timeline_sort_key(event: NumericTimelineEvent) -> tuple[int, int, int]:
    if isinstance(event, NumericForecastTimelineEvent):
        return event.sequence, 0, event.revision_id
    return event.forecast_revision_sequence, 1, event.entry_id
