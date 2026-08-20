"""Values returned by backup and portable-export operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataManagementStatus:
    """Current recovery status and safe suggested artifact names."""

    database_path: Path
    last_successful_backup_at: datetime | None
    suggested_backup_filename: str
    suggested_export_filename: str


@dataclass(frozen=True, slots=True)
class BackupResult:
    """A complete SQLite recovery artifact created at a chosen destination."""

    destination: Path
    completed_at: datetime
    last_successful_time_recorded: bool = True


@dataclass(frozen=True, slots=True)
class CsvExportResult:
    """A documented relational CSV bundle created at a chosen destination."""

    destination: Path
    exported_at: datetime
    csv_file_count: int
