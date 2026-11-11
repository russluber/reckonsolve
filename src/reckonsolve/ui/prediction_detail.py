"""Prediction detail responsibilities extracted from the desktop composition."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.one_shot import OneShotDetail
from reckonsolve.domain.predictions import (
    PredictionType,
)
from reckonsolve.domain.search import SearchDocument
from reckonsolve.ui.binary_detail import PredictionDetailScreen
from reckonsolve.ui.numeric_detail import NumericPredictionDetailScreen
from reckonsolve.ui.one_shot_detail import OneShotDetailScreen
from reckonsolve.ui.prediction_contracts import (
    NumericPredictionSnapshot,
    PredictionOperations,
    PredictionSnapshot,
)


class PredictionDetailHost(QWidget):
    """Keep one primary Detail navigation slot while selecting forecast type."""

    def __init__(
        self,
        operations: PredictionOperations,
        binary_detail: PredictionDetailScreen,
        numeric_detail: NumericPredictionDetailScreen,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionDetailHost")
        self._operations = operations
        self._binary_detail = binary_detail
        self._numeric_detail = numeric_detail
        self._one_shot_detail = OneShotDetailScreen(operations)
        self._current_type: PredictionType | None = None

        self._stack = QStackedWidget(self)
        self._stack.addWidget(binary_detail)
        self._stack.addWidget(numeric_detail)
        self._stack.addWidget(self._one_shot_detail)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def confirm_exit(self, destination: str = "return") -> bool:
        screen = self._stack.currentWidget()
        workspace = getattr(screen, "workspace", None)
        return workspace is None or workspace.confirm_exit(destination)

    def show_prediction(self, prediction: PredictionSnapshot | None) -> None:
        """Select and present the existing Binary detail screen."""

        if isinstance(prediction, OneShotDetail):
            self._one_shot_detail.show_prediction(prediction)
            self._stack.setCurrentWidget(self._one_shot_detail)
            return
        self._current_type = PredictionType.BINARY
        self._binary_detail.show_prediction(prediction)
        self._stack.setCurrentWidget(self._binary_detail)

    def show_numeric_prediction(
        self,
        prediction: NumericPredictionSnapshot | None,
    ) -> None:
        """Select and present the staged Numeric detail screen."""

        self._current_type = PredictionType.NUMERIC
        self._numeric_detail.show_prediction(prediction)
        self._stack.setCurrentWidget(self._numeric_detail)

    def show_latest_prediction(self) -> None:
        """Present the latest persisted forecast type after app restart."""

        latest = getattr(self._operations, "get_latest_for_navigation", None)
        if latest is not None:
            prediction = latest()
            if isinstance(prediction, OneShotDetail):
                self.show_prediction(prediction)
                return
        binary = self._operations.get_latest_prediction()
        get_latest_numeric = getattr(
            self._operations,
            "get_latest_numeric_prediction",
            lambda: None,
        )
        numeric = get_latest_numeric()
        if numeric is not None and (
            binary is None
            or (numeric.created_at, numeric.prediction_id)
            > (binary.created_at, binary.prediction_id)
        ):
            self.show_numeric_prediction(numeric)
            return
        self._current_type = PredictionType.BINARY
        self._stack.setCurrentWidget(self._binary_detail)
        if binary is None:
            self._binary_detail.show_prediction(None)
        else:
            self._binary_detail.refresh()

    def refresh(self) -> None:
        """Refresh the selected detail type, or select the latest at first visit."""

        if self._stack.currentWidget() is self._one_shot_detail:
            self._one_shot_detail.refresh()
            return
        if self._current_type is PredictionType.BINARY:
            self._binary_detail.refresh()
        elif self._current_type is PredictionType.NUMERIC:
            self._numeric_detail.refresh()
        else:
            self.show_latest_prediction()

    def focus_search_match(
        self, document: SearchDocument, *, emphasize: bool = True
    ) -> None:
        """Delegate matched-source navigation to the currently selected Detail."""

        if self._stack.currentWidget() is self._one_shot_detail:
            self._one_shot_detail.focus_search_match(document)
        elif self._current_type is PredictionType.NUMERIC:
            self._numeric_detail.focus_search_match(document)
        elif self._current_type is PredictionType.BINARY:
            self._binary_detail.focus_search_match(document)
        if not emphasize:
            for widget in self.findChildren(QWidget):
                if widget.property("searchMatchEmphasis"):
                    widget.setProperty("searchMatchEmphasis", False)
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
