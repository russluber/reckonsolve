"""Application shell, navigation, keyboard, and theme integration."""

from __future__ import annotations

from main_window_fakes import (
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from main_window_helpers import (
    operations as operations,  # noqa: PLC0414 - pytest fixture registration
)
from main_window_helpers import (
    window as window,  # noqa: PLC0414 - pytest fixture registration
)
from performance_helpers import loaded
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QLabel,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.performance import Section
from reckonsolve.ui import MainWindow
from reckonsolve.ui.presentation_settings import (
    MemoryPresentationSettings,
    WindowPresentationState,
)

EXPECTED_SCREEN_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)


EXPECTED_NAVIGATION_NAMES = (
    "Dashboard",
    "Predictions",
    "Analytics",
)


def test_window_geometry_and_maximized_state_restore_without_minimized_state(
    qtbot: QtBot,
) -> None:
    screens = (QRect(0, 0, 1920, 1080),)
    settings = MemoryPresentationSettings(
        WindowPresentationState(
            normal_geometry=(140, 90, 1100, 720),
            maximized=True,
        )
    )
    first = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=screens,
    )
    qtbot.addWidget(first)

    assert first.windowState() & Qt.WindowState.WindowMaximized
    assert not first.windowState() & Qt.WindowState.WindowMinimized
    first.close()

    reopened = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=screens,
    )
    qtbot.addWidget(reopened)

    assert reopened.windowState() & Qt.WindowState.WindowMaximized
    assert not reopened.windowState() & Qt.WindowState.WindowMinimized
    assert reopened.normalGeometry() == QRect(140, 90, 1100, 720)


def test_analytics_screen_replaces_the_placeholder(window: MainWindow, qtbot) -> None:
    window.navigate_to("Performance")
    loaded(window._analytics_screen, qtbot, refresh=False)
    assert (
        _required_child(window, QWidget, "analyticsScreen").objectName()
        == "analyticsScreen"
    )
    assert window.findChild(QLabel, "analyticsScreenPlaceholder") is None


def test_analytics_empty_state_is_honest_for_a_new_database(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.resize(1600, 900)
    window.show()
    window.navigate_to("Performance")
    screen = window._analytics_screen
    loaded(screen, qtbot, refresh=False)
    assert "No eligible results" in screen.message.text()
    assert screen.scroll_area.isVisible()
    assert screen.tag_filter.isEnabled() and screen.reset_button.isEnabled()
    assert all(section.isVisible() for section in screen.sections.values())
    assert all(result.error is None for result in screen.report.sections)
    for key in (Section.ADAPTIVE_BINARY, Section.ONE_SHOT_BINARY):
        section = screen.sections[key]
        assert section.count.text() == "0" and section.score.text() == "Not available"
        assert section.comparison.isHidden()


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()
