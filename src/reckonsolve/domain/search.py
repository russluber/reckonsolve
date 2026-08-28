"""Presentation-neutral full-text search values and pure relevance rules."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum

from .predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)


class SearchValidationError(ValueError):
    """A search request has an invalid user-supplied value."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class SearchMatchMode(StrEnum):
    """How independently parsed query clauses combine within one Prediction."""

    ALL = "all"
    ANY = "any"


class SearchSourceKind(StrEnum):
    """Stable classifications for searchable user-authored text."""

    QUESTION = "question"
    TAG = "tag"
    BACKGROUND = "background"
    RESOLUTION_CRITERIA = "resolution_criteria"
    FORECAST_RATIONALE = "forecast_rationale"
    FORECAST_REVIEW = "forecast_review"
    JOURNAL = "journal"
    RESOLUTION_NOTES = "resolution_notes"
    POSTMORTEM = "postmortem"
    INVALIDATION_REASON = "invalidation_reason"
    OUTCOME_CORRECTION_REASON = "outcome_correction_reason"


@dataclass(frozen=True, slots=True)
class SearchClause:
    """One safely parsed word or fragment-local phrase."""

    tokens: tuple[str, ...]
    is_phrase: bool = False
    is_prefix: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.tokens)


@dataclass(frozen=True, slots=True)
class ParsedSearchText:
    """Normalized ordinary user text without exposed FTS query syntax."""

    raw_text: str
    literal_text: str
    clauses: tuple[SearchClause, ...]

    @property
    def is_blank(self) -> bool:
        return not self.literal_text

    @property
    def coverage_size(self) -> int:
        if self.is_blank:
            return 0
        return max(1, len(self.clauses))


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """The M32 text-and-history search request."""

    text: str
    match_mode: SearchMatchMode = SearchMatchMode.ALL
    include_superseded: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise SearchValidationError("Search text must be text.", field="text")
        if not isinstance(self.match_mode, SearchMatchMode):
            raise SearchValidationError(
                "The search word-matching mode is invalid.",
                field="match_mode",
            )
        if not isinstance(self.include_superseded, bool):
            raise SearchValidationError(
                "The historical search choice is invalid.",
                field="include_superseded",
            )


@dataclass(frozen=True, slots=True)
class SearchDocument:
    """One rebuildable searchable fragment derived from canonical history."""

    prediction_id: int
    source_kind: SearchSourceKind
    source_record_id: int
    source_version_id: int | None
    source_sequence: int | None
    occurred_at: datetime | None
    is_superseded: bool
    text: str


@dataclass(frozen=True, slots=True)
class SearchPrediction:
    """Current canonical identity carried beside matching fragments."""

    prediction_id: int
    question: str
    prediction_type: PredictionType
    status: PredictionStatus
    created_at: datetime
    forecast_deadline: date | None
    tags: tuple[str, ...]
    latest_revision_at: datetime | None = None
    probability_percent: int | None = None
    numeric_lower_bound: FixedPrecisionValue | None = None
    numeric_median_estimate: FixedPrecisionValue | None = None
    numeric_upper_bound: FixedPrecisionValue | None = None
    numeric_confidence_percent: int | None = None
    numeric_unit: str | None = None
    binary_outcome: BinaryOutcome | None = None
    numeric_actual_value: FixedPrecisionValue | None = None


@dataclass(frozen=True, slots=True)
class SearchFragmentCandidate:
    """One indexed fragment plus the clauses that retrieved it."""

    row_id: int
    document: SearchDocument
    matched_clause_indexes: frozenset[int]
    relevance: float
    literal_match: bool = False
    exact_text_match: bool = False


@dataclass(frozen=True, slots=True)
class SearchFragmentHit:
    """One explainable canonical source retained after ranking."""

    document: SearchDocument
    matched_clause_indexes: frozenset[int]
    literal_match: bool
    exact_text_match: bool


