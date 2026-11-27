"""Compact reading labels within focused Prediction forms."""

from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


def compact_form_layout(form: QWidget) -> None:
    """Keep spare form height out of headings, context and field captions."""
    layout = form.layout()
    if isinstance(layout, QVBoxLayout) and not form.property("reckonsolveFormSpacer"):
        layout.addStretch()
        form.setProperty("reckonsolveFormSpacer", True)
    for label in form.findChildren(QLabel):
        policy = label.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        if label.wordWrap():
            # Measure at the available width, not QLabel's preferred width.
            # Keep the full measured height inside scrollable forms.
            policy.setHeightForWidth(True)
            policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
            label.setMinimumWidth(0)
        else:
            policy.setVerticalPolicy(QSizePolicy.Policy.Maximum)
        label.setSizePolicy(policy)
