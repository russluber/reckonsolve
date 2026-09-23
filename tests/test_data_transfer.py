import csv
import io
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zipfile import ZipFile

import pytest
from supported_fixtures import create_binary, create_numeric

from reckonsolve.application.errors import BackupError, CsvExportError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.settings import SettingsRepository
from reckonsolve.data.transfer import EXPORT_ARCHIVE_NAMES
from reckonsolve.domain.browser import ArchiveQuery
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode

NOW = datetime(2026, 8, 20, 18, 30, 45, 123456, tzinfo=UTC)


class FixedClock:
    def __init__(self):
        self.instant = NOW

    def now(self) -> datetime:
        self.instant += timedelta(seconds=1)
        return self.instant


def test_backup_is_recoverable_and_records_success_across_restart(tmp_path) -> None:
    source_path = tmp_path / "source.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    database = Database.open(source_path)
    operations = PredictionOperations(database, FixedClock())
    expected = _create_complete_history(operations)
    expected_numeric = _create_complete_numeric_history(operations)
    operations.set_stale_threshold_days(21)
    operations.create_saved_view(
        "Recovery work",
        SavedViewConfiguration(
            search_text="history",
            match_mode=SearchMatchMode.ALL,
            include_superseded=False,
            archive_query=ArchiveQuery(tags=("Research",)),
        ),
    )

    result = operations.create_backup(backup_path)

    assert result.destination == backup_path.resolve()
    assert result.completed_at >= NOW
    assert result.last_successful_time_recorded
    assert (
        operations.get_data_management_status().last_successful_backup_at
        == result.completed_at
    )
    assert operations.get_prediction(expected.prediction_id) == expected
    database.close()

    reopened_source = Database.open(source_path)
    assert (
        PredictionOperations(reopened_source, FixedClock())
        .get_data_management_status()
        .last_successful_backup_at
        == result.completed_at
    )
    reopened_source.close()

    recovered = Database.open(backup_path)
    recovered_operations = PredictionOperations(recovered, FixedClock())
    recovered_prediction = recovered_operations.get_prediction(expected.prediction_id)
    recovered_numeric = recovered_operations.get_numeric_prediction(
        expected_numeric.prediction_id
    )
    assert recovered_prediction.question == expected.question
    assert recovered_prediction.probability_percent == expected.probability_percent
    assert recovered_prediction.resolution == expected.resolution
    assert (
        len(recovered_operations.list_forecast_revisions(expected.prediction_id)) == 2
    )
    assert len(recovered_operations.list_timeline(expected.prediction_id)) == 4
    assert (
        len(recovered_operations.list_definition_changes(expected.prediction_id)) == 1
    )
    assert recovered_operations.get_stale_threshold_days() == 21
    assert [view.name for view in recovered_operations.list_saved_views()] == [
        "Recovery work"
    ]
    assert recovered_numeric.unit == "days"
    assert recovered_numeric.current_revision.quantiles.q05.decimal_value == Decimal(
        "0.0"
    )
    assert (
        recovered_numeric.current_revision.quantiles
        == expected_numeric.current_revision.quantiles
    )
    assert recovered_numeric.resolution is not None
    assert recovered_numeric.resolution.actual_value.decimal_value == Decimal("9.5")
    assert (
        len(
            recovered_operations.list_numeric_forecast_revisions(
                expected_numeric.prediction_id
            )
        )
        == 2
    )
    assert (
        len(recovered_operations.list_numeric_timeline(expected_numeric.prediction_id))
        == 4
    )
    recovered.close()


