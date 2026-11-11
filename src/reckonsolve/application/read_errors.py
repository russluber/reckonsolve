"""Translate identified transient read failures without disguising other faults."""

import sqlite3
from collections.abc import Callable
from functools import wraps

from .errors import DatabaseBusyError


def expected_database_read[**P, T](operation: Callable[P, T]) -> Callable[P, T]:
    """Keep SQLite busy/locked errors inside the presentation error boundary.

    Extended SQLite error codes retain their primary code in the low byte.
    Other storage failures and compatibility refusals must keep their meaning;
    they are not evidence that rebuilding the search projection would help.
    """

    @wraps(operation)
    def perform(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return operation(*args, **kwargs)
        except sqlite3.Error as error:
            primary = getattr(error, "sqlite_errorcode", 0) & 0xFF
            if primary not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise
            raise DatabaseBusyError(
                "The database is busy with another Reckonsolve action. "
                "Wait a moment and try again."
            ) from error

    return perform
