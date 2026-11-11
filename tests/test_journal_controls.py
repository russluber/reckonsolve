"""Applied/filter draft boundaries and one current-generation worker result."""

from datetime import date
from threading import Event

from PySide6.QtCore import QDate, QSignalBlocker
from PySide6.QtWidgets import QWidget

from reckonsolve.domain.browser import ArchiveQuery, ArchiveSort, ArchiveTagMatchMode
from reckonsolve.domain.journal import JournalPage, JournalRequest, JournalView
from reckonsolve.domain.search import SearchMatchMode, parse_search_text
from reckonsolve.ui.journal.filters import JournalFiltersDialog
from reckonsolve.ui.journal.retrieval import JournalRetrieval
from reckonsolve.ui.journal.state import JournalState


def test_filter_cancel_clear_apply_and_inclusive_open_ended_dates(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    original = JournalRequest(
        text="railway",
        view=JournalView.UNRESOLVED,
        filters=ArchiveQuery(tags=("Work",), tag_match_mode=ArchiveTagMatchMode.ANY),
        match_mode=SearchMatchMode.ANY,
        include_history=True,
        manual_sort=ArchiveSort.CREATED_OLDEST,
    )
    dialog = JournalFiltersDialog(original, ("Work", "Personal"), parent)
    qtbot.addWidget(dialog)
    dialog.clear()
    dialog.reject()
    assert dialog.applied == original
    dialog = JournalFiltersDialog(original, ("Work", "Personal"), parent)
    qtbot.addWidget(dialog)
    dialog.clear()
    enabled, editor = dialog.date_rows[0]
    enabled.setChecked(True)
    editor.setDate(QDate(2026, 11, 10))
    dialog.apply()
    assert dialog.applied.filters.date_start == date(2026, 11, 10)
    assert dialog.applied.filters.date_end is None
    assert dialog.applied.text == original.text and dialog.applied.view is original.view
    assert dialog.applied.manual_sort is original.manual_sort
    assert (
        dialog.applied.match_mode is SearchMatchMode.ALL
        and not dialog.applied.include_history
    )
    assert dialog.applied.filters.tags == ()


def test_invalid_or_reversed_filter_dates_apply_nothing_and_retain_raw_input(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    original = JournalRequest(text="unchanged")
    dialog = JournalFiltersDialog(original, (), parent)
    qtbot.addWidget(dialog)
    dialog.show()
    from_enabled, start = dialog.date_rows[0]
    through_enabled, end = dialog.date_rows[1]
    from_enabled.setChecked(True)
    through_enabled.setChecked(True)
    start.setDate(QDate(2026, 11, 12))
    end.setDate(QDate(2026, 11, 10))
    dialog.apply()
    assert dialog.applied == original and dialog.isVisible()
    assert start.date() == QDate(2026, 11, 12)
    # Represent the native editor's intermediate raw state without interpreting
    # it as a programmatic date replacement before Apply gets to inspect it.
    with QSignalBlocker(start.lineEdit()):
        start.lineEdit().setText("12 Nov")
    raw = start.lineEdit().text()
    assert raw == "12 Nov"
    dialog.apply()
    assert dialog.applied == original and start.lineEdit().text() == raw
    assert "Complete" in dialog.error.text()


def test_manual_sort_persists_except_cleared_relevance_and_reset_is_complete():
    state = JournalState()
    state.change(
        manual_sort=ArchiveSort.CREATED_OLDEST, text="railway", include_history=True
    )
    state.change(view=JournalView.NEEDS_POSTMORTEM)
    assert state.request.manual_sort is ArchiveSort.CREATED_OLDEST
    state.change(manual_sort=ArchiveSort.RELEVANCE)
    state.change(text="")
    assert state.request.manual_sort is None
    state.change(text="railway")
    assert state.request.manual_sort is None
    state.reset()
    assert state.request == JournalRequest()


def test_overlapping_requests_coalesce_and_only_latest_may_publish(qtbot):
    started, release = Event(), Event()
    calls, pages = [], []
    parent = QWidget()
    qtbot.addWidget(parent)

    def query(request):
        calls.append(request.text)
        if request.text == "first":
            started.set()
            assert release.wait(5)
        return JournalPage(request, (), 0, (), parse_search_text(request.text))

    retrieval = JournalRetrieval(query, parent)
    retrieval.ready.connect(pages.append)
    try:
        retrieval.request(JournalRequest(text="first"))
        qtbot.waitUntil(started.is_set)
        retrieval.request(JournalRequest(text="second"))
        retrieval.request(JournalRequest(text="latest"))
        release.set()
        qtbot.waitUntil(lambda: len(pages) == 1)
        assert calls == ["first", "latest"]
        assert pages[0].request.text == "latest"
    finally:
        release.set()
        retrieval.close()
