"""Privacy-safe regression corpus for user-visible search relevance."""

from __future__ import annotations

from dataclasses import dataclass

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import PredictionType


@dataclass(frozen=True, slots=True)
class RelevanceScenario:
    """One named remembered-text scenario with a top-three expectation."""

    name: str
    query: str
    expected_prediction_id: int


def _ids(results) -> tuple[int, ...]:
    return tuple(hit.prediction.prediction_id for hit in results.hits)


def test_full_privacy_safe_relevance_corpus(tmp_path) -> None:
    database = Database.open(tmp_path / "relevance.sqlite3")
    operations = PredictionOperations(database)

    exact = operations.create_prediction(
        "Will the Orion permit arrive by Friday?",
        65,
        rationale="The clerk confirmed the ordinary processing window.",
        tags=("Spaceflight", "Work"),
    )
    operations.create_prediction(
        "Will the routine permit review finish?",
        55,
        background="The Orion filing might arrive by Friday after review.",
    )
    split = operations.create_prediction(
        "Will the Vega launch happen?",
        60,
    )
    operations.add_journal_entry(
        split.prediction_id,
        "The permit was cleared by the range office.",
        expected_revision_id=split.current_revision_id,
        expected_metadata_version=split.metadata_version,
    )
    phrase = operations.create_prediction(
        "Will the lunar launch permit be approved?",
        50,
    )
    phrase_split = operations.create_prediction(
        "Will the lunar mission launch on schedule?",
        50,
    )
    operations.add_journal_entry(
        phrase_split.prediction_id,
        "The permit was approved separately.",
        expected_revision_id=phrase_split.current_revision_id,
        expected_metadata_version=phrase_split.metadata_version,
    )
    unicode_prediction = operations.create_prediction(
        "Will the café résumé arrive tomorrow?",
        70,
    )
    punctuation = operations.create_prediction(
        "Will O'Brien's 50%-funded follow-up succeed?",
        45,
    )
    duplicated = operations.create_prediction(
        "Will duplicated memory remain searchable?",
        40,
        background="Duplicated memory appears in more than one fragment.",
    )
    numeric = operations.create_numeric_prediction(
        "How many aurora samples will arrive?",
        "samples",
        0,
        2,
        5,
        9,
        80,
        rationale="A spectrometer estimate supplies the interval.",
    )
    corrected = operations.create_prediction(
        "Will the corrected field report remain useful?",
        50,
    )
    journal = operations.add_journal_entry(
        corrected.prediction_id,
        "Amber wording is obsolete.",
        expected_revision_id=corrected.current_revision_id,
        expected_metadata_version=corrected.metadata_version,
    )
    operations.correct_journal_entry(
        corrected.prediction_id,
        journal.entry_id,
        "Cerulean evidence is effective.",
        expected_correction_id=None,
    )

    scenarios = (
        RelevanceScenario(
            "exact current Question",
            '"will the orion permit arrive by friday"',
            exact.prediction_id,
        ),
        RelevanceScenario(
            "reordered Question words",
            "Friday Orion permit",
            exact.prediction_id,
        ),
        RelevanceScenario(
            "words split across Prediction fragments",
            "Vega permit",
            split.prediction_id,
        ),
        RelevanceScenario(
            "quoted phrase within one fragment",
            '"launch permit"',
            phrase.prediction_id,
        ),
        RelevanceScenario(
            "partial final word",
            "auro",
            numeric.prediction_id,
        ),
        RelevanceScenario(
            "case and Latin diacritics",
            "CAFE RESUME",
            unicode_prediction.prediction_id,
        ),
        RelevanceScenario(
            "apostrophe hyphen and percentage punctuation",
            "O'Brien 50% follow-up",
            punctuation.prediction_id,
        ),
        RelevanceScenario(
            "overlapping common terms favor stronger Question",
            "Orion permit",
            exact.prediction_id,
        ),
        RelevanceScenario(
            "identical text in multiple fragments groups once",
            "duplicated memory",
            duplicated.prediction_id,
        ),
        RelevanceScenario(
            "effective corrected Journal text",
            "cerulean evidence",
            corrected.prediction_id,
        ),
        RelevanceScenario(
            "exact Numeric Question",
            '"how many aurora samples will arrive"',
            numeric.prediction_id,
        ),
    )

    for scenario in scenarios:
        result_ids = _ids(operations.search_predictions(scenario.query))
        assert scenario.expected_prediction_id in result_ids[:3], scenario.name

    exact_results = operations.search_predictions(
        '"will the orion permit arrive by friday"'
    )
    assert _ids(exact_results)[0] == exact.prediction_id
    assert _ids(operations.search_predictions('"launch permit"')) == (
        phrase.prediction_id,
    )
    assert phrase_split.prediction_id not in _ids(
        operations.search_predictions('"launch permit"')
    )
    duplicate_results = operations.search_predictions("duplicated memory")
    assert _ids(duplicate_results) == (duplicated.prediction_id,)
    assert duplicate_results.hits[0].additional_match_count == 1

    assert operations.search_predictions("amber wording").hits == ()
    historical = operations.search_predictions(
        "amber wording",
        include_superseded=True,
    )
    assert _ids(historical) == (corrected.prediction_id,)
    assert historical.hits[0].best_match.document.is_superseded

    typo = operations.search_predictions("oroin")
    assert typo.hits == ()
    assert typo.suggestion == "orion"
    assert operations.search_predictions("orion").hits

    numeric_result = operations.search_predictions("aurora").hits[0].prediction
    assert numeric_result.prediction_type is PredictionType.NUMERIC
    assert numeric_result.numeric_unit == "samples"
    database.check_search_index()
    database.close()
