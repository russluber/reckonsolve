"""Readable Journal cards and safe matching excerpts; no record calculations."""

import html
from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.journal import JournalRow
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.domain.search import (
    ParsedSearchText,
    SearchDocument,
    SearchSourceKind,
    build_search_snippet,
    search_source_label,
)
from reckonsolve.ui.components import StatusBadge
from reckonsolve.ui.date_display import date_context, format_date, format_datetime
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
)


def emphasized(text: str, parsed: ParsedSearchText, *, full: bool = False) -> str:
    snippet = build_search_snippet(
        text, parsed, maximum_length=max(len(text), 40) if full else 220
    )
    pieces, cursor = [], 0
    for start, end in snippet.match_spans:
        pieces.extend(
            (
                html.escape(snippet.text[cursor:start]),
                "<b>",
                html.escape(snippet.text[start:end]),
                "</b>",
            )
        )
        cursor = end
    pieces.append(html.escape(snippet.text[cursor:]))
    return "".join(pieces)


def local_date(
    value: datetime, *, clock: bool = False, widget: QWidget | None = None
) -> str:
    return format_datetime(value, widget) if clock else format_date(value, widget)


class QuestionLabel(QLabel):
    activated = Signal()

    def __init__(self, text: str, accessible: str, parent: QWidget) -> None:
        super().__init__(text, parent)
        self.setAccessibleName(accessible)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setIndent(0)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("reckonsolveQuestionLink", "true")
        apply_text_role(self, TextRole.ROW_QUESTION)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() is Qt.MouseButton.LeftButton and not self.hasSelectedText():
            self.activated.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class JournalCard(QFrame):
    def __init__(
        self,
        row: JournalRow,
        parsed: ParsedSearchText,
        open_prediction: Callable[[int, SearchDocument | None], None],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.source_row = row
        self.rendered_date_context = date_context(parent)
        self.parsed = parsed
        prediction = row.prediction
        self.prediction_id = prediction.prediction_id
        self.setObjectName(f"journalPrediction{self.prediction_id}")
        self.layout_body = QVBoxLayout(self)
        self.layout_body.setContentsMargins(
            0, int(Spacing.GROUP), 0, int(Spacing.GROUP)
        )
        self.layout_body.setSpacing(int(Spacing.COMPACT))
        question = QuestionLabel(
            emphasized(prediction.question, parsed, full=True),
            prediction.question,
            self,
        )
        question.setObjectName(f"journalQuestion{self.prediction_id}")
        best = row.matches[0].document if row.matches else None
        question.activated.connect(lambda: open_prediction(self.prediction_id, best))
        self.layout_body.addWidget(question)
        if any(
            match.document.source_kind is SearchSourceKind.QUESTION
            and match.document.is_superseded
            for match in row.matches
        ):
            self._label(
                "Current wording"
                + (
                    f" · {local_date(row.current_question_at, widget=self)}"
                    if row.current_question_at
                    else ""
                )
            )
        self._label(row.forecast_label)
        if row.probability_percent is not None:
            self._label(f"{row.probability_percent}% Yes", TextRole.ROW_FORECAST)
        elif row.quantiles is not None:
            self._label(f"Unit: {prediction.numeric_unit}")
            # Surplus viewport width belongs after the complete forecast,
            # rather than between neighboring percentile/value groups.
            preview = QWidget(self)
            preview.setObjectName(f"journalNumericForecast{self.prediction_id}")
            values = FlowLayout(preview)
            values.setSpacing(int(Spacing.SECTION))
            for level, value in zip(
                (5, 25, 50, 75, 95), row.quantiles.values, strict=True
            ):
                group = QWidget(preview)
                column = QVBoxLayout(group)
                column.setContentsMargins(0, 0, 0, 0)
                column.setSpacing(int(Spacing.COMPACT))
                heading = QLabel(f"{level}th", group)
                apply_text_role(heading, TextRole.ROW_SECONDARY)
                number = QLabel(str(value), group)
                number.setObjectName(f"journalPercentile{self.prediction_id}_{level}")
                apply_text_role(number, TextRole.ROW_FORECAST)
                number.setAccessibleName(
                    f"{level}th percentile: {value} {prediction.numeric_unit}"
                )
                number.setWordWrap(True)
                number.setMinimumWidth(0)
                number.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                column.addWidget(heading)
                column.addWidget(number)
                values.addWidget(group)
            self.layout_body.addWidget(preview)
        if row.actual is not None:
            self._label(
                f"{'Outcome' if isinstance(row.actual, str) else 'Actual'}: {str(row.actual).title() if isinstance(row.actual, str) else str(row.actual)}"
                + (f" {prediction.numeric_unit}" if prediction.numeric_unit else "")
            )
        if row.excluded_later_forecast:
            self._label("Later revision excluded from scoring")
        if row.correction_label:
            self._label(row.correction_label)
        one_shot = prediction.forecast_contract.is_one_shot
        status = (
            "Answer Pending"
            if one_shot and prediction.status is PredictionStatus.OPEN
            else prediction.status.value.title()
        )
        meta = QHBoxLayout()
        mode = QLabel(
            f"{'One-Shot' if one_shot else 'Adaptive'} · {prediction.prediction_type.value.title()}",
            self,
        )
        apply_text_role(mode, TextRole.ROW_BODY)
        meta.addWidget(mode)
        tone = (
            StatusTone.WARNING
            if status in ("Locked", "Answer Pending")
            else StatusTone.SUCCESS
            if status == "Resolved"
            else StatusTone.CAUTION
            if status == "Invalid"
            else StatusTone.NEUTRAL
        )
        badge = StatusBadge(status, tone=tone, parent=self)
        apply_text_role(badge, TextRole.ROW_LABEL)
        meta.addWidget(badge)
        meta.addStretch()
        self.layout_body.addLayout(meta)
        dates = []
        if (
            not row.contextual_at
            or row.last_active.astimezone().date()
            != row.contextual_at.astimezone().date()
        ):
            dates.append(f"Last active: {local_date(row.last_active, widget=self)}")
        if row.contextual_at:
            dates.append(
                f"{row.contextual_label}: {local_date(row.contextual_at, clock=row.contextual_label == 'Forecast Deadline', widget=self)}"
            )
        self._label("    ".join(dates))
        passages = [
            match
            for match in row.matches
            if match.document.source_kind is not SearchSourceKind.QUESTION
            or match.document.is_superseded
        ]
        if passages:
            self._passage(passages[0].document, parsed, open_prediction)
        if len(passages) > 1:
            more = QPushButton(f"{len(passages) - 1} more matches", self)
            more.setCheckable(True)
            apply_action_role(more, ActionRole.QUIET)
            extra = QWidget(self)
            extra.setLayout(QVBoxLayout())
            extra.layout().setContentsMargins(0, 0, 0, 0)
            extra.hide()
            populated = False

            def toggle(checked):
                nonlocal populated
                if checked and not populated:
                    for match in passages[1:]:
                        self._passage(
                            match.document, parsed, open_prediction, container=extra
                        )
                    populated = True
                extra.setVisible(checked)

            more.toggled.connect(toggle)
            self.layout_body.addWidget(more, alignment=Qt.AlignmentFlag.AlignLeft)
            self.layout_body.addWidget(extra)
        separator = QFrame(self)
        separator.setObjectName("journalRowSeparator")
        separator.setFixedHeight(1)
        self.layout_body.addWidget(separator)

    def _label(self, text: str, role: TextRole = TextRole.ROW_SECONDARY) -> QLabel:
        label = QLabel(text, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        apply_text_role(label, role)
        self.layout_body.addWidget(label)
        return label

    def _passage(
        self,
        document: SearchDocument,
        parsed: ParsedSearchText,
        open_prediction,
        *,
        container: QWidget | None = None,
    ) -> None:
        destination = container.layout() if container else self.layout_body
        heading = search_source_label(document)
        if document.occurred_at:
            heading += f" · {local_date(document.occurred_at, widget=self)}"
        label = QLabel(heading, self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(label, TextRole.ROW_LABEL)
        destination.addWidget(label)
        excerpt = QLabel(emphasized(document.text, parsed), self)
        excerpt.setTextFormat(Qt.TextFormat.RichText)
        excerpt.setWordWrap(True)
        excerpt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        apply_text_role(excerpt, TextRole.ROW_BODY)
        destination.addWidget(excerpt)
        action = QPushButton(
            "Open historical passage" if document.is_superseded else "Open passage",
            self,
        )
        apply_action_role(action, ActionRole.QUIET)
        action.clicked.connect(lambda: open_prediction(self.prediction_id, document))
        destination.addWidget(action, alignment=Qt.AlignmentFlag.AlignLeft)
