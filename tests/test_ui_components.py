from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from reckonsolve.ui.components import (
    ContentPanel,
    EmptyStateLabel,
    PageHeader,
    PersistentMessageLabel,
)
from reckonsolve.ui.notifications import NotificationHost
from reckonsolve.ui.visual_system import (
    BADGE_TONE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    StatusTone,
    SurfaceRole,
    TextRole,
)


def test_shared_page_components_expose_semantic_and_accessible_structure(
    qtbot: QtBot,
) -> None:
    root = QWidget()
    qtbot.addWidget(root)
    header = PageHeader("Dashboard", "Supporting text", parent=root)
    action = QPushButton("Refresh", header)
    header.add_action(action)
    panel = ContentPanel("Open", "Current forecasts", parent=root)
    panel.set_count(3)
    empty = EmptyStateLabel("No forecasts.", parent=panel.body)
    panel.body_layout.addWidget(empty)
    message = PersistentMessageLabel(accessible_name="Page error", parent=root)
    message.show_message("Could not refresh.", StatusTone.ERROR)

    assert header.title_label.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert header.supporting_label.property(TEXT_ROLE_PROPERTY) == (
        TextRole.SECONDARY.value
    )
    assert not header.action_region.isHidden()
    assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert panel.count_badge.text() == "3"
    assert panel.count_badge.accessibleName() == "3 items"
    assert panel.count_badge.property(BADGE_TONE_PROPERTY) == StatusTone.NEUTRAL.value
    assert empty.property(TEXT_ROLE_PROPERTY) == TextRole.SECONDARY.value
    assert message.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert message.accessibleName() == "Page error"


def test_notification_is_overlayed_coalesced_and_keyboard_dismissible(
    qtbot: QtBot,
) -> None:
    root = QWidget()
    root.resize(720, 480)
    layout = QVBoxLayout(root)
    page = QLabel("Stable page content", root)
    layout.addWidget(page)
    host = NotificationHost(root, duration_ms=2_000, modal_widget=lambda: None)
    qtbot.addWidget(root)
    root.show()
    qtbot.waitExposed(root)
    baseline = page.geometry()

    host.show_message("Threshold saved.")
    first_position = host.pos()
    host.show_message("Threshold saved.")
    qtbot.wait(1)

    assert host.isVisible()
    assert page.geometry() == baseline
    assert host.current_message == "Threshold saved."
    assert host.repeat_count == 2
    assert host.message_label.text() == "Threshold saved. (2 times)"
    assert host.message_label.accessibleDescription() == host.message_label.text()
    assert host.width() >= 340
    assert host.dismiss_button.geometry().top() >= (
        host.message_label.geometry().bottom()
    )
    assert host.dismiss_button.geometry().right() > host.width() // 2
    assert first_position.x() > 0
    assert first_position.y() > 0

    host.dismiss_button.setFocus()
    qtbot.keyClick(host.dismiss_button, Qt.Key.Key_Escape)
    assert host.isHidden()


def test_notification_waits_for_modal_context_and_auto_dismisses(qtbot: QtBot) -> None:
    root = QWidget()
    root.resize(640, 400)
    root.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    modal = QWidget(root, Qt.WindowType.Dialog)
    modal_state: list[QWidget | None] = [modal]
    host = NotificationHost(
        root,
        duration_ms=40,
        modal_widget=lambda: modal_state[0],
    )
    qtbot.addWidget(root)
    root.show()
    root.setFocus()
    modal.show()

    host.show_message("Postmortem skipped.")
    assert host.isHidden()

    modal.hide()
    modal_state[0] = None
    host._modal_timer.timeout.emit()
    assert host.isVisible()
    qtbot.mouseMove(root, QPoint(1, 1))
    qtbot.waitUntil(host.isHidden, timeout=500)


def test_notification_presentation_failure_is_contained(qtbot: QtBot) -> None:
    root = QWidget()
    host = NotificationHost(
        root,
        modal_widget=lambda: (_ for _ in ()).throw(RuntimeError("backend failed")),
    )
    qtbot.addWidget(root)

    host.show_message("Already committed.")

    assert host.isHidden()
    assert host.current_message == ""
