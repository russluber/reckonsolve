"""Shared text for already saved One-Shot facts and calculated scores."""

from fractions import Fraction

from reckonsolve.analytics.quantiles import WISScore
from reckonsolve.domain.one_shot import OneShotDetail, OneShotValues, ReportedTime
from reckonsolve.domain.predictions import BinaryOutcome, PredictionStatus
from reckonsolve.domain.quantiles import quantile_summary
from reckonsolve.quantile_display import exact_score_text


def reported_time_text(value: ReportedTime | None) -> str:
    if value is None:
        return "Not reported"
    text = value.wall_time.isoformat(sep=" ", timespec="minutes")
    if value.offset_minutes is not None:
        offset = value.offset_minutes
        text += f" UTC{'+' if offset >= 0 else '-'}{abs(offset) // 60:02}:{abs(offset) % 60:02}"
    return text + (" (approximate)" if value.approximate else "")


def status_text(detail: OneShotDetail) -> str:
    return (
        "Waiting for answer"
        if detail.status is PredictionStatus.OPEN
        else detail.status.value.capitalize()
    )


def forecast_text(values: OneShotValues, unit: str = "") -> str:
    if values.quantiles is not None:
        return quantile_summary(values.quantiles, unit)
    return f"{values.probability_percent}% Yes"


def values_lines(values: OneShotValues, unit: str = "") -> tuple[str, ...]:
    lines = [
        f"Forecast: {forecast_text(values, unit)}",
        f"Forecast finalized (user-reported): {reported_time_text(values.forecast_reported)}",
    ]
    if values.answer is not None:
        answer = (
            values.answer.value.capitalize()
            if isinstance(values.answer, BinaryOutcome)
            else f"{values.answer} {unit}"
        )
        lines += [
            f"Answer: {answer}",
            f"Answer checked (user-reported): {reported_time_text(values.reveal_reported)}",
        ]
        if values.resolution_notes:
            lines.append(f"Resolution notes: {values.resolution_notes}")
        if values.postmortem:
            lines.append(f"Postmortem: {values.postmortem}")
    return tuple(lines)


def score_lines(score: Fraction | WISScore | None, unit: str = "") -> tuple[str, ...]:
    if score is None:
        return ()
    if isinstance(score, Fraction):
        return (f"Brier: {exact_score_text(score)} — lower is better",)
    lines = [
        f"WIS: {exact_score_text(score.wis)} {unit} — lower is better",
        f"Median absolute error: {exact_score_text(score.median_absolute_error)} {unit}",
        f"Signed median miss (actual minus median): {exact_score_text(score.signed_median_miss)} {unit}",
        f"Median contribution: {exact_score_text(score.median_contribution)} {unit}",
    ]
    for level, interval, contribution in (
        (50, score.interval_50, score.interval_50_contribution),
        (90, score.interval_90, score.interval_90_contribution),
    ):
        lines.append(
            f"{level}% interval: actual {interval.outcome_location}; width {exact_score_text(interval.width)} {unit}; "
            f"miss distance {exact_score_text(interval.miss_distance)} {unit}; interval score {exact_score_text(interval.score)} {unit}; "
            f"contribution {exact_score_text(contribution)} {unit}"
        )
    return tuple(lines)


def detail_lines(
    detail: OneShotDetail, score: Fraction | WISScore | None
) -> tuple[str, ...]:
    record = detail.record
    unit = record.definition.unit if record.definition else ""
    lines = [
        f"Prediction #{detail.prediction_id}: {detail.question}",
        f"One-Shot · {record.contract.prediction_type.value.capitalize()} · {status_text(detail)}",
        f"Model: {record.contract.forecast_model.value}",
        f"Scoring contract: {record.contract.scoring_contract.value}",
        f"Entered in Reckonsolve: {record.recorded_at.astimezone().isoformat()}",
    ]
    if record.answer_recorded_at:
        lines.append(
            f"Answer entered in Reckonsolve: {record.answer_recorded_at.astimezone().isoformat()}"
        )
    if record.definition:
        lines.append(
            f"Unit: {unit}; decimal places: {record.definition.decimal_places}; value constraint: {record.definition.value_constraint.value}"
        )
    lines.extend(values_lines(record.effective, unit))
    lines.extend(score_lines(score, unit))
    for label, value in (
        ("Tags", ", ".join(detail.tags)),
        ("Rationale", detail.rationale),
        ("Background", detail.background),
        ("Resolution Criteria", detail.resolution_criteria),
        ("Expected resolution", detail.expected_resolution),
    ):
        if value:
            lines.append(f"{label}: {value}")
    lines.extend(("", "Original saved facts", *values_lines(record.original, unit)))
    for correction in record.corrections:
        lines += [
            "",
            f"Transcription correction {correction.sequence} · {correction.corrected_at.astimezone().isoformat()}",
            "Before",
            *values_lines(correction.before, unit),
            "After",
            *values_lines(correction.after, unit),
        ]
        if correction.note:
            lines.append(f"Correction note: {correction.note}")
    for change in detail.definition_changes:
        lines.append(
            f"Definition change · {change.changed_at.astimezone().isoformat()}"
        )
        for field, label in (
            ("question", "Question"),
            ("resolution_criteria", "Resolution Criteria"),
        ):
            if field in change.changed_fields:
                lines.extend(
                    (
                        f"{label} before: {getattr(change, 'old_' + field) or 'Not supplied'}",
                        f"{label} after: {getattr(change, 'new_' + field) or 'Not supplied'}",
                    )
                )
    for journal in detail.journals:
        lines += [
            "",
            f"Journal · {journal.created_at.astimezone().isoformat()}",
            journal.body,
        ]
        if journal.corrections:
            lines.append(f"Original Journal: {journal.original_body}")
            lines.extend(
                f"Journal correction · {c.corrected_at.astimezone().isoformat()}: {c.body}"
                for c in journal.corrections
            )
    if detail.invalidation_history:
        history = detail.invalidation_history
        lines.append(
            f"Invalidated: {history.original.invalidated_at.astimezone().isoformat()}"
        )
        lines.append(f"Reason: {history.effective.reason or 'Not supplied'}")
        if history.corrections:
            lines.append(
                f"Original reason: {history.original.reason or 'Not supplied'}"
            )
            lines.extend(f"Reason correction: {c}" for c in history.corrections)
    return tuple(lines)
