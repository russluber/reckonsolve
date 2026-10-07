"""Format-5 portability preserves original and effective One-Shot history."""

import csv
import io
import sqlite3
from dataclasses import replace
from datetime import UTC, timedelta
from zipfile import ZipFile

import pytest
from supported_fixtures import create_binary, create_numeric
from test_one_shot_persistence import Clock, canonical_snapshot, request

from reckonsolve.application.errors import CsvExportError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli_creation import PromptSession
from reckonsolve.cli_transfer import export_csv_interactively
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.transfer import EXPORT_ARCHIVE_NAMES
from reckonsolve.domain.predictions import BinaryOutcome, FixedPrecisionValue
from reckonsolve.domain.quantiles import FiveQuantiles


def rows(archive, name):
    return list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig"))))


def test_mixed_export_replays_later_answers_and_corrected_exact_values(tmp_path):
    database = Database.open(tmp_path / "source.sqlite3")
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)
    try:
        create_binary(ops, "Deadline Binary", 50)
        create_numeric(
            ops, "Deadline Numeric", "m", 2, {5: -2, 25: -1, 50: 0, 75: 1, 95: 2}
        )
        binary = ops.one_shots.create(request(answered=False))
        clock.instant += timedelta(minutes=1)
        binary = ops.one_shots.correct(
            binary,
            replace(binary.record.effective, probability_percent=25),
            note="Copied 25%",
        )
        clock.instant += timedelta(minutes=1)
        binary = ops.one_shots.add_answer(
            binary,
            replace(
                binary.record.effective,
                answer=BinaryOutcome.YES,
                resolution_notes='=Evidence, "tree"\nSecond line',
            ),
        )
        # The last correction still has no answer: export must attach the later original answer.
        numeric = ops.one_shots.create(request(numeric=True))
        clock.instant += timedelta(minutes=1)
        huge = 9007199254740993
        numeric = ops.one_shots.correct(
            numeric,
            replace(
                numeric.record.effective,
                quantiles=FiveQuantiles.from_values(
                    {q: str(huge) for q in (5, 25, 50, 75, 95)}, 2
                ),
                answer=FixedPrecisionValue(huge * 100, 2),
                forecast_reported=None,
                postmortem="Measured twice",
            ),
            note="Transcription corrected",
        )
        waiting = ops.one_shots.create(request(answered=False))
        invalid = ops.one_shots.create(request(numeric=True, answered=False))
        ops.one_shots.invalidate(invalid, reason="Ambiguous target")
        before = canonical_snapshot(database._require_connection())
        trace = []
        database._require_connection().set_trace_callback(trace.append)
        destination = tmp_path / "mixed.zip"
        ops.export_csv_bundle(destination)
        database._require_connection().set_trace_callback(None)
        assert sum(sql == "BEGIN IMMEDIATE" for sql in trace) == 1
        assert canonical_snapshot(database._require_connection()) == before
        with ZipFile(destination) as archive:
            assert tuple(archive.namelist()) == EXPORT_ARCHIVE_NAMES
            readme = archive.read("README.txt").decode()
            assert "Format version: 5" in readme and "NOT UTC instants" in readme
            parents = rows(archive, "predictions.csv")
            assert len({p["forecast_model"] for p in parents}) == 4
            shots = [p for p in parents if "one-shot" in p["forecast_model"]]
            assert len(shots) == 4 and all(
                not p["forecast_deadline_at_utc"] for p in shots
            )
            original = {
                int(r["prediction_id"]): r
                for r in rows(archive, "one_shot_original_facts.csv")
            }
            effective = {
                int(r["prediction_id"]): r
                for r in rows(archive, "one_shot_effective_facts.csv")
            }
            corrections = rows(archive, "one_shot_corrections.csv")
            b, n = binary.prediction_id, numeric.prediction_id
            assert original[b]["probability_percent"] == "80"
            assert effective[b]["probability_percent"] == "25"
            assert effective[b]["outcome"] == "yes"
            assert corrections[0]["old_outcome"] == corrections[0]["new_outcome"] == ""
            assert effective[b]["resolution_notes"] == '=Evidence, "tree"\nSecond line'
            assert original[b]["forecast_wall"] == "2026-09-26T12:05"
            assert original[b]["forecast_offset"] == "-420"
            assert original[b]["forecast_approximate"] == "1"
            assert (
                original[b]["answer_recorded_at_utc"] > original[b]["recorded_at_utc"]
            )
            assert (
                effective[n]["q50_scaled"]
                == effective[n]["actual_scaled"]
                == str(huge * 100)
            )
            assert original[n]["forecast_wall"] and effective[n]["forecast_wall"] == ""
            assert corrections[1]["old_q50_scaled"] == original[n]["q50_scaled"]
            assert corrections[1]["new_actual_scaled"] == effective[n]["actual_scaled"]
            for identifier in (waiting.prediction_id, invalid.prediction_id):
                assert effective[identifier]["answer_recorded_at_utc"] == ""
                assert (
                    effective[identifier]["outcome"]
                    == effective[identifier]["actual_scaled"]
                    == ""
                )
            assert not rows(archive, "forecast_reviews.csv")
        expected = ops.get_one_shot_analytics()
        backup = tmp_path / "backup.sqlite3"
        ops.create_backup(backup)
    finally:
        database.close()
    for path in (tmp_path / "source.sqlite3", backup):
        recovered = Database.open(path)
        try:
            again = PredictionOperations(recovered, clock, UTC)
            assert again.get_one_shot_analytics() == expected
            assert again.one_shots.get(binary.prediction_id).record == binary.record
            recovered.check_search_index()
        finally:
            recovered.close()


