"""Immediate appearance changes without rebuilding screens or entered work."""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from .presentation_settings import AppearanceMode
from .visual_system import VISUAL_SYSTEM_PROPERTY, refresh_visual_system


def appearance_palette(dark: bool) -> QPalette:
    """Use ordinary Qt roles so inputs, native widgets and dialogs stay legible."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: ("#f8fafc", "#171b20"),
        QPalette.ColorRole.Base: ("#ffffff", "#20262d"),
        QPalette.ColorRole.AlternateBase: ("#f0f3f7", "#262e38"),
        QPalette.ColorRole.WindowText: ("#16202c", "#e4ebf3"),
        QPalette.ColorRole.Text: ("#16202c", "#e4ebf3"),
        QPalette.ColorRole.Button: ("#edf2f7", "#283341"),
        QPalette.ColorRole.ButtonText: ("#253d55", "#bed8f2"),
        QPalette.ColorRole.Highlight: ("#325f8d", "#a9cdec"),
        QPalette.ColorRole.HighlightedText: ("#ffffff", "#142535"),
        QPalette.ColorRole.PlaceholderText: ("#5b6d80", "#abb9c9"),
        QPalette.ColorRole.Mid: ("#b3bfce", "#526172"),
        QPalette.ColorRole.ToolTipBase: ("#ffffff", "#26313f"),
        QPalette.ColorRole.ToolTipText: ("#16202c", "#e4ebf3"),
    }
    for role, colors in roles.items():
        palette.setColor(role, QColor(colors[int(dark)]))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor("#8f9aaa" if dark else "#6b7786")
        )
    return palette


class AppearanceController(QObject):
    changed = Signal(object)

    def __init__(self, mode: AppearanceMode, parent: QObject) -> None:
        super().__init__(parent)
        self.mode = mode
        self._applying = False
        self._active = True
        application = QApplication.instance()
        fallback = application.property("reckonsolveSystemDarkFallback")
        if fallback is None:
            fallback = (
                application.palette().color(QPalette.ColorRole.Window).lightnessF()
                < 0.5
            )
            application.setProperty("reckonsolveSystemDarkFallback", fallback)
        self._system_dark_fallback = bool(fallback)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_changed)
        self.apply()

    @property
    def dark(self) -> bool:
        if self.mode is not AppearanceMode.FOLLOW_WINDOWS:
            return self.mode is AppearanceMode.DARK
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme is Qt.ColorScheme.Unknown:
            return self._system_dark_fallback
        return scheme is Qt.ColorScheme.Dark

    def select(self, mode: AppearanceMode) -> None:
        self.mode = mode
        self.apply()
        self.changed.emit(mode)

    def toggle(self) -> None:
        self.select(AppearanceMode.LIGHT if self.dark else AppearanceMode.DARK)

    def apply(self) -> None:
        if self._applying:
            return
        self._applying = True
        try:
            hints = QGuiApplication.styleHints()
            if self.mode is AppearanceMode.FOLLOW_WINDOWS:
                hints.unsetColorScheme()
            else:
                hints.setColorScheme(
                    Qt.ColorScheme.Dark
                    if self.mode is AppearanceMode.DARK
                    else Qt.ColorScheme.Light
                )
            application = QApplication.instance()
            palette = appearance_palette(self.dark)
            application.setPalette(palette)
            for window in application.topLevelWidgets():
                if window is self.parent() or (
                    window.isVisible() and window.property(VISUAL_SYSTEM_PROPERTY)
                ):
                    window.setPalette(palette)
                    # A resolved stylesheet can mask its old palette colors.
                    # Rebuild from the authoritative choice, not those old colors.
                    if window.property(VISUAL_SYSTEM_PROPERTY):
                        refresh_visual_system(window, palette=palette)
        finally:
            self._applying = False

    def _system_changed(self, _scheme) -> None:
        if (
            self._active
            and not self._applying
            and self.mode is AppearanceMode.FOLLOW_WINDOWS
        ):
            self.apply()
            self.changed.emit(self.mode)

    def close(self) -> None:
        if self._active:
            self._active = False
            QGuiApplication.styleHints().colorSchemeChanged.disconnect(
                self._system_changed
            )
