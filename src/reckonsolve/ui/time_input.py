"""Keyboard-first wall-clock time entry, independent of dates and storage."""

from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QTime, QTimeZone
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QTimeEdit, QWidget


class SegmentedTimeEdit(QTimeEdit):
    """One native field with predictable hour -> minute -> AM/PM tab stops."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry_section = self.Section.NoSection
        self._digits = ""
        self.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.setTimeZone(QTimeZone.utc())  # Carrier only; never a resolution instant.
        self.setDisplayFormat("hh:mm AP")
        self.setButtonSymbols(self.ButtonSymbols.NoButtons)
        self.setWrapping(True)
        self.setToolTip(
            "Type hours, Tab, minutes, Tab, then A or P. "
            "Use Up/Down to adjust a section, or Shift+Tab to go back."
        )
        self.setAccessibleDescription(self.toolTip())
        self.lineEdit().installEventFilter(self)

    def _reset_entry(self) -> None:
        self._entry_section = self.Section.NoSection
        self._digits = ""

    def keyPressEvent(self, event: QKeyEvent) -> None:
        section = self.currentSection()
        modified = event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        text = event.text()
        if not self.isReadOnly() and not modified:
            if (
                len(text) == 1
                and text in "0123456789"
                and section in (self.Section.HourSection, self.Section.MinuteSection)
            ):
                prefix = self._digits if self._entry_section == section else ""
                digits = (prefix if len(prefix) < 2 else "") + text
                maximum = 12 if section == self.Section.HourSection else 59
                number = min(int(digits), maximum)
                current = self.time()
                hour = (
                    number % 12 + (12 if current.hour() >= 12 else 0)
                    if section == self.Section.HourSection
                    else current.hour()
                )
                minute = (
                    number
                    if section == self.Section.MinuteSection
                    else current.minute()
                )
                self.setTime(QTime(hour, minute))
                self.setSelectedSection(section)
                self._entry_section, self._digits = section, digits
                # Keep valid input in its section for an explicit Tab. An
                # over-range entry is bounded and advances, like a browser's
                # native time field (e.g. 13 becomes 12, then selects minutes).
                if int(digits) > maximum:
                    self.setSelectedSection(
                        self.Section.MinuteSection
                        if section == self.Section.HourSection
                        else self.Section.AmPmSection
                    )
                    self._reset_entry()
                event.accept()
                return
            if text.lower() in ("a", "p"):
                current = self.time()
                self.setTime(
                    QTime(
                        current.hour() % 12 + (12 if text.lower() == "p" else 0),
                        current.minute(),
                    )
                )
                self.setSelectedSection(self.Section.AmPmSection)
                self._reset_entry()
                event.accept()
                return
        self._reset_entry()
        super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self._reset_entry()
        super().focusInEvent(event)
        if event.reason() == Qt.FocusReason.TabFocusReason:
            self.setSelectedSection(self.Section.HourSection)
        elif event.reason() == Qt.FocusReason.BacktabFocusReason:
            self.setSelectedSection(self.Section.AmPmSection)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.lineEdit() and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
        ):
            self._reset_entry()
        return super().eventFilter(watched, event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._reset_entry()
        super().focusOutEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._reset_entry()
        super().mousePressEvent(event)
        self.setSelectedSection(self.currentSection())

    def stepBy(self, steps: int) -> None:
        self._reset_entry()
        super().stepBy(steps)
