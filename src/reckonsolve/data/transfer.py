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
            "expected_resolution",
            "numeric_unit",
            "numeric_precision",
            "forecast_model",
            "scoring_contract",
            "forecast_deadline_at_utc",
        ),
        """
        SELECT
            predictions.id AS prediction_id,
            question,
            prediction_type,
            status AS persisted_status,
            created_at AS created_at_utc,
            updated_at AS updated_at_utc,
            metadata_version,
            background,
            resolution_criteria,
            expected_resolution,
            numeric_unit,
            numeric_precision,
            contract.forecast_model,
            contract.scoring_contract,
            contract.forecast_deadline_at AS forecast_deadline_at_utc
        FROM predictions AS predictions
        JOIN prediction_forecast_contracts AS contract
            ON contract.prediction_id = predictions.id
        ORDER BY predictions.id
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
        "definition_changes.csv",
        (
            "definition_change_id",
            "prediction_id",
            "changed_at_utc",
            "old_question",
            "new_question",
            "old_resolution_criteria",
            "new_resolution_criteria",
        ),
        """
        SELECT
            id AS definition_change_id,
            prediction_id,
            changed_at AS changed_at_utc,
            old_question,
            new_question,
            old_resolution_criteria,
            new_resolution_criteria
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
            "quantile_revision_id",
            "original_body",
            "created_at_utc",
        ),
        """
        SELECT
            id AS journal_entry_id,
            prediction_id,
            forecast_revision_id,
            quantile_revision_id,
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
            "quantile_revision_id",
            "created_at_utc",
            "note",
        ),
        """
        SELECT
            id AS forecast_review_id,
            prediction_id,
            forecast_revision_id,
            quantile_revision_id,
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
            "effective_resolution_at_utc",
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
            effective_resolution_at AS effective_resolution_at_utc,
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
            "effective_resolution_at_utc",
            "quantile_revision_id",
            "resolution_notes",
            "postmortem",
        ),
        """
        SELECT
            id AS numeric_resolution_id,
            prediction_id,
            actual_scaled,
            resolved_at AS resolved_at_utc,
            effective_resolution_at AS effective_resolution_at_utc,
            quantile_revision_id,
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
    _CsvTable(
        "invalidation_reason_corrections.csv",
        (
            "invalidation_correction_id",
            "prediction_id",
            "invalidation_id",
            "sequence",
            "old_reason",
            "new_reason",
            "corrected_at_utc",
        ),
        """
        SELECT
            id AS invalidation_correction_id,
            prediction_id,
            invalidation_id,
            sequence,
            old_reason,
            new_reason,
            corrected_at AS corrected_at_utc
        FROM invalidation_reason_corrections
        ORDER BY invalidation_id, sequence, id
        """,
    ),
    _CsvTable(
        "postmortem_completions.csv",
        (
            "completion_id",
            "prediction_id",
            "completed_at_utc",
        ),
        """
        SELECT
            id AS completion_id,
            prediction_id,
            completed_at AS completed_at_utc
        FROM postmortem_completions
        ORDER BY id
        """,
    ),
)

# Format 4 is deliberately a new analytical contract: retired interval-v1 rows
# and their correction tables are not emitted as empty compatibility shells.
_CSV_TABLES += (
    _CsvTable(
        "numeric_quantile_definitions.csv",
        ("prediction_id", "value_constraint"),
        "SELECT prediction_id, value_constraint FROM numeric_quantile_definitions "
        "ORDER BY prediction_id",
    ),
    _CsvTable(
        "numeric_quantile_revisions.csv",
        (
            "quantile_revision_id",
            "prediction_id",
            "sequence",
            "q05_scaled",
            "q25_scaled",
            "q50_scaled",
            "q75_scaled",
            "q95_scaled",
            "rationale",
            "created_at_utc",
        ),
        """SELECT id AS quantile_revision_id, prediction_id, sequence,
                  q05_scaled, q25_scaled, q50_scaled, q75_scaled, q95_scaled,
                  rationale, created_at AS created_at_utc
           FROM numeric_quantile_revisions
           ORDER BY prediction_id, sequence, id""",
    ),
    _CsvTable(
        "binary_trajectory_resolution_corrections.csv",
        (
            "correction_id",
            "prediction_id",
            "resolution_id",
            "sequence",
            "old_outcome",
            "new_outcome",
            "old_effective_resolution_at_utc",
            "new_effective_resolution_at_utc",
            "old_resolution_notes",
            "new_resolution_notes",
            "old_postmortem",
            "new_postmortem",
            "outcome_changed",
            "effective_time_changed",
            "resolution_notes_changed",
            "postmortem_changed",
            "correction_reason",
            "corrected_at_utc",
        ),
        """SELECT id AS correction_id, prediction_id, resolution_id, sequence,
                  old_outcome, new_outcome,
                  old_effective_resolution_at AS old_effective_resolution_at_utc,
                  new_effective_resolution_at AS new_effective_resolution_at_utc,
                  old_resolution_notes, new_resolution_notes,
                  old_postmortem, new_postmortem, outcome_changed,
                  effective_time_changed, resolution_notes_changed,
                  postmortem_changed, correction_reason,
                  corrected_at AS corrected_at_utc
           FROM binary_trajectory_resolution_corrections
           ORDER BY resolution_id, sequence, id""",
    ),
    _CsvTable(
        "numeric_quantile_resolution_corrections.csv",
        (
            "correction_id",
            "prediction_id",
            "numeric_resolution_id",
            "sequence",
            "old_actual_scaled",
            "new_actual_scaled",
            "old_effective_resolution_at_utc",
            "new_effective_resolution_at_utc",
            "old_resolution_notes",
            "new_resolution_notes",
            "old_postmortem",
            "new_postmortem",
            "actual_value_changed",
            "effective_time_changed",
            "resolution_notes_changed",
            "postmortem_changed",
            "correction_reason",
            "corrected_at_utc",
        ),
        """SELECT id AS correction_id, prediction_id, numeric_resolution_id,
                  sequence, old_actual_scaled, new_actual_scaled,
                  old_effective_resolution_at AS old_effective_resolution_at_utc,
                  new_effective_resolution_at AS new_effective_resolution_at_utc,
                  old_resolution_notes, new_resolution_notes,
                  old_postmortem, new_postmortem, actual_value_changed,
                  effective_time_changed, resolution_notes_changed,
                  postmortem_changed, correction_reason,
                  corrected_at AS corrected_at_utc
           FROM numeric_quantile_resolution_corrections
           ORDER BY numeric_resolution_id, sequence, id""",
    ),
)

# Format 5 retains the format-4 files and adds explicitly labeled One-Shot
# snapshots. The original forecast/answer rows and all correction links remain
# in the bundle, so the effective projection is convenient rather than authority.
_ONE_SHOT_VALUES = (
    "probability_percent",
    "q05_scaled",
    "q25_scaled",
    "q50_scaled",
    "q75_scaled",
    "q95_scaled",
    "forecast_wall",
    "forecast_approximate",
    "forecast_offset",
    "outcome",
    "actual_scaled",
    "reveal_wall",
    "reveal_approximate",
    "reveal_offset",
    "resolution_notes",
    "postmortem",
)
for _kind in ("original", "effective"):
    _CSV_TABLES += (
        _CsvTable(
            f"one_shot_{_kind}_facts.csv",
            (
                "prediction_id",
                "recorded_at_utc",
                "answer_recorded_at_utc",
                *_ONE_SHOT_VALUES,
            ),
            f"""SELECT f.prediction_id, p.created_at AS recorded_at_utc,
                       COALESCE(b.resolved_at, n.resolved_at) AS answer_recorded_at_utc,
                       {", ".join("f." + column for column in _ONE_SHOT_VALUES)}
                FROM one_shot_{_kind}_facts AS f
                JOIN predictions AS p ON p.id = f.prediction_id
                LEFT JOIN resolutions AS b ON b.prediction_id = f.prediction_id
                LEFT JOIN numeric_resolutions AS n ON n.prediction_id = f.prediction_id
                ORDER BY f.prediction_id""",
        ),
    )
_ONE_SHOT_CORRECTION_VALUES = tuple(
    prefix + column for prefix in ("old_", "new_") for column in _ONE_SHOT_VALUES
)
_CSV_TABLES += (
    _CsvTable(
        "one_shot_corrections.csv",
        (
            "correction_id",
            "prediction_id",
            "sequence",
            "corrected_at_utc",
            "note",
            *_ONE_SHOT_CORRECTION_VALUES,
        ),
        "SELECT id AS correction_id, prediction_id, sequence, "
        "corrected_at AS corrected_at_utc, note, "
        + ", ".join(_ONE_SHOT_CORRECTION_VALUES)
        + " FROM one_shot_corrections ORDER BY prediction_id, sequence, id",
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
    files = "\n".join(
        f"{table.filename}: {', '.join(table.columns)}" for table in _CSV_TABLES
    )
    return f"""Reckonsolve CSV Export Bundle
