"""Combined native workspace journeys, always with injected temporary journals."""

from datetime import UTC

import pytest
from supported_fixtures import create_binary, journal_migrations

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
)
from reckonsolve.ui.workspace_state import Route


@pytest.fixture
def workspace(qtbot, tmp_path):
    database = Database.open(
        tmp_path / "journal.sqlite3", migrations=journal_migrations()
    )
    operations = PredictionOperations(database, local_timezone=UTC)
    window = MainWindow(operations, presentation_settings=MemoryPresentationSettings())
    qtbot.addWidget(
        window,
        before_close_func=lambda widget: setattr(
            widget.creation_task, "confirm_exit", lambda: True
        ),
    )
    window.show()
    qtbot.waitUntil(lambda: window._journal_screen.loaded_once, timeout=10000)
    yield window, operations
    window.creation_task.confirm_exit = lambda: True
    window.creation_task.reset()
    window.close()
    database.close()


def test_shared_toolbar_and_independent_performance_origin(workspace, qtbot):
    window, operations = workspace
    assert window.current_screen_name == "Journal"
    assert not window._toolbar.back.isVisible()
    prediction = create_binary(operations, "Workspace journey", 60)
    window._open_prediction(prediction.prediction_id)
    assert window.workspace.current.route is Route.DETAIL
    assert window._toolbar.back.text() == "Back to Journal"
    window.navigate_to("Performance")
    assert window._toolbar.home.isVisible()
    window.navigate_to("Settings")
    window.return_to_source()
    assert window.current_screen_name == "Performance"
    assert window.workspace.performance_origin.prediction_id == prediction.prediction_id
    window.return_to_source()
    assert window.workspace.current.prediction_id == prediction.prediction_id


def test_creation_switch_retains_work_and_appearance_retains_selection(
    workspace, qtbot
):
    window, _ = workspace
    assert not window.creation_task.dirty()
    window.navigate_to("New Prediction")
    adaptive = window._new_prediction_screen
    adaptive.question_input.setText("My entered question")
    adaptive.question_input.setFocus()
    adaptive.question_input.setSelection(3, 7)
    window.appearance.select(AppearanceMode.DARK)
    assert adaptive.question_input.selectedText() == "entered"
    adaptive.one_shot_requested.emit()
    one_shot = window._one_shot_creation_screen
    one_shot.question.setText("Other mode question")
    one_shot.cancelled.emit()
    assert adaptive.question_input.text() == "My entered question"
    assert window.creation_task.dirty(0) and window.creation_task.dirty(1)
    assert not window._toolbar.new.isVisible()
    assert not window._toolbar.performance.isVisible()
    assert not window._toolbar.settings.isVisible()
    window._shortcut_new()
    assert adaptive.question_input.text() == "My entered question"


def test_live_results_publish_complete_count_and_applied_query(workspace, qtbot):
    window, operations = workspace
    prediction = create_binary(operations, "Elephant complete result", 60)
    journal = window._journal_screen
    journal.search_input.setText("Elephant")
    assert journal.loading and journal.cards == [] and not journal.count.isVisible()
    assert journal.text_pending
    journal.submit_search()
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.count.text() == "1 Prediction"
    assert journal.cards[0].prediction_id == prediction.prediction_id
    journal.search_input.setText("Nothingmatches")
    journal.submit_search()
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.count.text() == "0 Predictions"
    assert "No predictions match" in journal.message.text()


def test_creation_native_discard_guard_keeps_then_clears_both_modes(workspace, qtbot):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    window, operations = workspace
    original = create_binary(operations, "Creation origin", 60)
    window._open_prediction(original.prediction_id)
    window.navigate_to("New Prediction")
    window._new_prediction_screen.question_input.setText("Uncommitted Adaptive")
    window._one_shot_creation_screen.question.setText("Uncommitted One-Shot")
    window._creation_stack.setCurrentIndex(1)

    def choose(label):
        dialog = QApplication.activeModalWidget()
        next(button for button in dialog.buttons() if button.text() == label).click()

    QTimer.singleShot(0, lambda: choose("Keep editing"))
    window.return_to_source()
    assert window.current_screen_name == "New Prediction"
    assert window._one_shot_creation_screen.question.text() == "Uncommitted One-Shot"
    QTimer.singleShot(0, lambda: choose("Discard changes and return"))
    window.return_to_source()
    assert window.workspace.current.prediction_id == original.prediction_id
    assert not window.creation_task.dirty()
    assert window._new_prediction_screen.question_input.text() == ""
    assert window._one_shot_creation_screen.question.text() == ""
    window.navigate_to("New Prediction")
    assert window._creation_stack.currentIndex() == 0
    assert (
        operations.journal.query_independently(
            window._journal_screen.state.request
        ).total
        == 1
    )


