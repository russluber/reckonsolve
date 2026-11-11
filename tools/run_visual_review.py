"""Launch disposable current-model visual profiles without touching user data."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from reckonsolve.app import run
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import NewOneShotPrediction, OneShotValues
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)
from reckonsolve.identity import DEVELOPMENT_APPLICATION


@dataclass(frozen=True)
class _ReviewClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


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
        deadline = datetime.now(UTC) + timedelta(days=30)
        repeated = (
            " This deliberately long text checks wrapping, selectable history, and "
            "responsive layout without truncating meaningful personal context."
            if long_text
            else ""
        )
        open_binary = operations.create_prediction(
            f"Will the representative Binary forecast remain readable?{repeated}",
            65,
            forecast_deadline=deadline,
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
            {5: "1.0", 25: "2.0", 50: "3.0", 75: "5.0", 95: "8.0"},
            value_constraint=NumericValueConstraint.CONTINUOUS,
            forecast_deadline=deadline,
            rationale=f"The interval captures the plausible range.{repeated}",
            tags=("Visual review", "Numeric"),
        )

        resolved_binary = operations.create_prediction(
            f"Will a resolved Binary scorecard remain legible?{repeated}",
            75,
            forecast_deadline=deadline,
            tags=("Visual review", "Resolved"),
        )
        operations.resolve_prediction(
            resolved_binary.prediction_id,
            BinaryOutcome.YES,
            use_recorded_time=True,
            resolution_notes=f"The event happened.{repeated}",
            postmortem=f"The evidence was directionally useful.{repeated}",
            expected_revision_id=resolved_binary.current_revision_id,
            expected_metadata_version=resolved_binary.metadata_version,
        )

        resolved_numeric = operations.create_numeric_prediction(
            f"How many items were in the resolved Numeric outcome?{repeated}",
            "items",
            0,
            {5: 4, 25: 5, 50: 7, 75: 9, 95: 12},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=deadline,
            tags=("Visual review", "Resolved"),
        )
        operations.resolve_numeric_prediction(
            resolved_numeric.prediction_id,
            "9",
            use_recorded_time=True,
            resolution_notes=f"Nine items were observed.{repeated}",
            postmortem=f"The interval contained the outcome.{repeated}",
            expected_revision_id=resolved_numeric.current_revision.revision_id,
            expected_metadata_version=resolved_numeric.metadata_version,
        )

        invalid = operations.create_prediction(
            f"Will an Invalid lifecycle state remain explicit?{repeated}",
            40,
            forecast_deadline=deadline,
            tags=("Visual review", "Invalid"),
        )
        operations.invalidate_prediction(
            invalid.prediction_id,
            reason=f"The question became unresolvable.{repeated}",
            expected_revision_id=invalid.current_revision_id,
            expected_metadata_version=invalid.metadata_version,
        )
        operations.one_shots.create(
            NewOneShotPrediction(
                f"Is this sealed bag heavier than two kilograms?{repeated}",
                one_shot_contract(PredictionType.BINARY),
                OneShotValues(probability_percent=75, answer=BinaryOutcome.YES),
                background="An already-existing answer, recorded after a final guess.",
                tags=("Visual review", "One-Shot"),
            )
        )
        operations.one_shots.create(
            NewOneShotPrediction(
                f"Is the waiting-for-answer sample longer than one metre?{repeated}",
                one_shot_contract(PredictionType.BINARY),
                OneShotValues(probability_percent=60),
                background="Measure the already-existing sample after recording the guess.",
                tags=("Visual review", "Waiting"),
            )
        )
        # These historical fixtures are already Locked when the real review
        # window opens. No clock or Deadline is rewritten to manufacture it.
        historic = PredictionOperations(
            database, _ReviewClock(datetime.now(UTC) - timedelta(days=2))
        )
        expired = datetime.now(UTC) - timedelta(days=1)
        historic.create_prediction(
            "Will the Locked Binary actions stay clear?",
            60,
            forecast_deadline=expired,
            tags=("Visual review", "Locked"),
        )
        historic.create_numeric_prediction(
            "How readable is the Locked Numeric interval?",
            "units",
            0,
            {5: 1, 25: 2, 50: 3, 75: 3, 95: 5},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            forecast_deadline=expired,
            tags=("Visual review", "Locked"),
        )
        operations.one_shots.create(
            NewOneShotPrediction(
                f"What was the wind speed at the station?{repeated}",
                one_shot_contract(PredictionType.NUMERIC),
                OneShotValues(
                    quantiles=FiveQuantiles.from_values(
                        {5: "8.2", 25: "12.6", 50: "17.3", 75: "22.8", 95: "32.5"}, 1
                    ),
                    answer=FixedPrecisionValue.from_value("19.5", 1),
                ),
                QuantileDefinition("km/h", 1, NumericValueConstraint.CONTINUOUS),
                background="A measured value whose original answer already exists.",
                tags=("Visual review", "One-Shot"),
            )
        )
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
