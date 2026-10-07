"""Application shell, navigation, keyboard, and theme integration."""

from __future__ import annotations

from datetime import UTC, datetime

from main_window_fakes import (
    FakePrediction,
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
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.forecast_contracts import ForecastDeadline, prospective_contract
from reckonsolve.domain.predictions import (
    PredictionStatus,
    PredictionType,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.presentation_settings import (
    MemoryPresentationSettings,
    WindowPresentationState,
)
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    NAVIGATION_ACTIVE_PROPERTY,
    NAVIGATION_COMPACT_PROPERTY,
    TEXT_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    TextRole,
    semantic_colors,
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


def test_main_window_has_expected_navigation(window: MainWindow) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    sidebar = _required_child(window, QFrame, "applicationSidebar")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")

    assert window.windowTitle() == "Reckonsolve"
    assert sidebar.minimumWidth() == 240
    assert sidebar.maximumWidth() == 240
    assert window.screen_names == EXPECTED_SCREEN_NAMES
    assert window.navigation_names == EXPECTED_NAVIGATION_NAMES
    assert (
        tuple(navigation.item(index).text() for index in range(navigation.count()))
        == EXPECTED_NAVIGATION_NAMES
    )
    assert "Prediction Detail" not in tuple(
        navigation.item(index).text() for index in range(navigation.count())
    )
    assert new_prediction.text() == "New Prediction"
    assert new_prediction.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert settings.text() == "Settings"
    assert toggle.accessibleName() == "Collapse sidebar"
    assert window.current_screen_name == "Dashboard"
    assert navigation.currentRow() == 0
    assert navigation.property(NAVIGATION_COMPACT_PROPERTY) is False
    assert all(
        not navigation.item(index).icon().isNull()
        for index in range(navigation.count())
    )


def test_primary_navigation_never_scrolls_or_clips_a_destination(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    window.show()
    qtbot.waitUntil(lambda: navigation.viewport().height() > 0)

    for row in range(navigation.count()):
        navigation.setCurrentRow(row)
        item_rectangle = navigation.visualItemRect(navigation.item(row))
        assert navigation.viewport().rect().contains(item_rectangle)
        assert navigation.verticalScrollBar().value() == 0

    assert navigation.verticalScrollBar().maximum() == 0
    assert navigation.visualItemRect(navigation.item(0)).top() >= 0
    assert (
        navigation.visualItemRect(navigation.item(navigation.count() - 1)).bottom()
        <= navigation.viewport().rect().bottom()
    )


def test_sidebar_compact_mode_is_complete_accessible_and_remembered(
    qtbot: QtBot,
) -> None:
    settings = MemoryPresentationSettings()
    first = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=(QRect(0, 0, 1920, 1080),),
    )
    qtbot.addWidget(first)
    first.show()
    sidebar = _required_child(first, QFrame, "applicationSidebar")
    navigation = _required_child(first, QListWidget, "primaryNavigation")
    new_prediction = _required_child(
        first,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings_button = _required_child(first, QPushButton, "settingsNavigationButton")
    identity = _required_child(first, QLabel, "sidebarIdentity")
    toggle = _required_child(first, QPushButton, "sidebarModeToggle")

    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)

    assert first.sidebar_compact
    assert navigation.property(NAVIGATION_COMPACT_PROPERTY) is True
    assert sidebar.minimumWidth() == 68
    assert sidebar.maximumWidth() == 68
    assert identity.isHidden()
    assert new_prediction.text() == ""
    assert new_prediction.accessibleName() == "New Prediction"
    assert new_prediction.toolTip() == "Create a new prediction (Ctrl+N)"
    assert settings_button.text() == ""
    assert settings_button.accessibleName() == "Settings"
    assert toggle.accessibleName() == "Expand sidebar"
    expected_tooltips = {
        "Dashboard": "Dashboard (Ctrl+1)",
        "Predictions": "Predictions (Ctrl+2; Ctrl+F focuses Search)",
        "Analytics": "Analytics (Ctrl+3)",
    }
    for index, screen_name in enumerate(EXPECTED_NAVIGATION_NAMES):
        item = navigation.item(index)
        assert item.text() == ""
        assert item.data(Qt.ItemDataRole.AccessibleTextRole) == screen_name
        assert item.toolTip() == expected_tooltips[screen_name]
        assert not item.icon().isNull()
        item_rectangle = navigation.visualItemRect(item)
        assert item_rectangle.width() > item_rectangle.height()
        assert (
            abs(item_rectangle.center().x() - navigation.viewport().rect().center().x())
            <= 1
        )
    assert settings.state.sidebar_compact

    first.close()
    reopened = MainWindow(
        FakePredictionOperations(),
        presentation_settings=settings,
        available_screens=(QRect(0, 0, 1920, 1080),),
    )
    qtbot.addWidget(reopened)

    assert reopened.sidebar_compact
    assert (
        _required_child(
            reopened,
            QFrame,
            "applicationSidebar",
        ).width()
        == 68
    )


def test_compact_navigation_paints_each_icon_in_the_center_of_its_tile(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")
    window.show()
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    navigation.setCurrentRow(0)
    test_icon_color = QColor("#ff00ff")
    test_icon_pixmap = QPixmap(navigation.iconSize())
    test_icon_pixmap.fill(test_icon_color)
    test_icon = QIcon()
    for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected):
        test_icon.addPixmap(test_icon_pixmap, mode, QIcon.State.Off)
    navigation.item(0).setIcon(test_icon)
    image = navigation.viewport().grab().toImage()
    tile = navigation.visualItemRect(navigation.item(0))
    icon_pixels = tuple(
        QPoint(x, y)
        for y in range(tile.top(), tile.bottom() + 1)
        for x in range(tile.left(), tile.right() + 1)
        if image.pixelColor(x, y) == test_icon_color
    )

    assert icon_pixels
    painted_icon = QRect(
        QPoint(
            min(point.x() for point in icon_pixels),
            min(point.y() for point in icon_pixels),
        ),
        QPoint(
            max(point.x() for point in icon_pixels),
            max(point.y() for point in icon_pixels),
        ),
    )
    assert painted_icon.size() == navigation.iconSize()
    assert abs(painted_icon.center().x() - tile.center().x()) <= 1
    assert abs(painted_icon.center().y() - tile.center().y()) <= 1


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


def test_shell_distinguishes_action_primary_and_bottom_utility_routes(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    sidebar = _required_child(window, QFrame, "applicationSidebar")
    sidebar_layout = sidebar.layout()
    assert sidebar_layout is not None
    assert sidebar_layout.itemAt(sidebar_layout.count() - 2).spacerItem() is not None
    assert sidebar_layout.itemAt(sidebar_layout.count() - 1).widget() is settings

    qtbot.mouseClick(new_prediction, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "New Prediction"
    assert navigation.currentRow() == -1
    assert new_prediction.property(NAVIGATION_ACTIVE_PROPERTY) is True
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is False

    qtbot.mouseClick(settings, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "Settings"
    assert navigation.currentRow() == -1
    assert new_prediction.property(NAVIGATION_ACTIVE_PROPERTY) is False
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is True

    navigation.setCurrentRow(1)
    assert window.current_screen_name == "Predictions"
    assert settings.property(NAVIGATION_ACTIVE_PROPERTY) is False


def test_shell_navigation_remains_keyboard_operable_in_compact_mode(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    toggle = _required_child(window, QPushButton, "sidebarModeToggle")
    new_prediction = _required_child(
        window,
        QPushButton,
        "newPredictionNavigationButton",
    )
    settings = _required_child(window, QPushButton, "settingsNavigationButton")
    qtbot.keyClick(toggle, Qt.Key.Key_Space)
    assert window.sidebar_compact

    navigation.setFocus()
    qtbot.keyClick(navigation, Qt.Key.Key_Down)
    assert window.current_screen_name == "Predictions"
    qtbot.keyClick(navigation, Qt.Key.Key_Down)
    assert window.current_screen_name == "Analytics"

    new_prediction.setFocus()
    qtbot.keyClick(new_prediction, Qt.Key.Key_Space)
    assert window.current_screen_name == "New Prediction"

    settings.setFocus()
    qtbot.keyClick(settings, Qt.Key.Key_Space)
    assert window.current_screen_name == "Settings"


def test_global_shortcuts_are_documented_and_reach_only_navigation_actions(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    expected = {
        "globalShortcutNewPrediction": "Ctrl+N",
        "globalShortcutFindPredictions": "Ctrl+F",
        "globalShortcutDashboard": "Ctrl+1",
        "globalShortcutPredictions": "Ctrl+2",
        "globalShortcutAnalytics": "Ctrl+3",
        "globalShortcutSettings": "Ctrl+,",
        "globalShortcutToggleSidebar": "Ctrl+B",
        "globalShortcutReturnFromDetail": "Alt+Left",
    }
    shortcuts: dict[str, QShortcut] = {}
    for object_name, key in expected.items():
        shortcut = window.findChild(QShortcut, object_name)
        assert shortcut is not None
        assert shortcut.key().toString() == key
        shortcuts[object_name] = shortcut

    navigation.setFocus()
    shortcuts["globalShortcutNewPrediction"].activated.emit()
    assert window.current_screen_name == "New Prediction"
    question = _required_child(window, QLineEdit, "questionInput")
    qtbot.waitUntil(question.hasFocus)

    navigation.setFocus()
    shortcuts["globalShortcutFindPredictions"].activated.emit()
    assert window.current_screen_name == "Predictions"
    assert _required_child(window, QLineEdit, "predictionSearchInput").hasFocus()

    for object_name, screen_name in (
        ("globalShortcutDashboard", "Dashboard"),
        ("globalShortcutPredictions", "Predictions"),
        ("globalShortcutAnalytics", "Analytics"),
        ("globalShortcutSettings", "Settings"),
    ):
        navigation.setFocus()
        shortcuts[object_name].activated.emit()
        assert window.current_screen_name == screen_name

    navigation.setFocus()
    compact_before = window.sidebar_compact
    shortcuts["globalShortcutToggleSidebar"].activated.emit()
    assert window.sidebar_compact is not compact_before

    window.navigate_to("Analytics")
    window.navigate_to("Prediction Detail")
    navigation.setFocus()
    shortcuts["globalShortcutReturnFromDetail"].activated.emit()
    assert window.current_screen_name == "Analytics"

    shortcuts_panel = _required_child(window, ContentPanel, "keyboardShortcutsPanel")
    documented_keys = {label.text() for label in shortcuts_panel.findChildren(QLabel)}
    assert set(expected.values()) <= documented_keys


def test_global_shortcuts_pause_for_editing_and_modal_dialogs(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    prediction_shortcut = window.findChild(
        QShortcut,
        "globalShortcutPredictions",
    )
    analytics_shortcut = window.findChild(QShortcut, "globalShortcutAnalytics")
    toggle_shortcut = window.findChild(QShortcut, "globalShortcutToggleSidebar")
    assert prediction_shortcut is not None
    assert analytics_shortcut is not None
    assert toggle_shortcut is not None

    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    qtbot.mouseClick(question, Qt.MouseButton.LeftButton)
    assert question.hasFocus()
    compact_before = window.sidebar_compact
    prediction_shortcut.activated.emit()
    toggle_shortcut.activated.emit()
    assert window.current_screen_name == "New Prediction"
    assert window.sidebar_compact is compact_before

    window.navigate_to("Dashboard")
    dialog = QDialog(window)
    dialog.setModal(True)
    modal_button = QPushButton("Keep dialog open", dialog)
    dialog.show()
    modal_button.setFocus()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is dialog)

    analytics_shortcut.activated.emit()

    assert window.current_screen_name == "Dashboard"
    dialog.close()


def test_predictions_navigation_does_not_focus_the_archive_search(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    search_input = _required_child(window, QLineEdit, "predictionSearchInput")
    window.show()

    prediction_item = navigation.item(1)
    qtbot.mouseClick(
        navigation.viewport(),
        Qt.MouseButton.LeftButton,
        pos=navigation.visualItemRect(prediction_item).center(),
    )

    assert window.current_screen_name == "Predictions"
    assert not search_input.hasFocus()


def test_main_window_applies_foundational_semantic_roles(window: MainWindow) -> None:
    title = _required_child(window, QLabel, "newPredictionScreenTitle")
    create = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")
    delete = _required_child(window, QPushButton, "deletePredictionButton")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert create.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert create.accessibleName() == "Create prediction"
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert error.accessibleName() == "Prediction form error"
    assert delete.property(ACTION_ROLE_PROPERTY) == ActionRole.DESTRUCTIVE.value


def test_palette_change_refreshes_semantic_colors_and_navigation_icons(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    notification = _required_child(window, NotificationHost, "notificationHost")
    notification.show_message("Palette-safe acknowledgment.")
    light = QPalette(window.palette())
    dark = QPalette(window.palette())
    for palette, background, base, text, mid in (
        (light, "#f4f5f4", "#ffffff", "#1c211f", "#c7ceca"),
        (dark, "#171a18", "#202421", "#edf3ef", "#505852"),
    ):
        for role, value in (
            (QPalette.ColorRole.Window, background),
            (QPalette.ColorRole.Base, base),
            (QPalette.ColorRole.AlternateBase, background),
            (QPalette.ColorRole.WindowText, text),
            (QPalette.ColorRole.Text, text),
            (QPalette.ColorRole.ButtonText, text),
            (QPalette.ColorRole.HighlightedText, text),
            (QPalette.ColorRole.PlaceholderText, text),
            (QPalette.ColorRole.Mid, mid),
        ):
            palette.setColor(role, QColor(value))

    window.setPalette(light)
    light_colors = semantic_colors(light)
    qtbot.waitUntil(lambda: light_colors.accent in window.styleSheet())
    light_icon_key = navigation.item(0).icon().cacheKey()

    window.setPalette(dark)
    dark_colors = semantic_colors(dark)
    qtbot.waitUntil(lambda: dark_colors.accent in window.styleSheet())
    dark_icon_key = navigation.item(0).icon().cacheKey()

    assert light_colors.is_dark is False
    assert dark_colors.is_dark is True
    assert light_colors.accent != dark_colors.accent
    assert light_icon_key != dark_icon_key
    assert notification.current_message == "Palette-safe acknowledgment."
    assert not notification.isHidden()


def test_high_value_actions_keep_text_icons_and_accessible_names(
    window: MainWindow,
) -> None:
    expected_actions = {
        "createPredictionButton": "Create Prediction",
        "editPredictionDetailsButton": "Edit Details",
        "reviseForecastButton": "Revise Forecast",
        "addJournalEntryButton": "Add Journal Entry",
        "resolvePredictionButton": "Resolve",
        "markInvalidButton": "Mark Invalid",
        "deletePredictionButton": "Delete",
        "applyPredictionFiltersButton": "Apply filters",
        "clearPredictionFiltersButton": "Clear filters",
        "openSelectedPredictionButton": "Open selected",
        "refreshAnalyticsButton": "Refresh",
        "saveStaleThresholdButton": "Save threshold",
        "backUpNowButton": "Back Up Now",
        "exportCsvBundleButton": "Export CSV Bundle",
        "repairSearchIndexButton": "Repair Search Index",
    }

    for object_name, text in expected_actions.items():
        button = _required_child(window, QPushButton, object_name)
        assert button.text() == text
        assert not button.icon().isNull()
        assert button.accessibleName()


def test_main_window_navigates_to_each_primary_screen(window: MainWindow) -> None:
    screen_stack = _required_child(window, QStackedWidget, "screenStack")

    for expected_index, screen_name in enumerate(EXPECTED_SCREEN_NAMES):
        window.navigate_to(screen_name)

        assert window.current_screen_name == screen_name
        assert screen_stack.currentIndex() == expected_index


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


def test_contextual_detail_returns_to_dashboard_without_a_fake_destination(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(7, "Return this to Dashboard", 55)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    navigation = _required_child(window, QListWidget, "primaryNavigation")
    dashboard_calls = operations.dashboard_calls

    qtbot.mouseClick(
        _required_child(window, QPushButton, "dashboardOpenPrediction7"),
        Qt.MouseButton.LeftButton,
    )

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Dashboard"
    assert navigation.currentRow() == 0
    assert all(
        navigation.item(index).data(Qt.ItemDataRole.UserRole) != "Prediction Detail"
        for index in range(navigation.count())
    )

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Dashboard"
    assert operations.dashboard_calls == dashboard_calls


def test_contextual_detail_preserves_prediction_search_state_without_refresh(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(30, "Archive context item 30", 64)
    operations = FakePredictionOperations(latest)
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=tuple(
            PredictionBrowserItem(
                prediction_id=index,
                question=f"Archive context item {index}",
                probability_percent=64,
                status=PredictionStatus.OPEN,
                created_at=datetime(2026, 8, 20, 19, index, tzinfo=UTC),
                latest_revision_at=datetime(2026, 8, 20, 19, index, tzinfo=UTC),
                forecast_contract=prospective_contract(
                    PredictionType.BINARY,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            )
            for index in range(1, 31)
        ),
        available_tags=(),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    status = _required_child(window, QComboBox, "predictionStatusFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    search.setText("archive context")
    status.setCurrentIndex(status.findData(PredictionStatus.OPEN.value))
    _required_child(window, QPushButton, "applyPredictionFiltersButton").click()
    assert results.count() == 30
    results.setCurrentRow(29)
    results.verticalScrollBar().setValue(results.verticalScrollBar().maximum())
    scroll_position = results.verticalScrollBar().value()
    assert scroll_position > 0
    search_call_count = len(operations.search_calls)
    browser_call_count = len(operations.browser_calls)

    results.itemActivated.emit(results.item(29))

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Predictions"
    assert _required_child(window, QListWidget, "primaryNavigation").currentRow() == 1

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Predictions"
    assert search.text() == "archive context"
    assert status.currentData() == PredictionStatus.OPEN.value
    assert results.count() == 30
    assert results.currentRow() == 29
    assert results.verticalScrollBar().value() == scroll_position
    assert len(operations.search_calls) == search_call_count
    assert len(operations.browser_calls) == browser_call_count


def test_created_prediction_detail_returns_to_last_primary_destination(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(12, "Return creation to Analytics", 50)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Analytics")
    window.navigate_to("New Prediction")

    window._new_prediction_screen.prediction_created.emit(latest)

    back = _required_child(window, QPushButton, "backFromPredictionDetailButton")
    assert window.current_screen_name == "Prediction Detail"
    assert back.text() == "Back to Analytics"
    assert _required_child(window, QListWidget, "primaryNavigation").currentRow() == 2

    qtbot.mouseClick(back, Qt.MouseButton.LeftButton)

    assert window.current_screen_name == "Analytics"


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()
