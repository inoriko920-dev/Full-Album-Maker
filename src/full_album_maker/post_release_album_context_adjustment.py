from __future__ import annotations

"""Small UI-03 presentation adjustment for the Album context rail only."""

from PySide6.QtCore import QSize

from .foundation_icons import foundation_icon

_installed = False


def install_post_release_album_context_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .album_workspace import AlbumContextWidget

    original_init = AlbumContextWidget.__init__

    def init_with_reference_context(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.cover.setFixedSize(96, 96)
        icon_names = {
            "all": "album",
            "missing_cover": "media",
            "missing_visual": "timeline",
            "review": "settings",
        }
        for key, button in self.filter_buttons.items():
            button.setIcon(foundation_icon(icon_names[key], color="#234F8E", size=19))
            button.setIconSize(QSize(19, 19))
            button.setMinimumHeight(42)

    AlbumContextWidget.__init__ = init_with_reference_context
    _installed = True
