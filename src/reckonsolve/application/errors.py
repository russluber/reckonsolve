"""Expected errors that presentation code may show without a traceback."""

from reckonsolve.domain.predictions import PredictionStatus


class ApplicationError(Exception):
    """Base class for expected, user-presentable application failures."""


class BackupError(ApplicationError):
    """A complete recovery artifact could not be created safely."""


class CsvExportError(ApplicationError):
    """A portable CSV bundle could not be created safely."""


class SearchUnavailableError(ApplicationError):
    """A local search cannot complete safely until its stated cause is resolved."""


class SavedViewNotFoundError(ApplicationError):
    """The requested mutable Saved View no longer exists."""

    def __init__(self, saved_view_id: int) -> None:
        super().__init__(f"Saved View {saved_view_id} was not found.")
        self.saved_view_id = saved_view_id


class DuplicateSavedViewNameError(ApplicationError):
    """A Saved View name is already in use after normalization."""

    def __init__(self, name: str) -> None:
        super().__init__(f"A Saved View named {name!r} already exists.")
        self.name = name


class ValidationError(ApplicationError):
    """A user-supplied value failed authoritative validation."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class PredictionNotFoundError(ApplicationError):
    """The requested prediction does not exist."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(f"Prediction {prediction_id} was not found.")
        self.prediction_id = prediction_id


class MeaningChangeConfirmationRequired(ApplicationError):
    """A metadata save must be explicitly confirmed before it may proceed."""

    def __init__(self, changed_fields: tuple[str, ...]) -> None:
        field_labels = {
            "question": "Question",
            "resolution_criteria": "Resolution Criteria",
            "forecast_deadline": "Forecast Deadline",
        }
        definition_fields = tuple(
            field
            for field in changed_fields
            if field in ("question", "resolution_criteria")
        )
        messages: list[str] = []
        if definition_fields:
            labels = ", ".join(field_labels[field] for field in definition_fields)
            messages.append(
                f"Changing {labels} may change what this prediction means. "
                "If the proposition has changed materially, create a new prediction "
                "instead."
            )
        if "forecast_deadline" in changed_fields:
            messages.append(
                "Changing Forecast Deadline changes when forecast revisions become "
                "locked."
            )
        messages.append("Confirm this save to record it in Definition history.")
        super().__init__(" ".join(messages))
        self.changed_fields = changed_fields


class ConcurrentPredictionUpdateError(ApplicationError):
    """Prediction metadata changed between review and the confirmed save."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This prediction changed before the edit could be saved. "
            "Close this editor, reopen Edit Details to review the latest values, "
            "and try again."
        )
        self.prediction_id = prediction_id


class ConcurrentForecastUpdateError(ApplicationError):
    """The prediction changed after a revision form was opened."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This prediction changed before the forecast could be revised. "
            "Close this editor, reopen Revise Forecast to review the latest "
            "forecast and details, and try again."
        )
        self.prediction_id = prediction_id


class ForecastUnchangedError(ApplicationError):
    """A normal forecast revision must change the current probability."""

    def __init__(self, probability_percent: int) -> None:
        super().__init__(
            f"The current forecast is already {probability_percent}%. "
            "Change the probability to save a revision. To record reasoning without "
            "changing the forecast, add a Journal entry."
        )
        self.probability_percent = probability_percent


class NumericForecastUnchangedError(ApplicationError):
    """A normal Numeric revision must change at least one forecast value."""

    def __init__(self) -> None:
        super().__init__(
            "The current interval, median estimate, and confidence are unchanged. "
            "Change at least one value to save a revision. To record reasoning "
            "without changing the forecast, add a Journal entry."
        )


class ForecastRevisionNotAllowedError(ApplicationError):
    """Lifecycle state does not permit another normal forecast revision."""

    def __init__(self, status: PredictionStatus) -> None:
        status_label = status.value.capitalize()
        if status_label == "Locked":
            reason = "Its Forecast Deadline has passed."
        else:
            reason = f"Its status is {status_label}."
        super().__init__(f"This forecast cannot be revised. {reason}")
        self.status = status


class ConcurrentForecastReviewError(ApplicationError):
    """The forecast or definition changed after the Review action opened."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This prediction changed before the Forecast Review could be saved. "
            "Close this dialog, review the latest forecast and details, and try "
            "again."
        )
        self.prediction_id = prediction_id


class ForecastReviewNotAllowedError(ApplicationError):
    """Lifecycle state does not permit a Forecast Review."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(
            "A Forecast Review can be recorded only while a prediction is Open. "
            f"This prediction is {status.value.capitalize()}."
        )
        self.status = status


