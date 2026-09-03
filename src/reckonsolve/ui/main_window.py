"""The primary Reckonsolve application window."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QRect, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.search import SearchDocument
from reckonsolve.ui.analytics_screen import AnalyticsScreen
from reckonsolve.ui.dashboard import AttentionSettingsScreen, DashboardScreen
from reckonsolve.ui.icons import (
    LucideIcon,
    apply_lucide_icon,
    is_palette_change,
    lucide_icon,
    refresh_lucide_icons,
)
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.prediction_browser import PredictionBrowserScreen
from reckonsolve.ui.presentation_settings import (
    MINIMUM_WINDOW_SIZE,
    MemoryPresentationSettings,
    PresentationSettings,
    WindowPresentationState,
    safe_window_geometry,
)
from reckonsolve.ui.screens import (
    NewPredictionScreen,
    NumericPredictionDetailScreen,
    NumericPredictionSnapshot,
    PredictionDetailHost,
    PredictionDetailScreen,
    PredictionOperations,
    PredictionSnapshot,
)
from reckonsolve.ui.visual_system import (
    NAVIGATION_COMPACT_PROPERTY,
    ActionRole,
    Spacing,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_navigation_active,
    apply_navigation_compact,
    apply_surface_role,
    apply_text_role,
    install_visual_system,
    is_visual_system_change,
    refresh_visual_system,
)

_ROUTE_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)
_PRIMARY_DESTINATIONS = (
    "Dashboard",
    "Predictions",
    "Analytics",
)
_PRIMARY_ICONS = {
    "Dashboard": LucideIcon.LAYOUT_DASHBOARD,
    "Predictions": LucideIcon.LIST_FILTER,
    "Analytics": LucideIcon.CHART,
}
_EXPANDED_SIDEBAR_WIDTH = 240
_COMPACT_SIDEBAR_WIDTH = 68
_COMPACT_NAVIGATION_ROW_HEIGHT = 40
_COMPACT_NAVIGATION_SPACING = 1


class _PrimaryNavigationItemDelegate(QStyledItemDelegate):
    """Center icon-only navigation without changing expanded item layout."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        widget = option.widget
        if widget is None or not bool(widget.property(NAVIGATION_COMPACT_PROPERTY)):
            super().paint(painter, option, index)
            return

        compact_option = QStyleOptionViewItem(option)
        self.initStyleOption(compact_option, index)
        icon = QIcon(compact_option.icon)
        compact_option.icon = QIcon()
        compact_option.text = ""
        compact_option.features &= ~(
            QStyleOptionViewItem.ViewItemFeature.HasDecoration
            | QStyleOptionViewItem.ViewItemFeature.HasDisplay
        )
        widget.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            compact_option,
            painter,
            widget,
        )

        if icon.isNull():
            return
        mode = QIcon.Mode.Normal
        if not compact_option.state & QStyle.StateFlag.State_Enabled:
            mode = QIcon.Mode.Disabled
        elif compact_option.state & QStyle.StateFlag.State_Selected:
            mode = QIcon.Mode.Selected
        elif compact_option.state & QStyle.StateFlag.State_MouseOver:
            mode = QIcon.Mode.Active
        icon.paint(
            painter,
            _centered_icon_rect(compact_option.rect, self._navigation_icon_size()),
            Qt.AlignmentFlag.AlignCenter,
            mode,
            QIcon.State.Off,
        )

    def _navigation_icon_size(self) -> QSize:
        navigation = self.parent()
        if isinstance(navigation, QListWidget):
            return navigation.iconSize()
        return QSize(20, 20)


def _centered_icon_rect(item_rect: QRect, icon_size: QSize) -> QRect:
    width = min(max(1, icon_size.width()), item_rect.width())
    height = min(max(1, icon_size.height()), item_rect.height())
    icon_rect = QRect(0, 0, width, height)
    icon_rect.moveCenter(item_rect.center())
    return icon_rect


