from __future__ import annotations

"""Small deterministic scene details for selected Template fallback cards.

The approved UI-06 reference uses a sunset portrait for "Senja di Kota Ini", an
airy mountain title-card for "Jalan Pulang", and a green road-trip scene for
"Perjalanan Kita". These vector details are painted only when no real cached or
rendered thumbnail pixmap exists. No template model, filter metadata, apply
command, project state, or render behavior is changed.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

_installed = False


def _paint_subject(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    head_size = min(rect.width(), rect.height()) * 0.24
    cx = rect.left() + rect.width() * 0.77
    cy = rect.top() + rect.height() * 0.37
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(20, 22, 30, 205))
    painter.drawEllipse(QRectF(cx - head_size * 0.54, cy - head_size * 0.58, head_size, head_size * 1.08))
    painter.setBrush(QColor(92, 61, 54, 205))
    painter.drawPolygon(QPolygonF([
        QPointF(cx - head_size * 0.43, cy - head_size * 0.25),
        QPointF(cx - head_size * 0.62, cy - head_size * 0.02),
        QPointF(cx - head_size * 0.42, cy + head_size * 0.08),
        QPointF(cx - head_size * 0.31, cy + head_size * 0.34),
        QPointF(cx + head_size * 0.02, cy + head_size * 0.30),
        QPointF(cx + head_size * 0.08, cy - head_size * 0.22),
    ]))
    path = QPainterPath()
    path.moveTo(cx - head_size * 0.20, cy + head_size * 0.42)
    path.cubicTo(
        cx - head_size * 0.75, cy + head_size * 0.70,
        rect.left() + rect.width() * 0.62, rect.bottom(),
        rect.left() + rect.width() * 0.58, rect.bottom(),
    )
    path.lineTo(rect.right() + 2, rect.bottom() + 2)
    path.lineTo(rect.right() + 2, cy + head_size * 0.54)
    path.cubicTo(
        cx + head_size * 0.85, cy + head_size * 0.46,
        cx + head_size * 0.45, cy + head_size * 0.38,
        cx - head_size * 0.20, cy + head_size * 0.42,
    )
    path.closeSubpath()
    painter.setBrush(QColor(25, 31, 43, 215))
    painter.drawPath(path)
    painter.restore()


def _paint_jalan_pulang(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sky.setColorAt(0.0, QColor("#315D80"))
    sky.setColorAt(0.58, QColor("#7397AD"))
    sky.setColorAt(1.0, QColor("#B8CDD5"))
    painter.fillRect(rect, sky)
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
    painter.fillRect(QRectF(rect.left(), rect.top() + rect.height() * .25, rect.width(), rect.height() * .50), QColor(13, 38, 55, 34))
    painter.setPen(QPen(QColor("#F8FBFF"), 1))
    font = painter.font(); font.setBold(True); font.setPointSizeF(max(8.0, min(13.0, rect.width() / 15.0)))
    painter.setFont(font)
    painter.drawText(rect.adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "JALAN\nPULANG")
    painter.restore()


def _paint_perjalanan(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sky.setColorAt(0.0, QColor("#2F5D55"))
    sky.setColorAt(0.52, QColor("#78948A"))
    sky.setColorAt(1.0, QColor("#B8B890"))
    painter.fillRect(rect, sky)
    painter.setPen(Qt.PenStyle.NoPen)
    # Mountain horizon and green valley.
    painter.setBrush(QColor("#3E6654"))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() - 2, rect.bottom()),
        QPointF(rect.left() + rect.width() * .18, rect.top() + rect.height() * .48),
        QPointF(rect.left() + rect.width() * .36, rect.top() + rect.height() * .27),
        QPointF(rect.left() + rect.width() * .50, rect.top() + rect.height() * .50),
        QPointF(rect.left() + rect.width() * .68, rect.top() + rect.height() * .22),
        QPointF(rect.left() + rect.width() * .88, rect.top() + rect.height() * .46),
        QPointF(rect.right() + 2, rect.bottom()),
    ]))
    painter.setBrush(QColor("#567A4D"))
    painter.drawRect(QRectF(rect.left(), rect.top() + rect.height() * .60, rect.width(), rect.height() * .42))
    # Perspective road leading into the valley.
    painter.setBrush(QColor("#D7C9A0"))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() + rect.width() * .47, rect.top() + rect.height() * .54),
        QPointF(rect.left() + rect.width() * .54, rect.top() + rect.height() * .54),
        QPointF(rect.left() + rect.width() * .72, rect.bottom() + 2),
        QPointF(rect.left() + rect.width() * .27, rect.bottom() + 2),
    ]))
    # Small cream road-trip vehicle.
    car_w = rect.width() * .12; car_h = rect.height() * .12
    car_x = rect.left() + rect.width() * .45; car_y = rect.top() + rect.height() * .66
    painter.setBrush(QColor("#E7DDC0")); painter.drawRoundedRect(QRectF(car_x, car_y, car_w, car_h), 2, 2)
    painter.setBrush(QColor("#4F6867")); painter.drawRect(QRectF(car_x + car_w * .18, car_y + car_h * .18, car_w * .62, car_h * .34))
    painter.setPen(QPen(QColor("#F8FBF6"), 1))
    font = painter.font(); font.setBold(True); font.setPointSizeF(max(7.5, min(11.5, rect.width() / 17.0)))
    painter.setFont(font)
    painter.drawText(rect.adjusted(9, 7, -9, -9), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, "Perjalanan\nKita")
    painter.restore()


def install_post_release_template_subject_detail() -> None:
    global _installed
    if _installed:
        return
    from .template_workspace_step07 import TemplateThumbnailPlaceholder
    from .post_release_template_inspector_adjustment import TemplateInspectorPreview
    previous_thumb = TemplateThumbnailPlaceholder.paintEvent
    previous_preview = TemplateInspectorPreview.paintEvent

    def paint_thumbnail(self, event) -> None:
        previous_thumb(self, event)
        pixmap = getattr(self, "_pixmap", None)
        if pixmap is not None and not pixmap.isNull():
            return
        template_id = str(getattr(self, "template_id", ""))
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        if template_id == "spotify_clean":
            _paint_subject(painter, rect)
        elif template_id == "cafe_acoustic":
            _paint_jalan_pulang(painter, rect)
        elif template_id == "viral_full_album":
            _paint_perjalanan(painter, rect)
        painter.end()

    def paint_preview(self, event) -> None:
        previous_preview(self, event)
        if str(getattr(self, "template_id", "")) != "spotify_clean":
            return
        painter = QPainter(self)
        _paint_subject(painter, QRectF(self.rect()).adjusted(3, 3, -3, -3))
        painter.end()

    TemplateThumbnailPlaceholder.paintEvent = paint_thumbnail
    TemplateInspectorPreview.paintEvent = paint_preview
    _installed = True
