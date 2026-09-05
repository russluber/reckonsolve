from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from io import StringIO
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QListWidget

import reckonsolve.cli
from reckonsolve import main_cli, main_cli_dev
from reckonsolve.app import create_runtime as create_gui_runtime
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import create_runtime, run
from reckonsolve.data.database import Database
from reckonsolve.data.settings import SettingsRepository
from reckonsolve.data.transfer import EXPORT_ARCHIVE_NAMES
from reckonsolve.domain.browser import ArchiveQuery, ArchiveSort, ArchiveTagMatchMode
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 25, 17, 45, 12, 345678, tzinfo=UTC)


def test_cli_package_entry_points_delegate_to_stable_and_development_runners(
    monkeypatch,
) -> None:
    calls = []

    def fake_run(*, identity=STABLE_APPLICATION) -> int:
        calls.append(identity)
        return 31

    monkeypatch.setattr(reckonsolve.cli, "run", fake_run)

    with pytest.raises(SystemExit) as stable_exit:
        main_cli()
    with pytest.raises(SystemExit) as development_exit:
        main_cli_dev()

    assert stable_exit.value.code == 31
    assert development_exit.value.code == 31
    assert calls == [STABLE_APPLICATION, DEVELOPMENT_APPLICATION]


def test_cli_runtime_selects_paired_stable_and_development_paths(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "reckonsolve.paths.QStandardPaths.writableLocation",
        lambda _location: str(tmp_path / QCoreApplication.applicationName()),
    )

    stable = create_runtime(identity=STABLE_APPLICATION)
    assert stable.database.path == tmp_path / "Reckonsolve" / "reckonsolve.sqlite3"
    assert stable.database.schema_version == 15
    stable.close()

    development = create_runtime(identity=DEVELOPMENT_APPLICATION)
    assert development.database.path == (
        tmp_path / "Reckonsolve Dev" / "reckonsolve.sqlite3"
    )
    assert development.database.schema_version == 15
    development.close()

    assert stable.database.path != development.database.path


def test_cli_version_and_help_do_not_open_a_database(tmp_path, capsys) -> None:
    database_path = tmp_path / "must-not-exist.sqlite3"

    with pytest.raises(SystemExit) as version_exit:
        run(["--version"], database_path=database_path)
    version_output = capsys.readouterr()

    assert version_exit.value.code == 0
    assert version_output.out.startswith(f"reckonsolve-cli {version('reckonsolve')}")
    assert not database_path.exists()

    with pytest.raises(SystemExit) as help_exit:
        run(["list", "--help"], database_path=database_path)
    help_output = capsys.readouterr()

    assert help_exit.value.code == 0
    assert "--search TEXT" in help_output.out
    assert "--status" in help_output.out
    assert "--type" in help_output.out
    assert "--tag TAG" in help_output.out
    assert not database_path.exists()

    with pytest.raises(SystemExit) as search_help_exit:
        run(["search", "--help"], database_path=database_path)
    search_help_output = capsys.readouterr()

    assert search_help_exit.value.code == 0
    assert "QUERY" in search_help_output.out
    assert "--include-superseded-history" in search_help_output.out
    assert "--tag-mode" in search_help_output.out
    assert "--date-meaning" in search_help_output.out
    assert not database_path.exists()

    with pytest.raises(SystemExit) as saved_views_help_exit:
        run(["saved-views", "--help"], database_path=database_path)
    saved_views_help_output = capsys.readouterr()

    assert saved_views_help_exit.value.code == 0
    assert "Saved View" in saved_views_help_output.out
    assert not database_path.exists()

    with pytest.raises(SystemExit) as saved_view_help_exit:
        run(["saved-view", "--help"], database_path=database_path)
    saved_view_help_output = capsys.readouterr()

    assert saved_view_help_exit.value.code == 0
    assert "SAVED_VIEW_ID" in saved_view_help_output.out
    assert "--name NAME" in saved_view_help_output.out
    assert not database_path.exists()

    with pytest.raises(SystemExit) as create_help_exit:
        run(["create", "--help"], database_path=database_path)
    create_help_output = capsys.readouterr()

    assert create_help_exit.value.code == 0
    assert "binary" in create_help_output.out
    assert "numeric" in create_help_output.out
    assert not database_path.exists()

    for command in (
        "revise",
        "journal",
        "review",
        "resolve",
        "invalidate",
        "delete",
    ):
        with pytest.raises(SystemExit) as mutation_help_exit:
            run([command, "--help"], database_path=database_path)
        mutation_help_output = capsys.readouterr()

        assert mutation_help_exit.value.code == 0
        assert "PREDICTION_ID" in mutation_help_output.out
        assert not database_path.exists()

    for command in ("backup", "export-csv"):
        with pytest.raises(SystemExit) as transfer_help_exit:
            run([command, "--help"], database_path=database_path)
        transfer_help_output = capsys.readouterr()

        assert transfer_help_exit.value.code == 0
        assert "DESTINATION" in transfer_help_output.out
        assert not database_path.exists()


