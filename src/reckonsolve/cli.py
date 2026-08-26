"""Human-readable command-line companion for Reckonsolve."""

import argparse
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TextIO

from PySide6.QtCore import QCoreApplication

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli_creation import (
    CliInputCancelled,
    PromptSession,
    create_interactively,
)
from reckonsolve.cli_mutations import (
    delete_interactively,
    invalidate_interactively,
    journal_interactively,
    resolve_interactively,
    review_interactively,
    revise_interactively,
)
from reckonsolve.cli_text import terminal_text
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError
from reckonsolve.domain.attention import DashboardSnapshot
from reckonsolve.domain.browser import PredictionBrowserItem
from reckonsolve.domain.predictions import (
    DefinitionChange,
    FixedPrecisionValue,
    ForecastReviewTimelineEvent,
    ForecastTimelineEvent,
    JournalCorrection,
    JournalTimelineEvent,
    NumericForecastReviewTimelineEvent,
    NumericForecastTimelineEvent,
    NumericJournalTimelineEvent,
    NumericPrediction,
    PredictionDetail,
    PredictionStatus,
    PredictionType,
    TimelineEvent,
)
from reckonsolve.identity import (
    DEVELOPMENT_APPLICATION,
    STABLE_APPLICATION,
    ApplicationIdentity,
)
from reckonsolve.paths import ApplicationDataPathError, resolve_database_path


@dataclass(slots=True)
class CliRuntime:
    """Objects owned by one command-line invocation."""

    database: Database
    operations: PredictionOperations
    identity: ApplicationIdentity

    def close(self) -> None:
        """Close persistence deterministically."""

        self.database.close()


@dataclass(frozen=True, slots=True)
class AttentionIndicators:
    """Prediction identifiers in the two non-lifecycle attention buckets."""

    needs_attention: frozenset[int]
    ready_to_resolve: frozenset[int]

    @classmethod
    def from_snapshot(cls, snapshot: DashboardSnapshot) -> "AttentionIndicators":
        return cls(
            needs_attention=frozenset(
                prediction.prediction_id
                for prediction in snapshot.needs_attention_predictions
            ),
            ready_to_resolve=frozenset(
                prediction.prediction_id
                for prediction in snapshot.ready_to_resolve_predictions
            ),
        )

    def labels_for(self, prediction_id: int) -> tuple[str, ...]:
        labels: list[str] = []
        if prediction_id in self.needs_attention:
            labels.append("Needs Attention")
        if prediction_id in self.ready_to_resolve:
            labels.append("Ready to Resolve")
        return tuple(labels)