class MainWindow(QMainWindow):
    """Display the responsive navigation shell for the desktop application."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
        *,
        window_title: str = "Reckonsolve",
        presentation_settings: PresentationSettings | None = None,
        available_screens: tuple[QRect, ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle(window_title)
        self.setMinimumSize(MINIMUM_WINDOW_SIZE)
        self._refreshing_visual_system = False
        self._presentation_settings = (
            presentation_settings or MemoryPresentationSettings()
        )
        self._available_screens_override = available_screens
        self._presentation_state = self._presentation_settings.load()
        self._sidebar_compact = self._presentation_state.sidebar_compact
        self._last_primary_screen = "Dashboard"
        self._detail_return_screen: str | None = None
        self._detail_origin_focus: QWidget | None = None
        self._current_route_name = "Dashboard"

        self._screen_stack = QStackedWidget(self)
        self._screen_stack.setObjectName("screenStack")

        self._new_prediction_screen = NewPredictionScreen(operations)
        self._prediction_detail_screen = PredictionDetailScreen(operations)
        self._numeric_prediction_detail_screen = NumericPredictionDetailScreen(
            operations
        )
        self._prediction_detail_host = PredictionDetailHost(
            operations,
            self._prediction_detail_screen,
            self._numeric_prediction_detail_screen,
        )
        self._dashboard_screen = DashboardScreen(operations)
        self._prediction_browser_screen = PredictionBrowserScreen(operations)
        self._analytics_screen = AnalyticsScreen(operations)
        self._settings_screen = AttentionSettingsScreen(operations)

        self._back_from_detail_button = QPushButton("Back to Predictions", self)
        self._back_from_detail_button.setObjectName("backFromPredictionDetailButton")
        self._back_from_detail_button.setAccessibleName(
            "Return from Prediction Detail to Predictions"
        )
        apply_action_role(self._back_from_detail_button, ActionRole.QUIET)
        apply_lucide_icon(self._back_from_detail_button, LucideIcon.ARROW_LEFT)

        detail_container = QWidget(self)
        detail_container.setObjectName("contextualPredictionDetail")
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(int(Spacing.CONTROL))
        detail_layout.addWidget(
            self._back_from_detail_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        detail_layout.addWidget(self._prediction_detail_host, 1)

        screens = {
            "Dashboard": self._dashboard_screen,
            "New Prediction": self._new_prediction_screen,
            "Prediction Detail": detail_container,
            "Predictions": self._prediction_browser_screen,
            "Analytics": self._analytics_screen,
            "Settings": self._settings_screen,
        }
        self._screen_indexes: dict[str, int] = {}
        for route_name in _ROUTE_NAMES:
            self._screen_indexes[route_name] = self._screen_stack.addWidget(
                screens[route_name]
            )

        self._sidebar = QFrame(self)
        self._sidebar.setObjectName("applicationSidebar")
        apply_surface_role(self._sidebar, SurfaceRole.BASE)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(
            int(Spacing.CONTROL),
            int(Spacing.CONTROL),
            int(Spacing.CONTROL),
            int(Spacing.CONTROL),
        )
        sidebar_layout.setSpacing(int(Spacing.CONTROL))

        identity_row = QWidget(self._sidebar)
        identity_row.setObjectName("sidebarIdentityRow")
        identity_layout = QHBoxLayout(identity_row)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(int(Spacing.COMPACT))
        self._sidebar_identity = QLabel(window_title, identity_row)
        self._sidebar_identity.setObjectName("sidebarIdentity")
        self._sidebar_identity.setAccessibleName(window_title)
        self._sidebar_identity.setToolTip(window_title)
        apply_text_role(self._sidebar_identity, TextRole.SECTION_TITLE)
        self._sidebar_toggle = QPushButton("", identity_row)
        self._sidebar_toggle.setObjectName("sidebarModeToggle")
        apply_action_role(
            self._sidebar_toggle,
            ActionRole.QUIET,
            accessible_name="Collapse sidebar",
        )
        identity_layout.addWidget(self._sidebar_identity)
        identity_layout.addStretch()
        identity_layout.addWidget(self._sidebar_toggle)

        self._new_prediction_button = QPushButton("New Prediction", self._sidebar)
        self._new_prediction_button.setObjectName("newPredictionNavigationButton")
        self._new_prediction_button.setAccessibleName("New Prediction")
        self._new_prediction_button.setToolTip("Create a new prediction")
        apply_action_role(self._new_prediction_button, ActionRole.PRIMARY)
        apply_lucide_icon(self._new_prediction_button, LucideIcon.CIRCLE_PLUS)

        self._navigation = QListWidget(self._sidebar)
        self._navigation.setObjectName("primaryNavigation")
        self._navigation.setAccessibleName("Primary navigation")
        self._navigation.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._navigation.setIconSize(QSize(20, 20))
        self._navigation.setItemDelegate(
            _PrimaryNavigationItemDelegate(self._navigation)
        )
        self._navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._navigation.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._navigation.setSpacing(int(Spacing.COMPACT))
        self._expanded_navigation_row_height = max(
            44,
            self.fontMetrics().height() + 20,
        )
        for screen_name in _PRIMARY_DESTINATIONS:
            item = QListWidgetItem(screen_name)
            item.setData(Qt.ItemDataRole.UserRole, screen_name)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, screen_name)
            item.setToolTip(screen_name)
            item.setSizeHint(QSize(0, self._expanded_navigation_row_height))
            item.setIcon(lucide_icon(_PRIMARY_ICONS[screen_name], self.palette()))
            self._navigation.addItem(item)
        self._navigation.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._settings_button = QPushButton("Settings", self._sidebar)
        self._settings_button.setObjectName("settingsNavigationButton")
        self._settings_button.setAccessibleName("Settings")
        self._settings_button.setToolTip("Settings")
        apply_action_role(self._settings_button, ActionRole.QUIET)
        apply_lucide_icon(self._settings_button, LucideIcon.SETTINGS)

        sidebar_layout.addWidget(identity_row)
        sidebar_layout.addWidget(self._new_prediction_button)
        sidebar_layout.addWidget(self._navigation)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self._settings_button)

        content = QWidget(self)
        content.setObjectName("mainContent")
        layout = QHBoxLayout(content)
        layout.setContentsMargins(
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
        )
        layout.setSpacing(int(Spacing.ORDINARY))
        layout.addWidget(self._sidebar)
        layout.addWidget(self._screen_stack, 1)
        self.setCentralWidget(content)
        self._notification_host = NotificationHost(content)

        install_visual_system(self)
        self._fit_primary_navigation_height()
        self._set_sidebar_mode(self._sidebar_compact, persist=False)
        self._refresh_navigation_icons()
        refresh_lucide_icons(self)
        self._restore_window_state()

        self._navigation.currentRowChanged.connect(self._primary_navigation_changed)
        self._navigation.itemClicked.connect(self._primary_navigation_activated)
        self._navigation.itemActivated.connect(self._primary_navigation_activated)
        self._new_prediction_button.clicked.connect(
            lambda: self.navigate_to("New Prediction")
        )
        self._settings_button.clicked.connect(lambda: self.navigate_to("Settings"))
        self._sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self._back_from_detail_button.clicked.connect(self.return_from_detail)
        self._new_prediction_screen.prediction_created.connect(
            self._show_created_prediction
        )
        self._dashboard_screen.prediction_selected.connect(
            self._show_selected_prediction
        )
        self._prediction_browser_screen.prediction_selected.connect(
            self._show_selected_prediction
        )
        self._prediction_browser_screen.search_result_selected.connect(
            self._show_search_result
        )
        self._settings_screen.threshold_changed.connect(
            lambda _value: self._dashboard_screen.refresh()
        )
        self._dashboard_screen.routine_notification_requested.connect(
            self._show_routine_notification
        )
        self._settings_screen.routine_notification_requested.connect(
            self._show_routine_notification
        )
        self._activate_route("Dashboard", refresh=True, focus=False)

    def changeEvent(self, event: QEvent) -> None:
        """Refresh semantic styling and icons after native theme changes."""

        super().changeEvent(event)
        if (
            is_visual_system_change(event)
            and hasattr(self, "_screen_stack")
            and not self._refreshing_visual_system
        ):
            self._refreshing_visual_system = True
            try:
                refresh_visual_system(self)
                self._fit_primary_navigation_height()
            finally:
                self._refreshing_visual_system = False
        if is_palette_change(event) and hasattr(self, "_navigation"):
            self._refresh_navigation_icons()
            refresh_lucide_icons(self)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Persist disposable shell state without touching canonical data."""

        self._save_presentation_state()
        super().closeEvent(event)

    @property
    def screen_names(self) -> tuple[str, ...]:
        """Return every named screen route, including contextual Detail."""

        return _ROUTE_NAMES

    @property
    def navigation_names(self) -> tuple[str, ...]:
        """Return the three permanent primary destinations."""

        return _PRIMARY_DESTINATIONS

    @property
    def current_screen_name(self) -> str:
        """Return the route currently displayed in the content stack."""

        return self._current_route_name

    @property
    def sidebar_compact(self) -> bool:
        return self._sidebar_compact

    def navigate_to(self, screen_name: str) -> None:
        """Navigate to a named screen while preserving contextual semantics."""

        if screen_name not in self.screen_names:
            message = f"Unknown Reckonsolve screen: {screen_name!r}"
            raise ValueError(message)
        if screen_name == "Prediction Detail":
            if self.current_screen_name != "Prediction Detail":
                self._capture_detail_origin()
            self._activate_route(screen_name, refresh=True, focus=False)
            return
        self._activate_route(screen_name, refresh=True, focus=True)

    def toggle_sidebar(self) -> None:
        self._set_sidebar_mode(not self._sidebar_compact, persist=True)

    def return_from_detail(self) -> None:
        """Return to Detail's source without rebuilding an archive query."""

        if self.current_screen_name != "Prediction Detail":
            return
        destination = self._detail_return_screen or "Predictions"
        origin_focus = self._detail_origin_focus
        self._activate_route(destination, refresh=False, focus=False)
        self._detail_return_screen = None
        self._detail_origin_focus = None
        if origin_focus is not None:
            try:
                if origin_focus.isVisible():
                    origin_focus.setFocus(Qt.FocusReason.BacktabFocusReason)
                    return
            except RuntimeError:
                pass
        if destination == "Predictions":
            self._prediction_browser_screen.focus_search()
        elif destination == "Dashboard":
            self._navigation.setFocus(Qt.FocusReason.BacktabFocusReason)

    def _primary_navigation_changed(self, row: int) -> None:
        if row < 0:
            return
        screen_name = str(self._navigation.item(row).data(Qt.ItemDataRole.UserRole))
        if self.current_screen_name != screen_name:
            self._activate_route(screen_name, refresh=True, focus=True)

    def _primary_navigation_activated(self, item: QListWidgetItem) -> None:
        screen_name = str(item.data(Qt.ItemDataRole.UserRole))
        if self.current_screen_name != screen_name:
            self._activate_route(screen_name, refresh=True, focus=True)

    def _activate_route(
        self,
        screen_name: str,
        *,
        refresh: bool,
        focus: bool,
    ) -> None:
        if screen_name in _PRIMARY_DESTINATIONS:
            self._last_primary_screen = screen_name
        self._current_route_name = screen_name
        self._screen_stack.setCurrentIndex(self._screen_indexes[screen_name])
        self._sync_navigation_state()
        if screen_name == "Dashboard":
            if refresh:
                self._dashboard_screen.refresh()
        elif screen_name == "New Prediction":
            if focus:
                self._new_prediction_screen.focus_question()
        elif screen_name == "Prediction Detail":
            if refresh:
                self._prediction_detail_host.refresh()
        elif screen_name == "Predictions":
            if refresh:
                self._prediction_browser_screen.refresh()
            if focus:
                self._prediction_browser_screen.focus_search()
        elif screen_name == "Analytics":
            if refresh:
                self._analytics_screen.refresh()
        elif screen_name == "Settings" and refresh:
            self._settings_screen.refresh()

    def _capture_detail_origin(self) -> None:
        current = self.current_screen_name
        if current in _PRIMARY_DESTINATIONS:
            self._detail_return_screen = current
        elif current == "New Prediction":
            self._detail_return_screen = self._last_primary_screen
        else:
            self._detail_return_screen = "Predictions"
        focused = QApplication.focusWidget()
        self._detail_origin_focus = focused if isinstance(focused, QWidget) else None
        self._update_back_button()

    def _show_created_prediction(
        self,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
    ) -> None:
        self._capture_detail_origin()
        if hasattr(prediction, "decimal_places"):
            self._prediction_detail_host.show_numeric_prediction(prediction)
        else:
            self._prediction_detail_host.show_prediction(prediction)
        self._activate_route("Prediction Detail", refresh=False, focus=False)

    def _show_selected_prediction(
        self,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
    ) -> None:
        self._capture_detail_origin()
        if hasattr(prediction, "decimal_places"):
            self._prediction_detail_host.show_numeric_prediction(prediction)
        else:
            self._prediction_detail_host.show_prediction(prediction)
        self._activate_route("Prediction Detail", refresh=False, focus=False)

    def _show_search_result(
        self,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
        search_document: SearchDocument,
    ) -> None:
        """Open current Detail, then reveal the canonical source that matched."""

        self._show_selected_prediction(prediction)
        self._prediction_detail_host.focus_search_match(search_document)

    def _show_routine_notification(self, message: str) -> None:
        """Keep acknowledgment rendering outside committed application work."""

        try:
            self._notification_host.show_message(message)
        except (RuntimeError, TypeError, ValueError):
            # The operation has already completed and refreshed its canonical view.
            # A disposable presentation failure must not turn that into false failure.
            return

    def _sync_navigation_state(self) -> None:
        route = self.current_screen_name
        primary_active = route if route in _PRIMARY_DESTINATIONS else None
        if route == "Prediction Detail" and self._detail_return_screen in (
            _PRIMARY_DESTINATIONS
        ):
            primary_active = self._detail_return_screen
        with QSignalBlocker(self._navigation):
            if primary_active is None:
                self._navigation.setCurrentRow(-1)
                self._navigation.clearSelection()
            else:
                self._navigation.setCurrentRow(
                    _PRIMARY_DESTINATIONS.index(primary_active)
                )
        apply_navigation_active(
            self._new_prediction_button,
            route == "New Prediction",
        )
        apply_navigation_active(
            self._settings_button,
            route == "Settings",
        )

    def _update_back_button(self) -> None:
        destination = self._detail_return_screen or "Predictions"
        self._back_from_detail_button.setText(f"Back to {destination}")
        self._back_from_detail_button.setAccessibleName(
            f"Return from Prediction Detail to {destination}"
        )

    def _set_sidebar_mode(self, compact: bool, *, persist: bool) -> None:
        self._sidebar_compact = compact
        self._sidebar.setFixedWidth(
            _COMPACT_SIDEBAR_WIDTH if compact else _EXPANDED_SIDEBAR_WIDTH
        )
        self._sidebar_identity.setVisible(not compact)
        self._sidebar_identity.setText(self.windowTitle())
        self._new_prediction_button.setText("" if compact else "New Prediction")
        self._settings_button.setText("" if compact else "Settings")
        self._navigation.setSpacing(
            _COMPACT_NAVIGATION_SPACING if compact else int(Spacing.COMPACT)
        )
        apply_navigation_compact(self._navigation, compact)
        for row, screen_name in enumerate(_PRIMARY_DESTINATIONS):
            item = self._navigation.item(row)
            item.setText("" if compact else screen_name)
            item.setSizeHint(
                QSize(
                    0,
                    _COMPACT_NAVIGATION_ROW_HEIGHT
                    if compact
                    else self._expanded_navigation_row_height,
                )
            )
        self._fit_primary_navigation_height()

        if compact:
            toggle_name = "Expand sidebar"
            toggle_icon = LucideIcon.ARROW_RIGHT
        else:
            toggle_name = "Collapse sidebar"
            toggle_icon = LucideIcon.ARROW_LEFT
        self._sidebar_toggle.setAccessibleName(toggle_name)
        self._sidebar_toggle.setToolTip(toggle_name)
        apply_lucide_icon(self._sidebar_toggle, toggle_icon)
        refresh_lucide_icons(self._sidebar)
        if persist:
            self._save_presentation_state()

    def _restore_window_state(self) -> None:
        geometry = safe_window_geometry(
            self._presentation_state.normal_geometry,
            self._available_screen_geometries(),
        )
        self.setGeometry(geometry)
        state = self.windowState() & ~Qt.WindowState.WindowMinimized
        if self._presentation_state.maximized:
            state |= Qt.WindowState.WindowMaximized
        else:
            state &= ~Qt.WindowState.WindowMaximized
        self.setWindowState(state)

    def _save_presentation_state(self) -> None:
        maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)
        minimized = bool(self.windowState() & Qt.WindowState.WindowMinimized)
        normal = self.normalGeometry() if maximized or minimized else self.geometry()
        if not normal.isValid():
            normal = self.geometry()
        state = WindowPresentationState(
            sidebar_compact=self._sidebar_compact,
            normal_geometry=(normal.x(), normal.y(), normal.width(), normal.height()),
            maximized=maximized,
        )
        if self._presentation_settings.save(state):
            self._presentation_state = state

    def _available_screen_geometries(self) -> tuple[QRect, ...]:
        if self._available_screens_override is not None:
            return self._available_screens_override
        application = QApplication.instance()
        if not isinstance(application, QApplication):
            return ()
        primary = application.primaryScreen()
        ordered = [] if primary is None else [primary.availableGeometry()]
        for screen in application.screens():
            geometry = screen.availableGeometry()
            if geometry not in ordered:
                ordered.append(geometry)
        return tuple(ordered)

    def _refresh_navigation_icons(self) -> None:
        for row, screen_name in enumerate(_PRIMARY_DESTINATIONS):
            self._navigation.item(row).setIcon(
                lucide_icon(_PRIMARY_ICONS[screen_name], self.palette())
            )

    def _fit_primary_navigation_height(self) -> None:
        """Expose every fixed primary destination without an internal scroll."""

        row_heights = tuple(
            self._navigation.sizeHintForRow(row)
            for row in range(self._navigation.count())
        )
        content_height = sum(max(1, height) for height in row_heights)
        # QListView lays its configured spacing around each item, so every row
        # contributes a leading and trailing spacing interval.
        spacing_height = self._navigation.spacing() * self._navigation.count() * 2
        frame_height = self._navigation.frameWidth() * 2
        self._navigation.setFixedHeight(
            content_height + spacing_height + frame_height + 2
        )
        self._navigation.verticalScrollBar().setValue(0)


__all__ = ["MainWindow"]
