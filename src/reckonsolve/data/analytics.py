"""Read-only SQLite access for exactly-once scoring observations."""

import sqlite3

from reckonsolve.clock import parse_utc
from reckonsolve.domain.analytics import (
    AnalyticsSource,
    NumericAnalyticsSource,
    NumericScoringObservation,
    ScoringObservation,
)
from reckonsolve.domain.predictions import BinaryOutcome, FixedPrecisionValue

from .database import Database


class AnalyticsRepository:
    """Load canonical resolved observations without calculating scores."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_source(self) -> AnalyticsSource:
        """Return one captured scoring revision for every Binary Resolution."""

        with self._database.transaction() as connection:
            return _load_binary_source(connection)

    def get_numeric_source(self) -> NumericAnalyticsSource:
        """Return one captured scoring interval for every Numeric Resolution."""

        with self._database.transaction() as connection:
            return _load_numeric_source(connection)

    def get_sources(self) -> tuple[AnalyticsSource, NumericAnalyticsSource]:
        """Read both forecast types from one consistent SQLite snapshot."""

        with self._database.transaction() as connection:
            return _load_binary_source(connection), _load_numeric_source(connection)


def _load_binary_source(connection: sqlite3.Connection) -> AnalyticsSource:
    rows = connection.execute(
        """
        SELECT
            prediction.id AS prediction_id,
            prediction.question,
            resolution.id AS resolution_id,
            COALESCE(
                (
                    SELECT correction.new_outcome
                    FROM resolution_corrections AS correction
                    WHERE correction.resolution_id = resolution.id
                    ORDER BY correction.sequence DESC
                    LIMIT 1
                ),
                resolution.outcome
            ) AS outcome,
            EXISTS(
                SELECT 1
                FROM resolution_corrections AS correction
                WHERE correction.resolution_id = resolution.id
                    AND correction.outcome_changed = 1
            ) AS outcome_corrected,
            resolution.resolved_at,
            resolution.scoring_revision_id,
            scoring_revision.probability_percent,
            initial_revision.id AS initial_revision_id,
            initial_revision.probability_percent AS initial_probability_percent
        FROM resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'binary'
            AND prediction.status = 'resolved'
        JOIN forecast_revisions AS scoring_revision
            ON scoring_revision.prediction_id = prediction.id
            AND scoring_revision.id = resolution.scoring_revision_id
        JOIN forecast_revisions AS initial_revision
            ON initial_revision.prediction_id = prediction.id
            AND initial_revision.sequence = 1
        ORDER BY resolution.resolved_at, resolution.id
        """
    ).fetchall()
    tag_rows = connection.execute(
        """
        SELECT
            resolution.prediction_id,
            tag.display_name,
            tag.normalized_name,
            tag.id AS tag_id
        FROM resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'binary'
            AND prediction.status = 'resolved'
        JOIN prediction_tags AS prediction_tag
            ON prediction_tag.prediction_id = resolution.prediction_id
        JOIN tags AS tag ON tag.id = prediction_tag.tag_id
        ORDER BY tag.normalized_name, tag.id, resolution.prediction_id
        """
    ).fetchall()
    tags_by_prediction, available_tags = _group_tags(tag_rows)
    return AnalyticsSource(
        observations=tuple(
            ScoringObservation(
                prediction_id=int(row["prediction_id"]),
                question=str(row["question"]),
                resolution_id=int(row["resolution_id"]),
                resolved_at=parse_utc(str(row["resolved_at"])),
                scoring_revision_id=int(row["scoring_revision_id"]),
                probability_percent=int(row["probability_percent"]),
                outcome=BinaryOutcome(row["outcome"]),
                tags=tuple(tags_by_prediction.get(int(row["prediction_id"]), ())),
                outcome_corrected=bool(row["outcome_corrected"]),
                initial_revision_id=int(row["initial_revision_id"]),
                initial_probability_percent=int(row["initial_probability_percent"]),
            )
            for row in rows
        ),
        available_tags=available_tags,
    )


def _load_numeric_source(connection: sqlite3.Connection) -> NumericAnalyticsSource:
    rows = connection.execute(
        """
        SELECT
            prediction.id AS prediction_id,
            prediction.question,
            prediction.numeric_unit,
            prediction.numeric_precision,
            resolution.id AS resolution_id,
            COALESCE(
                (
                    SELECT correction.new_actual_scaled
                    FROM numeric_resolution_corrections AS correction
                    WHERE correction.numeric_resolution_id = resolution.id
                    ORDER BY correction.sequence DESC
                    LIMIT 1
                ),
                resolution.actual_scaled
            ) AS actual_scaled,
            EXISTS(
                SELECT 1
                FROM numeric_resolution_corrections AS correction
                WHERE correction.numeric_resolution_id = resolution.id
                    AND correction.actual_value_changed = 1
            ) AS actual_value_corrected,
            resolution.resolved_at,
            resolution.scoring_revision_id,
            scoring_revision.lower_scaled,
            scoring_revision.median_scaled,
            scoring_revision.upper_scaled,
            scoring_revision.confidence_percent,
            initial_revision.id AS initial_revision_id,
            initial_revision.lower_scaled AS initial_lower_scaled,
            initial_revision.median_scaled AS initial_median_scaled,
            initial_revision.upper_scaled AS initial_upper_scaled,
            initial_revision.confidence_percent AS initial_confidence_percent
        FROM numeric_resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'numeric'
            AND prediction.status = 'resolved'
        JOIN numeric_forecast_revisions AS scoring_revision
            ON scoring_revision.prediction_id = prediction.id
            AND scoring_revision.id = resolution.scoring_revision_id
        JOIN numeric_forecast_revisions AS initial_revision
            ON initial_revision.prediction_id = prediction.id
            AND initial_revision.sequence = 1
        ORDER BY resolution.resolved_at, resolution.id
        """
    ).fetchall()
    tag_rows = connection.execute(
        """
        SELECT
            resolution.prediction_id,
            tag.display_name,
            tag.normalized_name,
            tag.id AS tag_id
        FROM numeric_resolutions AS resolution
        JOIN predictions AS prediction
            ON prediction.id = resolution.prediction_id
            AND prediction.prediction_type = 'numeric'
            AND prediction.status = 'resolved'
        JOIN prediction_tags AS prediction_tag
            ON prediction_tag.prediction_id = resolution.prediction_id
        JOIN tags AS tag ON tag.id = prediction_tag.tag_id
        ORDER BY tag.normalized_name, tag.id, resolution.prediction_id
        """
    ).fetchall()
    tags_by_prediction, available_tags = _group_tags(tag_rows)
    units = tuple(
        sorted(
            {str(row["numeric_unit"]) for row in rows},
            key=lambda value: (value.casefold(), value),
        )
    )
    return NumericAnalyticsSource(
        observations=tuple(
            _map_numeric_scoring_observation(
                row,
                tuple(tags_by_prediction.get(int(row["prediction_id"]), ())),
            )
            for row in rows
        ),
        available_tags=available_tags,
        available_units=units,
    )


def _group_tags(
    rows: list[sqlite3.Row],
) -> tuple[dict[int, list[str]], tuple[str, ...]]:
    tags_by_prediction: dict[int, list[str]] = {}
    available_tags: list[str] = []
    seen_tags: set[str] = set()
    for row in rows:
        prediction_id = int(row["prediction_id"])
        display_name = str(row["display_name"])
        tags_by_prediction.setdefault(prediction_id, []).append(display_name)
        normalized_name = str(row["normalized_name"])
        if normalized_name not in seen_tags:
            available_tags.append(display_name)
            seen_tags.add(normalized_name)
    return tags_by_prediction, tuple(available_tags)


def _map_numeric_scoring_observation(
    row: sqlite3.Row,
    tags: tuple[str, ...],
) -> NumericScoringObservation:
    decimal_places = int(row["numeric_precision"])
    return NumericScoringObservation(
        prediction_id=int(row["prediction_id"]),
        question=str(row["question"]),
        resolution_id=int(row["resolution_id"]),
        resolved_at=parse_utc(str(row["resolved_at"])),
        scoring_revision_id=int(row["scoring_revision_id"]),
        unit=str(row["numeric_unit"]),
        lower_bound=FixedPrecisionValue(int(row["lower_scaled"]), decimal_places),
        median_estimate=FixedPrecisionValue(
            int(row["median_scaled"]),
            decimal_places,
        ),
        upper_bound=FixedPrecisionValue(int(row["upper_scaled"]), decimal_places),
        confidence_percent=int(row["confidence_percent"]),
        actual_value=FixedPrecisionValue(int(row["actual_scaled"]), decimal_places),
        tags=tags,
        actual_value_corrected=bool(row["actual_value_corrected"]),
        initial_revision_id=int(row["initial_revision_id"]),
        initial_lower_bound=FixedPrecisionValue(
            int(row["initial_lower_scaled"]),
            decimal_places,
        ),
        initial_median_estimate=FixedPrecisionValue(
            int(row["initial_median_scaled"]),
            decimal_places,
        ),
        initial_upper_bound=FixedPrecisionValue(
            int(row["initial_upper_scaled"]),
            decimal_places,
        ),
        initial_confidence_percent=int(row["initial_confidence_percent"]),
    )
