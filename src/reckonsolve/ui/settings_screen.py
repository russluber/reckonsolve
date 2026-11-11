"""Settings adapter: recovery tools, appearance and current keyboard help."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
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
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.presentation_settings import AppearanceMode
from reckonsolve.ui.tag_manager import TagManagerDialog
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
)


class AttentionSettingsOperations(Protocol):
    """Application operations used by the focused Settings screen."""

    def get_stale_threshold_days(self) -> int:
        """Return the persisted threshold."""

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist a validated threshold."""

    def get_data_management_status(self) -> DataManagementStatus:
        """Return recovery status and suggested destination names."""

    def create_backup(self, destination: Path) -> BackupResult:
        """Create a complete SQLite recovery artifact."""

    def export_csv_bundle(self, destination: Path) -> CsvExportResult:
        """Create a documented relational CSV ZIP."""

    def repair_search_index(self) -> None:
        """Rebuild the disposable search projection from canonical history."""


class SettingsScreen(QWidget):
    """Expose the small set of v0.1 attention and data-management controls."""

    appearance_changed = Signal(object)
    routine_notification_requested = Signal(str)

    def __init__(
        self,
        operations: AttentionSettingsOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScreen")
        self._operations = operations
        self._suggested_backup_filename = "reckonsolve-backup.sqlite3"
        self._suggested_export_filename = "reckonsolve-export.zip"

        header = PageHeader(
            "Settings",
            "Manage appearance and local recovery data.",
            title_object_name="settingsScreenTitle",
            supporting_object_name="settingsIntroduction",
            parent=self,
        )
        header.setObjectName("settingsPageHeader")

        appearance_group = ContentPanel("Appearance", parent=self)
        self.appearance_mode = QComboBox(appearance_group.body)
        self.appearance_mode.setObjectName("appearanceMode")
        self.appearance_mode.setAccessibleName("Appearance")
        for title, mode in (
            ("Follow Windows", AppearanceMode.FOLLOW_WINDOWS),
            ("Light", AppearanceMode.LIGHT),
            ("Dark", AppearanceMode.DARK),
        ):
            self.appearance_mode.addItem(title, mode)
        appearance_group.body_layout.addWidget(self.appearance_mode)
        self.appearance_mode.currentIndexChanged.connect(
            lambda: self.appearance_changed.emit(
                AppearanceMode(self.appearance_mode.currentData())
            )
        )

        data_group = ContentPanel(
            "Data and recovery",
            "Create a complete recovery copy or a portable analytical export.",
            parent=self,
        )
        data_group.setObjectName("dataManagementPanel")
        data_layout = data_group.body_layout
        data_description = QLabel(
            "A SQLite backup can restore the complete application. A CSV bundle "
            "is a portable analytical export and cannot restore Reckonsolve.",
            data_group.body,
        )
        data_description.setObjectName("dataManagementDescription")
        data_description.setWordWrap(True)
        data_description.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(data_description, TextRole.SECONDARY)

        self.database_path_label = QLabel("Database: loading...", data_group.body)
        self.database_path_label.setObjectName("databaseLocation")
        self.database_path_label.setWordWrap(True)
        self.database_path_label.setTextFormat(Qt.TextFormat.PlainText)
        self.database_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        apply_text_role(self.database_path_label, TextRole.BODY)

        self.last_backup_label = QLabel(
            "Last successful backup: loading...",
            data_group.body,
        )
        self.last_backup_label.setObjectName("lastSuccessfulBackup")
        self.last_backup_label.setTextFormat(Qt.TextFormat.PlainText)
        self.last_backup_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        apply_text_role(self.last_backup_label, TextRole.SECONDARY)

        self.backup_button = QPushButton("Back Up Now", data_group.body)
        self.backup_button.setObjectName("backUpNowButton")
        self.backup_button.setToolTip("Create a complete recoverable SQLite backup")
        apply_action_role(self.backup_button, ActionRole.PRIMARY)
        apply_lucide_icon(self.backup_button, LucideIcon.DATABASE_BACKUP)
        self.backup_button.clicked.connect(self._back_up_now)
        self.export_button = QPushButton("Export CSV Bundle", data_group.body)
        self.export_button.setObjectName("exportCsvBundleButton")
        self.export_button.setToolTip(
            "Create a portable analytical CSV bundle; it cannot restore the app"
        )
        apply_action_role(self.export_button, ActionRole.SECONDARY)
        apply_lucide_icon(self.export_button, LucideIcon.FILE_ARCHIVE)
        self.export_button.clicked.connect(self._export_csv_bundle)
        self.repair_search_button = QPushButton(
            "Repair Search Index",
            data_group.body,
        )
        self.repair_search_button.setObjectName("repairSearchIndexButton")
        self.repair_search_button.setToolTip(
            "Rebuild derived search data from canonical Prediction history"
        )
        apply_action_role(self.repair_search_button, ActionRole.QUIET)
        apply_lucide_icon(self.repair_search_button, LucideIcon.REFRESH)
        self.repair_search_button.clicked.connect(self._repair_search_index)
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.backup_button)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.repair_search_button)
        action_layout.addStretch()

        self.data_status_label = PersistentMessageLabel(
            accessible_name="Data management result",
            tone=StatusTone.NEUTRAL,
            parent=data_group.body,
        )
        self.data_status_label.setObjectName("dataManagementStatus")

        data_layout.addWidget(data_description)
        data_layout.addWidget(self.database_path_label)
        data_layout.addWidget(self.last_backup_label)
        data_layout.addLayout(action_layout)
        data_layout.addWidget(self.data_status_label)
        self.manage_tags_button = QPushButton("Manage Tags", data_group.body)
        self.manage_tags_button.setObjectName("manageTagsButton")
        apply_action_role(self.manage_tags_button, ActionRole.QUIET)
        self.manage_tags_button.clicked.connect(self._manage_tags)
        data_layout.addWidget(self.manage_tags_button)

        shortcuts_group = ContentPanel(
            "Keyboard shortcuts",
            "Shortcuts respect the current workspace and native modal dialogs.",
            parent=self,
        )
        shortcuts_group.setObjectName("keyboardShortcutsPanel")
        shortcuts_layout = QGridLayout()
        shortcuts_layout.setHorizontalSpacing(int(Spacing.SECTION))
        shortcuts_layout.setVerticalSpacing(int(Spacing.CONTROL))
        shortcut_items = (
            ("New Prediction · Journal, Detail or Performance", "Ctrl+N"),
            ("Focus Journal search · Journal only", "Ctrl+F"),
            ("Settings · outside creation", "Ctrl+,"),
        )
        for index, (action, keys) in enumerate(shortcut_items):
            action_label = QLabel(action, shortcuts_group.body)
            action_label.setTextFormat(Qt.TextFormat.PlainText)
            apply_text_role(action_label, TextRole.BODY)
            key_badge = StatusBadge(
                keys,
                StatusTone.NEUTRAL,
                parent=shortcuts_group.body,
            )
            key_badge.setAccessibleName(f"{action}: {keys}")
            shortcuts_layout.addWidget(action_label, index, 0)
            shortcuts_layout.addWidget(
                key_badge,
                index,
                1,
                alignment=Qt.AlignmentFlag.AlignLeft,
            )
        shortcuts_layout.setColumnStretch(0, 1)
        shortcuts_group.body_layout.addLayout(shortcuts_layout)

        content = QWidget(self)
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(int(Spacing.SECTION))
        content_layout.addWidget(appearance_group)
        content_layout.addWidget(data_group)
        content_layout.addWidget(shortcuts_group)
        content_layout.addStretch()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("settingsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.ORDINARY))
        layout.addWidget(header)
        layout.addWidget(self.scroll_area, 1)

        self.setTabOrder(self.appearance_mode, self.backup_button)
        self.setTabOrder(self.backup_button, self.export_button)
        self.setTabOrder(self.export_button, self.repair_search_button)

    def refresh(self) -> None:
        """Load persisted attention and recovery status when Settings is entered."""

        try:
            status = self._operations.get_data_management_status()
        except ApplicationError as error:
            self._show_data_status(str(error), StatusTone.ERROR)
            return
        self._suggested_backup_filename = status.suggested_backup_filename
        self._suggested_export_filename = status.suggested_export_filename
        self.database_path_label.setText(f"Database: {status.database_path}")
        self._show_last_backup(status.last_successful_backup_at)
        self.data_status_label.clear_message()

    def set_appearance(self, mode: AppearanceMode) -> None:
        with QSignalBlocker(self.appearance_mode):
            self.appearance_mode.setCurrentIndex(self.appearance_mode.findData(mode))

    def _back_up_now(self) -> None:
        destination = self._choose_destination(
            title="Create Reckonsolve Backup",
            suggested_filename=self._suggested_backup_filename,
            file_filter="SQLite database (*.sqlite3);;All files (*)",
            default_suffix=".sqlite3",
        )
        if destination is None:
            return
        try:
            result = self._operations.create_backup(destination)
        except ApplicationError as error:
            self._show_data_status(str(error), StatusTone.ERROR)
            return
        self._show_last_backup(result.completed_at)
        message = f"Backup created: {result.destination}"
        if not result.last_successful_time_recorded:
            message += (
                " The file is usable, but its successful time could not be "
                "recorded in Settings."
            )
        self._show_data_status(
            message,
            (
                StatusTone.SUCCESS
                if result.last_successful_time_recorded
                else StatusTone.WARNING
            ),
        )

    def _manage_tags(self) -> None:
        self._tag_manager_dialog = TagManagerDialog(self._operations, self)
        self._tag_manager_dialog.show()

    def _export_csv_bundle(self) -> None:
        destination = self._choose_destination(
            title="Export Reckonsolve CSV Bundle",
            suggested_filename=self._suggested_export_filename,
            file_filter="ZIP archive (*.zip);;All files (*)",
            default_suffix=".zip",
        )
        if destination is None:
            return
        try:
            result = self._operations.export_csv_bundle(destination)
        except ApplicationError as error:
            self._show_data_status(str(error), StatusTone.ERROR)
            return
        self._show_data_status(
            f"Exported {result.csv_file_count} CSV files: {result.destination}",
            StatusTone.SUCCESS,
        )

    def _repair_search_index(self) -> None:
        """Explicitly recreate only derived search data from canonical history."""

        try:
            self._operations.repair_search_index()
        except ApplicationError as error:
            self._show_data_status(str(error), StatusTone.ERROR)
            return
        self._show_data_status(
            "Search index repaired from canonical Prediction history.",
            StatusTone.SUCCESS,
        )

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
            self,
            title,
            str(initial_path),
            file_filter,
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
            else f"Last successful backup: {_format_local_timestamp(value)}"
        )

    def _show_data_status(self, message: str, tone: StatusTone) -> None:
        self.data_status_label.show_message(message, tone)


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")
