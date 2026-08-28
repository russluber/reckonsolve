from datetime import UTC, datetime

from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.search import (
    SearchDocument,
    SearchFragmentCandidate,
    SearchMatchMode,
    SearchPrediction,
    SearchSourceKind,
    build_search_snippet,
    normalize_search_literal,
    parse_search_text,
    rank_search_candidates,
    search_source_label,
    search_tokens,
)

NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)


def _prediction(prediction_id: int, question: str) -> SearchPrediction:
    return SearchPrediction(
        prediction_id=prediction_id,
        question=question,
        prediction_type=PredictionType.BINARY,
        status=PredictionStatus.OPEN,
        created_at=NOW,
        forecast_deadline=None,
        tags=(),
    )


def _candidate(
    row_id: int,
    prediction_id: int,
    text: str,
    source_kind: SearchSourceKind,
    *clause_indexes: int,
    superseded: bool = False,
    literal: bool = False,
    exact: bool = False,
    relevance: float = -1.0,
) -> SearchFragmentCandidate:
    return SearchFragmentCandidate(
        row_id=row_id,
        document=SearchDocument(
            prediction_id=prediction_id,
            source_kind=source_kind,
            source_record_id=row_id,
            source_version_id=None,
            source_sequence=None,
            occurred_at=NOW,
            is_superseded=superseded,
            text=text,
        ),
        matched_clause_indexes=frozenset(clause_indexes),
        relevance=relevance,
        literal_match=literal,
        exact_text_match=exact,
    )


def test_parser_accepts_words_phrases_prefixes_and_unicode() -> None:
    parsed = parse_search_text('  Café launch "third quarter" mil  ')

    assert [
        (clause.tokens, clause.is_phrase, clause.is_prefix) for clause in parsed.clauses
    ] == [
        (("cafe",), False, False),
        (("launch",), False, False),
        (("third", "quarter"), True, False),
        (("mil",), False, True),
    ]
    assert search_tokens("naïve—résumé 2026") == ("naive", "resume", "2026")
    assert normalize_search_literal("  CAFÉ\n launch ") == "cafe launch"


def test_parser_treats_unmatched_quote_as_ordinary_text() -> None:
    parsed = parse_search_text('launch "third quarter')

    assert [clause.tokens for clause in parsed.clauses] == [
        ("launch",),
        ("third",),
        ("quarter",),
    ]


def test_ranking_groups_fragments_and_requires_prediction_level_coverage() -> None:
    parsed = parse_search_text("launch permit")
    predictions = {
        1: _prediction(1, "Will launch happen?"),
        2: _prediction(2, "Will the permit arrive?"),
    }
    candidates = (
        _candidate(1, 1, "Will launch happen?", SearchSourceKind.QUESTION, 0),
        _candidate(2, 1, "The permit was filed", SearchSourceKind.JOURNAL, 1),
        _candidate(3, 2, "Will the permit arrive?", SearchSourceKind.QUESTION, 1),
    )

    all_hits = rank_search_candidates(
        parsed, SearchMatchMode.ALL, predictions, candidates
    )
    any_hits = rank_search_candidates(
        parsed, SearchMatchMode.ANY, predictions, candidates
    )

    assert [hit.prediction.prediction_id for hit in all_hits] == [1]
    assert all_hits[0].additional_match_count == 1
    assert [hit.prediction.prediction_id for hit in any_hits] == [1, 2]


def test_exact_current_question_outranks_other_sources_and_history() -> None:
    parsed = parse_search_text('"will launch happen"')
    predictions = {
        1: _prediction(1, "Will launch happen"),
        2: _prediction(2, "Different current question"),
        3: _prediction(3, "Another current question"),
    }
    candidates = (
        _candidate(
            1,
            1,
            "Will launch happen",
            SearchSourceKind.QUESTION,
            0,
            literal=True,
            exact=True,
        ),
        _candidate(
            2,
            2,
            "Will launch happen after the permit?",
            SearchSourceKind.JOURNAL,
            0,
            literal=True,
        ),
        _candidate(
            3,
            3,
            "Will launch happen",
            SearchSourceKind.QUESTION,
            0,
            superseded=True,
            literal=True,
            exact=True,
        ),
    )

    hits = rank_search_candidates(parsed, SearchMatchMode.ALL, predictions, candidates)

    assert [hit.prediction.prediction_id for hit in hits] == [1, 2, 3]
    assert hits[0].best_match.document.source_kind is SearchSourceKind.QUESTION
    assert not hits[0].best_match.document.is_superseded


def test_snippet_preserves_plain_source_text_and_marks_unicode_matches() -> None:
    source = (
        "Unrelated opening context that should be clipped before the remembered "
        "Café <evidence> changed the forecast substantially and safely."
    )

    snippet = build_search_snippet(
        source,
        parse_search_text("cafe evidence"),
        maximum_length=80,
    )

    assert snippet.text.startswith("…")
    assert "Café <evidence>" in snippet.text
    assert "<evidence>" in snippet.text
    emphasized = tuple(snippet.text[start:end] for start, end in snippet.match_spans)
    assert emphasized == ("Café", "evidence")


def test_source_labels_make_superseded_history_unmistakable() -> None:
    document = SearchDocument(
        prediction_id=1,
        source_kind=SearchSourceKind.JOURNAL,
        source_record_id=3,
        source_version_id=None,
        source_sequence=None,
        occurred_at=NOW,
        is_superseded=True,
        text="Earlier wording",
    )

    assert search_source_label(document) == ("Journal entry match — superseded history")
