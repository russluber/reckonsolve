"""Controlled mixed native fixture for measured Journal responsiveness."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from supported_fixtures import create_binary, create_numeric

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import NewOneShotPrediction, OneShotValues
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)


@dataclass
class CorpusClock:
    instant: datetime = datetime(2026, 11, 1, 12, tzinfo=UTC)

    def now(self):
        return self.instant


def populate_mixed_corpus(database, *, copies: int = 250):
    """Eight real-operation templates, then exact relational fixture replicas.

    Copy only supported canonical rows, preserving foreign-key mappings and
    original/correction chains. Rebuild derived search in the same transaction.
    This fixture builder never opens a default/profile database.
    """
    clock = CorpusClock()
    operations = PredictionOperations(database, clock, UTC)
    values = {5: -200, 25: -80, 50: 10, 75: 400, 95: 1500}
    for answered in (False, True):
        for one_shot in (False, True):
            for kind in PredictionType:
                numeric = kind is PredictionType.NUMERIC
                question = (
                    f"Will the remembered regional transport outcome support the elephant hypothesis? {kind.value} {one_shot} {answered} "
                    + "Long Question context and exact conditions. " * 7
                )
                if one_shot:
                    prediction = operations.one_shots.create(
                        NewOneShotPrediction(
                            question,
                            one_shot_contract(kind),
                            OneShotValues(
                                probability_percent=None if numeric else 63,
                                quantiles=FiveQuantiles.from_values(values, 0)
                                if numeric
                                else None,
                                answer=(
                                    FixedPrecisionValue(10, 0)
                                    if numeric
                                    else BinaryOutcome.YES
                                )
                                if answered
                                else None,
                            ),
                            QuantileDefinition(
                                "passengers", 0, NumericValueConstraint.WHOLE_NUMBER
                            )
                            if numeric
                            else None,
                            background="Supporting railway evidence " * 30,
                            tags=("Transport", "Research"),
                        )
                    )
                else:
                    prediction = (
                        create_numeric(
                            operations,
                            question,
                            "passengers",
                            0,
                            values,
                            tags=("Transport", "Research"),
                        )
                        if numeric
                        else create_binary(
                            operations, question, 63, tags=("Transport", "Research")
                        )
                    )
                    for index in range(12):
                        clock.instant += timedelta(minutes=1)
                        if numeric:
                            prediction = operations.revise_quantile_forecast(
                                prediction.prediction_id,
                                {
                                    key: value + index + 1
                                    for key, value in values.items()
                                },
                                rationale="Substantial railway revision rationale "
                                * 20,
                                expected_revision_id=prediction.current_revision.revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
                        else:
                            prediction = operations.revise_forecast(
                                prediction.prediction_id,
                                40 + index,
                                rationale="Substantial railway revision rationale "
                                * 20,
                                expected_revision_id=prediction.current_revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
                if not one_shot:
                    for index in range(6):
                        clock.instant += timedelta(minutes=1)
                        entry = (
                            operations.add_numeric_journal_entry(
                                prediction.prediction_id,
                                "Original superseded commuter evidence " * 25,
                                expected_revision_id=prediction.current_revision.revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
                            if numeric
                            else operations.add_journal_entry(
                                prediction.prediction_id,
                                "Original superseded commuter evidence " * 25,
                                expected_revision_id=prediction.current_revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
                        )
                        clock.instant += timedelta(minutes=1)
                        correction = (
                            operations.correct_numeric_journal_entry
                            if numeric
                            else operations.correct_journal_entry
                        )
                        correction(
                            prediction.prediction_id,
                            entry.entry_id,
                            "Current corrected railway evidence " * 25,
                            expected_correction_id=None,
                        )
                    if answered:
                        clock.instant += timedelta(minutes=1)
                        if numeric:
                            operations.resolve_numeric_prediction(
                                prediction.prediction_id,
                                "10",
                                use_recorded_time=True,
                                expected_revision_id=prediction.current_revision.revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
                        else:
                            operations.resolve_prediction(
                                prediction.prediction_id,
                                BinaryOutcome.YES,
                                use_recorded_time=True,
                                expected_revision_id=prediction.current_revision_id,
                                expected_metadata_version=prediction.metadata_version,
                            )
    with database.transaction() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
            if not row[0].startswith(("sqlite_", "prediction_search", "search_"))
        }
        foreign = {
            table: tuple(connection.execute(f'PRAGMA foreign_key_list("{table}")'))
            for table in tables
        }
        implicit = {"one_shot_answer_times": {"resolutions", "numeric_resolutions"}}
        selected = {"predictions"}
        while True:
            expanded = selected | {
                table
                for table in tables
                if any(row[2] in selected for row in foreign[table])
            }
            if expanded == selected:
                break
            selected = expanded
        for table in selected - {"predictions", "prediction_forecast_contracts"}:
            implicit.setdefault(table, set()).add("prediction_forecast_contracts")
        for table in ("resolutions", "numeric_resolutions", "prediction_invalidations"):
            implicit.setdefault(table, set()).update(
                {
                    "journal_entries",
                    "forecast_reviews",
                    "forecast_revisions",
                    "numeric_quantile_revisions",
                }
                & selected
            )
        pending, ordered = set(selected), []
        while pending:
            ready = sorted(
                table
                for table in pending
                if not (
                    {row[2] for row in foreign[table] if row[2] != table}
                    | implicit.get(table, set())
                )
                & pending
            )
            if not ready:
                raise AssertionError(
                    "Fixture has an unexpected cyclic table dependency"
                )
            ordered.extend(ready)
            pending.difference_update(ready)
        snapshots = []
        for table in ordered:
            columns = tuple(
                row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
            )
            shifted = {"id"} & set(columns)
            shifted.update(
                row[3]
                for row in foreign[table]
                if row[2] in selected and row[4] in ("id", "prediction_id")
            )
            rows = tuple(
                tuple(row) for row in connection.execute(f'SELECT * FROM "{table}"')
            )
            snapshots.append((table, columns, shifted, rows))
        for copy in range(1, copies):
            offset = copy * 10000
            for table, columns, shifted, rows in snapshots:
                if not rows:
                    continue
                connection.executemany(
                    f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in columns)})',
                    [
                        tuple(
                            "open"
                            if table == "predictions" and column == "status"
                            else value + offset
                            if column in shifted and value is not None
                            else value
                            for column, value in zip(columns, row, strict=True)
                        )
                        for row in rows
                    ],
                )
            parent_columns, parent_rows = next(
                (columns, rows)
                for table, columns, _shifted, rows in snapshots
                if table == "predictions"
            )
            for row in parent_rows:
                facts = dict(zip(parent_columns, row, strict=True))
                if facts["status"] != "open":
                    connection.execute(
                        "UPDATE predictions SET status = ? WHERE id = ?",
                        (facts["status"], facts["id"] + offset),
                    )
    return operations, clock
