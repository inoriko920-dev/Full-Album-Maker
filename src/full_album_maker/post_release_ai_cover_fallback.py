from __future__ import annotations

"""Use a song cover when an AI preview video has no directly loadable still.

QPixmap cannot decode an MP4 locator. The AI timeline should therefore fall back
to the song's existing cover artwork rather than painting a generic color block.
The media/project model is untouched; this is preview presentation only.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

_installed = False


def install_post_release_ai_cover_fallback() -> None:
    global _installed
    if _installed:
        return

    from . import post_release_ai_preview_timeline_surface as surface

    original = surface._cover_pixmap

    def cover_with_fallback(document, song, width: int, height: int):
        rendered = original(document, song, width, height)
        if rendered is not None:
            return rendered
        cover_id = getattr(song, "cover_asset_id", None)
        if not cover_id:
            return None
        asset = document.asset_map().get(cover_id)
        if asset is None:
            return None
        locator = Path(str(getattr(asset, "locator", "") or ""))
        if not locator.is_file():
            return None
        pixmap = QPixmap(str(locator))
        if pixmap.isNull():
            return None
        return pixmap.scaled(
            max(1, width),
            max(1, height),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    surface._cover_pixmap = cover_with_fallback
    _installed = True