==============================

Format version: 5
Exported at (UTC): {format_utc(exported_at)}

Purpose and limits
------------------
This is a relational analytical export, not an import or a recovery artifact.
Use a verified Reckonsolve .sqlite3 backup to recover the application. Format 5
exports the four supported Adaptive and One-Shot contracts; archives containing retired or
mismatched contracts are refused before this ZIP is created. It is not compatible
with the format-3 column layout. Format-4 files retain their columns; three new
One-Shot files are added, including header-only files when no One-Shots exist.
Retired numeric_forecast_revisions.csv,
resolution_corrections.csv, and numeric_resolution_corrections.csv are absent.
Their supported replacements are named below. Legacy date-only forecast_deadline
and old/new deadline columns are absent. The exact immutable Deadline lives in
predictions.csv as forecast_deadline_at_utc.

Encoding and nulls
------------------
Each CSV uses UTF-8 with a byte-order mark, comma delimiters, fully quoted fields,
and CRLF rows. An empty CSV field represents SQL NULL for optional columns; an
empty required text field represents an actual empty string. All columns ending
in _utc are RFC 3339 UTC instants; they retain microsecond precision and end in Z.
expected_resolution is an optional ISO YYYY-MM-DD planning date, not a scoring
cutoff. Fields ending in _scaled are exact signed integers; divide by
10^numeric_precision from the parent predictions.csv row to obtain base-ten values.
Never convert them through binary floating point. Free text is preserved verbatim.
When opening in spreadsheet software, import user text as text to prevent strings
beginning with =, +, -, or @ from being treated as formulas.

