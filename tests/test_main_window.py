from PySide6.QtWidgets import QLabel, QListWidget, QStackedWidget
from pytestqt.qtbot import QtBot

from reckonsolve.ui import MainWindow

EXPECTED_SCREEN_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)


def test_main_window_has_expected_navigation(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    navigation = window.findChild(QListWidget, "primaryNavigation")

    assert window.windowTitle() == "Reckonsolve"
    assert window.screen_names == EXPECTED_SCREEN_NAMES
    assert navigation is not None
    assert (
        tuple(navigation.item(index).text() for index in range(navigation.count()))
        == EXPECTED_SCREEN_NAMES
    )
    assert window.current_screen_name == "Dashboard"
    assert navigation.currentRow() == 0


def test_main_window_navigates_to_each_primary_screen(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    screen_stack = window.findChild(QStackedWidget, "screenStack")

    assert screen_stack is not None
    for expected_index, screen_name in enumerate(EXPECTED_SCREEN_NAMES):
        window.navigate_to(screen_name)

        assert window.current_screen_name == screen_name
        assert screen_stack.currentIndex() == expected_index


def test_each_screen_is_an_honest_placeholder(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    for screen_name in EXPECTED_SCREEN_NAMES:
        window.navigate_to(screen_name)
        current_screen = window.centralWidget().findChild(
            QLabel,
            f"{_object_name_prefix(screen_name)}ScreenPlaceholder",
        )

        assert current_screen is not None
        assert any(
            future_word in current_screen.text() for future_word in ("coming", "will")
        )


def test_main_window_can_be_shown_and_closed(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()


def _object_name_prefix(screen_name: str) -> str:
    first_word, *remaining_words = screen_name.split()
    return first_word.lower() + "".join(remaining_words)
