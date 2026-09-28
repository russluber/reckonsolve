"""Individual One-Shot use cases; no interface owns persistence or scoring."""

import sqlite3
from collections.abc import Callable
from fractions import Fraction

from reckonsolve.analytics.one_shot import one_shot_score
from reckonsolve.analytics.quantiles import WISScore
from reckonsolve.data.one_shot import OneShotRepository
from reckonsolve.data.predictions import ForecastContextChangedError
from reckonsolve.data.search_index import SearchIndexError
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotDetail,
    OneShotValues,
)

from .errors import ApplicationError, PredictionNotFoundError, ValidationError


class OneShotOperations:
    def __init__(self, repository: OneShotRepository) -> None:
        self.repository = repository

    def get(self, prediction_id: int) -> OneShotDetail:
        detail = self._perform(lambda: self.repository.find_detail(prediction_id))
        if detail is None:
            raise PredictionNotFoundError(prediction_id)
        return detail

    def create(self, request: NewOneShotPrediction) -> OneShotDetail:
        return self._perform(lambda: self.repository.create_detail(request))

    def add_answer(
        self, expected: OneShotDetail, values: OneShotValues
    ) -> OneShotDetail:
        return self._save(expected, values, correction=False)

    def correct(
        self, expected: OneShotDetail, values: OneShotValues, *, note: str | None = None
    ) -> OneShotDetail:
        return self._save(expected, values, correction=True, note=note)

    def _save(
        self,
        expected: OneShotDetail,
        values: OneShotValues,
        *,
        correction: bool,
        note: str | None = None,
    ) -> OneShotDetail:
        if correction:
            return self._perform(
                lambda: self.repository.correct_detail(
                    expected.record, values, note=note
                )
            )
        return self._perform(
            lambda: self.repository.add_answer_detail(expected.record, values)
        )

    def invalidate(
        self, expected: OneShotDetail, *, reason: str | None = None
    ) -> OneShotDetail:
        saved = self._terminal(expected, delete=False, reason=reason)
        assert saved is not None
        return saved

    def add_journal(self, expected: OneShotDetail, body: str) -> OneShotDetail:
        return self._perform(lambda: self.repository.add_journal(expected.record, body))

    def delete(self, expected: OneShotDetail, *, confirmed: bool = False) -> None:
        if not confirmed:
            raise ApplicationError(
                "Confirm permanent deletion before deleting this One-Shot."
            )
        self._terminal(expected, delete=True)

    def _terminal(
        self, expected: OneShotDetail, *, delete: bool, reason: str | None = None
    ) -> OneShotDetail | None:
        return self._perform(
            lambda: self.repository.invalidate_or_delete(
                expected.record, delete=delete, reason=reason
            )
        )

    @staticmethod
    def _perform[T](operation: Callable[[], T]) -> T:
        try:
            return operation()
        except ForecastContextChangedError as error:
            raise ApplicationError(str(error)) from error
        except ValueError as error:
            raise ValidationError(str(error), field="one_shot") from error
        except SearchIndexError as error:
            raise ApplicationError(f"One-Shot operation failed: {error}") from error
        except sqlite3.Error as error:
            raise ApplicationError(
                f"Could not complete the One-Shot operation: {error}"
            ) from error

    @staticmethod
    def score(detail: OneShotDetail) -> Fraction | WISScore | None:
        record = detail.record
        return one_shot_score(
            record.contract, record.status, record.effective, record.definition
        )
