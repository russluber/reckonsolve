from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from io import StringIO

import pytest
from PySide6.QtCore import QCoreApplication

import reckonsolve.cli
from reckonsolve import main_cli, main_cli_dev
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import create_runtime, run
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome
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
    assert stable.database.schema_version == 12
    stable.close()

    development = create_runtime(identity=DEVELOPMENT_APPLICATION)
    assert development.database.path == (
        tmp_path / "Reckonsolve Dev" / "reckonsolve.sqlite3"
    )
    assert development.database.schema_version == 12
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
