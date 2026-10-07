"""Explainable search results and matched-history navigation."""

from __future__ import annotations

from datetime import UTC, datetime

from main_window_fakes import (
    FakeJournalCorrection,
    FakeJournalTimelineEvent,
    FakePrediction,
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.search import (
    SearchDocument,
    SearchMatchMode,
    SearchSourceKind,
)
from reckonsolve.ui import MainWindow


def test_prediction_search_renders_safe_explainable_rows_and_shared_controls(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will <evidence> remain literal?",
        62,
        tags=("Research",),
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("evidence")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1
    assert results.currentRow() == -1
    assert results.selectedItems() == []
    assert operations.search_calls[-1][:3] == (
        "evidence",
        SearchMatchMode.ALL,
        False,
    )
    source = _required_child(window, QLabel, "predictionSearchResultSource7")
    snippet = _required_child(window, QLabel, "predictionSearchResultSnippet7")
    assert source.text() == "Question match"
    assert snippet.text() == "Will &lt;<b>evidence</b>&gt; remain literal?"
    assert "Question match" in str(
        results.item(0).data(Qt.ItemDataRole.AccessibleDescriptionRole)
    )

    history = _required_child(window, QCheckBox, "predictionSearchIncludeHistory")
    history.setChecked(True)
    assert operations.search_calls[-1][2] is True
    mode = _required_child(window, QComboBox, "predictionSearchMatchMode")
    mode.setCurrentIndex(mode.findData(SearchMatchMode.ANY.value))
    assert operations.search_calls[-1][1] is SearchMatchMode.ANY


def test_prediction_search_offers_deliberate_any_word_and_spelling_actions(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the archive remain searchable?", 50)
    )
    operations.search_any_word_available = True
    operations.search_suggestion = "archive"
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("archive absentword")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    any_word = _required_child(window, QPushButton, "predictionSearchAnyWordButton")
    suggestion = _required_child(
        window, QPushButton, "predictionSearchSuggestionButton"
    )
    assert not any_word.isHidden()
    assert not suggestion.isHidden()
    assert "archive" in suggestion.text()

    qtbot.mouseClick(any_word, Qt.MouseButton.LeftButton)
    assert operations.search_calls[-1][1] is SearchMatchMode.ANY
    qtbot.mouseClick(suggestion, Qt.MouseButton.LeftButton)
    assert search.text() == "archive"
    assert operations.search_calls[-1][0] == "archive"


def test_historical_journal_search_opens_the_exact_detail_context(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(7, "Will remembered evidence matter?", 62)
    operations = FakePredictionOperations(latest)
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=8,
            prediction_id=7,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
            body="Corrected Journal evidence",
            original_body="Superseded remembered wording",
            forecast_revision_id=latest.current_revision_id,
            forecast_revision_sequence=latest.current_revision_sequence,
            forecast_probability_percent=latest.probability_percent,
            current_correction_id=11,
            corrections=(
                FakeJournalCorrection(
                    correction_id=11,
                    body="Corrected Journal evidence",
                    corrected_at=datetime(2026, 8, 14, 19, 30, tzinfo=UTC),
                ),
            ),
        )
    ]
    operations.search_document = SearchDocument(
        prediction_id=7,
        source_kind=SearchSourceKind.JOURNAL,
        source_record_id=8,
        source_version_id=None,
        source_sequence=None,
        occurred_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
        is_superseded=True,
        text="Superseded remembered wording",
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    _required_child(window, QCheckBox, "predictionSearchIncludeHistory").setChecked(
        True
    )
    search.setText("remembered")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    results.itemActivated.emit(results.item(0))

    assert window.current_screen_name == "Prediction Detail"
    history = _required_child(window, QGroupBox, "journalEntryEditHistory8")
    original = _required_child(window, QLabel, "journalEntryOriginalBody8")
    assert history.isChecked()
    assert original.property("searchMatchEmphasis") is True


def test_prediction_search_failure_retains_the_last_successful_rows(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will archive search remain visible?", 50)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    search.setText("archive")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1

    operations.browser_error = ApplicationError("Search is temporarily busy.")
    search.setText("different")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    assert results.count() == 1
    assert "archive search" in str(
        results.item(0).data(Qt.ItemDataRole.AccessibleTextRole)
    )
    assert _required_child(window, QLabel, "predictionBrowserError").text() == (
        "Predictions could not refresh; showing the last loaded results. "
        "Search is temporarily busy."
    )


def test_prediction_search_controls_do_not_shift_when_results_become_empty(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will wow remain searchable?", 50)
    )
    window = MainWindow(operations)
    window.resize(960, 720)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")

    search.setText("wow")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    qtbot.waitUntil(
        lambda: (
            _required_child(window, QListWidget, "predictionBrowserResults").count()
            == 1
        )
    )
    populated_top = search.mapTo(window, search.rect().topLeft()).y()

    search.setText("sdsfs")
    qtbot.keyPress(search, Qt.Key.Key_Return)
    empty = _required_child(window, QLabel, "predictionBrowserEmpty")
    qtbot.waitUntil(lambda: not empty.isHidden())

    assert search.mapTo(window, search.rect().topLeft()).y() == populated_top
