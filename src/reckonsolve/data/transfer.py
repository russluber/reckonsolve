"""Consistent backup and documented relational CSV export persistence."""

from __future__ import annotations

import csv
import io
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from reckonsolve.clock import format_utc

from .database import Database


@dataclass(frozen=True, slots=True)
class _CsvTable:
    filename: str
    columns: tuple[str, ...]
    query: str


@dataclass(frozen=True, slots=True)
class _CsvContents:
    table: _CsvTable
    rows: tuple[tuple[object, ...], ...]


_CSV_TABLES = (
    _CsvTable(
        "predictions.csv",
        (
            "prediction_id",
            "question",
            "prediction_type",
            "persisted_status",
            "created_at_utc",
            "updated_at_utc",
            "metadata_version",
            "background",
            "resolution_criteria",
            "forecast_deadline",
            "expected_resolution",
            "numeric_unit",
            "numeric_precision",
        ),
        """
        SELECT
            id AS prediction_id,
            question,
            prediction_type,
            status AS persisted_status,
            created_at AS created_at_utc,
            updated_at AS updated_at_utc,
            metadata_version,
            background,
            resolution_criteria,
            forecast_deadline,
            expected_resolution,
            numeric_unit,
            numeric_precision
        FROM predictions
        ORDER BY id
        """,
    ),
    _CsvTable(
        "forecast_revisions.csv",
        (
            "revision_id",
            "prediction_id",
            "sequence",
            "probability_percent",
            "rationale",
            "created_at_utc",
        ),
        """
        SELECT
            id AS revision_id,
            prediction_id,
            sequence,
            probability_percent,
            rationale,
            created_at AS created_at_utc
        FROM forecast_revisions
        ORDER BY prediction_id, sequence, id
        """,
    ),
    _CsvTable(
        "numeric_forecast_revisions.csv",
        (
            "numeric_revision_id",
            "prediction_id",
            "sequence",
            "lower_scaled",
            "median_scaled",
            "upper_scaled",
            "confidence_percent",
            "rationale",
            "created_at_utc",
        ),
        """
        SELECT
            id AS numeric_revision_id,
            prediction_id,
            sequence,
            lower_scaled,
            median_scaled,
            upper_scaled,
            confidence_percent,
            rationale,
            created_at AS created_at_utc
        FROM numeric_forecast_revisions
        ORDER BY prediction_id, sequence, id
        """,
    ),
    _CsvTable(
        "definition_changes.csv",
        (
            "definition_change_id",
            "prediction_id",
            "changed_at_utc",
            "old_question",
            "new_question",
            "old_resolution_criteria",
            "new_resolution_criteria",
            "old_forecast_deadline",
            "new_forecast_deadline",
        ),
        """
        SELECT
            id AS definition_change_id,
            prediction_id,
            changed_at AS changed_at_utc,
            old_question,
            new_question,
            old_resolution_criteria,
            new_resolution_criteria,
            old_forecast_deadline,
            new_forecast_deadline
        FROM prediction_definition_changes
        ORDER BY prediction_id, id
        """,
    ),
    _CsvTable(
        "journal_entries.csv",
        (
            "journal_entry_id",
            "prediction_id",
            "forecast_revision_id",
            "numeric_forecast_revision_id",
            "original_body",
            "created_at_utc",
        ),
        """
        SELECT
            id AS journal_entry_id,
            prediction_id,
            forecast_revision_id,
            numeric_forecast_revision_id,
            body AS original_body,
            created_at AS created_at_utc
        FROM journal_entries
        ORDER BY prediction_id, id
        """,
    ),
    _CsvTable(
        "journal_corrections.csv",
        (
            "journal_correction_id",
            "prediction_id",
            "journal_entry_id",
            "sequence",
            "body",
            "corrected_at_utc",
        ),
        """
        SELECT
            id AS journal_correction_id,
            prediction_id,
            journal_entry_id,
            sequence,
            body,
            corrected_at AS corrected_at_utc
        FROM journal_entry_corrections
        ORDER BY journal_entry_id, sequence, id
        """,
    ),
    _CsvTable(
        "forecast_reviews.csv",
        (
            "forecast_review_id",
            "prediction_id",
            "forecast_revision_id",
            "numeric_forecast_revision_id",
            "created_at_utc",
            "note",
        ),
        """
        SELECT
            id AS forecast_review_id,
            prediction_id,
            forecast_revision_id,
            numeric_forecast_revision_id,
            created_at AS created_at_utc,
            note
        FROM forecast_reviews
        ORDER BY prediction_id, created_at, id
        """,
    ),
    _CsvTable(
        "resolutions.csv",
        (
            "resolution_id",
            "prediction_id",
            "outcome",
            "resolved_at_utc",
            "scoring_revision_id",
            "resolution_notes",
            "postmortem",
        ),
        """
        SELECT
            id AS resolution_id,
            prediction_id,
            outcome,
            resolved_at AS resolved_at_utc,
            scoring_revision_id,
            resolution_notes,
            postmortem
        FROM resolutions
        ORDER BY id
        """,
    ),
    _CsvTable(
        "numeric_resolutions.csv",
        (
            "numeric_resolution_id",
            "prediction_id",
            "actual_scaled",
            "resolved_at_utc",
            "scoring_numeric_revision_id",
            "resolution_notes",
            "postmortem",
        ),
        """
        SELECT
            id AS numeric_resolution_id,
            prediction_id,
            actual_scaled,
            resolved_at AS resolved_at_utc,
            scoring_revision_id AS scoring_numeric_revision_id,
            resolution_notes,
            postmortem
        FROM numeric_resolutions
        ORDER BY id
        """,
    ),
    _CsvTable(
        "invalidations.csv",
        (
            "invalidation_id",
            "prediction_id",
            "invalidated_at_utc",
            "reason",
        ),
        """
        SELECT
            id AS invalidation_id,
            prediction_id,
            invalidated_at AS invalidated_at_utc,
            reason
        FROM prediction_invalidations
        ORDER BY id
        """,
    ),
    _CsvTable(
        "tags.csv",
        ("tag_id", "display_name", "normalized_name"),
        """
        SELECT id AS tag_id, display_name, normalized_name
        FROM tags
        ORDER BY normalized_name, id
        """,
    ),
    _CsvTable(
        "prediction_tags.csv",
        ("prediction_id", "tag_id"),
        """
        SELECT prediction_id, tag_id
        FROM prediction_tags
        ORDER BY prediction_id, tag_id
        """,
    ),
)

