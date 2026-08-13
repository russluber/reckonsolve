"""Expected errors that presentation code may show without a traceback."""


class ApplicationError(Exception):
    """Base class for expected, user-presentable application failures."""


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
