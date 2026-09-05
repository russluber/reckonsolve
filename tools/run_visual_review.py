"""Launch disposable v0.6 visual-review databases without touching user data."""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from reckonsolve.app import run
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.identity import DEVELOPMENT_APPLICATION


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open an isolated, disposable Reckonsolve visual-review profile."
    )
    parser.add_argument(
        "profile",
        choices=("empty", "representative", "long-text"),
        help="Fixture shape to display; all data is deleted after the window closes.",
    )
    arguments = parser.parse_args()

    with TemporaryDirectory(prefix="reckonsolve-visual-review-") as temporary:
        database_path = Path(temporary) / "reckonsolve.sqlite3"
        if arguments.profile != "empty":
            _seed_review_database(
                database_path, long_text=arguments.profile == "long-text"
            )
        return run(
            argv=["reckonsolve-visual-review"],
            database_path=database_path,
            identity=DEVELOPMENT_APPLICATION,
        )


def _seed_review_database(database_path: Path, *, long_text: bool) -> None:
    database = Database.open(database_path)
    try:
        operations = PredictionOperations(database)
        repeated = (
            " This deliberately long text checks wrapping, selectable history, and "
            "responsive layout without truncating meaningful personal context."
            if long_text
            else ""
        )
        open_binary = operations.create_prediction(
            f"Will the representative Binary forecast remain readable?{repeated}",
            65,
            rationale=f"Initial evidence remains visible.{repeated}",
            background=f"Background context for the visual review.{repeated}",
            resolution_criteria=f"Resolve Yes when the stated event occurs.{repeated}",
            tags=("Visual review", "Binary"),
        )
        operations.add_journal_entry(
            open_binary.prediction_id,
            f"A Journal entry adds reasoning without changing the forecast.{repeated}",
            expected_revision_id=open_binary.current_revision_id,
            expected_metadata_version=open_binary.metadata_version,
        )
        operations.add_forecast_review(
            open_binary.prediction_id,
            note=f"The current probability was deliberately retained.{repeated}",
            expected_revision_id=open_binary.current_revision_id,
            expected_metadata_version=open_binary.metadata_version,
        )
        operations.create_numeric_prediction(
            f"How many days will the representative Numeric forecast take?{repeated}",
            "days",
            1,
            "1.0",
            "3.0",
            "8.0",
            80,
            rationale=f"The interval captures the plausible range.{repeated}",
            tags=("Visual review", "Numeric"),
        )

        resolved_binary = operations.create_prediction(
            f"Will a resolved Binary scorecard remain legible?{repeated}",
            75,
            tags=("Visual review", "Resolved"),
        )
        operations.resolve_prediction(
            resolved_binary.prediction_id,
            BinaryOutcome.YES,
            resolution_notes=f"The event happened.{repeated}",
            postmortem=f"The evidence was directionally useful.{repeated}",
            expected_revision_id=resolved_binary.current_revision_id,
            expected_metadata_version=resolved_binary.metadata_version,
        )

        resolved_numeric = operations.create_numeric_prediction(
            f"How many items were in the resolved Numeric outcome?{repeated}",
            "items",
            0,
            "4",
            "7",
            "12",
            70,
            tags=("Visual review", "Resolved"),
        )
        operations.resolve_numeric_prediction(
            resolved_numeric.prediction_id,
            "9",
            resolution_notes=f"Nine items were observed.{repeated}",
            postmortem=f"The interval contained the outcome.{repeated}",
            expected_revision_id=resolved_numeric.current_revision.revision_id,
            expected_metadata_version=resolved_numeric.metadata_version,
        )

        invalid = operations.create_prediction(
            f"Will an Invalid lifecycle state remain explicit?{repeated}",
            40,
            tags=("Visual review", "Invalid"),
        )
        operations.invalidate_prediction(
            invalid.prediction_id,
            reason=f"The question became unresolvable.{repeated}",
            expected_revision_id=invalid.current_revision_id,
            expected_metadata_version=invalid.metadata_version,
        )
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
