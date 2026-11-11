"""Compose the Journal workspace; canonical work stays in application operations."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError, PredictionNotFoundError
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.domain.one_shot import OneShotDetail
from reckonsolve.ui.analytics_screen import AnalyticsScreen
from reckonsolve.ui.appearance import AppearanceController
from reckonsolve.ui.creation_task import CreationTask
from reckonsolve.ui.icons import refresh_lucide_icons
from reckonsolve.ui.journal.screen import JournalScreen
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.one_shot import OneShotCreationScreen
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
    PredictionDetailHost,
    PredictionDetailScreen,
)
from reckonsolve.ui.settings_screen import SettingsScreen
from reckonsolve.ui.visual_system import (
    install_visual_system,
    is_visual_system_change,
    refresh_visual_system,
)
from reckonsolve.ui.workspace_state import Destination, Route, WorkspaceState
from reckonsolve.ui.workspace_toolbar import WorkspaceToolbar


class MainWindow(QMainWindow):
    """Keep a single source for each task, with current-state-checked returns."""

    def __init__(
        self,
        operations,
        parent=None,
        *,
        window_title="Reckonsolve",
        presentation_settings: PresentationSettings | None = None,
        available_screens: tuple[QRect, ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle(window_title)
        self.setMinimumSize(MINIMUM_WINDOW_SIZE)
        self.operations = operations
        self.workspace = WorkspaceState()
        self.archive_blocked = False
        self._refreshing_visual_system = False
        self._presentation_settings = (
            presentation_settings or MemoryPresentationSettings()
        )
        self._presentation_state = self._presentation_settings.load()
        self._available_screens_override = available_screens
        self.appearance = AppearanceController(
            self._presentation_state.appearance, self
        )
        self._toolbar = WorkspaceToolbar(window_title, self)
        self._screen_stack = QStackedWidget(self)
        self._screen_stack.setObjectName("screenStack")
        self._journal_screen = JournalScreen(
            operations.journal.query_independently, self
        )
        self._new_prediction_screen = NewPredictionScreen(operations)
        self._one_shot_creation_screen = OneShotCreationScreen(operations)
        self._creation_stack = QStackedWidget(self)
        self._creation_stack.addWidget(self._new_prediction_screen)
        self._creation_stack.addWidget(self._one_shot_creation_screen)
        self.creation_task = CreationTask(
            self,
            (self._new_prediction_screen, self._one_shot_creation_screen),
            (
                self._new_prediction_screen._reset_form,
                self._one_shot_creation_screen.reset,
            ),
            (
                self._new_prediction_screen.prediction_type_input,
                self._one_shot_creation_screen.form.type_input,
            ),
        )
        self._new_prediction_screen.save_guard = lambda: (
            self.creation_task.confirm_save(0)
        )
        self._one_shot_creation_screen.save_guard = lambda: (
            self.creation_task.confirm_save(1)
        )
        self._new_prediction_screen.one_shot_requested.connect(
            lambda: self._creation_stack.setCurrentIndex(1)
        )
        self._one_shot_creation_screen.cancelled.connect(
            lambda: self._creation_stack.setCurrentIndex(0)
        )
        for form in (self._new_prediction_screen, self._one_shot_creation_screen):
            form.prediction_created.connect(self._show_created_prediction)
        self._prediction_detail_screen = PredictionDetailScreen(operations)
        self._numeric_prediction_detail_screen = NumericPredictionDetailScreen(
            operations
        )
        for detail in (
            self._prediction_detail_screen,
            self._numeric_prediction_detail_screen,
        ):
            detail.skip_postmortem_button.completed.connect(
                self._show_routine_notification
            )
        self._prediction_detail_host = PredictionDetailHost(
            operations,
            self._prediction_detail_screen,
            self._numeric_prediction_detail_screen,
        )
        self._analytics_screen = AnalyticsScreen(operations)
        self._settings_screen = SettingsScreen(operations)
        self._screens = {
            Route.JOURNAL: self._journal_screen,
            Route.NEW: self._creation_stack,
            Route.DETAIL: self._prediction_detail_host,
            Route.PERFORMANCE: self._analytics_screen,
            Route.SETTINGS: self._settings_screen,
        }
        for screen in self._screens.values():
            self._screen_stack.addWidget(screen)
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._screen_stack, 1)
        self.setCentralWidget(content)
        self._notification_host = NotificationHost(content)
        self._toolbar.back_requested.connect(self.return_to_source)
        self._toolbar.journal_requested.connect(lambda: self.navigate_to("Journal"))
        self._toolbar.new_requested.connect(lambda: self.navigate_to("New Prediction"))
        self._toolbar.performance_requested.connect(
            lambda: self.navigate_to("Performance")
        )
        self._toolbar.settings_requested.connect(lambda: self.navigate_to("Settings"))
        self._toolbar.appearance_requested.connect(self.appearance.toggle)
        self.appearance.changed.connect(self._appearance_changed)
        self._settings_screen.appearance_changed.connect(self.appearance.select)
        self._settings_screen.routine_notification_requested.connect(
            self._show_routine_notification
        )
        self._journal_screen.prediction_selected.connect(self._open_prediction)
        self._journal_screen.repair_requested.connect(
            lambda: self.navigate_to("Settings")
        )
        self._journal_screen.archive_refused.connect(self._archive_refused)
        install_visual_system(self)
        self._restore_window_state()
        self._install_global_shortcuts()
        self._sync_toolbar()
        self._activate(Destination(), refresh=True)

    @property
    def screen_names(self) -> tuple[str, ...]:
        return tuple(route.value for route in Route)

    @property
    def navigation_names(self) -> tuple[str, ...]:
        return (Route.JOURNAL.value, Route.PERFORMANCE.value)

    @property
    def current_screen_name(self) -> str:
        return self.workspace.current.route.value

    def navigate_to(self, name: str) -> None:
        if self.archive_blocked:
            return
        # Old internal route callers are adapted; retired names are never visible.
        name = {
            "Dashboard": "Journal",
            "Predictions": "Journal",
            "Analytics": "Performance",
        }.get(name, name)
        route = Route(name)
        current = self.workspace.current.route
        if (
            current is Route.DETAIL
            and route is not Route.DETAIL
            and not self._prediction_detail_host.confirm_exit(
                "start New" if route is Route.NEW else "open " + route.value
            )
        ):
            return
        if current is Route.NEW:
            if route is Route.NEW:
                self._focus_creation()
                return
            if not self.creation_task.confirm_exit():
                return
            self.creation_task.reset()
        if route is Route.DETAIL:
            prediction = self.operations.get_latest_for_navigation()
            self._prediction_detail_host.refresh()
            self._activate(
                Destination(
                    route, prediction.prediction_id if prediction is not None else None
                ),
                refresh=False,
            )
            return
        if route is Route.NEW and current is Route.SETTINGS:
            return
        if route is Route.NEW:
            self._creation_stack.setCurrentIndex(0)
        self._activate(Destination(route), refresh=True)

    def _activate(
        self, destination: Destination, *, refresh: bool, remember_source: bool = True
    ) -> None:
        self.workspace.enter(destination, remember_source=remember_source)
        route = destination.route
        self._screen_stack.setCurrentWidget(self._screens[route])
        self._sync_toolbar()
        if route is Route.NEW:
            self._focus_creation()
        elif route is Route.JOURNAL and refresh:
            self._journal_screen.refresh()
        elif route is Route.PERFORMANCE and refresh:
            self._analytics_screen.refresh()
        elif route is Route.SETTINGS and refresh:
            self._settings_screen.refresh()

    def _focus_creation(self) -> None:
        if self._creation_stack.currentIndex() == 0:
            self._new_prediction_screen.focus_question()
        else:
            self._one_shot_creation_screen.question.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )

    def _sync_toolbar(self) -> None:
        route = self.workspace.current.route
        origin = self.workspace.back_destination()
        if route is Route.DETAIL:
            text = "Back to Journal"
        elif origin.route is Route.DETAIL:
            text = "Back to Prediction"
        else:
            text = f"Back to {origin.route.value}"
        self._toolbar.update_route(
            route,
            text,
            separate_home=route is Route.PERFORMANCE and origin.route is Route.DETAIL,
        )
        self._toolbar.update_appearance(self.appearance.dark)
        self._settings_screen.set_appearance(self.appearance.mode)

    def return_to_source(self) -> None:
        if self.archive_blocked:
            return
        route = self.workspace.current.route
        if route is Route.JOURNAL:
            return
        if route is Route.DETAIL and not self._prediction_detail_host.confirm_exit():
            return
        destination = self.workspace.back_destination()
        # Verify before asking for discard. A failed read is neither deletion
        # nor consent to discard work that the user must then keep editing.
        prediction = None
        return_notice = None
        if destination.route is Route.DETAIL:
            try:
                prediction = self.operations.get_prediction_for_navigation(
                    destination.prediction_id
                )
            except PredictionNotFoundError:
                destination = Destination()
                return_notice = (
                    "That Prediction is no longer available. Returned to Journal."
                )
            except (ForecastContractIntegrityError, MigrationError) as error:
                self._archive_refused(error)
                return
            except ApplicationError as error:
                self._show_routine_notification(f"Could not return yet. {error}")
                return
        if route is Route.NEW:
            if not self.creation_task.confirm_exit():
                return
            self.creation_task.reset()
        if prediction is not None:
            self._display_prediction(prediction)
        self._activate(destination, refresh=True, remember_source=False)
        if return_notice:
            self._show_routine_notification(return_notice)

    def return_from_detail(self) -> None:
        if self.workspace.current.route is Route.DETAIL:
            self.return_to_source()

    def _display_prediction(self, prediction) -> None:
        if isinstance(prediction, OneShotDetail) or not hasattr(
            prediction, "decimal_places"
        ):
            self._prediction_detail_host.show_prediction(prediction)
        else:
            self._prediction_detail_host.show_numeric_prediction(prediction)

    def _open_prediction(self, identifier: int, document=None) -> None:
        if self.archive_blocked:
            return
        try:
            prediction = self.operations.get_prediction_for_navigation(identifier)
            changed = False
            if document is not None:
                document, changed = self.operations.journal.resolve_passage(
                    identifier, document
                )
        except PredictionNotFoundError:
            self._journal_screen.refresh()
            self._show_routine_notification(
                "That Prediction is no longer available. Journal has been refreshed."
            )
            return
        except (ForecastContractIntegrityError, MigrationError) as error:
            self._archive_refused(error)
            return
        except ApplicationError as error:
            self._show_routine_notification(f"Could not open Prediction. {error}")
            return
        self._display_prediction(prediction)
        self._activate(Destination(Route.DETAIL, identifier), refresh=False)
        if document is not None:
            self._prediction_detail_host.focus_search_match(
                document, emphasize=not changed
            )
        if changed:
            self._show_routine_notification(
                "The matched passage changed after the search. Showing current text without the former match emphasis."
            )

    def _show_created_prediction(self, prediction) -> None:
        self.creation_task.reset()
        self._creation_stack.setCurrentIndex(0)
        if (
            isinstance(prediction, OneShotDetail)
            and prediction.record.effective.answer is not None
        ):
            self._display_prediction(prediction)
            self._activate(
                Destination(Route.DETAIL, prediction.prediction_id), refresh=False
            )
        else:
            self._activate(Destination(), refresh=True)
            self._show_routine_notification("Prediction created")

    def _install_global_shortcuts(self) -> None:
        self._global_shortcuts = {}
        for name, keys, action in (
            ("globalShortcutNewPrediction", "Ctrl+N", self._shortcut_new),
            ("globalShortcutFindPredictions", "Ctrl+F", self._shortcut_find),
            ("globalShortcutSettings", "Ctrl+,", self._shortcut_settings),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setObjectName(name)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(
                lambda selected=action: (
                    selected() if QApplication.activeModalWidget() is None else None
                )
            )
            self._global_shortcuts[name] = shortcut

    def _shortcut_new(self) -> None:
        if self.workspace.current.route is not Route.SETTINGS:
            self.navigate_to("New Prediction")

    def _shortcut_find(self) -> None:
        if self.workspace.current.route is Route.JOURNAL:
            self._journal_screen.focus_search()

    def _shortcut_settings(self) -> None:
        if self.workspace.current.route not in (Route.NEW, Route.SETTINGS):
            self.navigate_to("Settings")

    def _appearance_changed(self, _mode) -> None:
        self._sync_toolbar()
        if not self._save_presentation_state():
            self._show_routine_notification(
                "Appearance changed for this session, but the preference could not be remembered."
            )

    def _archive_refused(self, error: Exception) -> None:
        if self.archive_blocked:
            return
        self.archive_blocked = True
        self._journal_screen.block_archive(error)
        self._screen_stack.setEnabled(False)
        self._toolbar.new.setEnabled(False)
        self._toolbar.performance.setEnabled(False)
        self._toolbar.settings.setEnabled(False)
        QMessageBox.critical(self, "Journal cannot be opened", str(error))

    def _show_routine_notification(self, message: str) -> None:
        try:
            self._notification_host.show_message(message)
        except (RuntimeError, TypeError, ValueError):
            # A presentation failure cannot undo a committed canonical operation.
            return

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if (
            is_visual_system_change(event)
            and hasattr(self, "_screen_stack")
            and not self._refreshing_visual_system
        ):
            self._refreshing_visual_system = True
            try:
                refresh_visual_system(self, palette=QApplication.palette())
                refresh_lucide_icons(self)
            finally:
                self._refreshing_visual_system = False

    def closeEvent(self, event: QCloseEvent) -> None:
        if (
            self.workspace.current.route is Route.DETAIL
            and not self._prediction_detail_host.confirm_exit("close Reckonsolve")
        ):
            event.ignore()
            return
        if self.workspace.current.route is Route.NEW:
            if not self.creation_task.confirm_exit():
                event.ignore()
                return
            self.creation_task.reset()
        self._journal_screen.close_retrieval()
        self.appearance.close()
        self._save_presentation_state()
        super().closeEvent(event)

    def _restore_window_state(self) -> None:
        self.setGeometry(
            safe_window_geometry(
                self._presentation_state.normal_geometry,
                self._available_screen_geometries(),
            )
        )
        if self._presentation_state.maximized:
            self.setWindowState(Qt.WindowState.WindowMaximized)

    def _save_presentation_state(self) -> bool:
        maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)
        minimized = bool(self.windowState() & Qt.WindowState.WindowMinimized)
        normal = self.normalGeometry() if maximized or minimized else self.geometry()
        state = WindowPresentationState(
            normal_geometry=(normal.x(), normal.y(), normal.width(), normal.height()),
            maximized=maximized,
            appearance=self.appearance.mode,
        )
        if self._presentation_settings.save(state):
            self._presentation_state = state
            return True
        return False

    def _available_screen_geometries(self) -> tuple[QRect, ...]:
        if self._available_screens_override is not None:
            return self._available_screens_override
        application = QApplication.instance()
        primary = application.primaryScreen()
        screens = [primary] if primary is not None else []
        screens.extend(
            screen for screen in application.screens() if screen is not primary
        )
        return tuple(screen.availableGeometry() for screen in screens)