@dataclass(frozen=True, slots=True)
class SearchSnippet:
    """Plain text plus safe half-open ranges that presentation may emphasize."""

    text: str
    match_spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class PredictionSearchHit:
    """One grouped Prediction result with its best matching fragment."""

    prediction: SearchPrediction
    best_match: SearchFragmentHit
    additional_match_count: int


@dataclass(frozen=True, slots=True)
class PredictionSearchResults:
    """Read-only grouped results and transparent fallback guidance."""

    query: SearchQuery
    parsed_text: ParsedSearchText
    hits: tuple[PredictionSearchHit, ...]
    any_word_available: bool = False
    suggestion: str | None = None
    available_tags: tuple[str, ...] = ()


def parse_search_text(text: str) -> ParsedSearchText:
    """Parse ordinary text into safe words and fragment-local quoted phrases."""

    stripped = text.strip()
    if not stripped:
        return ParsedSearchText(raw_text=text, literal_text="", clauses=())

    segments: list[tuple[bool, str]] = []
    buffer: list[str] = []
    quoted = False
    for character in stripped:
        if character == '"':
            if buffer:
                segments.append((quoted, "".join(buffer)))
                buffer.clear()
            quoted = not quoted
        else:
            buffer.append(character)
    if buffer:
        # An unmatched final quote is treated as ordinary text rather than as a
        # surprising phrase operator.
        segments.append((False, "".join(buffer)))

    clauses: list[SearchClause] = []
    clause_segment_indexes: list[int] = []
    for segment_index, (is_quoted, segment) in enumerate(segments):
        tokens = search_tokens(segment)
        if is_quoted:
            if tokens:
                clauses.append(SearchClause(tokens=tokens, is_phrase=True))
                clause_segment_indexes.append(segment_index)
        else:
            for token in tokens:
                clauses.append(SearchClause(tokens=(token,)))
                clause_segment_indexes.append(segment_index)

    ends_in_unquoted_token = (
        bool(stripped)
        and stripped[-1] != '"'
        and _is_token_character(stripped[-1])
        and not quoted
    )
    if ends_in_unquoted_token:
        for index in range(len(clauses) - 1, -1, -1):
            clause = clauses[index]
            segment_is_quoted = segments[clause_segment_indexes[index]][0]
            if not segment_is_quoted and len(clause.tokens[0]) >= 2:
                clauses[index] = replace(clause, is_prefix=True)
                break

    literal_source = stripped
    if (
        len(segments) == 1
        and segments[0][0]
        and stripped.startswith('"')
        and stripped.endswith('"')
    ):
        literal_source = segments[0][1]

    return ParsedSearchText(
        raw_text=text,
        literal_text=normalize_search_literal(literal_source),
        clauses=tuple(clauses),
    )


def search_tokens(text: str) -> tuple[str, ...]:
    """Approximate unicode61 words for safe FTS queries and suggestions."""

    normalized = unicodedata.normalize("NFKD", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if category.startswith("M"):
            continue
        if _is_token_character(character):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def normalize_search_literal(text: str) -> str:
    """Normalize case, common Latin diacritics, and whitespace for literals."""

    normalized = unicodedata.normalize("NFKD", text).casefold()
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("M")
    )
    return " ".join(without_marks.split())


