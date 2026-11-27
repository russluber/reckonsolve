"""Readable documentary times and immutable One-Shot correction comparisons."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from reckonsolve.domain.one_shot import (
    OneShotDetail,
    OneShotSourceAction,
    OneShotValues,
)
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.one_shot_display import forecast_text
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.date_display import format_datetime, format_reported_time
from reckonsolve.ui.detail_reading import TimelineEntry
from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.one_shot import text_label
from reckonsolve.ui.one_shot_reading import OneShotReadingSection, finish_disclosure
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


def _label(text: str, parent: QWidget, role: TextRole) -> QLabel:
    label = text_label(text, parent)
    label.setMinimumWidth(0)
    if role is TextRole.DETAIL_TEXT:
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    apply_text_role(label, role)
    return label


def _group(title: str, rows: list[tuple[str, str]], parent: QWidget) -> QWidget:
    section = OneShotReadingSection(title, parent, end_rule=False)
    section.layout().setContentsMargins(0, int(Spacing.ORDINARY), 0, 0)
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(int(Spacing.GROUP))
    grid.setVerticalSpacing(int(Spacing.CONTROL))
    grid.setColumnStretch(1, 1)
    for index, (name, value) in enumerate(rows):
        grid.addWidget(
            _label(name, section, TextRole.DETAIL_TIME),
            index,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        grid.addWidget(_label(value, section, TextRole.DETAIL_TEXT), index, 1)
    section.body_layout.addLayout(grid)
    return section


def _fields(
    values: OneShotValues, unit: str, parent: QWidget
) -> dict[str, tuple[str, object, str]]:
    answer = values.answer
    answer_text = (
        "Not recorded"
        if answer is None
        else answer.value.capitalize()
        if isinstance(answer, BinaryOutcome)
        else f"{answer} {unit}".rstrip()
    )
    return {
        "forecast": (
            "Forecast",
            (values.probability_percent, values.quantiles),
            forecast_text(values, unit),
        ),
        "answer": ("Answer", answer, answer_text),
        "forecast_reported": (
            "Forecast finalized",
            values.forecast_reported,
            format_reported_time(values.forecast_reported, parent),
        ),
        "reveal_reported": (
            "Answer checked",
            values.reveal_reported,
            format_reported_time(values.reveal_reported, parent),
        ),
        "resolution_notes": (
            "Resolution Notes",
            values.resolution_notes,
            values.resolution_notes or "Not recorded",
        ),
        "postmortem": (
            "Postmortem",
            values.postmortem,
            values.postmortem or "Not recorded",
        ),
    }


def _snapshot(title: str, values: OneShotValues, unit: str, parent: QWidget) -> QWidget:
    block = OneShotReadingSection(title, parent, end_rule=False)
    block.layout().setContentsMargins(0, int(Spacing.ORDINARY), 0, 0)
    facts = _fields(values, unit, block)
    block.body_layout.addWidget(
        _group(
            "Forecast & Answer",
            [(facts[k][0], facts[k][2]) for k in ("forecast", "answer")],
            block,
        )
    )
    times = ["forecast_reported"] + (
        ["reveal_reported"] if values.answer is not None else []
    )
    block.body_layout.addWidget(
        _group("Reported by You", [(facts[k][0], facts[k][2]) for k in times], block)
    )
    for key in ("resolution_notes", "postmortem"):
        label, raw, text = facts[key]
        if raw is not None:
            prose = OneShotReadingSection(label, block, end_rule=False)
            prose.layout().setContentsMargins(0, int(Spacing.ORDINARY), 0, 0)
            prose.body_layout.addWidget(_label(text, prose, TextRole.DETAIL_TEXT))
            block.body_layout.addWidget(prose)
    return block


def recorded_facts(detail: OneShotDetail, parent: QWidget) -> ContentPanel:
    record = detail.record
    facts = ContentPanel("", parent=parent)
    facts.setObjectName("oneShotRecordedFacts")
    facts.title_label.parentWidget().hide()
    reported = [
        (
            "Forecast finalized",
            format_reported_time(record.effective.forecast_reported, facts),
        )
    ]
    if record.effective.answer is not None:
        reported.append(
            (
                "Answer checked",
                format_reported_time(record.effective.reveal_reported, facts),
            )
        )
    facts.body_layout.addWidget(_group("Reported by You", reported, facts))
    recorded = [("Forecast entered", format_datetime(record.recorded_at, facts))]
    if record.answer_recorded_at is not None:
        recorded.append(
            ("Answer entered", format_datetime(record.answer_recorded_at, facts))
        )
    facts.body_layout.addWidget(_group("Recorded by Reckonsolve", recorded, facts))
    if record.definition is not None:
        definition = record.definition
        facts.body_layout.addWidget(
            _group(
                "Numeric Definition",
                [
                    ("Unit", definition.unit),
                    ("Decimal Places", str(definition.decimal_places)),
                    ("Value Constraint", definition.value_constraint.value),
                ],
                facts,
            )
        )
    return facts


def correction_history(detail: OneShotDetail, parent: QWidget) -> ContentPanel:
    record = detail.record
    unit = record.definition.unit if record.definition is not None else ""
    history = ContentPanel("", parent=parent)
    history.setObjectName("oneShotCorrectionHistory")
    history.title_label.parentWidget().hide()
    history.body_layout.setSpacing(int(Spacing.SECTION))
    history.body_layout.addWidget(
        _snapshot("Original Saved Facts", record.original, unit, history)
    )
    if not record.corrections:
        history.body_layout.addWidget(
            _label("No corrections recorded.", history, TextRole.DETAIL_TIME)
        )
    for index, correction in enumerate(record.corrections):
        action = (
            "Postmortem Update"
            if correction.source_action is OneShotSourceAction.POSTMORTEM
            else "Transcription Correction"
        )
        event = TimelineEntry(
            f"{action} {correction.sequence}",
            correction.corrected_at,
            history,
            end_rule=index < len(record.corrections) - 1,
        )
        event.setObjectName(f"oneShotAuditCorrection{correction.correction_id}")
        before = _fields(correction.before, unit, event)
        after = _fields(correction.after, unit, event)
        for key, (name, value, text) in after.items():
            if before[key][1] == value:
                continue
            change = OneShotReadingSection(name, event, end_rule=False)
            change.layout().setContentsMargins(0, int(Spacing.COMPACT), 0, 0)
            compare = QGridLayout()
            compare.setContentsMargins(0, 0, 0, 0)
            compare.setHorizontalSpacing(int(Spacing.GROUP))
            prose = key in ("resolution_notes", "postmortem")
            for column, (caption, content) in enumerate(
                (("Before", before[key][2]), ("After", text))
            ):
                compare.setColumnStretch(0 if prose else column, 1)
                cell = QWidget(change)
                column_layout = QVBoxLayout(cell)
                column_layout.setContentsMargins(0, 0, 0, 0)
                column_layout.setSpacing(int(Spacing.COMPACT))
                column_layout.addWidget(_label(caption, cell, TextRole.DETAIL_TIME))
                column_layout.addWidget(_label(content, cell, TextRole.DETAIL_TEXT))
                # Prose reads across the pane; short facts align side by side.
                compare.addWidget(
                    cell,
                    column if prose else 0,
                    0 if prose else column,
                    Qt.AlignmentFlag.AlignTop,
                )
            change.body_layout.addLayout(compare)
            event.column.addWidget(change)
        if correction.note:
            note = OneShotReadingSection("Correction Note", event, end_rule=False)
            note.layout().setContentsMargins(0, int(Spacing.COMPACT), 0, 0)
            note.body_layout.addWidget(
                _label(correction.note, note, TextRole.DETAIL_TEXT)
            )
            event.column.addWidget(note)
        complete = QWidget(event)
        complete.setObjectName(f"oneShotCompleteSnapshot{correction.correction_id}")
        column = QVBoxLayout(complete)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(_snapshot("Before", correction.before, unit, complete))
        column.addWidget(_snapshot("After", correction.after, unit, complete))
        event.column.addWidget(
            finish_disclosure(
                collapse_section(complete, "Complete Recorded Snapshots", compact=True),
                end_rule=False,
            )
        )
        history.body_layout.addWidget(event)
    return history
