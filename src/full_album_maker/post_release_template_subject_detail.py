from __future__ import annotations

"""Small deterministic scene details for selected Template fallback cards.

The approved UI-06 reference uses photographic-looking fallback scenes.  These
vector details are painted only when no real cached/rendered thumbnail pixmap
exists.  No template model, filter metadata, apply command, project state, or
render behavior is changed.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

_installed = False


def _paint_subject(painter: QPainter, rect: QRectF) -> None:
    """Paint an abstract right-side portrait silhouette within *rect*."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)

    head_size = min(rect.width(), rect.height()) * 0.24
    cx = rect.left() + rect.width() * 0.77
    cy = rect.top() + rect.height() * 0.37
    hair = QColor(20, 22, 30, 205)
    face = QColor(92, 61, 54, 205)
    body = QColor(25, 31, 43, 215)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(hair)
    painter.drawEllipse(QRectF(cx - head_size * 0.54, cy - head_size * 0.58, head_size, head_size * 1.08))

    painter.setBrush(face)
    profile = QPolygonF([
        QPointF(cx - head_size * 0.43, cy - head_size * 0.25),
        QPointF(cx - head_size * 0.62, cy - head_size * 0.02),
        QPointF(cx - head_size * 0.42, cy + head_size * 0.08),
        QPointF(cx - head_size * 0.31, cy + head_size * 0.34),
        QPointF(cx + head_size * 0.02, cy + head_size * 0.30),
        QPointF(cx + head_size * 0.08, cy - head_size * 0.22),
    ])
    painter.drawPolygon(profile)

    path = QPainterPath()
    path.moveTo(cx - head_size * 0.20, cy + head_size * 0.42)
    path.cubicTo(
        cx - head_size * 0.75,
        cy + head_size * 0.70,
        rect.left() + rect.width() * 0.62,
        rect.bottom(),
        rect.left() + rect.width() * 0.58,
        rect.bottom(),
    )
    path.lineTo(rect.right() + 2, rect.bottom() + 2)
    path.lineTo(rect.right() + 2, cy + head_size * 0.54)
    path.cubicTo(
        cx + head_size * 0.85,
        cy + head_size * 0.46,
        cx + head_size * 0.45,
        cy + head_size * 0.38,
        cx - head_size * 0.20,
        cy + head_size * 0.42,
    )
    path.closeSubpath()
    painter.setBrush(body)
    painter.drawPath(path)
    painter.restore()


