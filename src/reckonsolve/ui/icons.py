"""Palette-aware rendering for the selected offline Lucide SVG resources."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from importlib.resources import files

from PySide6.QtCore import QByteArray, QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QWidget

from reckonsolve.ui.assets import icons as icon_resources
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    ActionRole,
    semantic_colors,
)

_RESOURCE_PACKAGE = "reckonsolve.ui.assets.icons"
_RENDER_SIZES = (16, 20, 24, 32, 40, 48)
_ICON_NAME_PROPERTY = "reckonsolveLucideIcon"


class LucideIcon(StrEnum):
    """The deliberately small Lucide subset used by Reckonsolve."""

    ARROW_LEFT = "arrow-left"
    ARROW_RIGHT = "arrow-right"
    BAN = "ban"
    CHART = "chart-no-axes-combined"
    CIRCLE_CHECK = "circle-check"
    CIRCLE_PLUS = "circle-plus"
    DATABASE_BACKUP = "database-backup"
    ERASER = "eraser"
    FILE_ARCHIVE = "file-archive"
    FILE_TEXT = "file-text"
    LAYOUT_DASHBOARD = "layout-dashboard"
    LIST_FILTER = "list-filter"
    NOTEBOOK_PEN = "notebook-pen"
    PENCIL = "pencil"
    REFRESH = "refresh-cw"
    SAVE = "save"
    SEARCH = "search"
    SETTINGS = "settings"
    TRASH = "trash-2"


class LucideResourceError(RuntimeError):
    """Raised when a bundled icon is absent or cannot be rendered."""


def lucide_icon(name: LucideIcon, palette: QPalette) -> QIcon:
    """Return one multi-size icon colored for normal, disabled, and selected UI."""

    colors = semantic_colors(palette)
    return _cached_icon(
        name.value,
        _palette_color(palette, QPalette.ColorGroup.Normal, QPalette.ColorRole.Text),
        colors.disabled_text,
        colors.on_accent_soft,
    )


def apply_lucide_icon(
    button: QAbstractButton,
    name: LucideIcon,
    *,
    size: int = 18,
) -> None:
    """Apply and remember an icon while retaining the button's visible text."""

    button.setProperty(_ICON_NAME_PROPERTY, name.value)
    button.setProperty(f"{_ICON_NAME_PROPERTY}Size", size)
    button.setIcon(_button_icon(name, button))
    button.setIconSize(QSize(size, size))
    if not button.accessibleName() and button.text():
        button.setAccessibleName(button.text().replace("&", ""))


def refresh_lucide_icons(root: QWidget) -> None:
    """Re-render remembered button icons after the active Qt palette changes."""

    for button in root.findChildren(QAbstractButton):
        raw_name = button.property(_ICON_NAME_PROPERTY)
        if not isinstance(raw_name, str) or not raw_name:
            continue
        size = button.property(f"{_ICON_NAME_PROPERTY}Size")
        apply_lucide_icon(
            button,
            LucideIcon(raw_name),
            size=size if isinstance(size, int) else 18,
        )


def is_palette_change(event: QEvent) -> bool:
    """Return whether a Qt event requires palette-colored icons to be refreshed."""

    return event.type() in (
        QEvent.Type.PaletteChange,
        QEvent.Type.ApplicationPaletteChange,
    )


@lru_cache(maxsize=128)
def _cached_icon(
    name: str,
    normal_color: str,
    disabled_color: str,
    selected_color: str,
) -> QIcon:
    try:
        svg = (
            files(_RESOURCE_PACKAGE).joinpath(f"{name}.svg").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError) as error:
        raise LucideResourceError(
            f"The bundled Lucide icon {name!r} is unavailable."
        ) from error
    if "currentColor" not in svg:
        raise LucideResourceError(
            f"The bundled Lucide icon {name!r} cannot follow the active palette."
        )

    icon = QIcon()
    for mode, color in (
        (QIcon.Mode.Normal, normal_color),
        (QIcon.Mode.Active, normal_color),
        (QIcon.Mode.Disabled, disabled_color),
        (QIcon.Mode.Selected, selected_color),
    ):
        for size in _RENDER_SIZES:
            icon.addPixmap(
                _render_svg(svg, QColor(color), size),
                mode,
                QIcon.State.Off,
            )
    return icon


def _render_svg(svg: str, color: QColor, size: int) -> QPixmap:
    renderer = QSvgRenderer(
        QByteArray(svg.replace("currentColor", color.name()).encode("utf-8"))
    )
    if not renderer.isValid():
        raise LucideResourceError("A bundled Lucide SVG could not be rendered.")
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter, QRectF(0, 0, size, size))
    finally:
        painter.end()
    return pixmap


def _button_icon(name: LucideIcon, button: QAbstractButton) -> QIcon:
    palette = button.palette()
    colors = semantic_colors(button.window().palette())
    action_role = button.property(ACTION_ROLE_PROPERTY)
    if action_role == ActionRole.PRIMARY.value:
        normal_color = colors.on_accent
    elif action_role == ActionRole.DESTRUCTIVE.value:
        normal_color = colors.destructive
    else:
        normal_color = _palette_color(
            palette,
            QPalette.ColorGroup.Normal,
            QPalette.ColorRole.Text,
        )
    return _cached_icon(
        name.value,
        normal_color,
        colors.disabled_text,
        colors.on_accent_soft,
    )


def _palette_color(
    palette: QPalette,
    group: QPalette.ColorGroup,
    role: QPalette.ColorRole,
) -> str:
    return palette.color(group, role).name()


__all__ = [
    "LucideIcon",
    "LucideResourceError",
    "apply_lucide_icon",
    "icon_resources",
    "is_palette_change",
    "lucide_icon",
    "refresh_lucide_icons",
]
