"""Transactional SQLite operations for global tag-library maintenance."""

import sqlite3
from datetime import datetime

from reckonsolve.clock import format_utc
from reckonsolve.domain.tags import (
    TagDeletePreview,
    TagLibraryItem,
    TagManagementContext,
    TagMergePreview,
    TagRenamePreview,
)

from .database import Database


class TagNotFoundError(RuntimeError):
    """A selected stable tag identity no longer exists."""


class DuplicateTagNameError(RuntimeError):
    """A proposed normalized name belongs to another retained tag."""


class TagRenameUnchangedError(RuntimeError):
    """A proposed rename changes neither display text nor identity."""


class TagMergeSelectionError(RuntimeError):
    """A merge does not contain distinct source and target identities."""


class TagLibraryContextChangedError(RuntimeError):
    """Tag relationships changed after the confirmation context was loaded."""


class TagRepository:
    """Read and mutate the retained tag library behind one explicit boundary."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def list_tags(self) -> tuple[TagLibraryItem, ...]:
        """List retained tags, including tags with no current relationships."""

        with self._database.transaction() as connection:
            return _list_tags(connection)

    def preview_rename(
        self,
        tag_id: int,
        proposed_display_name: str,
        proposed_normalized_name: str,
    ) -> TagRenamePreview:
        """Return a side-effect-free transaction-current rename preview."""

        with self._database.transaction() as connection:
            return _preview_rename(
                connection,
                tag_id,
                proposed_display_name,
                proposed_normalized_name,
            )

    def rename_tag(self, preview: TagRenamePreview, changed_at: datetime) -> None:
        """Retain identity while changing one label and affected metadata contexts."""

        with self._database.transaction() as connection:
            current = _preview_rename(
                connection,
                preview.context.item.tag_id,
                preview.proposed_display_name,
                preview.proposed_normalized_name,
            )
            if current != preview:
                raise TagLibraryContextChangedError
            connection.execute(
                """
                UPDATE tags
                SET display_name = ?, normalized_name = ?
                WHERE id = ?
                """,
                (
                    preview.proposed_display_name,
                    preview.proposed_normalized_name,
                    preview.context.item.tag_id,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise TagLibraryContextChangedError
            _advance_prediction_metadata(
                connection,
                preview.context.prediction_ids,
                changed_at,
            )

    def preview_merge(
        self,
        source_tag_ids: tuple[int, ...],
        target_tag_id: int,
    ) -> TagMergePreview:
        """Return a side-effect-free transaction-current many-to-one preview."""

        with self._database.transaction() as connection:
            return _preview_merge(connection, source_tag_ids, target_tag_id)

    def merge_tags(self, preview: TagMergePreview, changed_at: datetime) -> None:
        """Union and deduplicate all source relationships into the target."""

        source_ids = tuple(context.item.tag_id for context in preview.source_contexts)
        with self._database.transaction() as connection:
            current = _preview_merge(
                connection,
                source_ids,
                preview.target_context.item.tag_id,
            )
            if current != preview:
                raise TagLibraryContextChangedError
            target_id = preview.target_context.item.tag_id
            placeholders = _placeholders(source_ids)
            connection.execute(
                f"""
                INSERT OR IGNORE INTO prediction_tags (prediction_id, tag_id)
                SELECT prediction_id, ?
                FROM prediction_tags
                WHERE tag_id IN ({placeholders})
                """,
                (target_id, *source_ids),
            )
            connection.execute(
                f"""
                INSERT OR IGNORE INTO saved_view_tags (saved_view_id, tag_id)
                SELECT saved_view_id, ?
                FROM saved_view_tags
                WHERE tag_id IN ({placeholders})
                """,
                (target_id, *source_ids),
            )
            connection.execute(
                f"DELETE FROM prediction_tags WHERE tag_id IN ({placeholders})",
                source_ids,
            )
            connection.execute(
                f"DELETE FROM saved_view_tags WHERE tag_id IN ({placeholders})",
                source_ids,
            )
            connection.execute(
                f"DELETE FROM tags WHERE id IN ({placeholders})",
                source_ids,
            )
            if connection.execute("SELECT changes()").fetchone()[0] != len(source_ids):
                raise TagLibraryContextChangedError
            _advance_prediction_metadata(
                connection,
                preview.affected_prediction_ids,
                changed_at,
            )

    def preview_delete(self, tag_id: int) -> TagDeletePreview:
        """Return every relationship that one deletion will remove."""

        with self._database.transaction() as connection:
            return _preview_delete(connection, tag_id)

    def delete_tag(self, preview: TagDeletePreview, changed_at: datetime) -> None:
        """Remove one retained tag and all current relationships atomically."""

        with self._database.transaction() as connection:
            current = _preview_delete(connection, preview.tag.tag_id)
            if current != preview:
                raise TagLibraryContextChangedError
            connection.execute(
                "DELETE FROM prediction_tags WHERE tag_id = ?",
                (preview.tag.tag_id,),
            )
            connection.execute(
                "DELETE FROM saved_view_tags WHERE tag_id = ?",
                (preview.tag.tag_id,),
            )
            connection.execute("DELETE FROM tags WHERE id = ?", (preview.tag.tag_id,))
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise TagLibraryContextChangedError
            _advance_prediction_metadata(
                connection,
                preview.context.prediction_ids,
                changed_at,
            )


def _list_tags(connection: sqlite3.Connection) -> tuple[TagLibraryItem, ...]:
    rows = connection.execute(
        """
        SELECT
            tag.id,
            tag.display_name,
            tag.normalized_name,
            (SELECT COUNT(*) FROM prediction_tags
             WHERE prediction_tags.tag_id = tag.id) AS prediction_count,
            (SELECT COUNT(*) FROM saved_view_tags
             WHERE saved_view_tags.tag_id = tag.id) AS saved_view_count
        FROM tags AS tag
        ORDER BY tag.normalized_name, tag.id
        """
    ).fetchall()
    return tuple(_map_tag(row) for row in rows)


def _load_context(
    connection: sqlite3.Connection,
    tag_id: int,
) -> TagManagementContext:
    row = connection.execute(
        """
        SELECT id, display_name, normalized_name
        FROM tags
        WHERE id = ?
        """,
        (tag_id,),
    ).fetchone()
    if row is None:
        raise TagNotFoundError
    prediction_ids = tuple(
        int(candidate[0])
        for candidate in connection.execute(
            """
            SELECT prediction_id
            FROM prediction_tags
            WHERE tag_id = ?
            ORDER BY prediction_id
            """,
            (tag_id,),
        ).fetchall()
    )
    saved_view_ids = tuple(
        int(candidate[0])
        for candidate in connection.execute(
            """
            SELECT saved_view_id
            FROM saved_view_tags
            WHERE tag_id = ?
            ORDER BY saved_view_id
            """,
            (tag_id,),
        ).fetchall()
    )
    return TagManagementContext(
        item=TagLibraryItem(
            tag_id=int(row["id"]),
            display_name=str(row["display_name"]),
            normalized_name=str(row["normalized_name"]),
            prediction_count=len(prediction_ids),
            saved_view_count=len(saved_view_ids),
        ),
        prediction_ids=prediction_ids,
        saved_view_ids=saved_view_ids,
    )


def _preview_rename(
    connection: sqlite3.Connection,
    tag_id: int,
    proposed_display_name: str,
    proposed_normalized_name: str,
) -> TagRenamePreview:
    context = _load_context(connection, tag_id)
    if context.item.display_name == proposed_display_name:
        raise TagRenameUnchangedError
    collision = connection.execute(
        "SELECT id FROM tags WHERE normalized_name = ? AND id <> ?",
        (proposed_normalized_name, tag_id),
    ).fetchone()
    if collision is not None:
        raise DuplicateTagNameError
    return TagRenamePreview(
        context=context,
        proposed_display_name=proposed_display_name,
        proposed_normalized_name=proposed_normalized_name,
    )


def _preview_merge(
    connection: sqlite3.Connection,
    source_tag_ids: tuple[int, ...],
    target_tag_id: int,
) -> TagMergePreview:
    if (
        not source_tag_ids
        or len(set(source_tag_ids)) != len(source_tag_ids)
        or target_tag_id in source_tag_ids
    ):
        raise TagMergeSelectionError
    source_contexts = tuple(
        _load_context(connection, tag_id) for tag_id in sorted(source_tag_ids)
    )
    target_context = _load_context(connection, target_tag_id)
    affected_prediction_ids = tuple(
        sorted(
            {
                prediction_id
                for context in source_contexts
                for prediction_id in context.prediction_ids
            }
        )
    )
    affected_saved_view_ids = tuple(
        sorted(
            {
                saved_view_id
                for context in source_contexts
                for saved_view_id in context.saved_view_ids
            }
        )
    )
    return TagMergePreview(
        source_contexts=source_contexts,
        target_context=target_context,
        affected_prediction_ids=affected_prediction_ids,
        affected_saved_view_ids=affected_saved_view_ids,
    )


def _preview_delete(
    connection: sqlite3.Connection,
    tag_id: int,
) -> TagDeletePreview:
    return TagDeletePreview(_load_context(connection, tag_id))


def _advance_prediction_metadata(
    connection: sqlite3.Connection,
    prediction_ids: tuple[int, ...],
    changed_at: datetime,
) -> None:
    if not prediction_ids:
        return
    placeholders = _placeholders(prediction_ids)
    connection.execute(
        f"""
        UPDATE predictions
        SET updated_at = ?, metadata_version = metadata_version + 1
        WHERE id IN ({placeholders})
        """,
        (format_utc(changed_at), *prediction_ids),
    )
    if connection.execute("SELECT changes()").fetchone()[0] != len(prediction_ids):
        raise TagLibraryContextChangedError


def _map_tag(row: sqlite3.Row) -> TagLibraryItem:
    return TagLibraryItem(
        tag_id=int(row["id"]),
        display_name=str(row["display_name"]),
        normalized_name=str(row["normalized_name"]),
        prediction_count=int(row["prediction_count"]),
        saved_view_count=int(row["saved_view_count"]),
    )


def _placeholders(values: tuple[int, ...]) -> str:
    if not values:
        raise ValueError("At least one stable identifier is required.")
    return ", ".join("?" for _value in values)