def create_runtime(
    *,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
) -> CliRuntime:
    """Compose the CLI against the identity-selected canonical database."""

    QCoreApplication.setApplicationName(identity.application_name)
    resolved_database_path = resolve_database_path(database_path)
    database = Database.open(resolved_database_path)
    try:
        operations = PredictionOperations(database)
    except BaseException:
        database.close()
        raise
    return CliRuntime(
        database=database,
        operations=operations,
        identity=identity,
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    database_path: Path | None = None,
    identity: ApplicationIdentity = STABLE_APPLICATION,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse and execute one CLI command, returning its process status."""

    input_stream = sys.stdin if stdin is None else stdin
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    parser = _build_parser(identity)
    arguments = parser.parse_args(argv)

    runtime: CliRuntime | None = None
    try:
        runtime = create_runtime(database_path=database_path, identity=identity)
        if arguments.command == "list":
            return _run_list(runtime.operations, arguments, output)
        if arguments.command == "show":
            return _run_show(runtime.operations, arguments.prediction_id, output)
        if arguments.command == "create":
            return _run_create(
                runtime.operations,
                PredictionType(arguments.prediction_type),
                input_stream,
                output,
                errors,
            )
        if arguments.command == "revise":
            revise_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        if arguments.command == "journal":
            journal_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        if arguments.command == "review":
            review_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        if arguments.command == "resolve":
            resolve_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        if arguments.command == "invalidate":
            invalidate_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        if arguments.command == "delete":
            delete_interactively(
                runtime.operations,
                arguments.prediction_id,
                PromptSession(input_stream, output, errors),
            )
            return 0
        parser.error("A command is required.")
    except (CliInputCancelled, KeyboardInterrupt):
        print("Cancelled. No changes were made.", file=errors)
        return 130
    except (
        ApplicationDataPathError,
        ApplicationError,
        MigrationError,
        OSError,
        sqlite3.Error,
    ) as error:
        print(f"Error: {error}", file=errors)
        return 1
    finally:
        if runtime is not None:
            runtime.close()
    return 2


def _build_parser(identity: ApplicationIdentity) -> argparse.ArgumentParser:
    program_name = (
        "reckonsolve-cli-dev"
        if identity == DEVELOPMENT_APPLICATION
        else "reckonsolve-cli"
    )
    parser = argparse.ArgumentParser(
        prog=program_name,
        description=(
            "Use the same local forecasting journal as the matching "
            "Reckonsolve desktop application."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('reckonsolve')}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser(
        "list",
        help="List and filter current Prediction summaries.",
        description="List current Binary and Numeric Prediction summaries.",
    )
    list_parser.add_argument(
        "--search",
        default="",
        metavar="TEXT",
        help="Search Question text case-insensitively.",
    )
    list_parser.add_argument(
        "--status",
        choices=("all", *(status.value for status in PredictionStatus)),
        default="all",
        help="Filter by derived lifecycle status (default: all).",
    )
    list_parser.add_argument(
        "--type",
        choices=("all", *(prediction_type.value for prediction_type in PredictionType)),
        default="all",
        dest="prediction_type",
        help="Filter by forecast type (default: all).",
    )
    list_parser.add_argument(
        "--tag",
        metavar="TAG",
        help="Filter by one tag using case-insensitive identity.",
    )

    show_parser = commands.add_parser(
        "show",
        help="Show current detail and complete textual history.",
        description="Show one Prediction and its exact historical record.",
    )
    show_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    create_parser = commands.add_parser(
        "create",
        help="Interactively create a Binary or Numeric Prediction.",
        description="Create one Prediction and its first forecast atomically.",
    )
    create_types = create_parser.add_subparsers(
        dest="prediction_type",
        required=True,
        metavar="TYPE",
    )
    create_types.add_parser(
        "binary",
        help="Create a Binary Yes/No Prediction.",
        description=(
            "Prompt for a Question and 0-100% Yes probability, then optionally "
            "collect initial details before one atomic save."
        ),
    )
    create_types.add_parser(
        "numeric",
        help="Create a Numeric interval Prediction.",
        description=(
            "Prompt for a Question, unit, fixed precision, central interval, median, "
            "and confidence, then optionally collect initial details before one "
            "atomic save."
        ),
    )

    revise_parser = commands.add_parser(
        "revise",
        help="Interactively append a changed Binary or Numeric forecast.",
        description=(
            "Show the current type-aware forecast and append one changed immutable "
            "revision while the Prediction is Open."
        ),
    )
    revise_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    journal_parser = commands.add_parser(
        "journal",
        help="Add a one-line Journal entry without changing the forecast.",
        description=(
            "Show the current forecast and append one required one-line Journal "
            "entry while the Prediction is Open or Locked."
        ),
    )
    journal_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    review_parser = commands.add_parser(
        "review",
        help="Record deliberate retention of the current forecast.",
        description=(
            "Show the current forecast and record one Open-only Forecast Review "
            "with an optional one-line note."
        ),
    )
    review_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    resolve_parser = commands.add_parser(
        "resolve",
        help="Resolve a Binary or Numeric Prediction permanently.",
        description=(
            "Show the current forecast, collect a type-appropriate terminal "
            "outcome and optional notes, then require confirmation."
        ),
    )
    resolve_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    invalidate_parser = commands.add_parser(
        "invalidate",
        help="Preserve a Prediction as Invalid and exclude it from scoring.",
        description=(
            "Show the current forecast, collect an optional reason, and require "
            "confirmation before recording the terminal Invalid decision."
        ),
    )
    invalidate_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )

    delete_parser = commands.add_parser(
        "delete",
        help="Permanently delete one untouched Open Prediction.",
        description=(
            "Show the current forecast and require explicit confirmation before "
            "permanently deleting eligible untouched Open history."
        ),
    )
    delete_parser.add_argument(
        "prediction_id",
        type=_positive_prediction_id,
        metavar="PREDICTION_ID",
    )
    return parser


def _positive_prediction_id(value: str) -> int:
    try:
        prediction_id = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "PREDICTION_ID must be a positive whole number."
        ) from error
    if prediction_id < 1:
        raise argparse.ArgumentTypeError(
            "PREDICTION_ID must be a positive whole number."
        )
    return prediction_id


def _run_list(
    operations: PredictionOperations,
    arguments: argparse.Namespace,
    output: TextIO,
) -> int:
    status = None if arguments.status == "all" else PredictionStatus(arguments.status)
    prediction_type = (
        None
        if arguments.prediction_type == "all"
        else PredictionType(arguments.prediction_type)
    )
    snapshot = operations.browse_predictions(
        arguments.search,
        status=status,
        tag=arguments.tag,
        prediction_type=prediction_type,
    )
    if not snapshot.predictions:
        unfiltered = operations.browse_predictions()
        message = (
            "No predictions yet."
            if not unfiltered.predictions
            else "No predictions match the selected filters."
        )
        print(message, file=output)
        return 0

    indicators = AttentionIndicators.from_snapshot(operations.get_dashboard())
    print(
        _format_prediction_list(snapshot.predictions, indicators),
        file=output,
    )
    return 0


def _run_show(
    operations: PredictionOperations,
    prediction_id: int,
    output: TextIO,
) -> int:
    prediction = operations.get_prediction_for_navigation(prediction_id)
    indicators = AttentionIndicators.from_snapshot(operations.get_dashboard())
    definition_changes = operations.list_definition_changes(prediction_id)
    if isinstance(prediction, NumericPrediction):
        timeline = operations.list_numeric_timeline(prediction_id)
        rendered = _format_numeric_detail(
            prediction,
            timeline,
            definition_changes,
            indicators,
        )
    else:
        timeline = operations.list_timeline(prediction_id)
        rendered = _format_binary_detail(
            prediction,
            timeline,
            definition_changes,
            indicators,
        )
    print(rendered, file=output)
    return 0


def _run_create(
    operations: PredictionOperations,
    prediction_type: PredictionType,
    input_stream: TextIO,
    output: TextIO,
    errors: TextIO,
) -> int:
    created = create_interactively(
        operations,
        prediction_type,
        PromptSession(input_stream, output, errors),
    )
    print(file=output)
    if isinstance(created, NumericPrediction):
        summary = _numeric_forecast_summary(
            created.current_revision.lower_bound,
            created.current_revision.median_estimate,
            created.current_revision.upper_bound,
            created.current_revision.confidence_percent,
            created.unit,
        )
        type_label = "Numeric"
    else:
        summary = f"{created.probability_percent}% Yes"
        type_label = "Binary"
    print(f"Created {type_label} Prediction #{created.prediction_id}.", file=output)
    print(f"Current forecast: {summary}", file=output)
    return 0


def _format_prediction_list(
    predictions: tuple[PredictionBrowserItem, ...],
    indicators: AttentionIndicators,
) -> str:
    lines = [f"Predictions ({len(predictions)})"]
    for prediction in predictions:
        lines.append("")
        lines.append(
            f"#{prediction.prediction_id} | "
            f"{prediction.prediction_type.value.upper()} | "
            f"{prediction.status.value.upper()} | "
            f"{_browser_forecast_summary(prediction)}"
        )
        _append_field(lines, "Question", prediction.question, indent="  ")
        if prediction.tags:
            _append_field(lines, "Tags", ", ".join(prediction.tags), indent="  ")
        labels = indicators.labels_for(prediction.prediction_id)
        if labels:
            _append_field(lines, "Attention", ", ".join(labels), indent="  ")
    return "\n".join(lines)


def _browser_forecast_summary(prediction: PredictionBrowserItem) -> str:
    if prediction.prediction_type is PredictionType.BINARY:
        return f"{prediction.probability_percent}% Yes"
    return _numeric_forecast_summary(
        prediction.numeric_lower_bound,
        prediction.numeric_median_estimate,
        prediction.numeric_upper_bound,
        prediction.numeric_confidence_percent,
        prediction.numeric_unit,
    )


def _format_binary_detail(
    prediction: PredictionDetail,
    timeline: tuple[TimelineEvent, ...],
    definition_changes: tuple[DefinitionChange, ...],
    indicators: AttentionIndicators,
) -> str:
    lines = [f"Prediction #{prediction.prediction_id}", "Type: Binary"]
    _append_common_detail(lines, prediction, indicators)
    _append_field(lines, "Current forecast", f"{prediction.probability_percent}% Yes")
    if prediction.current_rationale is not None:
        _append_field(lines, "Current rationale", prediction.current_rationale)
    _append_binary_terminal(lines, prediction)
    _append_definition_history(lines, definition_changes)
    lines.extend(("", "Timeline"))
    for event in timeline:
        lines.append("")
        _append_binary_timeline_event(lines, event)
    return "\n".join(lines)


def _format_numeric_detail(
    prediction: NumericPrediction,
    timeline: tuple[
        NumericForecastTimelineEvent
        | NumericJournalTimelineEvent
        | NumericForecastReviewTimelineEvent,
        ...,
    ],
    definition_changes: tuple[DefinitionChange, ...],
    indicators: AttentionIndicators,
) -> str:
    lines = [f"Prediction #{prediction.prediction_id}", "Type: Numeric"]
    _append_common_detail(lines, prediction, indicators)
    _append_field(
        lines,
        "Current forecast",
        _numeric_forecast_summary(
            prediction.current_revision.lower_bound,
            prediction.current_revision.median_estimate,
            prediction.current_revision.upper_bound,
            prediction.current_revision.confidence_percent,
            prediction.unit,
        ),
    )
    _append_field(lines, "Unit", prediction.unit)
    _append_field(lines, "Decimal precision", str(prediction.decimal_places))
    if prediction.current_revision.rationale is not None:
        _append_field(lines, "Current rationale", prediction.current_revision.rationale)
    _append_numeric_terminal(lines, prediction, timeline)
    _append_definition_history(lines, definition_changes)
    lines.extend(("", "Timeline"))
    for event in timeline:
        lines.append("")
        _append_numeric_timeline_event(lines, event, prediction.unit)
    return "\n".join(lines)


def _append_common_detail(
    lines: list[str],
    prediction: PredictionDetail | NumericPrediction,
    indicators: AttentionIndicators,
) -> None:
    _append_field(lines, "Status", prediction.status.value.capitalize())
    _append_field(lines, "Question", prediction.question)
    _append_field(lines, "Created", _format_local_timestamp(prediction.created_at))
    _append_field(lines, "Updated", _format_local_timestamp(prediction.updated_at))
    labels = indicators.labels_for(prediction.prediction_id)
    if labels:
        _append_field(lines, "Attention", ", ".join(labels))
    if prediction.tags:
        _append_field(lines, "Tags", ", ".join(prediction.tags))
    if prediction.forecast_deadline is not None:
        _append_field(
            lines,
            "Forecast deadline",
            _format_date(prediction.forecast_deadline),
        )
    if prediction.expected_resolution is not None:
        _append_field(
            lines,
            "Expected resolution",
            _format_date(prediction.expected_resolution),
        )
    if prediction.background is not None:
        _append_field(lines, "Background", prediction.background)
    if prediction.resolution_criteria is not None:
        _append_field(lines, "Resolution criteria", prediction.resolution_criteria)


def _append_binary_terminal(
    lines: list[str],
    prediction: PredictionDetail,
) -> None:
    if prediction.resolution is not None:
        resolution = prediction.resolution
        lines.extend(("", "Resolution"))
        _append_field(lines, "Outcome", resolution.outcome.value.capitalize())
        _append_field(
            lines, "Resolved", _format_local_timestamp(resolution.resolved_at)
        )
        _append_field(
            lines,
            "Scoring forecast",
            f"{resolution.scoring_probability_percent}% Yes "
            f"(revision {resolution.scoring_revision_sequence}, "
            f"ID {resolution.scoring_revision_id})",
        )
        if resolution.resolution_notes is not None:
            _append_field(lines, "Resolution notes", resolution.resolution_notes)
        if resolution.postmortem is not None:
            _append_field(lines, "Postmortem", resolution.postmortem)
    elif prediction.invalidation is not None:
        invalidation = prediction.invalidation
        lines.extend(("", "Invalidation"))
        _append_field(
            lines,
            "Marked Invalid",
            _format_local_timestamp(invalidation.invalidated_at),
        )
        if invalidation.reason is not None:
            _append_field(lines, "Reason", invalidation.reason)


def _append_numeric_terminal(
    lines: list[str],
    prediction: NumericPrediction,
    timeline: tuple[
        NumericForecastTimelineEvent
        | NumericJournalTimelineEvent
        | NumericForecastReviewTimelineEvent,
        ...,
    ],
) -> None:
    if prediction.resolution is not None:
        resolution = prediction.resolution
        lines.extend(("", "Resolution"))
        _append_field(
            lines,
            "Actual value",
            f"{resolution.actual_value} {terminal_text(prediction.unit)}",
        )
        _append_field(
            lines, "Resolved", _format_local_timestamp(resolution.resolved_at)
        )
        scoring_revision = next(
            (
                event
                for event in timeline
                if isinstance(event, NumericForecastTimelineEvent)
                and event.revision_id == resolution.scoring_revision_id
            ),
            None,
        )
        if scoring_revision is not None:
            scoring_text = _numeric_forecast_summary(
                scoring_revision.lower_bound,
                scoring_revision.median_estimate,
                scoring_revision.upper_bound,
                scoring_revision.confidence_percent,
                prediction.unit,
            )
            _append_field(
                lines,
                "Scoring forecast",
                f"{scoring_text} (revision {resolution.scoring_revision_sequence}, "
                f"ID {resolution.scoring_revision_id})",
            )
        else:
            _append_field(
                lines,
                "Scoring revision",
                f"Revision {resolution.scoring_revision_sequence}, "
                f"ID {resolution.scoring_revision_id}",
            )
        if resolution.resolution_notes is not None:
            _append_field(lines, "Resolution notes", resolution.resolution_notes)
        if resolution.postmortem is not None:
            _append_field(lines, "Postmortem", resolution.postmortem)
    elif prediction.invalidation is not None:
        invalidation = prediction.invalidation
        lines.extend(("", "Invalidation"))
        _append_field(
            lines,
            "Marked Invalid",
            _format_local_timestamp(invalidation.invalidated_at),
        )
        if invalidation.reason is not None:
            _append_field(lines, "Reason", invalidation.reason)


def _append_definition_history(
    lines: list[str],
    changes: tuple[DefinitionChange, ...],
) -> None:
    if not changes:
        return
    lines.extend(("", "Definition history"))
    for change in changes:
        lines.append("")
        lines.append(
            f"Change {change.change_id} | {_format_local_timestamp(change.changed_at)}"
        )
        if "question" in change.changed_fields:
            _append_change(lines, "Question", change.old_question, change.new_question)
        if "resolution_criteria" in change.changed_fields:
            _append_change(
                lines,
                "Resolution criteria",
                change.old_resolution_criteria,
                change.new_resolution_criteria,
            )
        if "forecast_deadline" in change.changed_fields:
            _append_change(
                lines,
                "Forecast deadline",
                change.old_forecast_deadline,
                change.new_forecast_deadline,
            )


def _append_change(
    lines: list[str],
    label: str,
    old_value: str | date | None,
    new_value: str | date | None,
) -> None:
    _append_field(
        lines, f"{label} before", _display_optional_value(old_value), indent="  "
    )
    _append_field(
        lines, f"{label} after", _display_optional_value(new_value), indent="  "
    )


def _append_binary_timeline_event(lines: list[str], event: TimelineEvent) -> None:
    if isinstance(event, ForecastTimelineEvent):
        transition = (
            f"{event.probability_percent}% Yes"
            if event.previous_probability_percent is None
            else f"{event.previous_probability_percent}% -> "
            f"{event.probability_percent}% Yes"
        )
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | FORECAST | "
            f"Revision {event.sequence} (ID {event.revision_id}) | {transition}"
        )
        if event.rationale is not None:
            _append_field(lines, "Rationale", event.rationale, indent="  ")
        return
    if isinstance(event, JournalTimelineEvent):
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | JOURNAL | "
            f"Entry {event.entry_id}"
        )
        _append_field(lines, "Body", event.body, indent="  ")
        _append_field(
            lines,
            "Forecast at the time",
            f"{event.forecast_probability_percent}% Yes "
            f"(revision {event.forecast_revision_sequence}, "
            f"ID {event.forecast_revision_id})",
            indent="  ",
        )
        _append_correction_history(
            lines, event.created_at, event.original_body, event.corrections
        )
        return
    if isinstance(event, ForecastReviewTimelineEvent):
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | REVIEW | "
            f"Review {event.review_id}"
        )
        _append_field(
            lines,
            "Retained forecast",
            f"{event.forecast_probability_percent}% Yes "
            f"(revision {event.forecast_revision_sequence}, "
            f"ID {event.forecast_revision_id})",
            indent="  ",
        )
        if event.note is not None:
            _append_field(lines, "Note", event.note, indent="  ")


def _append_numeric_timeline_event(
    lines: list[str],
    event: (
        NumericForecastTimelineEvent
        | NumericJournalTimelineEvent
        | NumericForecastReviewTimelineEvent
    ),
    unit: str,
) -> None:
    if isinstance(event, NumericForecastTimelineEvent):
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | FORECAST | "
            f"Revision {event.sequence} (ID {event.revision_id})"
        )
        if event.previous_lower_bound is not None:
            previous = _numeric_forecast_summary(
                event.previous_lower_bound,
                event.previous_median_estimate,
                event.previous_upper_bound,
                event.previous_confidence_percent,
                unit,
            )
            _append_field(lines, "Before", previous, indent="  ")
        _append_field(
            lines,
            "Forecast",
            _numeric_forecast_summary(
                event.lower_bound,
                event.median_estimate,
                event.upper_bound,
                event.confidence_percent,
                unit,
            ),
            indent="  ",
        )
        if event.rationale is not None:
            _append_field(lines, "Rationale", event.rationale, indent="  ")
        return
    if isinstance(event, NumericJournalTimelineEvent):
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | JOURNAL | "
            f"Entry {event.entry_id}"
        )
        _append_field(lines, "Body", event.body, indent="  ")
        _append_field(
            lines,
            "Forecast at the time",
            _numeric_forecast_summary(
                event.lower_bound,
                event.median_estimate,
                event.upper_bound,
                event.confidence_percent,
                unit,
            )
            + f" (revision {event.forecast_revision_sequence}, "
            f"ID {event.numeric_forecast_revision_id})",
            indent="  ",
        )
        _append_correction_history(
            lines, event.created_at, event.original_body, event.corrections
        )
        return
    if isinstance(event, NumericForecastReviewTimelineEvent):
        lines.append(
            f"{_format_local_timestamp(event.created_at)} | REVIEW | "
            f"Review {event.review_id}"
        )
        _append_field(
            lines,
            "Retained forecast",
            _numeric_forecast_summary(
                event.lower_bound,
                event.median_estimate,
                event.upper_bound,
                event.confidence_percent,
                unit,
            )
            + f" (revision {event.forecast_revision_sequence}, "
            f"ID {event.numeric_forecast_revision_id})",
            indent="  ",
        )
        if event.note is not None:
            _append_field(lines, "Note", event.note, indent="  ")


def _append_correction_history(
    lines: list[str],
    created_at: datetime,
    original_body: str,
    corrections: tuple[JournalCorrection, ...],
) -> None:
    if not corrections:
        return
    _append_field(
        lines,
        "Edited",
        _format_local_timestamp(corrections[-1].corrected_at),
        indent="  ",
    )
    _append_field(
        lines,
        "Original body",
        f"[{_format_local_timestamp(created_at)}] {original_body}",
        indent="  ",
    )
    for index, correction in enumerate(corrections, start=1):
        _append_field(
            lines,
            f"Correction {index}",
            f"[{_format_local_timestamp(correction.corrected_at)}] {correction.body}",
            indent="  ",
        )


def _numeric_forecast_summary(
    lower_bound: FixedPrecisionValue | None,
    median_estimate: FixedPrecisionValue | None,
    upper_bound: FixedPrecisionValue | None,
    confidence_percent: int | None,
    unit: str | None,
) -> str:
    if (
        lower_bound is None
        or median_estimate is None
        or upper_bound is None
        or confidence_percent is None
        or unit is None
    ):
        raise ValueError("Numeric forecast data is incomplete.")
    safe_unit = terminal_text(unit)
    return (
        f"{confidence_percent}% interval {lower_bound} to {upper_bound} {safe_unit}; "
        f"median {median_estimate} {safe_unit}"
    )


def _append_field(
    lines: list[str],
    label: str,
    value: str,
    *,
    indent: str = "",
) -> None:
    safe_value = terminal_text(value)
    parts = safe_value.split("\n")
    lines.append(f"{indent}{label}: {parts[0]}")
    lines.extend(f"{indent}  {part}" for part in parts[1:])


def _display_optional_value(value: str | date | None) -> str:
    if value is None:
        return "Not set"
    if isinstance(value, date):
        return _format_date(value)
    return value


def _format_local_timestamp(value: datetime | None) -> str:
    if value is None:
        return "Not recorded"
    return value.astimezone().isoformat(sep=" ", timespec="microseconds")


def _format_date(value: date) -> str:
    return value.isoformat()
