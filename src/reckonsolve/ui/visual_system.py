"""Central palette-aware presentation primitives for the desktop interface.

The module deliberately owns presentation only.  Semantic properties let screens
state intent (for example, "primary action" or "error message") while one
palette-derived stylesheet decides how that intent is rendered.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLabel,
    QStyle,
    QWidget,
)

TEXT_ROLE_PROPERTY = "reckonsolveTextRole"
SURFACE_ROLE_PROPERTY = "reckonsolveSurfaceRole"
ACTION_ROLE_PROPERTY = "reckonsolveActionRole"
BADGE_TONE_PROPERTY = "reckonsolveBadgeTone"
MESSAGE_TONE_PROPERTY = "reckonsolveMessageTone"
VISUAL_SYSTEM_PROPERTY = "reckonsolveVisualSystem"


class Spacing(IntEnum):
    """Shared logical-pixel spacing values."""

    COMPACT = 6
    CONTROL = 8
    ORDINARY = 12
    SECTION = 20
    PAGE = 24


class Radius(IntEnum):
    """Shared logical-pixel corner radii."""

    SMALL = 4
    CONTROL = 7
    PANEL = 10


class MotionDuration(IntEnum):
    """Maximum durations for the restrained motion allowed by the product."""

    QUICK = 120
    DISCLOSURE = 180


class TextRole(StrEnum):
    """Relative typography roles based on the native application font."""

    BODY = "body"
    SECONDARY = "secondary"
    LABEL = "label"
    SECTION_TITLE = "section-title"
    PAGE_TITLE = "page-title"
    FORECAST = "forecast"


class SurfaceRole(StrEnum):
    """Semantic surface hierarchy for reusable regions."""

    CANVAS = "canvas"
    BASE = "base"
    RAISED = "raised"
    SELECTED = "selected"
    INPUT = "input"
    WARNING = "warning"
    ERROR = "error"
    DESTRUCTIVE = "destructive"


class ActionRole(StrEnum):
    """Visual hierarchy for controls that perform an action."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    QUIET = "quiet"
    DESTRUCTIVE = "destructive"


class StatusTone(StrEnum):
    """Text-preserving semantic tones for badges and message regions."""

    NEUTRAL = "neutral"
    ACCENT = "accent"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True, slots=True)
class SemanticColors:
    """Resolved opaque colors for one active Qt palette."""

    is_dark: bool
    canvas: str
    surface: str
    raised: str
    input: str
    text: str
    secondary_text: str
    border: str
    disabled_text: str
    disabled_surface: str
    accent: str
    on_accent: str
    accent_soft: str
    on_accent_soft: str
    focus: str
    warning: str
    warning_surface: str
    error: str
    error_surface: str
    destructive: str
    destructive_surface: str


_TEXT_ROLE_DELTAS = {
    TextRole.BODY: 0.0,
    TextRole.SECONDARY: 0.0,
    TextRole.LABEL: 0.0,
    TextRole.SECTION_TITLE: 1.0,
    TextRole.PAGE_TITLE: 4.0,
    TextRole.FORECAST: 7.0,
}

_TEXT_ROLE_WEIGHTS = {
    TextRole.BODY: QFont.Weight.Normal,
    TextRole.SECONDARY: QFont.Weight.Normal,
    TextRole.LABEL: QFont.Weight.DemiBold,
    TextRole.SECTION_TITLE: QFont.Weight.DemiBold,
    TextRole.PAGE_TITLE: QFont.Weight.Bold,
    TextRole.FORECAST: QFont.Weight.Bold,
}