Relationships and derivations
-----------------------------
prediction_id joins every Prediction-owned row to predictions.csv. forecast_model
and scoring_contract identify the four closed supported pairs:
  binary-trajectory-v1 / binary-trajectory-brier-v1
  numeric-quantiles-5-v2 / numeric-wis-v1
  binary-one-shot-v1 / binary-one-shot-brier-v1
  numeric-one-shot-5-v1 / numeric-one-shot-wis-v1
Do not pool their scores. persisted_status is open, resolved, or invalid; Locked
is derived from an open Prediction and its exact forecast_deadline_at_utc.
Invalid and unresolved Predictions supply history but no scoring observation.

Adaptive is the user-facing name for the existing deadline-based contracts. Model and
scoring identities are unchanged; a stored mode of deadline still means Adaptive.
The following trajectory and cutoff rules apply only to Adaptive contracts.
forecast_revisions.csv has every immutable Binary revision, with contiguous
sequence, saved instant, probability_percent (0-100), and optional rationale.
To reconstruct the Binary standing trajectory, sort by sequence, let the initial
revision stand from its created_at_utc, and use each subsequent revision as the
next segment boundary. The scoring window ends at the exact Deadline; effective
resolution may truncate the active portion. The last eligible revision before
the cutoff is not an independent scored observation. Early-resolution neutral
weight is a derived 0.25 tail, never a stored revision.

numeric_quantile_definitions.csv stores continuous or whole-number semantics.
numeric_quantile_revisions.csv has exactly q05/q25/q50/q75/q95 per immutable
revision. Each _scaled value uses the parent Prediction's numeric_precision;
ties are valid. To select a final scoring revision, apply all effective-time
corrections, set cutoff=min(effective_resolution_at_utc, forecast_deadline_at_utc),
and choose the highest-sequence revision whose created_at_utc is strictly before
that cutoff. A revision at the cutoff is excluded. An outcome at or before the
initial revision has no score; do not invent a final revision.

