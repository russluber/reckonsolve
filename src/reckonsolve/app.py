"""Application composition and startup."""

import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError
from reckonsolve.identity import STABLE_APPLICATION, ApplicationIdentity
from reckonsolve.paths import ApplicationDataPathError, resolve_database_path
from reckonsolve.ui.main_window import MainWindow

APPLICATION_NAME = STABLE_APPLICATION.application_name


@dataclass(slots=True)
class ApplicationRuntime:
    """Objects whose lifetime is tied to one application run."""

    qt_app: QApplication
    database: Database
    window: MainWindow
    identity: ApplicationIdentity = STABLE_APPLICATION

    def close(self) -> None:
        """Close the window and persistence resources deterministically."""

        try:
            self.window.close()
        finally:
            self.database.close()


def create_runtime(
    *,
    argv: Sequence[str] | None = None,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
) -> ApplicationRuntime:
    """Compose the application, using an explicit database path when supplied."""

    qt_app = _get_or_create_qapplication(argv, identity)
    resolved_database_path = resolve_database_path(database_path)
    database = Database.open(resolved_database_path)
    try:
        operations = PredictionOperations(database)
        window = MainWindow(operations, window_title=identity.window_title)
    except BaseException:
        database.close()
        raise

    return ApplicationRuntime(
        qt_app=qt_app,
        database=database,
        window=window,
        identity=identity,
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
) -> int:
    """Open the main window and run the Qt event loop."""

    try:
        runtime = create_runtime(
            argv=argv,
            database_path=database_path,
            identity=identity,
        )
    except (ApplicationDataPathError, MigrationError, OSError, sqlite3.Error) as error:
        application = QApplication.instance()
        if isinstance(application, QApplication):
            QMessageBox.critical(
                None,
                f"{identity.window_title} could not start",
                f"{identity.window_title} could not open its database. No existing data was "
                f"replaced.\n\n{error}",
            )
        return 1

    try:
        runtime.window.show()
        return runtime.qt_app.exec()
    finally:
        runtime.close()


def _get_or_create_qapplication(
    argv: Sequence[str] | None,
    identity: ApplicationIdentity,
) -> QApplication:
    QCoreApplication.setApplicationName(identity.application_name)

    existing_application = QApplication.instance()
    if existing_application is not None:
        if not isinstance(existing_application, QApplication):
            raise RuntimeError("A non-GUI Qt application already exists.")
        return existing_application

    arguments = list(sys.argv if argv is None else argv)
    return QApplication(arguments)