def semantic_colors(palette: QPalette) -> SemanticColors:
    """Resolve the shared light or dark color treatment from ``palette``."""

    canvas = _opaque(palette.color(QPalette.ColorRole.Window))
    text = _opaque(palette.color(QPalette.ColorRole.WindowText))
    is_dark = QColor(canvas).lightnessF() < 0.5
    surface = _theme_surface_color(
        _opaque(palette.color(QPalette.ColorRole.Base)),
        canvas,
        text,
        is_dark=is_dark,
        fallback_mix=0.035,
    )
    raised = _theme_surface_color(
        _opaque(palette.color(QPalette.ColorRole.AlternateBase)),
        canvas,
        text,
        is_dark=is_dark,
        fallback_mix=0.075,
    )
    input_color = _theme_surface_color(
        _opaque(palette.color(QPalette.ColorRole.Base)),
        canvas,
        text,
        is_dark=is_dark,
        fallback_mix=0.05,
    )

    secondary_candidate = _opaque(palette.color(QPalette.ColorRole.PlaceholderText))
    secondary_text = _contrast_fallback(
        secondary_candidate,
        canvas,
        text,
        minimum=4.5,
    )
    border_candidate = _opaque(palette.color(QPalette.ColorRole.Mid))
    border = _contrast_fallback(
        border_candidate,
        canvas,
        "#75808c" if is_dark else "#66717d",
        minimum=2.0,
    )

    if is_dark:
        return SemanticColors(
            is_dark=True,
            canvas=canvas,
            surface=surface,
            raised=raised,
            input=input_color,
            text=text,
            secondary_text=secondary_text,
            border=border,
            disabled_text="#89928d",
            disabled_surface="#2a302d",
            accent="#55c995",
            on_accent="#071a12",
            accent_soft="#193d30",
            on_accent_soft="#c7f4df",
            focus="#74e2ae",
            warning="#f0c66d",
            warning_surface="#3a2f17",
            error="#ff9a92",
            error_surface="#45211f",
            destructive="#ff8e87",
            destructive_surface="#48201e",
        )

    return SemanticColors(
        is_dark=False,
        canvas=canvas,
        surface=surface,
        raised=raised,
        input=input_color,
        text=text,
        secondary_text=secondary_text,
        border=border,
        disabled_text="#747b78",
        disabled_surface="#e3e7e5",
        accent="#176b4d",
        on_accent="#ffffff",
        accent_soft="#e3f2eb",
        on_accent_soft="#124f3a",
        focus="#0f7651",
        warning="#765200",
        warning_surface="#fff2c2",
        error="#a82a23",
        error_surface="#fde9e7",
        destructive="#a82a23",
        destructive_surface="#fde9e7",
    )


