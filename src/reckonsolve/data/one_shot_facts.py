"""One-Shot row mapping and validated replay, without transaction ownership."""

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime

from reckonsolve.clock import parse_utc
from reckonsolve.domain.forecast_contracts import ForecastContract
from reckonsolve.domain.one_shot import OneShotValues, ReportedTime
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)


@dataclass(frozen=True, slots=True)
class OneShotCorrection:
    correction_id: int
    sequence: int
    before: OneShotValues
    after: OneShotValues
    corrected_at: datetime
    note: str | None


@dataclass(frozen=True, slots=True)
class OneShotRecord:
    prediction_id: int
    contract: ForecastContract
    definition: QuantileDefinition | None
    status: PredictionStatus
    recorded_at: datetime
    answer_recorded_at: datetime | None
    metadata_version: int
    original: OneShotValues
    effective: OneShotValues
    corrections: tuple[OneShotCorrection, ...]

    @property
    def context(self) -> tuple[int, int | None, int | None]:
        return (
            self.metadata_version,
            self.corrections[-1].correction_id if self.corrections else None,
            1 if self.answer_recorded_at is not None else None,
        )


def _reported_columns(value: ReportedTime | None) -> tuple[str | None, int, int | None]:
    return (
        (None, 0, None)
        if value is None
        else (
            value.wall_time.isoformat(timespec="minutes"),
            int(value.approximate),
            value.offset_minutes,
        )
    )


def _snapshot(values: OneShotValues) -> tuple[object, ...]:
    return (
        values.probability_percent,
        *(
            (v.scaled_value for v in values.quantiles.values)
            if values.quantiles
            else (None,) * 5
        ),
        *_reported_columns(values.forecast_reported),
        values.answer.value if isinstance(values.answer, BinaryOutcome) else None,
        values.answer.scaled_value
        if isinstance(values.answer, FixedPrecisionValue)
        else None,
        *_reported_columns(values.reveal_reported),
        values.resolution_notes,
        values.postmortem,
    )


def _values(row: sqlite3.Row, precision: int | None, prefix: str = "") -> OneShotValues:
    def reported(kind: str) -> ReportedTime | None:
        wall = row[f"{prefix}{kind}_wall"]
        approximate = row[f"{prefix}{kind}_approximate"]
        offset = row[f"{prefix}{kind}_offset"]
        if approximate not in (0, 1) or (
            wall is None and (approximate != 0 or offset is not None)
        ):
            raise ValueError("Reported time metadata is inconsistent.")
        return (
            None
            if wall is None
            else ReportedTime(
                datetime.fromisoformat(wall),
                bool(approximate),
                offset,
            )
        )

    quantiles = (
        None
        if precision is None
        else FiveQuantiles(
            *(
                FixedPrecisionValue(row[f"{prefix}q{q:02}_scaled"], precision)
                for q in (5, 25, 50, 75, 95)
            )
        )
    )
    outcome, actual = row[prefix + "outcome"], row[prefix + "actual_scaled"]
    answer = (
        BinaryOutcome(outcome)
        if outcome is not None
        else (FixedPrecisionValue(actual, precision) if actual is not None else None)
    )
    return OneShotValues(
        row[prefix + "probability_percent"],
        quantiles,
        answer,
        reported("forecast"),
        reported("reveal"),
        row[prefix + "resolution_notes"],
        row[prefix + "postmortem"],
    )


def read_one_shot(
    connection: sqlite3.Connection, prediction_id: int, contract: ForecastContract
) -> OneShotRecord:
    connection = connection.cursor()
    connection.row_factory = sqlite3.Row
    parent = connection.execute(
        "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
    ).fetchone()
    precision = parent["numeric_precision"]
    definition = None
    if precision is not None:
        row = connection.execute(
            "SELECT value_constraint FROM numeric_quantile_definitions WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone()
        definition = QuantileDefinition(
            parent["numeric_unit"], precision, NumericValueConstraint(row[0])
        )
    original_row = connection.execute(
        "SELECT * FROM one_shot_original_facts WHERE prediction_id = ?",
        (prediction_id,),
    ).fetchone()
    if original_row is None:
        raise ValueError("A complete One-Shot original forecast is required.")
    original = _values(original_row, precision)
    original.validate_contract(contract, definition)
    corrections = tuple(
        OneShotCorrection(
            row["id"],
            row["sequence"],
            _values(row, precision, "old_"),
            _values(row, precision, "new_"),
            parse_utc(row["corrected_at"]),
            row["note"],
        )
        for row in connection.execute(
            "SELECT * FROM one_shot_corrections WHERE prediction_id = ? ORDER BY sequence",
            (prediction_id,),
        )
    )
    effective = _values(
        connection.execute(
            "SELECT * FROM one_shot_effective_facts WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone(),
        precision,
    )
    effective.validate_contract(contract, definition)
    table = "resolutions" if precision is None else "numeric_resolutions"
    answer_row = connection.execute(
        f"SELECT resolved_at FROM {table} WHERE prediction_id = ?", (prediction_id,)
    ).fetchone()
    recorded = parse_utc(parent["created_at"])
    answered = None if answer_row is None else parse_utc(answer_row[0])
    # Replay independently of the SQL effective projection to detect malformed
    # imported/tampered chains before they can be scored or copied by backup.
    current = replace(
        original,
        answer=None,
        reveal_reported=None,
        resolution_notes=None,
        postmortem=None,
    )
    previous_time = recorded
    for sequence, correction in enumerate(corrections, 1):
        if current.answer is None and correction.before.answer is not None:
            current = replace(
                current,
                answer=original.answer,
                reveal_reported=original.reveal_reported,
                resolution_notes=original.resolution_notes,
                postmortem=original.postmortem,
            )
        correction.before.validate_contract(contract, definition)
        correction.after.validate_contract(contract, definition)
        if (
            correction.sequence != sequence
            or correction.before != current
            or correction.before == correction.after
            or (correction.before.answer is None) != (correction.after.answer is None)
            or correction.corrected_at < previous_time
            or (
                correction.before.answer is not None
                and (answered is None or correction.corrected_at < answered)
            )
            or (
                correction.before.answer is None
                and answered is not None
                and correction.corrected_at > answered
            )
        ):
            raise ValueError("One-Shot correction history is inconsistent.")
        current = correction.after
        previous_time = correction.corrected_at
    if current.answer is None and original.answer is not None:
        current = replace(
            current,
            answer=original.answer,
            reveal_reported=original.reveal_reported,
            resolution_notes=original.resolution_notes,
            postmortem=original.postmortem,
        )
    status = PredictionStatus(parent["status"])
    if (
        current != effective
        or (status is PredictionStatus.RESOLVED) != (original.answer is not None)
        or (answered is not None and answered < recorded)
    ):
        raise ValueError("One-Shot original and effective facts are inconsistent.")
    return OneShotRecord(
        prediction_id,
        contract,
        definition,
        status,
        recorded,
        answered,
        parent["metadata_version"],
        original,
        effective,
        corrections,
    )
