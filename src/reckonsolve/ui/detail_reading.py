"""Small reading treatments shared by the four Prediction contracts."""

from functools import wraps

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.predictions import InvalidationHistory
from reckonsolve.domain.quantiles import FiveQuantiles
from reckonsolve.ui.detail_workspace import collapse_section, exact_detail_time
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    TextRole,
    apply_action_role,
    apply_text_role,
    refresh_widget_style,
)


class TerminalSummary(QWidget):
    """Lead terminal reading with supplied facts, never recalculate a score."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("detailTerminalSummary")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        metrics = QHBoxLayout()
        self.outcome = self._label("terminalOutcome", TextRole.FORECAST)
        self.score = self._label("terminalScore", TextRole.FORECAST)
        metrics.addWidget(self.outcome, 1, Qt.AlignmentFlag.AlignTop)
        metrics.addWidget(self.score, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(metrics)
        self.timing = self._label("terminalTiming", TextRole.SECONDARY)
        self.note = self._label("terminalExplanation", TextRole.BODY)
        layout.addWidget(self.timing)
        layout.addWidget(self.note)
        self.facts = self._label("terminalForecastFacts", TextRole.BODY)
        self.context = collapse_section(
            self.facts, "Forecast used for scoring", compact=True
        )
        self.context.setObjectName("terminalForecastContext")
        layout.addWidget(self.context)
        self.hide()

    def _label(self, name: str, role: TextRole) -> QLabel:
        label = QLabel(self)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        apply_text_role(label, role)
        return label

    def set_facts(
        self,
        *,
        outcome: str,
        score: str,
        timing: str,
        note: str,
        context: str,
        context_title: str = "Forecast used for scoring",
        timing_tooltip: str = "",
    ) -> None:
        for label, text in (
            (self.outcome, outcome),
            (self.score, score),
            (self.timing, timing),
            (self.note, note),
            (self.facts, context),
        ):
            label.setText(text)
            label.setVisible(bool(text))
        apply_text_role(
            self.score, TextRole.LABEL if score == "Not scored" else TextRole.FORECAST
        )
        apply_text_role(
            self.outcome,
            TextRole.SECTION_TITLE
            if outcome == "Recorded reason"
            else TextRole.FORECAST,
        )
        self.context.disclosure_button.setText(context_title)
        self.timing.setToolTip(timing_tooltip or timing)
        self.context.disclosure_button.setAccessibleName(context_title)
        self.context.disclosure_button.setChecked(False)
        self.context.disclosure_body.hide()
        self.context.setVisible(bool(context))
        self.show()


def invalidation_timing(
    original: str, history: InvalidationHistory | None, *, widget: QWidget | None = None
) -> str:
    """Keep the decision date separate from a later reason correction."""
    if history is None or not history.corrections:
        return original
    return (
        original
        + "\nReason corrected: "
        + exact_detail_time(history.corrections[-1].corrected_at, widget=widget)
        + " · Original decision date unchanged"
    )


def invalidation_exact_timing(history: InvalidationHistory | None) -> str:
    """Keep subminute instants inspectable beside human-readable dates."""
    if history is None:
        return ""
    text = "Marked Invalid: " + history.original.invalidated_at.isoformat()
    if history.corrections:
        text += (
            "\nReason corrected: " + history.corrections[-1].corrected_at.isoformat()
        )
    return text


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


def interval_transition_text(
    before: FiveQuantiles, after: FiveQuantiles, unit: str
) -> str:
    """Present complete changed forecasts without rounding or dropping endpoints."""
    return (
        f"90% interval: {before.q05} – {before.q95} → {after.q05} – {after.q95} {unit}\n"
        f"Median: {before.q50} → {after.q50} {unit}\n"
        f"50% interval: {before.q25} – {before.q75} → {after.q25} – {after.q75} {unit}"
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
    label = QLabel("Current Committed Revision", row)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
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


def reset_disclosures(root: QWidget, *, clear_matches: bool = False) -> None:
    for group in root.findChildren(QGroupBox):
        if group.isCheckable():
            group.setChecked(False)
    for widget in root.findChildren(QWidget):
        if clear_matches and widget.property("searchMatchEmphasis"):
            widget.setProperty("searchMatchEmphasis", False)
            refresh_widget_style(widget)
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
        reset_disclosures(screen, clear_matches=not keep)
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
        distribution = getattr(screen, "distribution_disclosure", None)
        if distribution is not None and prediction is not None:
            from reckonsolve.domain.predictions import PredictionStatus

            terminal = prediction.status in (
                PredictionStatus.RESOLVED,
                PredictionStatus.INVALID,
            )
            distribution.disclosure_button.setVisible(terminal)
            if not terminal:
                distribution.disclosure_body.show()
        if keep:
            for pane, value in zip(
                (workspace.timeline, workspace.overview), positions, strict=True
            ):
                pane.verticalScrollBar().setValue(value)
        return result

    return refresh
