from __future__ import annotations

"""Small luminance correction for deterministic Template fallback thumbnails.

Only placeholder thumbnails without a real cached/rendered pixmap are adjusted.
Real user/runtime thumbnails remain untouched.  The existing fallback painter is
kept as the source of composition; this layer lifts its luminance slightly and
redraws the title so text contrast remains stable.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

_installed = False


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
        painter.fillRect(inner, QColor(255, 255, 255, 46))

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