def test_cli_list_distinguishes_empty_database_from_no_matching_filters(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    empty_output = StringIO()

    assert (
        run(
            ["list", "--status", "resolved"],
            database_path=database_path,
            stdout=empty_output,
        )
        == 0
    )
    assert empty_output.getvalue() == "No predictions yet.\n"

    database = Database.open(database_path)
    PredictionOperations(
        database, FixedClock(NOW), local_timezone=UTC
    ).create_prediction(
        "Will one Open Prediction exist?",
        60,
    )
    database.close()

    filtered_output = StringIO()
    assert (
        run(
            ["list", "--status", "resolved"],
            database_path=database_path,
            stdout=filtered_output,
        )
        == 0
    )
    assert filtered_output.getvalue() == "No predictions match the selected filters.\n"


def test_cli_list_combines_filters_and_formats_type_aware_attention(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    old = NOW - timedelta(days=30)
    operations = PredictionOperations(database, FixedClock(old), local_timezone=UTC)
    operations.create_prediction(
        "Will the unrelated Binary item remain hidden?",
        35,
        tags=("Other",),
    )
    numeric = operations.create_numeric_prediction(
        "How many caf\u00e9 orders will arrive?",
        "orders",
        2,
        "-1.20",
        "2.00",
        "9.50",
        85,
        expected_resolution=date(2026, 8, 1),
        tags=("Caf\u00e9", "Work"),
    )
    database.close()

    output = StringIO()
    result = run(
        [
            "list",
            "--search",
            "CAF\u00c9 ORDERS",
            "--status",
            "open",
            "--type",
            "numeric",
            "--tag",
            "caf\u00e9",
        ],
        database_path=database_path,
        stdout=output,
    )

    assert result == 0
    rendered = output.getvalue()
    assert "Predictions (1)" in rendered
    assert f"#{numeric.prediction_id} | NUMERIC | OPEN" in rendered
    assert "85% interval -1.20 to 9.50 orders; median 2.00 orders" in rendered
    assert "Question: How many caf\u00e9 orders will arrive?" in rendered
    assert "Tags: Caf\u00e9, Work" in rendered
    assert "Attention: Needs Attention, Ready to Resolve" in rendered
    assert "unrelated Binary" not in rendered


def test_cli_search_uses_shared_explainable_query_and_rich_filters(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    target = operations.create_prediction(
        "Will the calibrated report arrive?",
        65,
        background="A tracked research deliverable.",
        expected_resolution=date(2000, 1, 1),
        tags=("Work", "Research"),
    )
    operations.add_journal_entry(
        target.prediction_id,
        "Precise journal evidence arrived from the project lead.",
        expected_revision_id=target.current_revision_id,
        expected_metadata_version=target.metadata_version,
    )
    operations.update_metadata(
        target.prediction_id,
        question="Will the revised report arrive?",
        background=target.background,
        resolution_criteria=target.resolution_criteria,
        forecast_deadline=target.forecast_deadline,
        expected_resolution=target.expected_resolution,
        tags=target.tags,
        expected_metadata_version=target.metadata_version,
        confirm_meaning_change=True,
    )
    operations.create_numeric_prediction(
        "How many unrelated deliveries will arrive?",
        "items",
        0,
        1,
        2,
        3,
        80,
        tags=("Work",),
    )
    operations.create_prediction("Will the mission launch?", 50, tags=("Other",))
    database.close()

    output = StringIO()
    result = run(
        [
            "search",
            '"precise journal evidence"',
            "--status",
            "open",
            "--type",
            "binary",
            "--tag",
            "work",
            "--tag",
            "research",
            "--tag-mode",
            "all",
            "--attention",
            "ready-to-resolve",
            "--date-meaning",
            "created",
            "--from",
            "2026-08-25",
            "--to",
            "2026-08-25",
            "--sort",
            "question-a-to-z",
        ],
        database_path=database_path,
        stdout=output,
    )

    assert result == 0
    rendered = output.getvalue()
    assert "Search results (1)" in rendered
    assert f"#{target.prediction_id} | BINARY | OPEN | 65% Yes" in rendered
    assert "Question: Will the revised report arrive?" in rendered
    assert "Tags: Research, Work" in rendered
    assert "Match: Journal entry match" in rendered
    assert "Snippet: Precise journal evidence arrived" in rendered
    assert "unrelated deliveries" not in rendered

    fallback = StringIO()
    assert (
        run(
            ["search", "revised impossibleword"],
            database_path=database_path,
            stdout=fallback,
        )
        == 0
    )
    assert "Try --any-words" in fallback.getvalue()

    suggested = StringIO()
    assert (
        run(
            ["search", "missoin"],
            database_path=database_path,
            stdout=suggested,
        )
        == 0
    )
    assert "Suggestion: search for 'mission'." in suggested.getvalue()

    any_words = StringIO()
    assert (
        run(
            ["search", "revised impossibleword", "--any-words"],
            database_path=database_path,
            stdout=any_words,
        )
        == 0
    )
    assert "Match mode: Any words" in any_words.getvalue()
    assert f"#{target.prediction_id} | BINARY | OPEN" in any_words.getvalue()

    current_only = StringIO()
    assert (
        run(
            ["search", '"calibrated report"'],
            database_path=database_path,
            stdout=current_only,
        )
        == 0
    )
    assert "No predictions match this search and filters." in current_only.getvalue()

    historical = StringIO()
    assert (
        run(
            [
                "search",
                '"calibrated report"',
                "--include-superseded-history",
            ],
            database_path=database_path,
            stdout=historical,
        )
        == 0
    )
    assert "Include superseded history: Yes" in historical.getvalue()
    assert "Match: Question match — superseded history" in historical.getvalue()


def test_cli_saved_views_list_and_execute_current_dynamic_queries(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    binary = operations.create_prediction(
        "Will saved-view evidence arrive?",
        55,
        tags=("Work", "Evidence"),
    )
    operations.add_journal_entry(
        binary.prediction_id,
        "The project lead says the evidence is now available.",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric = operations.create_numeric_prediction(
        "How many work items will finish?",
        "items",
        0,
        1,
        2,
        3,
        80,
        tags=("Work",),
    )
    evidence_view = operations.create_saved_view(
        "Evidence Search",
        SavedViewConfiguration(
            search_text="project lead",
            match_mode=SearchMatchMode.ALL,
            include_superseded=False,
            archive_query=ArchiveQuery(
                tags=("Work", "Evidence"),
                tag_match_mode=ArchiveTagMatchMode.ALL,
                sort=ArchiveSort.RELEVANCE,
            ),
        ),
    )
    numeric_view = operations.create_saved_view(
        "Numeric Work",
        SavedViewConfiguration(
            search_text="",
            match_mode=SearchMatchMode.ALL,
            include_superseded=False,
            archive_query=ArchiveQuery(
                prediction_type=PredictionType.NUMERIC,
                tags=("Work",),
                sort=ArchiveSort.QUESTION_A_TO_Z,
            ),
        ),
    )
    before_binary = operations.get_prediction(binary.prediction_id)
    before_numeric = operations.get_numeric_prediction(numeric.prediction_id)
    database.close()

    listed = StringIO()
    assert run(["saved-views"], database_path=database_path, stdout=listed) == 0
    rendered_list = listed.getvalue()
    assert "Saved Views (2)" in rendered_list
    assert f"#{evidence_view.saved_view_id} | Evidence Search" in rendered_list
    assert "Search: project lead" in rendered_list
    assert f"#{numeric_view.saved_view_id} | Numeric Work" in rendered_list
    assert "Forecast type: Numeric" in rendered_list

    by_name = StringIO()
    assert (
        run(
            ["saved-view", "--name", "eViDeNcE sEaRcH"],
            database_path=database_path,
            stdout=by_name,
        )
        == 0
    )
    rendered_name = by_name.getvalue()
    assert (
        f"Saved View #{evidence_view.saved_view_id}: Evidence Search" in rendered_name
    )
    assert f"#{binary.prediction_id} | BINARY | OPEN | 55% Yes" in rendered_name
    assert "Match: Journal entry match" in rendered_name
    assert "work items" not in rendered_name

    by_id = StringIO()
    assert (
        run(
            ["saved-view", "--id", str(numeric_view.saved_view_id)],
            database_path=database_path,
            stdout=by_id,
        )
        == 0
    )
    rendered_id = by_id.getvalue()
    assert f"Saved View #{numeric_view.saved_view_id}: Numeric Work" in rendered_id
    assert f"#{numeric.prediction_id} | NUMERIC | OPEN" in rendered_id
    assert "saved-view evidence" not in rendered_id

    missing_errors = StringIO()
    assert (
        run(
            ["saved-view", "--name", "No such view"],
            database_path=database_path,
            stdout=StringIO(),
            stderr=missing_errors,
        )
        == 1
    )
    assert "Saved View named 'No such view' was not found." in missing_errors.getvalue()

    reopened = Database.open(database_path)
    reopened_operations = PredictionOperations(reopened, FixedClock(NOW), UTC)
    assert reopened_operations.get_prediction(binary.prediction_id) == before_binary
    assert (
        reopened_operations.get_numeric_prediction(numeric.prediction_id)
        == before_numeric
    )
    assert len(reopened_operations.list_saved_views()) == 2
    reopened.close()


def test_cli_show_binary_includes_terminal_detail_and_complete_history(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).create_prediction(
        "Will the first wording hold?",
        40,
        rationale="Initial <reason>\x1b[31m",
        background="Two lines\nSecond line",
        resolution_criteria="Use the published result.",
        forecast_deadline=date(2099, 12, 30),
        expected_resolution=date(2099, 12, 31),
        tags=("History", "CLI"),
    )
    journal_operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=1)),
        local_timezone=UTC,
    )
    journal = journal_operations.add_journal_entry(
        created.prediction_id,
        "Original evidence",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=2)),
        local_timezone=UTC,
    ).correct_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "Corrected evidence",
        expected_correction_id=None,
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=3)),
        local_timezone=UTC,
    ).revise_forecast(
        created.prediction_id,
        65,
        rationale="New evidence",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=4)),
        local_timezone=UTC,
    ).add_forecast_review(
        created.prediction_id,
        note="Still convinced.",
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    updated = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=5)),
        local_timezone=UTC,
    ).update_metadata(
        created.prediction_id,
        question="Will the corrected wording hold?",
        background=created.background,
        resolution_criteria="Use the certified published result.",
        forecast_deadline=created.forecast_deadline,
        expected_resolution=created.expected_resolution,
        tags=created.tags,
        expected_metadata_version=revised.metadata_version,
        confirm_meaning_change=True,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=6)),
        local_timezone=UTC,
    ).resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Certified result published.",
        postmortem="The revision was justified.",
        expected_revision_id=updated.current_revision_id,
        expected_metadata_version=updated.metadata_version,
    )
    database.close()

    output = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=output,
        )
        == 0
    )
    rendered = output.getvalue()

    assert f"Prediction #{created.prediction_id}" in rendered
    assert "Type: Binary" in rendered
    assert "Status: Resolved" in rendered
    assert "Question: Will the corrected wording hold?" in rendered
    assert "Current forecast: 65% Yes" in rendered
    assert "Background: Two lines\n  Second line" in rendered
    assert "Tags: CLI, History" in rendered
    assert "Outcome: Yes" in rendered
    assert "Scoring forecast: 65% Yes (revision 2" in rendered
    assert "Resolution notes: Certified result published." in rendered
    assert "Postmortem: The revision was justified." in rendered
    assert "Definition history" in rendered
    assert "Question before: Will the first wording hold?" in rendered
    assert "Question after: Will the corrected wording hold?" in rendered
    assert "FORECAST | Revision 1" in rendered
    assert "FORECAST | Revision 2" in rendered
    assert "40% -> 65% Yes" in rendered
    assert "JOURNAL | Entry" in rendered
    assert "Body: Corrected evidence" in rendered
    assert "Original body:" in rendered
    assert "Original evidence" in rendered
    assert "Correction 1:" in rendered
    assert "REVIEW | Review" in rendered
    assert "Retained forecast: 65% Yes" in rendered
    assert "Note: Still convinced." in rendered
    assert "Initial <reason>\\x1b[31m" in rendered
    assert "\x1b[31m" not in rendered
    assert NOW.astimezone().isoformat(sep=" ", timespec="microseconds") in rendered


