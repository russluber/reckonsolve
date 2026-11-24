"""Compact reading labels within focused Prediction forms."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


def compact_form_layout(form: QWidget) -> None:
    """Keep spare form height out of headings, context and field captions."""
    if form.layout() is not None:
        form.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
    for label in form.findChildren(QLabel):
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        if label.wordWrap():
            label.setMinimumWidth(0)
