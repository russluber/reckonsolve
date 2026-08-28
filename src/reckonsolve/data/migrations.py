"""Ordered, transactional SQLite schema migrations."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass


class MigrationError(RuntimeError):
    """Base class for migration failures detected by Reckonsolve."""


class MigrationConfigurationError(MigrationError):
    """Raised when the migrations bundled with the application are invalid."""


class InvalidMigrationHistoryError(MigrationError):
    """Raised when recorded migration history is missing or inconsistent."""


class UnrecognizedDatabaseError(MigrationError):
    """Raised when a SQLite database does not belong to Reckonsolve."""


class UnsupportedSchemaVersionError(MigrationError):
    """Raised when a database was created by a newer application version."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable schema migration, applied statement by statement."""

    version: int
    name: str
    statements: tuple[str, ...]


MIGRATION_TABLE_SQL = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version >= 1),
    name TEXT NOT NULL UNIQUE
) STRICT
"""


MIGRATIONS = (
    Migration(
        version=1,
        name="initialize migration tracking",
        statements=(MIGRATION_TABLE_SQL,),
    ),
    Migration(
        version=2,
        name="add binary predictions and forecast revisions",
        statements=(
            """
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY,
                question TEXT NOT NULL
                    CHECK (length(question) > 0 AND question = trim(question)),
                prediction_type TEXT NOT NULL DEFAULT 'binary'
                    CHECK (prediction_type = 'binary'),
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved', 'invalid')),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                updated_at TEXT NOT NULL
                    CHECK (
                        length(updated_at) = 27
                        AND updated_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(updated_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(updated_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(updated_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(updated_at, 1, 10),
                            0
                        )
                    )
            ) STRICT
            """,
            """
            CREATE TABLE forecast_revisions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                probability_percent INTEGER NOT NULL
                    CHECK (
                        typeof(probability_percent) = 'integer'
                        AND probability_percent BETWEEN 0 AND 100
                ),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                sequence INTEGER NOT NULL CHECK (sequence >= 1),
                UNIQUE (prediction_id, sequence)
            ) STRICT
            """,
            """
            CREATE INDEX forecast_revisions_latest_by_prediction
            ON forecast_revisions (prediction_id, sequence DESC)
            """,
            """
            CREATE TRIGGER forecast_revisions_are_immutable
            BEFORE UPDATE ON forecast_revisions
            BEGIN
                SELECT RAISE(ABORT, 'saved forecast revisions are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=3,
        name="add prediction metadata and definition history",
        statements=(
            """
            ALTER TABLE predictions ADD COLUMN metadata_version INTEGER NOT NULL
                DEFAULT 1
                CHECK (
                    typeof(metadata_version) = 'integer'
                    AND metadata_version >= 1
                )
            """,
            """
            ALTER TABLE predictions ADD COLUMN background TEXT
                CHECK (background IS NULL OR (
                    length(background) > 0 AND background = trim(background)
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN resolution_criteria TEXT
                CHECK (resolution_criteria IS NULL OR (
                    length(resolution_criteria) > 0
                    AND resolution_criteria = trim(resolution_criteria)
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN forecast_deadline TEXT
                CHECK (forecast_deadline IS NULL OR (
                    length(forecast_deadline) = 10
                    AND forecast_deadline GLOB
                        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                    AND forecast_deadline BETWEEN '1752-09-14' AND '9999-12-31'
                    AND COALESCE(
                        date(forecast_deadline || 'T00:00:00Z', '+0 days')
                            = forecast_deadline,
                        0
                    )
                ))
            """,
            """
            ALTER TABLE predictions ADD COLUMN expected_resolution TEXT
                CHECK (expected_resolution IS NULL OR (
                    length(expected_resolution) = 10
                    AND expected_resolution GLOB
                        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                    AND expected_resolution BETWEEN '1752-09-14' AND '9999-12-31'
                    AND COALESCE(
                        date(expected_resolution || 'T00:00:00Z', '+0 days')
                            = expected_resolution,
                        0
                    )
                ))
            """,
            """
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL
                    CHECK (
                        length(display_name) > 0
                        AND display_name = trim(display_name)
                        AND instr(display_name, ',') = 0
                        AND instr(display_name, char(10)) = 0
                        AND instr(display_name, char(13)) = 0
                    ),
                normalized_name TEXT NOT NULL UNIQUE
                    CHECK (
                        length(normalized_name) > 0
                        AND normalized_name = trim(normalized_name)
                        AND instr(normalized_name, ',') = 0
                        AND instr(normalized_name, char(10)) = 0
                        AND instr(normalized_name, char(13)) = 0
                    )
            ) STRICT
            """,
            """
            CREATE TABLE prediction_tags (
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
                PRIMARY KEY (prediction_id, tag_id)
            ) WITHOUT ROWID, STRICT
            """,
            """
            CREATE INDEX prediction_tags_by_tag
            ON prediction_tags (tag_id, prediction_id)
            """,
            """
            CREATE TABLE prediction_definition_changes (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                changed_at TEXT NOT NULL
                    CHECK (
                        length(changed_at) = 27
                        AND changed_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(changed_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(changed_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(changed_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(changed_at, 1, 10),
                            0
                        )
                    ),
                old_question TEXT NOT NULL
                    CHECK (
                        length(old_question) > 0
                        AND old_question = trim(old_question)
                    ),
                new_question TEXT NOT NULL
                    CHECK (
                        length(new_question) > 0
                        AND new_question = trim(new_question)
                    ),
                old_resolution_criteria TEXT
                    CHECK (old_resolution_criteria IS NULL OR (
                        length(old_resolution_criteria) > 0
                        AND old_resolution_criteria = trim(old_resolution_criteria)
                    )),
                new_resolution_criteria TEXT
                    CHECK (new_resolution_criteria IS NULL OR (
                        length(new_resolution_criteria) > 0
                        AND new_resolution_criteria = trim(new_resolution_criteria)
                    )),
                old_forecast_deadline TEXT
                    CHECK (old_forecast_deadline IS NULL OR (
                        length(old_forecast_deadline) = 10
                        AND old_forecast_deadline GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                        AND old_forecast_deadline
                            BETWEEN '1752-09-14' AND '9999-12-31'
                        AND COALESCE(
                            date(
                                old_forecast_deadline || 'T00:00:00Z',
                                '+0 days'
                            ) = old_forecast_deadline,
                            0
                        )
                    )),
                new_forecast_deadline TEXT
                    CHECK (new_forecast_deadline IS NULL OR (
                        length(new_forecast_deadline) = 10
                        AND new_forecast_deadline GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                        AND new_forecast_deadline
                            BETWEEN '1752-09-14' AND '9999-12-31'
                        AND COALESCE(
                            date(
                                new_forecast_deadline || 'T00:00:00Z',
                                '+0 days'
                            ) = new_forecast_deadline,
                            0
                        )
                    )),
                CHECK (
                    old_question IS NOT new_question
                    OR old_resolution_criteria IS NOT new_resolution_criteria
                    OR old_forecast_deadline IS NOT new_forecast_deadline
                )
            ) STRICT
            """,
            """
            CREATE INDEX prediction_definition_changes_by_prediction
            ON prediction_definition_changes (prediction_id, id)
            """,
            """
            CREATE TRIGGER prediction_definition_changes_are_immutable
            BEFORE UPDATE ON prediction_definition_changes
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_definition_changes_reject_id_reuse
            BEFORE INSERT ON prediction_definition_changes
            WHEN EXISTS (
                SELECT 1
                FROM prediction_definition_changes
                WHERE id = NEW.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_definition_changes_reject_direct_delete
            BEFORE DELETE ON prediction_definition_changes
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved definition changes are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=4,
        name="add forecast revision rationale and immutability guards",
        statements=(
            """
            ALTER TABLE forecast_revisions ADD COLUMN rationale TEXT
                CHECK (rationale IS NULL OR (
                    length(rationale) > 0
                    AND rationale = trim(rationale)
                    AND instr(rationale, char(0)) = 0
                ))
            """,
            """
            CREATE TRIGGER forecast_revisions_reject_history_replacement
            BEFORE INSERT ON forecast_revisions
            WHEN EXISTS (
                SELECT 1 FROM forecast_revisions WHERE id = NEW.id
            )
            OR EXISTS (
                SELECT 1
                FROM forecast_revisions
                WHERE prediction_id = NEW.prediction_id
                    AND sequence = NEW.sequence
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved forecast revisions are immutable');
            END
            """,
            """
            CREATE TRIGGER forecast_revisions_reject_direct_delete
            BEFORE DELETE ON forecast_revisions
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved forecast revisions are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=5,
        name="add journal entries and transparent corrections",
        statements=(
            """
            CREATE UNIQUE INDEX forecast_revisions_prediction_identity
            ON forecast_revisions (prediction_id, id)
            """,
            """
            CREATE TABLE journal_entries (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                forecast_revision_id INTEGER NOT NULL,
                body TEXT NOT NULL
                    CHECK (
                        length(body) > 0
                        AND body = trim(
                            body,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(body, char(0)) = 0
                    ),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                UNIQUE (prediction_id, id),
                FOREIGN KEY (prediction_id, forecast_revision_id)
                    REFERENCES forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE
            ) STRICT
            """,
            """
            CREATE INDEX journal_entries_by_prediction_anchor
            ON journal_entries (prediction_id, forecast_revision_id, created_at, id)
            """,
            """
            CREATE TRIGGER journal_entries_require_current_revision
            BEFORE INSERT ON journal_entries
            WHEN NEW.forecast_revision_id IS NOT (
                SELECT id
                FROM forecast_revisions
                WHERE prediction_id = NEW.prediction_id
                ORDER BY sequence DESC
                LIMIT 1
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'journal entries must reference the current forecast revision'
                );
            END
            """,
            """
            CREATE TRIGGER journal_entries_require_open_prediction
            BEFORE INSERT ON journal_entries
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'new journal entries require an open or locked prediction'
                );
            END
            """,
            """
            CREATE TRIGGER journal_entries_are_immutable
            BEFORE UPDATE ON journal_entries
            BEGIN
                SELECT RAISE(ABORT, 'saved journal entries are immutable');
            END
            """,
            """
            CREATE TRIGGER journal_entries_reject_history_replacement
            BEFORE INSERT ON journal_entries
            WHEN EXISTS (
                SELECT 1 FROM journal_entries WHERE id = NEW.id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved journal entries are immutable');
            END
            """,
            """
            CREATE TRIGGER journal_entries_reject_direct_delete
            BEFORE DELETE ON journal_entries
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved journal entries are immutable');
            END
            """,
            """
            CREATE TABLE journal_entry_corrections (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL,
                journal_entry_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL
                    CHECK (typeof(sequence) = 'integer' AND sequence >= 1),
                body TEXT NOT NULL
                    CHECK (
                        length(body) > 0
                        AND body = trim(
                            body,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(body, char(0)) = 0
                    ),
                corrected_at TEXT NOT NULL
                    CHECK (
                        length(corrected_at) = 27
                        AND corrected_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(corrected_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(corrected_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(corrected_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(corrected_at, 1, 10),
                            0
                        )
                    ),
                FOREIGN KEY (prediction_id, journal_entry_id)
                    REFERENCES journal_entries(prediction_id, id)
                    ON DELETE CASCADE,
                UNIQUE (journal_entry_id, sequence)
            ) STRICT
            """,
            """
            CREATE INDEX journal_entry_corrections_by_entry
            ON journal_entry_corrections (journal_entry_id, sequence)
            """,
            """
            CREATE TRIGGER journal_entry_corrections_require_changed_body
            BEFORE INSERT ON journal_entry_corrections
            WHEN NEW.body = COALESCE(
                (
                    SELECT body
                    FROM journal_entry_corrections
                    WHERE journal_entry_id = NEW.journal_entry_id
                    ORDER BY sequence DESC
                    LIMIT 1
                ),
                (
                    SELECT body
                    FROM journal_entries
                    WHERE id = NEW.journal_entry_id
                )
            )
            BEGIN
                SELECT RAISE(ABORT, 'a journal correction must change the text');
            END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_require_next_sequence
            BEFORE INSERT ON journal_entry_corrections
            WHEN NEW.sequence != COALESCE(
                (
                    SELECT MAX(sequence)
                    FROM journal_entry_corrections
                    WHERE journal_entry_id = NEW.journal_entry_id
                ),
                0
            ) + 1
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'journal correction sequence must be contiguous'
                );
            END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_are_immutable
            BEFORE UPDATE ON journal_entry_corrections
            BEGIN
                SELECT RAISE(ABORT, 'saved journal corrections are immutable');
            END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_reject_history_replacement
            BEFORE INSERT ON journal_entry_corrections
            WHEN EXISTS (
                SELECT 1 FROM journal_entry_corrections WHERE id = NEW.id
            )
            OR EXISTS (
                SELECT 1
                FROM journal_entry_corrections
                WHERE journal_entry_id = NEW.journal_entry_id
                    AND sequence = NEW.sequence
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved journal corrections are immutable');
            END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_reject_direct_delete
            BEFORE DELETE ON journal_entry_corrections
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved journal corrections are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=6,
        name="add terminal lifecycle records and guarded transitions",
        statements=(
            """
            CREATE TABLE migration_v6_requires_nonterminal_predictions (
                sentinel INTEGER NOT NULL CHECK (sentinel = 1)
            ) STRICT
            """,
            """
            INSERT INTO migration_v6_requires_nonterminal_predictions (sentinel)
            SELECT 0 FROM predictions WHERE status != 'open'
            """,
            """
            DROP TABLE migration_v6_requires_nonterminal_predictions
            """,
            """
            CREATE TABLE resolutions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL UNIQUE
                    REFERENCES predictions(id) ON DELETE CASCADE,
                outcome TEXT NOT NULL CHECK (outcome IN ('yes', 'no')),
                resolved_at TEXT NOT NULL
                    CHECK (
                        length(resolved_at) = 27
                        AND resolved_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(resolved_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(resolved_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(resolved_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(resolved_at, 1, 10),
                            0
                        )
                    ),
                scoring_revision_id INTEGER NOT NULL,
                resolution_notes TEXT
                    CHECK (resolution_notes IS NULL OR (
                        length(resolution_notes) > 0
                        AND resolution_notes = trim(
                            resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(resolution_notes, char(0)) = 0
                    )),
                postmortem TEXT
                    CHECK (postmortem IS NULL OR (
                        length(postmortem) > 0
                        AND postmortem = trim(
                            postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(postmortem, char(0)) = 0
                    )),
                FOREIGN KEY (prediction_id, scoring_revision_id)
                    REFERENCES forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE
            ) STRICT
            """,
            """
            CREATE INDEX resolutions_by_resolved_at
            ON resolutions (resolved_at, id)
            """,
            """
            CREATE TABLE prediction_invalidations (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL UNIQUE
                    REFERENCES predictions(id) ON DELETE CASCADE,
                invalidated_at TEXT NOT NULL
                    CHECK (
                        length(invalidated_at) = 27
                        AND invalidated_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(invalidated_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(invalidated_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(invalidated_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(invalidated_at, 1, 10),
                            0
                        )
                    ),
                reason TEXT
                    CHECK (reason IS NULL OR (
                        length(reason) > 0
                        AND reason = trim(
                            reason,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(reason, char(0)) = 0
                    ))
            ) STRICT
            """,
            """
            CREATE TRIGGER resolutions_require_open_prediction
            BEFORE INSERT ON resolutions
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'only an open or locked prediction can be resolved'
                );
            END
            """,
            """
            CREATE TRIGGER resolutions_require_current_scoring_revision
            BEFORE INSERT ON resolutions
            WHEN NEW.scoring_revision_id IS NOT (
                SELECT id
                FROM forecast_revisions
                WHERE prediction_id = NEW.prediction_id
                ORDER BY sequence DESC
                LIMIT 1
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'resolution must capture the current forecast revision'
                );
            END
            """,
            """
            CREATE TRIGGER prediction_invalidations_require_open_prediction
            BEFORE INSERT ON prediction_invalidations
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'only an open or locked prediction can be marked invalid'
                );
            END
            """,
            """
            CREATE TRIGGER predictions_terminal_status_is_immutable
            BEFORE UPDATE OF status ON predictions
            WHEN OLD.status IN ('resolved', 'invalid')
                AND NEW.status IS NOT OLD.status
            BEGIN
                SELECT RAISE(ABORT, 'terminal prediction status is immutable');
            END
            """,
            """
            CREATE TRIGGER predictions_status_requires_terminal_record
            BEFORE UPDATE OF status ON predictions
            WHEN OLD.status = 'open'
                AND (
                    (
                        NEW.status = 'resolved'
                        AND NOT EXISTS (
                            SELECT 1 FROM resolutions
                            WHERE prediction_id = NEW.id
                        )
                    )
                    OR (
                        NEW.status = 'invalid'
                        AND NOT EXISTS (
                            SELECT 1 FROM prediction_invalidations
                            WHERE prediction_id = NEW.id
                        )
                    )
                )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'terminal status requires its immutable lifecycle record'
                );
            END
            """,
            """
            CREATE TRIGGER resolutions_mark_prediction_resolved
            AFTER INSERT ON resolutions
            BEGIN
                UPDATE predictions
                SET status = 'resolved', updated_at = NEW.resolved_at
                WHERE id = NEW.prediction_id;
            END
            """,
            """
            CREATE TRIGGER prediction_invalidations_mark_prediction_invalid
            AFTER INSERT ON prediction_invalidations
            BEGIN
                UPDATE predictions
                SET status = 'invalid', updated_at = NEW.invalidated_at
                WHERE id = NEW.prediction_id;
            END
            """,
            """
            CREATE TRIGGER resolutions_are_immutable
            BEFORE UPDATE ON resolutions
            BEGIN
                SELECT RAISE(ABORT, 'saved resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER resolutions_reject_history_replacement
            BEFORE INSERT ON resolutions
            WHEN EXISTS (SELECT 1 FROM resolutions WHERE id = NEW.id)
                OR EXISTS (
                    SELECT 1 FROM resolutions
                    WHERE prediction_id = NEW.prediction_id
                )
            BEGIN
                SELECT RAISE(ABORT, 'saved resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER resolutions_reject_direct_delete
            BEFORE DELETE ON resolutions
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_invalidations_are_immutable
            BEFORE UPDATE ON prediction_invalidations
            BEGIN
                SELECT RAISE(ABORT, 'saved invalidations are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_invalidations_reject_history_replacement
            BEFORE INSERT ON prediction_invalidations
            WHEN EXISTS (
                SELECT 1 FROM prediction_invalidations WHERE id = NEW.id
            )
                OR EXISTS (
                    SELECT 1 FROM prediction_invalidations
                    WHERE prediction_id = NEW.prediction_id
                )
            BEGIN
                SELECT RAISE(ABORT, 'saved invalidations are immutable');
            END
            """,
            """
            CREATE TRIGGER prediction_invalidations_reject_direct_delete
            BEFORE DELETE ON prediction_invalidations
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved invalidations are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=7,
        name="add persisted attention settings",
        statements=(
            """
            CREATE TABLE app_settings (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                stale_threshold_days INTEGER NOT NULL
                    CHECK (
                        typeof(stale_threshold_days) = 'integer'
                        AND stale_threshold_days BETWEEN 1 AND 9999
                    )
            ) STRICT
            """,
            """
            INSERT INTO app_settings (singleton, stale_threshold_days)
            VALUES (1, 14)
            """,
        ),
    ),
    Migration(
        version=8,
        name="record last successful backup time",
        statements=(
            """
            ALTER TABLE app_settings
            ADD COLUMN last_successful_backup_at TEXT
                CHECK (last_successful_backup_at IS NULL OR (
                    length(last_successful_backup_at) = 27
                    AND last_successful_backup_at GLOB
                        '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                        || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                        || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                    AND substr(last_successful_backup_at, 1, 4)
                        BETWEEN '0001' AND '9999'
                    AND substr(last_successful_backup_at, 12, 2)
                        BETWEEN '00' AND '23'
                    AND COALESCE(
                        date(
                            substr(last_successful_backup_at, 1, 10)
                                || 'T00:00:00Z',
                            '+0 days'
                        ) = substr(last_successful_backup_at, 1, 10),
                        0
                    )
                ))
            """,
        ),
    ),
    Migration(
        version=9,
        name="add numeric prediction foundation",
        statements=(
            """
            ALTER TABLE predictions
            RENAME COLUMN prediction_type TO prediction_type_binary_legacy
            """,
            """
            ALTER TABLE predictions
            ADD COLUMN prediction_type TEXT NOT NULL DEFAULT 'binary'
                CHECK (prediction_type IN ('binary', 'numeric'))
            """,
            """
            ALTER TABLE predictions
            ADD COLUMN numeric_unit TEXT
                CHECK (
                    (
                        prediction_type = 'binary'
                        AND numeric_unit IS NULL
                    )
                    OR (
                        prediction_type = 'numeric'
                        AND numeric_unit IS NOT NULL
                        AND length(numeric_unit) > 0
                        AND numeric_unit = trim(numeric_unit)
                        AND instr(numeric_unit, char(0)) = 0
                    )
                )
            """,
            """
            ALTER TABLE predictions
            ADD COLUMN numeric_precision INTEGER
                CHECK (
                    (
                        prediction_type = 'binary'
                        AND numeric_precision IS NULL
                    )
                    OR (
                        prediction_type = 'numeric'
                        AND typeof(numeric_precision) = 'integer'
                        AND numeric_precision BETWEEN 0 AND 6
                    )
                )
            """,
            """
            ALTER TABLE predictions DROP COLUMN prediction_type_binary_legacy
            """,
            """
            CREATE TRIGGER predictions_forecast_definition_is_immutable
            BEFORE UPDATE OF prediction_type, numeric_unit, numeric_precision
            ON predictions
            WHEN OLD.prediction_type IS NOT NEW.prediction_type
                OR OLD.numeric_unit IS NOT NEW.numeric_unit
                OR OLD.numeric_precision IS NOT NEW.numeric_precision
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'prediction type, numeric unit, and precision are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER forecast_revisions_require_binary_prediction
            BEFORE INSERT ON forecast_revisions
            WHEN (
                SELECT prediction_type
                FROM predictions
                WHERE id = NEW.prediction_id
            ) IS NOT 'binary'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'binary revisions require a binary prediction'
                );
            END
            """,
            """
            CREATE TABLE numeric_forecast_revisions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                lower_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(lower_scaled) = 'integer'
                        AND lower_scaled BETWEEN
                            -999999999999999999 AND 999999999999999999
                    ),
                median_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(median_scaled) = 'integer'
                        AND median_scaled BETWEEN
                            -999999999999999999 AND 999999999999999999
                    ),
                upper_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(upper_scaled) = 'integer'
                        AND upper_scaled BETWEEN
                            -999999999999999999 AND 999999999999999999
                    ),
                confidence_percent INTEGER NOT NULL
                    CHECK (
                        typeof(confidence_percent) = 'integer'
                        AND confidence_percent BETWEEN 1 AND 99
                    ),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                sequence INTEGER NOT NULL
                    CHECK (
                        typeof(sequence) = 'integer'
                        AND sequence >= 1
                    ),
                rationale TEXT
                    CHECK (rationale IS NULL OR (
                        length(rationale) > 0
                        AND rationale = trim(rationale)
                        AND instr(rationale, char(0)) = 0
                    )),
                UNIQUE (prediction_id, sequence),
                UNIQUE (prediction_id, id),
                CHECK (lower_scaled <= median_scaled),
                CHECK (median_scaled <= upper_scaled)
            ) STRICT
            """,
            """
            CREATE INDEX numeric_forecast_revisions_latest_by_prediction
            ON numeric_forecast_revisions (prediction_id, sequence DESC)
            """,
            """
            CREATE TRIGGER numeric_forecast_revisions_require_numeric_prediction
            BEFORE INSERT ON numeric_forecast_revisions
            WHEN (
                SELECT prediction_type
                FROM predictions
                WHERE id = NEW.prediction_id
            ) IS NOT 'numeric'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'numeric revisions require a numeric prediction'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_forecast_revisions_are_immutable
            BEFORE UPDATE ON numeric_forecast_revisions
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric forecast revisions are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_forecast_revisions_reject_history_replacement
            BEFORE INSERT ON numeric_forecast_revisions
            WHEN EXISTS (
                SELECT 1 FROM numeric_forecast_revisions WHERE id = NEW.id
            )
                OR EXISTS (
                    SELECT 1
                    FROM numeric_forecast_revisions
                    WHERE prediction_id = NEW.prediction_id
                        AND sequence = NEW.sequence
                )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric forecast revisions are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_forecast_revisions_reject_direct_delete
            BEFORE DELETE ON numeric_forecast_revisions
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric forecast revisions are immutable'
                );
            END
            """,
        ),
    ),
    Migration(
        version=10,
        name="make journal anchors type-aware for numeric forecasts",
        statements=(
            "DROP TRIGGER journal_entry_corrections_require_changed_body",
            "DROP TRIGGER journal_entry_corrections_require_next_sequence",
            "DROP TRIGGER journal_entry_corrections_are_immutable",
            "DROP TRIGGER journal_entry_corrections_reject_history_replacement",
            "DROP TRIGGER journal_entry_corrections_reject_direct_delete",
            "DROP TRIGGER journal_entries_require_current_revision",
            "DROP TRIGGER journal_entries_require_open_prediction",
            "DROP TRIGGER journal_entries_are_immutable",
            "DROP TRIGGER journal_entries_reject_history_replacement",
            "DROP TRIGGER journal_entries_reject_direct_delete",
            "ALTER TABLE journal_entry_corrections RENAME TO journal_entry_corrections_v9",
            "ALTER TABLE journal_entries RENAME TO journal_entries_v9",
            """
            CREATE TABLE journal_entries (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                forecast_revision_id INTEGER,
                numeric_forecast_revision_id INTEGER,
                body TEXT NOT NULL
                    CHECK (
                        length(body) > 0
                        AND body = trim(
                            body,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(body, char(0)) = 0
                    ),
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                UNIQUE (prediction_id, id),
                FOREIGN KEY (prediction_id, forecast_revision_id)
                    REFERENCES forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE,
                FOREIGN KEY (prediction_id, numeric_forecast_revision_id)
                    REFERENCES numeric_forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE,
                CHECK (
                    (forecast_revision_id IS NOT NULL)
                    != (numeric_forecast_revision_id IS NOT NULL)
                )
            ) STRICT
            """,
            """
            INSERT INTO journal_entries (
                id, prediction_id, forecast_revision_id, body, created_at
            )
            SELECT id, prediction_id, forecast_revision_id, body, created_at
            FROM journal_entries_v9
            """,
            """
            CREATE TABLE journal_entry_corrections (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL,
                journal_entry_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL
                    CHECK (typeof(sequence) = 'integer' AND sequence >= 1),
                body TEXT NOT NULL
                    CHECK (
                        length(body) > 0
                        AND body = trim(
                            body,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(body, char(0)) = 0
                    ),
                corrected_at TEXT NOT NULL
                    CHECK (
                        length(corrected_at) = 27
                        AND corrected_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(corrected_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(corrected_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(corrected_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(corrected_at, 1, 10),
                            0
                        )
                    ),
                FOREIGN KEY (prediction_id, journal_entry_id)
                    REFERENCES journal_entries(prediction_id, id)
                    ON DELETE CASCADE,
                UNIQUE (journal_entry_id, sequence)
            ) STRICT
            """,
            """
            INSERT INTO journal_entry_corrections (
                id, prediction_id, journal_entry_id, sequence, body, corrected_at
            )
            SELECT id, prediction_id, journal_entry_id, sequence, body, corrected_at
            FROM journal_entry_corrections_v9
            """,
            "DROP TABLE journal_entry_corrections_v9",
            "DROP TABLE journal_entries_v9",
            """
            CREATE INDEX journal_entries_by_prediction_binary_anchor
            ON journal_entries (prediction_id, forecast_revision_id, created_at, id)
            """,
            """
            CREATE INDEX journal_entries_by_prediction_numeric_anchor
            ON journal_entries (
                prediction_id, numeric_forecast_revision_id, created_at, id
            )
            """,
            """
            CREATE INDEX journal_entry_corrections_by_entry
            ON journal_entry_corrections (journal_entry_id, sequence)
            """,
            """
            CREATE TRIGGER journal_entries_require_current_type_revision
            BEFORE INSERT ON journal_entries
            WHEN (
                (SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id)
                    = 'binary'
                AND (
                    NEW.numeric_forecast_revision_id IS NOT NULL
                    OR NEW.forecast_revision_id IS NOT (
                        SELECT id FROM forecast_revisions
                        WHERE prediction_id = NEW.prediction_id
                        ORDER BY sequence DESC LIMIT 1
                    )
                )
            ) OR (
                (SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id)
                    = 'numeric'
                AND (
                    NEW.forecast_revision_id IS NOT NULL
                    OR NEW.numeric_forecast_revision_id IS NOT (
                        SELECT id FROM numeric_forecast_revisions
                        WHERE prediction_id = NEW.prediction_id
                        ORDER BY sequence DESC LIMIT 1
                    )
                )
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'journal entries must reference the current type-appropriate revision'
                );
            END
            """,
            """
            CREATE TRIGGER journal_entries_require_open_prediction
            BEFORE INSERT ON journal_entries
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'new journal entries require an open or locked prediction'
                );
            END
            """,
            """
            CREATE TRIGGER journal_entries_are_immutable
            BEFORE UPDATE ON journal_entries
            BEGIN SELECT RAISE(ABORT, 'saved journal entries are immutable'); END
            """,
            """
            CREATE TRIGGER journal_entries_reject_history_replacement
            BEFORE INSERT ON journal_entries
            WHEN EXISTS (SELECT 1 FROM journal_entries WHERE id = NEW.id)
            BEGIN SELECT RAISE(ABORT, 'saved journal entries are immutable'); END
            """,
            """
            CREATE TRIGGER journal_entries_reject_direct_delete
            BEFORE DELETE ON journal_entries
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN SELECT RAISE(ABORT, 'saved journal entries are immutable'); END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_require_changed_body
            BEFORE INSERT ON journal_entry_corrections
            WHEN NEW.body = COALESCE(
                (SELECT body FROM journal_entry_corrections
                    WHERE journal_entry_id = NEW.journal_entry_id
                    ORDER BY sequence DESC LIMIT 1),
                (SELECT body FROM journal_entries WHERE id = NEW.journal_entry_id)
            )
            BEGIN SELECT RAISE(ABORT, 'a journal correction must change the text'); END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_require_next_sequence
            BEFORE INSERT ON journal_entry_corrections
            WHEN NEW.sequence != COALESCE(
                (SELECT MAX(sequence) FROM journal_entry_corrections
                    WHERE journal_entry_id = NEW.journal_entry_id), 0
            ) + 1
            BEGIN SELECT RAISE(ABORT, 'journal correction sequence must be contiguous'); END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_are_immutable
            BEFORE UPDATE ON journal_entry_corrections
            BEGIN SELECT RAISE(ABORT, 'saved journal corrections are immutable'); END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_reject_history_replacement
            BEFORE INSERT ON journal_entry_corrections
            WHEN EXISTS (SELECT 1 FROM journal_entry_corrections WHERE id = NEW.id)
                OR EXISTS (SELECT 1 FROM journal_entry_corrections
                    WHERE journal_entry_id = NEW.journal_entry_id
                    AND sequence = NEW.sequence)
            BEGIN SELECT RAISE(ABORT, 'saved journal corrections are immutable'); END
            """,
            """
            CREATE TRIGGER journal_entry_corrections_reject_direct_delete
            BEFORE DELETE ON journal_entry_corrections
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN SELECT RAISE(ABORT, 'saved journal corrections are immutable'); END
            """,
        ),
    ),
    Migration(
        version=11,
        name="add numeric terminal lifecycle records",
        statements=(
            "DROP TRIGGER predictions_status_requires_terminal_record",
            "DROP TRIGGER resolutions_require_open_prediction",
            """
            CREATE TRIGGER resolutions_require_open_prediction
            BEFORE INSERT ON resolutions
            WHEN (
                SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'binary'
            OR (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'binary resolution requires an open or locked binary prediction'
                );
            END
            """,
            """
            CREATE TABLE numeric_resolutions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL UNIQUE
                    REFERENCES predictions(id) ON DELETE CASCADE,
                actual_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(actual_scaled) = 'integer'
                        AND abs(actual_scaled) <= 999999999999999999
                    ),
                resolved_at TEXT NOT NULL
                    CHECK (
                        length(resolved_at) = 27
                        AND resolved_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(resolved_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(resolved_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(resolved_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(resolved_at, 1, 10),
                            0
                        )
                    ),
                scoring_revision_id INTEGER NOT NULL,
                resolution_notes TEXT
                    CHECK (resolution_notes IS NULL OR (
                        length(resolution_notes) > 0
                        AND resolution_notes = trim(
                            resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(resolution_notes, char(0)) = 0
                    )),
                postmortem TEXT
                    CHECK (postmortem IS NULL OR (
                        length(postmortem) > 0
                        AND postmortem = trim(
                            postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(postmortem, char(0)) = 0
                    )),
                FOREIGN KEY (prediction_id, scoring_revision_id)
                    REFERENCES numeric_forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE
            ) STRICT
            """,
            """
            CREATE INDEX numeric_resolutions_by_resolved_at
            ON numeric_resolutions (resolved_at, id)
            """,
            """
            CREATE TRIGGER numeric_resolutions_require_open_prediction
            BEFORE INSERT ON numeric_resolutions
            WHEN (
                SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'numeric'
            OR (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'numeric resolution requires an open or locked numeric prediction'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolutions_require_current_scoring_revision
            BEFORE INSERT ON numeric_resolutions
            WHEN NEW.scoring_revision_id IS NOT (
                SELECT id
                FROM numeric_forecast_revisions
                WHERE prediction_id = NEW.prediction_id
                ORDER BY sequence DESC
                LIMIT 1
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'numeric resolution must capture the current forecast revision'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolutions_mark_prediction_resolved
            AFTER INSERT ON numeric_resolutions
            BEGIN
                UPDATE predictions
                SET status = 'resolved', updated_at = NEW.resolved_at
                WHERE id = NEW.prediction_id;
            END
            """,
            """
            CREATE TRIGGER numeric_resolutions_are_immutable
            BEFORE UPDATE ON numeric_resolutions
            BEGIN
                SELECT RAISE(ABORT, 'saved numeric resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER numeric_resolutions_reject_history_replacement
            BEFORE INSERT ON numeric_resolutions
            WHEN EXISTS (SELECT 1 FROM numeric_resolutions WHERE id = NEW.id)
                OR EXISTS (
                    SELECT 1 FROM numeric_resolutions
                    WHERE prediction_id = NEW.prediction_id
                )
            BEGIN
                SELECT RAISE(ABORT, 'saved numeric resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER numeric_resolutions_reject_direct_delete
            BEFORE DELETE ON numeric_resolutions
            WHEN EXISTS (
                SELECT 1 FROM predictions WHERE id = OLD.prediction_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'saved numeric resolutions are immutable');
            END
            """,
            """
            CREATE TRIGGER predictions_status_requires_terminal_record
            BEFORE UPDATE OF status ON predictions
            WHEN OLD.status = 'open'
                AND (
                    (
                        NEW.status = 'resolved'
                        AND (
                            (
                                NEW.prediction_type = 'binary'
                                AND NOT EXISTS (
                                    SELECT 1 FROM resolutions
                                    WHERE prediction_id = NEW.id
                                )
                            )
                            OR (
                                NEW.prediction_type = 'numeric'
                                AND NOT EXISTS (
                                    SELECT 1 FROM numeric_resolutions
                                    WHERE prediction_id = NEW.id
                                )
                            )
                        )
                    )
                    OR (
                        NEW.status = 'invalid'
                        AND NOT EXISTS (
                            SELECT 1 FROM prediction_invalidations
                            WHERE prediction_id = NEW.id
                        )
                    )
                )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'terminal status requires its immutable lifecycle record'
                );
            END
            """,
        ),
    ),
    Migration(
        version=12,
        name="add type-aware forecast reviews",
        statements=(
            """
            CREATE TABLE forecast_reviews (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL
                    REFERENCES predictions(id) ON DELETE CASCADE,
                forecast_revision_id INTEGER,
                numeric_forecast_revision_id INTEGER,
                created_at TEXT NOT NULL
                    CHECK (
                        length(created_at) = 27
                        AND created_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(created_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(created_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(created_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(created_at, 1, 10),
                            0
                        )
                    ),
                note TEXT
                    CHECK (note IS NULL OR (
                        length(note) > 0
                        AND note = trim(
                            note,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(note, char(0)) = 0
                    )),
                FOREIGN KEY (prediction_id, forecast_revision_id)
                    REFERENCES forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE,
                FOREIGN KEY (prediction_id, numeric_forecast_revision_id)
                    REFERENCES numeric_forecast_revisions(prediction_id, id)
                    ON DELETE CASCADE,
                CHECK (
                    (forecast_revision_id IS NOT NULL)
                    != (numeric_forecast_revision_id IS NOT NULL)
                )
            ) STRICT
            """,
            """
            CREATE INDEX forecast_reviews_by_prediction_binary_anchor
            ON forecast_reviews (
                prediction_id, forecast_revision_id, created_at, id
            )
            """,
            """
            CREATE INDEX forecast_reviews_by_prediction_numeric_anchor
            ON forecast_reviews (
                prediction_id, numeric_forecast_revision_id, created_at, id
            )
            """,
            """
            CREATE TRIGGER forecast_reviews_require_current_type_revision
            BEFORE INSERT ON forecast_reviews
            WHEN (
                (SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id)
                    = 'binary'
                AND (
                    NEW.numeric_forecast_revision_id IS NOT NULL
                    OR NEW.forecast_revision_id IS NOT (
                        SELECT id FROM forecast_revisions
                        WHERE prediction_id = NEW.prediction_id
                        ORDER BY sequence DESC LIMIT 1
                    )
                )
            ) OR (
                (SELECT prediction_type FROM predictions WHERE id = NEW.prediction_id)
                    = 'numeric'
                AND (
                    NEW.forecast_revision_id IS NOT NULL
                    OR NEW.numeric_forecast_revision_id IS NOT (
                        SELECT id FROM numeric_forecast_revisions
                        WHERE prediction_id = NEW.prediction_id
                        ORDER BY sequence DESC LIMIT 1
                    )
                )
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'forecast reviews must reference the current type-appropriate revision'
                );
            END
            """,
            """
            CREATE TRIGGER forecast_reviews_require_open_prediction
            BEFORE INSERT ON forecast_reviews
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'open'
            BEGIN
                SELECT RAISE(ABORT, 'forecast reviews require an open prediction');
            END
            """,
            """
            CREATE TRIGGER forecast_reviews_are_immutable
            BEFORE UPDATE ON forecast_reviews
            BEGIN SELECT RAISE(ABORT, 'saved forecast reviews are immutable'); END
            """,
            """
            CREATE TRIGGER forecast_reviews_reject_history_replacement
            BEFORE INSERT ON forecast_reviews
            WHEN EXISTS (SELECT 1 FROM forecast_reviews WHERE id = NEW.id)
            BEGIN SELECT RAISE(ABORT, 'saved forecast reviews are immutable'); END
            """,
            """
            CREATE TRIGGER forecast_reviews_reject_direct_delete
            BEFORE DELETE ON forecast_reviews
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN SELECT RAISE(ABORT, 'saved forecast reviews are immutable'); END
            """,
        ),
    ),
    Migration(
        version=13,
        name="add append-only terminal corrections",
        statements=(
            """
            CREATE UNIQUE INDEX resolutions_prediction_identity
            ON resolutions (prediction_id, id)
            """,
            """
            CREATE UNIQUE INDEX numeric_resolutions_prediction_identity
            ON numeric_resolutions (prediction_id, id)
            """,
            """
            CREATE UNIQUE INDEX prediction_invalidations_prediction_identity
            ON prediction_invalidations (prediction_id, id)
            """,
            """
            CREATE TABLE resolution_corrections (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL,
                resolution_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL
                    CHECK (typeof(sequence) = 'integer' AND sequence >= 1),
                old_outcome TEXT NOT NULL CHECK (old_outcome IN ('yes', 'no')),
                new_outcome TEXT NOT NULL CHECK (new_outcome IN ('yes', 'no')),
                old_resolution_notes TEXT
                    CHECK (old_resolution_notes IS NULL OR (
                        length(old_resolution_notes) > 0
                        AND old_resolution_notes = trim(
                            old_resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(old_resolution_notes, char(0)) = 0
                    )),
                new_resolution_notes TEXT
                    CHECK (new_resolution_notes IS NULL OR (
                        length(new_resolution_notes) > 0
                        AND new_resolution_notes = trim(
                            new_resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(new_resolution_notes, char(0)) = 0
                    )),
                old_postmortem TEXT
                    CHECK (old_postmortem IS NULL OR (
                        length(old_postmortem) > 0
                        AND old_postmortem = trim(
                            old_postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(old_postmortem, char(0)) = 0
                    )),
                new_postmortem TEXT
                    CHECK (new_postmortem IS NULL OR (
                        length(new_postmortem) > 0
                        AND new_postmortem = trim(
                            new_postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(new_postmortem, char(0)) = 0
                    )),
                outcome_changed INTEGER NOT NULL CHECK (outcome_changed IN (0, 1)),
                resolution_notes_changed INTEGER NOT NULL
                    CHECK (resolution_notes_changed IN (0, 1)),
                postmortem_changed INTEGER NOT NULL
                    CHECK (postmortem_changed IN (0, 1)),
                correction_reason TEXT
                    CHECK (correction_reason IS NULL OR (
                        length(correction_reason) > 0
                        AND correction_reason = trim(
                            correction_reason,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(correction_reason, char(0)) = 0
                    )),
                corrected_at TEXT NOT NULL
                    CHECK (
                        length(corrected_at) = 27
                        AND corrected_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(corrected_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(corrected_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(corrected_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(corrected_at, 1, 10),
                            0
                        )
                    ),
                FOREIGN KEY (prediction_id, resolution_id)
                    REFERENCES resolutions(prediction_id, id)
                    ON DELETE CASCADE,
                UNIQUE (resolution_id, sequence),
                CHECK (outcome_changed = (old_outcome IS NOT new_outcome)),
                CHECK (
                    resolution_notes_changed =
                        (old_resolution_notes IS NOT new_resolution_notes)
                ),
                CHECK (
                    postmortem_changed = (old_postmortem IS NOT new_postmortem)
                ),
                CHECK (
                    outcome_changed + resolution_notes_changed
                        + postmortem_changed >= 1
                ),
                CHECK (outcome_changed = 0 OR correction_reason IS NOT NULL)
            ) STRICT
            """,
            """
            CREATE INDEX resolution_corrections_by_resolution
            ON resolution_corrections (resolution_id, sequence)
            """,
            """
            CREATE TRIGGER resolution_corrections_require_current_snapshot
            BEFORE INSERT ON resolution_corrections
            WHEN NEW.old_outcome IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                ) THEN (
                    SELECT new_outcome FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT outcome FROM resolutions WHERE id = NEW.resolution_id
                ) END
            )
            OR NEW.old_resolution_notes IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                ) THEN (
                    SELECT new_resolution_notes FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT resolution_notes FROM resolutions
                    WHERE id = NEW.resolution_id
                ) END
            )
            OR NEW.old_postmortem IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                ) THEN (
                    SELECT new_postmortem FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT postmortem FROM resolutions
                    WHERE id = NEW.resolution_id
                ) END
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'resolution correction must continue the current snapshot'
                );
            END
            """,
            """
            CREATE TRIGGER resolution_corrections_require_next_sequence
            BEFORE INSERT ON resolution_corrections
            WHEN NEW.sequence != COALESCE(
                (
                    SELECT MAX(sequence) FROM resolution_corrections
                    WHERE resolution_id = NEW.resolution_id
                ),
                0
            ) + 1
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'resolution correction sequence must be contiguous'
                );
            END
            """,
            """
            CREATE TRIGGER resolution_corrections_are_immutable
            BEFORE UPDATE ON resolution_corrections
            BEGIN
                SELECT RAISE(ABORT, 'saved resolution corrections are immutable');
            END
            """,
            """
            CREATE TRIGGER resolution_corrections_reject_history_replacement
            BEFORE INSERT ON resolution_corrections
            WHEN EXISTS (SELECT 1 FROM resolution_corrections WHERE id = NEW.id)
            BEGIN
                SELECT RAISE(ABORT, 'saved resolution corrections are immutable');
            END
            """,
            """
            CREATE TRIGGER resolution_corrections_reject_direct_delete
            BEFORE DELETE ON resolution_corrections
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN
                SELECT RAISE(ABORT, 'saved resolution corrections are immutable');
            END
            """,
            """
            CREATE TABLE numeric_resolution_corrections (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL,
                numeric_resolution_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL
                    CHECK (typeof(sequence) = 'integer' AND sequence >= 1),
                old_actual_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(old_actual_scaled) = 'integer'
                        AND abs(old_actual_scaled) <= 999999999999999999
                    ),
                new_actual_scaled INTEGER NOT NULL
                    CHECK (
                        typeof(new_actual_scaled) = 'integer'
                        AND abs(new_actual_scaled) <= 999999999999999999
                    ),
                old_resolution_notes TEXT
                    CHECK (old_resolution_notes IS NULL OR (
                        length(old_resolution_notes) > 0
                        AND old_resolution_notes = trim(
                            old_resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(old_resolution_notes, char(0)) = 0
                    )),
                new_resolution_notes TEXT
                    CHECK (new_resolution_notes IS NULL OR (
                        length(new_resolution_notes) > 0
                        AND new_resolution_notes = trim(
                            new_resolution_notes,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(new_resolution_notes, char(0)) = 0
                    )),
                old_postmortem TEXT
                    CHECK (old_postmortem IS NULL OR (
                        length(old_postmortem) > 0
                        AND old_postmortem = trim(
                            old_postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(old_postmortem, char(0)) = 0
                    )),
                new_postmortem TEXT
                    CHECK (new_postmortem IS NULL OR (
                        length(new_postmortem) > 0
                        AND new_postmortem = trim(
                            new_postmortem,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(new_postmortem, char(0)) = 0
                    )),
                actual_value_changed INTEGER NOT NULL
                    CHECK (actual_value_changed IN (0, 1)),
                resolution_notes_changed INTEGER NOT NULL
                    CHECK (resolution_notes_changed IN (0, 1)),
                postmortem_changed INTEGER NOT NULL
                    CHECK (postmortem_changed IN (0, 1)),
                correction_reason TEXT
                    CHECK (correction_reason IS NULL OR (
                        length(correction_reason) > 0
                        AND correction_reason = trim(
                            correction_reason,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(correction_reason, char(0)) = 0
                    )),
                corrected_at TEXT NOT NULL
                    CHECK (
                        length(corrected_at) = 27
                        AND corrected_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(corrected_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(corrected_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(corrected_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(corrected_at, 1, 10),
                            0
                        )
                    ),
                FOREIGN KEY (prediction_id, numeric_resolution_id)
                    REFERENCES numeric_resolutions(prediction_id, id)
                    ON DELETE CASCADE,
                UNIQUE (numeric_resolution_id, sequence),
                CHECK (
                    actual_value_changed =
                        (old_actual_scaled IS NOT new_actual_scaled)
                ),
                CHECK (
                    resolution_notes_changed =
                        (old_resolution_notes IS NOT new_resolution_notes)
                ),
                CHECK (
                    postmortem_changed = (old_postmortem IS NOT new_postmortem)
                ),
                CHECK (
                    actual_value_changed + resolution_notes_changed
                        + postmortem_changed >= 1
                ),
                CHECK (actual_value_changed = 0 OR correction_reason IS NOT NULL)
            ) STRICT
            """,
            """
            CREATE INDEX numeric_resolution_corrections_by_resolution
            ON numeric_resolution_corrections (numeric_resolution_id, sequence)
            """,
            """
            CREATE TRIGGER numeric_resolution_corrections_require_current_snapshot
            BEFORE INSERT ON numeric_resolution_corrections
            WHEN NEW.old_actual_scaled IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                ) THEN (
                    SELECT new_actual_scaled FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT actual_scaled FROM numeric_resolutions
                    WHERE id = NEW.numeric_resolution_id
                ) END
            )
            OR NEW.old_resolution_notes IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                ) THEN (
                    SELECT new_resolution_notes
                    FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT resolution_notes FROM numeric_resolutions
                    WHERE id = NEW.numeric_resolution_id
                ) END
            )
            OR NEW.old_postmortem IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                ) THEN (
                    SELECT new_postmortem FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT postmortem FROM numeric_resolutions
                    WHERE id = NEW.numeric_resolution_id
                ) END
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'numeric resolution correction must continue the current snapshot'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolution_corrections_require_next_sequence
            BEFORE INSERT ON numeric_resolution_corrections
            WHEN NEW.sequence != COALESCE(
                (
                    SELECT MAX(sequence) FROM numeric_resolution_corrections
                    WHERE numeric_resolution_id = NEW.numeric_resolution_id
                ),
                0
            ) + 1
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'numeric resolution correction sequence must be contiguous'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolution_corrections_are_immutable
            BEFORE UPDATE ON numeric_resolution_corrections
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric resolution corrections are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolution_corrections_reject_history_replacement
            BEFORE INSERT ON numeric_resolution_corrections
            WHEN EXISTS (
                SELECT 1 FROM numeric_resolution_corrections WHERE id = NEW.id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric resolution corrections are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER numeric_resolution_corrections_reject_direct_delete
            BEFORE DELETE ON numeric_resolution_corrections
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved numeric resolution corrections are immutable'
                );
            END
            """,
            """
            CREATE TABLE invalidation_reason_corrections (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL,
                invalidation_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL
                    CHECK (typeof(sequence) = 'integer' AND sequence >= 1),
                old_reason TEXT
                    CHECK (old_reason IS NULL OR (
                        length(old_reason) > 0
                        AND old_reason = trim(
                            old_reason,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(old_reason, char(0)) = 0
                    )),
                new_reason TEXT
                    CHECK (new_reason IS NULL OR (
                        length(new_reason) > 0
                        AND new_reason = trim(
                            new_reason,
                            char(9) || char(10) || char(11) || char(12)
                                || char(13) || ' '
                        )
                        AND instr(new_reason, char(0)) = 0
                    )),
                corrected_at TEXT NOT NULL
                    CHECK (
                        length(corrected_at) = 27
                        AND corrected_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(corrected_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(corrected_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(corrected_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(corrected_at, 1, 10),
                            0
                        )
                    ),
                FOREIGN KEY (prediction_id, invalidation_id)
                    REFERENCES prediction_invalidations(prediction_id, id)
                    ON DELETE CASCADE,
                UNIQUE (invalidation_id, sequence),
                CHECK (old_reason IS NOT new_reason)
            ) STRICT
            """,
            """
            CREATE INDEX invalidation_reason_corrections_by_invalidation
            ON invalidation_reason_corrections (invalidation_id, sequence)
            """,
            """
            CREATE TRIGGER invalidation_reason_corrections_require_current_snapshot
            BEFORE INSERT ON invalidation_reason_corrections
            WHEN NEW.old_reason IS NOT (
                CASE WHEN EXISTS (
                    SELECT 1 FROM invalidation_reason_corrections
                    WHERE invalidation_id = NEW.invalidation_id
                ) THEN (
                    SELECT new_reason FROM invalidation_reason_corrections
                    WHERE invalidation_id = NEW.invalidation_id
                    ORDER BY sequence DESC LIMIT 1
                ) ELSE (
                    SELECT reason FROM prediction_invalidations
                    WHERE id = NEW.invalidation_id
                ) END
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'invalidation correction must continue the current snapshot'
                );
            END
            """,
            """
            CREATE TRIGGER invalidation_reason_corrections_require_next_sequence
            BEFORE INSERT ON invalidation_reason_corrections
            WHEN NEW.sequence != COALESCE(
                (
                    SELECT MAX(sequence) FROM invalidation_reason_corrections
                    WHERE invalidation_id = NEW.invalidation_id
                ),
                0
            ) + 1
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'invalidation correction sequence must be contiguous'
                );
            END
            """,
            """
            CREATE TRIGGER invalidation_reason_corrections_are_immutable
            BEFORE UPDATE ON invalidation_reason_corrections
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved invalidation reason corrections are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER invalidation_reason_corrections_reject_history_replacement
            BEFORE INSERT ON invalidation_reason_corrections
            WHEN EXISTS (
                SELECT 1 FROM invalidation_reason_corrections WHERE id = NEW.id
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved invalidation reason corrections are immutable'
                );
            END
            """,
            """
            CREATE TRIGGER invalidation_reason_corrections_reject_direct_delete
            BEFORE DELETE ON invalidation_reason_corrections
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'saved invalidation reason corrections are immutable'
                );
            END
            """,
            """
            CREATE TABLE postmortem_completions (
                id INTEGER PRIMARY KEY,
                prediction_id INTEGER NOT NULL UNIQUE
                    REFERENCES predictions(id) ON DELETE CASCADE,
                completed_at TEXT NOT NULL
                    CHECK (
                        length(completed_at) = 27
                        AND completed_at GLOB
                            '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T'
                            || '[0-2][0-9]:[0-5][0-9]:[0-5][0-9].'
                            || '[0-9][0-9][0-9][0-9][0-9][0-9]Z'
                        AND substr(completed_at, 1, 4) BETWEEN '0001' AND '9999'
                        AND substr(completed_at, 12, 2) BETWEEN '00' AND '23'
                        AND COALESCE(
                            date(
                                substr(completed_at, 1, 10) || 'T00:00:00Z',
                                '+0 days'
                            ) = substr(completed_at, 1, 10),
                            0
                        )
                    )
            ) STRICT
            """,
            """
            CREATE TRIGGER postmortem_completions_require_blank_resolved_postmortem
            BEFORE INSERT ON postmortem_completions
            WHEN (
                SELECT status FROM predictions WHERE id = NEW.prediction_id
            ) IS NOT 'resolved'
            OR (
                (
                    SELECT prediction_type FROM predictions
                    WHERE id = NEW.prediction_id
                ) = 'binary'
                AND (
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM resolution_corrections AS correction
                        JOIN resolutions AS resolution
                            ON resolution.id = correction.resolution_id
                        WHERE resolution.prediction_id = NEW.prediction_id
                    ) THEN (
                        SELECT correction.new_postmortem
                        FROM resolution_corrections AS correction
                        JOIN resolutions AS resolution
                            ON resolution.id = correction.resolution_id
                        WHERE resolution.prediction_id = NEW.prediction_id
                        ORDER BY correction.sequence DESC LIMIT 1
                    ) ELSE (
                        SELECT postmortem FROM resolutions
                        WHERE prediction_id = NEW.prediction_id
                    ) END
                ) IS NOT NULL
            )
            OR (
                (
                    SELECT prediction_type FROM predictions
                    WHERE id = NEW.prediction_id
                ) = 'numeric'
                AND (
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM numeric_resolution_corrections AS correction
                        JOIN numeric_resolutions AS resolution
                            ON resolution.id = correction.numeric_resolution_id
                        WHERE resolution.prediction_id = NEW.prediction_id
                    ) THEN (
                        SELECT correction.new_postmortem
                        FROM numeric_resolution_corrections AS correction
                        JOIN numeric_resolutions AS resolution
                            ON resolution.id = correction.numeric_resolution_id
                        WHERE resolution.prediction_id = NEW.prediction_id
                        ORDER BY correction.sequence DESC LIMIT 1
                    ) ELSE (
                        SELECT postmortem FROM numeric_resolutions
                        WHERE prediction_id = NEW.prediction_id
                    ) END
                ) IS NOT NULL
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'postmortem completion requires a blank resolved postmortem'
                );
            END
            """,
            """
            CREATE TRIGGER postmortem_completions_are_immutable
            BEFORE UPDATE ON postmortem_completions
            BEGIN
                SELECT RAISE(ABORT, 'saved postmortem completions are immutable');
            END
            """,
            """
            CREATE TRIGGER postmortem_completions_reject_history_replacement
            BEFORE INSERT ON postmortem_completions
            WHEN EXISTS (SELECT 1 FROM postmortem_completions WHERE id = NEW.id)
            BEGIN
                SELECT RAISE(ABORT, 'saved postmortem completions are immutable');
            END
            """,
            """
            CREATE TRIGGER postmortem_completions_reject_direct_delete
            BEFORE DELETE ON postmortem_completions
            WHEN EXISTS (SELECT 1 FROM predictions WHERE id = OLD.prediction_id)
            BEGIN
                SELECT RAISE(ABORT, 'saved postmortem completions are immutable');
            END
            """,
        ),
    ),
    Migration(
        version=14,
        name="add rebuildable full text search projection",
        statements=(
            """
            CREATE TABLE search_index_state (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                projection_version INTEGER NOT NULL
                    CHECK (
                        typeof(projection_version) = 'integer'
                        AND projection_version >= 0
                    ),
                document_count INTEGER NOT NULL
                    CHECK (
                        typeof(document_count) = 'integer'
                        AND document_count >= 0
                    )
            ) STRICT
            """,
            """
            INSERT INTO search_index_state (
                singleton_id, projection_version, document_count
            ) VALUES (1, 0, 0)
            """,
            """
            CREATE TABLE search_dirty_predictions (
                prediction_id INTEGER PRIMARY KEY
                    CHECK (
                        typeof(prediction_id) = 'integer'
                        AND prediction_id >= 1
                    )
            ) STRICT
            """,
            """
            CREATE VIRTUAL TABLE prediction_search USING fts5(
                prediction_id UNINDEXED,
                source_kind UNINDEXED,
                source_record_id UNINDEXED,
                source_version_id UNINDEXED,
                source_sequence UNINDEXED,
                occurred_at UNINDEXED,
                is_superseded UNINDEXED,
                body,
                tokenize = 'unicode61 remove_diacritics 2',
                prefix = '2 3 4'
            )
            """,
            """
            CREATE VIRTUAL TABLE prediction_search_vocabulary
            USING fts5vocab(prediction_search, 'row')
            """,
            """
            CREATE TRIGGER search_dirty_after_prediction_insert
            AFTER INSERT ON predictions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_prediction_update
            AFTER UPDATE ON predictions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_prediction_delete
            AFTER DELETE ON predictions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (OLD.id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_prediction_tag_insert
            AFTER INSERT ON prediction_tags
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_prediction_tag_delete
            AFTER DELETE ON prediction_tags
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (OLD.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_tag_update
            AFTER UPDATE OF display_name, normalized_name ON tags
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                SELECT prediction_id
                FROM prediction_tags
                WHERE tag_id = NEW.id;
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_binary_revision_insert
            AFTER INSERT ON forecast_revisions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_numeric_revision_insert
            AFTER INSERT ON numeric_forecast_revisions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_definition_change_insert
            AFTER INSERT ON prediction_definition_changes
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_journal_insert
            AFTER INSERT ON journal_entries
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_journal_correction_insert
            AFTER INSERT ON journal_entry_corrections
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_forecast_review_insert
            AFTER INSERT ON forecast_reviews
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_binary_resolution_insert
            AFTER INSERT ON resolutions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_numeric_resolution_insert
            AFTER INSERT ON numeric_resolutions
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_invalidation_insert
            AFTER INSERT ON prediction_invalidations
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_binary_resolution_correction_insert
            AFTER INSERT ON resolution_corrections
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_numeric_resolution_correction_insert
            AFTER INSERT ON numeric_resolution_corrections
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            CREATE TRIGGER search_dirty_after_invalidation_correction_insert
            AFTER INSERT ON invalidation_reason_corrections
            BEGIN
                INSERT OR IGNORE INTO search_dirty_predictions (prediction_id)
                VALUES (NEW.prediction_id);
            END
            """,
            """
            INSERT INTO search_dirty_predictions (prediction_id)
            SELECT id FROM predictions ORDER BY id
            """,
        ),
    ),
)


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Sequence[Migration] = MIGRATIONS,
) -> None:
    """Apply every pending migration in a single SQLite transaction."""

    ordered_migrations = tuple(migrations)
    _validate_registry(ordered_migrations)

    if connection.in_transaction:
        raise MigrationError("Migrations cannot run inside another transaction.")

    connection.execute("BEGIN IMMEDIATE")
    try:
        applied_count = _validated_applied_count(connection, ordered_migrations)
        for migration in ordered_migrations[applied_count:]:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name),
            )

        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_violations:
            raise MigrationError("A migration introduced a foreign-key violation.")
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def current_schema_version(connection: sqlite3.Connection) -> int:
    """Return the latest recorded schema version for an initialized database."""

    row = connection.execute(
        "SELECT MAX(version) AS version FROM schema_migrations"
    ).fetchone()
    if row is None or row[0] is None:
        raise InvalidMigrationHistoryError("The migration history is empty.")
    return int(row[0])


def _validate_registry(migrations: tuple[Migration, ...]) -> None:
    if not migrations:
        raise MigrationConfigurationError("At least one migration is required.")

    expected_versions = tuple(range(1, len(migrations) + 1))
    actual_versions = tuple(migration.version for migration in migrations)
    if actual_versions != expected_versions:
        raise MigrationConfigurationError(
            "Migration versions must be unique, ordered, and contiguous from 1."
        )

    names = tuple(migration.name for migration in migrations)
    if any(not name.strip() for name in names) or len(set(names)) != len(names):
        raise MigrationConfigurationError(
            "Migration names must be non-empty and unique."
        )


def _validated_applied_count(
    connection: sqlite3.Connection,
    migrations: tuple[Migration, ...],
) -> int:
    objects = connection.execute(
        """
        SELECT name, type
        FROM sqlite_schema
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    tracking_objects = [row for row in objects if row[0] == "schema_migrations"]

    if not tracking_objects:
        if objects:
            raise UnrecognizedDatabaseError(
                "The selected database contains data but no Reckonsolve migration history."
            )
        return 0

    if len(tracking_objects) != 1 or tracking_objects[0][1] != "table":
        raise InvalidMigrationHistoryError(
            "The schema_migrations object is not a valid table."
        )

    schema_row = connection.execute(
        """
        SELECT sql
        FROM sqlite_schema
        WHERE name = 'schema_migrations' AND type = 'table'
        """
    ).fetchone()
    if (
        schema_row is None
        or schema_row[0] is None
        or _normalize_sql(schema_row[0]) != _normalize_sql(MIGRATION_TABLE_SQL)
    ):
        raise InvalidMigrationHistoryError(
            "The migration history table does not match the required schema."
        )

    try:
        history = connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
    except sqlite3.Error as error:
        raise InvalidMigrationHistoryError(
            "The migration history table has an invalid structure."
        ) from error

    if not history:
        raise InvalidMigrationHistoryError("The migration history is empty.")

    for expected_version, row in enumerate(history, start=1):
        recorded_version = row[0]
        if recorded_version != expected_version:
            raise InvalidMigrationHistoryError(
                "Recorded migration versions must be contiguous from 1."
            )
        if recorded_version > len(migrations):
            raise UnsupportedSchemaVersionError(
                "The database schema is newer than this Reckonsolve version."
            )
        expected_name = migrations[recorded_version - 1].name
        if row[1] != expected_name:
            raise InvalidMigrationHistoryError(
                f"Migration {recorded_version} does not match this application build."
            )

    return len(history)


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.rstrip("; ").split()).casefold()
