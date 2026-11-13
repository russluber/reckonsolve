"""Prediction widgets responsibilities extracted from the desktop composition."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from PySide6.QtCore import QDate, QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.one_shot import OneShotJournal
from reckonsolve.domain.predictions import (
    MAX_METADATA_DATE,
    MIN_METADATA_DATE,
    BinaryResolutionHistory,
    DefinitionChange,
    InvalidationHistory,
    InvalidationReasonCorrection,
    NumericResolutionCorrection,
    NumericResolutionHistory,
    PredictionStatus,
    ResolutionCorrection,
)
from reckonsolve.domain.quantiles import (
    QuantileRevision,
    QuantileTimelineEvent,
    quantile_summary,
)
from reckonsolve.forecast_display import format_local_deadline
from reckonsolve.ui.date_display import (
    format_date,
    format_datetime,
    input_date_format,
    update_date_inputs,
)
from reckonsolve.ui.detail_reading import progressive_body, quiet_event
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.one_shot import text_label
from reckonsolve.ui.prediction_contracts import (
    ForecastReviewTimelineSnapshot,
    ForecastTimelineSnapshot,
    JournalTimelineSnapshot,
)
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
    refresh_widget_style,
)


class _StyledDialog(QDialog):
    """Apply the shared dialog grammar after a complete dialog is constructed."""

    def showEvent(self, event: QShowEvent) -> None:
        _apply_dialog_presentation(self)
        update_date_inputs(self)
        super().showEvent(event)


class _EffectiveTimeDialog(_StyledDialog):
    """Reserve wrapped form text's actual minimum height in the new time flows."""

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._fit_time_form()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_time_form()

    def _fit_time_form(self) -> None:
        if getattr(self, "effective_time", None) is None or self.layout() is None:
            return
        layout = self.layout()
        layout.invalidate()
        # minimumSize ignores wrapping. Unlike heightForWidth, this excludes
        # the text editors' preferred tall size while protecting legible inputs.
        height = max(
            layout.minimumSize().height(), layout.minimumHeightForWidth(self.width())
        )
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)


def _date_input_row(toggle: QCheckBox, date_input: QDateEdit) -> QWidget:
    row = QWidget(toggle.parentWidget())
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(toggle)
    layout.addWidget(date_input)
    layout.addStretch()
    return row


def _create_optional_date_controls(
    parent: QWidget,
    label: str,
    toggle_name: str,
    input_name: str,
    value: date | None,
) -> tuple[QCheckBox, QDateEdit]:
    toggle = QCheckBox(f"Set {label.lower()}", parent)
    toggle.setObjectName(toggle_name)
    date_input = QDateEdit(parent)
    date_input.setObjectName(input_name)
    date_input.setAccessibleName(label)
    date_input.setCalendarPopup(True)
    date_input.setDisplayFormat(input_date_format(date_input))
    date_input.setDateRange(
        _to_qdate(MIN_METADATA_DATE),
        _to_qdate(MAX_METADATA_DATE),
    )
    initial_date = QDate.currentDate() if value is None else _to_qdate(value)
    date_input.setDate(initial_date)
    toggle.setChecked(value is not None)
    date_input.setEnabled(toggle.isChecked())
    date_input.setVisible(toggle.isChecked())
    toggle.toggled.connect(date_input.setEnabled)
    toggle.toggled.connect(date_input.setVisible)
    return toggle, date_input


def _optional_date(toggle: QCheckBox, date_input: QDateEdit) -> date | None:
    if not toggle.isChecked():
        return None
    value = date_input.date()
    return date(value.year(), value.month(), value.day())


def _parse_tags(value: str) -> tuple[str, ...]:
    return tuple(tag.strip() for tag in value.split(",") if tag.strip())


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _detail_panel(
    object_name: str,
    parent: QWidget,
) -> tuple[QFrame, QVBoxLayout]:
    panel = QFrame(parent)
    panel.setObjectName(object_name)
    panel.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )
    apply_surface_role(panel, SurfaceRole.RAISED)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(
        int(Spacing.ORDINARY),
        int(Spacing.ORDINARY),
        int(Spacing.ORDINARY),
        int(Spacing.ORDINARY),
    )
    layout.setSpacing(int(Spacing.CONTROL))
    return panel, layout


