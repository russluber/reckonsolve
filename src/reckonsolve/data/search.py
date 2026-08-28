"""Purpose-specific read access to the derived Prediction search projection."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date

from reckonsolve.clock import parse_utc
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.search import (
    ParsedSearchText,
    SearchClause,
    SearchDocument,
    SearchFragmentCandidate,
    SearchPrediction,
    SearchSourceKind,
    normalize_search_literal,
    search_tokens,
)

from .database import Database
from .search_index import (
    SEARCH_PROJECTION_VERSION,
    SearchIndexBusyError,
    SearchIndexError,
    SearchIndexRepairRequiredError,
)


@dataclass(slots=True)
class _CandidateAccumulator:
    row_id: int
    document: SearchDocument
    matched_clause_indexes: set[int]
    relevance: float


class SearchRepository:
    """Retrieve explainable fragments without exposing FTS syntax to callers."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def find_candidates(
        self,
        parsed_text: ParsedSearchText,
        *,
        include_superseded: bool,
    ) -> tuple[
        dict[int, SearchPrediction],
        tuple[SearchFragmentCandidate, ...],
    ]:
        """Return every candidate needed for Prediction-level coverage ranking."""

        try:
            return self._find_candidates(
                parsed_text,
                include_superseded=include_superseded,
            )
        except SearchIndexError:
            raise
        except sqlite3.Error as error:
            _raise_if_search_busy(error)
            raise SearchIndexRepairRequiredError(
                "The local search index could not complete this query."
            ) from error

    def _find_candidates(
        self,
        parsed_text: ParsedSearchText,
        *,
        include_superseded: bool,
    ) -> tuple[
        dict[int, SearchPrediction],
        tuple[SearchFragmentCandidate, ...],
    ]:

        if parsed_text.is_blank:
            return {}, ()
        with self._database.transaction() as connection:
            _require_ready_index(connection)
            candidates: dict[int, _CandidateAccumulator] = {}
            for clause_index, clause in enumerate(parsed_text.clauses):
                for row in connection.execute(
                    """
                    SELECT
                        rowid, prediction_id, source_kind, source_record_id,
                        source_version_id, source_sequence, occurred_at,
                        is_superseded, body,
                        bm25(prediction_search) AS relevance
                    FROM prediction_search
                    WHERE prediction_search MATCH ?
                        AND (? = 1 OR is_superseded = 0)
                    ORDER BY relevance, rowid
                    """,
                    (_fts_query(clause), int(include_superseded)),
                ).fetchall():
                    _merge_candidate(candidates, row, clause_index=clause_index)

            if parsed_text.clauses:
                question_rows = connection.execute(
                    """
                    SELECT
                        rowid, prediction_id, source_kind, source_record_id,
                        source_version_id, source_sequence, occurred_at,
                        is_superseded, body, 0.0 AS relevance
                    FROM prediction_search
                    WHERE source_kind = 'question' AND is_superseded = 0
                    ORDER BY prediction_id, rowid
                    """
                ).fetchall()
                all_clause_indexes = range(len(parsed_text.clauses))
                for row in question_rows:
                    if parsed_text.literal_text in normalize_search_literal(
                        str(row["body"])
                    ):
                        for clause_index in all_clause_indexes:
                            _merge_candidate(
                                candidates,
                                row,
                                clause_index=clause_index,
                            )
            else:
                # Punctuation-only text has no FTS tokens, so a bounded scan of
                # derived documents preserves ordinary literal behavior.
                rows = connection.execute(
                    """
                    SELECT
                        rowid, prediction_id, source_kind, source_record_id,
                        source_version_id, source_sequence, occurred_at,
                        is_superseded, body, 0.0 AS relevance
                    FROM prediction_search
                    WHERE (? = 1 OR is_superseded = 0)
                    ORDER BY prediction_id, rowid
                    """,
                    (int(include_superseded),),
                ).fetchall()
                for row in rows:
                    if parsed_text.literal_text in normalize_search_literal(
                        str(row["body"])
                    ):
                        _merge_candidate(candidates, row, clause_index=None)

            prediction_ids = sorted(
                {candidate.document.prediction_id for candidate in candidates.values()}
            )
            predictions = _select_predictions(connection, prediction_ids)

        fragment_candidates = tuple(
            SearchFragmentCandidate(
                row_id=candidate.row_id,
                document=candidate.document,
                matched_clause_indexes=frozenset(candidate.matched_clause_indexes),
                relevance=candidate.relevance,
                literal_match=(
                    parsed_text.literal_text
                    in normalize_search_literal(candidate.document.text)
                ),
                exact_text_match=(
                    parsed_text.literal_text
                    == normalize_search_literal(candidate.document.text)
                ),
            )
            for candidate in candidates.values()
        )
        return predictions, fragment_candidates

    def suggest_spelling(
        self,
        parsed_text: ParsedSearchText,
        *,
        include_superseded: bool,
    ) -> str | None:
        """Suggest one corpus word for a simple one-edit zero-result query."""

        try:
            return self._suggest_spelling(
                parsed_text,
                include_superseded=include_superseded,
            )
        except SearchIndexError:
            raise
        except sqlite3.Error as error:
            _raise_if_search_busy(error)
            raise SearchIndexRepairRequiredError(
                "The local search index could not derive a spelling suggestion."
            ) from error

    def _suggest_spelling(
        self,
        parsed_text: ParsedSearchText,
        *,
        include_superseded: bool,
    ) -> str | None:

        if len(parsed_text.clauses) != 1:
            return None
        clause = parsed_text.clauses[0]
        if clause.is_phrase or len(clause.tokens) != 1:
            return None
        query_word = clause.tokens[0]
        if len(query_word) < 4:
            return None

        with self._database.transaction() as connection:
            _require_ready_index(connection)
            rows = connection.execute(
                """
                SELECT body
                FROM prediction_search
                WHERE (? = 1 OR is_superseded = 0)
                """,
                (int(include_superseded),),
            ).fetchall()
        vocabulary = Counter(
            token
            for row in rows
            for token in search_tokens(str(row["body"]))
            if token != query_word
        )
        choices = [
            token
            for token in vocabulary
            if abs(len(token) - len(query_word)) <= 1
            and _edit_distance_at_most_one(query_word, token)
        ]
        if not choices:
            return None
        return min(choices, key=lambda token: (-vocabulary[token], token))


