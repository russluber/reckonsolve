"""Schema 18: fixed five-quantile revisions and explicit shared-history anchors.

Rebuild only the three anchor tables and their referencing correction tables.
Unchanged DDL is drawn from the frozen, already shipped migration statements,
not from user-editable live sqlite_schema. No foreign-key disabling or writable
schema is involved, and all copies/drops/recreation share the migration transaction.
"""

import re


def _instant(column: str) -> str:
    return f"""{column} TEXT NOT NULL CHECK (
        length({column}) = 27 AND {column} GLOB
        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
        AND substr({column}, 1, 4) BETWEEN '0001' AND '9999'
        AND substr({column}, 12, 2) BETWEEN '00' AND '23'
        AND COALESCE(date(substr({column}, 1, 10), '+0 days') = substr({column}, 1, 10), 0)
    )"""


def _immutable(table: str, *, unique: str = "") -> tuple[str, ...]:
    return (
        f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table}
        BEGIN SELECT RAISE(ABORT, 'saved quantile facts are immutable'); END""",
        f"""CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table}
        WHEN EXISTS (SELECT 1 FROM {table} WHERE {unique or "id = NEW.id"})
        BEGIN SELECT RAISE(ABORT, 'saved quantile facts cannot be replaced'); END""",
        f"""CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}
        WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
        BEGIN SELECT RAISE(ABORT, 'saved quantile facts cannot be deleted'); END""",
    )


def build_m50_statements(prior_statements: tuple[str, ...]) -> tuple[str, ...]:
    """Compose one frozen successor to schema 17; never modify earlier migrations."""
    ddl = {}
    for statement in prior_statements:
        normalized = " ".join(statement.split())
        match = re.match(r"CREATE (?:UNIQUE )?(TABLE|INDEX|TRIGGER) (\w+)", normalized)
        if match:
            ddl[match[2]] = normalized
        match = re.match(r"DROP (?:TABLE|INDEX|TRIGGER) (\w+)", normalized)
        if match:
            ddl.pop(match[1], None)
        if normalized.startswith(
            "ALTER TABLE numeric_resolutions ADD COLUMN effective_resolution_at"
        ):
            column = normalized.split(" ADD COLUMN ", 1)[1]
            ddl["numeric_resolutions"] = ddl["numeric_resolutions"].replace(
                "FOREIGN KEY (prediction_id, scoring_revision_id)",
                column + ", FOREIGN KEY (prediction_id, scoring_revision_id)",
            )

    tables = {
        "journal_entries": "id, prediction_id, forecast_revision_id, numeric_forecast_revision_id, body, created_at",
        "forecast_reviews": "id, prediction_id, forecast_revision_id, numeric_forecast_revision_id, note, created_at",
        "numeric_resolutions": "id, prediction_id, actual_scaled, resolved_at, scoring_revision_id, resolution_notes, postmortem, effective_resolution_at",
        "journal_entry_corrections": "id, prediction_id, journal_entry_id, sequence, body, corrected_at",
        "numeric_resolution_corrections": "id, prediction_id, numeric_resolution_id, sequence, old_actual_scaled, new_actual_scaled, old_resolution_notes, new_resolution_notes, old_postmortem, new_postmortem, actual_value_changed, resolution_notes_changed, postmortem_changed, correction_reason, corrected_at",
        "numeric_quantile_resolution_corrections": "id, prediction_id, numeric_resolution_id, sequence, old_actual_scaled, new_actual_scaled, old_effective_resolution_at, new_effective_resolution_at, old_resolution_notes, new_resolution_notes, old_postmortem, new_postmortem, actual_value_changed, effective_time_changed, resolution_notes_changed, postmortem_changed, correction_reason, corrected_at",
    }
    attached = {
        name: sql
        for name, sql in ddl.items()
        if re.match(r"CREATE (?:UNIQUE )?(?:INDEX|TRIGGER) ", sql)
        and any(re.search(rf"\bON {table}\b", sql) for table in tables)
    }
    statements = list(FOUNDATION)
    # Snapshot before removing any guard; child-first drop avoids foreign-key cascades.
    for table in tables:
        statements.append(f"CREATE TABLE m50_copy_{table} AS SELECT * FROM {table}")
    for name, sql in attached.items():
        if sql.startswith("CREATE TRIGGER"):
            statements.append(f"DROP TRIGGER {name}")
    for table in reversed(tables):
        statements.append(f"DROP TABLE {table}")
    for table, columns in tables.items():
        sql = ddl[table]
        if table in {"journal_entries", "forecast_reviews"}:
            sql = sql.replace(
                "numeric_forecast_revision_id INTEGER,",
                "numeric_forecast_revision_id INTEGER, quantile_revision_id INTEGER,",
            )
            sql = sql.replace(
                "(forecast_revision_id IS NOT NULL) != (numeric_forecast_revision_id IS NOT NULL)",
                "(forecast_revision_id IS NOT NULL) + (numeric_forecast_revision_id IS NOT NULL) + (quantile_revision_id IS NOT NULL) = 1",
            )
            sql = (
                sql.removesuffix(") STRICT")
                + """, FOREIGN KEY (prediction_id, quantile_revision_id)
                REFERENCES numeric_quantile_revisions(prediction_id, id) ON DELETE CASCADE) STRICT"""
            )
        elif table == "numeric_resolutions":
            sql = sql.replace(
                "scoring_revision_id INTEGER NOT NULL,",
                "scoring_revision_id INTEGER, quantile_revision_id INTEGER,",
            )
            sql = (
                sql.removesuffix(") STRICT")
                + """, UNIQUE(prediction_id, id), CHECK ((scoring_revision_id IS NOT NULL) != (quantile_revision_id IS NOT NULL)),
                FOREIGN KEY (prediction_id, quantile_revision_id) REFERENCES numeric_quantile_revisions(prediction_id, id) ON DELETE CASCADE) STRICT"""
            )
        statements.append(sql)
        statements.append(
            f"INSERT INTO {table} ({columns}) SELECT {columns} FROM m50_copy_{table}"
        )
    for table in reversed(tables):
        statements.append(f"DROP TABLE m50_copy_{table}")
    for name, sql in attached.items():
        if name in {
            "journal_entries_require_current_type_revision",
            "forecast_reviews_require_current_type_revision",
            "numeric_resolutions_require_current_scoring_revision",
        }:
            continue
        statements.append(sql)
    for table, legacy_column in (
        ("journal_entries", "numeric_forecast_revision_id"),
        ("forecast_reviews", "numeric_forecast_revision_id"),
        ("numeric_resolutions", "scoring_revision_id"),
    ):
        binary = (
            "NULL" if table == "numeric_resolutions" else "NEW.forecast_revision_id"
        )
        statements.append(f"""
            CREATE TRIGGER {table}_require_model_anchor BEFORE INSERT ON {table}
            WHEN CASE (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id)
                WHEN 'binary-final-v1' THEN {binary} IS NOT (SELECT id FROM forecast_revisions WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1) OR {binary} IS NULL
                WHEN 'binary-trajectory-v1' THEN {binary} IS NOT (SELECT id FROM forecast_revisions WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1) OR {binary} IS NULL
                WHEN 'numeric-interval-v1' THEN NEW.{legacy_column} IS NOT (SELECT id FROM numeric_forecast_revisions WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1) OR NEW.{legacy_column} IS NULL
                WHEN 'numeric-quantiles-5-v2' THEN NEW.quantile_revision_id IS NOT (SELECT id FROM numeric_quantile_revisions WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1) OR NEW.quantile_revision_id IS NULL
                ELSE 1 END
            BEGIN SELECT RAISE(ABORT, 'history must reference the current forecast revision for its model'); END
        """)
        statements.append(
            f"CREATE INDEX {table}_by_quantile_anchor ON {table} (prediction_id, quantile_revision_id)"
        )
    statements.extend(FINAL_GUARDS)
    # The completion guard must see the latest model-appropriate Postmortem.
    statements.extend(
        (
            """CREATE VIEW numeric_resolution_history_rows AS
        SELECT id, prediction_id, sequence, new_postmortem FROM numeric_resolution_corrections
        UNION ALL SELECT id, prediction_id, sequence, new_postmortem FROM numeric_quantile_resolution_corrections""",
            "DROP TRIGGER postmortem_completions_require_blank_resolved_postmortem",
            ddl["postmortem_completions_require_blank_resolved_postmortem"].replace(
                "numeric_resolution_corrections", "numeric_resolution_history_rows"
            ),
        )
    )
    return tuple(statements)


FOUNDATION = (
    """CREATE TABLE numeric_quantile_definitions (
        prediction_id INTEGER PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
        value_constraint TEXT NOT NULL CHECK (value_constraint IN ('continuous', 'whole-number'))
    ) STRICT""",
    """CREATE TRIGGER numeric_quantile_definitions_require_contract
    BEFORE INSERT ON numeric_quantile_definitions
    WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) IS NOT 'numeric-quantiles-5-v2'
    BEGIN SELECT RAISE(ABORT, 'quantile definition requires the Numeric v2 contract'); END""",
    *_immutable(
        "numeric_quantile_definitions", unique="prediction_id = NEW.prediction_id"
    ),
    f"""CREATE TABLE numeric_quantile_revisions (
        id INTEGER PRIMARY KEY,
        prediction_id INTEGER NOT NULL REFERENCES numeric_quantile_definitions(prediction_id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL CHECK(sequence >= 1),
        {_instant("created_at")},
        q05_scaled INTEGER NOT NULL CHECK(q05_scaled BETWEEN -999999999999999999 AND 999999999999999999),
        q25_scaled INTEGER NOT NULL CHECK(q25_scaled BETWEEN -999999999999999999 AND 999999999999999999),
        q50_scaled INTEGER NOT NULL CHECK(q50_scaled BETWEEN -999999999999999999 AND 999999999999999999),
        q75_scaled INTEGER NOT NULL CHECK(q75_scaled BETWEEN -999999999999999999 AND 999999999999999999),
        q95_scaled INTEGER NOT NULL CHECK(q95_scaled BETWEEN -999999999999999999 AND 999999999999999999),
        rationale TEXT CHECK(rationale IS NULL OR (length(rationale) > 0 AND rationale = trim(rationale, char(9)||char(10)||char(11)||char(12)||char(13)||' ') AND instr(rationale, char(0)) = 0)),
        CHECK(q05_scaled <= q25_scaled AND q25_scaled <= q50_scaled AND q50_scaled <= q75_scaled AND q75_scaled <= q95_scaled),
        UNIQUE(prediction_id, sequence), UNIQUE(prediction_id, id)
    ) STRICT""",
    *_immutable(
        "numeric_quantile_revisions",
        unique="id = NEW.id OR (prediction_id = NEW.prediction_id AND sequence = NEW.sequence)",
    ),
    """CREATE INDEX numeric_quantile_revisions_latest ON numeric_quantile_revisions(prediction_id, sequence DESC)""",
    """CREATE TRIGGER quantile_revision_requires_active_ordered_contract
    BEFORE INSERT ON numeric_quantile_revisions
    WHEN (SELECT status FROM predictions WHERE id = NEW.prediction_id) IS NOT 'open'
        OR NEW.sequence != COALESCE((SELECT MAX(sequence) FROM numeric_quantile_revisions WHERE prediction_id = NEW.prediction_id), 0) + 1
        OR NEW.created_at >= (SELECT forecast_deadline_at FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id)
        OR (NEW.sequence = 1 AND NEW.created_at IS NOT (SELECT created_at FROM predictions WHERE id = NEW.prediction_id))
        OR NEW.created_at <= (SELECT created_at FROM numeric_quantile_revisions WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1)
        OR EXISTS (SELECT 1 FROM numeric_quantile_revisions WHERE prediction_id = NEW.prediction_id AND sequence = NEW.sequence - 1
            AND q05_scaled = NEW.q05_scaled AND q25_scaled = NEW.q25_scaled AND q50_scaled = NEW.q50_scaled AND q75_scaled = NEW.q75_scaled AND q95_scaled = NEW.q95_scaled)
    BEGIN SELECT RAISE(ABORT, 'quantile revision requires changed values, contiguous sequence, and strictly increasing pre-Deadline time'); END""",
    """CREATE TRIGGER quantile_revision_requires_integral_values
    BEFORE INSERT ON numeric_quantile_revisions
    WHEN (SELECT value_constraint FROM numeric_quantile_definitions WHERE prediction_id = NEW.prediction_id) = 'whole-number'
        AND EXISTS (SELECT 1 FROM predictions WHERE id = NEW.prediction_id AND (
            NEW.q05_scaled % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0 OR
            NEW.q25_scaled % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0 OR
            NEW.q50_scaled % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0 OR
            NEW.q75_scaled % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0 OR
            NEW.q95_scaled % CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) != 0))
    BEGIN SELECT RAISE(ABORT, 'whole-number quantiles must be integral'); END""",
    """CREATE TRIGGER legacy_numeric_revisions_require_legacy_contract
    BEFORE INSERT ON numeric_forecast_revisions
    WHEN (SELECT forecast_model FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id) IS NOT 'numeric-interval-v1'
    BEGIN SELECT RAISE(ABORT, 'interval revisions require a legacy Numeric contract'); END""",
    """CREATE TRIGGER quantile_revisions_dirty_search AFTER INSERT ON numeric_quantile_revisions
    BEGIN INSERT OR IGNORE INTO search_dirty_predictions(prediction_id) VALUES(NEW.prediction_id); END""",
)


FINAL_GUARDS = (
    """CREATE TRIGGER quantile_resolution_requires_recorded_order BEFORE INSERT ON numeric_resolutions
    WHEN NEW.quantile_revision_id IS NOT NULL AND NEW.resolved_at < (SELECT created_at FROM numeric_quantile_revisions WHERE id = NEW.quantile_revision_id)
    BEGIN SELECT RAISE(ABORT, 'Resolution recorded-at cannot precede its forecast context'); END""",
    """CREATE TRIGGER quantile_reviews_require_pre_deadline_time BEFORE INSERT ON forecast_reviews
    WHEN NEW.quantile_revision_id IS NOT NULL AND (
        NEW.created_at >= (SELECT forecast_deadline_at FROM prediction_forecast_contracts WHERE prediction_id = NEW.prediction_id)
        OR NEW.created_at < (SELECT created_at FROM numeric_quantile_revisions WHERE id = NEW.quantile_revision_id))
    BEGIN SELECT RAISE(ABORT, 'quantile Review must precede Deadline and follow its forecast'); END""",
    """CREATE TRIGGER quantile_resolution_requires_integral_value BEFORE INSERT ON numeric_resolutions
    WHEN (SELECT value_constraint FROM numeric_quantile_definitions WHERE prediction_id = NEW.prediction_id) = 'whole-number'
    AND NEW.actual_scaled % (SELECT CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) FROM predictions WHERE id = NEW.prediction_id) != 0
    BEGIN SELECT RAISE(ABORT, 'whole-number actual must be integral'); END""",
    """CREATE TRIGGER quantile_correction_requires_integral_value BEFORE INSERT ON numeric_quantile_resolution_corrections
    WHEN (SELECT value_constraint FROM numeric_quantile_definitions WHERE prediction_id = NEW.prediction_id) = 'whole-number'
    AND NEW.new_actual_scaled % (SELECT CAST('1' || substr('000000', 1, numeric_precision) AS INTEGER) FROM predictions WHERE id = NEW.prediction_id) != 0
    BEGIN SELECT RAISE(ABORT, 'whole-number corrected actual must be integral'); END""",
    """CREATE TRIGGER quantile_corrections_dirty_search AFTER INSERT ON numeric_quantile_resolution_corrections
    BEGIN INSERT OR IGNORE INTO search_dirty_predictions(prediction_id) VALUES(NEW.prediction_id); END""",
)
