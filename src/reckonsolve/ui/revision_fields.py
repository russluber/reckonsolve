"""Responsive current/draft comparisons for the existing exact Numeric fields."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

from reckonsolve.domain.quantiles import QUANTILE_LEVELS, FiveQuantiles
from reckonsolve.ui.quantile_input import FiveQuantileInput
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


def align_numeric_revision(editor: FiveQuantileInput, quantiles: FiveQuantiles) -> None:
    editor.preview_enabled = False
    editor.update_preview()
    layout = editor.layout()
    old_grid = layout.takeAt(0).layout()
    while old_grid.count():
        widget = old_grid.takeAt(0).widget()
        if widget is not None and widget not in editor.inputs.values():
            widget.hide()
            widget.deleteLater()
    layout.insertWidget(0, _RevisionComparison(editor, quantiles))


class _RevisionComparison(QWidget):
    """Switch layouts without replacing the draft widgets or their input values."""

    def __init__(self, editor: FiveQuantileInput, quantiles: FiveQuantiles) -> None:
        super().__init__(editor)
        self.setObjectName("numericRevisionComparison")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(int(Spacing.CONTROL))
        self.grid.setVerticalSpacing(int(Spacing.CONTROL))
        self.headings = (
            self._label("Current committed"),
            self._label("Draft revision"),
        )
        current = dict(zip(QUANTILE_LEVELS, quantiles.values, strict=True))
        self.rows = []
        for level, title in (
            (5, "90% interval · 5th"),
            (95, "90% interval · 95th"),
            (50, "Median · 50th"),
            (25, "50% interval · 25th"),
            (75, "50% interval · 75th"),
        ):
            field = editor.inputs[level]
            field.setParent(self)
            field.setAccessibleName(f"Draft {field.accessibleName()}")
            label = self._label(title)
            label.setObjectName(f"revisionPercentile{level:02}")
            label.setBuddy(field)
            value = self._label(str(current[level]), TextRole.BODY)
            value.setObjectName(f"revisionCommitted{level:02}")
            value.setAccessibleName(f"Committed {level}th percentile: {current[level]}")
            value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            field.setAccessibleDescription(f"Current committed value: {current[level]}")
            self.rows.append(
                (label, value, field, self._label("Current"), self._label("Draft"))
            )
        self._stacked: bool | None = None
        self._reflow()

    def _label(self, text: str, role: TextRole = TextRole.LABEL) -> QLabel:
        label = QLabel(text, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        apply_text_role(label, role)
        policy = label.sizePolicy()
        policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        label.setSizePolicy(policy)
        return label

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._reflow()

    def _reflow(self) -> None:
        if not getattr(self, "rows", None) or not hasattr(self, "_stacked"):
            return
        heading_width = sum(
            h.fontMetrics().horizontalAdvance(h.text()) for h in self.headings
        )
        percentile_width = max(
            label.fontMetrics().horizontalAdvance(label.text())
            for label, *_ in self.rows
        )
        stacked = self.width() < heading_width + percentile_width + 6 * int(
            Spacing.CONTROL
        )
        if stacked == self._stacked:
            return
        self._stacked = stacked
        while self.grid.count():
            self.grid.takeAt(0)
        for index, heading in enumerate(self.headings, 1):
            heading.setVisible(not stacked)
            if not stacked:
                self.grid.addWidget(heading, 0, index)
        for index, (label, value, field, current_label, draft_label) in enumerate(
            self.rows
        ):
            current_label.setVisible(stacked)
            draft_label.setVisible(stacked)
            if stacked:
                row = 3 * index
                self.grid.addWidget(label, row, 0, 1, 2)
                self.grid.addWidget(current_label, row + 1, 0)
                self.grid.addWidget(value, row + 1, 1)
                self.grid.addWidget(draft_label, row + 2, 0)
                self.grid.addWidget(field, row + 2, 1)
            else:
                row = index + 1
                self.grid.addWidget(label, row, 0)
                self.grid.addWidget(value, row, 1)
                self.grid.addWidget(field, row, 2)
            field.show()
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(2, 0 if stacked else 1)
