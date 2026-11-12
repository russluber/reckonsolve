"""Supporting Adaptive reading panels and immutable terminal Timeline events."""

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from reckonsolve.domain.predictions import (
    BinaryResolutionHistory,
    InvalidationHistory,
    NumericResolutionHistory,
    PredictionStatus,
)
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.detail_workspace import exact_detail_time
from reckonsolve.ui.visual_system import (
    Spacing,
    SurfaceRole,
    TextRole,
    apply_surface_role,
    apply_text_role,
)


class TimelineRows:
    """Retain rendered rows only while freshly read immutable facts still match."""

    def __init__(self, layout: QVBoxLayout) -> None:
        self.layout = layout
        self.snapshot: tuple[object, ...] | None = None
        self.rows: list[tuple[datetime, int, QWidget]] = []
        self._rendered: dict[
            tuple[int, str, int], tuple[tuple[object, ...], QWidget]
        ] = {}
        self._descending: bool | None = None

    def matches(self, snapshot: tuple[object, ...]) -> bool:
        return self.snapshot == snapshot

    def clear(self) -> None:
        self.snapshot = None
        self.rows = []
        self._rendered.clear()
        self._descending = None
        while self.layout.count():
            widget = self.layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def row(
        self,
        identity: tuple[int, str, int],
        facts: tuple[object, ...],
        build: Callable[[], QWidget],
    ) -> QWidget:
        previous = self._rendered.get(identity)
        if previous is not None and previous[0] == facts:
            return previous[1]
        widget = build()
        self._rendered[identity] = (facts, widget)
        return widget

    def replace(
        self,
        snapshot: tuple[object, ...],
        rows: list[tuple[datetime, int, QWidget]],
        *,
        descending: bool,
    ) -> None:
        retained = {id(row[2]) for row in rows}
        while self.layout.count():
            widget = self.layout.takeAt(0).widget()
            if widget is not None and id(widget) not in retained:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._rendered = {
            key: value
            for key, value in self._rendered.items()
            if id(value[1]) in retained
        }
        self._descending = None
        self.snapshot, self.rows = snapshot, rows
        self.order(descending=descending)

    def order(self, *, descending: bool) -> None:
        if self._descending == descending:
            return
        self._descending = descending
        # Moving layout items retains widget parents, selection and disclosures.
        # Recreating these trees incurs a large deferred Qt style/layout pass.
        while self.layout.count():
            self.layout.takeAt(0)
        for _, _, widget in sorted(
            self.rows, key=lambda row: (row[0], row[1]), reverse=descending
        ):
            self.layout.addWidget(widget)


class AdaptiveReadingSections:
    """Give factual notes and written reflection one visible home in Overview."""

    def __init__(
        self, notes: QLabel, postmortem: QLabel, completion: QLabel, parent: QWidget
    ) -> None:
        self.notes_text, self.postmortem, self.completion = (
            notes,
            postmortem,
            completion,
        )
        self.notes = ContentPanel("Resolution notes", parent=parent)
        self.notes.setObjectName("detailResolutionNotesPanel")
        self.notes.body_layout.addWidget(notes)
        self.reflection = ContentPanel("Postmortem", parent=parent)
        self.reflection.setObjectName("detailPostmortemPanel")
        self.empty = QLabel(
            "Postmortem not written. You can write it whenever you are ready.",
            self.reflection,
        )
        self.empty.setWordWrap(True)
        apply_text_role(self.empty, TextRole.SECONDARY)
        self.reflection.body_layout.addWidget(postmortem)
        self.reflection.body_layout.addWidget(completion)
        self.reflection.body_layout.addWidget(self.empty)
        for panel in (self.notes, self.reflection):
            apply_surface_role(panel, SurfaceRole.CANVAS)

    def sync(self, status: PredictionStatus) -> None:
        resolved = status is PredictionStatus.RESOLVED
        self.notes.setVisible(resolved and bool(self.notes_text.text().strip()))
        self.reflection.setVisible(resolved)
        self.postmortem.setVisible(bool(self.postmortem.text().strip()))
        self.completion.setVisible(bool(self.completion.text().strip()))
        self.empty.setVisible(
            not self.postmortem.text().strip() and not self.completion.text().strip()
        )


def terminal_timeline_rows(
    resolution: BinaryResolutionHistory | NumericResolutionHistory | None,
    invalidation: InvalidationHistory | None,
    parent: QWidget,
    *,
    unit: str = "",
) -> list[tuple[datetime, int, QWidget]]:
    """Use recorded-at facts for chronology; never substitute effective cutoff time."""
    rows: list[tuple[datetime, int, QWidget]] = []

    def add(instant: datetime, priority: int, name: str, title: str, body: str) -> None:
        row = QFrame(parent)
        row.setObjectName(name)
        apply_surface_role(row, SurfaceRole.CANVAS)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(
            int(Spacing.ORDINARY),
            int(Spacing.CONTROL),
            int(Spacing.ORDINARY),
            int(Spacing.CONTROL),
        )
        for text, role in (
            (title, TextRole.LABEL),
            (exact_detail_time(instant), TextRole.SECONDARY),
            (body, TextRole.BODY),
        ):
            if not text:
                continue
            label = QLabel(text, row)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            apply_text_role(label, role)
            if role is TextRole.SECONDARY:
                label.setToolTip(instant.isoformat())
            layout.addWidget(label)
        rows.append((instant, priority, row))

    if resolution is not None:
        original = resolution.original
        outcome = (
            "Original outcome: " + original.outcome.value.capitalize()
            if isinstance(resolution, BinaryResolutionHistory)
            else "Original actual value: "
            + str(original.actual_value)
            + (" " + unit if unit else "")
        )
        add(
            original.resolved_at,
            10,
            "terminalResolutionRecorded",
            "Resolution recorded",
            outcome
            + "\nThe original decision remains in history. Current effective results are above.",
        )
        for correction in resolution.corrections:
            reflection_only = correction.changed_fields == ("postmortem",)
            add(
                correction.corrected_at,
                20,
                f"terminalReflectionUpdated{correction.correction_id}"
                if reflection_only
                else f"terminalResolutionCorrection{correction.correction_id}",
                "Postmortem updated" if reflection_only else "Resolution corrected",
                correction.correction_reason
                or "The complete before/after facts are available in correction history.",
            )
        if resolution.postmortem_completion is not None:
            add(
                resolution.postmortem_completion.completed_at,
                30,
                "terminalPostmortemSkipped",
                "Postmortem deliberately skipped",
                "You may still write a Postmortem later. This completion remains in history.",
            )
    if invalidation is not None:
        original = invalidation.original
        add(
            original.invalidated_at,
            10,
            "terminalInvalidationRecorded",
            "Marked Invalid · Not scored",
            "Original Invalid decision. This prediction is preserved outside scoring.",
        )
        for correction in invalidation.corrections:
            add(
                correction.corrected_at,
                20,
                f"terminalInvalidationCorrection{correction.correction_id}",
                "Invalid reason corrected",
                "The reason wording was corrected. The original decision date is unchanged; before/after wording is available in reason history.",
            )
    return rows