def _paint_jalan_pulang(painter: QPainter, rect: QRectF) -> None:
    """Paint a cool mountain title-card scene for the cafe/acoustic fallback."""
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

    painter.fillRect(
        QRectF(rect.left(), rect.top() + rect.height() * .25, rect.width(), rect.height() * .50),
        QColor(13, 38, 55, 34),
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


def _paint_perjalanan(painter: QPainter, rect: QRectF) -> None:
    """Add the green travel-road + van cues visible in the approved card."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    painter.setPen(Qt.PenStyle.NoPen)

    # Green photographic cast and distant tree line.
    painter.fillRect(rect, QColor(22, 91, 61, 42))
    horizon = rect.top() + rect.height() * 0.48
    for index in range(9):
        x = rect.left() + rect.width() * (index / 8.0)
        half = rect.width() * 0.065
        peak = horizon - rect.height() * (0.10 + (index % 3) * 0.035)
        painter.setBrush(QColor(17, 66 + (index % 2) * 14, 44, 205))
        painter.drawPolygon(QPolygonF([
            QPointF(x - half, horizon + rect.height() * 0.18),
            QPointF(x, peak),
            QPointF(x + half, horizon + rect.height() * 0.18),
        ]))

    # Winding road, widening toward the foreground.
    road = QPainterPath()
    road.moveTo(rect.left() + rect.width() * 0.52, horizon - 1)
    road.cubicTo(
        rect.left() + rect.width() * 0.58,
        horizon + rect.height() * 0.10,
        rect.left() + rect.width() * 0.43,
        horizon + rect.height() * 0.18,
        rect.left() + rect.width() * 0.27,
        rect.bottom() + 2,
    )
    road.lineTo(rect.left() + rect.width() * 0.82, rect.bottom() + 2)
    road.cubicTo(
        rect.left() + rect.width() * 0.67,
        horizon + rect.height() * 0.20,
        rect.left() + rect.width() * 0.61,
        horizon + rect.height() * 0.08,
        rect.left() + rect.width() * 0.52,
        horizon - 1,
    )
    road.closeSubpath()
    painter.setBrush(QColor(164, 155, 126, 230))
    painter.drawPath(road)

    painter.setPen(QPen(QColor(239, 224, 174, 195), max(1.0, rect.width() * 0.008)))
    painter.drawLine(
        QPointF(rect.left() + rect.width() * 0.525, horizon + rect.height() * 0.04),
        QPointF(rect.left() + rect.width() * 0.55, rect.bottom() - rect.height() * 0.05),
    )

    # Small cream travel van.
    painter.setPen(Qt.PenStyle.NoPen)
    van = QRectF(
        rect.left() + rect.width() * 0.43,
        rect.top() + rect.height() * 0.60,
        rect.width() * 0.19,
        rect.height() * 0.18,
    )
    painter.setBrush(QColor("#E7E2C8"))
    painter.drawRoundedRect(van, 2, 2)
    painter.setBrush(QColor("#718E82"))
    painter.drawRect(QRectF(van.left() + van.width() * .12, van.top() + van.height() * .16, van.width() * .54, van.height() * .35))
    painter.setBrush(QColor("#213A35"))
    wheel = van.height() * .23
    painter.drawEllipse(QRectF(van.left() + van.width() * .16, van.bottom() - wheel * .55, wheel, wheel))
    painter.drawEllipse(QRectF(van.right() - van.width() * .30, van.bottom() - wheel * .55, wheel, wheel))
    painter.restore()


def _paint_cerita_baru(painter: QPainter, rect: QRectF) -> None:
    """Add a warm sunset valley composition to the Cerita Baru card."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    painter.setPen(Qt.PenStyle.NoPen)

    warm = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    warm.setColorAt(0.0, QColor(239, 151, 107, 72))
    warm.setColorAt(0.55, QColor(238, 151, 84, 95))
    warm.setColorAt(1.0, QColor(70, 48, 42, 35))
    painter.fillRect(rect, warm)

    sun_size = min(rect.width(), rect.height()) * 0.16
    painter.setBrush(QColor(255, 222, 142, 225))
    painter.drawEllipse(QRectF(
        rect.left() + rect.width() * 0.12,
        rect.top() + rect.height() * 0.43,
        sun_size,
        sun_size,
    ))

    painter.setBrush(QColor(102, 68, 53, 205))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() - 2, rect.bottom()),
        QPointF(rect.left() + rect.width() * .20, rect.top() + rect.height() * .60),
        QPointF(rect.left() + rect.width() * .36, rect.top() + rect.height() * .70),
        QPointF(rect.left() + rect.width() * .58, rect.top() + rect.height() * .49),
        QPointF(rect.left() + rect.width() * .76, rect.top() + rect.height() * .66),
        QPointF(rect.right() + 2, rect.top() + rect.height() * .56),
        QPointF(rect.right() + 2, rect.bottom() + 2),
    ]))
    painter.setBrush(QColor(48, 51, 42, 218))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left() - 2, rect.bottom()),
        QPointF(rect.left() + rect.width() * .28, rect.top() + rect.height() * .76),
        QPointF(rect.left() + rect.width() * .50, rect.top() + rect.height() * .82),
        QPointF(rect.left() + rect.width() * .73, rect.top() + rect.height() * .69),
        QPointF(rect.right() + 2, rect.top() + rect.height() * .76),
        QPointF(rect.right() + 2, rect.bottom() + 2),
    ]))
    painter.restore()