def test_temporary_origin_failure_retains_creation_work_and_is_not_deletion(
    workspace, monkeypatch
):
    from reckonsolve.application.errors import DatabaseBusyError

    window, operations = workspace
    original = create_binary(operations, "Temporary origin read", 60)
    window._open_prediction(original.prediction_id)
    window.navigate_to("New Prediction")
    window._new_prediction_screen.question_input.setText("Keep this input")
    discard_questions = []
    monkeypatch.setattr(
        window.creation_task,
        "confirm_exit",
        lambda: discard_questions.append(True) or True,
    )

    def busy(_identifier):
        raise DatabaseBusyError("Temporary lock")

    monkeypatch.setattr(operations, "get_prediction_for_navigation", busy)
    window.return_to_source()
    assert window.current_screen_name == "New Prediction"
    assert window._new_prediction_screen.question_input.text() == "Keep this input"
    assert window.workspace.new_origin.prediction_id == original.prediction_id
    assert discard_questions == []


def test_appearance_failure_keeps_page_filters_focus_and_forecasting_inputs(
    workspace, monkeypatch
):
    window, _operations = workspace
    window.navigate_to("New Prediction")
    editor = window._new_prediction_screen.question_input
    editor.setText("Retain selected words")
    editor.setFocus()
    editor.setSelection(7, 8)
    monkeypatch.setattr(window._presentation_settings, "save", lambda _state: False)
    window.appearance.toggle()
    assert window.current_screen_name == "New Prediction"
    assert (
        editor.text() == "Retain selected words" and editor.selectedText() == "selected"
    )
    assert "could not be remembered" in window._notification_host.current_message


def test_actual_palette_and_readable_rows_follow_both_appearances(workspace, qtbot):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QLabel

    from reckonsolve.ui.journal.rows import QuestionLabel
    from reckonsolve.ui.visual_system import semantic_colors

    window, operations = workspace
    create_binary(operations, "A full Question that wraps comfortably " * 14, 60)
    journal = window._journal_screen
    for mode in (AppearanceMode.LIGHT, AppearanceMode.DARK):
        window.appearance.select(mode)
        journal.refresh()
        qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
        qtbot.wait(60)
        colors = semantic_colors(window.palette())
        assert colors.is_dark == (mode is AppearanceMode.DARK)
        question = journal.cards[0].findChild(QuestionLabel)
        forecast = next(
            label
            for label in journal.cards[0].findChildren(QLabel)
            if label.text() == "60% Yes"
        )
        assert question.font().pointSizeF() >= forecast.font().pointSizeF()
        assert question.indent() == 0
        assert question.contentsRect().left() == forecast.contentsRect().left() == 0
        assert (
            question.palette().color(QPalette.ColorRole.WindowText).name()
            == colors.text
        )
        assert question.height() >= question.heightForWidth(question.width())
        assert journal.scroll.horizontalScrollBar().maximum() == 0
        assert not window._toolbar.appearance.icon().isNull()


def test_appearance_switch_updates_style_once_without_reloading_journal(
    workspace, qtbot, monkeypatch
):
    from PySide6.QtWidgets import QApplication

    from reckonsolve.ui.visual_system import semantic_colors

    window, operations = workspace
    create_binary(operations, "Retain this card during appearance changes", 75)
    journal = window._journal_screen
    journal.refresh()
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    window.appearance.select(AppearanceMode.LIGHT)
    QApplication.processEvents()
    card = journal.cards[0]
    request = journal.state.request
    styles = []
    original = window.setStyleSheet

    def record(stylesheet):
        styles.append(stylesheet)
        original(stylesheet)

    monkeypatch.setattr(window, "setStyleSheet", record)
    for expected_dark in (True, False):
        window.appearance.toggle()
        QApplication.processEvents()
        assert semantic_colors(window.palette()).is_dark is expected_dark
        assert journal.cards[0] is card and journal.state.request == request
        assert not journal.loading
    assert len(styles) == 2


def test_render_failure_shows_no_partial_listing_or_false_count(
    workspace, qtbot, monkeypatch, caplog
):
    window, operations = workspace
    create_binary(operations, "Rendering failure marker", 60)

    def fail(*args, **kwargs):
        raise RuntimeError("Injected rendering defect")

    monkeypatch.setattr("reckonsolve.ui.journal.screen.JournalCard", fail)
    journal = window._journal_screen
    journal.refresh()
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.page is None and journal.cards == []
    assert not journal.count.isVisible()
    assert "Injected rendering defect" in journal.message.text()
    assert "Unexpected Journal rendering failure" in caplog.text


def test_archive_refusal_blocks_old_listing_navigation_and_polling(
    workspace, monkeypatch
):
    from reckonsolve.data.migrations import MigrationError

    window, _operations = workspace
    notices = []
    monkeypatch.setattr(
        "reckonsolve.ui.main_window.QMessageBox.critical",
        lambda *args: notices.append(args[2]),
    )
    failure = MigrationError("Injected incompatible archive")
    window._archive_refused(failure)
    window._archive_refused(failure)
    journal = window._journal_screen
    assert journal.refused and not journal.poll.isActive()
    assert (
        journal.page is None and journal.cards == [] and not journal.count.isVisible()
    )
    assert "incompatible archive" in journal.message.text()
    window._shortcut_new()
    assert window.current_screen_name == "Journal"
    assert not window._toolbar.new.isEnabled() and len(notices) == 1