def _configure_detail_action_grid(
    layout: QGridLayout,
    buttons: tuple[QPushButton, ...],
) -> None:
    """Center a compact three-column action block that can still shrink safely."""

    layout.setColumnStretch(0, 1)
    for column in range(1, 4):
        layout.setColumnStretch(column, 5)
    layout.setColumnStretch(4, 1)
    for button in buttons:
        button.setMaximumWidth(210)
        button.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )


def _status_tone(status: PredictionStatus) -> StatusTone:
    if status is PredictionStatus.OPEN:
        return StatusTone.ACCENT
    if status is PredictionStatus.LOCKED:
        return StatusTone.WARNING
    if status is PredictionStatus.RESOLVED:
        return StatusTone.SUCCESS
    return StatusTone.ERROR


def _make_selectable(label: QLabel) -> None:
    """Allow copying text without adding read-only labels to keyboard tab order."""

    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


def _detail_value_row(
    label: str,
    row_name: str,
    value_name: str,
    parent: QWidget,
    *,
    stacked: bool = False,
) -> tuple[QWidget, QLabel]:
    row = QWidget(parent)
    row.setObjectName(row_name)
    layout = QVBoxLayout(row) if stacked else QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    if stacked:
        layout.setSpacing(int(Spacing.COMPACT))
    heading = QLabel(f"{label}:", row)
    apply_text_role(heading, TextRole.LABEL)
    value = QLabel("", row)
    value.setObjectName(value_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(stacked)
    _make_selectable(value)
    layout.addWidget(heading)
    layout.addWidget(value)
    if not stacked:
        layout.addStretch()
    return row, value


def _detail_text_section(
    heading_text: str,
    section_name: str,
    value_name: str,
    parent: QWidget,
) -> tuple[QWidget, QLabel]:
    section = QWidget(parent)
    section.setObjectName(section_name)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 8, 0, 0)
    heading = QLabel(heading_text, section)
    apply_text_role(heading, TextRole.LABEL)
    value = QLabel("", section)
    value.setObjectName(value_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(True)
    _make_selectable(value)
    layout.addWidget(heading)
    layout.addWidget(value)
    return section, value


def _focus_search_widget(scroll_area: QScrollArea, target: QWidget) -> None:
    """Scroll to one visible context and apply a temporary palette-safe cue."""

    ancestor = target.parentWidget()
    while ancestor is not None:
        if isinstance(ancestor, QGroupBox) and ancestor.isCheckable():
            ancestor.setChecked(True)
        toggle = getattr(ancestor, "disclosure_button", None)
        if toggle is not None:
            toggle.setChecked(True)
        ancestor = ancestor.parentWidget()
    target.setProperty("searchMatchEmphasis", True)
    refresh_widget_style(target)
    QTimer.singleShot(0, lambda: scroll_area.ensureWidgetVisible(target, 24, 24))
    timer = target.findChild(QTimer, "searchMatchEmphasisTimer")
    if timer is None:
        timer = QTimer(target)
        timer.setObjectName("searchMatchEmphasisTimer")
        timer.setSingleShot(True)

        def clear_emphasis() -> None:
            target.setProperty("searchMatchEmphasis", False)
            refresh_widget_style(target)

        timer.timeout.connect(clear_emphasis)
    # A retained row may be revealed again before its previous cue expires.
    timer.start(4_000)


def _collapsible_history_group(
    title: str,
    object_name: str,
    parent: QWidget,
) -> QGroupBox:
    group = QGroupBox(title, parent)
    group.setObjectName(object_name)
    group.setCheckable(True)
    group.setChecked(False)
    content = QWidget(group)
    content.setObjectName(f"{object_name}Content")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(4, 4, 4, 4)
    layout = QVBoxLayout(group)
    layout.addWidget(content)
    group.toggled.connect(content.setVisible)
    content.setHidden(True)
    group.setHidden(True)
    return group


def _history_content(group: QGroupBox) -> tuple[QWidget, QVBoxLayout]:
    content = group.findChild(QWidget, f"{group.objectName()}Content")
    if content is None or not isinstance(content.layout(), QVBoxLayout):
        raise RuntimeError("Terminal correction history content is unavailable.")
    return content, content.layout()


def _show_binary_resolution_correction_history(
    group: QGroupBox,
    history: BinaryResolutionHistory,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Resolution",
            history.original.resolved_at,
            (
                ("Outcome", history.original.outcome.value.capitalize()),
                ("Resolution notes", history.original.resolution_notes),
                ("Postmortem", history.original.postmortem),
                *(
                    (
                        (
                            "Effective resolution time",
                            format_local_deadline(
                                history.original.effective_resolution_at
                            ),
                        ),
                    )
                    if history.original.effective_resolution_at is not None
                    else ()
                ),
            ),
            "binaryResolutionOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(_binary_resolution_correction_frame(correction, content))
    _finish_terminal_history_group(group, len(history.corrections))


def _show_numeric_resolution_correction_history(
    group: QGroupBox,
    history: NumericResolutionHistory,
    unit: str,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Resolution",
            history.original.resolved_at,
            (
                ("Actual value", f"{history.original.actual_value} {unit}"),
                ("Resolution notes", history.original.resolution_notes),
                ("Postmortem", history.original.postmortem),
                *(
                    (
                        (
                            "Original effective resolution time",
                            format_local_deadline(
                                history.original.effective_resolution_at
                            ),
                        ),
                    )
                    if history.original.effective_resolution_at is not None
                    else ()
                ),
            ),
            "numericResolutionOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(
            _numeric_resolution_correction_frame(correction, unit, content)
        )
    _finish_terminal_history_group(group, len(history.corrections))


def _show_invalidation_correction_history(
    group: QGroupBox,
    history: InvalidationHistory,
) -> None:
    content, layout = _history_content(group)
    _clear_widget_layout(layout)
    layout.addWidget(
        _terminal_history_frame(
            "Original Invalidation",
            history.original.invalidated_at,
            (("Reason", history.original.reason),),
            "invalidationOriginal",
            content,
        )
    )
    for correction in history.corrections:
        layout.addWidget(_invalidation_correction_frame(correction, content))
    _finish_terminal_history_group(group, len(history.corrections))


def _finish_terminal_history_group(group: QGroupBox, correction_count: int) -> None:
    suffix = "correction" if correction_count == 1 else "corrections"
    base_title = (
        "Invalidation correction history"
        if "Invalidation" in group.objectName() or "invalidation" in group.objectName()
        else "Resolution correction history"
    )
    group.setTitle(
        "Reason history"
        if base_title.startswith("Invalidation")
        else "Resolution history"
    )
    group.setAccessibleName(f"{base_title} ({correction_count} {suffix})")
    group.setToolTip(group.accessibleName())
    group.setChecked(False)
    content, _layout = _history_content(group)
    count = QLabel(
        f"{correction_count} {suffix}. Original facts are shown first.", content
    )
    count.setObjectName("terminalCorrectionCount")
    count.setWordWrap(True)
    apply_text_role(count, TextRole.SECONDARY)
    _layout.insertWidget(0, count)
    content.setHidden(True)
    group.setHidden(correction_count == 0)


def _terminal_history_frame(
    heading_text: str,
    timestamp: datetime,
    values: tuple[tuple[str, object | None], ...],
    object_name: str,
    parent: QWidget,
) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName(object_name)
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)
    heading = QLabel(
        f"{heading_text} · {_format_local_timestamp(timestamp, widget=parent)}",
        frame,
    )
    heading.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(heading, TextRole.LABEL)
    layout.addWidget(heading)
    for label, value in values:
        item = QLabel(f"{label}: {_terminal_history_value(value)}", frame)
        item.setTextFormat(Qt.TextFormat.PlainText)
        item.setWordWrap(True)
        _make_selectable(item)
        layout.addWidget(item)
    return frame


def _binary_resolution_correction_frame(
    correction: ResolutionCorrection,
    parent: QWidget,
) -> QFrame:
    values = {
        "effective_resolution_at": (
            None
            if correction.old_effective_resolution_at is None
            else format_local_deadline(correction.old_effective_resolution_at),
            None
            if correction.new_effective_resolution_at is None
            else format_local_deadline(correction.new_effective_resolution_at),
        ),
        "outcome": (
            correction.old_outcome.value.capitalize(),
            correction.new_outcome.value.capitalize(),
        ),
        "resolution_notes": (
            correction.old_resolution_notes,
            correction.new_resolution_notes,
        ),
        "postmortem": (correction.old_postmortem, correction.new_postmortem),
    }
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        correction.changed_fields,
        values,
        correction.correction_reason,
        "resolutionCorrection",
        parent,
    )


