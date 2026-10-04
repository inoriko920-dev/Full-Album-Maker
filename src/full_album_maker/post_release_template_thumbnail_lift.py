from __future__ import annotations

"""Per-template luminance correction for deterministic Template fallbacks.

Only placeholder thumbnails without a real cached/rendered pixmap are adjusted.
Real user/runtime thumbnails remain untouched.  Each built-in fallback keeps its
existing scene composition while receiving a small deterministic luminance lift
appropriate to that scene; text is redrawn afterward for stable contrast.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

_installed = False

# Alpha byte for a white luminance lift. These values affect only the deterministic
# placeholder painter used while no real thumbnail exists.
_LIFT_ALPHA = {
    "spotify_clean": 16,
    "cafe_acoustic": 55,
    "viral_full_album": 17,
    "vinyl_nostalgia": 100,
    "neon_spectrum": 86,
    "romantic_bokeh": 99,
    "dark_cinematic": 56,
    "photo_album": 49,
    "cassette_retro": 19,
    "music_channel_pro": 89,
}


def install_post_release_template_thumbnail_lift() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateThumbnailPlaceholder

    previous_paint = TemplateThumbnailPlaceholder.paintEvent

    def lifted_paint(self, event) -> None:
        previous_paint(self, event)
        pixmap = getattr(self, "_pixmap", None)
        if pixmap is not None and not pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        inner = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        alpha = int(_LIFT_ALPHA.get(str(getattr(self, "template_id", "")), 46))
        if alpha > 0:
            painter.fillRect(inner, QColor(255, 255, 255, alpha))

        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(max(8.0, min(12.5, inner.width() / 17.0)))
        painter.setFont(font)
        painter.drawText(
            inner.adjusted(10, 20, -10, -8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
            str(getattr(self, "name", "Template") or "Template"),
        )
        painter.end()

    TemplateThumbnailPlaceholder.paintEvent = lifted_paint
    _installed = True