def build_search_snippet(
    text: str,
    parsed_text: ParsedSearchText,
    *,
    maximum_length: int = 180,
) -> SearchSnippet:
    """Select compact plain context and source-indexed ranges without markup."""

    if maximum_length < 40:
        raise ValueError("A search snippet must allow at least 40 characters.")
    spans = _matching_source_spans(text, parsed_text)
    if len(text) <= maximum_length:
        return SearchSnippet(text=text, match_spans=spans)

    first_match = spans[0][0] if spans else 0
    slice_start = max(0, first_match - maximum_length // 3)
    slice_end = min(len(text), slice_start + maximum_length)
    if slice_end - slice_start < maximum_length:
        slice_start = max(0, slice_end - maximum_length)

    if slice_start:
        next_space = text.find(" ", slice_start, min(slice_end, slice_start + 24))
        if next_space != -1 and next_space < first_match:
            slice_start = next_space + 1
    if slice_end < len(text):
        previous_space = text.rfind(" ", max(slice_start, slice_end - 24), slice_end)
        if previous_space > first_match:
            slice_end = previous_space

    prefix = "…" if slice_start else ""
    suffix = "…" if slice_end < len(text) else ""
    clipped_spans = tuple(
        (
            max(start, slice_start) - slice_start + len(prefix),
            min(end, slice_end) - slice_start + len(prefix),
        )
        for start, end in spans
        if end > slice_start and start < slice_end
    )
    return SearchSnippet(
        text=f"{prefix}{text[slice_start:slice_end]}{suffix}",
        match_spans=clipped_spans,
    )


def search_source_label(document: SearchDocument) -> str:
    """Return an inspectable user-facing classification without a raw score."""

    if document.source_kind is SearchSourceKind.QUESTION:
        label = "Question match"
    elif document.source_kind is SearchSourceKind.TAG:
        label = "Tag match"
    elif document.source_kind is SearchSourceKind.BACKGROUND:
        label = "Background match"
    elif document.source_kind is SearchSourceKind.RESOLUTION_CRITERIA:
        label = "Resolution Criteria match"
    elif document.source_kind is SearchSourceKind.FORECAST_RATIONALE:
        sequence = document.source_sequence
        label = (
            "Forecast rationale match"
            if sequence is None
            else f"Forecast revision {sequence} rationale"
        )
    elif document.source_kind is SearchSourceKind.FORECAST_REVIEW:
        label = "Forecast Review note"
    elif document.source_kind is SearchSourceKind.JOURNAL:
        label = "Journal entry match"
    elif document.source_kind is SearchSourceKind.RESOLUTION_NOTES:
        label = "Resolution notes match"
    elif document.source_kind is SearchSourceKind.POSTMORTEM:
        label = "Postmortem match"
    elif document.source_kind is SearchSourceKind.INVALIDATION_REASON:
        label = "Invalidation reason match"
    else:
        label = "Outcome-correction explanation"
    return f"{label} — superseded history" if document.is_superseded else label


def rank_search_candidates(
    parsed_text: ParsedSearchText,
    match_mode: SearchMatchMode,
    predictions: Mapping[int, SearchPrediction],
    candidates: Sequence[SearchFragmentCandidate],
) -> tuple[PredictionSearchHit, ...]:
    """Group fragment candidates and rank Predictions deterministically."""

    if parsed_text.is_blank:
        return ()

    by_prediction: dict[int, list[SearchFragmentCandidate]] = {}
    for candidate in candidates:
        if candidate.document.prediction_id in predictions:
            by_prediction.setdefault(candidate.document.prediction_id, []).append(
                candidate
            )

    required = frozenset(range(len(parsed_text.clauses)))
    ranked: list[tuple[tuple[object, ...], PredictionSearchHit]] = []
    for prediction_id, fragments in by_prediction.items():
        coverage = frozenset().union(
            *(fragment.matched_clause_indexes for fragment in fragments)
        )
        literal_only_match = any(fragment.literal_match for fragment in fragments)
        eligible = (
            literal_only_match
            if not parsed_text.clauses
            else (
                bool(coverage)
                if match_mode is SearchMatchMode.ANY
                else required.issubset(coverage)
            )
        )
        if not eligible:
            continue

        ordered_fragments = sorted(fragments, key=_fragment_rank_key)
        best = ordered_fragments[0]
        prediction = predictions[prediction_id]
        hit = PredictionSearchHit(
            prediction=prediction,
            best_match=SearchFragmentHit(
                document=best.document,
                matched_clause_indexes=best.matched_clause_indexes,
                literal_match=best.literal_match,
                exact_text_match=best.exact_text_match,
            ),
            additional_match_count=len(ordered_fragments) - 1,
        )
        current_question_fragments = tuple(
            fragment
            for fragment in fragments
            if fragment.document.source_kind is SearchSourceKind.QUESTION
            and not fragment.document.is_superseded
        )
        exact_question = any(
            fragment.exact_text_match for fragment in current_question_fragments
        )
        literal_question = any(
            fragment.literal_match for fragment in current_question_fragments
        )
        ranked.append(
            (
                (
                    0 if exact_question else 1,
                    0 if literal_question else 1,
                    _source_priority(best.document),
                    -len(coverage),
                    _fragment_rank_key(best),
                    prediction.prediction_id,
                ),
                hit,
            )
        )

    return tuple(hit for _, hit in sorted(ranked, key=lambda item: item[0]))


def _fragment_rank_key(candidate: SearchFragmentCandidate) -> tuple[object, ...]:
    document = candidate.document
    return (
        _source_priority(document),
        0 if candidate.exact_text_match else 1,
        0 if candidate.literal_match else 1,
        -len(candidate.matched_clause_indexes),
        candidate.relevance,
        document.source_sequence if document.source_sequence is not None else 0,
        document.source_record_id,
        document.source_version_id if document.source_version_id is not None else 0,
        candidate.row_id,
    )


def _source_priority(document: SearchDocument) -> int:
    priorities = {
        SearchSourceKind.QUESTION: 0,
        SearchSourceKind.TAG: 1,
        SearchSourceKind.BACKGROUND: 2,
        SearchSourceKind.RESOLUTION_CRITERIA: 2,
        SearchSourceKind.FORECAST_RATIONALE: 3,
        SearchSourceKind.FORECAST_REVIEW: 3,
        SearchSourceKind.JOURNAL: 3,
        SearchSourceKind.RESOLUTION_NOTES: 4,
        SearchSourceKind.POSTMORTEM: 4,
        SearchSourceKind.INVALIDATION_REASON: 4,
        SearchSourceKind.OUTCOME_CORRECTION_REASON: 4,
    }
    return priorities[document.source_kind] + (10 if document.is_superseded else 0)


def _is_token_character(character: str) -> bool:
    category = unicodedata.category(character)
    return category[0] in {"L", "N"} or category == "Co"


def _matching_source_spans(
    text: str,
    parsed_text: ParsedSearchText,
) -> tuple[tuple[int, int], ...]:
    token_spans: list[tuple[str, int, int]] = []
    token_start: int | None = None
    for index, character in enumerate((*text, " ")):
        if index < len(text) and _is_token_character(character):
            if token_start is None:
                token_start = index
        elif token_start is not None:
            normalized_tokens = search_tokens(text[token_start:index])
            if normalized_tokens:
                token_spans.append((normalized_tokens[0], token_start, index))
            token_start = None

    spans: list[tuple[int, int]] = []
    for clause in parsed_text.clauses:
        for query_token in clause.tokens:
            for source_token, start, end in token_spans:
                if source_token == query_token or (
                    clause.is_prefix and source_token.startswith(query_token)
                ):
                    spans.append((start, end))

    literal = parsed_text.literal_text
    if literal and " " not in literal:
        normalized_text, source_indexes = _normalized_text_with_source_indexes(text)
        search_at = 0
        while True:
            match_at = normalized_text.find(literal, search_at)
            if match_at < 0:
                break
            match_end = match_at + len(literal)
            spans.append(
                (
                    source_indexes[match_at],
                    source_indexes[match_end - 1] + 1,
                )
            )
            search_at = match_end

    merged: list[tuple[int, int]] = []
    for start, end in sorted(set(spans)):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _normalized_text_with_source_indexes(text: str) -> tuple[str, tuple[int, ...]]:
    characters: list[str] = []
    indexes: list[int] = []
    for source_index, source_character in enumerate(text):
        normalized = unicodedata.normalize("NFKD", source_character).casefold()
        for character in normalized:
            if unicodedata.category(character).startswith("M"):
                continue
            characters.append(character)
            indexes.append(source_index)
    return "".join(characters), tuple(indexes)
