"""Internal M56 persistence foundation; GUI/CLI operations arrive in M57.

All writes use the same immediate transaction and immutable source rows as the
deadline workflows. No original value or system timestamp is overwritten.
"""

import sqlite3
from dataclasses import replace

from reckonsolve.clock import Clock, as_utc, format_utc
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotValues,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    PredictionStatus,
    PredictionValidationError,
    _optional_text,
)

from .database import Database
from .forecast_contracts import select_forecast_contract
from .m56_migration import SNAPSHOT_FIELDS
from .one_shot_facts import OneShotRecord, _reported_columns, _snapshot, read_one_shot
from .predictions import ForecastContextChangedError, replace_tags


class OneShotRepository:
    """Internal, tested storage operations, deliberately absent from public entry points."""

    def __init__(self, database: Database, clock: Clock) -> None:
        self.database, self.clock = database, clock

    def get(self, prediction_id: int) -> OneShotRecord:
        with self.database.transaction(allow_one_shot=True) as connection:
            return read_one_shot(
                connection,
                prediction_id,
                select_forecast_contract(connection, prediction_id),
            )

    def create_prediction(self, request: NewOneShotPrediction) -> OneShotRecord:
        with self.database.transaction(allow_one_shot=True) as connection:
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
            return read_one_shot(connection, identifier, request.contract)

    def add_answer(
        self, expected: OneShotRecord, values: OneShotValues
    ) -> OneShotRecord:
        values.validate_contract(expected.contract, expected.definition)
        with self.database.transaction(allow_one_shot=True) as connection:
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
            return read_one_shot(connection, current.prediction_id, current.contract)

    def correct(
        self, expected: OneShotRecord, values: OneShotValues, *, note: str | None = None
    ) -> OneShotRecord:
        values.validate_contract(expected.contract, expected.definition)
        note = _optional_text(note, "note")
        with self.database.transaction(allow_one_shot=True) as connection:
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
            return read_one_shot(connection, current.prediction_id, current.contract)

    @staticmethod
    def _current(
        connection: sqlite3.Connection, expected: OneShotRecord
    ) -> OneShotRecord:
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
