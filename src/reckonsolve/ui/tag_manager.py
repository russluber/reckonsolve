"""Secondary desktop workflow for deliberate global tag maintenance."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.tags import (
    TagDeletePreview,
    TagLibraryItem,
    TagMergePreview,
    TagRenamePreview,
)
from reckonsolve.ui.components import ContentPanel, PersistentMessageLabel
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
)


class TagManagementOperations(Protocol):
    """Application boundary consumed by the secondary tag-library dialog."""

    def list_tags(self, name_filter: str = "") -> tuple[TagLibraryItem, ...]: ...

    def preview_tag_rename(self, tag_id: int, name: str) -> TagRenamePreview: ...

    def rename_tag(self, preview: TagRenamePreview) -> None: ...

    def preview_tag_merge(
        self,
        source_tag_ids: tuple[int, ...],
        target_tag_id: int,
    ) -> TagMergePreview: ...

    def merge_tags(self, preview: TagMergePreview) -> None: ...

    def preview_tag_delete(self, tag_id: int) -> TagDeletePreview: ...

    def delete_tag(self, preview: TagDeletePreview) -> None: ...


class TagManagerDialog(QDialog):
    """List, filter, rename, merge, and delete retained reusable tags."""

    def __init__(
        self,
        operations: TagManagementOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("tagManagerDialog")
        self.setWindowTitle("Manage Tags")
        self.setModal(True)
        self.resize(680, 440)
        self._operations = operations
        self._tags_by_id: dict[int, TagLibraryItem] = {}
        self.changed = False

        title = QLabel("Manage Tags", self)
        title.setObjectName("tagManagerTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(title, TextRole.PAGE_TITLE)

        introduction = QLabel(
            "Rename, merge, or delete reusable tags across Predictions and Saved "
            "Views. Forecast and Journal history are not changed.",
            self,
        )
        introduction.setObjectName("tagManagerIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(introduction, TextRole.SECONDARY)

        filter_label = QLabel("Filter tags", self)
        self.filter_input = QLineEdit(self)
        self.filter_input.setObjectName("tagManagerFilter")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.setPlaceholderText("Type part of a tag name")
        self.filter_input.setAccessibleName("Filter the tag library")
        filter_label.setBuddy(self.filter_input)
        apply_text_role(filter_label, TextRole.LABEL)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_input, 1)

        self.table = QTableWidget(0, 3, self)
        self.table.setObjectName("tagManagerTable")
        self.table.setAccessibleName("Tag library")
        self.table.setAccessibleDescription(
            "Tags with their current Prediction and Saved View association counts."
        )
        self.table.setHorizontalHeaderLabels(("Tag", "Predictions", "Saved Views"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.rename_button = QPushButton("Rename…", self)
        self.rename_button.setObjectName("renameTagButton")
        apply_lucide_icon(self.rename_button, LucideIcon.PENCIL)
        self.merge_button = QPushButton("Merge selected…", self)
        self.merge_button.setObjectName("mergeTagsButton")
        apply_lucide_icon(self.merge_button, LucideIcon.LIST_FILTER)
        self.delete_button = QPushButton("Delete…", self)
        self.delete_button.setObjectName("deleteTagButton")
        apply_lucide_icon(self.delete_button, LucideIcon.TRASH)
        apply_action_role(self.rename_button, ActionRole.SECONDARY)
        apply_action_role(self.merge_button, ActionRole.SECONDARY)
        apply_action_role(self.delete_button, ActionRole.DESTRUCTIVE)

        actions = QHBoxLayout()
        actions.addWidget(self.rename_button)
        actions.addWidget(self.merge_button)
        actions.addWidget(self.delete_button)
        actions.addStretch()

        self.status_label = PersistentMessageLabel(
            accessible_name="Tag management status",
            parent=self,
        )
        self.status_label.setObjectName("tagManagerStatus")

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_buttons.setObjectName("tagManagerCloseButtons")
        close_button = close_buttons.button(QDialogButtonBox.StandardButton.Close)
        apply_action_role(close_button, ActionRole.QUIET)

        library_panel = ContentPanel(
            "Tag library",
            "Counts show current Prediction and Saved View use.",
            parent=self,
        )
        library_panel.setObjectName("tagManagerLibraryPanel")
        library_panel.body_layout.addLayout(filter_layout)
        library_panel.body_layout.addWidget(self.table, 1)
        library_panel.body_layout.addLayout(actions)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
        )
        layout.setSpacing(int(Spacing.ORDINARY))
        layout.addWidget(title)
        layout.addWidget(introduction)
        layout.addWidget(library_panel, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(close_buttons)

        self.setTabOrder(self.filter_input, self.table)
        self.setTabOrder(self.table, self.rename_button)
        self.setTabOrder(self.rename_button, self.merge_button)
        self.setTabOrder(self.merge_button, self.delete_button)
        self.setTabOrder(self.delete_button, close_button)

        self.filter_input.textChanged.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.rename_button.clicked.connect(self._rename_selected)
        self.merge_button.clicked.connect(self._merge_selected)
        self.delete_button.clicked.connect(self._delete_selected)
        close_buttons.rejected.connect(self.reject)
        self.refresh()

    def refresh(self) -> None:
        """Reload current counts while preserving stable-ID selection."""

        selected_ids = set(self._selected_tag_ids())
        try:
            tags = self._operations.list_tags(self.filter_input.text())
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            return
        self._tags_by_id = {tag.tag_id: tag for tag in tags}
        self.table.setRowCount(len(tags))
        for row, tag in enumerate(tags):
            name_item = QTableWidgetItem(tag.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, tag.tag_id)
            prediction_count = QTableWidgetItem(str(tag.prediction_count))
            prediction_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            saved_view_count = QTableWidgetItem(str(tag.saved_view_count))
            saved_view_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, prediction_count)
            self.table.setItem(row, 2, saved_view_count)
            if tag.tag_id in selected_ids:
                self.table.selectRow(row)
        self._update_action_state()

    def _rename_selected(self) -> None:
        selected = self._selected_tags()
        if len(selected) != 1:
            return
        current = selected[0]
        proposed, accepted = QInputDialog.getText(
            self,
            "Rename Tag",
            "New tag name:",
            text=current.display_name,
        )
        if not accepted:
            return
        try:
            preview = self._operations.preview_tag_rename(current.tag_id, proposed)
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            return
        answer = QMessageBox.question(
            self,
            "Confirm Tag Rename",
            f"Rename {current.display_name!r} to "
            f"{preview.proposed_display_name!r}?\n\n"
            f"Affected Predictions: {preview.prediction_count}\n"
            "Saved View references retain this tag's stable identity.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._operations.rename_tag(preview)
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            self.refresh()
            return
        self.changed = True
        self._show_status(
            f"Renamed {current.display_name!r} to {preview.proposed_display_name!r}."
        )
        self.refresh()

    def _merge_selected(self) -> None:
        selected = self._selected_tags()
        if len(selected) < 2:
            return
        labels = [tag.display_name for tag in selected]
        target_name, accepted = QInputDialog.getItem(
            self,
            "Merge Tags",
            "Keep this target tag:",
            labels,
            0,
            False,
        )
        if not accepted:
            return
        target = next(tag for tag in selected if tag.display_name == target_name)
        sources = tuple(tag for tag in selected if tag.tag_id != target.tag_id)
        try:
            preview = self._operations.preview_tag_merge(
                tuple(tag.tag_id for tag in sources),
                target.tag_id,
            )
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            return
        source_names = ", ".join(repr(tag.display_name) for tag in sources)
        answer = QMessageBox.question(
            self,
            "Confirm Tag Merge",
            f"Merge {source_names} into {target.display_name!r}?\n\n"
            f"Affected Predictions: {preview.prediction_count}\n"
            f"Affected Saved Views: {preview.saved_view_count}\n\n"
            "Source tags will be removed. Prediction and Saved View references "
            "will be retargeted and deduplicated.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._operations.merge_tags(preview)
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            self.refresh()
            return
        self.changed = True
        self._show_status(f"Merged {source_names} into {target.display_name!r}.")
        self.refresh()

    def _delete_selected(self) -> None:
        selected = self._selected_tags()
        if len(selected) != 1:
            return
        current = selected[0]
        try:
            preview = self._operations.preview_tag_delete(current.tag_id)
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            return
        saved_view_warning = ""
        if preview.saved_view_count:
            saved_view_warning = (
                "\n\nAffected Saved Views will lose this tag condition and may "
                "return a broader set of Predictions."
            )
        answer = QMessageBox.question(
            self,
            "Confirm Tag Deletion",
            f"Delete tag {current.display_name!r}?\n\n"
            f"Prediction associations removed: {preview.prediction_count}\n"
            f"Saved View references removed: {preview.saved_view_count}"
            f"{saved_view_warning}\n\n"
            "Forecast, Journal, terminal, and scoring history will not change.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._operations.delete_tag(preview)
        except ApplicationError as error:
            self._show_status(str(error), is_error=True)
            self.refresh()
            return
        self.changed = True
        self._show_status(f"Deleted tag {current.display_name!r}.")
        self.refresh()

    def _selected_tag_ids(self) -> tuple[int, ...]:
        return tuple(tag.tag_id for tag in self._selected_tags())

    def _selected_tags(self) -> tuple[TagLibraryItem, ...]:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        selected: list[TagLibraryItem] = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is None:
                continue
            tag = self._tags_by_id.get(int(item.data(Qt.ItemDataRole.UserRole)))
            if tag is not None:
                selected.append(tag)
        return tuple(selected)

    def _update_action_state(self) -> None:
        count = len(self._selected_tags())
        self.rename_button.setEnabled(count == 1)
        self.merge_button.setEnabled(count >= 2)
        self.delete_button.setEnabled(count == 1)

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self.status_label.show_message(
            message,
            StatusTone.ERROR if is_error else StatusTone.SUCCESS,
        )
