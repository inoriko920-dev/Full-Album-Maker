from __future__ import annotations

"""Small UI-03 presentation adjustment for real song cover thumbnails only."""

from PySide6.QtCore import QSize

_installed = False


def install_post_release_album_thumbnail_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .album_workspace import AlbumSongTable

    original_init = AlbumSongTable.__init__

    def init_with_reference_thumbnail_size(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.setIconSize(QSize(40, 28))

    AlbumSongTable.__init__ = init_with_reference_thumbnail_size
    _installed = True
