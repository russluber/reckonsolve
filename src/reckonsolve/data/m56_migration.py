"""Schema 19: distinct One-Shot identities, documentary times, and corrections.

Only the contract table is rebuilt. Its successor is composed from shipped DDL;
all existing forecast, terminal, and shared-history rows stay in their tables.
"""

import re
from itertools import pairwise

from .m50_migration import _immutable, _instant

ONE_SHOT_MODELS = "'binary-one-shot-v1', 'numeric-one-shot-5-v1'"
FORECAST_FIELDS = (
    "probability_percent",
    "q05_scaled",
    "q25_scaled",
    "q50_scaled",
    "q75_scaled",
    "q95_scaled",
    "forecast_wall",
    "forecast_approximate",
    "forecast_offset",
)
ANSWER_FIELDS = (
    "outcome",
    "actual_scaled",
    "reveal_wall",
    "reveal_approximate",
    "reveal_offset",
    "resolution_notes",
    "postmortem",
)
SNAPSHOT_FIELDS = FORECAST_FIELDS + ANSWER_FIELDS


def _text_check(column: str) -> str:
    return f"""CHECK ({column} IS NULL OR
        (length({column}) > 0 AND instr({column}, char(0)) = 0
         AND {column} = trim({column}, char(9)||char(10)||char(11)||char(12)||char(13)||' ')))"""


def _reported_checks(prefix: str) -> str:
    wall, approximate, offset = (prefix + s for s in ("wall", "approximate", "offset"))
    return f"""CHECK ({approximate} IN (0, 1)),
        CHECK ({offset} IS NULL OR {offset} BETWEEN -1439 AND 1439),
        CHECK (({wall} IS NULL AND {approximate} = 0 AND {offset} IS NULL) OR
            ({wall} IS NOT NULL AND length({wall}) = 16 AND {wall} GLOB
             '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-2][0-9]:[0-5][0-9]'
             AND substr({wall}, 1, 4) BETWEEN '0001' AND '9999'
             AND substr({wall}, 12, 2) BETWEEN '00' AND '23'
             AND COALESCE(date(substr({wall}, 1, 10), '+0 days') = substr({wall}, 1, 10), 0)))"""


def _snapshot_columns(prefix: str) -> str:
    return ", ".join(
        f"{prefix}{field} {'TEXT' if field in ('outcome', 'forecast_wall', 'reveal_wall', 'resolution_notes', 'postmortem') else 'INTEGER'}"
        + (" NOT NULL" if field.endswith("approximate") else "")
        for field in SNAPSHOT_FIELDS
    )


def _snapshot_checks(prefix: str) -> str:
    p = prefix
    quantiles = [p + f"q{q:02}_scaled" for q in (5, 25, 50, 75, 95)]
    binary = " AND ".join(f"{q} IS NULL" for q in quantiles)
    numeric = " AND ".join(
        f"{q} IS NOT NULL AND {q} BETWEEN -999999999999999999 AND 999999999999999999"
        for q in quantiles
    )
    order = " AND ".join(f"{a} <= {b}" for a, b in pairwise(quantiles))
    return f"""CHECK (
        ({p}probability_percent IS NOT NULL AND {p}probability_percent BETWEEN 0 AND 100
         AND {binary} AND {p}actual_scaled IS NULL AND ({p}outcome IS NULL OR {p}outcome IN ('yes', 'no')))
        OR ({p}probability_percent IS NULL AND {numeric} AND {order} AND {p}outcome IS NULL
            AND ({p}actual_scaled IS NULL OR {p}actual_scaled BETWEEN -999999999999999999 AND 999999999999999999))),
        {_reported_checks(p + "forecast_")}, {_reported_checks(p + "reveal_")},
        {_text_check(p + "resolution_notes")}, {_text_check(p + "postmortem")},
        CHECK ({p}outcome IS NOT NULL OR {p}actual_scaled IS NOT NULL OR
            ({p}reveal_wall IS NULL AND {p}resolution_notes IS NULL AND {p}postmortem IS NULL))"""


