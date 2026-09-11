"""Schema 17: shared Binary terminal-text reads, never shared scoring cohorts."""

M48_STATEMENTS = (
    """
    CREATE VIEW binary_resolution_history_rows AS
    SELECT id, prediction_id, resolution_id, sequence,
        old_outcome, new_outcome, old_resolution_notes, new_resolution_notes,
        old_postmortem, new_postmortem, outcome_changed, resolution_notes_changed,
        postmortem_changed, correction_reason, corrected_at,
        NULL AS old_effective_resolution_at, NULL AS new_effective_resolution_at,
        0 AS effective_time_changed
    FROM resolution_corrections
    UNION ALL
    SELECT id, prediction_id, resolution_id, sequence,
        old_outcome, new_outcome, old_resolution_notes, new_resolution_notes,
        old_postmortem, new_postmortem, outcome_changed, resolution_notes_changed,
        postmortem_changed, correction_reason, corrected_at,
        old_effective_resolution_at, new_effective_resolution_at, effective_time_changed
    FROM binary_trajectory_resolution_corrections
    """,
    """
    CREATE TRIGGER trajectory_corrections_dirty_search
    AFTER INSERT ON binary_trajectory_resolution_corrections
    BEGIN
        INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
        VALUES (NEW.prediction_id);
    END
    """,
    "DROP TRIGGER postmortem_completions_require_blank_resolved_postmortem",
    """
    CREATE TRIGGER postmortem_completions_require_blank_resolved_postmortem
    BEFORE INSERT ON postmortem_completions
    WHEN (SELECT status FROM predictions WHERE id = NEW.prediction_id) IS NOT 'resolved'
    OR CASE (SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id)
        WHEN 'binary' THEN CASE WHEN EXISTS (
            SELECT 1 FROM binary_resolution_history_rows WHERE prediction_id = NEW.prediction_id
        ) THEN (
            SELECT new_postmortem FROM binary_resolution_history_rows
            WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1
        ) ELSE (SELECT postmortem FROM resolutions WHERE prediction_id = NEW.prediction_id) END
        WHEN 'numeric' THEN CASE WHEN EXISTS (
            SELECT 1 FROM numeric_resolution_corrections WHERE prediction_id = NEW.prediction_id
        ) THEN (
            SELECT new_postmortem FROM numeric_resolution_corrections
            WHERE prediction_id = NEW.prediction_id ORDER BY sequence DESC LIMIT 1
        ) ELSE (SELECT postmortem FROM numeric_resolutions WHERE prediction_id = NEW.prediction_id) END
    END IS NOT NULL
    BEGIN
        SELECT RAISE(ABORT, 'postmortem completion requires a blank resolved postmortem');
    END
    """,
    """
    INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
    SELECT DISTINCT prediction_id FROM binary_trajectory_resolution_corrections
    """,
)