def build_stylesheet(palette: QPalette) -> str:
    """Build the single semantic Qt stylesheet for ``palette``."""

    color = semantic_colors(palette)
    control_radius = int(Radius.CONTROL)
    panel_radius = int(Radius.PANEL)
    compact = int(Spacing.COMPACT)
    control = int(Spacing.CONTROL)
    ordinary = int(Spacing.ORDINARY)

    return f"""
QMainWindow#mainWindow,
QWidget#mainContent,
QStackedWidget#screenStack,
QDialog {{
    background-color: {color.canvas};
    color: {color.text};
}}

QLabel[reckonsolveTextRole="secondary"] {{
    color: {color.secondary_text};
}}
QLabel[reckonsolveTextRole="label"] {{
    color: {color.text};
}}
QLabel[reckonsolveTextRole="section-title"] {{
    color: {color.text};
}}
QLabel[reckonsolveTextRole="page-title"] {{
    color: {color.text};
}}
QLabel[reckonsolveTextRole="forecast"] {{
    color: {color.accent};
}}

QWidget[reckonsolveSurfaceRole="canvas"],
QFrame[reckonsolveSurfaceRole="canvas"] {{
    background-color: {color.canvas};
    color: {color.text};
    border: none;
}}
QWidget[reckonsolveSurfaceRole="base"],
QFrame[reckonsolveSurfaceRole="base"] {{
    background-color: {color.surface};
    border: 1px solid {color.border};
    border-radius: {panel_radius}px;
}}
QWidget[reckonsolveSurfaceRole="raised"],
QFrame[reckonsolveSurfaceRole="raised"],
QGroupBox[reckonsolveSurfaceRole="raised"],
QLabel[reckonsolveSurfaceRole="raised"] {{
    background-color: {color.raised};
    border: 1px solid {color.border};
    border-radius: {panel_radius}px;
}}
QWidget[reckonsolveSurfaceRole="selected"],
QFrame[reckonsolveSurfaceRole="selected"],
QLabel[reckonsolveSurfaceRole="selected"] {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border: 1px solid {color.accent};
    border-radius: {panel_radius}px;
}}
QWidget[reckonsolveSurfaceRole="warning"],
QFrame[reckonsolveSurfaceRole="warning"] {{
    background-color: {color.warning_surface};
    color: {color.warning};
    border: 1px solid {color.warning};
    border-radius: {panel_radius}px;
}}
QWidget[reckonsolveSurfaceRole="error"],
QFrame[reckonsolveSurfaceRole="error"] {{
    background-color: {color.error_surface};
    color: {color.error};
    border: 1px solid {color.error};
    border-radius: {panel_radius}px;
}}

QLineEdit,
QPlainTextEdit,
QTextEdit,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QComboBox {{
    background-color: {color.input};
    color: {color.text};
    border: 1px solid {color.border};
    border-radius: {control_radius}px;
    padding: {compact}px {control}px;
    selection-background-color: {color.accent};
    selection-color: {color.on_accent};
}}
QLineEdit:hover,
QPlainTextEdit:hover,
QTextEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QDateEdit:hover,
QComboBox:hover {{
    border-color: {color.secondary_text};
}}
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QComboBox:focus {{
    border: 2px solid {color.focus};
}}
QLineEdit:disabled,
QPlainTextEdit:disabled,
QTextEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QDateEdit:disabled,
QComboBox:disabled {{
    background-color: {color.disabled_surface};
    color: {color.disabled_text};
    border-color: {color.border};
}}

QPushButton {{
    background-color: {color.raised};
    color: {color.text};
    border: 1px solid {color.border};
    border-radius: {control_radius}px;
    padding: {compact}px {ordinary}px;
}}
QPushButton:hover {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border-color: {color.accent};
}}
QPushButton:pressed {{
    background-color: {color.accent};
    color: {color.on_accent};
}}
QPushButton:focus {{
    border: 2px solid {color.focus};
}}
QPushButton:disabled {{
    background-color: {color.disabled_surface};
    color: {color.disabled_text};
    border-color: {color.border};
}}

QPushButton[reckonsolveActionRole="primary"] {{
    background-color: {color.accent};
    color: {color.on_accent};
    border-color: {color.accent};
    font-weight: 600;
}}
QPushButton[reckonsolveActionRole="primary"]:hover {{
    background-color: {color.focus};
    color: {color.on_accent};
}}
QPushButton[reckonsolveActionRole="primary"]:pressed {{
    background-color: {color.on_accent_soft};
    color: {color.on_accent};
}}
QPushButton[reckonsolveActionRole="primary"]:focus {{
    border: 2px solid {color.on_accent};
}}
QPushButton[reckonsolveActionRole="primary"]:disabled {{
    background-color: {color.disabled_surface};
    color: {color.disabled_text};
    border-color: {color.border};
}}

QPushButton[reckonsolveActionRole="secondary"] {{
    background-color: {color.raised};
    color: {color.text};
}}
QPushButton[reckonsolveActionRole="quiet"] {{
    background-color: transparent;
    color: {color.text};
    border-color: transparent;
}}
QPushButton[reckonsolveActionRole="quiet"]:hover {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border-color: {color.accent_soft};
}}
QPushButton[reckonsolveActionRole="destructive"] {{
    background-color: transparent;
    color: {color.destructive};
    border-color: {color.destructive};
    font-weight: 600;
}}
QPushButton[reckonsolveActionRole="destructive"]:hover {{
    background-color: {color.destructive_surface};
    color: {color.destructive};
}}
QPushButton[reckonsolveActionRole="destructive"]:pressed {{
    background-color: {color.destructive};
    color: {color.on_accent};
}}
QPushButton[reckonsolveActionRole="destructive"]:focus {{
    border: 2px solid {color.focus};
}}
QPushButton[reckonsolveActionRole="destructive"]:disabled {{
    background-color: transparent;
    color: {color.disabled_text};
    border-color: {color.border};
}}

QLabel[reckonsolveBadgeTone] {{
    border-radius: {int(Radius.SMALL)}px;
    padding: 2px {compact}px;
    font-weight: 600;
}}
QLabel[reckonsolveBadgeTone="neutral"] {{
    background-color: {color.raised};
    color: {color.text};
    border: 1px solid {color.border};
}}
QLabel[reckonsolveBadgeTone="accent"],
QLabel[reckonsolveBadgeTone="success"] {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border: 1px solid {color.accent};
}}
QLabel[reckonsolveBadgeTone="warning"] {{
    background-color: {color.warning_surface};
    color: {color.warning};
    border: 1px solid {color.warning};
}}
QLabel[reckonsolveBadgeTone="error"],
QLabel[reckonsolveBadgeTone="destructive"] {{
    background-color: {color.error_surface};
    color: {color.error};
    border: 1px solid {color.error};
}}

QLabel[reckonsolveMessageTone] {{
    border-radius: {control_radius}px;
    padding: {control}px {ordinary}px;
}}
QLabel[reckonsolveMessageTone="neutral"] {{
    background-color: {color.raised};
    color: {color.text};
    border: 1px solid {color.border};
}}
QLabel[reckonsolveMessageTone="accent"],
QLabel[reckonsolveMessageTone="success"] {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border: 1px solid {color.accent};
}}
QLabel[reckonsolveMessageTone="warning"] {{
    background-color: {color.warning_surface};
    color: {color.warning};
    border: 1px solid {color.warning};
}}
QLabel[reckonsolveMessageTone="error"],
QLabel[reckonsolveMessageTone="destructive"] {{
    background-color: {color.error_surface};
    color: {color.error};
    border: 1px solid {color.error};
}}

QGroupBox {{
    border: 1px solid {color.border};
    border-radius: {panel_radius}px;
    margin-top: {ordinary}px;
    padding-top: {compact}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {ordinary}px;
    top: 2px;
    padding: 0 {int(Radius.SMALL)}px;
    color: {color.secondary_text};
}}

QListWidget {{
    background-color: {color.surface};
    color: {color.text};
    border: 1px solid {color.border};
    border-radius: {panel_radius}px;
    outline: 0;
}}
QListWidget::item {{
    border-radius: {int(Radius.SMALL)}px;
    padding: {control}px;
}}
QListWidget::item:hover {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
}}
QListWidget::item:selected {{
    background-color: {color.accent_soft};
    color: {color.on_accent_soft};
    border-left: 3px solid {color.accent};
}}
QListWidget:focus {{
    border: 2px solid {color.focus};
}}

QCheckBox:focus,
QRadioButton:focus,
QGroupBox:focus {{
    border: 1px solid {color.focus};
}}

QWidget[searchMatchEmphasis="true"] {{
    background-color: {color.accent_soft};
    border: 2px solid {color.focus};
    border-radius: {control_radius}px;
}}
""".strip()


