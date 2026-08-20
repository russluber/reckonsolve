from __future__ import annotations

from importlib.resources import files

from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from reckonsolve.ui.assets.icons import LUCIDE_VERSION
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon, lucide_icon


def test_selected_lucide_resources_are_complete_and_pinned() -> None:
    icon_root = files("reckonsolve.ui.assets.icons")
    resource_names = {
        resource.name.removesuffix(".svg")
        for resource in icon_root.iterdir()
        if resource.name.endswith(".svg")
    }

    assert LUCIDE_VERSION == "1.33.0"
    assert resource_names == {icon.value for icon in LucideIcon}
    assert icon_root.joinpath("LUCIDE_LICENSE.txt").is_file()


def test_every_selected_lucide_icon_renders_in_all_button_modes(qtbot: QtBot) -> None:
    button = QPushButton("Host")
    qtbot.addWidget(button)

    for name in LucideIcon:
        icon = lucide_icon(name, button.palette())
        assert not icon.isNull()
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Disabled, QIcon.Mode.Selected):
            assert not icon.pixmap(24, 24, mode, QIcon.State.Off).isNull()


def test_lucide_icons_are_recolored_for_the_active_palette(qtbot: QtBot) -> None:
    button = QPushButton("Host")
    qtbot.addWidget(button)
    light_palette = QPalette(button.palette())
    light_palette.setColor(QPalette.ColorRole.Text, QColor("#112233"))
    dark_palette = QPalette(button.palette())
    dark_palette.setColor(QPalette.ColorRole.Text, QColor("#e5e7eb"))

    light_icon = lucide_icon(LucideIcon.SEARCH, light_palette)
    dark_icon = lucide_icon(LucideIcon.SEARCH, dark_palette)

    assert light_icon.cacheKey() != dark_icon.cacheKey()
    assert "#112233" in _opaque_colors(light_icon)
    assert "#e5e7eb" in _opaque_colors(dark_icon)


def test_applying_icon_keeps_visible_text_and_accessible_name(qtbot: QtBot) -> None:
    button = QPushButton("&Save Changes")
    qtbot.addWidget(button)

    apply_lucide_icon(button, LucideIcon.SAVE)

    assert button.text() == "&Save Changes"
    assert button.accessibleName() == "Save Changes"
    assert not button.icon().isNull()
    assert button.iconSize().width() == 18


def _opaque_colors(icon: QIcon) -> set[str]:
    image = icon.pixmap(24, 24, QIcon.Mode.Normal, QIcon.State.Off).toImage()
    return {
        image.pixelColor(x, y).name()
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    }
