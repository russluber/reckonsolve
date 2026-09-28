"""Minimal current summaries needed to reopen an individually usable One-Shot."""

import sqlite3
from datetime import date

from reckonsolve.clock import parse_utc
from reckonsolve.domain.browser import PredictionBrowserItem

from .forecast_contracts import select_forecast_contract
from .one_shot_facts import read_one_shot


def read_archive(connection: sqlite3.Connection) -> tuple[PredictionBrowserItem, ...]:
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name = 'one_shot_forecast_times'"
        ).fetchone()
        is None
    ):
        return ()
    result = []
    for row in connection.execute("""SELECT p.* FROM predictions p
        JOIN one_shot_forecast_times t ON t.prediction_id = p.id ORDER BY p.id""").fetchall():
        identifier = row["id"]
        contract = select_forecast_contract(connection, identifier)
        record = read_one_shot(connection, identifier, contract)
        invalid = connection.execute(
            "SELECT invalidated_at FROM prediction_invalidations WHERE prediction_id = ?",
            (identifier,),
        ).fetchone()
        skipped = connection.execute(
            "SELECT 1 FROM postmortem_completions WHERE prediction_id = ?",
            (identifier,),
        ).fetchone()
        tags = tuple(
            r[0]
            for r in connection.execute(
                """SELECT t.display_name FROM tags t
            JOIN prediction_tags p ON p.tag_id = t.id WHERE p.prediction_id = ? ORDER BY t.normalized_name, t.id""",
                (identifier,),
            )
        )
        result.append(
            PredictionBrowserItem(
                prediction_id=identifier,
                question=row["question"],
                probability_percent=record.effective.probability_percent,
                status=record.status,
                created_at=record.recorded_at,
                latest_revision_at=record.recorded_at,
                expected_resolution=date.fromisoformat(row["expected_resolution"])
                if row["expected_resolution"]
                else None,
                terminal_decision_at=record.answer_recorded_at
                or (parse_utc(invalid[0]) if invalid else None),
                needs_postmortem=record.answer_recorded_at is not None
                and not record.effective.postmortem
                and skipped is None,
                tags=tags,
                prediction_type=contract.prediction_type,
                forecast_contract=contract,
                numeric_unit=row["numeric_unit"],
                numeric_quantiles=record.effective.quantiles,
                numeric_actual_value=record.effective.answer
                if record.definition
                else None,
            )
        )
    return tuple(result)
