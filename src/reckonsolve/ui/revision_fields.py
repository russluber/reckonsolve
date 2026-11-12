"""Aligned current/draft Numeric elicitation using the existing exact fields."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from reckonsolve.domain.quantiles import FiveQuantiles
from reckonsolve.ui.quantile_input import FiveQuantileInput
from reckonsolve.ui.visual_system import TextRole, apply_text_role


def align_numeric_revision(editor: FiveQuantileInput, quantiles: FiveQuantiles) -> None:
    editor.preview_enabled = False
    editor.update_preview()
    grid = editor.layout().itemAt(0).layout()
    while grid.count():
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None and widget not in editor.inputs.values():
            widget.hide()
            widget.deleteLater()
    for column, title in ((1, "Current committed"), (2, "Draft revision")):
        label = QLabel(title, editor)
        label.setWordWrap(True)
        apply_text_role(label, TextRole.LABEL)
        grid.addWidget(label, 0, column)
    current = dict(zip((5, 25, 50, 75, 95), quantiles.values, strict=True))
    for row, (title, levels) in enumerate(
        (("90% interval", (5, 95)), ("Median", (50,)), ("50% interval", (25, 75))), 1
    ):
        label = QLabel(
            title + "\n" + " · ".join(f"{level}th" for level in levels), editor
        )
        label.setWordWrap(True)
        grid.addWidget(label, row, 0)
        saved = QLabel(" to ".join(str(current[level]) for level in levels), editor)
        saved.setWordWrap(True)
        grid.addWidget(saved, row, 1)
        pair = QWidget(editor)
        inputs = QHBoxLayout(pair)
        inputs.setContentsMargins(0, 0, 0, 0)
        for level in levels:
            field = editor.inputs[level]
            field.setParent(pair)
            inputs.addWidget(field)
            field.show()
        grid.addWidget(pair, row, 2)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 2)
