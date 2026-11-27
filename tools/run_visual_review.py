"""Launch disposable current-model visual profiles without touching user data."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from reckonsolve.app import run
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotValues,
    ReportedTime,
)
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
        choices=(
            "empty",
            "representative",
            "long-text",
            "detail",
            "performance",
            "relocation",
            "integrated",
        ),
        help="Fixture shape to display; all data is deleted after the window closes.",
    )
    arguments = parser.parse_args()

    with TemporaryDirectory(prefix="reckonsolve-visual-review-") as temporary:
        if arguments.profile in {"relocation", "integrated"}:
            bootstrap = Path(temporary) / DEVELOPMENT_APPLICATION.application_name
            bootstrap.mkdir()
            _seed_performance_database(bootstrap / "reckonsolve.sqlite3", per_cohort=3)
            if arguments.profile == "integrated":
                _seed_review_database(
                    bootstrap / "reckonsolve.sqlite3", long_text=False, detail=True
                )
            for name in ("New journal folder", "Another journal folder"):
                (Path(temporary) / name).mkdir()
            print(f"Disposable move destinations: {Path(temporary)}")
            return run(
                argv=["reckonsolve-visual-review"],
                identity=DEVELOPMENT_APPLICATION,
                bootstrap_directory=bootstrap,
            )
        database_path = Path(temporary) / "reckonsolve.sqlite3"
        if arguments.profile == "performance":
            _seed_performance_database(database_path)
        elif arguments.profile != "empty":
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


def _seed_performance_database(database_path: Path, *, per_cohort: int = 12) -> None:
    """Four independent populations, exact units, ties and a zero-result tag.

    Controlled canonical writes also support larger disposable timing runs; no
    historical timestamps, scores or applied migrations are patched with SQL.
    """
    database = Database.open(database_path)
    clock = _ReviewClock(datetime(2026, 11, 1, 12, tzinfo=UTC))
    operations = PredictionOperations(database, clock)
    try:
        for index in range(per_cohort):
            clock.instant = datetime(2026, 11, 1, 12, tzinfo=UTC) + timedelta(
                minutes=index * 5
            )
            deadline = clock.instant + timedelta(days=5)
            tags = () if index % 3 == 0 else ("Work" if index % 3 == 1 else "Personal",)
            probability = (20, 50, 75, 90)[index % 4]
            whole = index % 2 == 1
            precision = 0 if whole else 1
            constraint = (
                NumericValueConstraint.WHOLE_NUMBER
                if whole
                else NumericValueConstraint.CONTINUOUS
            )
            unit = "days" if index % 4 < 2 else "items"
            values = {5: -10, 25: -2, 50: 0, 75: 4, 95: 12}
            actual = (-12, -2, 0, 3, 15)[index % 5]
            binary = operations.create_prediction(
                f"Adaptive Binary report example {index + 1}",
                probability,
                forecast_deadline=deadline,
                tags=tags,
            )
            numeric = operations.create_numeric_prediction(
                f"Adaptive Numeric report example {index + 1}",
                unit,
                precision,
                values,
                value_constraint=constraint,
                forecast_deadline=deadline,
                tags=tags,
            )
            clock.instant += timedelta(days=1)
            if index % 2 == 0:
                binary = operations.revise_forecast(
                    binary.prediction_id,
                    60,
                    expected_revision_id=binary.current_revision_id,
                    expected_metadata_version=binary.metadata_version,
                )
                numeric = operations.revise_quantile_forecast(
                    numeric.prediction_id,
                    {5: -10, 25: -1, 50: 1, 75: 5, 95: 12},
                    expected_revision_id=numeric.current_revision.revision_id,
                    expected_metadata_version=numeric.metadata_version,
                )
            clock.instant = (
                deadline - timedelta(hours=12) if index % 2 == 0 else deadline
            )
            outcome = BinaryOutcome.YES if index % 3 else BinaryOutcome.NO
            operations.resolve_prediction(
                binary.prediction_id,
                outcome,
                use_recorded_time=True,
                expected_revision_id=binary.current_revision_id,
                expected_metadata_version=binary.metadata_version,
            )
            operations.resolve_numeric_prediction(
                numeric.prediction_id,
                actual,
                use_recorded_time=True,
                expected_revision_id=numeric.current_revision.revision_id,
                expected_metadata_version=numeric.metadata_version,
            )
            one = operations.one_shots.create(
                NewOneShotPrediction(
                    f"One-Shot Binary report example {index + 1}",
                    one_shot_contract(PredictionType.BINARY),
                    OneShotValues(probability_percent=probability, answer=outcome),
                    tags=tags,
                )
            )
            operations.one_shots.create(
                NewOneShotPrediction(
                    f"One-Shot Numeric report example {index + 1}",
                    one_shot_contract(PredictionType.NUMERIC),
                    OneShotValues(
                        quantiles=FiveQuantiles.from_values(values, precision),
                        answer=FixedPrecisionValue.from_value(actual, precision),
                    ),
                    QuantileDefinition(unit, precision, constraint),
                    tags=tags,
                )
            )
            if index == 0:
                clock.instant += timedelta(minutes=1)
                operations.one_shots.correct(
                    one,
                    replace(one.record.effective, probability_percent=30),
                )
        operations.create_prediction(
            "Unresolved-only tag: no eligible Performance results",
            50,
            forecast_deadline=clock.instant + timedelta(days=30),
            tags=("No results yet",),
        )
    finally:
        database.close()


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
            _seed_finish_cases(database, now=datetime.now(UTC))
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


def _seed_finish_cases(database: Database, *, now: datetime) -> None:
    """Long/corrected histories are complete synthetic operations, never SQL edits."""
    for numeric in (False, True):
        _seed_adaptive_history(database, now=now, numeric=numeric, resolved=False)
        _seed_adaptive_history(database, now=now, numeric=numeric, resolved=True)
        _seed_corrected_exercise(database, now=now, numeric=numeric)
    clock = _ReviewClock(now - timedelta(days=2))
    operations = PredictionOperations(database, clock, UTC)
    for question, precision, values in (
        (
            "All equal · Numeric: can every percentile be zero?",
            0,
            {5: 0, 25: 0, 50: 0, 75: 0, 95: 0},
        ),
        (
            "Nearby percentiles · Numeric: can close values remain exact?",
            4,
            {5: "-1000000", 25: "0.0001", 50: "0.0002", 75: "0.0003", 95: "1000000"},
        ),
    ):
        operations.create_numeric_prediction(
            question,
            "million international passenger kilometres",
            precision,
            values,
            value_constraint=NumericValueConstraint.CONTINUOUS,
            forecast_deadline=now + timedelta(days=30),
            tags=("Detail review", "Numeric layout"),
        )


def _review_context(prediction, numeric: bool) -> dict[str, int]:
    return {
        "expected_revision_id": prediction.current_revision.revision_id
        if numeric
        else prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


def _clarify_review_question(
    operations: PredictionOperations, prediction, question: str
):
    return operations.update_metadata(
        prediction.prediction_id,
        question=question,
        background=prediction.background,
        resolution_criteria=prediction.resolution_criteria,
        forecast_deadline=prediction.forecast_deadline,
        expected_resolution=prediction.expected_resolution,
        tags=prediction.tags,
        expected_metadata_version=prediction.metadata_version,
        confirm_meaning_change=True,
    )


def _seed_adaptive_history(
    database: Database, *, now: datetime, numeric: bool, resolved: bool
) -> None:
    clock = _ReviewClock(now - timedelta(days=6))
    operations = PredictionOperations(database, clock, UTC)
    kind = "Numeric" if numeric else "Binary"
    prefix = "Reflection history" if resolved else "Long history"
    question = f"{prefix} · Adaptive {kind}: will the copperbridge source remain the basis of the published result?"
    common = {
        "forecast_deadline": now + timedelta(days=30),
        "rationale": "The original forecast is preserved even after many changes.",
        "resolution_criteria": "Use the published final observation.\n\n"
        + "Compare the published source, defined period and relevant population before recording the answer. "
        * 14,
        "background": "Optional background stays available without crowding ordinary reading. "
        * 20,
        "tags": ("Detail review", prefix),
    }
    prediction = (
        operations.create_numeric_prediction(
            question,
            "items",
            0,
            {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
            value_constraint=NumericValueConstraint.WHOLE_NUMBER,
            **common,
        )
        if numeric
        else operations.create_prediction(question, 60, **common)
    )
    add_journal = (
        operations.add_numeric_journal_entry
        if numeric
        else operations.add_journal_entry
    )
    clock.instant += timedelta(hours=1)
    first_journal = add_journal(
        prediction.prediction_id,
        "Birchbeacon was the initially recorded source. "
        + "This substantial Journal body should expand without losing its original position. "
        * 12,
        **_review_context(prediction, numeric),
    )
    for index in range(3 if resolved else 24):
        clock.instant += timedelta(hours=1)
        revise = (
            operations.revise_quantile_forecast
            if numeric
            else operations.revise_forecast
        )
        prediction = revise(
            prediction.prediction_id,
            {5: index - 1, 25: index, 50: index + 1, 75: index + 2, 95: index + 3}
            if numeric
            else 61 + index,
            rationale=f"Revision {index + 2}: new evidence changed the judgment.\n\n"
            + "The complete rationale remains readable and selectable in true chronology. "
            * (10 if index == 12 else 2),
            **_review_context(prediction, numeric),
        )
        clock.instant += timedelta(minutes=10)
        add_journal(
            prediction.prediction_id,
            f"Evidence entry {index + 1}: this note does not revise or refresh the forecast. "
            + "Preserve the current body and original anchor. " * 4,
            **_review_context(prediction, numeric),
        )
        if index % 4 == 0:
            clock.instant += timedelta(minutes=10)
            review = (
                operations.add_numeric_forecast_review
                if numeric
                else operations.add_forecast_review
            )
            review(
                prediction.prediction_id,
                note="I deliberately reconsidered and kept this complete forecast unchanged.",
                **_review_context(prediction, numeric),
            )
    clock.instant += timedelta(hours=1)
    correct_journal = (
        operations.correct_numeric_journal_entry
        if numeric
        else operations.correct_journal_entry
    )
    correct_journal(
        prediction.prediction_id,
        first_journal.record_id if numeric else first_journal.entry_id,
        "Cedarlight is the corrected source. Earlier wording remains available only in edit history.",
        expected_correction_id=None,
    )
    clock.instant += timedelta(hours=1)
    prediction = _clarify_review_question(
        operations,
        prediction,
        f"{prefix} · Adaptive {kind}: will the final published observation satisfy the clarified question and preserve the complete forecast history?",
    )
    if resolved:
        clock.instant += timedelta(hours=1)
        resolve = (
            operations.resolve_numeric_prediction
            if numeric
            else operations.resolve_prediction
        )
        resolve(
            prediction.prediction_id,
            2 if numeric else BinaryOutcome.YES,
            use_recorded_time=True,
            resolution_notes="Initial factual notes use the first published answer.",
            **_review_context(prediction, numeric),
        )
        clock.instant += timedelta(hours=1)
        correct = (
            operations.correct_numeric_resolution
            if numeric
            else operations.correct_binary_resolution
        )
        history = correct(
            prediction.prediction_id,
            3 if numeric else BinaryOutcome.NO,
            resolution_notes="Corrected factual notes use the verified publication.",
            postmortem=None,
            correction_reason="The original answer was transcribed from the preliminary source.",
            expected_correction_id=None,
        )
        clock.instant += timedelta(hours=1)
        save_postmortem(
            operations,
            history,
            "Later reflection: I checked the final source and separated evidence from transcription repair.",
        )


def _seed_corrected_exercise(
    database: Database, *, now: datetime, numeric: bool
) -> None:
    clock = _ReviewClock(now - timedelta(days=5))
    operations = PredictionOperations(database, clock, UTC)
    kind = "Numeric" if numeric else "Binary"
    values = (
        OneShotValues(
            quantiles=FiveQuantiles.from_values(
                {5: -2, 25: -1, 50: 0, 75: 2, 95: 4}, 0
            ),
            answer=FixedPrecisionValue.from_value(2, 0),
        )
        if numeric
        else OneShotValues(probability_percent=70, answer=BinaryOutcome.YES)
    )
    report = ReportedTime(
        (now - timedelta(days=6)).replace(tzinfo=None, second=0, microsecond=0),
        approximate=True,
        offset_minutes=0,
    )
    answer = values.answer
    values = replace(values, answer=None, forecast_reported=report)
    prediction = operations.one_shots.create(
        NewOneShotPrediction(
            f"Corrected exercise · One-Shot {kind}: did the copperbridge answer key match the original transcription?",
            one_shot_contract(
                PredictionType.NUMERIC if numeric else PredictionType.BINARY
            ),
            values,
            QuantileDefinition("items", 0, NumericValueConstraint.WHOLE_NUMBER)
            if numeric
            else None,
            rationale="The original guess was finalized before checking the external answer.",
            tags=("Detail review", "Corrected exercise"),
        )
    )
    # Journal capture precedes the first answer; correction retains its anchor.
    clock.instant += timedelta(hours=1)
    prediction = operations.one_shots.add_journal(
        prediction,
        "Birchbeacon was the first transcribed evidence. "
        + "Substantial context remains readable without changing the saved forecast. "
        * 10,
    )
    clock.instant += timedelta(hours=1)
    prediction = operations.one_shots.correct_journal(
        prediction,
        prediction.journals[0].entry_id,
        "Cedarlight is the corrected evidence. Earlier wording stays available on request.",
        expected_correction_id=None,
    )
    clock.instant += timedelta(hours=1)
    prediction = operations.one_shots.add_answer(
        prediction,
        replace(
            prediction.record.effective,
            answer=answer,
            reveal_reported=replace(
                report, wall_time=report.wall_time + timedelta(minutes=30)
            ),
        ),
    )
    clock.instant += timedelta(hours=1)
    prediction = _clarify_review_question(
        operations,
        prediction,
        f"Corrected exercise · One-Shot {kind}: does the verified answer key match the clarified completed exercise?",
    )
    clock.instant += timedelta(hours=1)
    repaired = operations.one_shots.correct(
        prediction,
        replace(
            prediction.record.effective,
            quantiles=FiveQuantiles.from_values({5: -2, 25: -1, 50: 1, 75: 2, 95: 4}, 0)
            if numeric
            else None,
            probability_percent=None if numeric else 75,
            answer=FixedPrecisionValue.from_value(3, 0)
            if numeric
            else BinaryOutcome.NO,
        ),
        note="Repaired the transcription against the verified answer key; originals and reported minutes remain intact.",
    )
    clock.instant += timedelta(hours=1)
    operations.one_shots.save_postmortem(
        repaired,
        "My later reflection is new work, distinct from the transcription repair.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