def _numeric_resolution_correction_frame(
    correction: NumericResolutionCorrection,
    unit: str,
    parent: QWidget,
) -> QFrame:
    values = {
        "effective_resolution_at": (
            format_local_deadline(correction.old_effective_resolution_at)
            if correction.old_effective_resolution_at is not None
            else None,
            format_local_deadline(correction.new_effective_resolution_at)
            if correction.new_effective_resolution_at is not None
            else None,
        ),
        "actual_value": (
            f"{correction.old_actual_value} {unit}",
            f"{correction.new_actual_value} {unit}",
        ),
        "resolution_notes": (
            correction.old_resolution_notes,
            correction.new_resolution_notes,
        ),
        "postmortem": (correction.old_postmortem, correction.new_postmortem),
    }
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        correction.changed_fields,
        values,
        correction.correction_reason,
        "numericResolutionCorrection",
        parent,
    )


def _invalidation_correction_frame(
    correction: InvalidationReasonCorrection,
    parent: QWidget,
) -> QFrame:
    return _terminal_correction_frame(
        correction.correction_id,
        correction.sequence,
        correction.corrected_at,
        ("reason",),
        {"reason": (correction.old_reason, correction.new_reason)},
        None,
        "invalidationReasonCorrection",
        parent,
    )


def _terminal_correction_frame(
    correction_id: int,
    sequence: int,
    corrected_at: datetime,
    changed_fields: tuple[str, ...],
    values: dict[str, tuple[object | None, object | None]],
    correction_reason: str | None,
    object_name_prefix: str,
    parent: QWidget,
) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName(f"{object_name_prefix}{correction_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)
    heading = QLabel(
        f"Correction {sequence} · {_format_local_timestamp(corrected_at, widget=parent)}",
        frame,
    )
    heading.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(heading, TextRole.LABEL)
    layout.addWidget(heading)
    for field_name in changed_fields:
        old_value, new_value = values[field_name]
        change = QLabel(
            f"{_terminal_field_label(field_name)}: "
            f"{_terminal_history_value(old_value)} "
            f"\N{RIGHTWARDS ARROW} {_terminal_history_value(new_value)}",
            frame,
        )
        change.setObjectName(
            f"{object_name_prefix}{correction_id}{_object_name_part(field_name)}"
        )
        change.setTextFormat(Qt.TextFormat.PlainText)
        change.setWordWrap(True)
        _make_selectable(change)
        layout.addWidget(change)
    if correction_reason is not None:
        reason = QLabel(f"Explanation: {correction_reason}", frame)
        reason.setObjectName(f"{object_name_prefix}{correction_id}Reason")
        reason.setTextFormat(Qt.TextFormat.PlainText)
        reason.setWordWrap(True)
        _make_selectable(reason)
        layout.addWidget(reason)
    return frame


def _apply_dialog_presentation(dialog: QDialog) -> None:
    """Apply one visual and accessibility grammar to existing focused dialogs."""

    root_layout = dialog.layout()
    if root_layout is not None:
        root_layout.setContentsMargins(
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
        )
        root_layout.setSpacing(int(Spacing.CONTROL))

    direct_labels = [
        label
        for label in dialog.findChildren(QLabel)
        if label.parentWidget() is dialog and label.text().strip()
    ]
    if direct_labels:
        apply_text_role(direct_labels[0], TextRole.SECTION_TITLE)

    for label in dialog.findChildren(QLabel):
        name = label.objectName().casefold()
        if label.buddy() is not None:
            apply_text_role(label, TextRole.LABEL)
        if "error" in name:
            apply_message_role(
                label,
                StatusTone.ERROR,
                accessible_name=label.accessibleName()
                or f"{dialog.windowTitle()} error",
            )
        elif "scorechangenotice" in name or "endpointnote" in name:
            apply_message_role(
                label,
                StatusTone.WARNING,
                accessible_name=label.accessibleName() or label.text(),
            )
        elif "explanation" in name or "helper" in name:
            apply_text_role(label, TextRole.SECONDARY)
        if any(
            token in name
            for token in (
                "currentprobability",
                "currentforecast",
                "forecastattime",
                "scoringforecast",
                "reviewcontext",
            )
        ):
            label.setWordWrap(True)
            _make_selectable(label)
            apply_surface_role(label, SurfaceRole.SELECTED)

    for buttons in dialog.findChildren(QDialogButtonBox):
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            apply_action_role(
                save,
                ActionRole.CAUTION
                if save.text() == "Mark Invalid"
                else ActionRole.PRIMARY,
            )
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            apply_action_role(cancel, ActionRole.SECONDARY)


def _dialog_error_label(object_name: str, parent: QWidget) -> QLabel:
    error = QLabel("", parent)
    error.setObjectName(object_name)
    error.setTextFormat(Qt.TextFormat.PlainText)
    error.setWordWrap(True)
    error.setHidden(True)
    return error


def _save_cancel_buttons(
    save_object_name: str,
    save_text: str,
    parent: QWidget,
) -> QDialogButtonBox:
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        parent,
    )
    save = buttons.button(QDialogButtonBox.StandardButton.Save)
    save.setObjectName(save_object_name)
    save.setText(save_text)
    save.setDefault(True)
    apply_lucide_icon(save, LucideIcon.SAVE)
    return buttons


