"""CLI orchestration for verified backup and relational CSV export."""

from pathlib import Path

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli_creation import PromptSession
from reckonsolve.domain.transfer import BackupResult, CsvExportResult


def backup_interactively(
    operations: PredictionOperations,
    session: PromptSession,
    destination: Path | None,
) -> BackupResult:
    """Choose a destination and create one complete recovery backup."""

    selected_destination = destination
    if selected_destination is None:
        selected_destination = _prompt_destination(
            session,
            operations.get_data_management_status().suggested_backup_filename,
        )
    result = operations.create_backup(selected_destination)
    print(f"Backup created: {result.destination}", file=session.output)
    print(
        "Recovery artifact: complete verified Reckonsolve SQLite database.",
        file=session.output,
    )
    if result.last_successful_time_recorded:
        print("Last successful backup time recorded.", file=session.output)
    else:
        print(
            "Warning: the backup is usable, but Reckonsolve could not record "
            "its completion time.",
            file=session.errors,
        )
    return result


def export_csv_interactively(
    operations: PredictionOperations,
    session: PromptSession,
    destination: Path | None,
) -> CsvExportResult:
    """Choose a destination and create one analytical CSV ZIP bundle."""

    selected_destination = destination
    if selected_destination is None:
        selected_destination = _prompt_destination(
            session,
            operations.get_data_management_status().suggested_export_filename,
        )
    result = operations.export_csv_bundle(selected_destination)
    print(f"CSV export created: {result.destination}", file=session.output)
    print(
        f"Exported {result.csv_file_count} CSV files in format version 2.",
        file=session.output,
    )
    print(
        "This ZIP is portable analytical data, not a recovery backup. "
        "Use a .sqlite3 backup to restore Reckonsolve.",
        file=session.output,
    )
    return result


def _prompt_destination(
    session: PromptSession,
    suggested_filename: str,
) -> Path:
    entered = session.ask(f"Destination [{suggested_filename}]: ").strip()
    return Path(entered) if entered else Path(suggested_filename)
