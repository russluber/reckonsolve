"""Persistent reading context, independent panes and one guarded writing task."""

from datetime import datetime

from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.creation_task import form_values
from reckonsolve.ui.date_display import format_datetime
from reckonsolve.ui.visual_system import (
    MotionDuration,
    Spacing,
    TextRole,
    animations_enabled,
    apply_text_role,
)


class DetailWorkspace(QScrollArea):
    """An outer fallback scroll keeps unusually tall headers reachable."""

    task_closed = Signal(str)

    def __init__(self, content: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(content)
        self.column = content.layout()
        self.panes = QWidget(content)
        self.panes.setMinimumHeight(150)
        self.columns = QHBoxLayout(self.panes)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(int(Spacing.SECTION))
        self.timeline, self.timeline_body = self._pane("detailTimelinePane")
        self.timeline_column = QWidget(self.panes)
        self.timeline_column.setMinimumWidth(0)
        self.timeline_column_layout = QVBoxLayout(self.timeline_column)
        self.timeline_column_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_column_layout.setSpacing(int(Spacing.CONTROL))
        self.timeline_column_layout.addWidget(self.timeline, 1)
        self.overview, self.overview_body = self._pane("detailOverviewPane")
        self.tabs = QTabWidget(self.panes)
        self.tabs.setObjectName("detailContextTabs")
        self.tabs.setStyleSheet("QTabWidget#detailContextTabs::pane { border: 0; }")
        self.tabs.addTab(self.overview, "Overview")
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._tab_changed)
        self.columns.addWidget(self.timeline_column, 3)
        self.columns.addWidget(self.tabs, 2)
        self.editor: QDialog | None = None
        self.editor_scroll: QScrollArea | None = None
        self.kind = ""
        self._baseline: tuple = ()
        self.inline = False
        self.single_column = False
        self.reading_proportion = 600
        self.overview_heading: QLabel | None = None
        self._proportion = 600
        self._transition = QVariantAnimation(self)
        self._transition.setDuration(int(MotionDuration.DISCLOSURE))
        self._transition.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._transition.valueChanged.connect(self._set_proportion)
        self._transition.finished.connect(self._finish_transition)
        self._timeline_scroll_policy = None

    def set_timeline_controls(self, controls: QWidget) -> None:
        """Keep history navigation reachable independently of its scroll position."""
        self.timeline_column_layout.insertWidget(0, controls)

    def set_reading_context(self, heading: QLabel, *, terminal: bool) -> None:
        self.overview_heading = heading
        self.reading_proportion = 500 if terminal else 600
        self.tabs.setTabText(
            0,
            "Archival Context" if heading.text() == "ARCHIVAL CONTEXT" else "Overview",
        )
        self._tab_changed(self.tabs.currentIndex())

    def _sync_context_heading(self) -> None:
        if self.overview_heading is not None:
            # The tab already names the reading context beside an unsaved task.
            self.overview_heading.setVisible(self.editor is None or self.inline)

    def _pane(self, name: str) -> tuple[QScrollArea, QWidget]:
        scroll = QScrollArea(self.panes)
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.ORDINARY))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        return scroll, body

    def compose(
        self,
        summary: QWidget,
        actions: QWidget,
        timeline: list[QWidget],
        overview: list[QWidget],
    ) -> None:
        while self.column.count():
            self.column.takeAt(0)
        self.column.setContentsMargins(16, 8, 16, 16)
        self.column.setSpacing(10)
        self.column.addWidget(summary)
        self.column.addWidget(actions)
        self.column.addWidget(self.panes, 1)
        for widget in timeline:
            self.timeline_body.layout().addWidget(widget)
        for widget in overview:
            self.overview_body.layout().addWidget(widget)

    def ensureWidgetVisible(
        self, widget: QWidget, xmargin: int = 50, ymargin: int = 50
    ) -> None:
        for pane in (self.timeline, self.overview, self.editor_scroll):
            if (
                pane is not None
                and pane.widget() is not None
                and pane.widget().isAncestorOf(widget)
            ):
                if pane is self.overview:
                    self.tabs.setCurrentIndex(0)
                elif pane is self.editor_scroll:
                    self.tabs.setCurrentIndex(1)
                pane.ensureWidgetVisible(widget, xmargin, ymargin)
                if self.verticalScrollBar().maximum() > 0:
                    super().ensureWidgetVisible(self.panes, 0, 0)
                return
        super().ensureWidgetVisible(widget, xmargin, ymargin)

    @property
    def dirty(self) -> bool:
        return (
            self.editor is not None and form_values(self.editor, ()) != self._baseline
        )

    def prepare_task(self, kind: str) -> bool:
        if self.editor is not None and self.kind == kind:
            if not self.inline:
                self.tabs.setCurrentIndex(1)
            self.ensureWidgetVisible(self.editor)
            self.editor.setFocus()
            return False
        return self.confirm_exit(
            "write Journal" if kind == "Journal" else "switch to " + kind
        )

    def confirm_exit(self, destination: str = "return") -> bool:
        if self.editor is not None and self.dirty:
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Leave entered work?")
            dialog.setText(
                f"Discard the entered {self.kind.lower()} work and {destination}?"
            )
            keep = dialog.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
            label = (
                "Discard revision and start New"
                if destination == "start New" and self.kind == "Revision"
                else "Discard revision and write Journal"
                if destination == "write Journal" and self.kind == "Revision"
                else "Discard changes and return"
                if destination == "return"
                else "Discard changes and continue"
            )
            discard = dialog.addButton(label, QMessageBox.ButtonRole.DestructiveRole)
            dialog.setDefaultButton(keep)
            dialog.exec()
            if dialog.clickedButton() is not discard:
                return False
        self.clear_editor()
        return True

    def begin_editor(self, editor: QDialog, kind: str) -> None:
        self.inline = False
        self.editor, self.kind = editor, kind
        editor.setProperty("contextualEditor", True)
        editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        editor.setMinimumSize(0, 0)
        for inner in editor.findChildren(
            QScrollArea, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            body = inner.takeWidget()
            if body is not None:
                editor.layout().replaceWidget(inner, body)
                body.setParent(editor)
                body.show()
                inner.hide()
                inner.deleteLater()
        editor.setModal(False)
        editor.setParent(self)
        editor.setWindowFlags(Qt.WindowType.Widget)
        scroll, _body = self._pane("detailWritingPane")
        old = scroll.takeWidget()
        old.deleteLater()
        scroll.setWidget(editor)
        self.editor_scroll = scroll
        self.tabs.addTab(scroll, kind + " · unsaved")
        self.tabs.tabBar().show()
        if self.single_column:
            self.tabs.show()
            self.tabs.tabBar().hide()
        self._baseline = form_values(editor, ())
        for buttons in editor.findChildren(QDialogButtonBox):
            save = buttons.button(QDialogButtonBox.StandardButton.Save)
            if save is not None and kind == "Revision":
                save.setText("Commit Revision")
        editor.finished.connect(lambda _result: self.clear_editor())
        self.tabs.setCurrentIndex(1)
        editor.show()
        for field in editor.findChildren(QWidget):
            if (
                isinstance(
                    field,
                    (
                        QLineEdit,
                        QAbstractSpinBox,
                        QPlainTextEdit,
                        QRadioButton,
                        QComboBox,
                        QCheckBox,
                    ),
                )
                and field.isVisible()
                and field.isEnabled()
            ):
                field.setFocus(Qt.FocusReason.OtherFocusReason)
                break

    def begin_inline_editor(self, editor: QDialog, parent: QWidget) -> None:
        """One-Shot reflection stays below its results, sharing exit protection."""
        self.editor, self.kind, self.inline = editor, "Postmortem", True
        editor.setParent(parent)
        editor.setWindowFlags(Qt.WindowType.Widget)
        parent.layout().addWidget(editor)
        self._baseline = form_values(editor, ())
        editor.finished.connect(lambda _result: self.clear_editor())
        editor.show()
        self.ensureWidgetVisible(editor)

    def clear_reading(self) -> None:
        """Refresh reading widgets without deleting a retained contextual task."""
        self.overview_heading = None
        if self.inline and self.editor is not None:
            self.editor.setParent(self)
        for body in (self.timeline_body, self.overview_body):
            while body.layout().count():
                item = body.layout().takeAt(0)
                if item.widget() is not None:
                    item.widget().hide()
                    item.widget().deleteLater()
        while self.column.count():
            widget = self.column.takeAt(0).widget()
            if widget is not None and widget is not self.panes:
                widget.hide()
                widget.deleteLater()

    def clear_editor(self) -> None:
        if self.editor is None:
            return
        editor, scroll, kind = self.editor, self.editor_scroll, self.kind
        self.editor, self.editor_scroll, self.kind = None, None, ""
        self.tabs.setCurrentIndex(0)
        if scroll is not None:
            self.tabs.removeTab(self.tabs.indexOf(scroll))
            scroll.hide()
            scroll.deleteLater()
        self.tabs.tabBar().hide()
        editor.hide()
        # Detach immediately: a same-turn reopen must find only the new form,
        # before Qt processes deferred deletion of the old scrolling container.
        editor.setParent(None)
        editor.deleteLater()
        self.inline = False
        self._change_proportion(self.reading_proportion)
        self._sync_context_heading()
        if self.single_column:
            self.tabs.hide()
        self.task_closed.emit(kind)

    def _tab_changed(self, index: int) -> None:
        writing = index > 0 and self.kind != "Mark Invalid"
        self._change_proportion(400 if writing else self.reading_proportion)
        self._sync_context_heading()

    def _change_proportion(self, value: int) -> None:
        if (
            self._transition.state() == QVariantAnimation.State.Running
            and self._transition.endValue() == value
        ):
            return
        self._transition.stop()
        self._finish_transition()
        if self.isVisible() and animations_enabled(self) and self._proportion != value:
            # Wrap the long Timeline once at completion, rather than laying out
            # every historical paragraph at each frame. Its real widgets keep
            # their geometry/selection while the viewport boundary moves.
            self._timeline_scroll_policy = self.timeline.horizontalScrollBarPolicy()
            self.timeline.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.timeline.setWidgetResizable(False)
            self._transition.blockSignals(True)
            self._transition.setStartValue(self._proportion)
            self._transition.setEndValue(value)
            self._transition.blockSignals(False)
            self._transition.start()
        else:
            self._set_proportion(value)

    def _finish_transition(self) -> None:
        if self._timeline_scroll_policy is not None:
            self.timeline.setWidgetResizable(True)
            self.timeline.setHorizontalScrollBarPolicy(self._timeline_scroll_policy)
            self._timeline_scroll_policy = None

    def _set_proportion(self, value: int) -> None:
        self._proportion = int(value)
        self.columns.setStretch(0, self._proportion)
        self.columns.setStretch(1, 1000 - self._proportion)


class HeaderTiming(QWidget):
    """Paired committed timing/Deadline labels; no draft-derived facts."""

    def __init__(self, deadline: QWidget, parent: QWidget, caption: str) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        label = QLabel(caption, left)
        label.setWordWrap(True)
        apply_text_role(label, TextRole.SECONDARY)
        left_layout.addWidget(label)
        self.activity = QLabel(self)
        self.activity.setWordWrap(True)
        self.activity.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        apply_text_role(self.activity, TextRole.SECONDARY)
        left_layout.addWidget(self.activity)
        for text in deadline.findChildren(QLabel):
            apply_text_role(text, TextRole.SECONDARY)
            if "deadline" in text.text().lower():
                text.setText("Forecast Deadline")
        row.addWidget(left, 3)
        row.addWidget(deadline, 2)


def collapse_section(
    widget: QWidget, title: str, *, expanded: bool = False, compact: bool = False
) -> QWidget:
    """A disclosure retains selectable content and its original identity."""
    container = QWidget(widget.parentWidget())
    container.setObjectName(widget.objectName() + "Disclosure")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    if compact:
        toggle = QToolButton(container)
        toggle.setText(title.replace("&", "&&"))
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setAutoRaise(True)
        toggle.setProperty("reckonsolveDisclosure", "true")
        toggle.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        apply_text_role(toggle, TextRole.LABEL)

        def update_arrow(checked: bool) -> None:
            toggle.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            )

        toggle.toggled.connect(update_arrow)
        update_arrow(expanded)
    else:
        toggle = QPushButton(title, container)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setAccessibleName(title)
    toggle.toggled.connect(widget.setVisible)
    widget.setVisible(expanded)
    if compact:
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)
    else:
        layout.addWidget(toggle)
    layout.addWidget(widget)
    container.disclosure_button = toggle
    container.disclosure_body = widget
    return container


def exact_detail_time(value: datetime, *, widget: QWidget | None = None) -> str:
    """Readable local time; exact provenance remains available on demand."""
    return format_datetime(value, widget)