def test_cli_show_numeric_preserves_exact_values_reviews_and_resolution(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).create_numeric_prediction(
        "What exact temperature will be measured?",
        "\u00b0C",
        3,
        "-10.125",
        "0.000",
        "12.500",
        80,
        rationale="Exact signed decimal baseline.",
        tags=("Numeric",),
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=1)),
        local_timezone=UTC,
    ).revise_numeric_forecast(
        created.prediction_id,
        "-8.250",
        "1.125",
        "11.750",
        90,
        rationale="A better instrument arrived.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=2)),
        local_timezone=UTC,
    ).add_numeric_forecast_review(
        created.prediction_id,
        note="Kept after checking the instrument.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    resolved = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=3)),
        local_timezone=UTC,
    ).resolve_numeric_prediction(
        created.prediction_id,
        "-8.250",
        resolution_notes="Read directly from the display.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    database.close()

    output = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=output,
        )
        == 0
    )
    rendered = output.getvalue()

    assert "Type: Numeric" in rendered
    assert "Status: Resolved" in rendered
    assert (
        "Current forecast: 90% interval -8.250 to 11.750 \u00b0C; median 1.125 \u00b0C"
        in rendered
    )
    assert "Decimal precision: 3" in rendered
    assert "Actual value: -8.250 \u00b0C" in rendered
    assert (
        "Scoring forecast: 90% interval -8.250 to 11.750 \u00b0C; median 1.125 \u00b0C"
        in rendered
    )
    assert f"ID {resolved.resolution.scoring_revision_id}" in rendered
    assert (
        "Before: 80% interval -10.125 to 12.500 \u00b0C; median 0.000 \u00b0C"
        in rendered
    )
    assert (
        "Forecast: 90% interval -8.250 to 11.750 \u00b0C; median 1.125 \u00b0C"
        in rendered
    )
    assert "REVIEW | Review" in rendered
    assert "Note: Kept after checking the instrument." in rendered


