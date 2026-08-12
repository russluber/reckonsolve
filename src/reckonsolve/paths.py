"""Per-user runtime paths."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths

DATABASE_FILENAME = "reckonsolve.sqlite3"


class ApplicationDataPathError(RuntimeError):
    """Raised when the platform cannot provide an application-data directory."""


def resolve_database_path(
    explicit_path: Path | None = None,
    *,
    app_data_directory: Path | None = None,
) -> Path:
    """Resolve the database path, allowing safe explicit injection in tests."""

    if explicit_path is not None:
        return Path(explicit_path)

    if app_data_directory is None:
        location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        if not location:
            raise ApplicationDataPathError(
                "Windows did not provide a local application-data directory."
            )
        app_data_directory = Path(location)

    return Path(app_data_directory) / DATABASE_FILENAME
