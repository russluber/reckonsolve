"""Launch disposable current-model visual profiles without touching user data."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
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


@dataclass
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
        choices=("empty", "representative", "long-text", "detail"),
        help="Fixture shape to display; all data is deleted after the window closes.",
    )
    arguments = parser.parse_args()

    with TemporaryDirectory(prefix="reckonsolve-visual-review-") as temporary:
        database_path = Path(temporary) / "reckonsolve.sqlite3"
        if arguments.profile != "empty":
            _seed_review_database(
                database_path,
                long_text=arguments.profile == "long-text",
                detail=arguments.profile == "detail",
            )
        return run(
            argv=["reckonsolve-visual-review"],
            database_path=database_path,
            identity=DEVELOPMENT_APPLICATION,
        )


def _seed_review_database(
    database_path: Path, *, long_text: bool, detail: bool = False
) -> None:
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
        if detail:
            _seed_detail_cases(database, now=datetime.now(UTC))
    finally:
        database.close()


def _seed_detail_cases(database: Database, *, now: datetime) -> None:
    """Build difficult reading cases through canonical operations on a temp store."""
    start = now - timedelta(days=4)
    clock = _ReviewClock(start)
    operations = PredictionOperations(database, clock, UTC)
    deadline = now + timedelta(days=30)
    tags = ("Detail review",)
    quantiles = {5: 1, 25: 2, 50: 3, 75: 4, 95: 5}

    def create(question: str, numeric: bool):
        clock.instant = start
        if numeric:
            return operations.create_numeric_prediction(
                question,
                "items",
                0,
                quantiles,
                value_constraint=NumericValueConstraint.WHOLE_NUMBER,
                forecast_deadline=deadline,
                tags=tags,
            )
        return operations.create_prediction(
            question, 65, forecast_deadline=deadline, tags=tags
        )

    def context(prediction, numeric: bool) -> dict[str, int]:
        return {
            "expected_revision_id": prediction.current_revision.revision_id
            if numeric
            else prediction.current_revision_id,
            "expected_metadata_version": prediction.metadata_version,
        }

    for numeric in (False, True):
        kind = "Numeric" if numeric else "Binary"
        for unscored in (False, True):
            label = "No eligible forecast" if unscored else "Earlier forecast scored"
            prediction = create(
                f"{label} · {kind}: which forecast supplied this result?", numeric
            )
            clock.instant += timedelta(hours=1)
            revise = (
                operations.revise_quantile_forecast
                if numeric
                else operations.revise_forecast
            )
            latest = revise(
                prediction.prediction_id,
                {key: value * 10 for key, value in quantiles.items()}
                if numeric
                else 90,
                rationale="Later evidence changed the forecast; the outcome's effective time precedes this revision.",
                **context(prediction, numeric),
            )
            clock.instant += timedelta(hours=1)
            resolve = (
                operations.resolve_numeric_prediction
                if numeric
                else operations.resolve_prediction
            )
            resolve(
                prediction.prediction_id,
                2 if numeric else BinaryOutcome.YES,
                effective_resolution_at=start
                if unscored
                else start + timedelta(minutes=30),
                resolution_notes="The original recorded-at time and every revision remain preserved.",
                **context(latest, numeric),
            )

        prediction = create(f"Corrected Invalid reason · Adaptive {kind}", numeric)
        clock.instant += timedelta(hours=1)
        invalidate = (
            operations.invalidate_numeric_prediction
            if numeric
            else operations.invalidate_prediction
        )
        invalidate(
            prediction.prediction_id,
            reason="The question had ambiguous criteria.",
            **context(prediction, numeric),
        )
        clock.instant += timedelta(hours=1)
        operations.correct_invalidation_reason(
            prediction.prediction_id,
            "The source defined two incompatible outcomes. This clarifies the reason while preserving the original Invalid decision date.",
            expected_correction_id=None,
        )

        clock.instant = start
        request = NewOneShotPrediction(
            f"Waiting for answer · One-Shot {kind}",
            one_shot_contract(
                PredictionType.NUMERIC if numeric else PredictionType.BINARY
            ),
            OneShotValues(quantiles=FiveQuantiles.from_values(quantiles, 0))
            if numeric
            else OneShotValues(probability_percent=70),
            QuantileDefinition("items", 0, NumericValueConstraint.WHOLE_NUMBER)
            if numeric
            else None,
            tags=tags,
        )
        operations.one_shots.create(request)
        pending = operations.one_shots.create(
            replace(request, question=f"Corrected Invalid reason · One-Shot {kind}")
        )
        clock.instant += timedelta(hours=1)
        operations.one_shots.invalidate(
            pending, reason="The original source was ambiguous."
        )
        clock.instant += timedelta(hours=1)
        operations.correct_invalidation_reason(
            pending.prediction_id,
            "Two different answer keys were published. The original exercise cannot be scored reliably.",
            expected_correction_id=None,
        )


if __name__ == "__main__":
    raise SystemExit(main())
