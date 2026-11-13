"""Coalesce requests onto one worker; only the current generation may publish."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from reckonsolve.application.errors import ApplicationError

logger = logging.getLogger(__name__)


class _Signals(QObject):
    done = Signal(int, object, object)


class _Read[Request, Result](QRunnable):
    def __init__(
        self,
        generation: int,
        request: Request,
        query: Callable[[Request], Result],
    ) -> None:
        super().__init__()
        self.generation, self.request, self.query = generation, request, query
        self.signals = _Signals()

    def run(self) -> None:
        result, failure = None, None
        try:
            result = self.query(self.request)
        except Exception as error:
            # Crossing the thread boundary must preserve both expected failures
            # and visible diagnostics for unexpected defects, never false zero.
            if not isinstance(error, ApplicationError):
                logger.exception("Unexpected report retrieval failure")
            failure = error
        self.signals.done.emit(self.generation, result, failure)


class ReadRequests[Request, Result](QObject):
    pending = Signal()
    ready = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        query: Callable[[Request], Result],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self.query = query
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.generation = 0
        self.latest: Request | None = None
        self.busy = False
        self.closed = False

    def request(self, request: Request) -> None:
        self.generation += 1
        self.latest = request
        self.pending.emit()
        if not self.busy:
            self._start()

    def invalidate(self) -> None:
        """Expire both a running read and queued work during input debounce."""
        self.generation += 1
        self.latest = None

    def _start(self) -> None:
        if self.closed or self.latest is None:
            return
        self.busy = True
        worker = _Read(self.generation, self.latest, self.query)
        self.latest = None
        worker.signals.done.connect(self._done)
        self.pool.start(worker)

    def _done(self, generation: int, result, failure) -> None:
        self.busy = False
        if self.closed:
            return
        if generation == self.generation:
            if failure is not None:
                self.failed.emit(failure)
            else:
                self.ready.emit(result)
        else:
            self._start()

    def close(self) -> None:
        self.closed = True
        self.generation += 1
        self.pool.clear()
        self.pool.waitForDone(30_000)
