"""Application composition and startup."""

import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.application.relocation import MoveReview, RelocationService
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.journal_location import MoveRecoveryRequired, RuntimeLocation
from reckonsolve.data.location_native import LocationError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.data.upgrade import UpgradeCancelledError, UpgradeReview
from reckonsolve.identity import STABLE_APPLICATION, ApplicationIdentity
from reckonsolve.paths import ApplicationDataPathError, open_runtime_location
from reckonsolve.ui.location_controls import LocationControls, review_recovery
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.presentation_settings import QtPresentationSettings

APPLICATION_NAME = STABLE_APPLICATION.application_name


@dataclass(slots=True)
class ApplicationRuntime:
    """Objects whose lifetime is tied to one application run."""

    qt_app: QApplication
    database: Database
    window: MainWindow
    identity: ApplicationIdentity = STABLE_APPLICATION
    location: RuntimeLocation | None = None
    restart_requested: bool = False
    storage_blocked: bool = False

    def close(self) -> None:
        """Close the window and persistence resources deterministically."""

        try:
            closed = self.window.close()
        except BaseException:
            self.database.close()
            if self.location is not None:
                self.location.close()
            raise
        if closed is not False:
            self.database.close()
            if self.location is not None:
                self.location.close()

    def relocate(self, review: MoveReview) -> None:
        """Reconstruct the whole runtime on success; reconnect in place on abort."""
        if self.location is None or self.location.store is None:
            raise LocationError(
                "This isolated database was opened without relocation settings."
            )
        self.window.setEnabled(False)
        try:
            for reads in (
                self.window._journal_screen.retrieval,
                self.window._analytics_screen.retrieval,
            ):
                if not reads.drain():
                    raise LocationError(
                        "Journal reads are still finishing. Try again after they finish."
                    )
            self.database.close()
            self.location.close()
            try:
                RelocationService(self.location.store).execute(review)
            except BaseException:
                try:
                    self.location.resume()
                    self.database.reconnect()
                except BaseException:
                    self.storage_blocked = True
                    self.window.archive_blocked = True
                    self.location.close()
                    raise
                raise
            try:
                if self.window.close() is False:
                    raise LocationError(
                        "The journal moved, but the window could not close. Close and reopen this same app."
                    )
            except BaseException:
                self.storage_blocked = True
                self.window.archive_blocked = True
                raise
            self.restart_requested = True
        finally:
            if not self.restart_requested and not self.storage_blocked:
                self.window.setEnabled(True)


def create_runtime(
    *,
    argv: Sequence[str] | None = None,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
    bootstrap_directory: Path | None = None,
) -> ApplicationRuntime:
    """Compose the application, using an explicit database path when supplied."""

    qt_app = _get_or_create_qapplication(argv, identity)
    location = open_runtime_location(
        database_path, identity, bootstrap_directory=bootstrap_directory
    )
    try:
        database = Database.open(
            location.database_path,
            confirm_upgrade=_confirm_upgrade,
            allow_create=location.allow_create,
        )
    except BaseException:
        location.close()
        raise
    try:
        if location.store is not None:
            location.store.mark_initialized()
        operations = PredictionOperations(database)
        window = MainWindow(
            operations,
            window_title=identity.window_title,
            presentation_settings=QtPresentationSettings(location.presentation_path),
        )
    except BaseException:
        database.close()
        location.close()
        raise

    runtime = ApplicationRuntime(
        qt_app=qt_app,
        database=database,
        window=window,
        identity=identity,
        location=location,
    )
    if location.store is not None:
        service = RelocationService(location.store)
        controls = LocationControls(
            service.preview, runtime.relocate, window._settings_screen
        )
        controls.storage_failed.connect(
            lambda error: _show_move_blocked(runtime, error)
        )
        controls.archive_refused.connect(window._archive_refused)
        window._settings_screen.add_location_controls(controls)
    return runtime


def run(
    argv: Sequence[str] | None = None,
    *,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
    bootstrap_directory: Path | None = None,
) -> int:
    """Open the main window and run the Qt event loop."""

    while True:
        try:
            runtime = create_runtime(
                argv=argv,
                database_path=database_path,
                identity=identity,
                bootstrap_directory=bootstrap_directory,
            )
        except MoveRecoveryRequired as error:
            if review_recovery(error):
                continue
            return 1
        except LocationError as error:
            QMessageBox.critical(
                None, f"{identity.window_title} location unavailable", str(error)
            )
            return 1
        except UpgradeCancelledError:
            return 0
        except (
            ApplicationDataPathError,
            ForecastContractIntegrityError,
            MigrationError,
            OSError,
            sqlite3.Error,
        ) as error:
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
            result = runtime.qt_app.exec()
        finally:
            runtime.close()
        if not runtime.restart_requested:
            return result
        runtime.window.deleteLater()
        runtime.qt_app.sendPostedEvents()


def _show_move_blocked(runtime: ApplicationRuntime, error: Exception) -> None:
    if runtime.storage_blocked:
        # Leave the frame closable, but no data actions may resume on an
        # uncertain journal. Next startup opens the explicit recovery review.
        runtime.window.setEnabled(True)
        runtime.window._screen_stack.setEnabled(False)
        runtime.window._toolbar.setEnabled(False)
        QMessageBox.critical(
            runtime.window,
            "Journal move needs recovery",
            f"Close and reopen this same Reckonsolve app. It will verify the active location or show the required recovery. No journal is available for editing.\n\n{error}",
        )


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


def _confirm_upgrade(review: UpgradeReview) -> bool:
    """Review the already verified copy while SQLite exclusion is still held."""
    return (
        QMessageBox.question(
            None,
            "Upgrade Journal and retire Saved Views?",
            f"A verified complete recovery backup has been saved to:\n{review.recovery}\n\n"
            f"This journal contains {review.saved_view_count} Saved View configuration(s). "
            "The upgrade removes those configurations from the active journal. "
            "Predictions, forecasting history and tags are retained. "
            "The recovery copy preserves the complete earlier journal.\n\n"
            "Continue with the upgrade?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        == QMessageBox.StandardButton.Yes
    )
