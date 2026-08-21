"""Purpose-specific SQLite access for binary predictions."""

import sqlite3
from datetime import date, datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.attention import DashboardPrediction
from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    DefinitionChange,
    FixedPrecisionValue,
    ForecastRevision,
    ForecastTimelineEvent,
    Invalidation,
    JournalCorrection,
    JournalTimelineEvent,
    NewForecastRevision,
    NewInvalidation,
    NewJournalCorrection,
    NewJournalEntry,
    NewPrediction,
    NewResolution,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionStatus,
    PredictionType,
    Resolution,
    TimelineEvent,
    changed_definition_fields,
    display_status,
    metadata_would_change,
)

from .database import Database


class PredictionChangedError(RuntimeError):
    """Raised when metadata changed after the application reviewed it."""


class ForecastContextChangedError(RuntimeError):
    """Raised when a revision form no longer matches current prediction state."""


class ForecastRevisionUnchangedError(RuntimeError):
    """Raised when a normal revision repeats the current probability."""


class ForecastRevisionDisallowedError(RuntimeError):
    """Raised when lifecycle state rejects a normal forecast revision."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class JournalContextChangedError(RuntimeError):
    """Raised when a Journal form no longer matches current prediction state."""


class JournalEntryDisallowedError(RuntimeError):
    """Raised when lifecycle state rejects a new Journal entry."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class JournalCorrectionContextChangedError(RuntimeError):
    """Raised when a Journal correction no longer matches current edit history."""


class LifecycleContextChangedError(RuntimeError):
    """Raised when a terminal action no longer matches reviewed prediction state."""


