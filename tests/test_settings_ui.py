"""Settings, backup/export, search repair, and notifications."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from main_window_fakes import (
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    SurfaceRole,
)


def test_settings_persists_threshold_and_refreshes_dashboard(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dashboard_calls = operations.dashboard_calls

    window.navigate_to("Settings")
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    save = _required_child(window, QPushButton, "saveStaleThresholdButton")
    assert threshold.value() == 14
    assert threshold.minimum() == 1
    assert threshold.maximum() == 9999

    threshold.setValue(30)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    assert operations.threshold_set_calls == [30]
    assert operations.stale_threshold_days == 30
    assert operations.dashboard_calls == dashboard_calls + 1
    assert _required_child(window, QLabel, "staleThresholdStatus").isHidden()
    notification = _required_child(window, NotificationHost, "notificationHost")
    assert notification.current_message == (
        "Needs Attention threshold saved at 30 days."
    )
    assert not notification.isHidden()
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 30 days"
    )


def test_settings_displays_database_and_persisted_backup_status(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.data_management_status = replace(
        operations.data_management_status,
        last_successful_backup_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Settings")

    assert _required_child(window, QLabel, "databaseLocation").text() == (
        f"Database: {Path('test-data/reckonsolve.sqlite3')}"
    )
    expected_local = (
        datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
        .astimezone()
        .strftime("%b %d, %Y, %I:%M %p")
        .replace(" 0", " ")
    )
    assert _required_child(window, QLabel, "lastSuccessfulBackup").text() == (
        f"Last successful backup: {expected_local}"
    )
    for panel_name in ("attentionSettingsPanel", "dataManagementPanel"):
        panel = _required_child(window, ContentPanel, panel_name)
        assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert (
        _required_child(
            window,
            QPushButton,
            "saveStaleThresholdButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "backUpNowButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "exportCsvBundleButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.SECONDARY.value
    )
    assert (
        _required_child(
            window,
            QPushButton,
            "repairSearchIndexButton",
        ).property(ACTION_ROLE_PROPERTY)
        == ActionRole.QUIET.value
    )
    database_path = _required_child(window, QLabel, "databaseLocation")
    assert database_path.textInteractionFlags() & (
        Qt.TextInteractionFlag.TextSelectableByKeyboard
    )


def test_settings_creates_backup_and_csv_bundle_from_selected_destinations(
    qtbot: QtBot,
    monkeypatch,
    tmp_path,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    selected_paths = iter(
        (
            str(tmp_path / "chosen-backup"),
            str(tmp_path / "chosen-export"),
        )
    )
    suggested_paths: list[str] = []

    def choose_file(_parent, _title, suggested, _file_filter):
        suggested_paths.append(suggested)
        return next(selected_paths), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_file)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )

    expected_backup = tmp_path / "chosen-backup.sqlite3"
    assert operations.backup_calls == [expected_backup]
    assert _required_child(window, QLabel, "dataManagementStatus").text() == (
        f"Backup created: {expected_backup}"
    )
    assert (
        _required_child(
            window,
            QLabel,
            "dataManagementStatus",
        ).property(MESSAGE_TONE_PROPERTY)
        == StatusTone.SUCCESS.value
    )
    assert (
        "Not yet"
        not in _required_child(
            window,
            QLabel,
            "lastSuccessfulBackup",
        ).text()
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )

    expected_export = tmp_path / "chosen-export.zip"
    assert operations.export_calls == [expected_export]
    assert _required_child(window, QLabel, "dataManagementStatus").text() == (
        f"Exported 16 CSV files: {expected_export}"
    )
    assert suggested_paths[0].endswith("reckonsolve-backup-20260820-123000.sqlite3")
    assert suggested_paths[1].endswith("reckonsolve-export-20260820-123000.zip")


def test_cancelling_data_destination_dialogs_has_no_side_effect(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_arguments: ("", ""),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.backup_calls == []
    assert operations.export_calls == []
    assert _required_child(window, QLabel, "dataManagementStatus").isHidden()


def test_settings_repairs_search_index_and_reports_expected_failure(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    button = _required_child(window, QPushButton, "repairSearchIndexButton")
    status = _required_child(window, QLabel, "dataManagementStatus")

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert operations.search_repair_calls == 1
    assert status.text() == ("Search index repaired from canonical Prediction history.")

    operations.search_repair_error = ApplicationError(
        "Search repair could not complete."
    )
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert operations.search_repair_calls == 2
    assert status.text() == "Search repair could not complete."


def test_settings_shows_expected_backup_export_and_status_errors(
    qtbot: QtBot,
    monkeypatch,
    tmp_path,
) -> None:
    operations = FakePredictionOperations()
    operations.data_management_error = ApplicationError("Backup status unavailable.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    status = _required_child(window, QLabel, "dataManagementStatus")
    assert status.text() == "Backup status unavailable."

    operations.data_management_error = None
    operations.backup_error = ApplicationError("Backup destination is locked.")
    operations.export_error = ApplicationError("Export destination is locked.")
    selected_paths = iter(
        (str(tmp_path / "backup.sqlite3"), str(tmp_path / "export.zip"))
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_arguments: (next(selected_paths), ""),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )
    assert status.text() == "Backup destination is locked."
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )
    assert status.text() == "Export destination is locked."
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value


def test_routine_notification_survives_navigation_without_reflow(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Settings")
    stack = _required_child(window, QStackedWidget, "screenStack")
    geometry_before = stack.geometry()
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    threshold.setValue(21)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveStaleThresholdButton"),
        Qt.MouseButton.LeftButton,
    )
    notification = _required_child(window, NotificationHost, "notificationHost")
    window.navigate_to("Dashboard")

    assert notification.isVisible()
    assert notification.current_message == (
        "Needs Attention threshold saved at 21 days."
    )
    assert stack.geometry() == geometry_before


def test_notification_failure_cannot_roll_back_a_saved_setting(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    threshold.setValue(22)
    notification = _required_child(window, NotificationHost, "notificationHost")
    monkeypatch.setattr(
        notification,
        "show_message",
        lambda _message: (_ for _ in ()).throw(RuntimeError("paint failed")),
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveStaleThresholdButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.threshold_set_calls == [22]
    assert operations.stale_threshold_days == 22
    assert _required_child(window, QLabel, "staleThresholdStatus").isHidden()


def test_dashboard_and_settings_show_expected_read_errors(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.dashboard_error = ApplicationError("Dashboard could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard unavailable. Dashboard could not be loaded."
    )
    assert _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.dashboard_error = None
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    operations.dashboard_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard could not refresh; showing the last loaded results. Refresh failed."
    )
    assert not _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.threshold_error = ApplicationError("Setting could not be loaded.")
    window.navigate_to("Settings")
    assert _required_child(window, QLabel, "staleThresholdStatus").text() == (
        "Setting could not be loaded."
    )
    assert not _required_child(window, QSpinBox, "staleThresholdInput").isEnabled()
    assert not _required_child(
        window,
        QPushButton,
        "saveStaleThresholdButton",
    ).isEnabled()
    assert operations.data_management_calls > 0
    assert _required_child(window, QLabel, "databaseLocation").text() == (
        f"Database: {Path('test-data/reckonsolve.sqlite3')}"
    )
