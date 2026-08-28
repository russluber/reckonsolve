"""Rebuildable FTS5 projection derived from canonical Prediction history."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.search import (
    SearchDocument,
    SearchSourceKind,
    normalize_search_literal,
)

SEARCH_PROJECTION_VERSION = 1


class SearchIndexError(sqlite3.DatabaseError):
    """Base class for explicit search capability and repair failures."""


class SearchIndexUnavailableError(SearchIndexError):
    """The running SQLite library does not provide the required FTS5 module."""


class SearchIndexRepairRequiredError(SearchIndexError):
    """The derived index is absent, inconsistent, or otherwise needs rebuilding."""


class SearchIndexBusyError(SearchIndexError):
    """Another local connection temporarily prevents a search read or repair."""


def require_fts5(connection: sqlite3.Connection) -> None:
    """Prove FTS5 exists without changing the canonical database schema."""

    try:
        connection.execute(
            "CREATE VIRTUAL TABLE temp.reckonsolve_fts5_probe USING fts5(body)"
        )
        connection.execute("DROP TABLE temp.reckonsolve_fts5_probe")
    except sqlite3.Error as error:
        raise SearchIndexUnavailableError(
            "This Python SQLite build does not provide the FTS5 search module."
        ) from error


def initialize_search_index(connection: sqlite3.Connection) -> bool:
    """Bring a migrated search projection to its expected version before use."""

    object_names = _search_object_names(connection)
    if not object_names:
        return False
    _require_complete_search_schema(object_names)
    if connection.in_transaction:
        raise SearchIndexError(
            "Search-index initialization cannot start inside another transaction."
        )

    connection.execute("BEGIN IMMEDIATE")
    try:
        state = connection.execute(
            """
            SELECT projection_version, document_count
            FROM search_index_state
            WHERE singleton_id = 1
            """
        ).fetchone()
        if (
            state is None
            or int(state[0]) != SEARCH_PROJECTION_VERSION
            or int(state[1]) != _search_document_count(connection)
        ):
            rebuild_search_index(connection)
        else:
            refresh_pending_search_documents(connection)
        try:
            check_search_index(connection)
        except SearchIndexRepairRequiredError:
            # Counts and the projection-version marker cannot detect an
            # equal-sized but incorrect projection. Canonical history is
            # authoritative, so restart/recovery repairs that case before
            # an apparently successful search can return false emptiness.
            rebuild_search_index(connection)
            check_search_index(connection)
        connection.execute("COMMIT")
    except BaseException as error:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        if isinstance(error, SearchIndexError):
            raise
        if isinstance(error, sqlite3.Error):
            raise SearchIndexRepairRequiredError(
                "The local search index could not be initialized from canonical data."
            ) from error
        raise
    return True


def refresh_pending_search_documents(connection: sqlite3.Connection) -> None:
    """Replace all dirty Prediction projections inside the caller's transaction."""

    rows = connection.execute(
        "SELECT prediction_id FROM search_dirty_predictions ORDER BY prediction_id"
    ).fetchall()
    if not rows:
        return
    _require_recorded_document_count(connection)
    for row in rows:
        prediction_id = int(row[0])
        _replace_prediction_documents(connection, prediction_id)
        connection.execute(
            "DELETE FROM search_dirty_predictions WHERE prediction_id = ?",
            (prediction_id,),
        )
    _record_document_count(connection)


def rebuild_search_index(connection: sqlite3.Connection) -> None:
    """Discard and deterministically reproduce every derived document."""

    connection.execute("DELETE FROM prediction_search")
    prediction_rows = connection.execute(
        "SELECT id FROM predictions ORDER BY id"
    ).fetchall()
    for row in prediction_rows:
        _insert_documents(
            connection,
            project_prediction_documents(connection, int(row[0])),
        )
    connection.execute("DELETE FROM search_dirty_predictions")
    document_count = _search_document_count(connection)
    connection.execute(
        """
        UPDATE search_index_state
        SET projection_version = ?, document_count = ?
        WHERE singleton_id = 1
        """,
        (SEARCH_PROJECTION_VERSION, document_count),
    )
    if connection.execute("SELECT changes()").fetchone()[0] != 1:
        raise SearchIndexRepairRequiredError(
            "The search projection version record is missing."
        )


