"""Persistence boundary for immutable Prediction forecast contracts."""

import sqlite3

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.forecast_contracts import (
    ForecastContract,
    ForecastContractValidationError,
    ForecastDeadline,
    ForecastModel,
    ScoringContract,
)
from reckonsolve.domain.predictions import PredictionType


class ForecastContractIntegrityError(RuntimeError):
    """Raised when persisted model identity is missing, unknown, or inconsistent."""


class RetiredForecastModelError(ForecastContractIntegrityError):
    """An entire database is unsupported if it contains a retired Prediction."""


def reject_retired_forecasts(connection: sqlite3.Connection) -> None:
    """Read-only compatibility gate, including databases predating model identity.

    Run under the caller's transaction before migration, repair, or normal work.
    Never infer a replacement contract or serve only the supported subset.
    """
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'predictions'"
        ).fetchone()
        is None
    ):
        return
    if not _contract_table_exists(connection):
        row = connection.execute("SELECT id FROM predictions LIMIT 1").fetchone()
        if row is None:
            return
        raise ForecastContractIntegrityError(
            f"Prediction {int(row[0])} has no stored forecast-model identity. "
            "Pre-v0.7 forecasts are retired. This database cannot be opened; "
            "no conversion or deletion occurred. Keep the original database or "
            "backup for use with a compatible earlier Reckonsolve version."
        )
    row = connection.execute(
        """
        SELECT prediction.id, contract.forecast_model
        FROM predictions AS prediction
        JOIN prediction_forecast_contracts AS contract
            ON contract.prediction_id = prediction.id
        WHERE contract.forecast_model IN ('binary-final-v1', 'numeric-interval-v1')
        ORDER BY prediction.id LIMIT 1
        """
    ).fetchone()
    if row is not None:
        raise RetiredForecastModelError(
            f"Prediction {int(row[0])} uses retired model '{row[1]}'. "
            "This database cannot be opened, even if it also contains current "
            "forecasts. No conversion or deletion occurred. Keep the original "
            "database or backup for use with a compatible earlier Reckonsolve version."
        )


def check_forecast_contract_integrity(connection: sqlite3.Connection) -> None:
    """Reject unsupported contracts before cohort-filtered reads can omit them.

    Empty historical schemas can migrate. Every retained Prediction must have a
    supported, complete pair, not merely every Prediction in a filtered result.
    """

    reject_retired_forecasts(connection)
    if not _contract_table_exists(connection):
        return

    quantiles_available = quantile_tables_exist(connection)
    quantile_join = (
        """
        LEFT JOIN numeric_quantile_revisions AS quantile_initial
            ON quantile_initial.prediction_id = prediction.id AND quantile_initial.sequence = 1
        LEFT JOIN numeric_quantile_definitions AS quantile_definition
            ON quantile_definition.prediction_id = prediction.id
    """
        if quantiles_available
        else ""
    )
    quantile_invalid = (
        """quantile_initial.id IS NULL OR quantile_definition.prediction_id IS NULL
        OR contract.forecast_deadline_at <= quantile_initial.created_at
        OR numeric_initial.id IS NOT NULL"""
        if quantiles_available
        else "1"
    )
    row = connection.execute(
        f"""
        SELECT prediction.id
        FROM predictions AS prediction
        LEFT JOIN prediction_forecast_contracts AS contract
            ON contract.prediction_id = prediction.id
        LEFT JOIN forecast_revisions AS binary_initial
            ON binary_initial.prediction_id = prediction.id
            AND binary_initial.sequence = 1
        LEFT JOIN numeric_forecast_revisions AS numeric_initial
            ON numeric_initial.prediction_id = prediction.id
            AND numeric_initial.sequence = 1
        {quantile_join}
        WHERE contract.prediction_id IS NULL
            OR prediction.prediction_type NOT IN ('binary', 'numeric')
            OR contract.forecast_model IS NULL
            OR contract.scoring_contract IS NULL
            OR (contract.forecast_model, contract.scoring_contract) NOT IN (
                ('binary-trajectory-v1', 'binary-trajectory-brier-v1'),
                ('numeric-quantiles-5-v2', 'numeric-wis-v1')
            )
            OR contract.forecast_deadline_at IS NULL
            OR (
                prediction.prediction_type = 'binary'
                AND contract.forecast_model != 'binary-trajectory-v1'
            )
            OR (
                prediction.prediction_type = 'numeric'
                AND contract.forecast_model != 'numeric-quantiles-5-v2'
            )
            OR (
                contract.forecast_model = 'binary-trajectory-v1'
                AND (
                    binary_initial.id IS NULL
                    OR contract.forecast_deadline_at <= binary_initial.created_at
                )
            )
            OR (
                contract.forecast_model = 'numeric-quantiles-5-v2'
                AND (
                    {quantile_invalid}
                )
            )
        LIMIT 1
        """
    ).fetchone()
    if row is not None:
        raise ForecastContractIntegrityError(
            f"Prediction {int(row[0])} has a missing or inconsistent forecast contract."
        )


