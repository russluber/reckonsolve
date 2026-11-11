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
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QLabel,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
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


def test_analytics_screen_replaces_the_placeholder(window: MainWindow) -> None:
    window.navigate_to("Analytics")

    assert _required_child(window, QWidget, "analyticsScreen").objectName() == (
        "analyticsScreen"
    )
    assert window.findChild(QLabel, "analyticsScreenPlaceholder") is None


def test_analytics_empty_state_is_honest_for_a_new_database(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.resize(1600, 900)
    window.show()

    window.navigate_to("Analytics")

    assert _required_child(window, QLabel, "analyticsEmpty").text() == (
        "No scored predictions yet. Resolve a prediction to begin analytics."
    )
    assert _required_child(window, QWidget, "analyticsScrollArea").isHidden()
    filters = _required_child(window, ContentPanel, "analyticsFiltersPanel")
    empty_region = _required_child(window, QWidget, "analyticsEmptyRegion")
    empty_label = _required_child(window, QLabel, "analyticsEmpty")
    assert filters.height() <= filters.sizeHint().height()
    assert empty_region.isVisible()
    assert empty_label.isVisible()
    assert empty_label.mapTo(empty_region, empty_label.rect().topLeft()).y() == 0
    assert empty_region.height() > empty_label.height()


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()
