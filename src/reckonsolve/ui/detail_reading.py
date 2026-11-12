"""Small reading treatments shared by the four Prediction contracts."""

from functools import wraps

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.quantiles import FiveQuantiles
from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    TextRole,
    apply_action_role,
    apply_text_role,
)


def timeline_controls(
    heading: QWidget, jump: QPushButton, order: QComboBox, parent: QWidget
) -> QWidget:
    """Keep reading navigation beside Timeline, wrapping in a narrow writing pane."""
    row = QWidget(parent)
    row.setObjectName("detailTimelineControls")
    row.setAccessibleName("Timeline controls")
    outer = QVBoxLayout(row)
    outer.setContentsMargins(int(Spacing.ORDINARY), 0, int(Spacing.ORDINARY), 0)
    controls = QWidget(row)
    layout = FlowLayout(controls)
    outer.addWidget(controls)
    apply_action_role(jump, ActionRole.QUIET)
    jump.setToolTip("Jump to the saved revision establishing the current forecast.")
    heading.setMinimumHeight(max(jump.sizeHint().height(), order.sizeHint().height()))
    for control in (heading, jump, order):
        control.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        layout.addWidget(control)
    return row


def interval_text(values: FiveQuantiles, unit: str) -> str:
    return (
        f"90% interval: {values.q05} – {values.q95} {unit}\n"
        f"Median: {values.q50} {unit}\n"
        f"50% interval: {values.q25} – {values.q75} {unit}"
    )


def progressive_body(label: QLabel) -> QWidget:
    """Keep the full selectable body as the search target; shorten ordinary reading."""
    if len(label.text()) <= 450 and label.text().count("\n") < 6:
        return label
    wrapper = collapse_section(label, "Read full entry")
    preview = QLabel(label.text()[:300].rstrip() + "…", wrapper)
    preview.setWordWrap(True)
    preview.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(preview, TextRole.BODY)
    wrapper.layout().insertWidget(0, preview)
    wrapper.disclosure_button.toggled.connect(preview.setHidden)
    return wrapper


def current_marker(row: QWidget) -> None:
    label = QLabel("Current committed revision", row)
    label.setObjectName("currentCommittedRevisionMarker")
    apply_text_role(label, TextRole.LABEL)
    row.layout().insertWidget(0, label)


def quiet_event(row: QWidget) -> None:
    """Use type/spacing for narrative events rather than competing forecast cards."""
    from reckonsolve.ui.visual_system import SurfaceRole, apply_surface_role

    apply_surface_role(row, SurfaceRole.CANVAS)
    row.setStyleSheet("QFrame { border: 0; }")


def reading_dialog(parent: QWidget, title: str, text: str) -> QDialog:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(840, 580)
    layout = QVBoxLayout(dialog)
    body = QLabel(text, dialog)
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setWordWrap(True)
    body.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    scroll = QScrollArea(dialog)
    scroll.setWidgetResizable(True)
    scroll.setWidget(body)
    layout.addWidget(scroll)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.open()
    return dialog


def criteria_reader(section: QWidget, label: QLabel) -> QPushButton:
    button = QPushButton("Read full criteria", section)
    apply_action_role(button, ActionRole.QUIET)
    button.clicked.connect(
        lambda: reading_dialog(section, "Resolution Criteria", label.text())
    )
    section.layout().addWidget(button)
    return button


def reset_disclosures(root: QWidget) -> None:
    for group in root.findChildren(QGroupBox):
        if group.isCheckable():
            group.setChecked(False)
    for widget in root.findChildren(QWidget):
        toggle = getattr(widget, "disclosure_button", None)
        if toggle is not None:
            toggle.setChecked(False)
            widget.disclosure_body.hide()


def reading_refresh(method):
    """Fresh visits collapse detail; an ongoing task retains consultation state."""

    @wraps(method)
    def refresh(screen, prediction):
        workspace = screen.workspace
        keep = workspace.editor is not None
        groups = (
            [
                (group.objectName(), group.isChecked())
                for group in screen.findChildren(QGroupBox)
                if group.isCheckable()
            ]
            if keep
            else []
        )
        disclosures = (
            [
                (widget.objectName(), widget.disclosure_button.isChecked())
                for widget in screen.findChildren(QWidget)
                if hasattr(widget, "disclosure_button")
            ]
            if keep
            else []
        )
        positions = [
            pane.verticalScrollBar().value()
            for pane in (workspace.timeline, workspace.overview)
        ]
        result = method(screen, prediction)
        reset_disclosures(screen)
        for name, checked in groups:
            group = screen.findChild(QGroupBox, name)
            if group is not None:
                group.setChecked(checked)
        for name, checked in disclosures:
            widget = screen.findChild(QWidget, name)
            if widget is not None:
                widget.disclosure_button.setChecked(checked)
        chart = getattr(screen, "chart_disclosure", None)
        if chart is not None and prediction is not None:
            from reckonsolve.domain.predictions import PredictionStatus

            invalid = prediction.status is PredictionStatus.INVALID
            chart.disclosure_button.setVisible(invalid)
            if not invalid:
                chart.disclosure_body.show()
        if keep:
            for pane, value in zip(
                (workspace.timeline, workspace.overview), positions, strict=True
            ):
                pane.verticalScrollBar().setValue(value)
        return result

    return refresh
