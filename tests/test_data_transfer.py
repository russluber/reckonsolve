import csv
import io
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from zipfile import ZipFile

import pytest

from reckonsolve.application.errors import BackupError, CsvExportError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.settings import SettingsRepository
from reckonsolve.data.transfer import EXPORT_ARCHIVE_NAMES
from reckonsolve.domain.predictions import BinaryOutcome

NOW = datetime(2026, 8, 20, 18, 30, 45, 123456, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_backup_is_recoverable_and_records_success_across_restart(tmp_path) -> None:
    source_path = tmp_path / "source.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    database = Database.open(source_path)
    operations = PredictionOperations(database, FixedClock())
    expected = _create_complete_history(operations)
    expected_numeric = _create_complete_numeric_history(operations)
    operations.set_stale_threshold_days(21)

    result = operations.create_backup(backup_path)

    assert result.destination == backup_path.resolve()
    assert result.completed_at == NOW
    assert result.last_successful_time_recorded
    assert operations.get_data_management_status().last_successful_backup_at == NOW
    assert operations.get_prediction(expected.prediction_id) == expected
    database.close()

    reopened_source = Database.open(source_path)
    assert (
        PredictionOperations(reopened_source, FixedClock())
        .get_data_management_status()
        .last_successful_backup_at
        == NOW
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
    assert recovered_numeric.unit == "days"
    assert recovered_numeric.current_revision.lower_bound.decimal_value == Decimal(
        "0.0"
    )
    assert recovered_numeric.current_revision.confidence_percent == 80
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
    operations.create_prediction("Will the old backup survive replacement failure?", 50)
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
    created = operations.create_prediction("Will self-backup be rejected?", 50)

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
    created = operations.create_prediction("Will this backup remain usable?", 65)
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


def test_csv_bundle_preserves_relational_history_and_raw_text(tmp_path) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    expected = _create_complete_history(operations)
    expected_numeric = _create_complete_numeric_history(operations)
    export_path = tmp_path / "reckonsolve-export.zip"

    result = operations.export_csv_bundle(export_path)

    assert result.destination == export_path.resolve()
    assert result.exported_at == NOW
    assert result.csv_file_count == 12
    assert SettingsRepository(database).get_last_successful_backup_at() is None
    with ZipFile(export_path) as archive:
        assert tuple(archive.namelist()) == EXPORT_ARCHIVE_NAMES
        assert archive.testzip() is None
        predictions = _read_csv(archive, "predictions.csv")
        revisions = _read_csv(archive, "forecast_revisions.csv")
        numeric_revisions = _read_csv(archive, "numeric_forecast_revisions.csv")
        definitions = _read_csv(archive, "definition_changes.csv")
        journals = _read_csv(archive, "journal_entries.csv")
        corrections = _read_csv(archive, "journal_corrections.csv")
        reviews = _read_csv(archive, "forecast_reviews.csv")
        resolutions = _read_csv(archive, "resolutions.csv")
        numeric_resolutions = _read_csv(archive, "numeric_resolutions.csv")
        invalidations = _read_csv(archive, "invalidations.csv")
        tags = _read_csv(archive, "tags.csv")
        prediction_tags = _read_csv(archive, "prediction_tags.csv")
        readme = archive.read("README.txt").decode("utf-8")

    resolved_row = next(
        row
        for row in predictions
        if row["prediction_id"] == str(expected.prediction_id)
    )
    assert resolved_row["question"] == expected.question
    assert resolved_row["persisted_status"] == "resolved"
    assert resolved_row["background"] == "Context, with a comma\nand a new line."
    numeric_row = next(
        row
        for row in predictions
        if row["prediction_id"] == str(expected_numeric.prediction_id)
    )
    assert numeric_row["prediction_type"] == "numeric"
    assert numeric_row["numeric_unit"] == "days"
    assert numeric_row["numeric_precision"] == "1"
    resolved_revisions = [
        row for row in revisions if row["prediction_id"] == str(expected.prediction_id)
    ]
    assert [row["sequence"] for row in resolved_revisions] == ["1", "2"]
    assert [row["probability_percent"] for row in resolved_revisions] == ["40", "70"]
    assert len(definitions) == 1
    assert journals[0]["original_body"] == 'Evidence said, "wait".\nThen changed.'
    assert journals[0]["forecast_revision_id"] == resolved_revisions[0]["revision_id"]
    numeric_journal = next(
        row
        for row in journals
        if row["prediction_id"] == str(expected_numeric.prediction_id)
    )
    assert (
        corrections[0]["body"] == "Corrected evidence, still multiline.\nSecond line."
    )
    assert resolutions[0]["scoring_revision_id"] == resolved_revisions[1]["revision_id"]
    assert resolutions[0]["outcome"] == "yes"
    numeric_history = [
        row
        for row in numeric_revisions
        if row["prediction_id"] == str(expected_numeric.prediction_id)
    ]
    assert [row["sequence"] for row in numeric_history] == ["1", "2"]
    assert [row["lower_scaled"] for row in numeric_history] == ["-15", "0"]
    assert [row["median_scaled"] for row in numeric_history] == ["20", "45"]
    assert [row["upper_scaled"] for row in numeric_history] == ["70", "90"]
    assert [row["confidence_percent"] for row in numeric_history] == ["80", "80"]
    assert numeric_journal["forecast_revision_id"] == ""
    assert (
        numeric_journal["numeric_forecast_revision_id"]
        == numeric_history[0]["numeric_revision_id"]
    )
    binary_review = next(
        row for row in reviews if row["prediction_id"] == str(expected.prediction_id)
    )
    numeric_review = next(
        row
        for row in reviews
        if row["prediction_id"] == str(expected_numeric.prediction_id)
    )
    assert binary_review["forecast_revision_id"] == resolved_revisions[0]["revision_id"]
    assert binary_review["numeric_forecast_revision_id"] == ""
    assert numeric_review["forecast_revision_id"] == ""
    assert (
        numeric_review["numeric_forecast_revision_id"]
        == numeric_history[0]["numeric_revision_id"]
    )
    numeric_resolution = next(
        row
        for row in numeric_resolutions
        if row["prediction_id"] == str(expected_numeric.prediction_id)
    )
    assert numeric_resolution["actual_scaled"] == "95"
    assert (
        numeric_resolution["scoring_numeric_revision_id"]
        == numeric_history[1]["numeric_revision_id"]
    )
    assert len(invalidations) == 1
    assert {row["display_name"] for row in tags} == {"Research", "Test"}
    assert len(prediction_tags) == 3
    assert "not a complete restoration format" in readme
    assert "highest sequence is the current Binary forecast" in readme
    assert "scoring_revision_id" in readme
    assert "Format version: 2" in readme
    assert "numeric_forecast_revisions.csv" in readme
    assert "forecast_reviews.csv" in readme
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


def test_csv_export_includes_numeric_interval_data(tmp_path) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    numeric = operations.create_numeric_prediction(
        "How many days will the reply take?",
        "days",
        0,
        1,
        3,
        7,
        80,
    )
    destination = tmp_path / "numeric-export.zip"

    result = operations.export_csv_bundle(destination)

    assert result.csv_file_count == 12
    with ZipFile(destination) as archive:
        rows = _read_csv(archive, "numeric_forecast_revisions.csv")
    assert rows == [
        {
            "numeric_revision_id": str(numeric.current_revision.revision_id),
            "prediction_id": str(numeric.prediction_id),
            "sequence": "1",
            "lower_scaled": "1",
            "median_scaled": "3",
            "upper_scaled": "7",
            "confidence_percent": "80",
            "rationale": "",
            "created_at_utc": "2026-08-20T18:30:45.123456Z",
        }
    ]
    database.close()


def test_failed_csv_export_preserves_existing_destination_and_source(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "source.sqlite3")
    operations = PredictionOperations(database, FixedClock())
    created = operations.create_prediction("Will export failure preserve data?", 35)
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
    assert operations.get_prediction(created.prediction_id).question == created.question
    database.close()


def test_csv_export_rejects_the_live_database_without_mutation(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock())
    created = operations.create_prediction("Will live data remain canonical?", 55)

    with pytest.raises(CsvExportError, match="cannot be an export file"):
        operations.export_csv_bundle(path)

    assert operations.get_prediction(created.prediction_id).question == created.question
    database.close()


def _create_complete_history(operations: PredictionOperations):
    created = operations.create_prediction(
        "Will the full, quoted history survive?",
        40,
        rationale="Initial rationale",
        background="Context, with a comma\nand a new line.",
        resolution_criteria="A published result counts.",
        forecast_deadline=date(2026, 8, 20),
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
        forecast_deadline=created.forecast_deadline,
        expected_resolution=created.expected_resolution,
        tags=("Research",),
        expected_metadata_version=revised.metadata_version,
        confirm_meaning_change=True,
    )
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Verified, with a source.",
        postmortem="The revision was warranted.",
        expected_revision_id=edited.current_revision_id,
        expected_metadata_version=edited.metadata_version,
    )
    invalid = operations.create_prediction(
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
    created = operations.create_numeric_prediction(
        "How many days will the type-aware export take?",
        "days",
        1,
        "-1.5",
        "2.0",
        "7.0",
        80,
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
    revised = operations.revise_numeric_forecast(
        created.prediction_id,
        "0.0",
        "4.5",
        "9.0",
        80,
        rationale="New evidence shifted the interval upward.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    return operations.resolve_numeric_prediction(
        revised.prediction_id,
        "9.5",
        resolution_notes="Observed in the final response.",
        postmortem="The upper tail was too narrow.",
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )


def _read_csv(archive: ZipFile, filename: str) -> list[dict[str, str]]:
    text = archive.read(filename).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text, newline="")))