def check_search_index(
    connection: sqlite3.Connection,
    *,
    verify_projection: bool = True,
) -> None:
    """Verify FTS internals and optionally compare every derived document."""

    _require_complete_search_schema(_search_object_names(connection))
    state = connection.execute(
        """
        SELECT projection_version, document_count
        FROM search_index_state
        WHERE singleton_id = 1
        """
    ).fetchone()
    if state is None or int(state[0]) != SEARCH_PROJECTION_VERSION:
        raise SearchIndexRepairRequiredError(
            "The search index uses an incompatible projection version."
        )
    if connection.execute("SELECT 1 FROM search_dirty_predictions LIMIT 1").fetchone():
        raise SearchIndexRepairRequiredError(
            "The search index has pending canonical changes."
        )
    if int(state[1]) != _search_document_count(connection):
        raise SearchIndexRepairRequiredError(
            "The search index has missing or unexpected documents."
        )
    try:
        connection.execute(
            "INSERT INTO prediction_search(prediction_search) VALUES('integrity-check')"
        )
    except sqlite3.Error as error:
        raise SearchIndexRepairRequiredError(
            "SQLite reported that the local full-text index is inconsistent."
        ) from error

    if not verify_projection:
        return
    expected: list[tuple[object, ...]] = []
    for row in connection.execute("SELECT id FROM predictions ORDER BY id").fetchall():
        expected.extend(
            _document_comparison_key(document)
            for document in project_prediction_documents(connection, int(row[0]))
        )
    actual = [
        (
            int(row["prediction_id"]),
            str(row["source_kind"]),
            int(row["source_record_id"]),
            None if row["source_version_id"] is None else int(row["source_version_id"]),
            None if row["source_sequence"] is None else int(row["source_sequence"]),
            None if row["occurred_at"] is None else str(row["occurred_at"]),
            bool(int(row["is_superseded"])),
            str(row["body"]),
        )
        for row in connection.execute(
            """
            SELECT
                prediction_id, source_kind, source_record_id,
                source_version_id, source_sequence, occurred_at,
                is_superseded, body
            FROM prediction_search
            """
        ).fetchall()
    ]
    if sorted(expected, key=_comparison_sort_key) != sorted(
        actual, key=_comparison_sort_key
    ):
        raise SearchIndexRepairRequiredError(
            "The search index does not match canonical Prediction history."
        )