def build_m56_statements(prior_statements: tuple[str, ...]) -> tuple[str, ...]:
    ddl = {}
    for statement in prior_statements:
        normalized = " ".join(statement.split())
        match = re.match(r"CREATE (?:UNIQUE )?(TABLE|INDEX|TRIGGER) (\w+)", normalized)
        if match:
            ddl[match[2]] = normalized
        match = re.match(r"DROP (?:TABLE|INDEX|TRIGGER) (\w+)", normalized)
        if match:
            ddl.pop(match[1], None)
    contract = ddl["prediction_forecast_contracts"]
    contract = contract.replace(
        "'numeric-quantiles-5-v2' )",
        "'numeric-quantiles-5-v2', 'binary-one-shot-v1', 'numeric-one-shot-5-v1' )",
    )
    contract = contract.replace(
        "'numeric-wis-v1' )",
        "'numeric-wis-v1', 'binary-one-shot-brier-v1', 'numeric-one-shot-wis-v1' )",
    )
    contract = contract.replace(
        ") ) ) STRICT",
        ") OR (forecast_model = 'binary-one-shot-v1' AND scoring_contract = 'binary-one-shot-brier-v1' AND forecast_deadline_at IS NULL) "
        "OR (forecast_model = 'numeric-one-shot-5-v1' AND scoring_contract = 'numeric-one-shot-wis-v1' AND forecast_deadline_at IS NULL) ) ) STRICT",
    )
    statements = [
        "CREATE TABLE m56_contract_copy AS SELECT * FROM prediction_forecast_contracts",
        "DROP TABLE prediction_forecast_contracts",
        contract,
        "INSERT INTO prediction_forecast_contracts SELECT * FROM m56_contract_copy",
        "DROP TABLE m56_contract_copy",
    ]
    for name, sql in ddl.items():
        if (
            sql.startswith("CREATE TRIGGER")
            and " ON prediction_forecast_contracts " in sql
        ):
            if name == "prediction_forecast_contracts_require_matching_type":
                sql = sql.replace(
                    "'binary-final-v1', 'binary-trajectory-v1'",
                    "'binary-final-v1', 'binary-trajectory-v1', 'binary-one-shot-v1'",
                )
            statements.append(sql)
    statements.append("""CREATE TRIGGER forecast_contracts_no_replace BEFORE INSERT ON prediction_forecast_contracts
        WHEN EXISTS (SELECT 1 FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id)
        BEGIN SELECT RAISE(ABORT, 'saved forecast contracts cannot be replaced'); END""")
    for name in (
        "numeric_quantile_definitions_require_contract",
        "journal_entries_require_model_anchor",
        "numeric_resolutions_require_model_anchor",
    ):
        sql = ddl[name]
        if name == "numeric_quantile_definitions_require_contract":
            sql = sql.replace(
                "IS NOT 'numeric-quantiles-5-v2'",
                "NOT IN ('numeric-quantiles-5-v2', 'numeric-one-shot-5-v1')",
            )
        else:
            sql = sql.replace(
                "WHEN 'binary-trajectory-v1' THEN",
                "WHEN 'binary-one-shot-v1' THEN "
                + (
                    "NEW.forecast_revision_id IS NOT (SELECT id FROM forecast_revisions WHERE prediction_id = NEW.prediction_id AND sequence = 1) OR NEW.forecast_revision_id IS NULL "
                    if name.startswith("journal")
                    else "1 "
                )
                + "WHEN 'binary-trajectory-v1' THEN",
            )
            sql = sql.replace(
                "WHEN 'numeric-quantiles-5-v2' THEN",
                "WHEN 'numeric-one-shot-5-v1' THEN NEW.quantile_revision_id IS NOT (SELECT id FROM numeric_quantile_revisions WHERE prediction_id = NEW.prediction_id AND sequence = 1) OR NEW.quantile_revision_id IS NULL WHEN 'numeric-quantiles-5-v2' THEN",
            )
        statements.extend((f"DROP TRIGGER {name}", sql))
    for table in ("forecast_revisions", "numeric_quantile_revisions"):
        statements.append(f"""CREATE TRIGGER {table}_one_shot_single BEFORE INSERT ON {table}
            WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) IN ({ONE_SHOT_MODELS})
            AND (NEW.sequence != 1 OR EXISTS (SELECT 1 FROM {table} WHERE prediction_id = NEW.prediction_id)
                 OR NEW.created_at IS NOT (SELECT created_at FROM predictions WHERE id = NEW.prediction_id)
                 OR (SELECT status FROM predictions WHERE id = NEW.prediction_id) IS NOT 'open')
            BEGIN SELECT RAISE(ABORT, 'One-Shot has exactly one original forecast'); END""")
    statements.extend(
        (
            f"""CREATE TRIGGER one_shot_no_reviews BEFORE INSERT ON forecast_reviews
            WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) IN ({ONE_SHOT_MODELS})
            BEGIN SELECT RAISE(ABORT, 'One-Shot does not allow Forecast Reviews'); END""",
            f"""CREATE TRIGGER one_shot_no_date_deadline BEFORE UPDATE OF forecast_deadline ON predictions
            WHEN NEW.forecast_deadline IS NOT NULL AND (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.id) IN ({ONE_SHOT_MODELS})
            BEGIN SELECT RAISE(ABORT, 'One-Shot has no Forecast Deadline'); END""",
        )
    )
    for table in ("resolutions", "numeric_resolutions"):
        statements.append(f"""CREATE TRIGGER {table}_one_shot_timing BEFORE INSERT ON {table}
            WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) IN ({ONE_SHOT_MODELS})
            AND (NEW.effective_resolution_at IS NOT NULL OR NEW.resolved_at < (SELECT created_at FROM predictions WHERE id = NEW.prediction_id)
                 OR NEW.resolved_at < (SELECT MAX(corrected_at) FROM one_shot_corrections WHERE prediction_id = NEW.prediction_id))
            BEGIN SELECT RAISE(ABORT, 'One-Shot answer has only an app-recorded instant'); END""")
    for kind in ("forecast", "answer"):
        table = f"one_shot_{kind}_times"
        statements.extend(
            (
                f"""CREATE TABLE {table} (
                prediction_id INTEGER PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
                wall TEXT, approximate INTEGER NOT NULL DEFAULT 0, offset INTEGER,
                {_reported_checks("")}
            ) STRICT""",
                *_immutable(table, unique="prediction_id = NEW.prediction_id"),
                f"""CREATE TRIGGER {table}_require_contract BEFORE INSERT ON {table}
                WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) NOT IN ({ONE_SHOT_MODELS})
                    OR NOT EXISTS (SELECT 1 FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id)
                BEGIN SELECT RAISE(ABORT, 'reported times require a One-Shot contract'); END""",
            )
        )
    statements.append("""CREATE TRIGGER one_shot_answer_times_require_answer BEFORE INSERT ON one_shot_answer_times
        WHEN NOT EXISTS (SELECT 1 FROM resolutions WHERE prediction_id = NEW.prediction_id)
         AND NOT EXISTS (SELECT 1 FROM numeric_resolutions WHERE prediction_id = NEW.prediction_id)
        BEGIN SELECT RAISE(ABORT, 'reported reveal requires an original answer'); END""")
    statements.append(f"""CREATE TABLE one_shot_corrections (
        id INTEGER PRIMARY KEY, prediction_id INTEGER NOT NULL REFERENCES one_shot_forecast_times(prediction_id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK(sequence >= 1), {_instant("corrected_at")}, note TEXT {_text_check("note")},
        {_snapshot_columns("old_")}, {_snapshot_columns("new_")},
        {_snapshot_checks("old_")}, {_snapshot_checks("new_")},
        UNIQUE(prediction_id, sequence),
        CHECK ((old_probability_percent IS NULL) = (new_probability_percent IS NULL)),
        CHECK ((old_outcome IS NULL) = (new_outcome IS NULL)),
        CHECK ((old_actual_scaled IS NULL) = (new_actual_scaled IS NULL)),
        CHECK ({" OR ".join(f"old_{f} IS NOT new_{f}" for f in SNAPSHOT_FIELDS)})
    ) STRICT""")
    statements.extend(
        _immutable(
            "one_shot_corrections",
            unique="id = NEW.id OR (prediction_id = NEW.prediction_id AND sequence = NEW.sequence)",
        )
    )
    statements.append("""CREATE VIEW one_shot_original_facts AS
        SELECT p.id AS prediction_id, b.probability_percent,
            q.q05_scaled, q.q25_scaled, q.q50_scaled, q.q75_scaled, q.q95_scaled,
            f.wall AS forecast_wall, f.approximate AS forecast_approximate, f.offset AS forecast_offset,
            r.outcome, n.actual_scaled,
            a.wall AS reveal_wall, COALESCE(a.approximate, 0) AS reveal_approximate, a.offset AS reveal_offset,
            CASE p.prediction_type WHEN 'binary' THEN r.resolution_notes ELSE n.resolution_notes END AS resolution_notes,
            CASE p.prediction_type WHEN 'binary' THEN r.postmortem ELSE n.postmortem END AS postmortem
        FROM predictions p JOIN one_shot_forecast_times f ON f.prediction_id = p.id
        LEFT JOIN forecast_revisions b ON b.prediction_id = p.id AND b.sequence = 1
        LEFT JOIN numeric_quantile_revisions q ON q.prediction_id = p.id AND q.sequence = 1
        LEFT JOIN resolutions r ON r.prediction_id = p.id
        LEFT JOIN numeric_resolutions n ON n.prediction_id = p.id
        LEFT JOIN one_shot_answer_times a ON a.prediction_id = p.id""")
    # A forecast may have been corrected while waiting. Adding the original answer
    # later must not cause that correction's blank answer to hide the new answer.
    projection = []
    for field in SNAPSHOT_FIELDS:
        alias = "f" if field in FORECAST_FIELDS else "a"
        projection.append(
            f"CASE WHEN {alias}.id IS NULL THEN o.{field} ELSE {alias}.new_{field} END AS {field}"
        )
    statements.append(f"""CREATE VIEW one_shot_effective_facts AS
        SELECT o.prediction_id, {", ".join(projection)} FROM one_shot_original_facts o
        LEFT JOIN one_shot_corrections f ON f.id = (SELECT id FROM one_shot_corrections WHERE prediction_id = o.prediction_id ORDER BY sequence DESC LIMIT 1)
        LEFT JOIN one_shot_corrections a ON a.id = (SELECT id FROM one_shot_corrections WHERE prediction_id = o.prediction_id AND (new_outcome IS NOT NULL OR new_actual_scaled IS NOT NULL) ORDER BY sequence DESC LIMIT 1)""")
    statements.append(f"""CREATE TRIGGER one_shot_corrections_require_current BEFORE INSERT ON one_shot_corrections
        WHEN NEW.sequence != COALESCE((SELECT MAX(sequence) FROM one_shot_corrections WHERE prediction_id = NEW.prediction_id), 0) + 1
        OR NOT EXISTS (SELECT 1 FROM one_shot_effective_facts WHERE prediction_id = NEW.prediction_id AND
            {" AND ".join(f"NEW.old_{f} IS {f}" for f in SNAPSHOT_FIELDS)})
        OR NEW.corrected_at < (SELECT created_at FROM predictions WHERE id = NEW.prediction_id)
        OR NEW.corrected_at < (SELECT MAX(corrected_at) FROM one_shot_corrections WHERE prediction_id = NEW.prediction_id)
        OR NEW.corrected_at < (SELECT resolved_at FROM resolutions WHERE prediction_id = NEW.prediction_id)
        OR NEW.corrected_at < (SELECT resolved_at FROM numeric_resolutions WHERE prediction_id = NEW.prediction_id)
        BEGIN SELECT RAISE(ABORT, 'One-Shot correction requires current facts, next sequence, and app time'); END""")
    quantities = ["new_" + f for f in (*FORECAST_FIELDS[1:6], "actual_scaled")]
    statements.append(f"""CREATE TRIGGER one_shot_corrections_integral BEFORE INSERT ON one_shot_corrections
        WHEN (SELECT value_constraint FROM numeric_quantile_definitions WHERE prediction_id = NEW.prediction_id) = 'whole-number'
        AND EXISTS (SELECT 1 FROM predictions WHERE id = NEW.prediction_id AND (
            {" OR ".join(f"NEW.{f} % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0" for f in quantities)}))
        BEGIN SELECT RAISE(ABORT, 'whole-number corrections must be integral'); END""")
    return tuple(statements)
