"""Purpose-specific SQLite access for binary predictions."""

import sqlite3
from datetime import date, datetime

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.predictions import (
    DefinitionChange,
    ForecastRevision,
    NewForecastRevision,
    NewPrediction,
    PredictionDetail,
    PredictionMetadataUpdate,
    PredictionStatus,
    changed_definition_fields,
    display_status,
    metadata_would_change,
)

from .database import Database


class PredictionChangedError(RuntimeError):
    """Raised when metadata changed after the application reviewed it."""


class ForecastContextChangedError(RuntimeError):
    """Raised when a revision form no longer matches current prediction state."""


class ForecastRevisionUnchangedError(RuntimeError):
    """Raised when a normal revision repeats the current probability."""


class ForecastRevisionDisallowedError(RuntimeError):
    """Raised when lifecycle state rejects a normal forecast revision."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(status.value)
        self.status = status


class PredictionRepository:
    """Persist and query predictions without exposing table-level CRUD."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_prediction(
        self,
        new_prediction: NewPrediction,
        created_at: datetime,
    ) -> PredictionDetail:
        """Insert a prediction and sequence-one revision in one transaction."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            prediction_cursor = connection.execute(
                """
                INSERT INTO predictions (
                    question,
                    prediction_type,
                    status,
                    created_at,
                    updated_at,
                    background,
                    resolution_criteria,
                    forecast_deadline,
                    expected_resolution
                )
                VALUES (?, 'binary', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_prediction.question,
                    PredictionStatus.OPEN.value,
                    timestamp,
                    timestamp,
                    new_prediction.background,
                    new_prediction.resolution_criteria,
                    _format_date(new_prediction.forecast_deadline),
                    _format_date(new_prediction.expected_resolution),
                ),
            )
            prediction_id = prediction_cursor.lastrowid
            if prediction_id is None:
                raise sqlite3.DatabaseError("SQLite did not return a prediction ID.")

            _replace_tags(connection, prediction_id, new_prediction.tags)
            connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id,
                    probability_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    prediction_id,
                    new_prediction.probability_percent,
                    timestamp,
                    new_prediction.rationale,
                ),
            )
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                raise sqlite3.DatabaseError(
                    "The created prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                row,
                _select_tags(connection, prediction_id),
            )

        return detail

    def append_forecast_revision(
        self,
        prediction_id: int,
        new_revision: NewForecastRevision,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        created_at: datetime,
        current_date: date,
    ) -> PredictionDetail | None:
        """Recheck reviewed state and append exactly one immutable revision."""

        timestamp = format_utc(created_at)
        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                _select_tags(connection, prediction_id),
            )
            if (
                current.current_revision_id != expected_revision_id
                or current.metadata_version != expected_metadata_version
            ):
                raise ForecastContextChangedError

            effective_status = display_status(
                current.status,
                current.forecast_deadline,
                current_date,
            )
            if effective_status is not PredictionStatus.OPEN:
                raise ForecastRevisionDisallowedError(effective_status)
            if current.probability_percent == new_revision.probability_percent:
                raise ForecastRevisionUnchangedError

            revision_cursor = connection.execute(
                """
                INSERT INTO forecast_revisions (
                    prediction_id,
                    probability_percent,
                    created_at,
                    sequence,
                    rationale
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    new_revision.probability_percent,
                    timestamp,
                    current.current_revision_sequence + 1,
                    new_revision.rationale,
                ),
            )
            if revision_cursor.lastrowid is None:
                raise sqlite3.DatabaseError("SQLite did not return a revision ID.")

            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The revised prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                updated_row,
                _select_tags(connection, prediction_id),
            )

        return detail

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[ForecastRevision, ...] | None:
        """Load immutable forecast revisions in sequence order."""

        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                """
                SELECT
                    id,
                    prediction_id,
                    probability_percent,
                    sequence,
                    created_at,
                    rationale
                FROM forecast_revisions
                WHERE prediction_id = ?
                ORDER BY sequence
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_forecast_revision(row) for row in rows)

    def get_latest_prediction(self) -> PredictionDetail | None:
        """Load the newest prediction and derive its current revision."""

        with self._database.transaction() as connection:
            row = connection.execute(
                f"""
                {_PREDICTION_DETAIL_SELECT}
                ORDER BY prediction.created_at DESC, prediction.id DESC
                LIMIT 1
                """
            ).fetchone()
            detail = (
                None
                if row is None
                else _map_prediction_detail(
                    row,
                    _select_tags(connection, int(row["prediction_id"])),
                )
            )

        return detail

    def get_prediction(self, prediction_id: int) -> PredictionDetail | None:
        """Load one prediction and derive its current revision."""

        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            detail = (
                None
                if row is None
                else _map_prediction_detail(
                    row,
                    _select_tags(connection, prediction_id),
                )
            )

        return detail

    def update_metadata(
        self,
        prediction_id: int,
        update: PredictionMetadataUpdate,
        *,
        expected: PredictionDetail,
        expected_metadata_version: int,
        changed_at: datetime,
    ) -> PredictionDetail | None:
        """Replace metadata and append any definition record atomically."""

        timestamp = format_utc(changed_at)
        with self._database.transaction() as connection:
            row = _select_prediction_detail(connection, prediction_id)
            if row is None:
                return None
            current = _map_prediction_detail(
                row,
                _select_tags(connection, prediction_id),
            )
            if (
                current.metadata_version != expected_metadata_version
                or not _same_editable_metadata(current, expected)
            ):
                raise PredictionChangedError
            if not metadata_would_change(current, update):
                return current

            definition_fields = changed_definition_fields(current, update)
            connection.execute(
                """
                UPDATE predictions
                SET
                    question = ?,
                    background = ?,
                    resolution_criteria = ?,
                    forecast_deadline = ?,
                    expected_resolution = ?,
                    updated_at = ?,
                    metadata_version = metadata_version + 1
                WHERE id = ? AND metadata_version = ?
                """,
                (
                    update.question,
                    update.background,
                    update.resolution_criteria,
                    _format_date(update.forecast_deadline),
                    _format_date(update.expected_resolution),
                    timestamp,
                    prediction_id,
                    expected_metadata_version,
                ),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise PredictionChangedError
            _replace_tags(connection, prediction_id, update.tags)
            if definition_fields:
                connection.execute(
                    """
                    INSERT INTO prediction_definition_changes (
                        prediction_id,
                        changed_at,
                        old_question,
                        new_question,
                        old_resolution_criteria,
                        new_resolution_criteria,
                        old_forecast_deadline,
                        new_forecast_deadline
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prediction_id,
                        timestamp,
                        current.question,
                        update.question,
                        current.resolution_criteria,
                        update.resolution_criteria,
                        _format_date(current.forecast_deadline),
                        _format_date(update.forecast_deadline),
                    ),
                )

            updated_row = _select_prediction_detail(connection, prediction_id)
            if updated_row is None:
                raise sqlite3.DatabaseError(
                    "The updated prediction could not be loaded."
                )
            detail = _map_prediction_detail(
                updated_row,
                _select_tags(connection, prediction_id),
            )

        return detail

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...] | None:
        """Load immutable definition changes in save order."""

        with self._database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM predictions WHERE id = ?",
                (prediction_id,),
            ).fetchone()
            if exists is None:
                return None
            rows = connection.execute(
                """
                SELECT
                    id,
                    prediction_id,
                    changed_at,
                    old_question,
                    new_question,
                    old_resolution_criteria,
                    new_resolution_criteria,
                    old_forecast_deadline,
                    new_forecast_deadline
                FROM prediction_definition_changes
                WHERE prediction_id = ?
                ORDER BY id
                """,
                (prediction_id,),
            ).fetchall()

        return tuple(_map_definition_change(row) for row in rows)


_PREDICTION_DETAIL_SELECT = """
SELECT
    prediction.id AS prediction_id,
    prediction.question,
    prediction.status,
    prediction.created_at,
    prediction.updated_at,
    prediction.metadata_version,
    prediction.background,
    prediction.resolution_criteria,
    prediction.forecast_deadline,
    prediction.expected_resolution,
    current_revision.id AS current_revision_id,
    current_revision.probability_percent,
    current_revision.sequence AS current_revision_sequence,
    current_revision.rationale AS current_rationale
FROM predictions AS prediction
JOIN forecast_revisions AS current_revision
    ON current_revision.id = (
        SELECT candidate.id
        FROM forecast_revisions AS candidate
        WHERE candidate.prediction_id = prediction.id
        ORDER BY candidate.sequence DESC
        LIMIT 1
    )
"""


def _select_prediction_detail(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        {_PREDICTION_DETAIL_SELECT}
        WHERE prediction.id = ?
        """,
        (prediction_id,),
    ).fetchone()


def _map_prediction_detail(
    row: sqlite3.Row,
    tags: tuple[str, ...] = (),
) -> PredictionDetail:
    status = PredictionStatus(row["status"])
    return PredictionDetail(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        probability_percent=int(row["probability_percent"]),
        status=status,
        created_at=parse_utc(str(row["created_at"])),
        current_revision_id=int(row["current_revision_id"]),
        current_revision_sequence=int(row["current_revision_sequence"]),
        current_rationale=_optional_string(row["current_rationale"]),
        background=_optional_string(row["background"]),
        resolution_criteria=_optional_string(row["resolution_criteria"]),
        forecast_deadline=_parse_date(row["forecast_deadline"]),
        expected_resolution=_parse_date(row["expected_resolution"]),
        tags=tags,
        updated_at=parse_utc(str(row["updated_at"])),
        metadata_version=int(row["metadata_version"]),
    )


def _map_forecast_revision(row: sqlite3.Row) -> ForecastRevision:
    return ForecastRevision(
        revision_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        probability_percent=int(row["probability_percent"]),
        sequence=int(row["sequence"]),
        created_at=parse_utc(str(row["created_at"])),
        rationale=_optional_string(row["rationale"]),
    )


def _select_tags(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT tag.display_name
        FROM tags AS tag
        JOIN prediction_tags AS prediction_tag ON prediction_tag.tag_id = tag.id
        WHERE prediction_tag.prediction_id = ?
        ORDER BY tag.normalized_name, tag.id
        """,
        (prediction_id,),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _replace_tags(
    connection: sqlite3.Connection,
    prediction_id: int,
    tags: tuple[str, ...],
) -> None:
    connection.execute(
        "DELETE FROM prediction_tags WHERE prediction_id = ?",
        (prediction_id,),
    )
    for display_name in tags:
        normalized_name = display_name.casefold()
        connection.execute(
            """
            INSERT INTO tags (display_name, normalized_name)
            VALUES (?, ?)
            ON CONFLICT (normalized_name) DO NOTHING
            """,
            (display_name, normalized_name),
        )
        tag_row = connection.execute(
            "SELECT id FROM tags WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        if tag_row is None:
            raise sqlite3.DatabaseError("A tag could not be loaded after insertion.")
        connection.execute(
            """
            INSERT INTO prediction_tags (prediction_id, tag_id)
            VALUES (?, ?)
            """,
            (prediction_id, int(tag_row[0])),
        )


def _same_editable_metadata(
    left: PredictionDetail,
    right: PredictionDetail,
) -> bool:
    scalar_fields = (
        "question",
        "background",
        "resolution_criteria",
        "forecast_deadline",
        "expected_resolution",
        "updated_at",
        "metadata_version",
    )
    return all(
        getattr(left, field_name) == getattr(right, field_name)
        for field_name in scalar_fields
    ) and {tag.casefold() for tag in left.tags} == {
        tag.casefold() for tag in right.tags
    }


def _map_definition_change(row: sqlite3.Row) -> DefinitionChange:
    old_question = str(row["old_question"])
    new_question = str(row["new_question"])
    old_resolution_criteria = _optional_string(row["old_resolution_criteria"])
    new_resolution_criteria = _optional_string(row["new_resolution_criteria"])
    old_forecast_deadline = _parse_date(row["old_forecast_deadline"])
    new_forecast_deadline = _parse_date(row["new_forecast_deadline"])
    changed_fields = tuple(
        field_name
        for field_name, old_value, new_value in (
            ("question", old_question, new_question),
            (
                "resolution_criteria",
                old_resolution_criteria,
                new_resolution_criteria,
            ),
            ("forecast_deadline", old_forecast_deadline, new_forecast_deadline),
        )
        if old_value != new_value
    )
    return DefinitionChange(
        change_id=int(row["id"]),
        prediction_id=int(row["prediction_id"]),
        changed_at=parse_utc(str(row["changed_at"])),
        changed_fields=changed_fields,
        old_question=old_question,
        new_question=new_question,
        old_resolution_criteria=old_resolution_criteria,
        new_resolution_criteria=new_resolution_criteria,
        old_forecast_deadline=old_forecast_deadline,
        new_forecast_deadline=new_forecast_deadline,
    )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_date(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))
