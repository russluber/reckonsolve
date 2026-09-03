from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    BADGE_TONE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    NAVIGATION_ACTIVE_PROPERTY,
    NAVIGATION_COMPACT_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    VISUAL_SYSTEM_PROPERTY,
    ActionRole,
    MotionDuration,
    Radius,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    animations_enabled,
    apply_action_role,
    apply_badge_role,
    apply_message_role,
    apply_navigation_active,
    apply_navigation_compact,
    apply_surface_role,
    apply_text_role,
    build_stylesheet,
    contrast_ratio,
    install_visual_system,
    semantic_colors,
)


def _test_palette(window: str, base: str, text: str, mid: str) -> QPalette:
    palette = QPalette()
    for role, value in (
        (QPalette.ColorRole.Window, window),
        (QPalette.ColorRole.Base, base),
        (QPalette.ColorRole.AlternateBase, window),
        (QPalette.ColorRole.WindowText, text),
        (QPalette.ColorRole.Text, text),
        (QPalette.ColorRole.ButtonText, text),
        (QPalette.ColorRole.PlaceholderText, text),
        (QPalette.ColorRole.Mid, mid),
    ):
        palette.setColor(role, QColor(value))
    return palette


def test_visual_tokens_form_small_shared_scales() -> None:
    assert tuple(Spacing) == (
        Spacing.COMPACT,
        Spacing.CONTROL,
        Spacing.ORDINARY,
        Spacing.SECTION,
        Spacing.PAGE,
    )
    assert tuple(Radius) == (Radius.SMALL, Radius.CONTROL, Radius.PANEL)
    assert MotionDuration.QUICK < MotionDuration.DISCLOSURE <= 200


@pytest.mark.parametrize(
    ("palette", "expected_dark"),
    [
        (_test_palette("#f4f5f4", "#ffffff", "#1c211f", "#c7ceca"), False),
        (_test_palette("#171a18", "#202421", "#edf3ef", "#505852"), True),
    ],
)
def test_semantic_colors_are_palette_aware_and_contrast_safe(
    palette: QPalette,
    expected_dark: bool,
) -> None:
    colors = semantic_colors(palette)

    assert colors.is_dark is expected_dark
    assert contrast_ratio(colors.accent, colors.on_accent) >= 4.5
    assert contrast_ratio(colors.warning, colors.warning_surface) >= 4.5
    assert contrast_ratio(colors.error, colors.error_surface) >= 4.5
    assert contrast_ratio(colors.secondary_text, colors.canvas) >= 4.5
    assert contrast_ratio(colors.text, colors.surface) >= 4.5
    assert contrast_ratio(colors.text, colors.raised) >= 4.5
    assert contrast_ratio(colors.text, colors.input) >= 4.5


def test_dark_palette_rejects_white_native_alternate_surface() -> None:
    palette = _test_palette("#1f1f1f", "#242725", "#f2f5f3", "#555b57")
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#ffffff"))

    colors = semantic_colors(palette)

    assert colors.is_dark
    assert colors.raised != "#ffffff"
    assert QColor(colors.raised).lightnessF() < 0.5
    assert contrast_ratio(colors.text, colors.raised) >= 4.5
    assert f"background-color: {colors.raised};" in build_stylesheet(palette)


def test_stylesheet_covers_semantic_roles_and_interaction_states() -> None:
    palette = _test_palette("#f4f5f4", "#ffffff", "#1c211f", "#c7ceca")
    stylesheet = build_stylesheet(palette)
    colors = semantic_colors(palette)

    for selector in (
        'reckonsolveTextRole="page-title"',
        'reckonsolveSurfaceRole="raised"',
        'reckonsolveActionRole="primary"',
        'reckonsolveActionRole="quiet"',
        'reckonsolveActionRole="destructive"',
        'reckonsolveNavigationActive="true"',
        'reckonsolveCompactNavigation="true"',
        "QListWidget#predictionBrowserResults {\n    padding:",
        'reckonsolveBadgeTone="warning"',
        'reckonsolveMessageTone="error"',
        'searchMatchEmphasis="true"',
    ):
        assert selector in stylesheet
    assert ":hover" in stylesheet
    assert ":pressed" in stylesheet
    assert ":focus" in stylesheet
    assert ":disabled" in stylesheet
    assert "top: 2px;" in stylesheet
    assert (
        "QListWidget::item:hover {\n"
        f"    background-color: {colors.accent_soft};\n"
        f"    color: {colors.on_accent_soft};\n"
        "}"
    ) in stylesheet


def test_visual_helpers_assign_roles_fonts_and_accessible_names(qtbot: QtBot) -> None:
    root = QWidget()
    title = QLabel("Predictions", root)
    panel = QWidget(root)
    button = QPushButton("&Save Review", root)
    badge = QLabel("Open", root)
    message = QLabel("Could not save.", root)
    qtbot.addWidget(root)

    install_visual_system(root)
    apply_text_role(title, TextRole.PAGE_TITLE)
    apply_surface_role(panel, SurfaceRole.RAISED)
    apply_action_role(button, ActionRole.PRIMARY)
    apply_navigation_active(button, True)
    apply_navigation_compact(panel, True)
    apply_badge_role(badge, StatusTone.ACCENT)
    apply_message_role(
        message,
        StatusTone.ERROR,
        accessible_name="Save error",
    )

    assert root.property(VISUAL_SYSTEM_PROPERTY) is True
    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert title.font().bold()
    assert title.font().pointSizeF() > root.font().pointSizeF()
    assert panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert button.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert button.property(NAVIGATION_ACTIVE_PROPERTY) is True
    assert panel.property(NAVIGATION_COMPACT_PROPERTY) is True
    assert button.accessibleName() == "Save Review"
    assert badge.property(BADGE_TONE_PROPERTY) == StatusTone.ACCENT.value
    assert badge.accessibleName() == "Open"
    assert message.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert message.accessibleName() == "Save error"


def test_icon_only_actions_require_an_explicit_accessible_name(qtbot: QtBot) -> None:
    button = QPushButton("")
    qtbot.addWidget(button)

    with pytest.raises(ValueError, match="accessible name"):
        apply_action_role(button, ActionRole.QUIET)

    apply_action_role(
        button,
        ActionRole.QUIET,
        accessible_name="Collapse sidebar",
    )
    assert button.accessibleName() == "Collapse sidebar"


def test_disabled_action_keeps_role_and_visual_system_contract(qtbot: QtBot) -> None:
    root = QWidget()
    button = QPushButton("Create Prediction", root)
    qtbot.addWidget(root)
    install_visual_system(root)
    apply_action_role(button, ActionRole.PRIMARY)

    button.setDisabled(True)

    assert not button.isEnabled()
    assert button.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert 'reckonsolveActionRole="primary"]:disabled' in root.styleSheet()


def test_motion_preference_comes_from_qt_style_hint(qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    assert isinstance(animations_enabled(widget), bool)


def test_visual_boundary_has_no_domain_application_analytics_or_data_imports() -> None:
    source_path = (
        Path(__file__).parents[1] / "src" / "reckonsolve" / "ui" / "visual_system.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "reckonsolve.analytics",
        "reckonsolve.application",
        "reckonsolve.data",
        "reckonsolve.domain",
    )
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(module.startswith(forbidden_prefixes) for module in imported_modules)
