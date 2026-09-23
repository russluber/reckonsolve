"""Read-only SQLite access for exactly-once scoring observations."""

import sqlite3

from reckonsolve.clock import parse_utc
from reckonsolve.domain.analytics import (
    QuantileAnalyticsSource,
    QuantileScoringRecord,
    TrajectoryAnalyticsSource,
    TrajectoryScoringRecord,
)
from reckonsolve.domain.forecast_contracts import ForecastCohort, ForecastContract
from reckonsolve.domain.predictions import (
    BinaryResolutionHistory,
    ForecastRevision,
    NumericResolutionHistory,
)
from reckonsolve.domain.quantiles import QuantileDefinition, QuantileRevision

from .database import Database
from .forecast_contracts import (
    check_forecast_contract_integrity,
    select_supported_contract,
)
from .quantiles import read_definition, read_revisions
from .terminal_history import (
    _select_binary_resolution_history,
    _select_numeric_resolution_history,
)


class AnalyticsRepository:
    """Load canonical resolved observations without calculating scores."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get_quantile_source(
        self, prediction_id: int
    ) -> (
        tuple[
            ForecastContract,
            QuantileDefinition,
            tuple[QuantileRevision, ...],
            NumericResolutionHistory,
        ]
        | None
    ):
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM predictions WHERE id = ?", (prediction_id,)
            ).fetchone()
            if row is None or row[0] != "resolved":
                return None
            contract = select_supported_contract(connection, prediction_id)
            if (
                contract is None
                or contract.cohort is not ForecastCohort.QUANTILE_NUMERIC
            ):
                return None
            history = _select_numeric_resolution_history(connection, prediction_id)
            assert history is not None
            return (
                contract,
                read_definition(connection, prediction_id),
                read_revisions(connection, prediction_id),
                history,
            )

    def get_trajectory_source(
        self, prediction_id: int
    ) -> (
        tuple[ForecastContract, tuple[ForecastRevision, ...], BinaryResolutionHistory]
        | None
    ):
        """One consistent snapshot of a resolved prospective Binary and all revisions."""
        with self._database.transaction() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM predictions WHERE id = ? AND prediction_type = 'binary' AND status = 'resolved'",
                    (prediction_id,),
                ).fetchone()
                is None
            ):
                return None
            contract = select_supported_contract(connection, prediction_id)
            if contract is None:
                return None
            history = _select_binary_resolution_history(connection, prediction_id)
            assert history is not None
            revisions = tuple(
                ForecastRevision(
                    int(row["id"]),
                    prediction_id,
                    int(row["probability_percent"]),
                    int(row["sequence"]),
                    parse_utc(row["created_at"]),
                    row["rationale"],
                )
                for row in connection.execute(
                    "SELECT * FROM forecast_revisions WHERE prediction_id = ? ORDER BY sequence",
                    (prediction_id,),
                )
            )
            return contract, revisions, history

    def get_forecast_sources(
        self,
    ) -> tuple[
        TrajectoryAnalyticsSource,
        QuantileAnalyticsSource,
    ]:
        """Read every aggregate cohort from one consistent SQLite snapshot."""

        with self._database.transaction() as connection:
            check_forecast_contract_integrity(connection)
            return (
                _load_trajectory_source(connection),
                _load_quantile_source(connection),
            )


def _load_trajectory_source(
    connection: sqlite3.Connection,
) -> TrajectoryAnalyticsSource:
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'prediction_forecast_contracts'"
        ).fetchone()
        is None
    ):
        return TrajectoryAnalyticsSource(records=())
    rows = connection.execute(
        """
        SELECT prediction.id AS prediction_id, prediction.question
        FROM predictions AS prediction
        JOIN prediction_forecast_contracts AS contract
            ON contract.prediction_id = prediction.id
            AND contract.forecast_model = 'binary-trajectory-v1'
            AND contract.scoring_contract = 'binary-trajectory-brier-v1'
        JOIN resolutions AS resolution
            ON resolution.prediction_id = prediction.id
        WHERE prediction.prediction_type = 'binary'
            AND prediction.status = 'resolved'
        ORDER BY resolution.resolved_at, resolution.id
        """
    ).fetchall()
    prediction_ids = tuple(int(row["prediction_id"]) for row in rows)
    if not prediction_ids:
        return TrajectoryAnalyticsSource(records=())
    placeholders = ", ".join("?" for _ in prediction_ids)
    revision_rows = connection.execute(
        f"""
        SELECT *
        FROM forecast_revisions
        WHERE prediction_id IN ({placeholders})
        ORDER BY prediction_id, sequence
        """,
        prediction_ids,
    ).fetchall()
    tag_rows = connection.execute(
        f"""
        SELECT prediction_tag.prediction_id, tag.display_name,
               tag.normalized_name, tag.id AS tag_id
        FROM prediction_tags AS prediction_tag
        JOIN tags AS tag ON tag.id = prediction_tag.tag_id
        WHERE prediction_tag.prediction_id IN ({placeholders})
        ORDER BY tag.normalized_name, tag.id, prediction_tag.prediction_id
        """,
        prediction_ids,
    ).fetchall()
    revisions_by_prediction: dict[int, list[ForecastRevision]] = {}
    for row in revision_rows:
        prediction_id = int(row["prediction_id"])
        revisions_by_prediction.setdefault(prediction_id, []).append(
            ForecastRevision(
                int(row["id"]),
                prediction_id,
                int(row["probability_percent"]),
                int(row["sequence"]),
                parse_utc(str(row["created_at"])),
                row["rationale"],
            )
        )
    tags_by_prediction, _available_tags = _group_tags(list(tag_rows))
    records: list[TrajectoryScoringRecord] = []
    for row in rows:
        prediction_id = int(row["prediction_id"])
        contract = select_supported_contract(connection, prediction_id)
        history = _select_binary_resolution_history(connection, prediction_id)
        assert contract is not None and history is not None
        records.append(
            TrajectoryScoringRecord(
                question=str(row["question"]),
                contract=contract,
                revisions=tuple(revisions_by_prediction[prediction_id]),
                resolution_history=history,
                tags=tuple(tags_by_prediction.get(prediction_id, ())),
            )
        )
    return TrajectoryAnalyticsSource(records=tuple(records))


def _load_quantile_source(connection: sqlite3.Connection) -> QuantileAnalyticsSource:
    # Historical fixture schemas have no prospective Numeric tables.
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'numeric_quantile_revisions'"
        ).fetchone()
        is None
    ):
        return QuantileAnalyticsSource(records=())
    rows = connection.execute(
        """
        SELECT p.id, p.question FROM predictions AS p
        JOIN prediction_forecast_contracts AS c ON c.prediction_id = p.id
        JOIN numeric_resolutions AS r ON r.prediction_id = p.id
        WHERE p.status = 'resolved' AND p.prediction_type = 'numeric'
          AND c.forecast_model = 'numeric-quantiles-5-v2'
          AND c.scoring_contract = 'numeric-wis-v1'
        ORDER BY r.resolved_at, r.id
        """
    ).fetchall()
    records: list[QuantileScoringRecord] = []
    for row in rows:
        prediction_id = int(row["id"])
        contract = select_supported_contract(connection, prediction_id)
        history = _select_numeric_resolution_history(connection, prediction_id)
        assert contract is not None and history is not None
        tags = tuple(
            str(tag[0])
            for tag in connection.execute(
                "SELECT t.display_name FROM tags AS t "
                "JOIN prediction_tags AS pt ON pt.tag_id = t.id "
                "WHERE pt.prediction_id = ? ORDER BY t.normalized_name, t.id",
                (prediction_id,),
            )
        )
        records.append(
            QuantileScoringRecord(
                question=str(row["question"]),
                contract=contract,
                definition=read_definition(connection, prediction_id),
                revisions=read_revisions(connection, prediction_id),
                resolution_history=history,
                tags=tags,
            )
        )
    return QuantileAnalyticsSource(tuple(records))


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
