"""Interactive Binary and Numeric creation prompts for the CLI."""

from dataclasses import dataclass
from datetime import date
from typing import TextIO

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.domain.predictions import (
    MAX_METADATA_DATE,
    MAX_NUMERIC_DECIMAL_PLACES,
    MIN_METADATA_DATE,
    MIN_NUMERIC_DECIMAL_PLACES,
    FixedPrecisionValue,
    NewNumericForecastRevision,
    NumericPrediction,
    PredictionDetail,
    PredictionType,
    PredictionValidationError,
)


class CliInputCancelled(Exception):
    """Raised when interactive input ends before a mutation is submitted."""


@dataclass(frozen=True, slots=True)
class CreationDetails:
    """Optional initial Prediction and first-revision values."""

    rationale: str | None = None
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class PromptSession:
    """Line-oriented, injectable terminal input and output."""

    input: TextIO
    output: TextIO
    errors: TextIO

    def ask(self, prompt: str) -> str:
        print(prompt, end="", file=self.output, flush=True)
        value = self.input.readline()
        if value == "":
            raise CliInputCancelled
        return value.rstrip("\r\n")

    def explain_error(self, message: str) -> None:
        print(message, file=self.errors)


def create_interactively(
    operations: PredictionOperations,
    prediction_type: PredictionType,
    session: PromptSession,
) -> PredictionDetail | NumericPrediction:
    """Collect one complete creation request, then persist it atomically."""

    if prediction_type is PredictionType.BINARY:
        return _create_binary(operations, session)
    return _create_numeric(operations, session)


def _create_binary(
    operations: PredictionOperations,
    session: PromptSession,
) -> PredictionDetail:
    question = _ask_required_text(session, "Question: ", "Question is required.")
    probability = _ask_whole_number(
        session,
        "Probability [50]: ",
        minimum=0,
        maximum=100,
        default=50,
        label="Probability",
    )
    if probability in (0, 100):
        print(
            f"Note: {probability}% expresses absolute certainty.",
            file=session.output,
        )
    details = _ask_creation_details(session)
    return operations.create_prediction(
        question,
        probability,
        rationale=details.rationale,
        background=details.background,
        resolution_criteria=details.resolution_criteria,
        forecast_deadline=details.forecast_deadline,
        expected_resolution=details.expected_resolution,
        tags=details.tags,
    )


def _create_numeric(
    operations: PredictionOperations,
    session: PromptSession,
) -> NumericPrediction:
    question = _ask_required_text(session, "Question: ", "Question is required.")
    unit = _ask_required_text(session, "Unit: ", "Unit is required.")
    decimal_places = _ask_whole_number(
        session,
        "Decimal places [0]: ",
        minimum=MIN_NUMERIC_DECIMAL_PLACES,
        maximum=MAX_NUMERIC_DECIMAL_PLACES,
        default=0,
        label="Decimal places",
    )
    lower_bound, median_estimate, upper_bound, confidence = _ask_numeric_forecast(
        session,
        decimal_places,
    )
    details = _ask_creation_details(session)
    return operations.create_numeric_prediction(
        question,
        unit,
        decimal_places,
        lower_bound,
        median_estimate,
        upper_bound,
        confidence,
        rationale=details.rationale,
        background=details.background,
        resolution_criteria=details.resolution_criteria,
        forecast_deadline=details.forecast_deadline,
        expected_resolution=details.expected_resolution,
        tags=details.tags,
    )


def _ask_numeric_forecast(
    session: PromptSession,
    decimal_places: int,
) -> tuple[str, str, str, int]:
    while True:
        lower_bound = _ask_required_text(
            session,
            "Lower bound: ",
            "Lower bound is required.",
        )
        median_estimate = _ask_required_text(
            session,
            "Median estimate: ",
            "Median estimate is required.",
        )
        upper_bound = _ask_required_text(
            session,
            "Upper bound: ",
            "Upper bound is required.",
        )
        confidence = _ask_whole_number(
            session,
            "Confidence [80]: ",
            minimum=1,
            maximum=99,
            default=80,
            label="Confidence",
        )
        try:
            NewNumericForecastRevision(
                lower_bound=FixedPrecisionValue.from_value(
                    lower_bound,
                    decimal_places,
                    field="lower_bound",
                ),
                median_estimate=FixedPrecisionValue.from_value(
                    median_estimate,
                    decimal_places,
                    field="median_estimate",
                ),
                upper_bound=FixedPrecisionValue.from_value(
                    upper_bound,
                    decimal_places,
                    field="upper_bound",
                ),
                confidence_percent=confidence,
            )
        except PredictionValidationError as error:
            session.explain_error(f"Invalid numeric forecast: {error}")
            continue
        return lower_bound, median_estimate, upper_bound, confidence


def _ask_creation_details(session: PromptSession) -> CreationDetails:
    if not _ask_yes_no(session, "Add optional details? [y/N]: ", default=False):
        return CreationDetails()

    rationale = _optional_line(session.ask("Initial rationale (optional, one line): "))
    background = _optional_line(session.ask("Background (optional, one line): "))
    resolution_criteria = _optional_line(
        session.ask("Resolution Criteria (optional, one line): ")
    )
    forecast_deadline = _ask_optional_date(
        session,
        "Forecast Deadline (YYYY-MM-DD, optional): ",
    )
    expected_resolution = _ask_optional_date(
        session,
        "Expected Resolution (YYYY-MM-DD, optional): ",
    )
    tags_text = session.ask("Tags (optional, comma-separated): ")
    tags = tuple(part.strip() for part in tags_text.split(","))
    return CreationDetails(
        rationale=rationale,
        background=background,
        resolution_criteria=resolution_criteria,
        forecast_deadline=forecast_deadline,
        expected_resolution=expected_resolution,
        tags=tags,
    )


def _ask_required_text(
    session: PromptSession,
    prompt: str,
    missing_message: str,
) -> str:
    while True:
        value = session.ask(prompt)
        if value.strip():
            return value
        session.explain_error(missing_message)


def _ask_whole_number(
    session: PromptSession,
    prompt: str,
    *,
    minimum: int,
    maximum: int,
    default: int,
    label: str,
) -> int:
    while True:
        value = session.ask(prompt).strip()
        if not value:
            return default
        try:
            parsed = int(value)
        except ValueError:
            parsed = minimum - 1
        if minimum <= parsed <= maximum:
            return parsed
        session.explain_error(
            f"{label} must be a whole number from {minimum} to {maximum}."
        )


def _ask_yes_no(
    session: PromptSession,
    prompt: str,
    *,
    default: bool,
) -> bool:
    while True:
        value = session.ask(prompt).strip().casefold()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        session.explain_error("Enter y or n.")


def _ask_optional_date(session: PromptSession, prompt: str) -> date | None:
    while True:
        value = session.ask(prompt).strip()
        if not value:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            parsed = None
        if parsed is not None and MIN_METADATA_DATE <= parsed <= MAX_METADATA_DATE:
            return parsed
        session.explain_error(
            "Enter a date from 1752-09-14 through 9999-12-31 as YYYY-MM-DD, "
            "or leave it blank."
        )


def _optional_line(value: str) -> str | None:
    return value if value.strip() else None
