"""SQLite persistence for mutable dynamic Saved Views."""

import sqlite3
from collections import defaultdict
from datetime import date

from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveQuery,
    ArchiveSort,
    ArchiveTagMatchMode,
)
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.saved_views import (
    SavedView,
    SavedViewConfiguration,
    SavedViewTag,
)
from reckonsolve.domain.search import SearchMatchMode

from .database import Database


class SavedViewNotFoundError(RuntimeError):
    """The requested mutable Saved View no longer exists."""


class DuplicateSavedViewNameError(RuntimeError):
    """A normalized Saved View name already belongs to another row."""


class SavedViewRepository:
    """Persist configurations and stable tag references without result membership."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def list_saved_views(self) -> tuple[SavedView, ...]:
        """Return every view with current tag labels in deterministic name order."""

        with self._database.transaction() as connection:
            return _load_saved_views(connection)

    def create_saved_view(
        self,
        name: str,
        normalized_name: str,
        configuration: SavedViewConfiguration,
    ) -> SavedView:
        """Save a new named configuration and stable tag references atomically."""

        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO saved_views (
                        display_name, normalized_name, search_text, match_mode,
                        include_superseded, status, prediction_type, tag_match_mode,
                        attention, date_meaning, date_start, date_end, sort
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _saved_view_values(name, normalized_name, configuration),
                )
                saved_view_id = int(cursor.lastrowid)
                _insert_tag_references(
                    connection,
                    saved_view_id,
                    _tag_ids_for_names(connection, configuration.archive_query.tags),
                )
                view = _load_saved_view(connection, saved_view_id)
        except sqlite3.IntegrityError as error:
            if "saved_views.normalized_name" in str(error):
                raise DuplicateSavedViewNameError from error
            raise
        if view is None:
            raise sqlite3.DatabaseError("The new Saved View could not be loaded.")
        return view

    def update_saved_view(
        self,
        saved_view_id: int,
        configuration: SavedViewConfiguration,
    ) -> SavedView:
        """Replace one view's dynamic configuration without changing its identity."""

        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE saved_views
                SET search_text = ?, match_mode = ?, include_superseded = ?,
                    status = ?, prediction_type = ?, tag_match_mode = ?,
                    attention = ?, date_meaning = ?, date_start = ?, date_end = ?,
                    sort = ?
                WHERE id = ?
                """,
                (*_saved_view_values("", "", configuration)[2:], saved_view_id),
            )
            if cursor.rowcount != 1:
                raise SavedViewNotFoundError
            connection.execute(
                "DELETE FROM saved_view_tags WHERE saved_view_id = ?",
                (saved_view_id,),
            )
            _insert_tag_references(
                connection,
                saved_view_id,
                _tag_ids_for_names(connection, configuration.archive_query.tags),
            )
            view = _load_saved_view(connection, saved_view_id)
        if view is None:
            raise sqlite3.DatabaseError("The updated Saved View could not be loaded.")
        return view

    def rename_saved_view(
        self,
        saved_view_id: int,
        name: str,
        normalized_name: str,
    ) -> SavedView:
        """Change display spelling and case-insensitive identity explicitly."""

        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    """
                    UPDATE saved_views
                    SET display_name = ?, normalized_name = ?
                    WHERE id = ?
                    """,
                    (name, normalized_name, saved_view_id),
                )
                if cursor.rowcount != 1:
                    raise SavedViewNotFoundError
                view = _load_saved_view(connection, saved_view_id)
        except sqlite3.IntegrityError as error:
            if "saved_views.normalized_name" in str(error):
                raise DuplicateSavedViewNameError from error
            raise
        if view is None:
            raise sqlite3.DatabaseError("The renamed Saved View could not be loaded.")
        return view

    def delete_saved_view(self, saved_view_id: int) -> None:
        """Delete only this mutable preference and its tag references."""

        with self._database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM saved_views WHERE id = ?", (saved_view_id,)
            )
            if cursor.rowcount != 1:
                raise SavedViewNotFoundError


def _saved_view_values(
    name: str,
    normalized_name: str,
    configuration: SavedViewConfiguration,
) -> tuple[object, ...]:
    query = configuration.archive_query
    return (
        name,
        normalized_name,
        configuration.search_text,
        configuration.match_mode.value,
        int(configuration.include_superseded),
        None if query.status is None else query.status.value,
        None if query.prediction_type is None else query.prediction_type.value,
        query.tag_match_mode.value,
        None if query.attention is None else query.attention.value,
        query.date_meaning.value,
        None if query.date_start is None else query.date_start.isoformat(),
        None if query.date_end is None else query.date_end.isoformat(),
        query.sort.value,
    )


def _insert_tag_references(
    connection: sqlite3.Connection,
    saved_view_id: int,
    tag_ids: tuple[int, ...],
) -> None:
    if not tag_ids:
        return
    connection.executemany(
        """
        INSERT INTO saved_view_tags (saved_view_id, tag_id)
        VALUES (?, ?)
        """,
        ((saved_view_id, tag_id) for tag_id in tag_ids),
    )


def _tag_ids_for_names(
    connection: sqlite3.Connection,
    tag_names: tuple[str, ...],
) -> tuple[int, ...]:
    wanted = {name.strip().casefold() for name in tag_names if name.strip()}
    if not wanted:
        return ()
    rows = connection.execute(
        """
        SELECT id, normalized_name
        FROM tags
        ORDER BY id
        """
    ).fetchall()
    identifiers_by_name = {
        str(row["normalized_name"]): int(row["id"])
        for row in rows
        if str(row["normalized_name"]) in wanted
    }
    missing = wanted - identifiers_by_name.keys()
    if missing:
        raise sqlite3.IntegrityError("A selected Saved View tag no longer exists.")
    return tuple(identifiers_by_name[name] for name in sorted(wanted))


def _load_saved_views(connection: sqlite3.Connection) -> tuple[SavedView, ...]:
    rows = connection.execute(
        """
        SELECT id, display_name, normalized_name, search_text, match_mode,
               include_superseded, status, prediction_type, tag_match_mode,
               attention, date_meaning, date_start, date_end, sort
        FROM saved_views
        ORDER BY normalized_name, id
        """
    ).fetchall()
    tags_by_view = _saved_view_tags(connection)
    return tuple(
        _map_saved_view(row, tags_by_view.get(int(row["id"]), ())) for row in rows
    )


def _load_saved_view(
    connection: sqlite3.Connection,
    saved_view_id: int,
) -> SavedView | None:
    rows = _load_saved_views(connection)
    return next((view for view in rows if view.saved_view_id == saved_view_id), None)


def _saved_view_tags(
    connection: sqlite3.Connection,
) -> dict[int, tuple[SavedViewTag, ...]]:
    grouped: dict[int, list[SavedViewTag]] = defaultdict(list)
    rows = connection.execute(
        """
        SELECT reference.saved_view_id, tag.id AS tag_id, tag.display_name
        FROM saved_view_tags AS reference
        JOIN tags AS tag ON tag.id = reference.tag_id
        ORDER BY reference.saved_view_id, tag.normalized_name, tag.id
        """
    ).fetchall()
    for row in rows:
        grouped[int(row["saved_view_id"])].append(
            SavedViewTag(int(row["tag_id"]), str(row["display_name"]))
        )
    return {saved_view_id: tuple(tags) for saved_view_id, tags in grouped.items()}


def _map_saved_view(row, tags: tuple[SavedViewTag, ...]) -> SavedView:
    query = ArchiveQuery(
        status=(
            None if row["status"] is None else PredictionStatus(str(row["status"]))
        ),
        prediction_type=(
            None
            if row["prediction_type"] is None
            else PredictionType(str(row["prediction_type"]))
        ),
        tags=tuple(tag.display_name for tag in tags),
        tag_match_mode=ArchiveTagMatchMode(str(row["tag_match_mode"])),
        attention=(
            None
            if row["attention"] is None
            else ArchiveAttention(str(row["attention"]))
        ),
        date_meaning=ArchiveDateMeaning(str(row["date_meaning"])),
        date_start=(
            None
            if row["date_start"] is None
            else date.fromisoformat(str(row["date_start"]))
        ),
        date_end=(
            None
            if row["date_end"] is None
            else date.fromisoformat(str(row["date_end"]))
        ),
        sort=ArchiveSort(str(row["sort"])),
    )
    return SavedView(
        saved_view_id=int(row["id"]),
        name=str(row["display_name"]),
        normalized_name=str(row["normalized_name"]),
        configuration=SavedViewConfiguration(
            search_text=str(row["search_text"]),
            match_mode=SearchMatchMode(str(row["match_mode"])),
            include_superseded=bool(int(row["include_superseded"])),
            archive_query=query,
        ),
        tags=tags,
    )