def test_cli_export_uses_same_format_five_bundle(tmp_path):
    database = Database.open(tmp_path / "cli.sqlite3")
    try:
        ops = PredictionOperations(database, Clock(), UTC)
        ops.one_shots.create(request())
        output, errors = io.StringIO(), io.StringIO()
        session = PromptSession(io.StringIO(), output, errors)
        export_csv_interactively(ops, session, tmp_path / "cli.zip")
        assert "format version 5" in output.getvalue() and not errors.getvalue()
        with ZipFile(tmp_path / "cli.zip") as archive:
            assert len(rows(archive, "one_shot_effective_facts.csv")) == 1
    finally:
        database.close()


@pytest.mark.parametrize("failure", ["write", "validation", "contract"])
def test_failed_one_shot_export_keeps_previous_artifact_and_source(
    tmp_path, monkeypatch, failure
):
    database = Database.open(tmp_path / "source.sqlite3")
    ops = PredictionOperations(database, Clock(), UTC)
    shot = ops.one_shots.create(request())
    destination = tmp_path / "existing.zip"
    destination.write_bytes(b"previous artifact")
    try:
        if failure == "contract":
            with sqlite3.connect(database.path) as connection:
                connection.execute(
                    "DROP TRIGGER prediction_forecast_contracts_are_immutable"
                )
                connection.execute("PRAGMA ignore_check_constraints = ON")
                connection.execute(
                    "UPDATE prediction_forecast_contracts SET scoring_contract='unknown' WHERE prediction_id=?",
                    (shot.prediction_id,),
                )
        else:

            def fail(*args, **kwargs):
                raise OSError("export interrupted")

            monkeypatch.setattr(
                "reckonsolve.data.transfer."
                + (
                    "_write_archive_member"
                    if failure == "write"
                    else "_validate_export_archive"
                ),
                fail,
            )
        before = database.path.read_bytes()
        with pytest.raises((CsvExportError, ForecastContractIntegrityError)):
            ops.export_csv_bundle(destination)
        assert destination.read_bytes() == b"previous artifact"
        assert database.path.read_bytes() == before
        assert not tuple(tmp_path.glob(".existing.zip.*.tmp"))
    finally:
        database.close()
