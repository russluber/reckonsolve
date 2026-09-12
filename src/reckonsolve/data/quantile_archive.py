"""Current quantile summaries from stored cohort identity in the caller's snapshot."""

import sqlite3
from datetime import date

from reckonsolve.clock import parse_utc
from reckonsolve.domain.browser import PredictionBrowserItem
from reckonsolve.domain.predictions import (
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import FiveQuantiles

from .forecast_contracts import quantile_tables_exist, select_forecast_contract


def read_archive(connection: sqlite3.Connection) -> tuple[PredictionBrowserItem, ...]:
    if not quantile_tables_exist(connection):
        return ()
    rows = connection.execute("""
        SELECT p.*, r.created_at AS revision_at,
               r.q05_scaled, r.q25_scaled, r.q50_scaled, r.q75_scaled, r.q95_scaled,
               (SELECT MAX(created_at) FROM forecast_reviews WHERE prediction_id = p.id) AS review_at,
               (SELECT invalidated_at FROM prediction_invalidations WHERE prediction_id = p.id) AS invalid_at
        FROM predictions p
        JOIN prediction_forecast_contracts c ON c.prediction_id = p.id
        JOIN numeric_quantile_revisions r ON r.prediction_id = p.id
        WHERE c.forecast_model = 'numeric-quantiles-5-v2'
          AND r.sequence = (SELECT MAX(sequence) FROM numeric_quantile_revisions WHERE prediction_id = p.id)
        ORDER BY p.created_at DESC, p.id DESC
    """).fetchall()
    result = []
    for row in rows:
        tags = tuple(
            r[0]
            for r in connection.execute(
                "SELECT t.display_name FROM tags t JOIN prediction_tags p ON p.tag_id = t.id WHERE p.prediction_id = ? ORDER BY t.normalized_name, t.id",
                (row["id"],),
            )
        )
        result.append(
            PredictionBrowserItem(
                prediction_id=row["id"],
                question=row["question"],
                probability_percent=None,
                status=PredictionStatus(row["status"]),
                created_at=parse_utc(row["created_at"]),
                latest_revision_at=parse_utc(row["revision_at"]),
                expected_resolution=date.fromisoformat(row["expected_resolution"])
                if row["expected_resolution"]
                else None,
                latest_review_at=parse_utc(row["review_at"])
                if row["review_at"]
                else None,
                terminal_decision_at=parse_utc(row["invalid_at"])
                if row["invalid_at"]
                else None,
                tags=tags,
                prediction_type=PredictionType.NUMERIC,
                numeric_unit=row["numeric_unit"],
                forecast_contract=select_forecast_contract(connection, row["id"]),
                numeric_quantiles=FiveQuantiles(
                    *(
                        FixedPrecisionValue(
                            row[f"q{level:02}_scaled"], row["numeric_precision"]
                        )
                        for level in (5, 25, 50, 75, 95)
                    )
                ),
            )
        )
    return tuple(result)
