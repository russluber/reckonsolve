"""Disposable, identity-isolated settings for the desktop presentation shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QRect, QSettings, QSize

DEFAULT_WINDOW_SIZE = QSize(960, 640)
MINIMUM_WINDOW_SIZE = QSize(760, 520)


@dataclass(frozen=True, slots=True)
class WindowPresentationState:
    """Noncanonical shell preferences loaded at desktop startup."""

    sidebar_compact: bool = False
    normal_geometry: tuple[int, int, int, int] | None = None
    maximized: bool = False


class PresentationSettings(Protocol):
    """Small persistence seam used by the shell and isolated by tests."""

    def load(self) -> WindowPresentationState:
        """Load valid values or safe defaults."""

    def save(self, state: WindowPresentationState) -> bool:
        """Persist a complete state, returning whether the write succeeded."""


class MemoryPresentationSettings:
    """Nonpersistent default for directly constructed windows and tests."""

    def __init__(
        self,
        state: WindowPresentationState | None = None,
    ) -> None:
        self.state = state or WindowPresentationState()

    def load(self) -> WindowPresentationState:
        return self.state

    def save(self, state: WindowPresentationState) -> bool:
        self.state = state
        return True


class QtPresentationSettings:
    """INI-backed Qt settings stored beside, but outside, canonical SQLite."""

    _SIDEBAR_KEY = "shell/sidebar_compact"
    _GEOMETRY_KEY = "window/normal_geometry"
    _MAXIMIZED_KEY = "window/maximized"

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> WindowPresentationState:
        try:
            settings = self._open()
            state = WindowPresentationState(
                sidebar_compact=_parse_bool(
                    settings.value(self._SIDEBAR_KEY),
                    default=False,
                ),
                normal_geometry=_parse_geometry(
                    settings.value(self._GEOMETRY_KEY),
                ),
                maximized=_parse_bool(
                    settings.value(self._MAXIMIZED_KEY),
                    default=False,
                ),
            )
            if settings.status() != QSettings.Status.NoError:
                return WindowPresentationState()
            return state
        except (OSError, RuntimeError, TypeError, ValueError):
            return WindowPresentationState()

    def save(self, state: WindowPresentationState) -> bool:
        try:
            settings = self._open()
            settings.setValue(self._SIDEBAR_KEY, state.sidebar_compact)
            geometry = state.normal_geometry
            if geometry is None:
                settings.remove(self._GEOMETRY_KEY)
            else:
                settings.setValue(
                    self._GEOMETRY_KEY,
                    ",".join(str(value) for value in geometry),
                )
            settings.setValue(self._MAXIMIZED_KEY, state.maximized)
            settings.sync()
            return settings.status() == QSettings.Status.NoError
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def _open(self) -> QSettings:
        return QSettings(str(self.path), QSettings.Format.IniFormat)


def safe_window_geometry(
    saved_geometry: tuple[int, int, int, int] | None,
    available_screens: tuple[QRect, ...],
    *,
    default_size: QSize = DEFAULT_WINDOW_SIZE,
    minimum_size: QSize = MINIMUM_WINDOW_SIZE,
) -> QRect:
    """Return a fully visible normal geometry or a centered safe default."""

    screens = tuple(screen for screen in available_screens if screen.isValid())
    if not screens:
        return QRect(100, 100, default_size.width(), default_size.height())

    if saved_geometry is not None:
        x, y, width, height = saved_geometry
        if width > 0 and height > 0:
            candidate = QRect(x, y, width, height)
            screen = _meaningfully_intersecting_screen(candidate, screens)
            if screen is not None:
                return _fit_inside(candidate, screen, minimum_size)

    primary = screens[0]
    width = min(max(default_size.width(), minimum_size.width()), primary.width())
    height = min(max(default_size.height(), minimum_size.height()), primary.height())
    return QRect(
        primary.left() + max(0, (primary.width() - width) // 2),
        primary.top() + max(0, (primary.height() - height) // 2),
        width,
        height,
    )


def _meaningfully_intersecting_screen(
    candidate: QRect,
    screens: tuple[QRect, ...],
) -> QRect | None:
    best: QRect | None = None
    best_area = 0
    for screen in screens:
        intersection = candidate.intersected(screen)
        area = intersection.width() * intersection.height()
        if area > best_area:
            best = screen
            best_area = area
    if best is None:
        return None

    intersection = candidate.intersected(best)
    required_width = min(160, max(96, candidate.width() // 4))
    required_height = min(120, max(64, candidate.height() // 4))
    if intersection.width() < required_width or intersection.height() < required_height:
        return None
    return best


def _fit_inside(candidate: QRect, screen: QRect, minimum_size: QSize) -> QRect:
    width = min(max(candidate.width(), minimum_size.width()), screen.width())
    height = min(max(candidate.height(), minimum_size.height()), screen.height())
    maximum_x = screen.right() - width + 1
    maximum_y = screen.bottom() - height + 1
    x = min(max(candidate.x(), screen.left()), maximum_x)
    y = min(max(candidate.y(), screen.top()), maximum_y)
    return QRect(x, y, width, height)


def _parse_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return default


def _parse_geometry(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    try:
        geometry = tuple(int(part.strip()) for part in parts)
    except ValueError:
        return None
    x, y, width, height = geometry
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "MINIMUM_WINDOW_SIZE",
    "MemoryPresentationSettings",
    "PresentationSettings",
    "QtPresentationSettings",
    "WindowPresentationState",
    "safe_window_geometry",
]