class ConcurrentJournalUpdateError(ApplicationError):
    """The prediction changed after a new Journal form was opened."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This prediction changed before the Journal entry could be saved. "
            "Close this editor, reopen Add Journal Entry to review the latest "
            "forecast and details, and try again."
        )
        self.prediction_id = prediction_id


class JournalEntryNotAllowedError(ApplicationError):
    """Lifecycle state does not permit a new Journal assertion."""

    def __init__(self, status: PredictionStatus) -> None:
        super().__init__(
            "A new Journal entry cannot be added after a prediction is "
            f"{status.value.capitalize()}."
        )
        self.status = status


class JournalEntryNotFoundError(ApplicationError):
    """The requested Journal entry does not exist under the prediction."""

    def __init__(self, entry_id: int) -> None:
        super().__init__(f"Journal entry {entry_id} was not found.")
        self.entry_id = entry_id


class ConcurrentJournalCorrectionError(ApplicationError):
    """A Journal entry received another correction after review."""

    def __init__(self, entry_id: int) -> None:
        super().__init__(
            "This Journal entry changed before the correction could be saved. "
            "Close this editor, reopen Correct Entry to review the latest text, "
            "and try again."
        )
        self.entry_id = entry_id


class ConcurrentLifecycleUpdateError(ApplicationError):
    """A terminal action no longer matches the prediction the user reviewed."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This prediction changed before the lifecycle action could be saved. "
            "Close this dialog, review the latest prediction, and try again."
        )
        self.prediction_id = prediction_id


class ConcurrentTerminalCorrectionError(ApplicationError):
    """Terminal history changed after the correction was reviewed."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(
            "This terminal record changed before the correction could be saved. "
            "Review the latest Resolution or Invalidation history and try again."
        )
        self.prediction_id = prediction_id


class TerminalCorrectionNotAllowedError(ApplicationError):
    """The requested Prediction has no matching correctable terminal record."""

    def __init__(self, prediction_id: int, record_name: str) -> None:
        super().__init__(
            f"Prediction {prediction_id} has no {record_name} that can be corrected."
        )
        self.prediction_id = prediction_id
        self.record_name = record_name


class TerminalCorrectionUnchangedError(ApplicationError):
    """A terminal correction must change at least one effective value."""

    def __init__(self) -> None:
        super().__init__(
            "The outcome and terminal text are unchanged. "
            "Change at least one value to record a correction."
        )


class PostmortemCompletionNotAllowedError(ApplicationError):
    """The current Prediction cannot record a Skip Postmortem completion."""

    def __init__(self, reason: str) -> None:
        messages = {
            "not_resolved": "Only a Resolved prediction can skip its Postmortem.",
            "already_completed": "This Postmortem has already been marked complete.",
            "has_postmortem": "This Resolution already has a Postmortem.",
        }
        super().__init__(messages.get(reason, "This Postmortem cannot be skipped."))
        self.reason = reason


class LifecycleTransitionNotAllowedError(ApplicationError):
    """An already-terminal prediction cannot receive another terminal decision."""

    def __init__(self, action: str, status: PredictionStatus) -> None:
        super().__init__(
            f"This prediction cannot be {action}. Its status is already "
            f"{status.value.capitalize()}."
        )
        self.action = action
        self.status = status


class PredictionDeletionConfirmationRequired(ApplicationError):
    """Permanent deletion was requested without explicit confirmation."""

    def __init__(self) -> None:
        super().__init__("Permanent deletion must be explicitly confirmed.")


class PredictionDeletionNotAllowedError(ApplicationError):
    """The prediction has lifecycle state or history that must be preserved."""

    def __init__(self, reason: str) -> None:
        if reason == PredictionStatus.LOCKED.value:
            message = (
                "A Locked prediction cannot be deleted. Mark it Invalid to preserve "
                "the forecast while excluding it from scoring."
            )
        elif reason in (
            PredictionStatus.RESOLVED.value,
            PredictionStatus.INVALID.value,
        ):
            message = (
                "Terminal prediction history cannot be deleted from the normal "
                "interface."
            )
        else:
            message = (
                "Only an untouched Open prediction can be deleted. Mark this "
                "prediction Invalid to preserve its meaningful history while "
                "excluding it from scoring."
            )
        super().__init__(message)
        self.reason = reason