def install_visual_system(root: QWidget) -> None:
    """Install or refresh the visual system on one top-level widget tree."""

    root.setProperty(VISUAL_SYSTEM_PROPERTY, True)
    root.setStyleSheet(build_stylesheet(root.palette()))
    refresh_semantic_fonts(root)


def refresh_visual_system(root: QWidget) -> None:
    """Re-resolve stylesheet colors and semantic fonts after a theme change."""

    install_visual_system(root)


def is_visual_system_change(event: QEvent) -> bool:
    """Return whether an event requires palette or font semantics to refresh."""

    return event.type() in (
        QEvent.Type.PaletteChange,
        QEvent.Type.ApplicationPaletteChange,
        QEvent.Type.FontChange,
        QEvent.Type.ApplicationFontChange,
    )


def apply_text_role(widget: QWidget, role: TextRole) -> None:
    """Assign a semantic typography role while retaining the native font."""

    widget.setProperty(TEXT_ROLE_PROPERTY, role.value)
    _apply_semantic_font(widget, role)
    refresh_widget_style(widget)


def apply_surface_role(widget: QWidget, role: SurfaceRole) -> None:
    """Assign a semantic surface role to a reusable region."""

    widget.setProperty(SURFACE_ROLE_PROPERTY, role.value)
    refresh_widget_style(widget)


def apply_action_role(
    button: QAbstractButton,
    role: ActionRole,
    *,
    accessible_name: str | None = None,
) -> None:
    """Assign an action role and guarantee a meaningful accessible name."""

    resolved_name = (
        accessible_name or button.accessibleName() or _plain_button_text(button)
    )
    if not resolved_name:
        raise ValueError("An icon-only action requires an accessible name.")
    button.setAccessibleName(resolved_name)
    button.setProperty(ACTION_ROLE_PROPERTY, role.value)
    refresh_widget_style(button)


def apply_badge_role(label: QLabel, tone: StatusTone = StatusTone.NEUTRAL) -> None:
    """Style a compact status label without replacing its text meaning."""

    label.setProperty(BADGE_TONE_PROPERTY, tone.value)
    if not label.accessibleName() and label.text():
        label.setAccessibleName(label.text())
    refresh_widget_style(label)


def apply_message_role(
    label: QLabel,
    tone: StatusTone,
    *,
    accessible_name: str,
) -> None:
    """Style an inline message that remains in the page's normal layout."""

    if not accessible_name.strip():
        raise ValueError("A persistent message region requires an accessible name.")
    label.setAccessibleName(accessible_name)
    label.setProperty(MESSAGE_TONE_PROPERTY, tone.value)
    label.setWordWrap(True)
    refresh_widget_style(label)


