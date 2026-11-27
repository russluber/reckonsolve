"""Wait for current asynchronous report data and settled Qt geometry in UI checks."""

import runpy
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from reckonsolve.application.performance import Section
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database


def loaded(screen, qtbot, *, refresh=True):
    if refresh:
        screen.refresh()
    qtbot.waitUntil(lambda: not screen.loading, timeout=10000)
    assert screen.report is not None, screen.message.text()
    qtbot.wait(30)
    return screen.report


def adaptive_binary(screen):
    return screen.sections[Section.ADAPTIVE_BINARY]


def adaptive_numeric(screen):
    return screen.sections[Section.ADAPTIVE_NUMERIC]


def one_shot_binary(screen):
    return screen.sections[Section.ONE_SHOT_BINARY]


def one_shot_numeric(screen):
    return screen.sections[Section.ONE_SHOT_NUMERIC]


class Clock:
    def now(self):
        return datetime(2026, 11, 12, 12, tzinfo=UTC)


@contextmanager
def performance_database(tmp_path):
    path = tmp_path / "performance.sqlite3"
    runpy.run_path(str(Path(__file__).parents[1] / "tools/run_visual_review.py"))[
        "_seed_review_database"
    ](path, long_text=False, detail=True)
    database = Database.open(path)
    operations = PredictionOperations(database, Clock())
    yield database, operations
    database.close()
