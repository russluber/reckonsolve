"""Purpose-specific read access to the derived Prediction search projection."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date

from reckonsolve.clock import parse_utc
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)
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
        tuple[str, ...],
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
        tuple[str, ...],
    ]:

        if parsed_text.is_blank:
            return {}, (), ()
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
            available_tags = tuple(
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT display_name
                    FROM tags
                    WHERE EXISTS (
                        SELECT 1 FROM prediction_tags
                        WHERE prediction_tags.tag_id = tags.id
                    )
                    ORDER BY normalized_name, id
                    """
                ).fetchall()
            )

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
        return predictions, fragment_candidates, available_tags

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
    if not prediction_ids:
        return {}
    wanted_ids = set(prediction_ids)
    rows = connection.execute(
        """
        SELECT
            prediction.id AS prediction_id,
            prediction.question,
            prediction.prediction_type,
            prediction.status,
            prediction.created_at,
            prediction.forecast_deadline,
            current_revision.probability_percent,
            NULL AS numeric_lower_scaled,
            NULL AS numeric_median_scaled,
            NULL AS numeric_upper_scaled,
            NULL AS numeric_confidence_percent,
            NULL AS numeric_unit,
            NULL AS numeric_precision,
            current_revision.created_at AS latest_revision_at,
            (
                SELECT COALESCE(
                    (
                        SELECT correction.new_outcome
                        FROM resolution_corrections AS correction
                        WHERE correction.resolution_id = resolution.id
                        ORDER BY correction.sequence DESC
                        LIMIT 1
                    ),
                    resolution.outcome
                )
                FROM resolutions AS resolution
                WHERE resolution.prediction_id = prediction.id
            ) AS binary_outcome,
            NULL AS numeric_actual_scaled
        FROM predictions AS prediction
        JOIN forecast_revisions AS current_revision
            ON current_revision.id = (
                SELECT candidate.id
                FROM forecast_revisions AS candidate
                WHERE candidate.prediction_id = prediction.id
                ORDER BY candidate.sequence DESC
                LIMIT 1
            )
        WHERE prediction.prediction_type = 'binary'
        UNION ALL
        SELECT
            prediction.id AS prediction_id,
            prediction.question,
            prediction.prediction_type,
            prediction.status,
            prediction.created_at,
            prediction.forecast_deadline,
            NULL AS probability_percent,
            current_revision.lower_scaled AS numeric_lower_scaled,
            current_revision.median_scaled AS numeric_median_scaled,
            current_revision.upper_scaled AS numeric_upper_scaled,
            current_revision.confidence_percent AS numeric_confidence_percent,
            prediction.numeric_unit,
            prediction.numeric_precision,
            current_revision.created_at AS latest_revision_at,
            NULL AS binary_outcome,
            (
                SELECT COALESCE(
                    (
                        SELECT correction.new_actual_scaled
                        FROM numeric_resolution_corrections AS correction
                        WHERE correction.numeric_resolution_id = resolution.id
                        ORDER BY correction.sequence DESC
                        LIMIT 1
                    ),
                    resolution.actual_scaled
                )
                FROM numeric_resolutions AS resolution
                WHERE resolution.prediction_id = prediction.id
            ) AS numeric_actual_scaled
        FROM predictions AS prediction
        JOIN numeric_forecast_revisions AS current_revision
            ON current_revision.id = (
                SELECT candidate.id
                FROM numeric_forecast_revisions AS candidate
                WHERE candidate.prediction_id = prediction.id
                ORDER BY candidate.sequence DESC
                LIMIT 1
            )
        WHERE prediction.prediction_type = 'numeric'
        """
    ).fetchall()
    tag_rows = connection.execute(
        """
        SELECT link.prediction_id, tag.display_name
        FROM tags AS tag
        JOIN prediction_tags AS link ON link.tag_id = tag.id
        ORDER BY tag.normalized_name, tag.id, link.prediction_id
        """
    ).fetchall()
    tags_by_prediction: dict[int, list[str]] = {}
    for tag_row in tag_rows:
        prediction_id = int(tag_row["prediction_id"])
        if prediction_id in wanted_ids:
            tags_by_prediction.setdefault(prediction_id, []).append(
                str(tag_row["display_name"])
            )

    predictions: dict[int, SearchPrediction] = {}
    for row in rows:
        prediction_id = int(row["prediction_id"])
        if prediction_id not in wanted_ids:
            continue
        prediction_type = PredictionType(str(row["prediction_type"]))
        decimal_places = (
            None if row["numeric_precision"] is None else int(row["numeric_precision"])
        )
        predictions[prediction_id] = SearchPrediction(
            prediction_id=prediction_id,
            question=str(row["question"]),
            prediction_type=prediction_type,
            status=PredictionStatus(str(row["status"])),
            created_at=parse_utc(str(row["created_at"])),
            forecast_deadline=(
                None
                if row["forecast_deadline"] is None
                else date.fromisoformat(str(row["forecast_deadline"]))
            ),
            tags=tuple(tags_by_prediction.get(prediction_id, ())),
            latest_revision_at=parse_utc(str(row["latest_revision_at"])),
            probability_percent=(
                None
                if row["probability_percent"] is None
                else int(row["probability_percent"])
            ),
            numeric_lower_bound=(
                None
                if decimal_places is None
                else FixedPrecisionValue(
                    int(row["numeric_lower_scaled"]), decimal_places
                )
            ),
            numeric_median_estimate=(
                None
                if decimal_places is None
                else FixedPrecisionValue(
                    int(row["numeric_median_scaled"]), decimal_places
                )
            ),
            numeric_upper_bound=(
                None
                if decimal_places is None
                else FixedPrecisionValue(
                    int(row["numeric_upper_scaled"]), decimal_places
                )
            ),
            numeric_confidence_percent=(
                None
                if row["numeric_confidence_percent"] is None
                else int(row["numeric_confidence_percent"])
            ),
            numeric_unit=(
                None if row["numeric_unit"] is None else str(row["numeric_unit"])
            ),
            binary_outcome=(
                None
                if row["binary_outcome"] is None
                else BinaryOutcome(str(row["binary_outcome"]))
            ),
            numeric_actual_value=(
                None
                if decimal_places is None or row["numeric_actual_scaled"] is None
                else FixedPrecisionValue(
                    int(row["numeric_actual_scaled"]), decimal_places
                )
            ),
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