def test_failed_backup_preserves_existing_destination_and_success_time(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    create_binary(operations, "Will the old backup survive replacement failure?", 50)
    destination = tmp_path / "existing.sqlite3"
    original = b"previous usable backup"
    destination.write_bytes(original)

    def fail_replace(_source, _destination) -> None:
        raise OSError("simulated destination failure")

    monkeypatch.setattr("reckonsolve.data.database.os.replace", fail_replace)

    with pytest.raises(BackupError, match="simulated destination failure"):
        operations.create_backup(destination)

    assert destination.read_bytes() == original
    assert SettingsRepository(database).get_last_successful_backup_at() is None
    assert tuple(tmp_path.glob(".existing.sqlite3.*.tmp")) == ()
    database.close()


def test_backup_rejects_the_live_database_without_mutation(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock())
    created = create_binary(operations, "Will self-backup be rejected?", 50)

    with pytest.raises(BackupError, match="cannot be its own backup"):
        operations.create_backup(path)

    assert operations.get_prediction(created.prediction_id).question == created.question
    assert SettingsRepository(database).get_last_successful_backup_at() is None
    database.close()


def test_backup_remains_usable_if_recording_its_success_time_fails(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    created = create_binary(operations, "Will this backup remain usable?", 65)
    destination = tmp_path / "usable.sqlite3"

    def fail_to_record(_value) -> None:
        raise sqlite3.OperationalError("simulated settings write failure")

    monkeypatch.setattr(
        operations._settings_repository,
        "set_last_successful_backup_at",
        fail_to_record,
    )

    result = operations.create_backup(destination)

    assert not result.last_successful_time_recorded
    assert SettingsRepository(database).get_last_successful_backup_at() is None
    database.close()
    recovered = Database.open(destination)
    assert (
        PredictionOperations(recovered, FixedClock())
        .get_prediction(created.prediction_id)
        .question
        == created.question
    )
    recovered.close()


def test_current_history_refuses_incomplete_csv_without_losing_backup(tmp_path) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    binary = _create_complete_history(operations)
    numeric = _create_complete_numeric_history(operations)
    destination = tmp_path / "export.zip"
    source = tmp_path / "source.sqlite3"
    before = source.read_bytes()
    with pytest.raises(CsvExportError, match="format"):
        operations.export_csv_bundle(destination)
    assert not destination.exists()
    assert source.read_bytes() == before
    assert operations.get_prediction(binary.prediction_id) == binary
    assert operations.get_numeric_prediction(numeric.prediction_id) == numeric
    database.close()


def test_empty_csv_bundle_has_every_header_and_no_data_rows(tmp_path) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    export_path = tmp_path / "empty.zip"

    operations.export_csv_bundle(export_path)

    with ZipFile(export_path) as archive:
        for filename in EXPORT_ARCHIVE_NAMES[:-1]:
            contents = _read_csv(archive, filename)
            assert contents == []
    database.close()


def test_numeric_csv_refusal_preserves_existing_destination(tmp_path) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    numeric = create_numeric(
        operations,
        "Numeric export?",
        "days",
        1,
        {5: "-1.5", 25: "0.0", 50: "2.0", 75: "4.0", 95: "7.0"},
    )
    destination = tmp_path / "export.zip"
    destination.write_bytes(b"previous export")
    with pytest.raises(CsvExportError, match="format"):
        operations.export_csv_bundle(destination)
    assert destination.read_bytes() == b"previous export"
    assert operations.get_numeric_prediction(numeric.prediction_id) == numeric
    database.close()


def test_failed_csv_export_preserves_existing_destination_and_source(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    destination = tmp_path / "existing.zip"
    original = b"previous export"
    destination.write_bytes(original)

    def fail_replace(_source, _destination) -> None:
        raise OSError("simulated ZIP destination failure")

    monkeypatch.setattr("reckonsolve.data.transfer.os.replace", fail_replace)

    with pytest.raises(CsvExportError, match="simulated ZIP destination failure"):
        operations.export_csv_bundle(destination)

    assert destination.read_bytes() == original
    assert tuple(tmp_path.glob(".existing.zip.*.tmp")) == ()
    assert operations.browse_predictions().predictions == ()
    database.close()


def test_csv_export_rejects_the_live_database_without_mutation(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock())
    created = create_binary(operations, "Will live data remain canonical?", 55)

    with pytest.raises(CsvExportError, match="format"):
        operations.export_csv_bundle(path)

    assert operations.get_prediction(created.prediction_id).question == created.question
    database.close()


def test_backup_preserves_both_terminal_correction_chains_and_postmortem_completion(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    binary = _create_complete_history(operations)
    numeric = _create_complete_numeric_history(operations)
    operations.correct_binary_resolution(
        binary.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Corrected source",
        postmortem=None,
        correction_reason="Corrected outcome",
        expected_correction_id=None,
    )
    operations.correct_numeric_resolution(
        numeric.prediction_id,
        "10.5",
        resolution_notes="Corrected numeric source",
        postmortem=None,
        correction_reason="Corrected actual",
        expected_correction_id=None,
    )
    operations.record_postmortem_skip(
        binary.prediction_id,
        expected_correction_id=operations.get_binary_resolution_history(
            binary.prediction_id
        ).current_correction_id,
    )
    operations.record_postmortem_skip(
        numeric.prediction_id,
        expected_correction_id=operations.get_numeric_resolution_history(
            numeric.prediction_id
        ).current_correction_id,
    )
    expected_binary = operations.get_binary_resolution_history(binary.prediction_id)
    expected_numeric = operations.get_numeric_resolution_history(numeric.prediction_id)
    destination = tmp_path / "recovery.sqlite3"
    operations.create_backup(destination)
    database.close()
    recovered = Database.open(destination)
    ops = PredictionOperations(recovered, FixedClock())
    assert ops.get_binary_resolution_history(binary.prediction_id) == expected_binary
    assert ops.get_numeric_resolution_history(numeric.prediction_id) == expected_numeric
    recovered.check_search_index()
    recovered.close()


def _create_complete_history(operations: PredictionOperations):
    created = create_binary(
        operations,
        "Will the full, quoted history survive?",
        40,
        rationale="Initial rationale",
        background="Context, with a comma\nand a new line.",
        resolution_criteria="A published result counts.",
        forecast_deadline=datetime(2026, 8, 21, tzinfo=UTC),
        expected_resolution=date(2026, 8, 21),
        tags=("Research",),
    )
    journal = operations.add_journal_entry(
        created.prediction_id,
        'Evidence said, "wait".\nThen changed.',
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.add_forecast_review(
        created.prediction_id,
        note="I deliberately kept the initial probability.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.correct_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "Corrected evidence, still multiline.\nSecond line.",
        expected_correction_id=None,
    )
    revised = operations.revise_forecast(
        created.prediction_id,
        70,
        rationale="Stronger evidence arrived.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    edited = operations.update_metadata(
        created.prediction_id,
        question="Will the full, quoted history survive export?",
        background=created.background,
        resolution_criteria=created.resolution_criteria,
        forecast_deadline=None,
        expected_resolution=created.expected_resolution,
        tags=("Research",),
        expected_metadata_version=revised.metadata_version,
        confirm_meaning_change=True,
    )
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        resolution_notes="Verified, with a source.",
        postmortem="The revision was warranted.",
        expected_revision_id=edited.current_revision_id,
        expected_metadata_version=edited.metadata_version,
    )
    invalid = create_binary(
        operations,
        "Will an invalid record remain exported?",
        10,
        tags=("Test",),
    )
    operations.invalidate_prediction(
        invalid.prediction_id,
        reason="The event was cancelled.",
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    return resolved


def _create_complete_numeric_history(operations: PredictionOperations):
    created = create_numeric(
        operations,
        "How many days will the type-aware export take?",
        "days",
        1,
        {5: "-1.5", 25: "0.0", 50: "2.0", 75: "4.0", 95: "7.0"},
        rationale="Initial numeric rationale.",
        tags=("Research",),
    )
    journal = operations.add_numeric_journal_entry(
        created.prediction_id,
        "The estimate remains plausible.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations.correct_numeric_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "The estimate remains plausible after checking the evidence.",
        expected_correction_id=None,
    )
    operations.add_numeric_forecast_review(
        created.prediction_id,
        note="Deliberately retained the first interval.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    revised = operations.revise_quantile_forecast(
        created.prediction_id,
        {5: "0.0", 25: "2.0", 50: "4.5", 75: "6.0", 95: "9.0"},
        rationale="New evidence shifted the interval upward.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    return operations.resolve_numeric_prediction(
        revised.prediction_id,
        "9.5",
        use_recorded_time=True,
        resolution_notes="Observed in the final response.",
        postmortem="The upper tail was too narrow.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )


def _read_csv(archive: ZipFile, filename: str) -> list[dict[str, str]]:
    text = archive.read(filename).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text, newline="")))