def refresh_widget_style(widget: QWidget) -> None:
    """Re-evaluate dynamic-property selectors after a semantic role changes."""

    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def refresh_semantic_fonts(root: QWidget) -> None:
    """Reapply role-relative fonts after the native application font changes."""

    widgets = (root, *root.findChildren(QWidget))
    for widget in widgets:
        raw_role = widget.property(TEXT_ROLE_PROPERTY)
        if isinstance(raw_role, str) and raw_role:
            _apply_semantic_font(widget, TextRole(raw_role))


def animations_enabled(widget: QWidget | None = None) -> bool:
    """Honor Qt's platform animation preference for later restrained motion."""

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return False
    return bool(
        application.style().styleHint(
            QStyle.StyleHint.SH_Widget_Animate,
            None,
            widget,
        )
    )


def contrast_ratio(first: str | QColor, second: str | QColor) -> float:
    """Return the WCAG relative-luminance contrast ratio for two opaque colors."""

    first_luminance = _relative_luminance(QColor(first))
    second_luminance = _relative_luminance(QColor(second))
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _apply_semantic_font(widget: QWidget, role: TextRole) -> None:
    application = QApplication.instance()
    base_font = (
        application.font() if isinstance(application, QApplication) else widget.font()
    )
    base_size = base_font.pointSizeF()
    if base_size <= 0:
        base_size = widget.font().pointSizeF()
    font = QFont(base_font)
    if base_size > 0:
        font.setPointSizeF(max(8.0, base_size + _TEXT_ROLE_DELTAS[role]))
    font.setWeight(_TEXT_ROLE_WEIGHTS[role])
    widget.setFont(font)


def _plain_button_text(button: QAbstractButton) -> str:
    return button.text().replace("&", "").strip()


def _opaque(color: QColor) -> str:
    if color.alpha() < 255:
        color = QColor(color.red(), color.green(), color.blue())
    return color.name()


def _contrast_fallback(
    candidate: str,
    background: str,
    fallback: str,
    *,
    minimum: float,
) -> str:
    if contrast_ratio(candidate, background) >= minimum:
        return candidate
    return fallback


def _theme_surface_color(
    candidate: str,
    canvas: str,
    text: str,
    *,
    is_dark: bool,
    fallback_mix: float,
) -> str:
    """Reject native surface roles that conflict with the active theme.

    Some Windows dark palettes expose a white ``AlternateBase`` even though
    ``Window`` and ``WindowText`` describe a dark theme.  Using that role
    directly would produce white buttons and cards with white text.
    """

    candidate_is_dark = QColor(candidate).lightnessF() < 0.5
    if candidate_is_dark == is_dark and contrast_ratio(text, candidate) >= 4.5:
        return candidate
    return _mix_colors(canvas, text, fallback_mix)


def _mix_colors(background: str, foreground: str, amount: float) -> str:
    base = QColor(background)
    overlay = QColor(foreground)
    inverse = 1.0 - amount
    return QColor(
        round(base.red() * inverse + overlay.red() * amount),
        round(base.green() * inverse + overlay.green() * amount),
        round(base.blue() * inverse + overlay.blue() * amount),
    ).name()


def _relative_luminance(color: QColor) -> float:
    channels = (color.redF(), color.greenF(), color.blueF())

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


__all__ = [
    "ACTION_ROLE_PROPERTY",
    "BADGE_TONE_PROPERTY",
    "MESSAGE_TONE_PROPERTY",
    "SURFACE_ROLE_PROPERTY",
    "TEXT_ROLE_PROPERTY",
    "VISUAL_SYSTEM_PROPERTY",
    "ActionRole",
    "MotionDuration",
    "Radius",
    "SemanticColors",
    "Spacing",
    "StatusTone",
    "SurfaceRole",
    "TextRole",
    "animations_enabled",
    "apply_action_role",
    "apply_badge_role",
    "apply_message_role",
    "apply_surface_role",
    "apply_text_role",
    "build_stylesheet",
    "contrast_ratio",
    "install_visual_system",
    "is_visual_system_change",
    "refresh_semantic_fonts",
    "refresh_visual_system",
    "refresh_widget_style",
    "semantic_colors",
]