CSV_FILE_NAMES = tuple(table.filename for table in _CSV_TABLES)
EXPORT_ARCHIVE_NAMES = (*CSV_FILE_NAMES, "README.txt")


class DataTransferRepository:
    """Create recovery and portable artifacts from canonical SQLite data."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def database_path(self) -> Path:
        return self._database.path

    def create_backup(self, destination: Path) -> Path:
        """Create one verified SQLite recovery snapshot."""

        return self._database.backup_to(destination)

    def export_csv_bundle(
        self,
        destination: Path,
        *,
        exported_at: datetime,
    ) -> tuple[Path, int]:
        """Create one verified ZIP from a consistent relational read."""

        contents = self._read_csv_contents()
        destination_path = _validated_destination(
            destination,
            source=self._database.path,
        )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination_path.name}.",
            suffix=".tmp",
            dir=destination_path.parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        installed = False
        try:
            with ZipFile(
                temporary_path,
                mode="w",
                compression=ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for item in contents:
                    _write_archive_member(
                        archive,
                        item.table.filename,
                        _render_csv(item),
                        exported_at,
                    )
                _write_archive_member(
                    archive,
                    "README.txt",
                    _export_readme(exported_at).encode("utf-8"),
                    exported_at,
                )
            _validate_export_archive(temporary_path)
            os.replace(temporary_path, destination_path)
            installed = True
            return destination_path, len(contents)
        finally:
            if not installed and temporary_path.exists():
                temporary_path.unlink()

    def _read_csv_contents(self) -> tuple[_CsvContents, ...]:
        with self._database.transaction() as connection:
            return tuple(
                _CsvContents(
                    table=table,
                    rows=tuple(
                        tuple(row[column] for column in table.columns)
                        for row in connection.execute(table.query).fetchall()
                    ),
                )
                for table in _CSV_TABLES
            )


def _validated_destination(destination: Path, *, source: Path) -> Path:
    destination_path = Path(destination)
    parent = destination_path.parent.resolve(strict=True)
    if not parent.is_dir():
        raise NotADirectoryError(f"Export destination is not a folder: {parent}")
    resolved_destination = (parent / destination_path.name).resolve(strict=False)
    resolved_source = source.resolve(strict=True)
    if resolved_destination == resolved_source or (
        resolved_destination.exists()
        and os.path.samefile(resolved_destination, resolved_source)
    ):
        raise ValueError("The live Reckonsolve database cannot be an export file.")
    return resolved_destination


def _render_csv(contents: _CsvContents) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, dialect="excel", quoting=csv.QUOTE_ALL)
    writer.writerow(contents.table.columns)
    writer.writerows(contents.rows)
    return stream.getvalue().encode("utf-8-sig")


def _write_archive_member(
    archive: ZipFile,
    filename: str,
    contents: bytes,
    exported_at: datetime,
) -> None:
    instant = exported_at.astimezone(UTC)
    date_time = (
        (instant.year, instant.month, instant.day, instant.hour, instant.minute, 0)
        if 1980 <= instant.year <= 2107
        else (1980, 1, 1, 0, 0, 0)
    )
    info = ZipInfo(
        filename,
        date_time=date_time,
    )
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, contents)


def _validate_export_archive(path: Path) -> None:
    with ZipFile(path, mode="r") as archive:
        if tuple(archive.namelist()) != EXPORT_ARCHIVE_NAMES:
            raise BadZipFile("The export bundle has unexpected contents.")
        invalid_member = archive.testzip()
        if invalid_member is not None:
            raise BadZipFile(f"The export member {invalid_member} is corrupt.")


def _export_readme(exported_at: datetime) -> str:
    return f"""Reckonsolve CSV Export Bundle
