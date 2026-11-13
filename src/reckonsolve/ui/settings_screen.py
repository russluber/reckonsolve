"""Organized local administration with a distinct result beside every tool."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.domain.transfer import (
    BackupResult,
    CsvExportResult,
    DataManagementStatus,
)
from reckonsolve.ui.components import (
    ContentPanel,
    PageHeader,
    PersistentMessageLabel,
    StatusBadge,
)
from reckonsolve.ui.date_display import (
    DateFormat,
    format_datetime,
    windows_zone_description,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.presentation_settings import AppearanceMode
from reckonsolve.ui.quantile_analytics import _label
from reckonsolve.ui.settings_tools import SettingsTool
from reckonsolve.ui.tag_manager import TagManagementOperations, TagManagerDialog
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    apply_action_role,
    apply_surface_role,
)


class SettingsOperations(TagManagementOperations, Protocol):
    def get_data_management_status(self) -> DataManagementStatus: ...
    def create_backup(self, destination: Path) -> BackupResult: ...
    def export_csv_bundle(self, destination: Path) -> CsvExportResult: ...
    def repair_search_index(self) -> None: ...


AttentionSettingsOperations = SettingsOperations


class SettingsScreen(QWidget):
    appearance_changed = Signal(object)
    date_format_changed = Signal(object)
    routine_notification_requested = Signal(str)
    tags_changed = Signal(object)
    archive_refused = Signal(object)

    def __init__(
        self, operations: SettingsOperations, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScreen")
        self._operations = operations
        self._suggested_backup_filename = "reckonsolve-backup.sqlite3"
        self._suggested_export_filename = "reckonsolve-export.zip"
        content = QWidget(self)
        content.setObjectName("settingsContent")
        content.setMaximumWidth(920)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(int(Spacing.SECTION))
        layout.addWidget(
            PageHeader(
                "Settings",
                "Data, recovery and shared maintenance.",
                title_object_name="settingsScreenTitle",
                supporting_object_name="settingsIntroduction",
                parent=content,
            )
        )
        self.data_status_label = PersistentMessageLabel(
            accessible_name="Settings data status", parent=content
        )
        self.data_status_label.setObjectName("dataManagementStatus")
        self.data_status_label.setWordWrap(True)
        self.data_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.data_status_label)
        appearance = ContentPanel("Appearance", parent=content)
        apply_surface_role(appearance, SurfaceRole.CANVAS)
        self.appearance_mode = QComboBox(appearance.body)
        self.appearance_mode.setObjectName("appearanceMode")
        self.appearance_mode.setAccessibleName("Appearance")
        for title, mode in (
            ("Follow Windows", AppearanceMode.FOLLOW_WINDOWS),
            ("Light", AppearanceMode.LIGHT),
            ("Dark", AppearanceMode.DARK),
        ):
            self.appearance_mode.addItem(title, mode)
        appearance.body_layout.addWidget(self.appearance_mode)
        self.appearance_mode.currentIndexChanged.connect(
            lambda: self.appearance_changed.emit(
                AppearanceMode(self.appearance_mode.currentData())
            )
        )
        layout.addWidget(appearance)
        dates = ContentPanel("Dates and Time", parent=content)
        apply_surface_role(dates, SurfaceRole.CANVAS)
        self.date_format_input = QComboBox(dates.body)
        self.date_format_input.setObjectName("dateFormatPreference")
        self.date_format_input.setAccessibleName("Date format")
        for value in DateFormat:
            self.date_format_input.addItem(value.value, value)
        self.date_format_input.currentIndexChanged.connect(
            lambda: self.date_format_changed.emit(
                DateFormat(self.date_format_input.currentData())
            )
        )
        dates.body_layout.addWidget(self.date_format_input)
        self.time_zone_label = _label(windows_zone_description(), dates.body)
        self.time_zone_label.setAccessibleName("Windows time zone")
        dates.body_layout.addWidget(self.time_zone_label)
        layout.addWidget(dates)
        location = ContentPanel("Database location", parent=content)
        location.setObjectName("dataManagementPanel")
        self.location_panel = location
        self.location_controls = None
        apply_surface_role(location, SurfaceRole.CANVAS)
        self.database_path_label = _label("Database: loading…", location.body)
        self.database_path_label.setObjectName("databaseLocation")
        self.database_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        location.body_layout.addWidget(self.database_path_label)
        layout.addWidget(location)
        self.backup_tool = SettingsTool(
            "Backups",
            "Complete SQLite backup for recovery.",
            "Back Up Now",
            "backUpNow",
            content,
        )
        self.last_backup_label = _label(
            "Last successful backup: loading…", self.backup_tool.body
        )
        self.last_backup_label.setObjectName("lastSuccessfulBackup")
        self.backup_tool.body_layout.insertWidget(1, self.last_backup_label)
        self.backup_button = self.backup_tool.button
        apply_action_role(self.backup_button, ActionRole.PRIMARY)
        apply_lucide_icon(self.backup_button, LucideIcon.DATABASE_BACKUP)
        self.backup_button.clicked.connect(self._back_up_now)
        self.export_tool = SettingsTool(
            "Export",
            "CSV files support analysis; they cannot restore the database.",
            "Export CSV Bundle",
            "exportCsvBundle",
            content,
        )
        self.export_button = self.export_tool.button
        apply_lucide_icon(self.export_button, LucideIcon.FILE_ARCHIVE)
        self.export_button.clicked.connect(self._export_csv_bundle)
        self.tag_tool = SettingsTool(
            "Shared tags",
            "Rename, merge or delete reusable tags across your journal.",
            "Manage Tags",
            "manageTags",
            content,
        )
        self.manage_tags_button = self.tag_tool.button
        self.manage_tags_button.clicked.connect(self._manage_tags)
        self.search_tool = SettingsTool(
            "Search index",
            "Rebuild derived search data from saved records.",
            "Repair Search Index",
            "repairSearchIndex",
            content,
        )
        self.repair_search_button = self.search_tool.button
        apply_action_role(self.repair_search_button, ActionRole.QUIET)
        apply_lucide_icon(self.repair_search_button, LucideIcon.REFRESH)
        self.repair_search_button.clicked.connect(self._repair_search_index)
        self.tools = (
            self.backup_tool,
            self.export_tool,
            self.tag_tool,
            self.search_tool,
        )
        for tool in self.tools:
            layout.addWidget(tool)
        shortcuts = ContentPanel("Keyboard shortcuts", parent=content)
        shortcuts.setObjectName("keyboardShortcutsPanel")
        apply_surface_role(shortcuts, SurfaceRole.CANVAS)
        grid = QGridLayout()
        for row, (action, keys) in enumerate(
            (
                ("New Prediction · Journal, Detail or Performance", "Ctrl+N"),
                ("Focus Journal search · Journal only", "Ctrl+F"),
                ("Settings · outside creation", "Ctrl+,"),
            )
        ):
            grid.addWidget(_label(action, shortcuts.body), row, 0)
            badge = StatusBadge(keys, StatusTone.NEUTRAL, parent=shortcuts.body)
            badge.setAccessibleName(f"{action}: {keys}")
            grid.addWidget(badge, row, 1, Qt.AlignmentFlag.AlignLeft)
        grid.setColumnStretch(0, 1)
        shortcuts.body_layout.addLayout(grid)
        layout.addWidget(shortcuts)
        layout.addStretch()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("settingsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll_area)
        self.setTabOrder(self.appearance_mode, self.backup_button)
        self.setTabOrder(self.backup_button, self.export_button)
        self.setTabOrder(self.export_button, self.manage_tags_button)
        self.setTabOrder(self.manage_tags_button, self.repair_search_button)

    def refresh(self) -> None:
        try:
            status = self._operations.get_data_management_status()
        except (ForecastContractIntegrityError, MigrationError) as error:
            self.archive_refused.emit(error)
            return
        except ApplicationError as error:
            self.data_status_label.show_message(str(error), StatusTone.ERROR)
            return
        self._suggested_backup_filename = status.suggested_backup_filename
        self._suggested_export_filename = status.suggested_export_filename
        self.database_path_label.setText(f"Database: {status.database_path}")
        self.database_path_label.setToolTip(str(status.database_path))
        self._show_last_backup(status.last_successful_backup_at)
        self.data_status_label.clear_message()

    def leave(self) -> None:
        """Visit-local results expire on navigation, not minimization or recoloring."""
        for tool in self.tools:
            tool.clear_result()
        self.data_status_label.clear_message()
        if self.location_controls is not None:
            self.location_controls.clear_result()

    def add_location_controls(self, controls: QWidget) -> None:
        self.location_controls = controls
        self.location_panel.body_layout.addWidget(controls)

    def set_appearance(self, mode: AppearanceMode) -> None:
        with QSignalBlocker(self.appearance_mode):
            self.appearance_mode.setCurrentIndex(self.appearance_mode.findData(mode))

    def set_date_format(self, value: DateFormat) -> None:
        self.display_date_format = value
        with QSignalBlocker(self.date_format_input):
            self.date_format_input.setCurrentIndex(
                self.date_format_input.findData(value)
            )
        self.time_zone_label.setText(windows_zone_description())
        for tool in self.tools:
            if tool.date_renderer is not None:
                tool.result.setText(tool.date_renderer())

    def _run(
        self,
        tool: SettingsTool,
        operation: Callable[[], tuple[str, StatusTone]],
        *,
        destination: Path | None = None,
    ) -> None:
        tool.date_renderer = None
        try:
            message, tone = operation()
        except (ForecastContractIntegrityError, MigrationError) as error:
            self.archive_refused.emit(error)
            return
        except ApplicationError as error:
            message = str(error) + (
                f"\nSelected destination: {destination}" if destination else ""
            )
            tool.show_result(message, StatusTone.ERROR)
            return
        tool.show_result(message, tone)

    def _back_up_now(self) -> None:
        destination = self._choose_destination(
            title="Create Reckonsolve Backup",
            suggested_filename=self._suggested_backup_filename,
            file_filter="SQLite database (*.sqlite3);;All files (*)",
            default_suffix=".sqlite3",
        )
        if destination is None:
            return

        def create() -> tuple[str, StatusTone]:
            result = self._operations.create_backup(destination)
            if result.last_successful_time_recorded:
                self._show_last_backup(result.completed_at)

            def receipt() -> str:
                message = f"Backup created: {result.destination}\nComplete SQLite backup · {_format_local_timestamp(result.completed_at, widget=self)}"
                if not result.last_successful_time_recorded:
                    message += "\nThe file is usable, but its successful time could not be recorded in Settings."
                return message

            self.backup_tool.date_renderer = receipt
            return receipt(), (
                StatusTone.SUCCESS
                if result.last_successful_time_recorded
                else StatusTone.WARNING
            )

        self._run(self.backup_tool, create, destination=destination)

    def _export_csv_bundle(self) -> None:
        destination = self._choose_destination(
            title="Export Reckonsolve CSV Bundle",
            suggested_filename=self._suggested_export_filename,
            file_filter="ZIP archive (*.zip);;All files (*)",
            default_suffix=".zip",
        )
        if destination is None:
            return

        def export() -> tuple[str, StatusTone]:
            result = self._operations.export_csv_bundle(destination)
            self.export_tool.date_renderer = lambda: (
                f"Exported {result.csv_file_count} CSV files: {result.destination}\nAnalytical export · {_format_local_timestamp(result.exported_at, widget=self)}"
            )
            return (
                self.export_tool.date_renderer(),
                StatusTone.SUCCESS,
            )

        self._run(self.export_tool, export, destination=destination)

    def _repair_search_index(self) -> None:
        def repair() -> tuple[str, StatusTone]:
            self._operations.repair_search_index()
            return (
                "Search index repaired from canonical Prediction history.",
                StatusTone.SUCCESS,
            )

        self._run(self.search_tool, repair)

    def _manage_tags(self) -> None:
        dialog = TagManagerDialog(self._operations, self)
        if dialog.archive_error is not None:
            self.archive_refused.emit(dialog.archive_error)
            return
        if dialog.latest_result is not None:
            self._tag_result(*dialog.latest_result)
        dialog.change_committed.connect(self._tag_committed)
        dialog.result_reported.connect(self._tag_result)
        dialog.archive_refused.connect(self.archive_refused)
        dialog.exec()

    def _tag_result(self, message: str, is_error: bool) -> None:
        self.tag_tool.show_result(
            message, StatusTone.ERROR if is_error else StatusTone.SUCCESS
        )

    def _tag_committed(self, change) -> None:
        self.tag_tool.show_result(change.message)
        self.tags_changed.emit(change)

    def _choose_destination(
        self,
        *,
        title: str,
        suggested_filename: str,
        file_filter: str,
        default_suffix: str,
    ) -> Path | None:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        initial_path = (
            Path(documents) / suggested_filename
            if documents
            else Path(suggested_filename)
        )
        selected, _selected_filter = QFileDialog.getSaveFileName(
            self, title, str(initial_path), file_filter
        )
        if not selected:
            return None
        destination = Path(selected)
        return (
            destination
            if destination.suffix
            else destination.with_suffix(default_suffix)
        )

    def _show_last_backup(self, value: datetime | None) -> None:
        self.last_backup_label.setText(
            "Last successful backup: Not yet"
            if value is None
            else f"Last successful backup: {_format_local_timestamp(value, widget=self)}"
        )
        self.last_backup_label.setToolTip(
            value.isoformat() if value is not None else ""
        )


def _format_local_timestamp(value: datetime, *, widget: QWidget | None = None) -> str:
    return format_datetime(value, widget)
