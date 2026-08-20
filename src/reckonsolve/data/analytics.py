"""Read-only SQLite access for exactly-once scoring observations."""

from reckonsolve.clock import parse_utc
from reckonsolve.domain.analytics import AnalyticsSource, ScoringObservation
from reckonsolve.domain.predictions import BinaryOutcome

from .database import Database


class AnalyticsRepository:
    """Load canonical resolved observations without calculating scores."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_source(self) -> AnalyticsSource:
        """Return one captured scoring revision for every valid Resolution."""

        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT
                    prediction.id AS prediction_id,
                    prediction.question,
                    resolution.id AS resolution_id,
                    resolution.outcome,
                    resolution.resolved_at,
                    resolution.scoring_revision_id,
                    scoring_revision.probability_percent
                FROM resolutions AS resolution
                JOIN predictions AS prediction
                    ON prediction.id = resolution.prediction_id
                    AND prediction.status = 'resolved'
                JOIN forecast_revisions AS scoring_revision
                    ON scoring_revision.prediction_id = prediction.id
                    AND scoring_revision.id = resolution.scoring_revision_id
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
                    AND prediction.status = 'resolved'
                JOIN prediction_tags AS prediction_tag
                    ON prediction_tag.prediction_id = resolution.prediction_id
                JOIN tags AS tag ON tag.id = prediction_tag.tag_id
                ORDER BY tag.normalized_name, tag.id, resolution.prediction_id
                """
            ).fetchall()

        tags_by_prediction: dict[int, list[str]] = {}
        available_tags: list[str] = []
        seen_tags: set[str] = set()
        for row in tag_rows:
            prediction_id = int(row["prediction_id"])
            display_name = str(row["display_name"])
            tags_by_prediction.setdefault(prediction_id, []).append(display_name)
            normalized_name = str(row["normalized_name"])
            if normalized_name not in seen_tags:
                available_tags.append(display_name)
                seen_tags.add(normalized_name)

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
                )
                for row in rows
            ),
            available_tags=tuple(available_tags),
        )
