from __future__ import annotations

"""Deterministic landscape refinement for selected Template fallback cards.

Only fallback placeholders without a real thumbnail pixmap are painted.  The
first refinement targets `cafe_acoustic` (Jalan Pulang): a blue mountain scene
with centered title treatment that better communicates the real template style.
No template model, filter metadata, apply command, or project state is changed.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF

_installed = False


def _paint_jalan_pulang(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)

    sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sky.setColorAt(0.0, QColor("#315D80"))
    sky.setColorAt(0.58, QColor("#7397AD"))
    sky.setColorAt(1.0, QColor("#B8CDD5"))
    painter.fillRect(rect, sky)

    # Distant mountain range.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#385C6D"))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() - 2, rect.bottom()),
        QPointF(rect.left() + rect.width() * .12, rect.top() + rect.height() * .58),
        QPointF(rect.left() + rect.width() * .28, rect.top() + rect.height() * .29),
        QPointF(rect.left() + rect.width() * .42, rect.top() + rect.height() * .60),
        QPointF(rect.left() + rect.width() * .58, rect.top() + rect.height() * .22),
        QPointF(rect.left() + rect.width() * .75, rect.top() + rect.height() * .54),
        QPointF(rect.left() + rect.width() * .91, rect.top() + rect.height() * .34),
        QPointF(rect.right() + 2, rect.bottom()),
    ]))
    painter.setBrush(QColor(25, 59, 73, 195))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() - 2, rect.bottom()),
        QPointF(rect.left() + rect.width() * .20, rect.top() + rect.height() * .64),
        QPointF(rect.left() + rect.width() * .40, rect.top() + rect.height() * .73),
        QPointF(rect.left() + rect.width() * .62, rect.top() + rect.height() * .55),
        QPointF(rect.left() + rect.width() * .82, rect.top() + rect.height() * .67),
        QPointF(rect.right() + 2, rect.top() + rect.height() * .54),
        QPointF(rect.right() + 2, rect.bottom() + 2),
    ]))

    # A faint horizon haze keeps the title legible while preserving landscape.
    painter.fillRect(
        QRectF(rect.left(), rect.top() + rect.height() * .28, rect.width(), rect.height() * .46),
        QColor(13, 38, 55, 38),
    )
    painter.setPen(QPen(QColor("#F8FBFF"), 1))
    font = painter.font()
    font.setBold(True)
    font.setPointSizeF(max(8.0, min(13.0, rect.width() / 15.0)))
    painter.setFont(font)
    painter.drawText(
        rect.adjusted(8, 8, -8, -8),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        "JALAN\nPULANG",
    )
    painter.restore()


def install_post_release_template_landscape_detail() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateThumbnailPlaceholder

    previous_paint = TemplateThumbnailPlaceholder.paintEvent

    def paint_thumbnail(self, event) -> None:
        previous_paint(self, event)
        if str(getattr(self, "template_id", "")) != "cafe_acoustic":
            return
        pixmap = getattr(self, "_pixmap", None)
        if pixmap is not None and not pixmap.isNull():
            return
        painter = QPainter(self)
        _paint_jalan_pulang(painter, QRectF(self.rect()).adjusted(5, 5, -5, -5))
        painter.end()

    TemplateThumbnailPlaceholder.paintEvent = paint_thumbnail
    _installed = True
