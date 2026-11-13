"""One comprehensive report with retained session scope and current-only reads."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.performance import (
    PerformanceReport,
    PerformanceRequest,
    Section,
)
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.ui.analytics_components import _ResponsiveMetricRow
from reckonsolve.ui.components import PageHeader, PersistentMessageLabel
from reckonsolve.ui.performance_sections import BinarySection, NumericSection
from reckonsolve.ui.performance_state import PerformanceState
from reckonsolve.ui.read_requests import ReadRequests
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_surface_role,
    apply_text_role,
)


class PerformanceScreen(QWidget):
    archive_refused = Signal(object)

    def __init__(
        self,
        operations,
        parent: QWidget | None = None,
        *,
        query: Callable[[PerformanceRequest], PerformanceReport] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsScreen")
        self.state = PerformanceState()
        self.report: PerformanceReport | None = None
        self.loading = False
        self.refused = False
        self._refreshing_section: Section | None = None
        self._position_pending = False
        self._operations = operations
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("performanceScrollArea")
        self.scroll_area.setAccessibleName("Comprehensive Performance report")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget(self.scroll_area)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(int(Spacing.SECTION))
        self.header = PageHeader(
            "Performance",
            "Your forecasting record. Adaptive and One-Shot results stay separate.",
            title_object_name="analyticsScreenTitle",
            parent=self.content,
        )
        layout.addWidget(self.header)
        # The strip is one viewport child, positioned over its reserved slot.
        # Pinning it never reparents focused controls or duplicates filters.
        self.controls_slot = QWidget(self.content)
        layout.addWidget(self.controls_slot)
        self.controls = QWidget(self.scroll_area.viewport())
        self.controls.setObjectName("performanceScopeStrip")
        self.controls.setAutoFillBackground(True)
        apply_surface_role(self.controls, SurfaceRole.CANVAS)
        controls_layout = QHBoxLayout(self.controls)
        controls_layout.setContentsMargins(12, 6, 12, 6)
        label = QLabel("Tag", self.controls)
        self.tag_filter = QComboBox(self.controls)
        self.tag_filter.setObjectName("analyticsTagFilter")
        self.tag_filter.setAccessibleName("Tag for all Performance sections")
        self.tag_filter.setMinimumContentsLength(12)
        self.tag_filter.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.tag_filter.addItem("All tags", None)
        label.setBuddy(self.tag_filter)
        scope = QLabel("Applies to all sections", self.controls)
        scope.setWordWrap(True)
        apply_text_role(scope, TextRole.SECONDARY)
        self.reset_button = QPushButton("Reset View", self.controls)
        self.reset_button.setObjectName("resetPerformanceView")
        apply_action_role(self.reset_button, ActionRole.SECONDARY)
        controls_layout.addWidget(label)
        controls_layout.addWidget(self.tag_filter)
        controls_layout.addWidget(scope, 1)
        controls_layout.addWidget(self.reset_button)

        self.message = PersistentMessageLabel(
            accessible_name="Performance report status", parent=self.content
        )
        self.message.setObjectName("performanceStatus")
        layout.addWidget(self.message)
        self.retry_button = QPushButton("Try again", self.content)
        apply_action_role(self.retry_button, ActionRole.SECONDARY)
        layout.addWidget(self.retry_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.retry_button.hide()
        self.sections = {}
        for mode, description, keys in (
            (
                "Adaptive",
                "Forecasts you can revise over time.",
                (Section.ADAPTIVE_BINARY, Section.ADAPTIVE_NUMERIC),
            ),
            (
                "One-Shot",
                "One forecast per prediction. Selective entry of transcribed exercises can bias these results.",
                (Section.ONE_SHOT_BINARY, Section.ONE_SHOT_NUMERIC),
            ),
        ):
            heading = QLabel(mode, self.content)
            apply_text_role(heading, TextRole.SECTION_TITLE)
            layout.addWidget(heading)
            explanation = QLabel(description, self.content)
            explanation.setWordWrap(True)
            apply_text_role(explanation, TextRole.SECONDARY)
            layout.addWidget(explanation)
            binary = BinarySection(keys[0], self.content)
            numeric = NumericSection(keys[1], self.content)
            for key, widget in ((keys[0], binary), (keys[1], numeric)):
                self.sections[key] = widget
                widget.retry_requested.connect(lambda key=key: self.retry_section(key))
                widget.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
                )
            pair = _ResponsiveMetricRow(
                (binary, numeric),
                stack_below=960,
                object_name=f"{mode}PerformancePair",
                parent=self.content,
            )
            layout.addWidget(pair)
        layout.addStretch()
        self.scroll_area.setWidget(self.content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll_area)
        self.controls.raise_()
        self.scroll_area.viewport().installEventFilter(self)
        self.controls_slot.installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            self._position_controls
        )
        self.retrieval = ReadRequests(
            query
            or (lambda request: operations.performance.query_independently(request)),
            self,
        )
        self.retrieval.pending.connect(self._pending)
        self.retrieval.ready.connect(self._ready)
        self.retrieval.failed.connect(self._failed)
        self.tag_filter.currentIndexChanged.connect(self._tag_changed)
        self.sections[Section.ADAPTIVE_NUMERIC].unit_changed.connect(
            lambda unit: self._unit_changed(unit, adaptive=True)
        )
        self.sections[Section.ONE_SHOT_NUMERIC].unit_changed.connect(
            lambda unit: self._unit_changed(unit, adaptive=False)
        )
        self.reset_button.clicked.connect(self.reset_view)
        self.retry_button.clicked.connect(self.refresh)
        QTimer.singleShot(0, self._position_controls)

    def refresh(self, *, preserve: bool = True) -> None:
        if self.refused:
            return
        if preserve and not self.loading and self.report is not None:
            self.state.position = self.scroll_area.verticalScrollBar().value()
        self._refreshing_section = None
        self.retrieval.request(self.state.request)

    def retry_section(self, section: Section) -> None:
        if self.refused:
            return
        if not self.loading:
            self.state.position = self.scroll_area.verticalScrollBar().value()
        self._refreshing_section = section
        self.retrieval.request(self.state.request)

    def _pending(self) -> None:
        self.loading = True
        if self._refreshing_section is None:
            self.report = None
        self.message.show_message(
            "Loading current report…"
            if self._refreshing_section is None
            else "Retrying the unavailable section…",
            StatusTone.NEUTRAL,
        )
        self.retry_button.hide()
        for key, section in self.sections.items():
            if self._refreshing_section is None or key == self._refreshing_section:
                section.pending()

    def _ready(self, report: PerformanceReport) -> None:
        self.content.setUpdatesEnabled(False)
        self.loading = False
        self._refreshing_section = None
        self.report = report
        self.state.tag_id = report.effective_tag_id
        choices = [
            ("All tags", None),
            *((tag.display_name, tag.tag_id) for tag in report.tags),
        ]
        self._choices(self.tag_filter, choices, self.state.tag_id)
        self.tag_filter.setToolTip(
            self.tag_filter.currentText() + " · applies to all sections"
        )
        for key, choices, selected in (
            (Section.ADAPTIVE_NUMERIC, report.adaptive_units, self.state.adaptive_unit),
            (Section.ONE_SHOT_NUMERIC, report.one_shot_units, self.state.one_shot_unit),
        ):
            self._choices(
                self.sections[key].unit_filter,
                [("All units", None), *((unit, unit) for unit in choices)],
                selected,
            )
        for result in report.sections:
            self.sections[result.section].show_result(result)
        failures = sum(result.error is not None for result in report.sections)
        self.retry_button.setVisible(failures == 4)
        if failures == 4:
            self.message.show_message(
                "Performance could not load. Try again; this is not an empty report.",
                StatusTone.ERROR,
            )
        elif failures:
            self.message.show_message(
                f"{failures} section(s) could not load. The other results are current."
                + (" " + report.notice if report.notice else ""),
                StatusTone.WARNING,
            )
        elif report.notice:
            self.message.show_message(report.notice, StatusTone.INFO)
        elif all(self._count(result.data) == 0 for result in report.sections):
            self.message.show_message(
                "No eligible results match this report scope. The four groups remain separate; no scores are invented.",
                StatusTone.INFO,
            )
        else:
            self.message.clear_message()
        QTimer.singleShot(0, self._restore_position)

    @staticmethod
    def _count(data) -> int:
        return getattr(
            data, "scored_prediction_count", getattr(data, "resolved_count", 0)
        )

    @staticmethod
    def _choices(
        control: QComboBox, choices: list[tuple[str, object]], selected
    ) -> None:
        with QSignalBlocker(control):
            control.clear()
            for label, value in choices:
                control.addItem(label, value)
            index = control.findData(selected)
            if index < 0:
                control.addItem(str(selected) + " (unavailable)", selected)
                index = control.count() - 1
            control.setCurrentIndex(index)
            control.setToolTip(control.currentText())

    def _failed(self, error: Exception) -> None:
        self.loading = False
        self.report = None
        self.message.show_message(
            "Performance unavailable. " + str(error), StatusTone.ERROR
        )
        self.retry_button.show()
        for section in self.sections.values():
            section.results.hide()
            section.status.clear_message()
            section.retry.hide()
        if isinstance(error, (ForecastContractIntegrityError, MigrationError)):
            self.refused = True
            self.retry_button.hide()
            self.retrieval.invalidate()
            self.archive_refused.emit(error)

    def _tag_changed(self) -> None:
        self.state.tag_id = self.tag_filter.currentData()
        self.refresh()

    def _unit_changed(self, unit, *, adaptive: bool) -> None:
        if adaptive:
            self.state.adaptive_unit = unit
        else:
            self.state.one_shot_unit = unit
        self.refresh()

    def tag_changed(self, change) -> None:
        """Follow only a successfully confirmed merge's known stable target."""
        if change.kind == "merge" and self.state.tag_id in change.source_ids:
            self.state.tag_id = change.target_id
            with QSignalBlocker(self.tag_filter):
                index = self.tag_filter.findData(change.target_id)
                if index < 0:
                    self.tag_filter.addItem(change.target_name, change.target_id)
                    index = self.tag_filter.count() - 1
                self.tag_filter.setCurrentIndex(index)
        self.retrieval.invalidate()
        self.report = None
        self.loading = False

    def leave(self) -> None:
        # Loading/failure collapses the body. Do not replace the last useful
        # reading position with that temporary geometry on a detour/retry.
        if not self.loading and self.report is not None:
            self.state.position = self.scroll_area.verticalScrollBar().value()

    def reset_view(self) -> None:
        self.state.reset()
        for section in self.sections.values():
            section.reset_disclosures()
        with QSignalBlocker(self.tag_filter):
            self.tag_filter.setCurrentIndex(0)
        for key in (Section.ADAPTIVE_NUMERIC, Section.ONE_SHOT_NUMERIC):
            control = self.sections[key].unit_filter
            with QSignalBlocker(control):
                control.setCurrentIndex(0)
        self.refresh(preserve=False)

    def _restore_position(self) -> None:
        if not self.loading:
            self.scroll_area.verticalScrollBar().setValue(self.state.position)
        self._position_controls()
        self.content.setUpdatesEnabled(True)

    def _position_controls(self) -> None:
        if not hasattr(self, "controls"):
            return
        width = max(1, self.scroll_area.viewport().width() - 32)
        height = self.controls.sizeHint().height()
        if self.controls_slot.height() != height:
            self.controls_slot.setFixedHeight(height)
        point = self.controls_slot.mapTo(
            self.scroll_area.viewport(), self.controls_slot.rect().topLeft()
        )
        self.controls.setGeometry(16, max(0, point.y()), width, height)
        self.controls.raise_()

    def eventFilter(self, watched, event) -> bool:
        if not self._position_pending and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.LayoutRequest,
            QEvent.Type.FontChange,
        ):
            self._position_pending = True
            QTimer.singleShot(0, self._position_later)
        return super().eventFilter(watched, event)

    def _position_later(self) -> None:
        self._position_pending = False
        self._position_controls()

    def close_retrieval(self) -> None:
        self.retrieval.close()