def select_forecast_contract(
    connection: sqlite3.Connection,
    prediction_id: int,
) -> ForecastContract:
    """Load and validate one durable identity without guessing from old columns."""

    row = connection.execute(
        """
        SELECT
            prediction.prediction_type,
            contract.forecast_model,
            contract.scoring_contract,
            contract.forecast_deadline_at
        FROM predictions AS prediction
        LEFT JOIN prediction_forecast_contracts AS contract
            ON contract.prediction_id = prediction.id
        WHERE prediction.id = ?
        """,
        (prediction_id,),
    ).fetchone()
    if row is None:
        raise ForecastContractIntegrityError("Prediction does not exist.")
    if row[1] is None or row[2] is None:
        raise ForecastContractIntegrityError(
            "Prediction has no durable forecast-model identity."
        )
    try:
        deadline = None if row[3] is None else ForecastDeadline(parse_utc(str(row[3])))
        return ForecastContract(
            prediction_type=PredictionType(str(row[0])),
            forecast_model=ForecastModel(str(row[1])),
            scoring_contract=ScoringContract(str(row[2])),
            forecast_deadline=deadline,
        )
    except (ValueError, ForecastContractValidationError) as error:
        raise ForecastContractIntegrityError(
            "Prediction has an unrecognized or inconsistent forecast contract."
        ) from error


def insert_prospective_contract(
    connection: sqlite3.Connection,
    prediction_id: int,
    contract: ForecastContract,
) -> None:
    """Persist a validated new-model contract for later vertical slices."""

    if contract.forecast_deadline is None:
        raise ForecastContractIntegrityError(
            "A prospective contract with an exact Deadline is required."
        )
    connection.execute(
        """
        INSERT INTO prediction_forecast_contracts (
            prediction_id,
            forecast_model,
            scoring_contract,
            forecast_deadline_at
        ) VALUES (?, ?, ?, ?)
        """,
        (
            prediction_id,
            contract.forecast_model.value,
            contract.scoring_contract.value,
            format_utc(contract.forecast_deadline.instant),
        ),
    )


def _contract_table_exists(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_schema
            WHERE type = 'table' AND name = 'prediction_forecast_contracts'
            """
        ).fetchone()
        is not None
    )


def binary_corrections_relation(connection: sqlite3.Connection) -> str:
    """Supported Binary correction chain, also present in staged schema 16."""
    return "binary_trajectory_resolution_corrections"


def quantile_tables_exist(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'numeric_quantile_revisions'"
        ).fetchone()
        is not None
    )


def numeric_corrections_relation(connection: sqlite3.Connection) -> str:
    """Common effective terminal projection, never scoring-revision authority."""
    return "numeric_quantile_resolution_corrections"


def select_supported_contract(
    connection: sqlite3.Connection, prediction_id: int
) -> ForecastContract:
    """Read one supported identity after the whole-database compatibility gate."""
    return select_forecast_contract(connection, prediction_id)


def binary_contract_columns(connection: sqlite3.Connection) -> str:
    """Project the durable identity alongside the Binary detail query."""
    return """
        , (SELECT forecast_model FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS forecast_model
        , (SELECT scoring_contract FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS scoring_contract
        , (SELECT forecast_deadline_at FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS forecast_deadline_at
    """


def map_binary_contract(row: sqlite3.Row) -> ForecastContract:
    try:
        return ForecastContract(
            PredictionType.BINARY,
            ForecastModel(row["forecast_model"]),
            ScoringContract(row["scoring_contract"]),
            None
            if row["forecast_deadline_at"] is None
            else ForecastDeadline(parse_utc(row["forecast_deadline_at"])),
        )
    except ValueError as error:
        raise ForecastContractIntegrityError(
            "Invalid Binary forecast contract."
        ) from error
