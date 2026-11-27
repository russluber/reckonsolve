"""Settings, backup/export, search repair, and notifications."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from main_window_fakes import (
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QStyleFactory,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.location_controls import LocationControls
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
)
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    SurfaceRole,
)


@pytest.mark.parametrize("appearance", [AppearanceMode.LIGHT, AppearanceMode.DARK])
@pytest.mark.parametrize("style_name", ["windows11", "Fusion"])
def test_compact_settings_fits_all_ordinary_options_and_preserves_keyboard_order(
    qtbot, qapp, appearance, style_name
):
    available_styles = QStyleFactory.keys()
    assert style_name in available_styles
    original_style = qapp.style().objectName()
    original_font = qapp.font()
    qapp.setStyle(style_name)
    try:
        operations = FakePredictionOperations()
        operations.data_management_status = replace(
            operations.data_management_status,
            database_path=Path(
                "C:/Users/visual/AppData/Local/Reckonsolve/reckonsolve.sqlite3"
            ),
        )
        window = MainWindow(
            operations, presentation_settings=MemoryPresentationSettings()
        )
        qtbot.addWidget(window)
        screen = window._settings_screen

        def unused(*_args):
            pytest.fail("Layout and keyboard navigation must not move a journal")

        controls = LocationControls(unused, unused, screen)
        screen.add_location_controls(controls)
        window.appearance.select(appearance)
        window.show()
        window.navigate_to("Settings")
        fields = (
            screen.appearance_mode,
            screen.date_format_input,
            controls.choose,
            screen.backup_button,
            screen.export_button,
            screen.manage_tags_button,
            screen.repair_search_button,
        )
        for width, height in ((1600, 1000), (1000, 700), (760, 520)):
            window.resize(width, height)
            qtbot.wait(70)
            assert window._workspace_content.width() == min(width, 1320)
            assert screen.scroll_area.verticalScrollBar().maximum() == 0
            assert screen.scroll_area.horizontalScrollBar().maximum() == 0
            viewport = screen.scroll_area.viewport()
            for field in fields:
                assert field.isVisible()
                top_left = field.mapTo(viewport, field.rect().topLeft())
                bottom_right = field.mapTo(viewport, field.rect().bottomRight())
                assert viewport.rect().contains(top_left)
                assert viewport.rect().contains(bottom_right)
            for label in screen.findChildren(QLabel):
                if label.isVisible() and label.wordWrap():
                    assert label.height() >= label.heightForWidth(label.width())
        screen.appearance_mode.setFocus()
        for expected in fields[1:]:
            for _ in range(20):
                qtbot.keyClick(window.focusWidget(), Qt.Key.Key_Tab)
                if window.focusWidget() in fields:
                    break
            assert window.focusWidget() is expected
        assert operations.backup_calls == []
        assert operations.export_calls == []
        assert operations.search_repair_calls == 0

        qapp.setFont(QFont("Segoe UI", 15))
        qtbot.waitUntil(
            lambda: (
                screen.backup_button.mapTo(
                    screen, screen.backup_button.rect().topLeft()
                ).y()
                > controls.choose.mapTo(screen, controls.choose.rect().bottomLeft()).y()
                and screen.scroll_area.verticalScrollBar().maximum() > 0
                and screen.scroll_area.horizontalScrollBar().maximum() == 0
            )
        )
        assert screen.scroll_area.horizontalScrollBar().maximum() == 0
        assert operations.backup_calls == []
    finally:
        qapp.setFont(original_font)
        qapp.setStyle(original_style)
        # Flush restyle work while registered widgets still own their timers.
        qapp.processEvents()


@pytest.mark.parametrize("appearance", [AppearanceMode.LIGHT, AppearanceMode.DARK])
def test_compact_settings_preserves_long_results_with_safe_overflow(qtbot, appearance):
    window = MainWindow(
        FakePredictionOperations(), presentation_settings=MemoryPresentationSettings()
    )
    qtbot.addWidget(window)
    window.appearance.select(appearance)
    window.resize(760, 520)
    window.show()
    window.navigate_to("Settings")
    screen = window._settings_screen
    message = "The backup destination could not be opened. " * 40
    screen.backup_tool.show_result(message, StatusTone.ERROR)
    qtbot.wait(60)
    result = screen.backup_tool.result
    assert result.text() == message
    assert result.height() >= result.heightForWidth(result.width())
    assert screen.scroll_area.horizontalScrollBar().maximum() == 0
    screen.scroll_area.ensureWidgetVisible(result)
    assert result.isVisible()
    window.navigate_to("Journal")
    window.navigate_to("Settings")
    qtbot.wait(60)
    assert result.isHidden()
    assert screen.scroll_area.verticalScrollBar().maximum() == 0


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
        .strftime("%Y-%m-%d, %I:%M %p")
    )
    assert _required_child(window, QLabel, "lastSuccessfulBackup").text() == (
        f"Last successful backup: {expected_local}"
    )
    for panel_name in ("dataManagementPanel",):
        panel = _required_child(window, ContentPanel, panel_name)
        assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.CANVAS.value
    assert window.findChild(QWidget, "attentionSettingsPanel") is None
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
    assert (
        _required_child(window, QLabel, "backUpNowResult")
        .text()
        .startswith(f"Backup created: {expected_backup}\nComplete SQLite backup")
    )
    assert (
        _required_child(
            window,
            QLabel,
            "backUpNowResult",
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
    assert (
        _required_child(window, QLabel, "exportCsvBundleResult")
        .text()
        .startswith(f"Exported 16 CSV files: {expected_export}\nAnalytical export")
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
    status = _required_child(window, QLabel, "repairSearchIndexResult")

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
    status = _required_child(window, QLabel, "backUpNowResult")
    assert (
        status.text()
        == f"Backup destination is locked.\nSelected destination: {tmp_path / 'backup.sqlite3'}"
    )
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    qtbot.mouseClick(
        _required_child(window, QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )
    backup_message = status.text()
    status = _required_child(window, QLabel, "exportCsvBundleResult")
    assert (
        status.text()
        == f"Export destination is locked.\nSelected destination: {tmp_path / 'export.zip'}"
    )
    assert _required_child(window, QLabel, "backUpNowResult").text() == backup_message
    assert status.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