def _paint_kisah_kita(painter: QPainter, rect: QRectF) -> None:
    """Add a warm sunset, tree and couple silhouettes to Kisah Kita."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    painter.setPen(Qt.PenStyle.NoPen)

    painter.fillRect(rect, QColor(232, 143, 80, 45))
    sun = min(rect.width(), rect.height()) * 0.18
    painter.setBrush(QColor(255, 211, 124, 215))
    painter.drawEllipse(QRectF(
        rect.left() + rect.width() * 0.20,
        rect.top() + rect.height() * 0.46,
        sun,
        sun,
    ))

    # Sparse tree on the left.
    painter.setPen(QPen(QColor(30, 35, 30, 225), max(1.0, rect.width() * .010)))
    trunk_x = rect.left() + rect.width() * 0.10
    painter.drawLine(QPointF(trunk_x, rect.bottom()), QPointF(trunk_x + rect.width() * .02, rect.top() + rect.height() * .48))
    painter.drawLine(QPointF(trunk_x + rect.width() * .01, rect.top() + rect.height() * .62), QPointF(trunk_x - rect.width() * .07, rect.top() + rect.height() * .48))
    painter.drawLine(QPointF(trunk_x + rect.width() * .015, rect.top() + rect.height() * .58), QPointF(trunk_x + rect.width() * .08, rect.top() + rect.height() * .44))

    # Two simple human silhouettes at the right.
    painter.setPen(Qt.PenStyle.NoPen)
    for cx, scale in ((0.70, 1.0), (0.80, 0.93)):
        head = min(rect.width(), rect.height()) * 0.10 * scale
        x = rect.left() + rect.width() * cx
        y = rect.top() + rect.height() * 0.40
        painter.setBrush(QColor(25, 28, 27, 235))
        painter.drawEllipse(QRectF(x - head / 2, y - head / 2, head, head))
        body = QPainterPath()
        body.moveTo(x - head * .42, y + head * .45)
        body.lineTo(x + head * .42, y + head * .45)
        body.lineTo(x + head * .82, rect.bottom() + 2)
        body.lineTo(x - head * .86, rect.bottom() + 2)
        body.closeSubpath()
        painter.drawPath(body)
    painter.restore()


def _paint_album_kenangan(painter: QPainter, rect: QRectF) -> None:
    """Paint overlapping Polaroid cards to match the family-album reference."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillRect(rect, QColor(181, 151, 116, 32))

    def polaroid(cx: float, cy: float, angle: float, picture: QColor, accent: QColor) -> None:
        painter.save()
        painter.translate(QPointF(cx, cy))
        painter.rotate(angle)
        w = rect.width() * 0.25
        h = rect.height() * 0.58
        card = QRectF(-w / 2, -h / 2, w, h)
        painter.setBrush(QColor(249, 246, 235, 245))
        painter.drawRoundedRect(card, 1.5, 1.5)
        photo = card.adjusted(w * .10, h * .08, -w * .10, -h * .25)
        painter.setBrush(picture)
        painter.drawRect(photo)
        # Tiny people/photo cues.
        painter.setBrush(accent)
        radius = max(2.0, min(photo.width(), photo.height()) * .15)
        painter.drawEllipse(QRectF(photo.center().x() - radius * 1.2, photo.center().y() - radius * .7, radius, radius))
        painter.drawEllipse(QRectF(photo.center().x() + radius * .2, photo.center().y() - radius * .9, radius, radius))
        painter.restore()

    base_y = rect.top() + rect.height() * .53
    polaroid(rect.left() + rect.width() * .39, base_y, -8.0, QColor("#7C8F78"), QColor("#3E382F"))
    polaroid(rect.left() + rect.width() * .54, base_y - rect.height() * .04, 4.0, QColor("#B57B54"), QColor("#3A2A25"))
    polaroid(rect.left() + rect.width() * .68, base_y, 8.0, QColor("#607B88"), QColor("#262B2E"))
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
        elif template_id == "vinyl_nostalgia":
            _paint_cerita_baru(painter, rect)
        elif template_id == "neon_spectrum":
            _paint_kisah_kita(painter, rect)
        elif template_id == "romantic_bokeh":
            _paint_album_kenangan(painter, rect)
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
