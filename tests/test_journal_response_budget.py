"""The required 2,000-record corpus checks full count, rows and native latency.

Local evaluation budget, selected before measurement: warm request to rendered
60-row page p95 <= 750 ms; cold <= 1.5 s. Timing is reported, not a machine-speed
CI assertion. A live-search release needs recorded evidence within that budget.
"""

import json
from time import perf_counter

from journal_corpus import populate_mixed_corpus

from reckonsolve.data.database import Database
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.ui.journal.screen import JournalScreen
from reckonsolve.ui.visual_system import install_visual_system


def test_mixed_2000_prediction_count_and_request_to_render(qtbot, tmp_path):
    database = Database.open(tmp_path / "mixed.sqlite3")
    try:
        operations, _clock = populate_mixed_corpus(database)
        page = operations.journal.query(JournalRequest())
        assert page.total == 2000 and len(page.rows) == 60 and page.has_more
        with database.read_snapshot() as connection:
            assert (
                sorted(
                    row[0]
                    for row in connection.execute("""SELECT COUNT(*) FROM predictions p
                JOIN prediction_forecast_contracts c ON c.prediction_id = p.id
                GROUP BY p.prediction_type, c.forecast_model""")
                )
                == [500] * 4
            )
        screen = JournalScreen(operations.journal.query_independently)
        install_visual_system(screen)
        qtbot.addWidget(
            screen, before_close_func=lambda widget: widget.close_retrieval()
        )
        screen.resize(1140, 780)
        screen.show()
        elapsed = []
        for index, text in enumerate(
            (
                "",
                "railway",
                "elephant",
                "elaphant",
                "railway evidence",
                "commuter",
                "railway",
                "elephant",
            )
        ):
            started = perf_counter()
            screen.state.change(text=text, include_history=text == "commuter")
            screen.refresh(restore=False)
            qtbot.waitUntil(lambda: not screen.loading, timeout=30000)
            assert screen.page is not None
            assert len(screen.cards) == (0 if text == "elaphant" else 60)
            assert screen.page.total == (
                0 if text == "elaphant" else 1000 if text == "commuter" else 2000
            )
            if text == "elaphant":
                assert screen.page.suggestion == "elephant"
            qtbot.wait(40)  # Include native layout/paint after the queued response.
            elapsed.append(round((perf_counter() - started) * 1000, 1))
        print("JOURNAL_LATENCY_MS", json.dumps(elapsed))
        screen.close_retrieval()
    finally:
        database.close()
