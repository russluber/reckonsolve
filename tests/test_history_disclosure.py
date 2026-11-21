"""History sizing handles Qt's unavailable height-for-width measurement."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from reckonsolve.ui.history_disclosure import history_disclosure
from reckonsolve.ui.visual_system import install_visual_system


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
