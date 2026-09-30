"""Atomic One-Shot persistence shared by desktop and CLI operations.

All writes use the same immediate transaction and immutable source rows as the
deadline workflows. No original value or system timestamp is overwritten.
"""

import sqlite3
from dataclasses import replace
from datetime import date

from reckonsolve.clock import Clock, as_utc, format_utc, parse_utc
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotDetail,
    OneShotJournal,
    OneShotValues,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    JournalCorrection,
    NewJournalCorrection,
    NewJournalEntry,
    PostmortemCompletion,
    PredictionStatus,
    PredictionValidationError,
    _optional_text,
)

from .database import Database
from .forecast_contracts import select_forecast_contract
from .m56_migration import SNAPSHOT_FIELDS
from .one_shot_facts import OneShotRecord, _reported_columns, _snapshot, read_one_shot
from .predictions import (
    ForecastContextChangedError,
    _map_definition_change,
    replace_tags,
    select_tags,
)
from .terminal_history import _select_invalidation_history


class OneShotRepository:
    """Immutable originals and explicit transcription repairs."""

    def __init__(self, database: Database, clock: Clock) -> None:
        self.database, self.clock = database, clock

    def get(self, prediction_id: int) -> OneShotRecord:
        with self.database.transaction() as connection:
            return read_one_shot(
                connection,
                prediction_id,
                select_forecast_contract(connection, prediction_id),
            )

    def find_detail(self, prediction_id: int) -> OneShotDetail | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
            ).fetchone()
            if row is None:
                return None
            contract = select_forecast_contract(connection, prediction_id)
            if not contract.is_one_shot:
                return None
            return self._detail(
                connection, read_one_shot(connection, prediction_id, contract)
            )

    @staticmethod
    def _detail(connection: sqlite3.Connection, record: OneShotRecord) -> OneShotDetail:
        identifier = record.prediction_id
        row = connection.execute(
            "SELECT * FROM predictions WHERE id = ?", (identifier,)
        ).fetchone()
        table = (
            "forecast_revisions"
            if record.definition is None
            else "numeric_quantile_revisions"
        )
        rationale = connection.execute(
            f"SELECT rationale FROM {table} WHERE prediction_id = ?", (identifier,)
        ).fetchone()[0]
        changes = tuple(
            _map_definition_change(r)
            for r in connection.execute(
                "SELECT * FROM prediction_definition_changes WHERE prediction_id = ? ORDER BY id",
                (identifier,),
            )
        )
        untouched = (
            record.status is PredictionStatus.OPEN
            and record.metadata_version == 1
            and not record.corrections
            and not changes
        )
        untouched = (
            untouched
            and connection.execute(
                "SELECT 1 FROM journal_entries WHERE prediction_id = ?", (identifier,)
            ).fetchone()
            is None
        )
        journals = tuple(
            OneShotJournal(
                r["id"],
                parse_utc(r["created_at"]),
                r["body"],
                tuple(
                    JournalCorrection(c["id"], c["body"], parse_utc(c["corrected_at"]))
                    for c in connection.execute(
                        "SELECT * FROM journal_entry_corrections WHERE journal_entry_id = ? ORDER BY sequence",
                        (r["id"],),
                    )
                ),
            )
            for r in connection.execute(
                "SELECT * FROM journal_entries WHERE prediction_id = ? ORDER BY id",
                (identifier,),
            )
        )
        completion_row = connection.execute(
            "SELECT id, completed_at FROM postmortem_completions WHERE prediction_id = ?",
            (identifier,),
        ).fetchone()
        completion = (
            None
            if completion_row is None
            else PostmortemCompletion(
                int(completion_row["id"]),
                identifier,
                parse_utc(completion_row["completed_at"]),
            )
        )
        return OneShotDetail(
            record,
            row["question"],
            rationale,
            row["background"],
            row["resolution_criteria"],
            date.fromisoformat(row["expected_resolution"])
            if row["expected_resolution"]
            else None,
            select_tags(connection, identifier),
            parse_utc(row["updated_at"]),
            bool(untouched),
            changes,
            journals,
            _select_invalidation_history(connection, identifier),
            completion,
        )

    def add_journal(self, expected: OneShotRecord, body: str) -> OneShotDetail:
        entry = NewJournalEntry(body)
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            if current.status is not PredictionStatus.OPEN:
                raise ValueError(
                    "New Journal entries are allowed only while waiting for an answer."
                )
            table, anchor = (
                ("forecast_revisions", "forecast_revision_id")
                if current.definition is None
                else ("numeric_quantile_revisions", "quantile_revision_id")
            )
            connection.execute(
                f"INSERT INTO journal_entries (prediction_id, {anchor}, body, created_at) SELECT ?, id, ?, ? FROM {table} WHERE prediction_id = ?",
                (
                    current.prediction_id,
                    entry.body,
                    format_utc(as_utc(self.clock.now())),
                    current.prediction_id,
                ),
            )

            return self._detail(connection, current)

    def correct_journal(
        self,
        expected: OneShotRecord,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> OneShotDetail:
        correction = NewJournalCorrection(body)
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            entry = next(
                (
                    journal
                    for journal in self._detail(connection, current).journals
                    if journal.entry_id == entry_id
                ),
                None,
            )
            if entry is None:
                raise ValueError("The Journal entry no longer exists.")
            if entry.current_correction_id != expected_correction_id:
                raise ForecastContextChangedError(
                    "The Journal entry changed. Refresh and try again."
                )
            if entry.body == correction.body:
                raise ValueError("The Journal entry is unchanged.")
            connection.execute(
                """INSERT INTO journal_entry_corrections
                   (prediction_id, journal_entry_id, sequence, body, corrected_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    current.prediction_id,
                    entry_id,
                    len(entry.corrections) + 1,
                    correction.body,
                    format_utc(as_utc(self.clock.now())),
                ),
            )
            return self._detail(connection, current)

    def skip_postmortem(self, expected: OneShotRecord) -> OneShotDetail:
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            if current.status is not PredictionStatus.RESOLVED:
                raise ValueError("Only a Resolved One-Shot can skip its Postmortem.")
            if current.effective.postmortem is not None:
                raise ValueError("This One-Shot already has a Postmortem.")
            if connection.execute(
                "SELECT 1 FROM postmortem_completions WHERE prediction_id = ?",
                (current.prediction_id,),
            ).fetchone():
                raise ValueError("This Postmortem has already been skipped.")
            connection.execute(
                "INSERT INTO postmortem_completions (prediction_id, completed_at) VALUES (?, ?)",
                (current.prediction_id, format_utc(as_utc(self.clock.now()))),
            )
            return self._detail(connection, current)

    def invalidate_or_delete(
        self,
        expected: OneShotRecord,
        *,
        delete: bool = False,
        reason: str | None = None,
    ) -> OneShotDetail | None:
        reason = _optional_text(reason, "reason")
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            if current.status is not PredictionStatus.OPEN:
                raise ValueError(
                    "Only a One-Shot waiting for an answer can be invalidated or deleted."
                )
            if delete:
                if not self._detail(connection, current).deletion_allowed:
                    raise ValueError(
                        "This One-Shot has history. Mark it Invalid to preserve it."
                    )
                connection.execute(
                    "DELETE FROM predictions WHERE id = ?", (current.prediction_id,)
                )
                return None
            else:
                connection.execute(
                    "INSERT INTO prediction_invalidations (prediction_id, invalidated_at, reason) VALUES (?, ?, ?)",
                    (
                        current.prediction_id,
                        format_utc(as_utc(self.clock.now())),
                        reason,
                    ),
                )
            return self._detail(
                connection,
                read_one_shot(connection, current.prediction_id, current.contract),
            )

    def create_prediction(self, request: NewOneShotPrediction) -> OneShotRecord:
        return self.create_detail(request).record

    def create_detail(self, request: NewOneShotPrediction) -> OneShotDetail:
        with self.database.transaction() as connection:
            timestamp = format_utc(as_utc(self.clock.now()))
            definition = request.definition
            identifier = connection.execute(
                """INSERT INTO predictions
                (question, prediction_type, status, created_at, updated_at, numeric_unit, numeric_precision,
                 background, resolution_criteria, expected_resolution)
                VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.question,
                    request.contract.prediction_type.value,
                    timestamp,
                    timestamp,
                    definition.unit if definition else None,
                    definition.decimal_places if definition else None,
                    request.background,
                    request.resolution_criteria,
                    request.expected_resolution.isoformat()
                    if request.expected_resolution
                    else None,
                ),
            ).lastrowid
            connection.execute(
                """INSERT INTO prediction_forecast_contracts
                (prediction_id, forecast_model, scoring_contract) VALUES (?, ?, ?)""",
                (
                    identifier,
                    request.contract.forecast_model.value,
                    request.contract.scoring_contract.value,
                ),
            )
            if definition is None:
                connection.execute(
                    """INSERT INTO forecast_revisions
                    (prediction_id, sequence, probability_percent, created_at, rationale) VALUES (?, 1, ?, ?, ?)""",
                    (
                        identifier,
                        request.values.probability_percent,
                        timestamp,
                        request.rationale,
                    ),
                )
            else:
                connection.execute(
                    "INSERT INTO numeric_quantile_definitions VALUES (?, ?)",
                    (identifier, definition.value_constraint.value),
                )
                connection.execute(
                    """INSERT INTO numeric_quantile_revisions
                    (prediction_id, sequence, created_at, q05_scaled, q25_scaled, q50_scaled, q75_scaled, q95_scaled, rationale)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        identifier,
                        timestamp,
                        *(v.scaled_value for v in request.values.quantiles.values),
                        request.rationale,
                    ),
                )
            replace_tags(connection, identifier, request.tags)
            connection.execute(
                "INSERT INTO one_shot_forecast_times VALUES (?, ?, ?, ?)",
                (identifier, *_reported_columns(request.values.forecast_reported)),
            )
            if request.values.answer is not None:
                self._insert_answer(connection, identifier, request.values, timestamp)
            return self._detail(
                connection, read_one_shot(connection, identifier, request.contract)
            )

    def add_answer(
        self, expected: OneShotRecord, values: OneShotValues
    ) -> OneShotRecord:
        return self.add_answer_detail(expected, values).record

    def add_answer_detail(
        self, expected: OneShotRecord, values: OneShotValues
    ) -> OneShotDetail:
        values.validate_contract(expected.contract, expected.definition)
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            if (
                current.status is not PredictionStatus.OPEN
                or current.effective.answer is not None
            ):
                raise ValueError(
                    "Only a One-Shot waiting for an answer may be answered."
                )
            if (
                values.answer is None
                or replace(
                    values,
                    answer=None,
                    reveal_reported=None,
                    resolution_notes=None,
                    postmortem=None,
                )
                != current.effective
            ):
                raise ValueError(
                    "Add answer cannot change the saved forecast or reported forecast time."
                )
            self._insert_answer(
                connection,
                current.prediction_id,
                values,
                format_utc(as_utc(self.clock.now())),
            )
            return self._detail(
                connection,
                read_one_shot(connection, current.prediction_id, current.contract),
            )

    def correct(
        self, expected: OneShotRecord, values: OneShotValues, *, note: str | None = None
    ) -> OneShotRecord:
        return self.correct_detail(expected, values, note=note).record

    def correct_detail(
        self, expected: OneShotRecord, values: OneShotValues, *, note: str | None = None
    ) -> OneShotDetail:
        values.validate_contract(expected.contract, expected.definition)
        note = _optional_text(note, "note")
        with self.database.transaction() as connection:
            current = self._current(connection, expected)
            if values == current.effective:
                raise PredictionValidationError(
                    "The transcription is unchanged.", field="forecast"
                )
            if (values.answer is None) != (current.effective.answer is None):
                raise ValueError(
                    "Corrections cannot add or remove an answer; use Add answer."
                )
            columns = ["prediction_id", "sequence", "corrected_at", "note"] + [
                p + f for p in ("old_", "new_") for f in SNAPSHOT_FIELDS
            ]
            connection.execute(
                f"INSERT INTO one_shot_corrections ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                (
                    current.prediction_id,
                    len(current.corrections) + 1,
                    format_utc(as_utc(self.clock.now())),
                    note,
                    *_snapshot(current.effective),
                    *_snapshot(values),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO search_dirty_predictions (prediction_id) VALUES (?)",
                (current.prediction_id,),
            )
            return self._detail(
                connection,
                read_one_shot(connection, current.prediction_id, current.contract),
            )

    @staticmethod
    def _current(
        connection: sqlite3.Connection, expected: OneShotRecord
    ) -> OneShotRecord:
        if (
            connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?", (expected.prediction_id,)
            ).fetchone()
            is None
        ):
            raise ForecastContextChangedError(
                "This One-Shot was deleted. Reload before saving."
            )
        current = read_one_shot(
            connection,
            expected.prediction_id,
            select_forecast_contract(connection, expected.prediction_id),
        )
        if current.context != expected.context or current.status != expected.status:
            raise ForecastContextChangedError(
                "This One-Shot changed. Reload it before saving."
            )
        return current

    @staticmethod
    def _insert_answer(
        connection: sqlite3.Connection,
        identifier: int,
        values: OneShotValues,
        timestamp: str,
    ) -> None:
        if isinstance(values.answer, BinaryOutcome):
            connection.execute(
                """INSERT INTO resolutions
                (prediction_id, outcome, resolved_at, scoring_revision_id, resolution_notes, postmortem)
                SELECT ?, ?, ?, id, ?, ? FROM forecast_revisions WHERE prediction_id = ? AND sequence = 1""",
                (
                    identifier,
                    values.answer.value,
                    timestamp,
                    values.resolution_notes,
                    values.postmortem,
                    identifier,
                ),
            )
        else:
            connection.execute(
                """INSERT INTO numeric_resolutions
                (prediction_id, actual_scaled, resolved_at, quantile_revision_id, resolution_notes, postmortem)
                SELECT ?, ?, ?, id, ?, ? FROM numeric_quantile_revisions WHERE prediction_id = ? AND sequence = 1""",
                (
                    identifier,
                    values.answer.scaled_value,
                    timestamp,
                    values.resolution_notes,
                    values.postmortem,
                    identifier,
                ),
            )
        connection.execute(
            "INSERT INTO one_shot_answer_times VALUES (?, ?, ?, ?)",
            (identifier, *_reported_columns(values.reveal_reported)),
        )
