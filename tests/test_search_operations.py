from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.application.errors import SearchUnavailableError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.search_index import SearchIndexRepairRequiredError
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.domain.search import SearchMatchMode, SearchSourceKind

NOW = datetime(2026, 8, 27, 18, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = NOW

    def now(self) -> datetime:
        return self.instant


def _operations(database: Database) -> PredictionOperations:
    return PredictionOperations(database, FixedClock(), UTC)


def _matching_ids(results) -> list[int]:
    return [hit.prediction.prediction_id for hit in results.hits]


def test_binary_search_projects_every_source_and_hides_superseded_text_by_default(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    created = operations.create_prediction(
        "Will the café orbital launch succeed?",
        60,
        rationale="Astronaut testimony supports the forecast.",
        background="The zephyr dossier contains the background evidence.",
        resolution_criteria="Use the originalcriterion launch certificate.",
        tags=("Spaceflight",),
    )
    revised = operations.revise_forecast(
        created.prediction_id,
        70,
        rationale="Telemetry shows the booster is healthy.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.add_forecast_review(
        created.prediction_id,
        note="Reviewnote deliberately retains this probability.",
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    journal = operations.add_journal_entry(
        created.prediction_id,
        "Oldjournal reported a preliminary weather window.",
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    corrected_journal = operations.correct_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "Currentjournal reports a confirmed weather window.",
        expected_correction_id=None,
    )
    updated = operations.update_metadata(
        created.prediction_id,
        question="Will the café orbital mission succeed?",
        background=created.background,
        resolution_criteria="Use the currentcriterion mission certificate.",
        forecast_deadline=created.forecast_deadline,
        expected_resolution=created.expected_resolution,
        tags=created.tags,
        expected_metadata_version=created.metadata_version,
        confirm_meaning_change=True,
    )
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Originalnotes came from the first bulletin.",
        postmortem="Originalpostmortem focused on launch weather.",
        expected_revision_id=updated.current_revision_id,
        expected_metadata_version=updated.metadata_version,
    )
    correction = operations.correct_binary_resolution(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Currentnotes use the certified bulletin.",
        postmortem="Currentpostmortem emphasizes source verification.",
        correction_reason="Certificationreason explains the corrected outcome.",
        expected_correction_id=None,
    )
    assert corrected_journal.current_correction_id is not None
    assert correction.current_correction_id is not None
    assert resolved.resolution is not None

    expected_current_sources = {
        "mission": SearchSourceKind.QUESTION,
        "spaceflight": SearchSourceKind.TAG,
        "zephyr": SearchSourceKind.BACKGROUND,
        "currentcriterion": SearchSourceKind.RESOLUTION_CRITERIA,
        "astronaut": SearchSourceKind.FORECAST_RATIONALE,
        "telemetry": SearchSourceKind.FORECAST_RATIONALE,
        "reviewnote": SearchSourceKind.FORECAST_REVIEW,
        "currentjournal": SearchSourceKind.JOURNAL,
        "currentnotes": SearchSourceKind.RESOLUTION_NOTES,
        "currentpostmortem": SearchSourceKind.POSTMORTEM,
        "certificationreason": SearchSourceKind.OUTCOME_CORRECTION_REASON,
    }
    for query, source_kind in expected_current_sources.items():
        results = operations.search_predictions(query)
        assert _matching_ids(results) == [created.prediction_id]
        assert results.hits[0].best_match.document.source_kind is source_kind
        assert not results.hits[0].best_match.document.is_superseded

    for historical_query in (
        "launch",
        "originalcriterion",
        "oldjournal",
        "originalnotes",
        "originalpostmortem",
    ):
        assert operations.search_predictions(historical_query).hits == ()
        historical = operations.search_predictions(
            historical_query, include_superseded=True
        )
        assert _matching_ids(historical) == [created.prediction_id]
        assert historical.hits[0].best_match.document.is_superseded

    database.check_search_index()
    database.close()


def test_numeric_sources_and_actual_value_correction_reason_are_searchable(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    created = operations.create_numeric_prediction(
        "How many comet observations will be logged?",
        "observations",
        0,
        1,
        4,
        9,
        80,
        rationale="Initialcomet estimate uses last season.",
    )
    revised = operations.revise_numeric_forecast(
        created.prediction_id,
        2,
        5,
        10,
        75,
        rationale="Revisednebula estimate uses current conditions.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.add_numeric_forecast_review(
        created.prediction_id,
        note="Numericreview retains the interval.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    operations.add_numeric_journal_entry(
        created.prediction_id,
        "Numericjournal records the observing schedule.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    resolved = operations.resolve_numeric_prediction(
        created.prediction_id,
        6,
        resolution_notes="Numericnotes use the preliminary count.",
        postmortem="Numericpostmortem discusses interval width.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    operations.correct_numeric_resolution(
        created.prediction_id,
        7,
        resolution_notes="Finalnumericnotes use the audited count.",
        postmortem="Finalnumericpostmortem discusses the missed signal.",
        correction_reason="Recalibrationreason documents the instrument change.",
        expected_correction_id=None,
    )
    assert resolved.resolution is not None

    for query in (
        "initialcomet",
        "revisednebula",
        "numericreview",
        "numericjournal",
        "finalnumericnotes",
        "finalnumericpostmortem",
        "recalibrationreason",
    ):
        assert _matching_ids(operations.search_predictions(query)) == [
            created.prediction_id
        ]
    assert operations.search_predictions("numericnotes").hits == ()
    assert _matching_ids(
        operations.search_predictions("numericnotes", include_superseded=True)
    ) == [created.prediction_id]

    database.check_search_index()
    database.close()


def test_invalidation_reason_corrections_obey_history_scope(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    created = operations.create_prediction("Will this source remain valid?", 50)
    operations.invalidate_prediction(
        created.prediction_id,
        reason="Originalinvalidreason was ambiguous.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.correct_invalidation_reason(
        created.prediction_id,
        "Currentinvalidreason cites the withdrawn source.",
        expected_correction_id=None,
    )

    current = operations.search_predictions("currentinvalidreason")
    assert _matching_ids(current) == [created.prediction_id]
    assert (
        current.hits[0].best_match.document.source_kind
        is SearchSourceKind.INVALIDATION_REASON
    )
    assert operations.search_predictions("originalinvalidreason").hits == ()
    assert _matching_ids(
        operations.search_predictions("originalinvalidreason", include_superseded=True)
    ) == [created.prediction_id]
    database.close()


def test_words_phrases_prefixes_literals_all_any_and_suggestions(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    split = operations.create_prediction(
        "Will the café permit arrive---before the mission?",
        55,
    )
    operations.add_journal_entry(
        split.prediction_id,
        "Approved yesterday by the astronautical office.",
        expected_revision_id=split.current_revision_id,
        expected_metadata_version=split.metadata_version,
    )
    phrase = operations.create_prediction(
        "Will the permit approved jointly remain effective?",
        65,
    )

    assert _matching_ids(operations.search_predictions("CAFÉ")) == [split.prediction_id]
    assert _matching_ids(operations.search_predictions("issio")) == [
        split.prediction_id
    ]
    assert _matching_ids(operations.search_predictions("---")) == [split.prediction_id]
    assert _matching_ids(operations.search_predictions("astron")) == [
        split.prediction_id
    ]
    for ordinary_query in ("50%", "O'Brien", "mission OR *", 'mission "'):
        operations.search_predictions(ordinary_query)
    assert _matching_ids(operations.search_predictions('"permit approved"')) == [
        phrase.prediction_id
    ]

    all_results = operations.search_predictions("mission nonexistentword")
    assert all_results.hits == ()
    assert all_results.any_word_available is True
    any_results = operations.search_predictions(
        "mission nonexistentword", match_mode=SearchMatchMode.ANY
    )
    assert _matching_ids(any_results) == [split.prediction_id]

    suggestion = operations.search_predictions("missoin")
    assert suggestion.hits == ()
    assert suggestion.suggestion == "mission"
    database.close()


def test_exact_current_question_ranks_first_and_results_group_by_prediction(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    exact = operations.create_prediction("Will launch happen", 50)
    repeated = operations.create_prediction(
        "A different proposition",
        50,
        background="Will launch happen according to the background?",
    )
    operations.add_journal_entry(
        repeated.prediction_id,
        "Will launch happen according to the journal?",
        expected_revision_id=repeated.current_revision_id,
        expected_metadata_version=repeated.metadata_version,
    )

    results = operations.search_predictions('"will launch happen"')

    assert _matching_ids(results) == [exact.prediction_id, repeated.prediction_id]
    assert results.hits[0].best_match.exact_text_match is True
    assert results.hits[1].additional_match_count == 1
    database.close()


def test_index_updates_survive_restart_and_sequential_independent_connections(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = Database.open(path)
    second = Database.open(path)
    created = _operations(first).create_prediction(
        "Will independent search connections agree?", 50
    )

    assert _matching_ids(_operations(second).search_predictions("independent")) == [
        created.prediction_id
    ]
    second.close()
    first.close()

    reopened = Database.open(path)
    assert _matching_ids(_operations(reopened).search_predictions("independent")) == [
        created.prediction_id
    ]
    reopened.close()


def test_independent_write_lock_produces_a_bounded_retryable_search_error(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = Database.open(path)
    second = Database.open(path)
    _operations(first).create_prediction("Will the busy search retry?", 50)
    with second.transaction() as connection:
        connection.execute("PRAGMA busy_timeout = 1")

    with first.transaction() as connection:
        connection.execute("SELECT 1")
        with pytest.raises(SearchUnavailableError, match="busy"):
            _operations(second).search_predictions("retry")

    first.close()
    second.close()


def test_deleting_an_untouched_prediction_removes_its_search_documents(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    created = operations.create_prediction("Disposable searchable forecast", 50)
    assert _matching_ids(operations.search_predictions("disposable")) == [
        created.prediction_id
    ]

    operations.delete_prediction(
        created.prediction_id,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
        confirm_permanent_deletion=True,
    )

    assert operations.search_predictions("disposable").hits == ()
    database.check_search_index()
    database.close()


def test_index_refresh_failure_rolls_back_the_canonical_write(
    tmp_path, monkeypatch
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)

    def fail_refresh(_connection) -> None:
        raise SearchIndexRepairRequiredError("forced search projection failure")

    with monkeypatch.context() as context:
        context.setattr(
            "reckonsolve.data.database.refresh_pending_search_documents",
            fail_refresh,
        )
        with pytest.raises(SearchIndexRepairRequiredError):
            operations.create_prediction("This write must roll back", 50)

    assert operations.browse_predictions().predictions == ()
    database.check_search_index()
    database.close()


def test_corrupt_projection_reports_repair_and_rebuild_restores_search(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)
    created = operations.create_prediction("Will repair restore the index?", 50)
    with database.transaction() as connection:
        connection.execute("DELETE FROM prediction_search")

    with pytest.raises(SearchIndexRepairRequiredError):
        database.check_search_index()
    with pytest.raises(SearchUnavailableError):
        operations.search_predictions("repair")

    operations.repair_search_index()
    assert _matching_ids(operations.search_predictions("repair")) == [
        created.prediction_id
    ]
    database.check_search_index()
    database.close()


def test_missing_search_documents_are_rebuilt_from_canonical_data_on_restart(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    created = _operations(database).create_prediction(
        "Will startup rebuild missing search documents?", 50
    )
    with database.transaction() as connection:
        connection.execute("DELETE FROM prediction_search")
    database.close()

    reopened = Database.open(path)
    assert _matching_ids(_operations(reopened).search_predictions("startup")) == [
        created.prediction_id
    ]
    reopened.check_search_index()
    reopened.close()


def test_stale_projection_state_is_rebuilt_on_restart_and_databases_are_isolated(
    tmp_path,
) -> None:
    stable_path = tmp_path / "stable.sqlite3"
    development_path = tmp_path / "development.sqlite3"
    stable = Database.open(stable_path)
    development = Database.open(development_path)
    stable_created = _operations(stable).create_prediction(
        "Stable-only searchable forecast", 50
    )
    _operations(development).create_prediction(
        "Development-only searchable forecast", 50
    )
    with stable.transaction() as connection:
        connection.execute(
            "UPDATE search_index_state SET projection_version = 0 WHERE singleton_id = 1"
        )
    stable.close()

    reopened = Database.open(stable_path)
    assert _matching_ids(_operations(reopened).search_predictions("stable")) == [
        stable_created.prediction_id
    ]
    assert _operations(reopened).search_predictions("development").hits == ()
    assert _operations(development).search_predictions("stable").hits == ()
    reopened.check_search_index()
    reopened.close()
    development.close()


def test_blank_search_is_empty_and_invalid_mode_is_presentable(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = _operations(database)

    assert operations.search_predictions(" \n ").hits == ()
    with pytest.raises(Exception) as captured:
        operations.search_predictions("text", match_mode="all")  # type: ignore[arg-type]
    assert captured.value.__class__.__name__ == "ValidationError"

    with database.transaction() as connection:
        connection.execute(
            "UPDATE search_index_state SET projection_version = 0 WHERE singleton_id = 1"
        )
    with pytest.raises(SearchUnavailableError):
        operations.search_predictions("text")
    database.close()