==============================

Format version: 2
Exported at (UTC): {format_utc(exported_at)}

Purpose
-------
This ZIP is a portable analytical representation of Reckonsolve prediction data.
It is not a complete restoration format. Use a Reckonsolve .sqlite3 backup for
application recovery. Application settings are intentionally excluded.

CSV conventions
---------------
- Encoding: UTF-8 with a byte-order mark.
- Delimiter: comma. Every field is quoted. Rows use CRLF line endings.
- Blank optional fields represent SQL NULL. Required text fields are never blank.
- Columns ending in _utc contain canonical RFC 3339 UTC instants ending in Z.
- Forecast Deadline and Expected Resolution are ISO YYYY-MM-DD calendar dates.
- Free-text values are preserved verbatim. When opening in spreadsheet software,
  import free-text columns as text if values beginning with =, +, -, or @ should
  never be interpreted as formulas.

Files and relationships
-----------------------
predictions.csv
  One current Prediction row. persisted_status is open, resolved, or invalid;
  Locked remains derived from an open row and its inclusive forecast_deadline.
  prediction_type is binary or numeric. numeric_unit and numeric_precision are
  blank for Binary rows and define the enduring Numeric quantity. Numeric scaled
  values in the related files equal the displayed value multiplied by
  10^numeric_precision; do not parse them as binary floating-point values.

forecast_revisions.csv
  Every immutable ForecastRevision. prediction_id joins predictions.csv. The
  highest sequence is the current Binary forecast; probability_percent remains
  0-100. It contains only Binary Prediction rows.

numeric_forecast_revisions.csv
  Every immutable Numeric ForecastRevision. prediction_id joins a Numeric row in
  predictions.csv. lower_scaled, median_scaled, and upper_scaled use that
  Prediction's numeric_precision; the highest sequence is the current Numeric
  interval. confidence_percent is a whole percentage from 1 through 99.

definition_changes.csv
  Every immutable protected-definition snapshot. prediction_id joins
  predictions.csv; old/new fields preserve Question, Resolution Criteria, and
  Forecast Deadline context.

journal_entries.csv
  Every original Journal entry. prediction_id joins predictions.csv and
  exactly one of forecast_revision_id or numeric_forecast_revision_id identifies
  the type-appropriate forecast current when it was written.

journal_corrections.csv
  Every immutable Journal body correction. journal_entry_id joins
  journal_entries.csv. The highest sequence is the current displayed body; if
  there is no correction, original_body remains current.

resolutions.csv
  One immutable Yes/No outcome for each resolved Binary Prediction. prediction_id joins
  predictions.csv and scoring_revision_id identifies the exact ForecastRevision
  used for Brier and calibration scoring.

numeric_resolutions.csv
  One immutable outcome for each resolved Numeric Prediction. prediction_id joins
  predictions.csv and scoring_numeric_revision_id identifies the exact Numeric
  ForecastRevision used for Numeric scoring. actual_scaled uses the parent
  Prediction's numeric_precision.

forecast_reviews.csv
  Every immutable deliberate reconsideration that retained the current forecast.
  prediction_id joins predictions.csv and exactly one of forecast_revision_id or
  numeric_forecast_revision_id identifies the type-appropriate reviewed forecast.
  Reviews are not ForecastRevisions and do not add scoring observations.

invalidations.csv
  One immutable invalidation record for each Invalid Prediction. Invalid
  Predictions remain historical but are excluded from scoring.

tags.csv
  Reusable tag identities. display_name is the retained user-facing spelling;
  normalized_name is the case-folded identity used for matching.

prediction_tags.csv
  Many-to-many links joining prediction_id to tag_id.
"""
