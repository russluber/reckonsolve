"""Persistence boundary for immutable Prediction forecast contracts."""

import sqlite3

from reckonsolve.clock import format_utc, parse_utc
from reckonsolve.domain.forecast_contracts import (
    ForecastContract,
    ForecastContractValidationError,
    ForecastDeadline,
    ForecastModel,
    ScoringContract,
    legacy_contract,
)
from reckonsolve.domain.predictions import PredictionType


class ForecastContractIntegrityError(RuntimeError):
    """Raised when persisted model identity is missing, unknown, or inconsistent."""


def check_forecast_contract_integrity(connection: sqlite3.Connection) -> None:
    """Reject a schema-16 database whose Prediction contracts are incomplete."""

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
            OR (
                prediction.prediction_type = 'binary'
                AND contract.forecast_model NOT IN (
                    'binary-final-v1', 'binary-trajectory-v1'
                )
            )
            OR (
                prediction.prediction_type = 'numeric'
                AND contract.forecast_model NOT IN (
                    'numeric-interval-v1', 'numeric-quantiles-5-v2'
                )
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


def insert_legacy_contract_if_supported(
    connection: sqlite3.Connection,
    prediction_id: int,
    prediction_type: PredictionType,
) -> None:
    """Assign current creation flows explicitly when schema 16 is available.

    Migration tests intentionally exercise current repositories against older
    schema slices, so absence of the table is the only supported no-op.
    """

    if not _contract_table_exists(connection):
        return
    contract = legacy_contract(prediction_type)
    connection.execute(
        """
        INSERT INTO prediction_forecast_contracts (
            prediction_id,
            forecast_model,
            scoring_contract,
            forecast_deadline_at
        ) VALUES (?, ?, ?, NULL)
        """,
        (
            prediction_id,
            contract.forecast_model.value,
            contract.scoring_contract.value,
        ),
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

    if contract.is_legacy or contract.forecast_deadline is None:
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
    """Shared terminal text/history only; scoring still dispatches by cohort."""
    if connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'view' AND name = 'binary_resolution_history_rows'"
    ).fetchone():
        return "binary_resolution_history_rows"
    return "resolution_corrections"


def quantile_tables_exist(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'numeric_quantile_revisions'"
        ).fetchone()
        is not None
    )


def select_supported_contract(
    connection: sqlite3.Connection, prediction_id: int
) -> ForecastContract | None:
    """Only historical schema fixtures may lack a contract table."""
    if not _contract_table_exists(connection):
        return None
    return select_forecast_contract(connection, prediction_id)


def binary_contract_columns(connection: sqlite3.Connection) -> str:
    """Project the durable identity alongside the legacy-compatible detail query."""
    if not _contract_table_exists(connection):
        return ""
    return """
        , (SELECT forecast_model FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS forecast_model
        , (SELECT scoring_contract FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS scoring_contract
        , (SELECT forecast_deadline_at FROM prediction_forecast_contracts
           WHERE prediction_id = prediction.id) AS forecast_deadline_at
    """


def map_binary_contract(row: sqlite3.Row) -> ForecastContract | None:
    if "forecast_model" not in row.keys():  # noqa: SIM118 -- Row membership tests values.
        return None
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
