"""Interactive active-forecast mutation workflows for the CLI."""

from reckonsolve.application.errors import (
    ForecastReviewNotAllowedError,
    ForecastRevisionNotAllowedError,
    JournalEntryNotAllowedError,
    LifecycleTransitionNotAllowedError,
    PredictionDeletionNotAllowedError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli_creation import CliInputCancelled, PromptSession
from reckonsolve.cli_text import terminal_text
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    NewNumericForecastRevision,
    NumericPrediction,
    PredictionDetail,
    PredictionStatus,
    PredictionValidationError,
)


def revise_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Append one type-appropriate revision after reviewing current context."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if prediction.status is not PredictionStatus.OPEN:
        raise ForecastRevisionNotAllowedError(prediction.status)

    if isinstance(prediction, NumericPrediction):
        values = _ask_numeric_revision(prediction, session)
        rationale = _optional_line(session.ask("What changed? (optional, one line): "))
        revised = operations.revise_numeric_forecast(
            prediction_id,
            values[0],
            values[1],
            values[2],
            values[3],
            rationale=rationale,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    else:
        probability = _ask_changed_probability(prediction, session)
        rationale = _optional_line(session.ask("What changed? (optional, one line): "))
        revised = operations.revise_forecast(
            prediction_id,
            probability,
            rationale=rationale,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )

    print(file=session.output)
    print(f"Revised Prediction #{prediction_id}.", file=session.output)
    print(
        f"Current forecast: {_forecast_summary(revised)}",
        file=session.output,
    )


def journal_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Append one Journal entry anchored to the reviewed current revision."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
        raise JournalEntryNotAllowedError(prediction.status)

    body = _ask_required_line(
        session,
        "Journal entry (required, one line): ",
        "Journal entry text is required.",
    )
    if isinstance(prediction, NumericPrediction):
        operations.add_numeric_journal_entry(
            prediction_id,
            body,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    else:
        operations.add_journal_entry(
            prediction_id,
            body,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )

    print(file=session.output)
    print(f"Added Journal entry to Prediction #{prediction_id}.", file=session.output)
    print("The current forecast is unchanged.", file=session.output)


def review_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Record deliberate retention of the reviewed current forecast."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if prediction.status is not PredictionStatus.OPEN:
        raise ForecastReviewNotAllowedError(prediction.status)

    print(
        "This records that you reconsidered the forecast and kept it unchanged.",
        file=session.output,
    )
    note = _optional_line(session.ask("Review note (optional, one line): "))
    if isinstance(prediction, NumericPrediction):
        operations.add_numeric_forecast_review(
            prediction_id,
            note=note,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    else:
        operations.add_forecast_review(
            prediction_id,
            note=note,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )

    print(file=session.output)
    print(
        f"Recorded Forecast Review for Prediction #{prediction_id}.",
        file=session.output,
    )
    print("The current forecast is unchanged.", file=session.output)


def resolve_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Record one confirmed terminal outcome against reviewed forecast context."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
        raise LifecycleTransitionNotAllowedError("resolved", prediction.status)

    print(
        "Resolution records a terminal outcome and captures this forecast for "
        "scoring. It cannot be reopened or changed.",
        file=session.output,
    )
    if isinstance(prediction, NumericPrediction):
        actual_value = _ask_exact_actual_value(prediction, session)
    else:
        outcome = _ask_binary_outcome(session)
    resolution_notes = _optional_line(
        session.ask("Resolution notes (optional, one line): ")
    )
    postmortem = _optional_line(session.ask("Postmortem (optional, one line): "))
    _confirm_or_cancel(session, "Resolve this prediction permanently? [y/N]: ")

    if isinstance(prediction, NumericPrediction):
        resolved = operations.resolve_numeric_prediction(
            prediction_id,
            actual_value,
            resolution_notes=resolution_notes,
            postmortem=postmortem,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        if resolved.resolution is None:
            raise RuntimeError("Resolved Numeric Prediction has no resolution record.")
        outcome_summary = (
            f"{resolved.resolution.actual_value} {terminal_text(prediction.unit)}"
        )
    else:
        operations.resolve_prediction(
            prediction_id,
            outcome,
            resolution_notes=resolution_notes,
            postmortem=postmortem,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        outcome_summary = outcome.value.capitalize()

    print(file=session.output)
    print(f"Resolved Prediction #{prediction_id}.", file=session.output)
    print(f"Outcome: {outcome_summary}", file=session.output)


def invalidate_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Record one confirmed Invalid decision against reviewed forecast context."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
        raise LifecycleTransitionNotAllowedError(
            "marked Invalid",
            prediction.status,
        )

    print(
        "Invalid preserves this prediction and its complete history but excludes "
        "it from scoring. It cannot be reopened or changed.",
        file=session.output,
    )
    reason = _optional_line(session.ask("Reason (optional, one line): "))
    _confirm_or_cancel(session, "Mark this prediction Invalid? [y/N]: ")

    if isinstance(prediction, NumericPrediction):
        operations.invalidate_numeric_prediction(
            prediction_id,
            reason=reason,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    else:
        operations.invalidate_prediction(
            prediction_id,
            reason=reason,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )

    print(file=session.output)
    print(f"Marked Prediction #{prediction_id} Invalid.", file=session.output)
    print("Its history is preserved and excluded from scoring.", file=session.output)


def delete_interactively(
    operations: PredictionOperations,
    prediction_id: int,
    session: PromptSession,
) -> None:
    """Permanently delete one confirmed, transaction-current untouched row."""

    prediction = operations.get_prediction_for_navigation(prediction_id)
    _print_reviewed_context(prediction, session)
    if (
        prediction.status is not PredictionStatus.OPEN
        or not prediction.deletion_allowed
    ):
        reason = (
            prediction.status.value
            if prediction.status is not PredictionStatus.OPEN
            else "meaningful_history"
        )
        raise PredictionDeletionNotAllowedError(reason)

    type_label = (
        "Numeric Prediction"
        if isinstance(prediction, NumericPrediction)
        else "Prediction"
    )
    print(
        f"This permanently deletes the {type_label} and its initial forecast. "
        "This action cannot be undone.",
        file=session.output,
    )
    _confirm_or_cancel(session, "Permanently delete this prediction? [y/N]: ")

    if isinstance(prediction, NumericPrediction):
        operations.delete_numeric_prediction(
            prediction_id,
            expected_revision_id=prediction.current_revision.revision_id,
            expected_metadata_version=prediction.metadata_version,
            confirm_permanent_deletion=True,
        )
    else:
        operations.delete_prediction(
            prediction_id,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
            confirm_permanent_deletion=True,
        )

    print(file=session.output)
    print(f"Deleted Prediction #{prediction_id} permanently.", file=session.output)


def _print_reviewed_context(
    prediction: PredictionDetail | NumericPrediction,
    session: PromptSession,
) -> None:
    print(f"Prediction #{prediction.prediction_id}", file=session.output)
    print(f"Question: {terminal_text(prediction.question)}", file=session.output)
    print(f"Status: {prediction.status.value.capitalize()}", file=session.output)
    print(f"Current forecast: {_forecast_summary(prediction)}", file=session.output)
    print(file=session.output)


def _forecast_summary(prediction: PredictionDetail | NumericPrediction) -> str:
    if not isinstance(prediction, NumericPrediction):
        return f"{prediction.probability_percent}% Yes"
    revision = prediction.current_revision
    return (
        f"{revision.confidence_percent}% interval "
        f"{revision.lower_bound} to {revision.upper_bound} "
        f"{terminal_text(prediction.unit)}; median {revision.median_estimate} "
        f"{terminal_text(prediction.unit)}"
    )


def _ask_changed_probability(
    prediction: PredictionDetail,
    session: PromptSession,
) -> int:
    while True:
        value = session.ask("New probability (0-100): ").strip()
        try:
            probability = int(value)
        except ValueError:
            probability = -1
        if not 0 <= probability <= 100:
            session.explain_error("Probability must be a whole number from 0 to 100.")
            continue
        if probability == prediction.probability_percent:
            session.explain_error(
                "The probability is unchanged. Enter a different probability, "
                "or cancel and use review or journal instead."
            )
            continue
        if probability in (0, 100):
            print(
                f"Note: {probability}% expresses absolute certainty.",
                file=session.output,
            )
        return probability


def _ask_numeric_revision(
    prediction: NumericPrediction,
    session: PromptSession,
) -> tuple[str, str, str, int]:
    current = prediction.current_revision
    while True:
        lower_bound = _ask_with_default(
            session,
            "Lower bound",
            str(current.lower_bound),
        )
        median_estimate = _ask_with_default(
            session,
            "Median estimate",
            str(current.median_estimate),
        )
        upper_bound = _ask_with_default(
            session,
            "Upper bound",
            str(current.upper_bound),
        )
        confidence = _ask_confidence_with_default(
            session,
            current.confidence_percent,
        )
        try:
            candidate = NewNumericForecastRevision(
                lower_bound=FixedPrecisionValue.from_value(
                    lower_bound,
                    prediction.decimal_places,
                    field="lower_bound",
                ),
                median_estimate=FixedPrecisionValue.from_value(
                    median_estimate,
                    prediction.decimal_places,
                    field="median_estimate",
                ),
                upper_bound=FixedPrecisionValue.from_value(
                    upper_bound,
                    prediction.decimal_places,
                    field="upper_bound",
                ),
                confidence_percent=confidence,
            )
        except PredictionValidationError as error:
            session.explain_error(f"Invalid numeric forecast: {error}")
            continue
        if (
            candidate.lower_bound == current.lower_bound
            and candidate.median_estimate == current.median_estimate
            and candidate.upper_bound == current.upper_bound
            and candidate.confidence_percent == current.confidence_percent
        ):
            session.explain_error(
                "The numeric forecast is unchanged. Change at least one value, "
                "or cancel and use review or journal instead."
            )
            continue
        return lower_bound, median_estimate, upper_bound, confidence


def _ask_binary_outcome(session: PromptSession) -> BinaryOutcome:
    while True:
        value = session.ask("Outcome (yes/no): ").strip().casefold()
        if value in ("y", "yes"):
            return BinaryOutcome.YES
        if value in ("n", "no"):
            return BinaryOutcome.NO
        session.explain_error("Enter yes or no.")


def _ask_exact_actual_value(
    prediction: NumericPrediction,
    session: PromptSession,
) -> str:
    while True:
        value = session.ask(f"Actual value ({terminal_text(prediction.unit)}): ")
        if not value.strip():
            session.explain_error("Actual value is required.")
            continue
        try:
            FixedPrecisionValue.from_value(
                value,
                prediction.decimal_places,
                field="actual_value",
            )
        except PredictionValidationError as error:
            session.explain_error(f"Invalid actual value: {error}")
            continue
        return value


def _ask_with_default(
    session: PromptSession,
    label: str,
    default: str,
) -> str:
    value = session.ask(f"{label} [{default}]: ")
    return value if value.strip() else default


def _ask_confidence_with_default(
    session: PromptSession,
    default: int,
) -> int:
    while True:
        value = session.ask(f"Confidence [{default}]: ").strip()
        if not value:
            return default
        try:
            confidence = int(value)
        except ValueError:
            confidence = 0
        if 1 <= confidence <= 99:
            return confidence
        session.explain_error("Confidence must be a whole number from 1 to 99.")


def _ask_required_line(
    session: PromptSession,
    prompt: str,
    missing_message: str,
) -> str:
    while True:
        value = session.ask(prompt)
        if value.strip():
            return value
        session.explain_error(missing_message)


def _optional_line(value: str) -> str | None:
    return value if value.strip() else None


def _confirm_or_cancel(session: PromptSession, prompt: str) -> None:
    while True:
        value = session.ask(prompt).strip().casefold()
        if value in ("y", "yes"):
            return
        if not value or value in ("n", "no"):
            raise CliInputCancelled
        session.explain_error("Enter y or n.")
