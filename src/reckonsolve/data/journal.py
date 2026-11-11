"""One checked snapshot for Journal retrieval, activity and scoring sources."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from reckonsolve.clock import parse_utc
from reckonsolve.domain.analytics import (
    QuantileAnalyticsSource,
    TrajectoryAnalyticsSource,
)
from reckonsolve.domain.browser import PredictionBrowserSnapshot
from reckonsolve.domain.one_shot import OneShotRecord
from reckonsolve.domain.search import (
    ParsedSearchText,
    SearchDocument,
    SearchFragmentCandidate,
    SearchPrediction,
    SearchSourceKind,
)

from .analytics import _load_quantile_source, _load_trajectory_source
from .database import Database
from .forecast_contracts import (
    binary_corrections_relation,
    numeric_corrections_relation,
)
from .predictions import read_browser_snapshot
from .search import read_search_candidates, read_spelling_suggestion
from .search_index import project_prediction_documents


@dataclass(frozen=True, slots=True)
class JournalSource:
    browser: PredictionBrowserSnapshot
    trajectory: TrajectoryAnalyticsSource
    numeric: QuantileAnalyticsSource
    one_shots: dict[int, OneShotRecord]
    activity: dict[int, datetime]
    question_dates: dict[int, datetime]
    search_predictions: dict[int, SearchPrediction]
    candidates: tuple[SearchFragmentCandidate, ...]
    tags: tuple[str, ...]


class JournalPredictionMissingError(LookupError):
    """The Prediction, rather than just an editable text source, is absent."""


class JournalRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def resolve_passage(
        self, identifier: int, document: SearchDocument
    ) -> tuple[SearchDocument | None, bool]:
        """Recheck a canonical source, never substitute an arbitrary match."""
        with self.database.read_snapshot() as connection:
            if not connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?", (identifier,)
            ).fetchone():
                raise JournalPredictionMissingError(identifier)
            documents = project_prediction_documents(connection, identifier)
            for current in documents:
                if current == document:
                    return current, False
            if (
                document.source_kind is SearchSourceKind.JOURNAL
                and not document.is_superseded
            ):
                for current in documents:
                    if (
                        current.source_kind is document.source_kind
                        and current.source_record_id == document.source_record_id
                        and not current.is_superseded
                    ):
                        return current, current.text != document.text
            # Historical navigation is explicit; a formerly current source must
            # never silently become a historical match under current-only search.
            for current in documents:
                if document.is_superseded and (
                    current.source_kind,
                    current.source_record_id,
                    current.source_version_id,
                    current.text,
                ) == (
                    document.source_kind,
                    document.source_record_id,
                    document.source_version_id,
                    document.text,
                ):
                    return current, False
            if not document.is_superseded:
                for current in documents:
                    if (
                        current.source_kind is document.source_kind
                        and current.source_record_id == document.source_record_id
                        and not current.is_superseded
                    ):
                        return current, True
                return None, True  # e.g. an ordinary removed tag; keep current Detail.
            raise ValueError(
                "The historical source could not be verified in canonical history."
            )

    def read(self, parsed: ParsedSearchText, *, include_history: bool) -> JournalSource:
        records = {}
        with self.database.read_snapshot(one_shots=records) as connection:
            browser = read_browser_snapshot(connection, one_shots=records)
            snapshots = {
                item.prediction_id: SearchPrediction(
                    prediction_id=item.prediction_id,
                    question=item.question,
                    prediction_type=item.prediction_type,
                    status=item.status,
                    created_at=item.created_at,
                    forecast_deadline=item.forecast_deadline,
                    tags=item.tags,
                    forecast_contract=item.forecast_contract,
                )
                for item in browser.predictions
            }
            predictions, candidates, _ = (
                read_search_candidates(
                    connection,
                    parsed,
                    include_superseded=include_history,
                    prediction_snapshots=snapshots,
                )
                if not parsed.is_blank
                else ({}, (), ())
            )
            question_dates = {
                row[0]: parse_utc(row[1])
                for row in connection.execute("""SELECT prediction_id, occurred_at
                    FROM prediction_search WHERE source_kind = 'question'
                    AND is_superseded = 0 AND occurred_at IS NOT NULL""")
            }
            return JournalSource(
                browser,
                _load_trajectory_source(connection),
                _load_quantile_source(connection),
                records,
                read_activity(connection),
                question_dates,
                predictions,
                candidates,
                tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT display_name FROM tags ORDER BY normalized_name, id"
                    )
                ),
            )

    def suggest(self, parsed: ParsedSearchText, *, include_history: bool) -> str | None:
        with self.database.read_snapshot() as connection:
            return read_spelling_suggestion(
                connection, parsed, include_superseded=include_history
            )


def read_activity(connection: sqlite3.Connection) -> dict[int, datetime]:
    """Derive qualifying work; repair timestamps never substitute for activity."""
    events = connection.execute(f"""
        SELECT id, created_at FROM predictions
        UNION ALL SELECT prediction_id, created_at FROM forecast_revisions
        UNION ALL SELECT prediction_id, created_at FROM numeric_quantile_revisions
        UNION ALL SELECT prediction_id, created_at FROM forecast_reviews
        UNION ALL SELECT prediction_id, created_at FROM journal_entries
        UNION ALL SELECT prediction_id, resolved_at FROM resolutions
        UNION ALL SELECT prediction_id, resolved_at FROM numeric_resolutions
        UNION ALL SELECT prediction_id, invalidated_at FROM prediction_invalidations
        UNION ALL SELECT prediction_id, corrected_at FROM {binary_corrections_relation(connection)}
            WHERE old_postmortem IS NULL AND new_postmortem IS NOT NULL
        UNION ALL SELECT prediction_id, corrected_at FROM {numeric_corrections_relation(connection)}
            WHERE old_postmortem IS NULL AND new_postmortem IS NOT NULL
    """).fetchall()
    if any(
        row[1] == "source_action"
        for row in connection.execute("PRAGMA table_info(one_shot_corrections)")
    ):
        events += connection.execute("""SELECT prediction_id, corrected_at
            FROM one_shot_corrections WHERE source_action = 'postmortem'
            AND old_postmortem IS NULL AND new_postmortem IS NOT NULL""").fetchall()
    result = {}
    for identifier, timestamp in events:
        instant = parse_utc(timestamp)
        if identifier not in result or instant > result[identifier]:
            result[identifier] = instant
    return result
