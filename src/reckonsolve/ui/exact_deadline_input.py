"""Explicit deadline choices with local-calendar shortcuts and exact UTC output."""

from datetime import UTC, datetime

from PySide6.QtCore import QDateTime, Qt, QTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QGridLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ValidationError
from reckonsolve.clock import Clock, SystemClock
from reckonsolve.domain.forecast_contracts import ForecastDeadline
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    TextRole,
    apply_action_role,
    apply_text_role,
)


def _offset_text(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    minutes = abs(seconds) // 60
    return f"{sign}{minutes // 60:02}:{minutes % 60:02}"


class ExactDeadlineInput(QWidget):
    """A draft remains unset until a shortcut or Custom is explicitly chosen."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        clock: Clock | None = None,
        time_zone: QTimeZone | None = None,
    ) -> None:
        super().__init__(parent)
        self._clock = clock or SystemClock()
        self._zone = time_zone if time_zone is not None else QTimeZone.systemTimeZone()
        self._chosen = False
        self._columns = 0
        self._fold_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        title = QLabel("Forecast Deadline · Required", self)
        apply_text_role(title, TextRole.LABEL)
        layout.addWidget(title)

        self.shortcut_row = QWidget(self)
        self.shortcut_row.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.shortcuts = QGridLayout(self.shortcut_row)
        self.shortcuts.setContentsMargins(0, 0, 0, 0)
        self.shortcuts.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.shortcuts.setSpacing(int(Spacing.COMPACT))
        self.preset_buttons: dict[int, QPushButton] = {}
        for days, text in (
            (0, "End of today"),
            (1, "End of tomorrow"),
            (7, "7 days"),
            (30, "30 days"),
        ):
            button = QPushButton(text, self)
            button.setObjectName(f"deadlinePreset{days}")
            button.setToolTip(f"{text}: 11:59 PM in your local time zone.")
            apply_action_role(button, ActionRole.SECONDARY)
            button.clicked.connect(lambda _checked=False, d=days: self.choose_preset(d))
            self.preset_buttons[days] = button
        self.custom_button = QPushButton("Custom…", self)
        self.custom_button.setObjectName("deadlineCustom")
        apply_action_role(self.custom_button, ActionRole.SECONDARY)
        self.custom_button.clicked.connect(self.choose_custom)
        self._buttons = [*self.preset_buttons.values(), self.custom_button]
        layout.addWidget(self.shortcut_row)

        self.edit_controls = QWidget(self)
        fields = QVBoxLayout(self.edit_controls)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(int(Spacing.COMPACT))
        self.editor = QDateTimeEdit(self.edit_controls)
        # A UTC carrier preserves the typed wall time even during a DST gap.
        # Resolve against the local zone explicitly, never silently normalize it.
        self.editor.setTimeZone(QTimeZone.utc())
        self.editor.setObjectName("exactDeadlineInput")
        self.editor.setAccessibleName("Forecast Deadline date and time")
        self.editor.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.editor.setCalendarPopup(True)
        self.editor.setKeyboardTracking(False)
        fields.addWidget(self.editor, alignment=Qt.AlignmentFlag.AlignLeft)
        self.occurrence = QComboBox(self.edit_controls)
        self.occurrence.setAccessibleName("Choose which occurrence of this local time")
        fields.addWidget(self.occurrence, alignment=Qt.AlignmentFlag.AlignLeft)
        self.use_offset = QCheckBox("Use another UTC offset", self.edit_controls)
        self.use_offset.setObjectName("exactDeadlineUseOffset")
        self.offset = QLineEdit(self.edit_controls)
        self.offset.setObjectName("exactDeadlineOffset")
        self.offset.setAccessibleName("Forecast Deadline UTC offset")
        self.offset.setPlaceholderText("±HH:MM")
        self.offset.setMaximumWidth(110)
        layout.addWidget(self.edit_controls)

        self.summary = QLabel(self)
        self.summary.setObjectName("exactDeadlineSummary")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        apply_text_role(self.summary, TextRole.BODY)
        layout.addWidget(self.summary)
        layout.addWidget(self.use_offset)
        layout.addWidget(self.offset)
        note = QLabel(
            "Last moment you can revise or review this forecast. Permanent after "
            "creation; separate from Expected Resolution.",
            self,
        )
        note.setWordWrap(True)
        apply_text_role(note, TextRole.SECONDARY)
        layout.addWidget(note)

        self.editor.dateTimeChanged.connect(self._refresh)
        self.use_offset.toggled.connect(self._refresh)
        self.offset.textChanged.connect(self._refresh)
        self.occurrence.currentIndexChanged.connect(self._refresh)
        self.reset()
        self._layout_shortcuts()

    @property
    def is_set(self) -> bool:
        return self._chosen

    def _local_now(self) -> QDateTime:
        return QDateTime.fromMSecsSinceEpoch(
            int(self._clock.now().timestamp() * 1000), self._zone
        )

    def reset(self) -> None:
        self._chosen = False
        self._fold_key = None
        self.use_offset.setChecked(False)
        self.offset.clear()
        self._refresh()

    def choose_preset(self, days: int) -> None:
        """Resolve once at the click, not again when the draft is submitted."""
        self._chosen = True
        self.use_offset.setChecked(False)
        self.editor.setDateTime(
            QDateTime(
                self._local_now().date().addDays(days), QTime(23, 59), QTimeZone.utc()
            )
        )
        self._refresh()

    def choose_custom(self) -> None:
        if not self._chosen:
            self.choose_preset(0)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self.editor.setSelectedSection(QDateTimeEdit.Section.DaySection)

    def _local_candidates(self) -> list[QDateTime]:
        date = self.editor.date()
        time = QTime(self.editor.time().hour(), self.editor.time().minute())
        candidates = []
        for resolution in (
            QDateTime.TransitionResolution.PreferBefore,
            QDateTime.TransitionResolution.PreferAfter,
        ):
            candidate = QDateTime(date, time, self._zone, resolution)
            if (
                candidate.isValid()
                and candidate.date() == date
                and candidate.time() == time
                and candidate not in candidates
            ):
                candidates.append(candidate)
        return sorted(candidates, key=lambda candidate: candidate.toMSecsSinceEpoch())

    def _resolve(self) -> tuple[datetime, str]:
        if self.use_offset.isChecked():
            offset = self.offset.text().strip()
            wall = self.editor.dateTime().toString("yyyy-MM-dd'T'HH:mm") + ":00"
            try:
                if (
                    len(offset) != 6
                    or offset[0] not in "+-"
                    or offset[3] != ":"
                    or not offset[1:3].isascii()
                    or not offset[1:3].isdigit()
                    or not offset[4:].isascii()
                    or not offset[4:].isdigit()
                    or int(offset[1:3]) > 23
                    or int(offset[4:]) > 59
                ):
                    raise ValueError
                return (
                    ForecastDeadline(datetime.fromisoformat(wall + offset)).instant,
                    f"UTC{offset} · Explicit offset",
                )
            except ValueError as error:
                raise ValidationError(
                    "Enter a UTC offset such as -07:00 or +00:00.",
                    field="forecast_deadline",
                ) from error
        if not self._zone.isValid():
            raise ValidationError(
                "Your local time zone is unavailable. Use an explicit UTC offset.",
                field="forecast_deadline",
            )
        candidates = self._local_candidates()
        if not candidates:
            raise ValidationError(
                "This local time does not exist because the clocks move forward. "
                "Choose another time or use an explicit UTC offset.",
                field="forecast_deadline",
            )
        if len(candidates) > 1:
            index = self.occurrence.currentData()
            if index is None:
                raise ValidationError(
                    "This local time occurs twice. Choose its first or second occurrence.",
                    field="forecast_deadline",
                )
            candidate = candidates[index]
        else:
            candidate = candidates[0]
        zone_name = self._zone.displayName(candidate, QTimeZone.NameType.LongName)
        return (
            datetime.fromtimestamp(candidate.toSecsSinceEpoch(), UTC),
            f"{zone_name} · UTC{_offset_text(candidate.offsetFromUtc())}",
        )

    def _refresh(self, *_args: object) -> None:
        self.edit_controls.setVisible(self._chosen)
        self.use_offset.setVisible(self._chosen)
        self.offset.setVisible(self._chosen and self.use_offset.isChecked())
        candidates = self._local_candidates() if self._chosen else []
        ambiguous = len(candidates) == 2 and not self.use_offset.isChecked()
        self.occurrence.setVisible(ambiguous)
        key = self.editor.dateTime().toString("yyyy-MM-dd HH:mm") if ambiguous else None
        if key != self._fold_key:
            self._fold_key = key
            self.occurrence.blockSignals(True)
            self.occurrence.clear()
            if ambiguous:
                self.occurrence.addItem("Choose which occurrence…", None)
                for index, candidate in enumerate(candidates):
                    label = "First" if index == 0 else "Second"
                    self.occurrence.addItem(
                        f"{label} occurrence · UTC{_offset_text(candidate.offsetFromUtc())}",
                        index,
                    )
            self.occurrence.blockSignals(False)
        if not self._chosen:
            self.summary.setText("Not set — choose a shortcut or Custom.")
            return
        try:
            instant, zone_label = self._resolve()
            wall = self.editor.dateTime().toString("dddd, MMMM d, yyyy 'at' h:mm AP")
            text = f"{wall}\n{zone_label}"
            if instant <= self._clock.now():
                text += "\nChoose a future deadline before creating this prediction."
            self.summary.setText(text)
        except ValidationError as error:
            self.summary.setText(str(error))

    def value(self) -> datetime:
        if not self._chosen:
            raise ValidationError(
                "Set an exact Forecast Deadline before creating this prediction.",
                field="forecast_deadline",
            )
        # Commit pending typed date/time before reading the visible minute.
        self.editor.interpretText()
        return self._resolve()[0]

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_shortcuts()

    def _layout_shortcuts(self) -> None:
        width = max(button.sizeHint().width() for button in self._buttons)
        columns = max(
            1,
            min(
                len(self._buttons),
                (self.width() + self.shortcuts.spacing())
                // (width + self.shortcuts.spacing()),
            ),
        )
        if columns != self._columns:
            self._columns = columns
            while self.shortcuts.count():
                self.shortcuts.takeAt(0)
            for index, button in enumerate(self._buttons):
                self.shortcuts.addWidget(
                    button,
                    index // columns,
                    index % columns,
                    Qt.AlignmentFlag.AlignLeft,
                )
        for column in range(len(self._buttons) + 1):
            self.shortcuts.setColumnStretch(column, 1 if column == columns else 0)
