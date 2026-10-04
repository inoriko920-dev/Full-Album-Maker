from __future__ import annotations

"""Small scene-detail refinement for the selected Spotify-clean fallback.

The approved UI-06 reference uses a sunset portrait composition for the selected
"Senja di Kota Ini" card and inspector preview.  This layer adds only a simple
vector silhouette to the deterministic fallback painter.  Real cached/rendered
thumbnail pixmaps are never changed and no template/domain behavior is touched.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPolygonF

_installed = False


def _paint_subject(painter: QPainter, rect: QRectF) -> None:
    """Paint an abstract right-side portrait silhouette within *rect*."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipRect(rect)

    # Head/hair mass near the right third, matching the selected-template scene
    # without embedding or tracing the golden bitmap.
    head_size = min(rect.width(), rect.height()) * 0.24
    cx = rect.left() + rect.width() * 0.77
    cy = rect.top() + rect.height() * 0.37
    hair = QColor(20, 22, 30, 205)
    face = QColor(92, 61, 54, 205)
    body = QColor(25, 31, 43, 215)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(hair)
    painter.drawEllipse(QRectF(cx - head_size * 0.54, cy - head_size * 0.58, head_size, head_size * 1.08))

    # A small profile wedge leaves a readable face edge toward the left.
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

    # Shoulder/body shape extends to the lower-right edge.
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
        if str(getattr(self, "template_id", "")) != "spotify_clean":
            return
        if pixmap is not None and not pixmap.isNull():
            return
        painter = QPainter(self)
        _paint_subject(painter, QRectF(self.rect()).adjusted(5, 5, -5, -5))
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
