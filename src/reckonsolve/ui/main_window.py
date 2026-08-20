"""The primary Reckonsolve application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.dashboard import AttentionSettingsScreen, DashboardScreen
from reckonsolve.ui.prediction_browser import PredictionBrowserScreen
from reckonsolve.ui.screens import (
    NewPredictionScreen,
    PredictionDetailScreen,
    PredictionOperations,
    PredictionSnapshot,
)

_SCREEN_DEFINITIONS: tuple[tuple[str, str, str | None], ...] = (
    (
        "Dashboard",
        "dashboard",
        None,
    ),
    (
        "New Prediction",
        "newPrediction",
        None,
    ),
    (
        "Prediction Detail",
        "predictionDetail",
        None,
    ),
    (
        "Predictions",
        "predictions",
        None,
    ),
    (
        "Analytics",
        "analytics",
        "Forecast analytics are coming in a later milestone.",
    ),
    (
        "Settings",
        "settings",
        None,
    ),
)


class MainWindow(QMainWindow):
    """Display the primary navigation shell for the desktop application."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mainWindow")
        self.setWindowTitle("Reckonsolve")
        self.resize(960, 640)

        self._navigation = QListWidget(self)
        self._navigation.setObjectName("primaryNavigation")
        self._navigation.setAccessibleName("Primary navigation")
        self._navigation.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._screen_stack = QStackedWidget(self)
        self._screen_stack.setObjectName("screenStack")

        self._new_prediction_screen = NewPredictionScreen(operations)
        self._prediction_detail_screen = PredictionDetailScreen(operations)
        self._dashboard_screen = DashboardScreen(operations)
        self._prediction_browser_screen = PredictionBrowserScreen(operations)
        self._settings_screen = AttentionSettingsScreen(operations)

        for screen_name, object_name, placeholder_text in _SCREEN_DEFINITIONS:
            navigation_item = QListWidgetItem(screen_name)
            navigation_item.setData(Qt.ItemDataRole.UserRole, screen_name)
            self._navigation.addItem(navigation_item)
            if screen_name == "Dashboard":
                screen = self._dashboard_screen
            elif screen_name == "New Prediction":
                screen = self._new_prediction_screen
            elif screen_name == "Prediction Detail":
                screen = self._prediction_detail_screen
            elif screen_name == "Predictions":
                screen = self._prediction_browser_screen
            elif screen_name == "Settings":
                screen = self._settings_screen
            else:
                if placeholder_text is None:
                    raise AssertionError(f"Missing placeholder text for {screen_name}")
                screen = self._create_placeholder_screen(
                    screen_name,
                    object_name,
                    placeholder_text,
                )
            self._screen_stack.addWidget(screen)

        content = QWidget(self)
        content.setObjectName("mainContent")
        layout = QHBoxLayout(content)
        layout.addWidget(self._navigation)
        layout.addWidget(self._screen_stack, 1)
        self.setCentralWidget(content)

        self._navigation.currentRowChanged.connect(self._show_screen)
        self._new_prediction_screen.prediction_created.connect(
            self._show_created_prediction
        )
        self._dashboard_screen.prediction_selected.connect(
            self._show_selected_prediction
        )
        self._prediction_browser_screen.prediction_selected.connect(
            self._show_selected_prediction
        )
        self._settings_screen.threshold_changed.connect(
            lambda _value: self._dashboard_screen.refresh()
        )
        self._navigation.setCurrentRow(0)

    @property
    def screen_names(self) -> tuple[str, ...]:
        """Return the primary screens in navigation order."""
        return tuple(definition[0] for definition in _SCREEN_DEFINITIONS)

    @property
    def current_screen_name(self) -> str:
        """Return the name of the currently displayed primary screen."""
        return self.screen_names[self._screen_stack.currentIndex()]

    def navigate_to(self, screen_name: str) -> None:
        """Select a primary screen by its exact display name."""
        try:
            screen_index = self.screen_names.index(screen_name)
        except ValueError:
            message = f"Unknown Reckonsolve screen: {screen_name!r}"
            raise ValueError(message) from None

        self._navigation.setCurrentRow(screen_index)

    def _show_screen(self, screen_index: int) -> None:
        self._screen_stack.setCurrentIndex(screen_index)
        if self.current_screen_name == "Dashboard":
            self._dashboard_screen.refresh()
        elif self.current_screen_name == "New Prediction":
            self._new_prediction_screen.focus_question()
        elif self.current_screen_name == "Prediction Detail":
            self._prediction_detail_screen.refresh()
        elif self.current_screen_name == "Predictions":
            self._prediction_browser_screen.refresh()
            self._prediction_browser_screen.focus_search()
        elif self.current_screen_name == "Settings":
            self._settings_screen.refresh()

    def _show_created_prediction(self, prediction: PredictionSnapshot) -> None:
        self._prediction_detail_screen.show_prediction(prediction)
        self.navigate_to("Prediction Detail")

    def _show_selected_prediction(self, prediction: PredictionSnapshot) -> None:
        self._prediction_detail_screen.show_prediction(prediction)
        self.navigate_to("Prediction Detail")

    @staticmethod
    def _create_placeholder_screen(
        screen_name: str,
        object_name: str,
        placeholder_text: str,
    ) -> QWidget:
        screen = QWidget()
        screen.setObjectName(f"{object_name}Screen")

        title = QLabel(screen_name, screen)
        title.setObjectName(f"{object_name}ScreenTitle")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        placeholder = QLabel(placeholder_text, screen)
        placeholder.setObjectName(f"{object_name}ScreenPlaceholder")
        placeholder.setWordWrap(True)

        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addStretch()
        return screen