def _confirm_terminal_correction(
    parent: QWidget,
    *,
    score_affecting: bool,
) -> bool:
    if score_affecting:
        title = "Confirm score-affecting correction"
        message = (
            "This correction changes an outcome or effective time and recomputes scoring "
            "from the corrected facts. Original terminal facts and every forecast "
            "remain in history. Save this correction?"
        )
    else:
        title = "Confirm terminal correction"
        message = (
            "This appends a correction while preserving the original terminal "
            "record and every earlier version. Save this correction?"
        )
    answer = QMessageBox.warning(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return answer == QMessageBox.StandardButton.Yes


def _normalized_optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _terminal_history_value(value: object | None) -> str:
    return "Not set" if value is None or value == "" else str(value)


def _terminal_field_label(field_name: str) -> str:
    return {
        "effective_resolution_at": "Effective resolution time",
        "outcome": "Outcome",
        "actual_value": "Actual value",
        "resolution_notes": "Resolution notes",
        "postmortem": "Postmortem",
        "reason": "Reason",
    }[field_name]


def _definition_change_widget(
    change: DefinitionChange,
    parent: QWidget,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"definitionChange{change.change_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)
    timestamp = QLabel(_format_local_timestamp(change.changed_at, widget=parent), frame)
    timestamp.setObjectName(f"definitionChangeTimestamp{change.change_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(timestamp, TextRole.SECONDARY)
    layout.addWidget(timestamp)
    values = {
        "question": (change.old_question, change.new_question),
        "resolution_criteria": (
            change.old_resolution_criteria,
            change.new_resolution_criteria,
        ),
        "forecast_deadline": (
            change.old_forecast_deadline,
            change.new_forecast_deadline,
        ),
    }
    for field_name in change.changed_fields:
        old_value, new_value = values[field_name]
        field_change = QLabel(
            f"{_field_label(field_name)}: {_history_value(old_value, widget=parent)} → "
            f"{_history_value(new_value, widget=parent)}",
            frame,
        )
        field_change.setObjectName(
            f"definitionChange{change.change_id}{_object_name_part(field_name)}"
        )
        field_change.setTextFormat(Qt.TextFormat.PlainText)
        field_change.setWordWrap(True)
        _make_selectable(field_change)
        layout.addWidget(field_change)
    return frame


def _forecast_timeline_widget(
    revision: ForecastTimelineSnapshot,
    parent: QWidget,
    *,
    scoring_excluded: bool = False,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"forecastRevision{revision.revision_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)

    timestamp = QLabel(
        _format_local_timestamp(revision.created_at, widget=parent), frame
    )
    timestamp.setToolTip(revision.created_at.astimezone().isoformat(sep=" "))
    timestamp.setWordWrap(True)
    _make_selectable(timestamp)
    timestamp.setObjectName(f"forecastRevisionTimestamp{revision.revision_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(timestamp, TextRole.SECONDARY)
    layout.addWidget(timestamp)

    if revision.previous_probability_percent is None:
        probability_text = f"FORECAST  {revision.probability_percent}%"
    else:
        probability_text = (
            f"FORECAST  {revision.previous_probability_percent}% "
            f"\N{RIGHTWARDS ARROW} {revision.probability_percent}%"
        )
    probability = QLabel(probability_text, frame)
    probability.setObjectName(f"forecastRevisionProbability{revision.revision_id}")
    probability.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(probability, TextRole.LABEL)
    _make_selectable(probability)
    layout.addWidget(probability)

    if scoring_excluded:
        notice = QLabel(
            "At or after scoring cutoff — preserved in history, not scored.", frame
        )
        notice.setObjectName(f"forecastRevisionScoringExclusion{revision.revision_id}")
        notice.setWordWrap(True)
        apply_text_role(notice, TextRole.SECONDARY)
        _make_selectable(notice)
        layout.addWidget(notice)

    if revision.rationale:
        rationale = QLabel(revision.rationale, frame)
        rationale.setObjectName(f"forecastRevisionRationale{revision.revision_id}")
        rationale.setTextFormat(Qt.TextFormat.PlainText)
        rationale.setWordWrap(True)
        _make_selectable(rationale)
        layout.addWidget(rationale)
    return frame


def _journal_entry_widget(
    entry: JournalTimelineSnapshot,
    parent: QWidget,
    correct_entry: Callable[[JournalTimelineSnapshot], None],
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"journalEntry{entry.entry_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)

    timestamp = QLabel(_format_local_timestamp(entry.created_at, widget=parent), frame)
    timestamp.setToolTip(entry.created_at.astimezone().isoformat(sep=" "))
    timestamp.setWordWrap(True)
    _make_selectable(timestamp)
    timestamp.setObjectName(f"journalEntryTimestamp{entry.entry_id}")
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(timestamp, TextRole.SECONDARY)
    layout.addWidget(timestamp)

    heading_row = QWidget(frame)
    heading_layout = FlowLayout(heading_row)
    heading_layout.setContentsMargins(0, 0, 0, 0)
    kind = QLabel("JOURNAL", heading_row)
    kind.setObjectName(f"journalEntryKind{entry.entry_id}")
    kind.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(kind, TextRole.LABEL)
    heading_layout.addWidget(kind)
    if entry.current_correction_id is not None:
        latest_correction = entry.corrections[-1]
        edited = QLabel(
            f"Edited {_format_local_timestamp(latest_correction.corrected_at, widget=parent)}",
            heading_row,
        )
        edited.setObjectName(f"journalEntryEdited{entry.entry_id}")
        edited.setTextFormat(Qt.TextFormat.PlainText)
        edited.setWordWrap(True)
        apply_text_role(edited, TextRole.SECONDARY)
        heading_layout.addWidget(edited)
    correct_button = QPushButton("Correct Entry", heading_row)
    correct_button.setObjectName(f"correctJournalEntryButton{entry.entry_id}")
    apply_action_role(correct_button, ActionRole.QUIET)
    apply_lucide_icon(correct_button, LucideIcon.PENCIL, size=16)
    correct_button.setToolTip(
        "Save a correction while preserving the original and prior versions."
    )
    correct_button.clicked.connect(
        lambda _checked=False, current=entry: correct_entry(current)
    )
    heading_layout.addWidget(correct_button)
    layout.addWidget(heading_row)

    body = QLabel(entry.body, frame)
    body.setObjectName(f"journalEntryBody{entry.entry_id}")
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setWordWrap(True)
    _make_selectable(body)
    layout.addWidget(progressive_body(body))
    quiet_event(frame)

    forecast_context = QLabel(
        f"Forecast at the time: {entry.forecast_probability_percent}%",
        frame,
    )
    forecast_context.setObjectName(f"journalEntryForecastAtTime{entry.entry_id}")
    forecast_context.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(forecast_context, TextRole.SECONDARY)
    _make_selectable(forecast_context)
    layout.addWidget(forecast_context)

    if entry.corrections:
        layout.addWidget(_journal_edit_history_widget(entry, frame))
    return frame


def _forecast_review_widget(
    review: ForecastReviewTimelineSnapshot,
    parent: QWidget,
) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName(f"forecastReview{review.review_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)
    timestamp = QLabel(_format_local_timestamp(review.created_at, widget=parent), frame)
    timestamp.setToolTip(review.created_at.astimezone().isoformat(sep=" "))
    timestamp.setWordWrap(True)
    _make_selectable(timestamp)
    timestamp.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(timestamp, TextRole.SECONDARY)
    heading = QLabel(
        f"REVIEW  STILL AT {review.forecast_probability_percent}%",
        frame,
    )
    heading.setObjectName(f"forecastReviewHeading{review.review_id}")
    heading.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(heading, TextRole.LABEL)
    layout.addWidget(timestamp)
    layout.addWidget(heading)
    if review.note:
        note = QLabel(review.note, frame)
        note.setObjectName(f"forecastReviewNote{review.review_id}")
        note.setTextFormat(Qt.TextFormat.PlainText)
        note.setWordWrap(True)
        _make_selectable(note)
        layout.addWidget(progressive_body(note))
    quiet_event(frame)
    return frame


def _one_shot_journal_timeline_widget(
    entry: OneShotJournal,
    parent: QWidget,
    correct_entry: Callable[[int], None],
) -> QWidget:
    """Show the effective Journal text at its original position in the timeline."""

    frame = QFrame(parent)
    frame.setObjectName(f"oneShotJournalEntry{entry.entry_id}")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    apply_surface_role(frame, SurfaceRole.BASE)
    layout = QVBoxLayout(frame)

    timestamp = text_label(
        _format_local_timestamp(entry.created_at, widget=parent), frame
    )
    timestamp.setToolTip(entry.created_at.astimezone().isoformat(sep=" "))
    apply_text_role(timestamp, TextRole.SECONDARY)
    layout.addWidget(timestamp)

    heading_row = QWidget(frame)
    heading_layout = QHBoxLayout(heading_row)
    heading_layout.setContentsMargins(0, 0, 0, 0)
    kind = text_label("JOURNAL", heading_row)
    apply_text_role(kind, TextRole.LABEL)
    heading_layout.addWidget(kind)
    if entry.corrections:
        edited = text_label(
            f"Edited {_format_local_timestamp(entry.corrections[-1].corrected_at, widget=parent)}",
            heading_row,
        )
        edited.setWordWrap(False)
        apply_text_role(edited, TextRole.SECONDARY)
        heading_layout.addWidget(edited)
    heading_layout.addStretch()
    button = QPushButton("Correct Entry", heading_row)
    button.setObjectName(f"oneShotCorrectJournal{entry.entry_id}")
    apply_action_role(button, ActionRole.QUIET)
    apply_lucide_icon(button, LucideIcon.PENCIL, size=16)
    button.setToolTip(
        "Save a correction while preserving the original and prior versions."
    )
    button.clicked.connect(
        lambda _checked=False, entry_id=entry.entry_id: correct_entry(entry_id)
    )
    heading_layout.addWidget(button)
    layout.addWidget(heading_row)

    body = text_label(entry.body, frame)
    body.setObjectName(f"oneShotJournalBody{entry.entry_id}")
    layout.addWidget(progressive_body(body))
    quiet_event(frame)
    if entry.corrections:
        layout.addWidget(_journal_edit_history_widget(entry, frame))
    return frame


def _journal_edit_history_widget(
    entry: JournalTimelineSnapshot | QuantileTimelineEvent | OneShotJournal,
    parent: QWidget,
) -> QGroupBox:
    prior_version_count = len(entry.corrections)
    suffix = "version" if prior_version_count == 1 else "versions"
    history = QGroupBox(
        "Edit history",
        parent,
    )
    history.setObjectName(f"journalEntryEditHistory{entry.entry_id}")
    history.setAccessibleName(f"Edit history ({prior_version_count} prior {suffix})")
    apply_surface_role(history, SurfaceRole.BASE)
    history.setCheckable(True)
    history.setChecked(False)

    content = QWidget(history)
    content.setObjectName(f"journalEntryEditHistoryContent{entry.entry_id}")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(4, 4, 4, 4)
    count = QLabel(f"{prior_version_count} prior {suffix}", content)
    count.setWordWrap(True)
    apply_text_role(count, TextRole.SECONDARY)
    content_layout.addWidget(count)

    original_heading = QLabel(
        f"Original · {_format_local_timestamp(entry.created_at, widget=parent)}",
        content,
    )
    original_heading.setObjectName(f"journalEntryOriginalHeading{entry.entry_id}")
    original_heading.setTextFormat(Qt.TextFormat.PlainText)
    original_heading.setWordWrap(True)
    original_body = QLabel(entry.original_body, content)
    original_body.setObjectName(f"journalEntryOriginalBody{entry.entry_id}")
    original_body.setTextFormat(Qt.TextFormat.PlainText)
    original_body.setWordWrap(True)
    _make_selectable(original_body)
    content_layout.addWidget(original_heading)
    content_layout.addWidget(original_body)

    for index, correction in enumerate(entry.corrections[:-1], start=1):
        correction_heading = QLabel(
            f"Correction {index} · {_format_local_timestamp(correction.corrected_at, widget=parent)}",
            content,
        )
        correction_heading.setObjectName(
            f"journalCorrectionHeading{correction.correction_id}"
        )
        correction_heading.setTextFormat(Qt.TextFormat.PlainText)
        correction_heading.setWordWrap(True)
        correction_body = QLabel(correction.body, content)
        correction_body.setObjectName(
            f"journalCorrectionBody{correction.correction_id}"
        )
        correction_body.setTextFormat(Qt.TextFormat.PlainText)
        correction_body.setWordWrap(True)
        _make_selectable(correction_body)
        content_layout.addWidget(correction_heading)
        content_layout.addWidget(correction_body)

    history_layout = QVBoxLayout(history)
    history_layout.addWidget(content)
    history.toggled.connect(content.setVisible)
    content.setHidden(True)
    return history


class _MultilineSubmitKeyFilter(QObject):
    """Make Ctrl+Enter submit while an ordinary Enter remains a newline."""

    def __init__(
        self,
        submit: Callable[[], None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._submit = submit

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            modifiers = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
                modifiers & Qt.KeyboardModifier.ControlModifier
            ):
                self._submit()
                return True
        return super().eventFilter(watched, event)


def _clear_widget_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _format_local_timestamp(value: datetime, *, widget: QWidget | None = None) -> str:
    return format_datetime(value, widget)


def _format_date(value: date | None, *, widget: QWidget | None = None) -> str:
    return format_date(value, widget)


def _numeric_forecast_text(
    revision: QuantileRevision,
    unit: str,
) -> str:
    """Format one Numeric ForecastRevision for plain-language UI context."""

    return quantile_summary(revision.quantiles, unit)


def _history_value(value: str | date | None, *, widget: QWidget | None = None) -> str:
    if value is None or value == "":
        return "Not set"
    if isinstance(value, date):
        return _format_date(value, widget=widget)
    return f"“{value}”"


def _field_label(field_name: str) -> str:
    return {
        "question": "Question",
        "resolution_criteria": "Resolution Criteria",
        "forecast_deadline": "Forecast Deadline",
    }.get(field_name, field_name.replace("_", " ").title())


def _object_name_part(field_name: str) -> str:
    words = field_name.split("_")
    return "".join(word.title() for word in words)
