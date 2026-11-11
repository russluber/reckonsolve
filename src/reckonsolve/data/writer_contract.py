"""Connection-local capability for schema-21 writers, including stale clients."""

import sqlite3

WRITER_VERSION = 21


def register_writer(connection: sqlite3.Connection) -> None:
    """Authorize this build's connection; old connections lack this function.

    SQL guards remain in the database after upgrade. An already-open older
    process therefore fails before a canonical write, not just at next startup.
    This is compatibility coordination, not an authentication/security system.
    """
    connection.create_function("reckonsolve_writer_version", 0, lambda: WRITER_VERSION)