class LifecycleTransitionDisallowedError(RuntimeError):
    """Raised when a terminal action targets an already-terminal prediction."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class PredictionDeletionDisallowedError(RuntimeError):
    """Raised when a prediction no longer qualifies as untouched Open junk."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PredictionRepository:
    """Persist and query predictions without exposing table-level CRUD."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_prediction(
        self,
        new_prediction: NewPrediction,
        created_at: datetime,
    ) -> PredictionDetail:
        """Insert a prediction and sequence-one revision in one transaction."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            prediction_cursor = connection.execute(
                """
                INSERT INTO predictions (
                    question,
                    prediction_type,
                    status,
                    created_at,
                    updated_at,
                    background,
                    resolution_criteria,
                    forecast_deadline,
                    expected_resolution
                )
                VALUES (?, 'binary', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_prediction.question,
                    PredictionStatus.OPEN.value,
                    timestamp,
                    timestamp,
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
            connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id,
                    probability_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    prediction_id,
                    new_prediction.probability_percent,
                    timestamp,
                    new_prediction.rationale,
                ),
            )
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                raise sqlite3.DatabaseError(
                    "The created prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                row,
                select_tags(connection, prediction_id),
            )

        return detail

    def append_forecast_revision(
        self,
        prediction_id: int,
        new_revision: NewForecastRevision,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        created_at: datetime,
        current_date: date,
    ) -> PredictionDetail | None:
        """Recheck reviewed state and append exactly one immutable revision."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision_id != expected_revision_id
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
            if current.probability_percent == new_revision.probability_percent:
                raise ForecastRevisionUnchangedError

            revision_cursor = connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id,
                    probability_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    new_revision.probability_percent,
                    timestamp,
                    current.current_revision_sequence + 1,
                    new_revision.rationale,
                ),
            )
            if revision_cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a revision ID.")

            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The revised prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                updated_row,
                select_tags(connection, prediction_id),
            )

        return detail

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[ForecastRevision, ...] | None:
        """Load immutable forecast revisions in sequence order."""

        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                """
                SELECT
                    id,
                    prediction_id,
                    probability_percent,
                    sequence,
                    created_at,
                    rationale
                FROM forecast_revisions
                WHERE prediction_id = ?
                ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_forecast_revision(row) for row in rows)

    def add_journal_entry(
        self,
        prediction_id: int,
        new_entry: NewJournalEntry,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        created_at: datetime,
    ) -> JournalTimelineEvent | None:
        """Capture the transaction-current revision and append one Journal entry."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(row)
            if (
                current.current_revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise JournalContextChangedError
            if current.status is not PredictionStatus.OPEN:
                raise JournalEntryDisallowedError(current.status)

            cursor = connection.execute(
                """
                INSERT INTO journal_entries (
                    prediction_id,
                    forecast_revision_id,
                    body,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    current.current_revision_id,
                    new_entry.body,
                    timestamp,
                ),
            )
            entry_id = cursor.lastrowid
            if entry_id is None:
                raise sqlite3.DatabaseError("SQLite did not return a Journal entry ID.")
            entry = _select_journal_event(connection, prediction_id, entry_id)
            if entry is None:
                raise sqlite3.DatabaseError(
                    "The created Journal entry could not be loaded."
                )

        return entry

    def get_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
    ) -> JournalTimelineEvent | None:
        """Load one Journal entry with all immutable correction versions."""

        with self._database.transaction() as connection:
            return _select_journal_event(connection, prediction_id, entry_id)

    def append_journal_correction(
        self,
        prediction_id: int,
        entry_id: int,
        correction: NewJournalCorrection,
        *,
        expected_correction_id: int | None,
        corrected_at: datetime | None,
    ) -> JournalTimelineEvent | None:
        """Recheck correction history and append a new body version."""

        with self._database.transaction() as connection:
            current = _select_journal_event(connection, prediction_id, entry_id)
            if current is None:
                return None
            if current.current_correction_id != expected_correction_id:
                raise JournalCorrectionContextChangedError
            if current.body == correction.body:
                return current
            if corrected_at is None:
                raise sqlite3.DatabaseError(
                    "A changed Journal correction requires a timestamp."
                )

            cursor = connection.execute(
                """
                INSERT INTO journal_entry_corrections (
                    prediction_id,
                    journal_entry_id,
                    sequence,
                    body,
                    corrected_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    entry_id,
                    len(current.corrections) + 1,
                    correction.body,
                    format_utc(corrected_at),
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError(
                    "SQLite did not return a Journal correction ID."
                )
            updated = _select_journal_event(connection, prediction_id, entry_id)
            if updated is None:
                raise sqlite3.DatabaseError(
                    "The corrected Journal entry could not be loaded."
                )

        return updated

    def resolve_prediction(
        self,
        prediction_id: int,
        resolution: NewResolution,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        resolved_at: datetime,
    ) -> PredictionDetail | None:
        """Capture the current scoring revision and terminal outcome atomically."""

        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            if current.status is not PredictionStatus.OPEN:
                raise LifecycleTransitionDisallowedError(current.status)

            cursor = connection.execute(
                """
                INSERT INTO resolutions (
                    prediction_id,
                    outcome,
                    resolved_at,
                    scoring_revision_id,
                    resolution_notes,
                    postmortem
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    resolution.outcome.value,
                    format_utc(resolved_at),
                    current.current_revision_id,
                    resolution.resolution_notes,
                    resolution.postmortem,
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a resolution ID.")
            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The resolved prediction could not be loaded."
                )
            updated = _map_prediction_detail(
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
    ) -> PredictionDetail | None:
        """Preserve an immutable non-scored terminal decision atomically."""

        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.current_revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            if current.status is not PredictionStatus.OPEN:
                raise LifecycleTransitionDisallowedError(current.status)

            cursor = connection.execute(
                """
                INSERT INTO prediction_invalidations (
                    prediction_id,
                    invalidated_at,
                    reason
                )
                VALUES (?, ?, ?)
                """,
                (
                    prediction_id,
                    format_utc(invalidated_at),
                    invalidation.reason,
                ),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return an invalidation ID.")
            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The invalid prediction could not be loaded."
                )
            updated = _map_prediction_detail(
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
        """Delete only a transaction-current untouched Open prediction."""

        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return False
            current = _map_prediction_detail(row)
            if (
                current.current_revision_id != expected_revision_id
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
                "DELETE FROM predictions WHERE id = ?",
                (prediction_id,),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise LifecycleContextChangedError

        return True

    def list_timeline(
        self,
        prediction_id: int,
    ) -> tuple[TimelineEvent, ...] | None:
        """Load forecast and Journal events in deterministic causal order."""

        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
            if exists is None:
                return None
            revision_rows = connection.execute(
                """
                SELECT
                    id,
                    prediction_id,
                    probability_percent,
                    sequence,
                    created_at,
                    rationale
                FROM forecast_revisions
                WHERE prediction_id = ?
                ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()
            journal_rows = connection.execute(
                """
                SELECT
                    journal.id AS entry_id,
                    journal.prediction_id,
                    journal.created_at,
                    journal.body AS original_body,
                    revision.id AS forecast_revision_id,
                    revision.sequence AS forecast_revision_sequence,
                    revision.probability_percent AS forecast_probability_percent
                FROM journal_entries AS journal
                JOIN forecast_revisions AS revision
                    ON revision.id = journal.forecast_revision_id
                    AND revision.prediction_id = journal.prediction_id
                WHERE journal.prediction_id = ?
                """,
                (prediction_id,),
            ).fetchall()
            correction_rows = connection.execute(
                """
                SELECT
                    id,
                    journal_entry_id,
                    body,
                    corrected_at
                FROM journal_entry_corrections
                WHERE prediction_id = ?
                ORDER BY journal_entry_id, sequence
                """,
                (prediction_id,),
            ).fetchall()

        corrections_by_entry: dict[int, list[JournalCorrection]] = {}
        for row in correction_rows:
            corrections_by_entry.setdefault(int(row["journal_entry_id"]), []).append(
                _map_journal_correction(row)
            )

        events: list[TimelineEvent] = []
        previous_probability: int | None = None
        for row in revision_rows:
            probability = int(row["probability_percent"])
            events.append(
                ForecastTimelineEvent(
                    revision_id=int(row["id"]),
                    prediction_id=int(row["prediction_id"]),
                    created_at=parse_utc(str(row["created_at"])),
                    sequence=int(row["sequence"]),
                    probability_percent=probability,
                    previous_probability_percent=previous_probability,
                    rationale=_optional_string(row["rationale"]),
                )
            )
            previous_probability = probability
        for row in journal_rows:
            entry_id = int(row["entry_id"])
            events.append(
                _map_journal_event(
                    row,
                    tuple(corrections_by_entry.get(entry_id, ())),
                )
            )

        return tuple(sorted(events, key=_timeline_sort_key))

    def get_latest_prediction(self) -> PredictionDetail | None:
        """Load the newest prediction and derive its current revision."""

        with self._database.transaction() as connection:
            row = connection.execute(
                f"""
                {_PREDICTION_DETAIL_SELECT}
                ORDER BY prediction.created_at DESC, prediction.id DESC
                LIMIT 1
                """
            ).fetchone()
            detail = (
                None
                if row is None
                else _map_prediction_detail(
                    row,
                    select_tags(connection, int(row["prediction_id"])),
                )
            )

        return detail

    def list_dashboard_predictions(self) -> tuple[DashboardPrediction, ...]:
        """Load every nonterminal prediction with its current forecast facts."""

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    prediction.id AS prediction_id,
                    prediction.question,
                    prediction.prediction_type,
                    prediction.status,
                    prediction.forecast_deadline,
                    prediction.expected_resolution,
                    current_revision.probability_percent,
                    NULL AS numeric_lower_scaled,
                    NULL AS numeric_median_scaled,
                    NULL AS numeric_upper_scaled,
                    NULL AS numeric_confidence_percent,
                    NULL AS numeric_unit,
                    NULL AS numeric_precision,
                    current_revision.created_at AS latest_revision_at
                FROM predictions AS prediction
                JOIN forecast_revisions AS current_revision
                    ON current_revision.id = (
                        SELECT candidate.id
                        FROM forecast_revisions AS candidate
                        WHERE candidate.prediction_id = prediction.id
                        ORDER BY candidate.sequence DESC
                        LIMIT 1
                    )
                WHERE prediction.status = 'open'
                    AND prediction.prediction_type = 'binary'
                UNION ALL
                SELECT
                    prediction.id AS prediction_id,
                    prediction.question,
                    prediction.prediction_type,
                    prediction.status,
                    prediction.forecast_deadline,
                    prediction.expected_resolution,
                    NULL AS probability_percent,
                    current_revision.lower_scaled AS numeric_lower_scaled,
                    current_revision.median_scaled AS numeric_median_scaled,
                    current_revision.upper_scaled AS numeric_upper_scaled,
                    current_revision.confidence_percent AS numeric_confidence_percent,
                    prediction.numeric_unit,
                    prediction.numeric_precision,
                    current_revision.created_at AS latest_revision_at
                FROM predictions AS prediction
                JOIN numeric_forecast_revisions AS current_revision
                    ON current_revision.id = (
                        SELECT candidate.id
                        FROM numeric_forecast_revisions AS candidate
                        WHERE candidate.prediction_id = prediction.id
                        ORDER BY candidate.sequence DESC
                        LIMIT 1
                    )
                WHERE prediction.status = 'open'
                    AND prediction.prediction_type = 'numeric'
                ORDER BY prediction.id
                """
            ).fetchall()

        return tuple(_map_dashboard_prediction(row) for row in rows)

    def list_browser_predictions(self) -> PredictionBrowserSnapshot:
        """Load every prediction summary and every associated tag."""

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    prediction.id AS prediction_id,
                    prediction.question,
                    prediction.prediction_type,
                    prediction.status,
                    prediction.created_at,
                    prediction.forecast_deadline,
                    current_revision.probability_percent,
                    NULL AS numeric_lower_scaled,
                    NULL AS numeric_median_scaled,
                    NULL AS numeric_upper_scaled,
                    NULL AS numeric_confidence_percent,
                    NULL AS numeric_unit,
                    NULL AS numeric_precision,
                    current_revision.created_at AS latest_revision_at
                FROM predictions AS prediction
                JOIN forecast_revisions AS current_revision
                    ON current_revision.id = (
                        SELECT candidate.id
                        FROM forecast_revisions AS candidate
                        WHERE candidate.prediction_id = prediction.id
                        ORDER BY candidate.sequence DESC
                        LIMIT 1
                    )
                WHERE prediction.prediction_type = 'binary'
                UNION ALL
                SELECT
                    prediction.id AS prediction_id,
                    prediction.question,
                    prediction.prediction_type,
                    prediction.status,
                    prediction.created_at,
                    prediction.forecast_deadline,
                    NULL AS probability_percent,
                    current_revision.lower_scaled AS numeric_lower_scaled,
                    current_revision.median_scaled AS numeric_median_scaled,
                    current_revision.upper_scaled AS numeric_upper_scaled,
                    current_revision.confidence_percent AS numeric_confidence_percent,
                    prediction.numeric_unit,
                    prediction.numeric_precision,
                    current_revision.created_at AS latest_revision_at
                FROM predictions AS prediction
                JOIN numeric_forecast_revisions AS current_revision
                    ON current_revision.id = (
                        SELECT candidate.id
                        FROM numeric_forecast_revisions AS candidate
                        WHERE candidate.prediction_id = prediction.id
                        ORDER BY candidate.sequence DESC
                        LIMIT 1
                    )
                WHERE prediction.prediction_type = 'numeric'
                ORDER BY 5 DESC, 1 DESC
                """
            ).fetchall()
            tag_rows = connection.execute(
                """
                SELECT prediction_tag.prediction_id, tag.display_name
                FROM tags AS tag
                JOIN prediction_tags AS prediction_tag
                    ON prediction_tag.tag_id = tag.id
                ORDER BY tag.normalized_name, tag.id, prediction_tag.prediction_id
                """
            ).fetchall()

        tags_by_prediction: dict[int, list[str]] = {}
        available_tags: list[str] = []
        seen_tag_names: set[str] = set()
        for row in tag_rows:
            prediction_id = int(row["prediction_id"])
            display_name = str(row["display_name"])
            tags_by_prediction.setdefault(prediction_id, []).append(display_name)
            normalized_name = display_name.casefold()
            if normalized_name not in seen_tag_names:
                available_tags.append(display_name)
                seen_tag_names.add(normalized_name)

        return PredictionBrowserSnapshot(
            predictions=tuple(
                _map_browser_prediction(
                    row,
                    tuple(tags_by_prediction.get(int(row["prediction_id"]), ())),
                )
                for row in rows
            ),
            available_tags=tuple(available_tags),
        )

    def get_prediction(self, prediction_id: int) -> PredictionDetail | None:
        """Load one prediction and derive its current revision."""

        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            detail = (
                None
                if row is None
                else _map_prediction_detail(
                    row,
                    select_tags(connection, prediction_id),
                )
            )

        return detail

    def update_metadata(
        self,
        prediction_id: int,
        update: PredictionMetadataUpdate,
        *,
        expected: PredictionDetail,
        expected_metadata_version: int,
        changed_at: datetime,
    ) -> PredictionDetail | None:
        """Replace metadata and append any definition record atomically."""

        timestamp = format_utc(changed_at)
        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                select_tags(connection, prediction_id),
            )
            if (
                current.metadata_version != expected_metadata_version
                or not _same_editable_metadata(current, expected)
            ):
                raise PredictionChangedError
            if not metadata_would_change(current, update):
                return current

            definition_fields = changed_definition_fields(current, update)
            connection.execute(
                """
                UPDATE predictions
                SET
                    question = ?,
                    background = ?,
                    resolution_criteria = ?,
                    forecast_deadline = ?,
                    expected_resolution = ?,
                    updated_at = ?,
                    metadata_version = metadata_version + 1
                WHERE id = ? AND metadata_version = ?
                """,
                (
                    update.question,
                    update.background,
                    update.resolution_criteria,
                    _format_date(update.forecast_deadline),
                    _format_date(update.expected_resolution),
                    timestamp,
                    prediction_id,
                    expected_metadata_version,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise PredictionChangedError
            replace_tags(connection, prediction_id, update.tags)
            if definition_fields:
                connection.execute(
                    """
                    INSERT INTO prediction_definition_changes (
                        prediction_id,
                        changed_at,
                        old_question,
                        new_question,
                        old_resolution_criteria,
                        new_resolution_criteria,
                        old_forecast_deadline,
                        new_forecast_deadline
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prediction_id,
                        timestamp,
                        current.question,
                        update.question,
                        current.resolution_criteria,
                        update.resolution_criteria,
                        _format_date(current.forecast_deadline),
                        _format_date(update.forecast_deadline),
                    ),
                )

            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The updated prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                updated_row,
                select_tags(connection, prediction_id),
            )

        return detail

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...] | None:
        """Load immutable definition changes in save order."""

        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                """
                SELECT
                    id,
                    prediction_id,
                    changed_at,
                    old_question,
                    new_question,
                    old_resolution_criteria,
                    new_resolution_criteria,
                    old_forecast_deadline,
                    new_forecast_deadline
                FROM prediction_definition_changes
                WHERE prediction_id = ?
                ORDER BY id
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_definition_change(row) for row in rows)


_PREDICTION_DETAIL_SELECT = """
SELECT
    prediction.id AS prediction_id,
    prediction.question,
    prediction.status,
    prediction.created_at,
    prediction.updated_at,
    prediction.metadata_version,
    prediction.background,
    prediction.resolution_criteria,
    prediction.forecast_deadline,
    prediction.expected_resolution,
    current_revision.id AS current_revision_id,
    current_revision.probability_percent,
    current_revision.sequence AS current_revision_sequence,
    current_revision.rationale AS current_rationale,
    resolution.id AS resolution_id,
    resolution.outcome AS resolution_outcome,
    resolution.resolved_at,
    resolution.scoring_revision_id,
    resolution.resolution_notes,
    resolution.postmortem,
    scoring_revision.sequence AS scoring_revision_sequence,
    scoring_revision.probability_percent AS scoring_probability_percent,
    invalidation.id AS invalidation_id,
    invalidation.invalidated_at,
    invalidation.reason AS invalidation_reason,
    (
        prediction.status = 'open'
        AND prediction.metadata_version = 1
        AND current_revision.sequence = 1
        AND NOT EXISTS (
            SELECT 1 FROM journal_entries
            WHERE prediction_id = prediction.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM prediction_definition_changes
            WHERE prediction_id = prediction.id
        )
    ) AS deletion_allowed
FROM predictions AS prediction
JOIN forecast_revisions AS current_revision
    ON current_revision.id = (
        SELECT candidate.id
        FROM forecast_revisions AS candidate
        WHERE candidate.prediction_id = prediction.id
        ORDER BY candidate.sequence DESC
        LIMIT 1
    )
LEFT JOIN resolutions AS resolution
    ON resolution.prediction_id = prediction.id
LEFT JOIN forecast_revisions AS scoring_revision
    ON scoring_revision.prediction_id = resolution.prediction_id
    AND scoring_revision.id = resolution.scoring_revision_id
LEFT JOIN prediction_invalidations AS invalidation
    ON invalidation.prediction_id = prediction.id
"""


def _select_prediction_detail(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        {_PREDICTION_DETAIL_SELECT}
        WHERE prediction.id = ?
        """,
        (prediction_id,),
    ).fetchone()


def _map_prediction_detail(
    row: sqlite3.Row,
    tags: tuple[str, ...] = (),
) -> PredictionDetail:
    status = PredictionStatus(row["status"])
    resolution = (
        None
        if row["resolution_id"] is None
        else Resolution(
            resolution_id=int(row["resolution_id"]),
            prediction_id=int(row["prediction_id"]),
            outcome=BinaryOutcome(row["resolution_outcome"]),
            resolved_at=parse_utc(str(row["resolved_at"])),
            scoring_revision_id=int(row["scoring_revision_id"]),
            scoring_revision_sequence=int(row["scoring_revision_sequence"]),
            scoring_probability_percent=int(row["scoring_probability_percent"]),
            resolution_notes=_optional_string(row["resolution_notes"]),
            postmortem=_optional_string(row["postmortem"]),
        )
    )
    invalidation = (
        None
        if row["invalidation_id"] is None
        else Invalidation(
            invalidation_id=int(row["invalidation_id"]),
            prediction_id=int(row["prediction_id"]),
            invalidated_at=parse_utc(str(row["invalidated_at"])),
            reason=_optional_string(row["invalidation_reason"]),
        )
    )
    return PredictionDetail(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        probability_percent=int(row["probability_percent"]),
        status=status,
        created_at=parse_utc(str(row["created_at"])),
        current_revision_id=int(row["current_revision_id"]),
        current_revision_sequence=int(row["current_revision_sequence"]),
        current_rationale=_optional_string(row["current_rationale"]),
        background=_optional_string(row["background"]),
        resolution_criteria=_optional_string(row["resolution_criteria"]),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        expected_resolution=_parse_date(row["expected_resolution"]),
        tags=tags,
        updated_at=parse_utc(str(row["updated_at"])),
        metadata_version=int(row["metadata_version"]),
        resolution=resolution,
        invalidation=invalidation,
        deletion_allowed=bool(row["deletion_allowed"]),
    )


def _map_dashboard_prediction(row: sqlite3.Row) -> DashboardPrediction:
    """Map one type-aware nonterminal summary from the shared read query."""

    prediction_type = PredictionType(row["prediction_type"])
    numeric_values = _map_numeric_summary_values(row, prediction_type)
    return DashboardPrediction(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        probability_percent=(
            None
            if prediction_type is PredictionType.NUMERIC
            else int(row["probability_percent"])
        ),
        status=PredictionStatus(row["status"]),
        latest_revision_at=parse_utc(str(row["latest_revision_at"])),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        expected_resolution=_parse_date(row["expected_resolution"]),
        prediction_type=prediction_type,
        **numeric_values,
    )


def _map_browser_prediction(
    row: sqlite3.Row,
    tags: tuple[str, ...],
) -> PredictionBrowserItem:
    """Map one type-aware archive summary from the shared read query."""

    prediction_type = PredictionType(row["prediction_type"])
    numeric_values = _map_numeric_summary_values(row, prediction_type)
    return PredictionBrowserItem(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        probability_percent=(
            None
            if prediction_type is PredictionType.NUMERIC
            else int(row["probability_percent"])
        ),
        status=PredictionStatus(row["status"]),
        created_at=parse_utc(str(row["created_at"])),
        latest_revision_at=parse_utc(str(row["latest_revision_at"])),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        tags=tags,
        prediction_type=prediction_type,
        **numeric_values,
    )


def _map_numeric_summary_values(
    row: sqlite3.Row,
    prediction_type: PredictionType,
) -> dict[str, FixedPrecisionValue | int | str | None]:
    """Return populated Numeric summary fields only for Numeric rows."""

    if prediction_type is PredictionType.BINARY:
        return {}
    decimal_places = int(row["numeric_precision"])
    return {
        "numeric_lower_bound": FixedPrecisionValue(
            int(row["numeric_lower_scaled"]),
            decimal_places,
        ),
        "numeric_median_estimate": FixedPrecisionValue(
            int(row["numeric_median_scaled"]),
            decimal_places,
        ),
        "numeric_upper_bound": FixedPrecisionValue(
            int(row["numeric_upper_scaled"]),
            decimal_places,
        ),
        "numeric_confidence_percent": int(row["numeric_confidence_percent"]),
        "numeric_unit": str(row["numeric_unit"]),
    }


def _map_forecast_revision(row: sqlite3.Row) -> ForecastRevision:
    return ForecastRevision(
        revision_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        probability_percent=int(row["probability_percent"]),
        sequence=int(row["sequence"]),
        created_at=parse_utc(str(row["created_at"])),
        rationale=_optional_string(row["rationale"]),
    )


def _select_journal_event(
    connection: sqlite3.Connection,
    prediction_id: int,
    entry_id: int,
) -> JournalTimelineEvent | None:
    row = connection.execute(
        """
        SELECT
            journal.id AS entry_id,
            journal.prediction_id,
            journal.created_at,
            journal.body AS original_body,
            revision.id AS forecast_revision_id,
            revision.sequence AS forecast_revision_sequence,
            revision.probability_percent AS forecast_probability_percent
        FROM journal_entries AS journal
        JOIN forecast_revisions AS revision
            ON revision.id = journal.forecast_revision_id
            AND revision.prediction_id = journal.prediction_id
        WHERE journal.prediction_id = ? AND journal.id = ?
        """,
        (prediction_id, entry_id),
    ).fetchone()
    if row is None:
        return None
    correction_rows = connection.execute(
        """
        SELECT id, journal_entry_id, body, corrected_at
        FROM journal_entry_corrections
        WHERE prediction_id = ? AND journal_entry_id = ?
        ORDER BY sequence
        """,
        (prediction_id, entry_id),
    ).fetchall()
    return _map_journal_event(
        row,
        tuple(_map_journal_correction(item) for item in correction_rows),
    )


def _map_journal_correction(row: sqlite3.Row) -> JournalCorrection:
    return JournalCorrection(
        correction_id=int(row["id"]),
        body=str(row["body"]),
        corrected_at=parse_utc(str(row["corrected_at"])),
    )


def _map_journal_event(
    row: sqlite3.Row,
    corrections: tuple[JournalCorrection, ...],
) -> JournalTimelineEvent:
    original_body = str(row["original_body"])
    current = corrections[-1] if corrections else None
    return JournalTimelineEvent(
        entry_id=int(row["entry_id"]),
        prediction_id=int(row["prediction_id"]),
        created_at=parse_utc(str(row["created_at"])),
        body=original_body if current is None else current.body,
        original_body=original_body,
        forecast_revision_id=int(row["forecast_revision_id"]),
        forecast_revision_sequence=int(row["forecast_revision_sequence"]),
        forecast_probability_percent=int(row["forecast_probability_percent"]),
        current_correction_id=(None if current is None else current.correction_id),
        corrections=corrections,
    )


def _timeline_sort_key(event: TimelineEvent) -> tuple[object, ...]:
    if isinstance(event, ForecastTimelineEvent):
        return (event.sequence, 0, event.revision_id)
    return (
        event.forecast_revision_sequence,
        1,
        event.entry_id,
    )


def select_tags(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT tag.display_name
        FROM tags AS tag
        JOIN prediction_tags AS prediction_tag ON prediction_tag.tag_id = tag.id
        WHERE prediction_tag.prediction_id = ?
        ORDER BY tag.normalized_name, tag.id
        """,
        (prediction_id,),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def replace_tags(
    connection: sqlite3.Connection,
    prediction_id: int,
    tags: tuple[str, ...],
) -> None:
    connection.execute(
        "DELETE FROM prediction_tags WHERE prediction_id = ?",
        (prediction_id,),
    )
    for display_name in tags:
        normalized_name = display_name.casefold()
        connection.execute(
            """
            INSERT INTO tags (display_name, normalized_name)
            VALUES (?, ?)
            ON CONFLICT (normalized_name) DO NOTHING
            """,
            (display_name, normalized_name),
        )
        tag_row = connection.execute(
            "SELECT id FROM tags WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        if tag_row is None:
            raise sqlite3.DatabaseError("A tag could not be loaded after insertion.")
        connection.execute(
            """
            INSERT INTO prediction_tags (prediction_id, tag_id)
            VALUES (?, ?)
            """,
            (prediction_id, int(tag_row[0])),
        )


def _same_editable_metadata(
    left: PredictionDetail,
    right: PredictionDetail,
) -> bool:
    scalar_fields = (
        "question",
        "background",
        "resolution_criteria",
        "forecast_deadline",
        "expected_resolution",
        "updated_at",
        "metadata_version",
    )
    return all(
        getattr(left, field_name) == getattr(right, field_name)
        for field_name in scalar_fields
    ) and {tag.casefold() for tag in left.tags} == {
        tag.casefold() for tag in right.tags
    }


def _map_definition_change(row: sqlite3.Row) -> DefinitionChange:
    old_question = str(row["old_question"])
    new_question = str(row["new_question"])
    old_resolution_criteria = _optional_string(row["old_resolution_criteria"])
    new_resolution_criteria = _optional_string(row["new_resolution_criteria"])
    old_forecast_deadline = _parse_date(row["old_forecast_deadline"])
    new_forecast_deadline = _parse_date(row["new_forecast_deadline"])
    changed_fields = tuple(
        field_name
        for field_name, old_value, new_value in (
            ("question", old_question, new_question),
            (
                "resolution_criteria",
                old_resolution_criteria,
                new_resolution_criteria,
            ),
            ("forecast_deadline", old_forecast_deadline, new_forecast_deadline),
        )
        if old_value != new_value
    )
    return DefinitionChange(
        change_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        changed_at=parse_utc(str(row["changed_at"])),
        changed_fields=changed_fields,
        old_question=old_question,
        new_question=new_question,
        old_resolution_criteria=old_resolution_criteria,
        new_resolution_criteria=new_resolution_criteria,
        old_forecast_deadline=old_forecast_deadline,
        new_forecast_deadline=new_forecast_deadline,
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))