resolutions.csv and numeric_resolutions.csv hold the original immutable terminal
facts. resolved_at_utc is the recorded-at instant; effective_resolution_at_utc is
the initial effective instant. scoring_revision_id / quantile_revision_id are
recording-context anchors, not scoring authority for these v0.7 contracts.
The current effective outcome, actual value, notes, Postmortem, and effective
time come from replaying their respective correction tables in sequence.
binary_trajectory_resolution_corrections.csv and
numeric_quantile_resolution_corrections.csv retain complete before/after
snapshots, changed-field flags, explanation, and correction timestamp.
An outcome/actual or effective-time change requires a reason. The original
recorded-at never changes. Corrections can alter final scoring selection;
derived scores are never exported as canonical facts.

journal_entries.csv and forecast_reviews.csv anchor to exactly one of
forecast_revision_id (Binary) or quantile_revision_id (Numeric). A Journal
records reasoning without revising the forecast; a Review deliberately retains
the standing forecast. journal_corrections.csv preserves every body correction;
its last sequence supplies current displayed text, or original_body if absent.
definition_changes.csv preserves protected Question and Resolution Criteria
edits; the exact Deadline cannot be edited. invalidations.csv and
invalidation_reason_corrections.csv preserve the original invalidation and
its later explanation history. postmortem_completions.csv records a deliberate
Skip; a later Postmortem may coexist. tags.csv and prediction_tags.csv preserve
stable tag identities and many-to-many membership.

One-Shot facts and transcription history
---------------------------------------
One-Shot predictions have a blank forecast_deadline_at_utc and no effective
resolution instant. Open means Waiting for answer; they never become Locked.
The single sequence-one Binary/quantile revision is the original forecast,
including its rationale. Original answers use the shared resolution files;
their captured revision IDs are audit anchors, not the corrected scoring values.
There are no One-Shot Forecast Reviews or ordinary forecast revisions.

one_shot_original_facts.csv combines the immutable original forecast with the
first answer, if any. The answer may have been entered later: recorded_at_utc
is the app's forecast-entry instant and answer_recorded_at_utc is the app's
answer-entry instant. Neither is a claimed time of an external phone note.
one_shot_effective_facts.csv is a derived convenience snapshot of current facts,
with the same immutable entry instants. It is not a second observation.
one_shot_corrections.csv preserves each complete old_/new_ snapshot, contiguous
per-Prediction sequence, immutable correction_id/corrected_at_utc, and optional note.
These are transcription corrections, not forecast updates.

To replay, start with the original forecast without an answer. Apply forecast
corrections in sequence. Before the first correction whose old snapshot has an
answer, attach the original answer/reveal/notes/Postmortem fields. If no such
correction exists, attach those fields after all forecast-only corrections.
This preserves a later first answer even when the last forecast-only correction
has blank answer fields. The result must match one_shot_effective_facts.csv.

Snapshot columns (also under old_/new_ in corrections): probability_percent is
the whole Yes percentage for Binary; q05/q25/q50/q75/q95_scaled and actual_scaled
are exact Numeric integers at the parent's precision. Inapplicable type fields
are blank. outcome is yes or no. resolution_notes and postmortem are optional text.
forecast_wall and reveal_wall are optional user-reported YYYY-MM-DDTHH:MM wall
minutes, NOT UTC instants. The corresponding _approximate flags are 0/1; _offset
is optional signed minutes east of UTC, documentary context only. A missing
wall time has approximate=0 and blank offset. No time-zone conversion, cutoff,
or elapsed weight may be inferred from these fields. All app timestamps are UTC.

Score exactly once from the effective forecast and answer: ordinary Binary Brier
or exact five-quantile Numeric WIS. Missing answers and Invalid records have no
score. Do not use the deadline cutoff/trajectory rules above for One-Shot or pool
its observations with Adaptive analytics. Do not average raw WIS across
questions. Corrections retain original values; reported times never alter scores.

Columns by file (all exported columns, in order)
------------------------------------------------
{files}

Intentional exclusions
----------------------
Saved Views, application settings, presentation preferences, search index and
repair state, ranking data, derived scores, interpolated CDF points, and click
telemetry are not analytical history and are not in this ZIP. A complete SQLite
backup retains canonical data and settings; its derived search projection can
be rebuilt from history.
"""
