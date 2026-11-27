"""History sizing handles Qt's unavailable height-for-width measurement."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from reckonsolve.ui.history_disclosure import history_disclosure
from reckonsolve.ui.visual_system import install_visual_system


def test_history_uses_natural_height_when_parent_has_surplus_space(qtbot):
    from datetime import UTC, datetime

    from reckonsolve.ui.prediction_widgets import _HistoryEntry

    parent = QWidget()
    qtbot.addWidget(parent)
    install_visual_system(parent)
    layout = QVBoxLayout(parent)
    history = history_disclosure("Edit History", "surplusSpaceHistory", parent)
    layout.addWidget(history)
    body = history.disclosure_body
    row = _HistoryEntry(
        "Original", datetime(2026, 11, 20, tzinfo=UTC), body, end_rule=False
    )
    row.column.addWidget(QLabel("The original recorded reasoning.", row))
    body.layout().addWidget(row)
    history.show()
    parent.resize(500, 900)
    parent.show()
    history.disclosure_button.setChecked(True)
    qtbot.waitUntil(
        lambda: (
            body.height() <= body.layout().minimumSize().height() + 2
            and history.height() <= history.layout().minimumSize().height() + 2
        ),
        timeout=2000,
    )
    assert body.height() <= body.layout().minimumSize().height() + 2
    assert history.height() <= history.layout().minimumSize().height() + 2
    history.disclosure_button.setChecked(False)
    qtbot.waitUntil(lambda: history.height() < 120, timeout=2000)
    assert history.height() < 120


@pytest.mark.parametrize("kind", ["journal", "resolution"])
def test_expanded_original_shrinks_after_widening_without_retaining_blank_height(
    qtbot, kind
):
    from datetime import UTC, datetime

    from reckonsolve.ui.prediction_widgets import _HistoryEntry

    parent = QWidget()
    qtbot.addWidget(parent)
    install_visual_system(parent)
    parent_layout = QVBoxLayout(parent)
    parent_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    row = _HistoryEntry(
        "Original", datetime(2026, 11, 20, tzinfo=UTC), parent, end_rule=True
    )
    body = QLabel(
        ("Original reasoning remains readable. " * 30) + "\nA second paragraph.", row
    )
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setWordWrap(True)
    if kind == "resolution":
        row.column.addWidget(QLabel("Original outcome: Yes", row))
    row.column.addWidget(body)
    parent_layout.addWidget(row)
    parent.resize(220, 900)
    parent.show()
    qtbot.wait(60)
    narrow = body.height()
    parent.resize(800, 900)
    qtbot.wait(80)
    oracle = QLabel(body.text())
    oracle.setFont(body.font())
    oracle.setTextFormat(Qt.TextFormat.PlainText)
    oracle.setWordWrap(True)
    natural = oracle.heightForWidth(body.width())
    assert narrow > natural
    assert body.height() <= natural + 2
    assert body.height() >= natural
    qtbot.wait(30)
    assert not row._height_timer.isActive()


@pytest.mark.parametrize(
    "name", ["resolutionCorrectionHistory", "numericResolutionCorrectionHistory"]
)
def test_history_startup_and_empty_expansion_never_set_negative_sizes(
    qtbot, qtlog, name
):
    parent = QWidget()
    qtbot.addWidget(parent)
    install_visual_system(parent)
    layout = QVBoxLayout(parent)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    history = history_disclosure("Resolution History", name, parent)
    layout.addWidget(history)
    # An unavailable measurement is a legitimate Qt state while content and
    # controls are hidden, before an actual Prediction has been selected.
    history.disclosure_button.hide()
    history.disclosure_count.hide()
    assert history.layout().minimumHeightForWidth(history.width()) == -1
    qtbot.wait(30)

    history.disclosure_button.show()
    history.disclosure_count.show()
    history.show()
    parent.resize(400, 500)
    parent.show()
    history.disclosure_button.setChecked(True)
    qtbot.wait(30)
    assert (
        history.disclosure_body.layout().minimumHeightForWidth(
            history.disclosure_body.width()
        )
        == -1
    )

    text = QLabel("Original recorded notes remain fully readable. " * 12)
    text.setWordWrap(True)
    history.disclosure_body.layout().addWidget(text)
    qtbot.wait(40)
    assert text.height() >= text.heightForWidth(text.width())
    history.disclosure_button.setChecked(False)
    qtbot.wait(30)
    assert history.minimumHeight() >= 0
    assert history.height() < 200
    assert not [
        record.message
        for record in qtlog.records
        if "QWidget::setMinimumSize" in record.message
        or "Negative sizes" in record.message
    ]