def _fts_query(clause: SearchClause) -> str:
    phrase = '"' + " ".join(clause.tokens).replace('"', '""') + '"'
    return phrase + ("*" if clause.is_prefix and not clause.is_phrase else "")


def _merge_candidate(
    candidates: dict[int, _CandidateAccumulator],
    row,
    *,
    clause_index: int | None,
) -> None:
    row_id = int(row["rowid"])
    existing = candidates.get(row_id)
    if existing is None:
        existing = _CandidateAccumulator(
            row_id=row_id,
            document=_map_document(row),
            matched_clause_indexes=set(),
            relevance=float(row["relevance"]),
        )
        candidates[row_id] = existing
    else:
        existing.relevance = min(existing.relevance, float(row["relevance"]))
    if clause_index is not None:
        existing.matched_clause_indexes.add(clause_index)


def _map_document(row) -> SearchDocument:
    return SearchDocument(
        prediction_id=int(row["prediction_id"]),
        source_kind=SearchSourceKind(str(row["source_kind"])),
        source_record_id=int(row["source_record_id"]),
        source_version_id=(
            None if row["source_version_id"] is None else int(row["source_version_id"])
        ),
        source_sequence=(
            None if row["source_sequence"] is None else int(row["source_sequence"])
        ),
        occurred_at=(
            None if row["occurred_at"] is None else parse_utc(str(row["occurred_at"]))
        ),
        is_superseded=bool(int(row["is_superseded"])),
        text=str(row["body"]),
    )


def _select_predictions(
    connection,
    prediction_ids: list[int],
) -> dict[int, SearchPrediction]:
    predictions: dict[int, SearchPrediction] = {}
    for prediction_id in prediction_ids:
        row = connection.execute(
            """
            SELECT
                id, question, prediction_type, status,
                created_at, forecast_deadline
            FROM predictions
            WHERE id = ?
            """,
            (prediction_id,),
        ).fetchone()
        if row is None:
            continue
        tag_rows = connection.execute(
            """
            SELECT tag.display_name
            FROM tags AS tag
            JOIN prediction_tags AS link ON link.tag_id = tag.id
            WHERE link.prediction_id = ?
            ORDER BY tag.normalized_name, tag.id
            """,
            (prediction_id,),
        ).fetchall()
        predictions[prediction_id] = SearchPrediction(
            prediction_id=prediction_id,
            question=str(row["question"]),
            prediction_type=PredictionType(str(row["prediction_type"])),
            status=PredictionStatus(str(row["status"])),
            created_at=parse_utc(str(row["created_at"])),
            forecast_deadline=(
                None
                if row["forecast_deadline"] is None
                else date.fromisoformat(str(row["forecast_deadline"]))
            ),
            tags=tuple(str(tag_row[0]) for tag_row in tag_rows),
        )
    return predictions


def _require_ready_index(connection) -> None:
    try:
        state = connection.execute(
            """
            SELECT projection_version, document_count
            FROM search_index_state
            WHERE singleton_id = 1
            """
        ).fetchone()
        dirty = connection.execute(
            "SELECT 1 FROM search_dirty_predictions LIMIT 1"
        ).fetchone()
        actual_document_count = int(
            connection.execute("SELECT COUNT(*) FROM prediction_search").fetchone()[0]
        )
    except Exception as error:
        raise SearchIndexRepairRequiredError(
            "The local search index is unavailable and requires repair."
        ) from error
    if (
        state is None
        or int(state[0]) != SEARCH_PROJECTION_VERSION
        or int(state[1]) != actual_document_count
        or dirty is not None
    ):
        raise SearchIndexRepairRequiredError(
            "The local search index is stale and requires repair."
        )


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        differences = [
            index
            for index, (a, b) in enumerate(zip(left, right, strict=True))
            if a != b
        ]
        if len(differences) == 1:
            return True
        return (
            len(differences) == 2
            and differences[1] == differences[0] + 1
            and left[differences[0]] == right[differences[1]]
            and left[differences[1]] == right[differences[0]]
        )
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    short_index = 0
    long_index = 0
    skipped = False
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
        elif skipped:
            return False
        else:
            skipped = True
            long_index += 1
    return True


def _raise_if_search_busy(error: sqlite3.Error) -> None:
    error_code = getattr(error, "sqlite_errorcode", None)
    if (
        isinstance(error_code, int)
        and error_code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    ) or "locked" in str(error).casefold():
        raise SearchIndexBusyError(
            "The local database is temporarily busy with another connection."
        ) from error
