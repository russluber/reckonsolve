"""Line-oriented One-Shot input over the shared application operations."""

from dataclasses import replace
from datetime import datetime

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli_creation import (
    CliInputCancelled,
    PromptSession,
    _ask_required_text,
    _ask_whole_number,
    _ask_yes_no,
    ask_quantiles,
)
from reckonsolve.cli_text import terminal_text
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotDetail,
    OneShotValues,
    ReportedTime,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)
from reckonsolve.one_shot_display import detail_lines, forecast_text, status_text
from reckonsolve.reported_time import parse_reported_offset


def ask_reported_time(session: PromptSession, label: str) -> ReportedTime | None:
    while True:
        raw = session.ask(
            f"{label} (user-reported YYYY-MM-DD HH:MM, optional): "
        ).strip()
        if not raw:
            return None
        try:
            wall = datetime.fromisoformat(raw)
            ReportedTime(wall)
        except ValueError:
            session.explain_error(
                "Enter a wall-clock date and minute without an offset or seconds, or leave blank."
            )
            continue
        approximate = _ask_yes_no(session, "Approximate time? [y/N]: ", default=False)
        while True:
            raw_offset = session.ask("UTC offset (optional, e.g. -07:00): ").strip()
            try:
                return ReportedTime(
                    wall,
                    approximate,
                    parse_reported_offset(raw_offset) if raw_offset else None,
                )
            except ValueError as error:
                session.explain_error(str(error))


def ask_answer(
    session: PromptSession, values: OneShotValues, definition: QuantileDefinition | None
) -> OneShotValues:
    while True:
        raw = session.ask(
            "Actual value: " if definition else "Answer [yes/no]: "
        ).strip()
        try:
            if definition:
                answer = FixedPrecisionValue.from_value(raw, definition.decimal_places)
                definition.validate_value(answer)
            else:
                normalized = {"y": "yes", "n": "no"}.get(raw.casefold(), raw.casefold())
                answer = BinaryOutcome(normalized)
            break
        except ValueError as error:
            session.explain_error(str(error) if definition else "Choose yes or no.")
    reveal = ask_reported_time(session, "When did you check the answer?")
    notes = session.ask("Resolution notes (optional, one line): ")
    postmortem = session.ask("Postmortem (optional, one line): ")
    return replace(
        values,
        answer=answer,
        reveal_reported=reveal,
        resolution_notes=notes,
        postmortem=postmortem,
    )


def create_one_shot(
    operations: PredictionOperations,
    prediction_type: PredictionType,
    session: PromptSession,
) -> OneShotDetail:
    print(
        "One-Shot: enter the final guess you settled on before checking an already-existing answer. Reported times are optional documentation.",
        file=session.output,
    )
    question = _ask_required_text(session, "Question: ", "Question is required.")
    definition = None
    if prediction_type is PredictionType.BINARY:
        probability = _ask_whole_number(
            session,
            "Probability [50]: ",
            minimum=0,
            maximum=100,
            default=50,
            label="Probability",
        )
        values = OneShotValues(probability_percent=probability)
    else:
        unit = _ask_required_text(session, "Unit: ", "Unit is required.")
        precision = _ask_whole_number(
            session,
            "Decimal places [0]: ",
            minimum=0,
            maximum=6,
            default=0,
            label="Decimal places",
        )
        while True:
            choice = (
                session.ask(
                    "Value constraint: decimal/continuous-style or whole-number [d/w]: "
                )
                .strip()
                .casefold()
            )
            if choice in ("d", "w"):
                break
            session.explain_error("Choose d or w; this definition is permanent.")
        definition = QuantileDefinition(
            unit,
            precision,
            NumericValueConstraint.CONTINUOUS
            if choice == "d"
            else NumericValueConstraint.WHOLE_NUMBER,
        )
        values = OneShotValues(
            quantiles=FiveQuantiles.from_values(
                ask_quantiles(session, definition), precision
            )
        )
    values = replace(
        values,
        forecast_reported=ask_reported_time(
            session, "When did you finalize the forecast?"
        ),
    )
    background = session.ask(
        "Background (optional; context and how you will check the answer): "
    )
    if _ask_yes_no(session, "Include the answer now? [y/N]: ", default=False):
        values = ask_answer(session, values, definition)
    details = {}
    if _ask_yes_no(session, "Add optional details? [y/N]: ", default=False):
        details = {
            "rationale": session.ask(
                "Rationale / when I started thinking (optional): "
            ),
            "tags": tuple(
                t.strip()
                for t in session.ask("Tags (optional, comma-separated): ").split(",")
                if t.strip()
            ),
        }
    if not _ask_yes_no(session, "Save this One-Shot? [y/N]: ", default=False):
        raise CliInputCancelled
    try:
        saved = operations.one_shots.create(
            NewOneShotPrediction(
                question,
                one_shot_contract(prediction_type),
                values,
                definition,
                background=background,
                **details,
            )
        )
    except ValueError as error:
        raise ApplicationError(str(error)) from error
    print(
        terminal_text(
            "\n".join(detail_lines(saved, operations.one_shots.score(saved)))
        ),
        file=session.output,
    )
    return saved


def mutate_one_shot(
    action: str,
    operations: PredictionOperations,
    detail: OneShotDetail,
    session: PromptSession,
) -> None:
    if action in ("revise", "review"):
        operations.require_deadline_operation(detail.prediction_id)
    print(
        terminal_text(
            f"Prediction #{detail.prediction_id}: {detail.question}\nOne-Shot · {status_text(detail)}\n"
            + forecast_text(
                detail.record.effective,
                detail.record.definition.unit if detail.record.definition else "",
            )
        ),
        file=session.output,
    )
    if detail.status is not PredictionStatus.OPEN:
        raise ApplicationError(
            "This One-Shot is terminal. Use desktop Correct transcription for copying mistakes."
        )
    if action == "journal":
        body = _ask_required_text(
            session, "Journal entry (one line): ", "Journal text is required."
        )
        operations.one_shots.add_journal(detail, body)
    elif action == "resolve":
        values = ask_answer(session, detail.record.effective, detail.record.definition)
        if not _ask_yes_no(
            session,
            "Save the answer and mark this One-Shot Resolved? [y/N]: ",
            default=False,
        ):
            raise CliInputCancelled
        saved = operations.one_shots.add_answer(detail, values)
        print(
            terminal_text(
                "\n".join(detail_lines(saved, operations.one_shots.score(saved)))
            ),
            file=session.output,
        )
        return
    elif action == "invalidate":
        reason = session.ask("Reason (optional): ")
        if not _ask_yes_no(
            session,
            "Preserve this One-Shot as Invalid, excluded from scoring? [y/N]: ",
            default=False,
        ):
            raise CliInputCancelled
        operations.one_shots.invalidate(detail, reason=reason)
    elif action == "delete":
        if not detail.deletion_allowed:
            raise ApplicationError(
                "This One-Shot has meaningful history. Mark it Invalid to preserve it."
            )
        if not _ask_yes_no(
            session,
            "Permanently delete this untouched One-Shot? [y/N]: ",
            default=False,
        ):
            raise CliInputCancelled
        operations.one_shots.delete(detail, confirmed=True)
    print(f"Saved: {action} for One-Shot #{detail.prediction_id}.", file=session.output)
