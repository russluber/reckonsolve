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

_SCREEN_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    (
        "Dashboard",
        "dashboard",
        "Your forecasting dashboard is coming in a later milestone.",
    ),
    (
        "New Prediction",
        "newPrediction",
        "Prediction creation is coming in the next milestone.",
    ),
    (
        "Prediction Detail",
        "predictionDetail",
        "Prediction details will appear here after creation is implemented.",
    ),
    (
        "Predictions",
        "predictions",
        "Prediction browsing is coming in a later milestone.",
    ),
    (
        "Analytics",
        "analytics",
        "Forecast analytics are coming in a later milestone.",
    ),
    (
        "Settings",
        "settings",
        "Settings and data-management tools are coming in a later milestone.",
    ),
)


class MainWindow(QMainWindow):
    """Display the primary navigation shell for the desktop application."""

    def __init__(self, parent: QWidget | None = None) -> None:
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

        for screen_name, object_name, placeholder_text in _SCREEN_DEFINITIONS:
            navigation_item = QListWidgetItem(screen_name)
            navigation_item.setData(Qt.ItemDataRole.UserRole, screen_name)
            self._navigation.addItem(navigation_item)
            self._screen_stack.addWidget(
                self._create_placeholder_screen(
                    screen_name,
                    object_name,
                    placeholder_text,
                )
            )

        content = QWidget(self)
        content.setObjectName("mainContent")
        layout = QHBoxLayout(content)
        layout.addWidget(self._navigation)
        layout.addWidget(self._screen_stack, 1)
        self.setCentralWidget(content)

        self._navigation.currentRowChanged.connect(self._screen_stack.setCurrentIndex)
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