def test_cli_show_not_found_is_clear_nonzero_and_closes_database(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    output = StringIO()
    errors = StringIO()

    result = run(
        ["show", "999"],
        database_path=database_path,
        stdout=output,
        stderr=errors,
    )

    assert result == 1
    assert output.getvalue() == ""
    assert errors.getvalue() == "Error: Prediction 999 was not found.\n"
    reopened = Database.open(database_path)
    assert reopened.is_open
    reopened.close()


def test_cli_read_commands_do_not_create_or_change_product_history(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    created = operations.create_prediction(
        "Will read-only CLI commands leave history untouched?",
        52,
        rationale="One immutable forecast.",
    )
    before_detail = operations.get_prediction(created.prediction_id)
    before_timeline = operations.list_timeline(created.prediction_id)
    before_threshold = operations.get_stale_threshold_days()
    before_schema_version = database.schema_version
    database.close()

    list_output = StringIO()
    show_output = StringIO()
    assert run(["list"], database_path=database_path, stdout=list_output) == 0
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=show_output,
        )
        == 0
    )

    reopened = Database.open(database_path)
    reopened_operations = PredictionOperations(
        reopened,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    assert reopened_operations.get_prediction(created.prediction_id) == before_detail
    assert reopened_operations.list_timeline(created.prediction_id) == before_timeline
    assert reopened_operations.get_stale_threshold_days() == before_threshold
    assert reopened.schema_version == before_schema_version
    reopened.close()


def test_cli_rejects_unrecognized_database_without_replacing_it(tmp_path) -> None:
    database_path = tmp_path / "not-reckonsolve.sqlite3"
    original_bytes = b"This is not a SQLite database."
    database_path.write_bytes(original_bytes)
    output = StringIO()
    errors = StringIO()

    result = run(
        ["list"],
        database_path=database_path,
        stdout=output,
        stderr=errors,
    )

    assert result == 1
    assert output.getvalue() == ""
    assert errors.getvalue().startswith("Error: ")
    assert database_path.read_bytes() == original_bytes


def test_cli_creates_minimal_binary_with_gui_default_and_stable_id(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    output = StringIO()
    errors = StringIO()

    result = run(
        ["create", "binary"],
        database_path=database_path,
        stdin=StringIO("Will the CLI default this Binary forecast correctly?\n\n\n"),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert errors.getvalue() == ""
    assert "Probability [50]:" in output.getvalue()
    assert "Created Binary Prediction #1." in output.getvalue()
    assert "Current forecast: 50% Yes" in output.getvalue()

    database = Database.open(database_path)
    created = PredictionOperations(database).get_prediction(1)
    assert created.question == "Will the CLI default this Binary forecast correctly?"
    assert created.probability_percent == 50
    assert created.current_revision_sequence == 1
    assert created.current_rationale is None
    assert created.background is None
    assert created.tags == ()
    database.close()


def test_cli_creates_binary_with_all_optional_details_and_endpoint_note(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    output = StringIO()

    result = run(
        ["create", "binary"],
        database_path=database_path,
        stdin=StringIO(
            "Will the complete Binary creation persist?\n"
            "0\n"
            "yes\n"
            "Initial reasons\n"
            "Background context\n"
            "Use the official result\n"
            "2099-12-30\n"
            "2099-12-31\n"
            "Work, Personal, work\n"
        ),
        stdout=output,
    )

    assert result == 0
    assert "Note: 0% expresses absolute certainty." in output.getvalue()
    assert "Created Binary Prediction #1." in output.getvalue()
    assert "Current forecast: 0% Yes" in output.getvalue()

    database = Database.open(database_path)
    created = PredictionOperations(database).get_prediction(1)
    timeline = PredictionOperations(database).list_timeline(1)
    assert created.probability_percent == 0
    assert created.current_rationale == "Initial reasons"
    assert created.background == "Background context"
    assert created.resolution_criteria == "Use the official result"
    assert created.forecast_deadline == date(2099, 12, 30)
    assert created.expected_resolution == date(2099, 12, 31)
    assert set(created.tags) == {"Work", "Personal"}
    assert len(timeline) == 1
    database.close()


def test_cli_numeric_creation_retries_invalid_fields_and_round_trips_exactly(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    output = StringIO()
    errors = StringIO()

    result = run(
        ["create", "numeric"],
        database_path=database_path,
        stdin=StringIO(
            "What exact temperature will be recorded?\n"
            "\u00b0C\n"
            "7\n"
            "3\n"
            "3.00\n"
            "2.00\n"
            "1.00\n"
            "80\n"
            "-1.25\n"
            "2.00\n"
            "9.50\n"
            "100\n"
            "85\n"
            "y\n"
            "Exact initial interval\n"
            "Instrument background\n"
            "Use the calibrated display\n"
            "2099-01-01\n"
            "2099-01-02\n"
            "Numeric, Weather\n"
        ),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert "Decimal places must be a whole number from 0 to 6." in errors.getvalue()
    assert (
        "Invalid numeric forecast: Numeric forecasts require lower bound <= median "
        "<= upper bound." in errors.getvalue()
    )
    assert "Confidence must be a whole number from 1 to 99." in errors.getvalue()
    assert "Created Numeric Prediction #1." in output.getvalue()
    assert (
        "Current forecast: 85% interval -1.250 to 9.500 \u00b0C; median 2.000 \u00b0C"
        in output.getvalue()
    )

    database = Database.open(database_path)
    created = PredictionOperations(database).get_numeric_prediction(1)
    assert created.decimal_places == 3
    assert created.unit == "\u00b0C"
    assert str(created.current_revision.lower_bound) == "-1.250"
    assert str(created.current_revision.median_estimate) == "2.000"
    assert str(created.current_revision.upper_bound) == "9.500"
    assert created.current_revision.confidence_percent == 85
    assert created.current_revision.rationale == "Exact initial interval"
    assert created.background == "Instrument background"
    assert created.resolution_criteria == "Use the calibrated display"
    assert created.forecast_deadline == date(2099, 1, 1)
    assert created.expected_resolution == date(2099, 1, 2)
    assert set(created.tags) == {"Numeric", "Weather"}
    assert len(PredictionOperations(database).list_numeric_timeline(1)) == 1
    database.close()


@pytest.mark.parametrize(
    "input_stream",
    (
        StringIO("Will EOF cancel before a probability?\n"),
        pytest.param(None, id="keyboard-interrupt"),
    ),
)
def test_cli_creation_cancellation_is_clear_and_creates_no_prediction(
    tmp_path,
    input_stream,
) -> None:
    class InterruptingInput(StringIO):
        def readline(self, *args, **kwargs) -> str:
            raise KeyboardInterrupt

    database_path = tmp_path / "reckonsolve.sqlite3"
    errors = StringIO()
    supplied_input = InterruptingInput() if input_stream is None else input_stream

    result = run(
        ["create", "binary"],
        database_path=database_path,
        stdin=supplied_input,
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 130
    assert errors.getvalue().endswith("Cancelled. No changes were made.\n")
    database = Database.open(database_path)
    assert PredictionOperations(database).browse_predictions().predictions == ()
    database.close()


def test_cli_creation_domain_failure_is_atomic(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    errors = StringIO()

    result = run(
        ["create", "binary"],
        database_path=database_path,
        stdin=StringIO(
            "Will a past deadline prevent this creation?\n60\ny\n\n\n\n2000-01-01\n\n\n"
        ),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "Forecast Deadline cannot be earlier than today" in errors.getvalue()
    database = Database.open(database_path)
    assert PredictionOperations(database).browse_predictions().predictions == ()
    database.close()


def test_cli_created_binary_and_numeric_predictions_appear_in_desktop_browser(
    qtbot,
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    assert (
        run(
            ["create", "binary"],
            database_path=database_path,
            stdin=StringIO("Will the GUI display this CLI Binary?\n70\n\n"),
            stdout=StringIO(),
        )
        == 0
    )
    assert (
        run(
            ["create", "numeric"],
            database_path=database_path,
            stdin=StringIO(
                "How many CLI items will the GUI display?\nitems\n\n2\n5\n9\n\n\n"
            ),
            stdout=StringIO(),
        )
        == 0
    )

    runtime = create_gui_runtime(database_path=database_path)
    qtbot.addWidget(runtime.window)
    runtime.window.show()
    runtime.window.navigate_to("Predictions")
    results = runtime.window.findChild(QListWidget, "predictionBrowserResults")

    assert results is not None
    assert results.count() == 2
    rendered_rows = "\n".join(
        (
            str(results.item(index).data(Qt.ItemDataRole.AccessibleTextRole))
            + "\n"
            + str(results.item(index).data(Qt.ItemDataRole.AccessibleDescriptionRole))
        )
        for index in range(2)
    )
    assert "Will the GUI display this CLI Binary?" in rendered_rows
    assert "70%" in rendered_rows
    assert "How many CLI items will the GUI display?" in rendered_rows
    assert "80% interval: 2–9 items" in rendered_rows
    assert "median: 5 items" in rendered_rows
    runtime.close()


def test_cli_revises_binary_with_validation_retry_and_immutable_history(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will the Binary CLI revision be retained?\x1b[31m",
        40,
    )
    database.close()
    output = StringIO()
    errors = StringIO()

    result = run(
        ["revise", str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO("not-a-number\n40\n100\nNew decisive evidence\n"),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert "Question: Will the Binary CLI revision be retained?\\x1b[31m" in (
        output.getvalue()
    )
    assert "\x1b[31m" not in output.getvalue()
    assert "Current forecast: 40% Yes" in output.getvalue()
    assert "Note: 100% expresses absolute certainty." in output.getvalue()
    assert f"Revised Prediction #{created.prediction_id}." in output.getvalue()
    assert "Current forecast: 100% Yes" in output.getvalue()
    assert "Probability must be a whole number from 0 to 100." in errors.getvalue()
    assert "The probability is unchanged." in errors.getvalue()

    database = Database.open(database_path)
    operations = PredictionOperations(database)
    revisions = operations.list_forecast_revisions(created.prediction_id)
    assert [
        (revision.sequence, revision.probability_percent) for revision in revisions
    ] == [
        (1, 40),
        (2, 100),
    ]
    assert revisions[1].rationale == "New decisive evidence"
    database.close()


def test_cli_revises_numeric_with_exact_defaults_and_validation_retry(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_numeric_prediction(
        "What exact value will the Numeric CLI revise?",
        "units",
        3,
        "-1.250",
        "2.000",
        "9.500",
        80,
    )
    database.close()
    output = StringIO()
    errors = StringIO()

    result = run(
        ["revise", str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO(
            "3.000\n2.000\n1.000\n80\n"
            "\n\n\n\n"
            "\n2.125\n\n90\nInstrument reading changed\n"
        ),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert "Lower bound [-1.250]:" in output.getvalue()
    assert "Median estimate [2.000]:" in output.getvalue()
    assert "Upper bound [9.500]:" in output.getvalue()
    assert "Confidence [80]:" in output.getvalue()
    assert (
        "Current forecast: 90% interval -1.250 to 9.500 units; "
        "median 2.125 units" in output.getvalue()
    )
    assert "Invalid numeric forecast:" in errors.getvalue()
    assert "The numeric forecast is unchanged." in errors.getvalue()

    database = Database.open(database_path)
    revisions = PredictionOperations(database).list_numeric_forecast_revisions(
        created.prediction_id
    )
    assert len(revisions) == 2
    assert str(revisions[0].median_estimate) == "2.000"
    assert str(revisions[1].lower_bound) == "-1.250"
    assert str(revisions[1].median_estimate) == "2.125"
    assert str(revisions[1].upper_bound) == "9.500"
    assert revisions[1].confidence_percent == 90
    assert revisions[1].rationale == "Instrument reading changed"
    database.close()


@pytest.mark.parametrize("prediction_type", ("binary", "numeric"))
def test_cli_journal_and_review_preserve_forecast_history_and_cross_interface_timeline(
    tmp_path,
    prediction_type,
) -> None:
    database_path = tmp_path / f"{prediction_type}.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    if prediction_type == "binary":
        created = operations.create_prediction("Will active records stay distinct?", 65)
    else:
        created = operations.create_numeric_prediction(
            "How many active records will stay distinct?",
            "records",
            0,
            "2",
            "5",
            "9",
            75,
        )
    database.close()
    journal_output = StringIO()
    journal_errors = StringIO()

    assert (
        run(
            ["journal", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("\nA concise CLI Journal entry\n"),
            stdout=journal_output,
            stderr=journal_errors,
        )
        == 0
    )
    assert "Journal entry text is required." in journal_errors.getvalue()
    assert "The current forecast is unchanged." in journal_output.getvalue()

    review_output = StringIO()
    assert (
        run(
            ["review", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("Rechecked the available evidence\n"),
            stdout=review_output,
        )
        == 0
    )
    assert "kept it unchanged" in review_output.getvalue()
    assert "The current forecast is unchanged." in review_output.getvalue()

    database = Database.open(database_path)
    operations = PredictionOperations(database)
    if prediction_type == "binary":
        assert len(operations.list_forecast_revisions(created.prediction_id)) == 1
        timeline = operations.list_timeline(created.prediction_id)
    else:
        assert (
            len(operations.list_numeric_forecast_revisions(created.prediction_id)) == 1
        )
        timeline = operations.list_numeric_timeline(created.prediction_id)
    assert len(timeline) == 3
    database.close()

    show_output = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=show_output,
        )
        == 0
    )
    rendered = show_output.getvalue()
    assert "JOURNAL | Entry" in rendered
    assert "Body: A concise CLI Journal entry" in rendered
    assert "REVIEW | Review" in rendered
    assert "Note: Rechecked the available evidence" in rendered


def test_cli_journal_does_not_refresh_attention_but_review_does(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    old = NOW - timedelta(days=30)
    database = Database.open(database_path)
    created = PredictionOperations(
        database,
        FixedClock(old),
        local_timezone=UTC,
    ).create_prediction("Will Review refresh this stale forecast?", 55)
    database.close()
    monkeypatch.setattr(
        reckonsolve.cli,
        "PredictionOperations",
        lambda database: PredictionOperations(
            database,
            FixedClock(NOW),
            local_timezone=UTC,
        ),
    )

    assert (
        run(
            ["journal", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("New evidence without reconsideration\n"),
            stdout=StringIO(),
        )
        == 0
    )
    database = Database.open(database_path)
    snapshot = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).get_dashboard()
    assert [item.prediction_id for item in snapshot.needs_attention_predictions] == [
        created.prediction_id
    ]
    database.close()

    assert (
        run(
            ["review", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("\n"),
            stdout=StringIO(),
        )
        == 0
    )
    database = Database.open(database_path)
    operations = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    assert operations.get_dashboard().needs_attention_predictions == ()
    assert len(operations.list_forecast_revisions(created.prediction_id)) == 1
    database.close()


@pytest.mark.parametrize(
    "command",
    ("revise", "journal", "review", "resolve", "invalidate", "delete"),
)
def test_cli_mutation_eof_cancels_without_history(
    tmp_path,
    command,
) -> None:
    database_path = tmp_path / f"{command}.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will cancelled active commands leave history alone?",
        45,
    )
    before = PredictionOperations(database).list_timeline(created.prediction_id)
    database.close()
    errors = StringIO()

    result = run(
        [command, str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 130
    assert errors.getvalue() == "Cancelled. No changes were made.\n"
    database = Database.open(database_path)
    assert PredictionOperations(database).list_timeline(created.prediction_id) == before
    database.close()


def test_cli_rejects_stale_revision_context_without_overwriting_other_change(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will concurrent CLI revision context be rejected?",
        30,
    )
    database.close()

    class ConcurrentRevisionInput(StringIO):
        changed = False

        def readline(self, *args, **kwargs) -> str:
            if not self.changed:
                self.changed = True
                concurrent_database = Database.open(database_path)
                concurrent_operations = PredictionOperations(concurrent_database)
                current = concurrent_operations.get_prediction(created.prediction_id)
                concurrent_operations.revise_forecast(
                    created.prediction_id,
                    50,
                    expected_revision_id=current.current_revision_id,
                    expected_metadata_version=current.metadata_version,
                )
                concurrent_database.close()
            return super().readline(*args, **kwargs)

    errors = StringIO()
    result = run(
        ["revise", str(created.prediction_id)],
        database_path=database_path,
        stdin=ConcurrentRevisionInput("70\nLate local reasoning\n"),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "changed before the forecast could be revised" in errors.getvalue()
    database = Database.open(database_path)
    revisions = PredictionOperations(database).list_forecast_revisions(
        created.prediction_id
    )
    assert [revision.probability_percent for revision in revisions] == [30, 50]
    database.close()


@pytest.mark.parametrize(
    ("command", "command_input", "expected_error"),
    (
        (
            "journal",
            "Locally reviewed Journal text\n",
            "changed before the Journal entry could be saved",
        ),
        (
            "review",
            "Locally reviewed Forecast Review note\n",
            "changed before the Forecast Review could be saved",
        ),
    ),
)
def test_cli_journal_and_review_reject_stale_metadata_context(
    tmp_path,
    command,
    command_input,
    expected_error,
) -> None:
    database_path = tmp_path / f"{command}.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will stale prose context be rejected?",
        35,
    )
    database.close()

    class ConcurrentMetadataInput(StringIO):
        changed = False

        def readline(self, *args, **kwargs) -> str:
            if not self.changed:
                self.changed = True
                concurrent_database = Database.open(database_path)
                concurrent_operations = PredictionOperations(concurrent_database)
                current = concurrent_operations.get_prediction(created.prediction_id)
                concurrent_operations.update_metadata(
                    created.prediction_id,
                    question=current.question,
                    background="Background added by another interface.",
                    resolution_criteria=current.resolution_criteria,
                    forecast_deadline=current.forecast_deadline,
                    expected_resolution=current.expected_resolution,
                    tags=current.tags,
                    expected_metadata_version=current.metadata_version,
                )
                concurrent_database.close()
            return super().readline(*args, **kwargs)

    errors = StringIO()
    result = run(
        [command, str(created.prediction_id)],
        database_path=database_path,
        stdin=ConcurrentMetadataInput(command_input),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert expected_error in errors.getvalue()
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    assert len(operations.list_timeline(created.prediction_id)) == 1
    assert (
        operations.get_prediction(created.prediction_id).background
        == "Background added by another interface."
    )
    database.close()


def test_cli_active_commands_respect_derived_lock_boundaries(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    created_at = NOW - timedelta(days=3)
    database = Database.open(database_path)
    created = PredictionOperations(
        database,
        FixedClock(created_at),
        local_timezone=UTC,
    ).create_prediction(
        "Will this forecast be Locked at the command boundary?",
        60,
        forecast_deadline=(created_at + timedelta(days=1)).date(),
    )
    database.close()
    monkeypatch.setattr(
        reckonsolve.cli,
        "PredictionOperations",
        lambda database: PredictionOperations(
            database,
            FixedClock(NOW),
            local_timezone=UTC,
        ),
    )

    for command, expected_error in (
        ("revise", "Forecast Deadline has passed"),
        ("review", "prediction is Locked"),
    ):
        errors = StringIO()
        assert (
            run(
                [command, str(created.prediction_id)],
                database_path=database_path,
                stdin=StringIO("70\n"),
                stdout=StringIO(),
                stderr=errors,
            )
            == 1
        )
        assert expected_error in errors.getvalue()

    assert (
        run(
            ["journal", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("Evidence after the deadline\n"),
            stdout=StringIO(),
        )
        == 0
    )
    database = Database.open(database_path)
    operations = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    assert operations.get_prediction(created.prediction_id).status.value == "locked"
    assert len(operations.list_forecast_revisions(created.prediction_id)) == 1
    assert len(operations.list_timeline(created.prediction_id)) == 2
    database.close()


def test_cli_resolves_binary_with_confirmation_and_final_scoring_revision(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    created = operations.create_prediction("Will the CLI resolution be Yes?", 60)
    revised = operations.revise_forecast(
        created.prediction_id,
        35,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    database.close()
    output = StringIO()
    errors = StringIO()

    result = run(
        ["resolve", str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO(
            "maybe\nyes\nCertified public result\nI updated too slowly\nperhaps\ny\n"
        ),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert "Current forecast: 35% Yes" in output.getvalue()
    assert "cannot be reopened or changed" in output.getvalue()
    assert "Resolved Prediction #" in output.getvalue()
    assert "Outcome: Yes" in output.getvalue()
    assert "Enter yes or no." in errors.getvalue()
    assert "Enter y or n." in errors.getvalue()

    database = Database.open(database_path)
    resolved = PredictionOperations(database).get_prediction(created.prediction_id)
    assert resolved.status.value == "resolved"
    assert resolved.resolution is not None
    assert resolved.resolution.outcome is BinaryOutcome.YES
    assert resolved.resolution.scoring_revision_id == revised.current_revision_id
    assert resolved.resolution.scoring_probability_percent == 35
    assert resolved.resolution.resolution_notes == "Certified public result"
    assert resolved.resolution.postmortem == "I updated too slowly"
    assert PredictionOperations(database).get_analytics().scored_prediction_count == 1
    database.close()


def test_cli_resolves_numeric_with_exact_validation_and_optional_text(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_numeric_prediction(
        "What exact quantity will resolve?",
        "widgets",
        2,
        "-5.00",
        "1.25",
        "8.50",
        85,
    )
    database.close()
    output = StringIO()
    errors = StringIO()

    result = run(
        ["resolve", str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO("\n1.234\n-2.5\nMeasured directly\n\nyes\n"),
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert "Actual value (widgets):" in output.getvalue()
    assert "Outcome: -2.50 widgets" in output.getvalue()
    assert "Actual value is required." in errors.getvalue()
    assert "Invalid actual value:" in errors.getvalue()

    database = Database.open(database_path)
    operations = PredictionOperations(database)
    resolved = operations.get_numeric_prediction(created.prediction_id)
    assert resolved.status.value == "resolved"
    assert resolved.resolution is not None
    assert str(resolved.resolution.actual_value) == "-2.50"
    assert (
        resolved.resolution.scoring_revision_id == created.current_revision.revision_id
    )
    assert resolved.resolution.resolution_notes == "Measured directly"
    assert resolved.resolution.postmortem is None
    assert operations.get_forecast_analytics().numeric.scored_prediction_count == 1
    database.close()


@pytest.mark.parametrize("prediction_type", ("binary", "numeric"))
def test_cli_invalidation_preserves_both_forecast_types_outside_scoring(
    tmp_path,
    prediction_type,
) -> None:
    database_path = tmp_path / f"{prediction_type}.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    if prediction_type == "binary":
        created = operations.create_prediction("Will this become Invalid?", 45)
    else:
        created = operations.create_numeric_prediction(
            "How many invalid quantities will remain?",
            "items",
            0,
            "1",
            "3",
            "8",
            70,
        )
    database.close()
    output = StringIO()

    assert (
        run(
            ["invalidate", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("The event became undefined\ny\n"),
            stdout=output,
        )
        == 0
    )
    assert "preserves this prediction and its complete history" in output.getvalue()
    assert "excluded from scoring" in output.getvalue()

    database = Database.open(database_path)
    operations = PredictionOperations(database)
    invalid = operations.get_prediction_for_navigation(created.prediction_id)
    assert invalid.status.value == "invalid"
    assert invalid.invalidation is not None
    assert invalid.invalidation.reason == "The event became undefined"
    assert invalid.resolution is None
    analytics = operations.get_forecast_analytics()
    assert analytics.binary.scored_prediction_count == 0
    assert analytics.numeric.scored_prediction_count == 0
    database.close()


@pytest.mark.parametrize("prediction_type", ("binary", "numeric"))
def test_cli_permanently_deletes_only_confirmed_untouched_open_predictions(
    tmp_path,
    prediction_type,
) -> None:
    database_path = tmp_path / f"{prediction_type}.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    operations.create_prediction("Will a survivor remain?", 50)
    if prediction_type == "binary":
        target = operations.create_prediction("Will this disposable row go?", 50)
    else:
        target = operations.create_numeric_prediction(
            "How many disposable rows will go?",
            "rows",
            0,
            "1",
            "2",
            "3",
            80,
        )
    database.close()
    output = StringIO()

    assert (
        run(
            ["delete", str(target.prediction_id)],
            database_path=database_path,
            stdin=StringIO("yes\n"),
            stdout=output,
        )
        == 0
    )
    assert "cannot be undone" in output.getvalue()
    assert f"Deleted Prediction #{target.prediction_id} permanently." in (
        output.getvalue()
    )

    database = Database.open(database_path)
    assert target.prediction_id not in {
        item.prediction_id
        for item in PredictionOperations(database).browse_predictions().predictions
    }
    database.close()


@pytest.mark.parametrize(
    ("command", "command_input"),
    (
        ("resolve", "yes\nFactual result\nReflection\nno\n"),
        ("invalidate", "Optional reason\n\n"),
        ("delete", "n\n"),
    ),
)
def test_cli_declined_terminal_confirmation_cancels_without_changes(
    tmp_path,
    command,
    command_input,
) -> None:
    database_path = tmp_path / f"{command}.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will declining confirmation preserve this row?",
        52,
    )
    before = PredictionOperations(database).get_prediction(created.prediction_id)
    database.close()
    errors = StringIO()

    result = run(
        [command, str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO(command_input),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 130
    assert errors.getvalue() == "Cancelled. No changes were made.\n"
    database = Database.open(database_path)
    after = PredictionOperations(database).get_prediction(created.prediction_id)
    assert after == before
    database.close()


@pytest.mark.parametrize("prediction_type", ("binary", "numeric"))
def test_cli_delete_directs_meaningful_history_to_invalid(
    tmp_path,
    prediction_type,
) -> None:
    database_path = tmp_path / f"{prediction_type}.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    if prediction_type == "binary":
        created = operations.create_prediction("Will revised history survive?", 40)
        operations.revise_forecast(
            created.prediction_id,
            60,
            expected_revision_id=created.current_revision_id,
            expected_metadata_version=created.metadata_version,
        )
    else:
        created = operations.create_numeric_prediction(
            "How many journaled records survive?",
            "records",
            0,
            "1",
            "2",
            "4",
            80,
        )
        operations.add_numeric_journal_entry(
            created.prediction_id,
            "Meaningful evidence",
            expected_revision_id=created.current_revision.revision_id,
            expected_metadata_version=created.metadata_version,
        )
    database.close()
    errors = StringIO()

    result = run(
        ["delete", str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO("yes\n"),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "Mark this prediction Invalid" in errors.getvalue()
    database = Database.open(database_path)
    assert PredictionOperations(database).get_prediction_for_navigation(
        created.prediction_id
    )
    database.close()


@pytest.mark.parametrize(
    ("prediction_type", "command"),
    (
        ("binary", "resolve"),
        ("binary", "invalidate"),
        ("numeric", "resolve"),
        ("numeric", "invalidate"),
    ),
)
def test_cli_locked_predictions_allow_both_terminal_decisions(
    tmp_path,
    monkeypatch,
    prediction_type,
    command,
) -> None:
    database_path = tmp_path / f"{prediction_type}-{command}.sqlite3"
    created_at = NOW - timedelta(days=3)
    database = Database.open(database_path)
    operations = PredictionOperations(
        database,
        FixedClock(created_at),
        local_timezone=UTC,
    )
    deadline = (created_at + timedelta(days=1)).date()
    if prediction_type == "binary":
        created = operations.create_prediction(
            "Will this Locked Binary terminate?",
            65,
            forecast_deadline=deadline,
        )
    else:
        created = operations.create_numeric_prediction(
            "How many Locked Numeric values terminate?",
            "values",
            0,
            "1",
            "5",
            "9",
            80,
            forecast_deadline=deadline,
        )
    database.close()
    monkeypatch.setattr(
        reckonsolve.cli,
        "PredictionOperations",
        lambda database: PredictionOperations(
            database,
            FixedClock(NOW),
            local_timezone=UTC,
        ),
    )
    if command == "invalidate":
        command_input = "Deadline made it unresolvable\ny\n"
    elif prediction_type == "binary":
        command_input = "no\n\n\ny\n"
    else:
        command_input = "6\n\n\ny\n"

    assert (
        run(
            [command, str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO(command_input),
            stdout=StringIO(),
        )
        == 0
    )
    database = Database.open(database_path)
    terminal = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).get_prediction_for_navigation(created.prediction_id)
    assert terminal.status.value == ("resolved" if command == "resolve" else "invalid")
    database.close()


@pytest.mark.parametrize("command", ("resolve", "invalidate", "delete"))
def test_cli_rejects_every_terminal_action_after_resolution(
    tmp_path,
    command,
) -> None:
    database_path = tmp_path / f"{command}.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    created = operations.create_prediction(
        "Will terminal CLI decisions remain one-way?",
        70,
    )
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    database.close()
    errors = StringIO()

    result = run(
        [command, str(created.prediction_id)],
        database_path=database_path,
        stdin=StringIO("yes\n\n\nyes\n"),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "Resolved" in errors.getvalue() or "Terminal prediction history" in (
        errors.getvalue()
    )
    database = Database.open(database_path)
    current = PredictionOperations(database).get_prediction(created.prediction_id)
    assert current == resolved
    database.close()


@pytest.mark.parametrize(
    ("command", "command_input"),
    (
        ("resolve", "yes\n\n\ny\n"),
        ("invalidate", "Reason reviewed locally\ny\n"),
    ),
)
def test_cli_terminal_commands_reject_stale_reviewed_forecast(
    tmp_path,
    command,
    command_input,
) -> None:
    database_path = tmp_path / f"{command}.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will a concurrent forecast block termination?",
        25,
    )
    database.close()

    class ConcurrentRevisionInput(StringIO):
        changed = False

        def readline(self, *args, **kwargs) -> str:
            if not self.changed:
                self.changed = True
                concurrent_database = Database.open(database_path)
                concurrent_operations = PredictionOperations(concurrent_database)
                current = concurrent_operations.get_prediction(created.prediction_id)
                concurrent_operations.revise_forecast(
                    created.prediction_id,
                    55,
                    expected_revision_id=current.current_revision_id,
                    expected_metadata_version=current.metadata_version,
                )
                concurrent_database.close()
            return super().readline(*args, **kwargs)

    errors = StringIO()
    result = run(
        [command, str(created.prediction_id)],
        database_path=database_path,
        stdin=ConcurrentRevisionInput(command_input),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "changed before the lifecycle action could be saved" in errors.getvalue()
    database = Database.open(database_path)
    current = PredictionOperations(database).get_prediction(created.prediction_id)
    assert current.status.value == "open"
    assert current.probability_percent == 55
    database.close()


def test_cli_delete_rechecks_untouched_history_after_confirmation_prompt(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will concurrent history block deletion?",
        50,
    )
    database.close()

    class ConcurrentJournalInput(StringIO):
        changed = False

        def readline(self, *args, **kwargs) -> str:
            if not self.changed:
                self.changed = True
                concurrent_database = Database.open(database_path)
                concurrent_operations = PredictionOperations(concurrent_database)
                current = concurrent_operations.get_prediction(created.prediction_id)
                concurrent_operations.add_journal_entry(
                    created.prediction_id,
                    "Meaningful history from another interface",
                    expected_revision_id=current.current_revision_id,
                    expected_metadata_version=current.metadata_version,
                )
                concurrent_database.close()
            return super().readline(*args, **kwargs)

    errors = StringIO()
    result = run(
        ["delete", str(created.prediction_id)],
        database_path=database_path,
        stdin=ConcurrentJournalInput("yes\n"),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "Mark this prediction Invalid" in errors.getvalue()
    database = Database.open(database_path)
    assert len(PredictionOperations(database).list_timeline(created.prediction_id)) == 2
    database.close()


def test_cli_terminal_write_lock_failure_is_clear_and_preserves_state(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will lock contention leave this prediction Open?",
        50,
    )
    database.close()
    runtime = reckonsolve.cli.create_runtime(database_path=database_path)
    runtime.database._require_connection().execute("PRAGMA busy_timeout = 1")
    locker = Database.open(database_path)
    lock_context = locker.transaction()
    lock_context.__enter__()
    monkeypatch.setattr(
        reckonsolve.cli,
        "create_runtime",
        lambda **_kwargs: runtime,
    )
    errors = StringIO()
    try:
        result = run(
            ["invalidate", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("Lock test\ny\n"),
            stdout=StringIO(),
            stderr=errors,
        )
    finally:
        lock_context.__exit__(None, None, None)
        locker.close()

    assert result == 1
    assert "locked" in errors.getvalue().casefold()
    database = Database.open(database_path)
    current = PredictionOperations(database).get_prediction(created.prediction_id)
    assert current.status.value == "open"
    assert current.invalidation is None
    database.close()


def test_cli_backup_is_recoverable_and_records_success_across_restart(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    backup_path = tmp_path / "cli-backup.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_numeric_prediction(
        "How many records will the CLI backup recover?",
        "records",
        2,
        "-1.25",
        "3.00",
        "9.50",
        80,
        rationale="Preserve this exact interval.",
        tags=("CLI", "Recovery"),
    )
    database.close()
    monkeypatch.setattr(
        reckonsolve.cli,
        "PredictionOperations",
        lambda database: PredictionOperations(
            database,
            FixedClock(NOW),
            local_timezone=UTC,
        ),
    )
    output = StringIO()

    result = run(
        ["backup", str(backup_path)],
        database_path=database_path,
        stdout=output,
    )

    assert result == 0
    assert f"Backup created: {backup_path.resolve()}" in output.getvalue()
    assert "complete verified Reckonsolve SQLite database" in output.getvalue()
    assert "Last successful backup time recorded." in output.getvalue()

    reopened_source = Database.open(database_path)
    assert SettingsRepository(reopened_source).get_last_successful_backup_at() == NOW
    reopened_source.close()
    recovered = Database.open(backup_path)
    recovered_prediction = PredictionOperations(recovered).get_numeric_prediction(
        created.prediction_id
    )
    assert recovered_prediction.question == created.question
    assert str(recovered_prediction.current_revision.lower_bound) == "-1.25"
    assert str(recovered_prediction.current_revision.upper_bound) == "9.50"
    assert recovered_prediction.tags == ("CLI", "Recovery")
    recovered.close()


def test_cli_export_prompt_creates_complete_format_three_bundle(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    export_path = tmp_path / "cli-export.zip"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will the CLI export retain this Binary history?",
        65,
        rationale="Retain this rationale.",
        tags=("Export",),
    )
    database.close()
    output = StringIO()

    result = run(
        ["export-csv"],
        database_path=database_path,
        stdin=StringIO(f"{export_path}\n"),
        stdout=output,
    )

    assert result == 0
    assert "Destination [reckonsolve-export-" in output.getvalue()
    assert f"CSV export created: {export_path.resolve()}" in output.getvalue()
    assert "Exported 16 CSV files in format version 3." in output.getvalue()
    assert "not a recovery backup" in output.getvalue()
    with ZipFile(export_path) as archive:
        assert tuple(archive.namelist()) == EXPORT_ARCHIVE_NAMES
        assert archive.testzip() is None
        assert str(created.prediction_id).encode() in archive.read("predictions.csv")
        assert b"Format version: 3" in archive.read("README.txt")


def test_cli_show_preserves_complete_v04_terminal_histories_read_only(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)

    binary_operations = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    binary = binary_operations.create_prediction(
        "Will CLI show every Binary terminal fact?",
        70,
    )
    binary_operations.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Original Binary notes",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=1)),
        local_timezone=UTC,
    ).record_postmortem_skip(
        binary.prediction_id,
        expected_correction_id=None,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=2)),
        local_timezone=UTC,
    ).correct_binary_resolution(
        binary.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Corrected Binary notes",
        postmortem="Later Binary reflection",
        correction_reason="The certified outcome was No.",
        expected_correction_id=None,
    )

    numeric_operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=3)),
        local_timezone=UTC,
    )
    numeric = numeric_operations.create_numeric_prediction(
        "What exact value will CLI show?",
        "points",
        2,
        "-2.00",
        "1.50",
        "8.00",
        80,
    )
    numeric_operations.resolve_numeric_prediction(
        numeric.prediction_id,
        "7.25",
        postmortem="Original Numeric reflection",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=4)),
        local_timezone=UTC,
    ).correct_numeric_resolution(
        numeric.prediction_id,
        "-1.25",
        resolution_notes="Corrected Numeric notes",
        postmortem=None,
        correction_reason="The source used a signed value.",
        expected_correction_id=None,
    )

    invalid_operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=5)),
        local_timezone=UTC,
    )
    invalid = invalid_operations.create_prediction(
        "Will CLI show Invalid reason history?",
        20,
    )
    invalid_operations.invalidate_prediction(
        invalid.prediction_id,
        reason="Original invalid reason",
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=6)),
        local_timezone=UTC,
    ).correct_invalidation_reason(
        invalid.prediction_id,
        "Corrected invalid reason",
        expected_correction_id=None,
    )
    with database.transaction() as connection:
        counts_before = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "resolution_corrections",
                "numeric_resolution_corrections",
                "invalidation_reason_corrections",
                "postmortem_completions",
            )
        )
    database.close()

    binary_output = StringIO()
    numeric_output = StringIO()
    invalid_output = StringIO()
    assert (
        run(
            ["show", str(binary.prediction_id)],
            database_path=database_path,
            stdout=binary_output,
        )
        == 0
    )
    assert (
        run(
            ["show", str(numeric.prediction_id)],
            database_path=database_path,
            stdout=numeric_output,
        )
        == 0
    )
    assert (
        run(
            ["show", str(invalid.prediction_id)],
            database_path=database_path,
            stdout=invalid_output,
        )
        == 0
    )

    binary_text = binary_output.getvalue()
    assert "Effective outcome: No" in binary_text
    assert "Original Resolution |" in binary_text
    assert "Outcome: Yes" in binary_text
    assert "Correction 1 |" in binary_text
    assert "Changed fields: Outcome, Resolution notes, Postmortem" in binary_text
    assert "Correction reason: The certified outcome was No." in binary_text
    assert "Postmortem before: Not set" in binary_text
    assert "Postmortem after: Later Binary reflection" in binary_text
    assert "Postmortem completion" in binary_text
    assert "Skipped:" in binary_text

    numeric_text = numeric_output.getvalue()
    assert "Effective actual value: -1.25 points" in numeric_text
    assert "Actual value before: 7.25 points" in numeric_text
    assert "Actual value after: -1.25 points" in numeric_text
    assert "Postmortem before: Original Numeric reflection" in numeric_text
    assert "Postmortem after: Not set" in numeric_text
    assert "Correction reason: The source used a signed value." in numeric_text

    invalid_text = invalid_output.getvalue()
    assert "Effective reason: Corrected invalid reason" in invalid_text
    assert "Original Invalidation |" in invalid_text
    assert "Reason before: Original invalid reason" in invalid_text
    assert "Reason after: Corrected invalid reason" in invalid_text

    reopened = Database.open(database_path)
    with reopened.transaction() as connection:
        counts_after = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "resolution_corrections",
                "numeric_resolution_corrections",
                "invalidation_reason_corrections",
                "postmortem_completions",
            )
        )
    reopened.close()
    assert counts_after == counts_before

    reopened = Database.open(database_path)
    assert SettingsRepository(reopened).get_last_successful_backup_at() is None
    reopened.close()


def test_cli_blank_transfer_prompt_accepts_timestamped_suggestion(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "data" / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    PredictionOperations(database).create_prediction(
        "Will the suggested export destination work?",
        50,
    )
    database.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        reckonsolve.cli,
        "PredictionOperations",
        lambda database: PredictionOperations(
            database,
            FixedClock(NOW),
            local_timezone=UTC,
        ),
    )
    expected = tmp_path / "reckonsolve-export-20260825-174512.zip"

    result = run(
        ["export-csv"],
        database_path=database_path,
        stdin=StringIO("\n"),
        stdout=StringIO(),
    )

    assert result == 0
    assert expected.is_file()
    with ZipFile(expected) as archive:
        assert tuple(archive.namelist()) == EXPORT_ARCHIVE_NAMES


def test_cli_transfer_prompt_eof_cancels_without_artifact_or_setting_change(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    PredictionOperations(database).create_prediction(
        "Will transfer cancellation leave canonical data alone?",
        50,
    )
    database.close()
    errors = StringIO()

    result = run(
        ["backup"],
        database_path=database_path,
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 130
    assert errors.getvalue() == "Cancelled. No changes were made.\n"
    assert tuple(tmp_path.glob("reckonsolve-backup-*.sqlite3")) == ()
    reopened = Database.open(database_path)
    operations = PredictionOperations(reopened)
    assert len(operations.browse_predictions().predictions) == 1
    assert SettingsRepository(reopened).get_last_successful_backup_at() is None
    reopened.close()


@pytest.mark.parametrize("command", ("backup", "export-csv"))
def test_cli_transfer_rejects_canonical_database_destination_without_mutation(
    tmp_path,
    command,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    created = PredictionOperations(database).create_prediction(
        "Will a rejected transfer preserve this forecast?",
        45,
    )
    database.close()
    errors = StringIO()

    result = run(
        [command, str(database_path)],
        database_path=database_path,
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "live Reckonsolve database" in errors.getvalue()
    reopened = Database.open(database_path)
    operations = PredictionOperations(reopened)
    assert operations.get_prediction(created.prediction_id).probability_percent == 45
    assert SettingsRepository(reopened).get_last_successful_backup_at() is None
    reopened.close()


@pytest.mark.parametrize(
    ("command", "patch_target", "destination_name"),
    (
        ("backup", "reckonsolve.data.database.os.replace", "existing.sqlite3"),
        ("export-csv", "reckonsolve.data.transfer.os.replace", "existing.zip"),
    ),
)
def test_cli_transfer_failure_preserves_existing_destination(
    tmp_path,
    monkeypatch,
    command,
    patch_target,
    destination_name,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    destination = tmp_path / destination_name
    original = b"existing safe artifact"
    destination.write_bytes(original)
    database = Database.open(database_path)
    PredictionOperations(database).create_prediction(
        "Will an existing artifact survive CLI failure?",
        55,
    )
    database.close()

    def fail_replace(_source, _destination) -> None:
        raise OSError("simulated CLI destination failure")

    monkeypatch.setattr(patch_target, fail_replace)
    errors = StringIO()

    result = run(
        [command, str(destination)],
        database_path=database_path,
        stdout=StringIO(),
        stderr=errors,
    )

    assert result == 1
    assert "simulated CLI destination failure" in errors.getvalue()
    assert destination.read_bytes() == original
    assert tuple(tmp_path.glob(f".{destination.name}.*.tmp")) == ()
    reopened = Database.open(database_path)
    assert SettingsRepository(reopened).get_last_successful_backup_at() is None
    reopened.close()


def test_cli_and_desktop_connections_share_reads_and_sequential_writes(
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    desktop_database = Database.open(database_path)
    desktop_operations = PredictionOperations(desktop_database)
    created = desktop_operations.create_prediction(
        "Will independent connections preserve one canonical history?",
        30,
    )

    simultaneous_read = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=simultaneous_read,
        )
        == 0
    )
    assert "Current forecast: 30% Yes" in simultaneous_read.getvalue()

    assert (
        run(
            ["revise", str(created.prediction_id)],
            database_path=database_path,
            stdin=StringIO("70\nCLI evidence changed the forecast\n"),
            stdout=StringIO(),
        )
        == 0
    )
    refreshed = desktop_operations.get_prediction(created.prediction_id)
    assert refreshed.probability_percent == 70
    desktop_operations.add_journal_entry(
        created.prediction_id,
        "Desktop reasoning after the CLI revision",
        expected_revision_id=refreshed.current_revision_id,
        expected_metadata_version=refreshed.metadata_version,
    )
    resolved = desktop_operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=refreshed.current_revision_id,
        expected_metadata_version=refreshed.metadata_version,
    )
    assert resolved.resolution is not None
    desktop_operations.correct_binary_resolution(
        created.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Desktop corrected the terminal fact",
        postmortem="Desktop added a later Postmortem",
        correction_reason="The verified outcome was No.",
        expected_correction_id=None,
    )
    corrected_read = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=corrected_read,
        )
        == 0
    )
    assert "Effective outcome: No" in corrected_read.getvalue()
    assert "Outcome before: Yes" in corrected_read.getvalue()
    assert "Postmortem after: Desktop added a later Postmortem" in (
        corrected_read.getvalue()
    )
    desktop_database.close()

    after_restart = StringIO()
    assert (
        run(
            ["show", str(created.prediction_id)],
            database_path=database_path,
            stdout=after_restart,
        )
        == 0
    )
    rendered = after_restart.getvalue()
    assert "Current forecast: 70% Yes" in rendered
    assert "Rationale: CLI evidence changed the forecast" in rendered
    assert "Body: Desktop reasoning after the CLI revision" in rendered
    assert "Correction reason: The verified outcome was No." in rendered
