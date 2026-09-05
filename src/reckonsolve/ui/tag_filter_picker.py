"""Compact searchable multi-select tag control for the Predictions archive."""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    QSize,
    QStringListModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QCompleter,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


class _FlowLayout(QLayout):
    """Lay compact children left-to-right and wrap them onto new rows."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(int(Spacing.CONTROL))

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )

    def clear_widgets(self) -> None:
        """Remove and schedule deletion for every chip widget."""

        while self._items:
            item = self.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()
        self.invalidate()

    def _arrange(self, rect: QRect, *, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() + 1 and line_height > 0:
                x = rect.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class TagFilterPicker(QWidget):
    """Search available tags and expose current selections as removable chips."""

    selection_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("predictionTagFilter")
        self.setAccessibleName("Filter predictions by one or more tags")
        self._available_tags: tuple[str, ...] = ()
        self._selected_tags: tuple[str, ...] = ()

        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("predictionTagSearchInput")
        self.search_input.setAccessibleName("Search available prediction tags")
        self.search_input.setPlaceholderText("Search or choose a tag…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setToolTip(
            "Click an empty field to browse every available unselected tag, or "
            "type to narrow the suggestions."
        )
        self.search_input.installEventFilter(self)

        self._completion_model = QStringListModel(self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_input.setCompleter(self._completer)
        self._completer.activated[str].connect(self.select_tag)
        self.search_input.returnPressed.connect(self._select_entered_tag)

        self.empty_label = QLabel("No tags selected", self)
        self.empty_label.setObjectName("predictionTagSelectionEmpty")
        self.empty_label.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(self.empty_label, TextRole.SECONDARY)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.empty_label.setMinimumHeight(
            self.empty_label.fontMetrics().height() + (2 * int(Spacing.COMPACT)) + 2
        )

        self._chip_host = QWidget(self)
        self._chip_host.setObjectName("predictionTagChipRegion")
        self._chip_layout = _FlowLayout(self._chip_host)
        self._chip_host.setHidden(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.COMPACT))
        layout.addWidget(self.search_input)
        layout.addWidget(self.empty_label)
        layout.addWidget(self._chip_host)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Offer all tag choices when the empty picker receives interaction."""

        if watched is self.search_input:
            if event.type() == QEvent.Type.FocusOut:
                self._completer.popup().hide()
            elif (
                event.type() == QEvent.Type.MouseButtonRelease
                and not self.search_input.text()
            ):
                QTimer.singleShot(0, self._show_available_tags)
        return super().eventFilter(watched, event)

    def available_tags(self) -> tuple[str, ...]:
        """Return current canonical choices in their display order."""

        return self._available_tags

    def selected_tags(self) -> tuple[str, ...]:
        """Return selected canonical display names in available-tag order."""

        return self._selected_tags

    def set_available_tags(self, tags: tuple[str, ...]) -> None:
        """Replace suggestions while retaining selections that still exist."""

        self._available_tags = tags
        selected_keys = {tag.casefold() for tag in self._selected_tags}
        retained = tuple(tag for tag in tags if tag.casefold() in selected_keys)
        if retained != self._selected_tags:
            self._selected_tags = retained
            self._render_chips()
        self._refresh_completions()

    def set_selected_tags(self, tags: tuple[str, ...]) -> None:
        """Replace selection without emitting a user-driven change signal."""

        selected_keys = {tag.casefold() for tag in tags}
        selected = tuple(
            tag for tag in self._available_tags if tag.casefold() in selected_keys
        )
        if selected == self._selected_tags:
            return
        self._selected_tags = selected
        self._render_chips()
        self._refresh_completions()

    def clear_selection(self) -> None:
        """Clear every selected tag and notify archive filtering once."""

        if not self._selected_tags:
            return
        self._selected_tags = ()
        self._selection_updated()

    def select_tag(self, tag: str) -> None:
        """Select one exact available tag, ignoring duplicates and unknown text."""

        canonical = self._canonical_tag(tag)
        if canonical is None:
            return
        selected_keys = {item.casefold() for item in self._selected_tags}
        if canonical.casefold() in selected_keys:
            self._finish_completion()
            QTimer.singleShot(0, self._finish_completion)
            return
        selected_keys.add(canonical.casefold())
        self._selected_tags = tuple(
            item for item in self._available_tags if item.casefold() in selected_keys
        )
        self._finish_completion()
        self._selection_updated()
        # QCompleter may insert its activated text after emitting ``activated``.
        # Clear once more on the next event-loop turn so a selected tag never
        # remains as stale input above its chip.
        QTimer.singleShot(0, self._finish_completion)

    def remove_tag(self, tag: str) -> None:
        """Remove one selected tag through its close affordance."""

        key = tag.casefold()
        retained = tuple(item for item in self._selected_tags if item.casefold() != key)
        if retained == self._selected_tags:
            return
        self._selected_tags = retained
        self._selection_updated()
        # The clicked chip is about to be deleted. Keep focus in the tag task
        # instead of allowing Qt to advance into the following Saved View field.
        self.search_input.setFocus(Qt.FocusReason.MouseFocusReason)

    def _select_entered_tag(self) -> None:
        text = self.search_input.text().strip()
        canonical = self._canonical_tag(text)
        if canonical is None:
            matches = tuple(
                tag
                for tag in self._available_tags
                if text.casefold() in tag.casefold() and tag not in self._selected_tags
            )
            if len(matches) == 1:
                canonical = matches[0]
        if canonical is not None:
            self.select_tag(canonical)

    def _canonical_tag(self, candidate: str) -> str | None:
        key = candidate.strip().casefold()
        return next(
            (tag for tag in self._available_tags if tag.casefold() == key),
            None,
        )

    def _selection_updated(self) -> None:
        self._render_chips()
        self._refresh_completions()
        self.selection_changed.emit()

    def _refresh_completions(self) -> None:
        selected_keys = {tag.casefold() for tag in self._selected_tags}
        self._completion_model.setStringList(
            [tag for tag in self._available_tags if tag.casefold() not in selected_keys]
        )

    def _show_available_tags(self) -> None:
        if not self.search_input.hasFocus() or not self._completion_model.rowCount():
            return
        self._completer.setCompletionPrefix("")
        self._completer.popup().setMinimumWidth(self.search_input.width())
        self._completer.complete()

    def _finish_completion(self) -> None:
        self.search_input.clear()
        self._completer.popup().hide()

    def _render_chips(self) -> None:
        self._chip_layout.clear_widgets()
        for index, tag in enumerate(self._selected_tags):
            chip = QPushButton(f"{tag}  ×", self._chip_host)
            chip.setObjectName(f"predictionTagChip{index}")
            chip.setAccessibleName(f"Remove tag {tag}")
            chip.setProperty("reckonsolveTagChip", True)
            chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            chip.clicked.connect(
                lambda _checked=False, selected_tag=tag: self.remove_tag(selected_tag)
            )
            self._chip_layout.addWidget(chip)
        has_selection = bool(self._selected_tags)
        self.empty_label.setHidden(has_selection)
        self._chip_host.setHidden(not has_selection)
        self._chip_host.updateGeometry()
        self.updateGeometry()


__all__ = ["TagFilterPicker"]