def project_prediction_documents(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> tuple[SearchDocument, ...]:
    """Derive the complete current and superseded corpus for one Prediction."""

    prediction = connection.execute(
        """
        SELECT id, question, background, resolution_criteria, created_at, updated_at
        FROM predictions
        WHERE id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if prediction is None:
        return ()

    created_at = parse_utc(str(prediction["created_at"]))
    updated_at = parse_utc(str(prediction["updated_at"]))
    documents: list[SearchDocument] = []

    def add(
        source_kind: SearchSourceKind,
        source_record_id: int,
        text: object,
        *,
        source_version_id: int | None = None,
        source_sequence: int | None = None,
        occurred_at=created_at,
        is_superseded: bool = False,
    ) -> None:
        if text is None:
            return
        body = str(text)
        if not body:
            return
        documents.append(
            SearchDocument(
                prediction_id=prediction_id,
                source_kind=source_kind,
                source_record_id=source_record_id,
                source_version_id=source_version_id,
                source_sequence=source_sequence,
                occurred_at=occurred_at,
                is_superseded=is_superseded,
                text=body,
            )
        )

    add(SearchSourceKind.QUESTION, prediction_id, prediction["question"])
    add(
        SearchSourceKind.BACKGROUND,
        prediction_id,
        prediction["background"],
        occurred_at=updated_at,
    )
    add(
        SearchSourceKind.RESOLUTION_CRITERIA,
        prediction_id,
        prediction["resolution_criteria"],
        occurred_at=updated_at,
    )

    for row in connection.execute(
        """
        SELECT tag.id, tag.display_name
        FROM tags AS tag
        JOIN prediction_tags AS link ON link.tag_id = tag.id
        WHERE link.prediction_id = ?
        ORDER BY tag.normalized_name, tag.id
        """,
        (prediction_id,),
    ).fetchall():
        add(SearchSourceKind.TAG, int(row["id"]), row["display_name"])

    for table in ("forecast_revisions", "numeric_forecast_revisions"):
        for row in connection.execute(
            f"""
            SELECT id, sequence, created_at, rationale
            FROM {table}
            WHERE prediction_id = ? AND rationale IS NOT NULL
            ORDER BY sequence
            """,
            (prediction_id,),
        ).fetchall():
            add(
                SearchSourceKind.FORECAST_RATIONALE,
                int(row["id"]),
                row["rationale"],
                source_sequence=int(row["sequence"]),
                occurred_at=parse_utc(str(row["created_at"])),
            )

    for row in connection.execute(
        """
        SELECT
            review.id, review.created_at, review.note,
            COALESCE(binary_revision.sequence, numeric_revision.sequence) AS sequence
        FROM forecast_reviews AS review
        LEFT JOIN forecast_revisions AS binary_revision
            ON binary_revision.id = review.forecast_revision_id
            AND binary_revision.prediction_id = review.prediction_id
        LEFT JOIN numeric_forecast_revisions AS numeric_revision
            ON numeric_revision.id = review.numeric_forecast_revision_id
            AND numeric_revision.prediction_id = review.prediction_id
        WHERE review.prediction_id = ? AND review.note IS NOT NULL
        ORDER BY review.id
        """,
        (prediction_id,),
    ).fetchall():
        add(
            SearchSourceKind.FORECAST_REVIEW,
            int(row["id"]),
            row["note"],
            source_sequence=int(row["sequence"]),
            occurred_at=parse_utc(str(row["created_at"])),
        )

    _append_journal_documents(connection, prediction_id, add)
    _append_definition_history_documents(connection, prediction_id, prediction, add)
    _append_resolution_documents(connection, prediction_id, add)
    _append_invalidation_documents(connection, prediction_id, add)

    return tuple(documents)


def _append_journal_documents(connection, prediction_id: int, add) -> None:
    rows = connection.execute(
        """
        SELECT
            entry.id, entry.body, entry.created_at,
            COALESCE(binary_revision.sequence, numeric_revision.sequence) AS sequence
        FROM journal_entries AS entry
        LEFT JOIN forecast_revisions AS binary_revision
            ON binary_revision.id = entry.forecast_revision_id
            AND binary_revision.prediction_id = entry.prediction_id
        LEFT JOIN numeric_forecast_revisions AS numeric_revision
            ON numeric_revision.id = entry.numeric_forecast_revision_id
            AND numeric_revision.prediction_id = entry.prediction_id
        WHERE entry.prediction_id = ?
        ORDER BY entry.id
        """,
        (prediction_id,),
    ).fetchall()
    for row in rows:
        entry_id = int(row["id"])
        created_at = parse_utc(str(row["created_at"]))
        versions: list[tuple[int | None, str]] = [(None, str(row["body"]))]
        for correction in connection.execute(
            """
            SELECT id, body
            FROM journal_entry_corrections
            WHERE journal_entry_id = ?
            ORDER BY sequence
            """,
            (entry_id,),
        ).fetchall():
            versions.append((int(correction["id"]), str(correction["body"])))
        current_version_id, current_text = versions[-1]
        add(
            SearchSourceKind.JOURNAL,
            entry_id,
            current_text,
            source_version_id=current_version_id,
            source_sequence=int(row["sequence"]),
            occurred_at=created_at,
        )
        _append_unique_superseded_versions(
            add,
            SearchSourceKind.JOURNAL,
            entry_id,
            versions[:-1],
            current_text=current_text,
            source_sequence=int(row["sequence"]),
            occurred_at=created_at,
        )


def _append_definition_history_documents(
    connection,
    prediction_id: int,
    prediction,
    add,
) -> None:
    rows = connection.execute(
        """
        SELECT
            id, changed_at, old_question, new_question,
            old_resolution_criteria, new_resolution_criteria
        FROM prediction_definition_changes
        WHERE prediction_id = ?
        ORDER BY id
        """,
        (prediction_id,),
    ).fetchall()
    current_question = str(prediction["question"])
    current_criteria = (
        None
        if prediction["resolution_criteria"] is None
        else str(prediction["resolution_criteria"])
    )
    _append_unique_snapshot_values(
        add,
        SearchSourceKind.QUESTION,
        rows,
        ("old_question", "new_question"),
        current_question,
    )
    _append_unique_snapshot_values(
        add,
        SearchSourceKind.RESOLUTION_CRITERIA,
        rows,
        ("old_resolution_criteria", "new_resolution_criteria"),
        current_criteria,
    )


def _append_resolution_documents(connection, prediction_id: int, add) -> None:
    for resolution_table, correction_table, actual_flag in (
        ("resolutions", "resolution_corrections", "outcome_changed"),
        (
            "numeric_resolutions",
            "numeric_resolution_corrections",
            "actual_value_changed",
        ),
    ):
        resolution = connection.execute(
            f"""
            SELECT id, resolved_at, resolution_notes, postmortem
            FROM {resolution_table}
            WHERE prediction_id = ?
            """,
            (prediction_id,),
        ).fetchone()
        if resolution is None:
            continue
        resolution_id = int(resolution["id"])
        parent_column = (
            "resolution_id"
            if correction_table == "resolution_corrections"
            else "numeric_resolution_id"
        )
        corrections = connection.execute(
            f"""
            SELECT
                id, sequence, new_resolution_notes, new_postmortem,
                correction_reason, corrected_at, {actual_flag} AS outcome_changed
            FROM {correction_table}
            WHERE {parent_column} = ?
            ORDER BY sequence
            """,
            (resolution_id,),
        ).fetchall()
        versions: list[tuple[int | None, int, object, object, object]] = [
            (
                None,
                0,
                resolution["resolution_notes"],
                resolution["postmortem"],
                resolution["resolved_at"],
            )
        ]
        for correction in corrections:
            versions.append(
                (
                    int(correction["id"]),
                    int(correction["sequence"]),
                    correction["new_resolution_notes"],
                    correction["new_postmortem"],
                    correction["corrected_at"],
                )
            )
            if bool(correction["outcome_changed"]):
                add(
                    SearchSourceKind.OUTCOME_CORRECTION_REASON,
                    int(correction["id"]),
                    correction["correction_reason"],
                    source_sequence=int(correction["sequence"]),
                    occurred_at=parse_utc(str(correction["corrected_at"])),
                )
        _append_terminal_field_versions(
            add,
            SearchSourceKind.RESOLUTION_NOTES,
            resolution_id,
            versions,
            value_index=2,
        )
        _append_terminal_field_versions(
            add,
            SearchSourceKind.POSTMORTEM,
            resolution_id,
            versions,
            value_index=3,
        )


def _append_invalidation_documents(connection, prediction_id: int, add) -> None:
    invalidation = connection.execute(
        """
        SELECT id, invalidated_at, reason
        FROM prediction_invalidations
        WHERE prediction_id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if invalidation is None:
        return
    invalidation_id = int(invalidation["id"])
    versions: list[tuple[int | None, int, object, object]] = [
        (None, 0, invalidation["reason"], invalidation["invalidated_at"])
    ]
    for correction in connection.execute(
        """
        SELECT id, sequence, new_reason, corrected_at
        FROM invalidation_reason_corrections
        WHERE invalidation_id = ?
        ORDER BY sequence
        """,
        (invalidation_id,),
    ).fetchall():
        versions.append(
            (
                int(correction["id"]),
                int(correction["sequence"]),
                correction["new_reason"],
                correction["corrected_at"],
            )
        )
    current_version_id, current_sequence, current_value, current_time = versions[-1]
    add(
        SearchSourceKind.INVALIDATION_REASON,
        invalidation_id,
        current_value,
        source_version_id=current_version_id,
        source_sequence=current_sequence,
        occurred_at=parse_utc(str(current_time)),
    )
    seen = {
        normalize_search_literal(str(current_value))
        if current_value is not None
        else ""
    }
    for version_id, sequence, value, occurred_at in versions[:-1]:
        if value is None:
            continue
        normalized = normalize_search_literal(str(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        add(
            SearchSourceKind.INVALIDATION_REASON,
            invalidation_id,
            value,
            source_version_id=version_id,
            source_sequence=sequence,
            occurred_at=parse_utc(str(occurred_at)),
            is_superseded=True,
        )


def _append_terminal_field_versions(
    add,
    source_kind: SearchSourceKind,
    source_record_id: int,
    versions: list[tuple[int | None, int, object, object, object]],
    *,
    value_index: int,
) -> None:
    current = versions[-1]
    current_value = current[value_index]
    add(
        source_kind,
        source_record_id,
        current_value,
        source_version_id=current[0],
        source_sequence=current[1],
        occurred_at=parse_utc(str(current[4])),
    )
    seen = {
        normalize_search_literal(str(current_value))
        if current_value is not None
        else ""
    }
    for version in versions[:-1]:
        value = version[value_index]
        if value is None:
            continue
        normalized = normalize_search_literal(str(value))
        if normalized in seen:
            continue
        seen.add(normalized)
        add(
            source_kind,
            source_record_id,
            value,
            source_version_id=version[0],
            source_sequence=version[1],
            occurred_at=parse_utc(str(version[4])),
            is_superseded=True,
        )


def _append_unique_superseded_versions(
    add,
    source_kind: SearchSourceKind,
    source_record_id: int,
    versions: Iterable[tuple[int | None, str]],
    *,
    current_text: str,
    source_sequence: int,
    occurred_at,
) -> None:
    seen = {normalize_search_literal(current_text)}
    for version_id, text in versions:
        normalized = normalize_search_literal(text)
        if normalized in seen:
            continue
        seen.add(normalized)
        add(
            source_kind,
            source_record_id,
            text,
            source_version_id=version_id,
            source_sequence=source_sequence,
            occurred_at=occurred_at,
            is_superseded=True,
        )


def _append_unique_snapshot_values(
    add,
    source_kind: SearchSourceKind,
    rows,
    field_names: tuple[str, str],
    current_value: str | None,
) -> None:
    seen = {
        normalize_search_literal(current_value) if current_value is not None else ""
    }
    for row in rows:
        for field_name in field_names:
            value = row[field_name]
            if value is None:
                continue
            normalized = normalize_search_literal(str(value))
            if normalized in seen:
                continue
            seen.add(normalized)
            add(
                source_kind,
                int(row["id"]),
                value,
                source_sequence=int(row["id"]),
                occurred_at=parse_utc(str(row["changed_at"])),
                is_superseded=True,
            )


def _replace_prediction_documents(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> None:
    connection.execute(
        "DELETE FROM prediction_search WHERE prediction_id = ?",
        (prediction_id,),
    )
    _insert_documents(
        connection,
        project_prediction_documents(connection, prediction_id),
    )


def _insert_documents(
    connection: sqlite3.Connection,
    documents: Iterable[SearchDocument],
) -> None:
    connection.executemany(
        """
        INSERT INTO prediction_search (
            prediction_id, source_kind, source_record_id,
            source_version_id, source_sequence, occurred_at,
            is_superseded, body
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                document.prediction_id,
                document.source_kind.value,
                document.source_record_id,
                document.source_version_id,
                document.source_sequence,
                None
                if document.occurred_at is None
                else format_utc(document.occurred_at),
                int(document.is_superseded),
                document.text,
            )
            for document in documents
        ),
    )


def _document_comparison_key(document: SearchDocument) -> tuple[object, ...]:
    return (
        document.prediction_id,
        document.source_kind.value,
        document.source_record_id,
        document.source_version_id,
        document.source_sequence,
        None if document.occurred_at is None else format_utc(document.occurred_at),
        document.is_superseded,
        document.text,
    )


def _comparison_sort_key(value: tuple[object, ...]) -> tuple[str, ...]:
    return tuple("" if item is None else str(item) for item in value)


def _search_object_names(connection: sqlite3.Connection) -> set[str]:
    names = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE name IN (
            'search_index_state',
            'search_dirty_predictions',
            'prediction_search',
            'prediction_search_vocabulary'
        )
        """
    ).fetchall()
    return {str(row[0]) for row in names}


def _require_complete_search_schema(object_names: set[str]) -> None:
    required = {
        "search_index_state",
        "search_dirty_predictions",
        "prediction_search",
        "prediction_search_vocabulary",
    }
    if object_names != required:
        raise SearchIndexRepairRequiredError(
            "The local search schema is incomplete and requires repair."
        )


def _search_document_count(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute("SELECT COUNT(*) FROM prediction_search").fetchone()[0]
    )


def _require_recorded_document_count(connection: sqlite3.Connection) -> None:
    state = connection.execute(
        """
        SELECT projection_version, document_count
        FROM search_index_state
        WHERE singleton_id = 1
        """
    ).fetchone()
    if (
        state is None
        or int(state[0]) != SEARCH_PROJECTION_VERSION
        or int(state[1]) != _search_document_count(connection)
    ):
        raise SearchIndexRepairRequiredError(
            "The local search index is inconsistent and requires repair."
        )


def _record_document_count(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE search_index_state
        SET document_count = ?
        WHERE singleton_id = 1 AND projection_version = ?
        """,
        (_search_document_count(connection), SEARCH_PROJECTION_VERSION),
    )
    if connection.execute("SELECT changes()").fetchone()[0] != 1:
        raise SearchIndexRepairRequiredError(
            "The search projection version record is missing or incompatible."
        )
