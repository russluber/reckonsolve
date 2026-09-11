"""Numeric v2 persistence foundation, deliberately not wired to public creation yet."""

import sqlite3

from reckonsolve.clock import Clock, format_utc, parse_utc
from reckonsolve.domain.forecast_contracts import (
    ForecastCohort,
    ForecastingWindow,
    prospective_contract,
)
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    JournalCorrection,
    PredictionType,
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
from .predictions import ForecastContextChangedError, replace_tags


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
    """Internal storage API for the upcoming active workflow; no model selector."""

    def __init__(self, database: Database, clock: Clock) -> None:
        self._database = database
        self._clock = clock

    def create_prediction(self, new: NewQuantilePrediction) -> QuantileRevision:
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
            created = read_revisions(connection, prediction_id)[0]
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
        rationale = _optional_text(rationale, "rationale")
        with self._database.transaction() as connection:
            revisions = read_revisions(connection, prediction_id)
            current = revisions[-1]
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
            saved = read_revisions(connection, prediction_id)[-1]
        return saved

    def list_revisions(self, prediction_id: int) -> tuple[QuantileRevision, ...]:
        with self._database.transaction() as connection:
            return read_revisions(connection, prediction_id)

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
