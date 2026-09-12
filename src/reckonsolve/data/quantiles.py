"""Transactional five-quantile creation, revision, and anchored history."""

import sqlite3
from datetime import date

from reckonsolve.clock import Clock, format_utc, parse_utc
from reckonsolve.domain.forecast_contracts import (
    ForecastCohort,
    ForecastingWindow,
    contract_status,
    prospective_contract,
)
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    Invalidation,
    JournalCorrection,
    NewForecastReview,
    NewJournalCorrection,
    NewJournalEntry,
    NumericPrediction,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
    _optional_text,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NewQuantilePrediction,
    NumericValueConstraint,
    QuantileDefinition,
    QuantileRevision,
    QuantileTimelineEvent,
)
from reckonsolve.domain.timeline import order_timeline

from .database import Database
from .forecast_contracts import (
    ForecastContractIntegrityError,
    insert_prospective_contract,
    select_forecast_contract,
)
from .predictions import (
    ForecastContextChangedError,
    ForecastReviewContextChangedError,
    ForecastReviewDisallowedError,
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


def read_prediction(
    connection: sqlite3.Connection, prediction_id: int
) -> NumericPrediction:
    definition = read_definition(connection, prediction_id)
    revisions = read_revisions(connection, prediction_id)
    row = connection.execute(
        "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
    ).fetchone()
    invalid = connection.execute(
        "SELECT * FROM prediction_invalidations WHERE prediction_id = ?",
        (prediction_id,),
    ).fetchone()
    untouched = row["metadata_version"] == 1 and len(revisions) == 1
    for table in (
        "journal_entries",
        "forecast_reviews",
        "prediction_definition_changes",
    ):
        untouched = (
            untouched
            and connection.execute(
                f"SELECT 1 FROM {table} WHERE prediction_id = ? LIMIT 1",
                (prediction_id,),
            ).fetchone()
            is None
        )
    return NumericPrediction(
        prediction_id,
        row["question"],
        definition.unit,
        definition.decimal_places,
        PredictionStatus(row["status"]),
        parse_utc(row["created_at"]),
        parse_utc(row["updated_at"]),
        revisions[-1],
        background=row["background"],
        resolution_criteria=row["resolution_criteria"],
        expected_resolution=date.fromisoformat(row["expected_resolution"])
        if row["expected_resolution"]
        else None,
        tags=select_tags(connection, prediction_id),
        metadata_version=row["metadata_version"],
        invalidation=None
        if invalid is None
        else Invalidation(
            invalid["id"],
            prediction_id,
            parse_utc(invalid["invalidated_at"]),
            invalid["reason"],
        ),
        deletion_allowed=untouched and row["status"] == "open",
        forecast_contract=select_forecast_contract(connection, prediction_id),
        value_constraint=definition.value_constraint,
    )


def read_definition(
    connection: sqlite3.Connection, prediction_id: int
) -> QuantileDefinition:
    if (
        select_forecast_contract(connection, prediction_id).cohort
        is not ForecastCohort.QUANTILE_NUMERIC
    ):
        raise ForecastContractIntegrityError(
            "A five-quantile Numeric Prediction is required."
        )
    row = connection.execute(
        """SELECT p.numeric_unit, p.numeric_precision, d.value_constraint
        FROM predictions p JOIN numeric_quantile_definitions d ON d.prediction_id = p.id WHERE p.id = ?""",
        (prediction_id,),
    ).fetchone()
    if row is None:
        raise ForecastContractIntegrityError("Numeric v2 definition is missing.")
    return QuantileDefinition(row[0], row[1], NumericValueConstraint(row[2]))


def read_revisions(
    connection: sqlite3.Connection, prediction_id: int
) -> tuple[QuantileRevision, ...]:
    definition = read_definition(connection, prediction_id)
    rows = connection.execute(
        "SELECT * FROM numeric_quantile_revisions WHERE prediction_id = ? ORDER BY sequence",
        (prediction_id,),
    ).fetchall()
    revisions = []
    for row in rows:
        quantiles = FiveQuantiles(
            *(
                FixedPrecisionValue(
                    row[f"q{level:02}_scaled"], definition.decimal_places
                )
                for level in (5, 25, 50, 75, 95)
            )
        )
        definition.validate_quantiles(quantiles)
        revisions.append(
            QuantileRevision(
                row["id"],
                prediction_id,
                quantiles,
                row["sequence"],
                parse_utc(row["created_at"]),
                row["rationale"],
            )
        )
    return tuple(revisions)


def _insert_revision(
    connection: sqlite3.Connection,
    prediction_id: int,
    quantiles: FiveQuantiles,
    sequence: int,
    timestamp: str,
    rationale: str | None,
) -> int:
    cursor = connection.execute(
        """INSERT INTO numeric_quantile_revisions (
        prediction_id, sequence, created_at, q05_scaled, q25_scaled, q50_scaled, q75_scaled, q95_scaled, rationale
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            prediction_id,
            sequence,
            timestamp,
            *(v.scaled_value for v in quantiles.values),
            rationale,
        ),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


class QuantilePredictionRepository:
    """Model-specific storage behind the shared application operations."""

    def __init__(self, database: Database, clock: Clock) -> None:
        self._database = database
        self._clock = clock

    def create_prediction(self, new: NewQuantilePrediction) -> QuantileRevision:
        """Keep the foundation's revision-only seed interface."""
        return self.create_detail(new).current_revision

    def create_detail(self, new: NewQuantilePrediction) -> NumericPrediction:
        """Return the complete creation snapshot from the same write transaction."""
        with self._database.transaction() as connection:
            now = self._clock.now()
            ForecastingWindow(now, new.forecast_deadline)
            timestamp = format_utc(now)
            cursor = connection.execute(
                """INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at, numeric_unit,
                numeric_precision, background, resolution_criteria, expected_resolution
                ) VALUES (?, 'numeric', 'open', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new.question,
                    timestamp,
                    timestamp,
                    new.definition.unit,
                    new.definition.decimal_places,
                    new.background,
                    new.resolution_criteria,
                    None
                    if new.expected_resolution is None
                    else new.expected_resolution.isoformat(),
                ),
            )
            prediction_id = cursor.lastrowid
            assert prediction_id is not None
            insert_prospective_contract(
                connection,
                prediction_id,
                prospective_contract(PredictionType.NUMERIC, new.forecast_deadline),
            )
            connection.execute(
                "INSERT INTO numeric_quantile_definitions VALUES (?, ?)",
                (prediction_id, new.definition.value_constraint.value),
            )
            replace_tags(connection, prediction_id, new.tags)
            _insert_revision(
                connection, prediction_id, new.quantiles, 1, timestamp, new.rationale
            )
            created = read_prediction(connection, prediction_id)
        return created

    def append_revision(
        self,
        prediction_id: int,
        quantiles: FiveQuantiles,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        rationale: str | None = None,
    ) -> QuantileRevision:
        return self.revise_prediction(
            prediction_id,
            quantiles,
            expected_revision_id=expected_revision_id,
            expected_metadata_version=expected_metadata_version,
            rationale=rationale,
        ).current_revision

    def revise_prediction(
        self,
        prediction_id: int,
        quantiles: FiveQuantiles,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        rationale: str | None = None,
    ) -> NumericPrediction:
        rationale = _optional_text(rationale, "rationale")
        with self._database.transaction() as connection:
            revisions = read_revisions(connection, prediction_id)
            current = revisions[-1]
            status = PredictionStatus(
                connection.execute(
                    "SELECT status FROM predictions WHERE id = ?", (prediction_id,)
                ).fetchone()[0]
            )
            if status is not PredictionStatus.OPEN:
                raise ForecastRevisionDisallowedError(status)
            metadata_version = connection.execute(
                "SELECT metadata_version FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()[0]
            if (
                current.revision_id != expected_revision_id
                or metadata_version != expected_metadata_version
            ):
                raise ForecastContextChangedError(
                    "Prediction changed; reload before revising."
                )
            definition = read_definition(connection, prediction_id)
            definition.validate_replacement(current.quantiles, quantiles)
            contract = select_forecast_contract(connection, prediction_id)
            window = ForecastingWindow(
                revisions[0].created_at, contract.forecast_deadline
            )
            now = window.validate_revision(
                previous_revision_at=current.created_at,
                proposed_revision_at=self._clock.now(),
            )
            _insert_revision(
                connection,
                prediction_id,
                quantiles,
                current.sequence + 1,
                format_utc(now),
                rationale,
            )
            saved = read_prediction(connection, prediction_id)
        return saved

    def list_revisions(self, prediction_id: int) -> tuple[QuantileRevision, ...]:
        with self._database.transaction() as connection:
            return read_revisions(connection, prediction_id)

    def get_prediction(self, prediction_id: int) -> NumericPrediction:
        with self._database.transaction() as connection:
            return read_prediction(connection, prediction_id)

    def add_note(
        self,
        prediction_id: int,
        *,
        body: str | None,
        review: bool,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> QuantileTimelineEvent:
        note = NewForecastReview(body).note if review else NewJournalEntry(body).body
        with self._database.transaction() as connection:
            current = read_prediction(connection, prediction_id)
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise (
                    ForecastReviewContextChangedError
                    if review
                    else JournalContextChangedError
                )
            now = self._clock.now()
            if now < current.current_revision.created_at:
                raise PredictionValidationError(
                    "The recorded time cannot precede the anchored forecast.",
                    field="created_at",
                )
            status = contract_status(
                current.status, None, now.date(), current.forecast_contract, now
            )
            if review and status is not PredictionStatus.OPEN:
                raise ForecastReviewDisallowedError(status)
            if not review and status not in (
                PredictionStatus.OPEN,
                PredictionStatus.LOCKED,
            ):
                raise JournalEntryDisallowedError(status)
            table, field = (
                ("forecast_reviews", "note") if review else ("journal_entries", "body")
            )
            cursor = connection.execute(
                f"INSERT INTO {table} (prediction_id, quantile_revision_id, created_at, {field}) VALUES (?, ?, ?, ?)",
                (prediction_id, expected_revision_id, format_utc(now), note),
            )
            return QuantileTimelineEvent(
                "review" if review else "journal",
                cursor.lastrowid,
                current.current_revision,
                now,
                note,
                note,
            )

    def correct_journal(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> QuantileTimelineEvent | None:
        body = NewJournalCorrection(body).body
        with self._database.transaction() as connection:
            read_definition(connection, prediction_id)
            row = connection.execute(
                "SELECT * FROM journal_entries WHERE prediction_id = ? AND id = ?",
                (prediction_id, entry_id),
            ).fetchone()
            if row is None:
                return None
            corrections = connection.execute(
                "SELECT * FROM journal_entry_corrections WHERE journal_entry_id = ? ORDER BY sequence",
                (entry_id,),
            ).fetchall()
            if (
                corrections[-1]["id"] if corrections else None
            ) != expected_correction_id:
                raise JournalCorrectionContextChangedError
            if body != (corrections[-1]["body"] if corrections else row["body"]):
                connection.execute(
                    "INSERT INTO journal_entry_corrections (prediction_id, journal_entry_id, sequence, body, corrected_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        prediction_id,
                        entry_id,
                        len(corrections) + 1,
                        body,
                        format_utc(self._clock.now()),
                    ),
                )
        return next(
            e
            for e in self.list_timeline(prediction_id)
            if e.kind == "journal" and e.record_id == entry_id
        )

    def invalidate_or_delete(
        self,
        prediction_id: int,
        *,
        delete: bool,
        reason: str | None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> None:
        reason = _optional_text(reason, "reason")
        with self._database.transaction() as connection:
            current = read_prediction(connection, prediction_id)
            if (
                current.current_revision.revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise LifecycleContextChangedError
            now = self._clock.now()
            status = contract_status(
                current.status, None, now.date(), current.forecast_contract, now
            )
            if delete:
                if status is not PredictionStatus.OPEN:
                    raise PredictionDeletionDisallowedError(status.value)
                if not current.deletion_allowed:
                    raise PredictionDeletionDisallowedError("meaningful_history")
                connection.execute(
                    "DELETE FROM predictions WHERE id = ?", (prediction_id,)
                )
            else:
                if status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
                    raise LifecycleTransitionDisallowedError(status)
                connection.execute(
                    "INSERT INTO prediction_invalidations (prediction_id, invalidated_at, reason) VALUES (?, ?, ?)",
                    (prediction_id, format_utc(now), reason),
                )

    def list_timeline(self, prediction_id: int) -> tuple[QuantileTimelineEvent, ...]:
        with self._database.transaction() as connection:
            revisions = read_revisions(connection, prediction_id)
            anchors = {r.revision_id: r for r in revisions}
            events = [
                QuantileTimelineEvent(
                    "forecast", r.revision_id, r, r.created_at, r.rationale
                )
                for r in revisions
            ]
            for kind, table, field in (
                ("journal", "journal_entries", "body"),
                ("review", "forecast_reviews", "note"),
            ):
                for row in connection.execute(
                    f"SELECT * FROM {table} WHERE prediction_id = ? ORDER BY id",
                    (prediction_id,),
                ):
                    corrections = ()
                    if kind == "journal":
                        corrections = tuple(
                            JournalCorrection(
                                c["id"], c["body"], parse_utc(c["corrected_at"])
                            )
                            for c in connection.execute(
                                "SELECT * FROM journal_entry_corrections WHERE journal_entry_id = ? ORDER BY sequence",
                                (row["id"],),
                            )
                        )
                    events.append(
                        QuantileTimelineEvent(
                            kind,
                            row["id"],
                            anchors[row["quantile_revision_id"]],
                            parse_utc(row["created_at"]),
                            corrections[-1].body if corrections else row[field],
                            row[field],
                            corrections,
                        )
                    )
        kinds = {"forecast": 0, "journal": 1, "review": 2}
        return order_timeline(
            events, key=lambda e: (e.revision.sequence, kinds[e.kind], e.record_id)
        )
