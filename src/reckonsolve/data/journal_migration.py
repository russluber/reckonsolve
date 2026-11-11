"""New ordered Journal migration; historical migration statements stay intact."""

import sqlite3

from .m56_migration import SNAPSHOT_FIELDS


def build_journal_statements(previous: tuple[str, ...]) -> tuple[str, ...]:
    """Derive guarded application tables from the preceding immutable schema."""
    statements = [
        (
            "ALTER TABLE one_shot_corrections ADD COLUMN source_action TEXT NOT NULL "
            "DEFAULT 'transcription' CHECK (source_action IN ('transcription', 'postmortem'))"
        ),
        "DROP TABLE saved_view_tags",
        "DROP TABLE saved_views",
    ]
    other_changes = " OR ".join(
        f"NEW.old_{field} IS NOT NEW.new_{field}"
        for field in SNAPSHOT_FIELDS
        if field != "postmortem"
    )
    statements.append(f"""CREATE TRIGGER one_shot_postmortem_action
        BEFORE INSERT ON one_shot_corrections
        WHEN NEW.source_action = 'postmortem' AND (
            (SELECT status FROM predictions WHERE id = NEW.prediction_id) != 'resolved'
            OR ({other_changes})
        )
        BEGIN SELECT RAISE(ABORT, 'Postmortem action must change reflection alone on an answered One-Shot'); END""")
    connection = sqlite3.connect(":memory:", autocommit=True)
    try:
        for statement in (*previous, *statements):
            connection.execute(statement)
        # FTS virtual/shadow tables cannot carry ordinary BEFORE triggers.
        # Repair also updates guarded search_index_state in the same transaction.
        tables = sorted(
            row[1]
            for row in connection.execute("PRAGMA main.table_list")
            if row[2] == "table" and not row[1].startswith("sqlite_")
        )
    finally:
        connection.close()
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        for action in ("INSERT", "UPDATE", "DELETE"):
            name = f"journal_writer_{table}_{action.lower()}"
            statements.append(f"""CREATE TRIGGER "{name}" BEFORE {action} ON {quoted}
                WHEN reckonsolve_writer_version() < 21
                BEGIN SELECT RAISE(ABORT, 'This journal requires the updated Reckonsolve writer'); END""")
    return tuple(statements)
