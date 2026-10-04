from __future__ import annotations

"""Presentation-only UI-06 template-card fidelity layer.

The real async thumbnail cache remains authoritative. While a thumbnail is not
available, cards paint a deterministic scene keyed by template_id instead of a
flat navy rectangle. Existing selection, favorite, preview and apply signals are
unchanged. Badge/favorite/ratio chrome is moved over the thumbnail to match the
compact gallery layout and to avoid wasting a full row below the image.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel

_installed = False

_PALETTES = {
    "spotify_clean": ("#243B61", "#D9855F", "#F4B36A"),
    "cafe_acoustic": ("#224E72", "#5B92B0", "#B8D5DD"),
    "viral_full_album": ("#315D52", "#6E9271", "#C5B879"),
    "vinyl_nostalgia": ("#9D552F", "#D78645", "#F4C16F"),
    "neon_spectrum": ("#4B332D", "#B05D3D", "#E7A86F"),
    "romantic_bokeh": ("#5B463C", "#9C765C", "#D4B89A"),
    "dark_cinematic": ("#1C4E83", "#4A8BC1", "#B7DAEF"),
    "photo_album": ("#8E765E", "#D4A86B", "#F2D9A8"),
    "cassette_retro": ("#6B4A52", "#A87466", "#D6B28C"),
    "music_channel_pro": ("#273451", "#5C6C91", "#9AA9C7"),
}


def _paint_fallback(widget, painter: QPainter, inner: QRectF) -> None:
    top, mid, bottom = _PALETTES.get(widget.template_id, ("#263B5C", "#607A9E", "#B4C6D8"))
    gradient = QLinearGradient(inner.topLeft(), inner.bottomLeft())
    gradient.setColorAt(0.0, QColor(top))
    gradient.setColorAt(0.55, QColor(mid))
    gradient.setColorAt(1.0, QColor(bottom))
    painter.fillRect(inner, gradient)

    tid = widget.template_id
    painter.save()
    painter.setClipRect(inner)
    if tid in {"spotify_clean", "vinyl_nostalgia", "neon_spectrum"}:
        sun = QColor("#FFD59A")
        sun.setAlpha(205)
        painter.setBrush(sun)
        painter.setPen(Qt.PenStyle.NoPen)
        size = min(inner.width(), inner.height()) * 0.33
        painter.drawEllipse(QRectF(inner.right() - size * 1.15, inner.top() + 9, size, size))
        painter.setBrush(QColor(22, 36, 48, 175))
        points = QPolygonF([
            QPointF(inner.left(), inner.bottom()),
            QPointF(inner.left() + inner.width() * .35, inner.top() + inner.height() * .58),
            QPointF(inner.left() + inner.width() * .57, inner.top() + inner.height() * .72),
            QPointF(inner.left() + inner.width() * .78, inner.top() + inner.height() * .54),
            QPointF(inner.right(), inner.bottom()),
        ])
        painter.drawPolygon(points)
    elif tid in {"cafe_acoustic", "viral_full_album", "dark_cinematic", "music_channel_pro"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 48, 68, 170))
        painter.drawPolygon(QPolygonF([
            QPointF(inner.left(), inner.bottom()),
            QPointF(inner.left() + inner.width() * .24, inner.top() + inner.height() * .45),
            QPointF(inner.left() + inner.width() * .43, inner.top() + inner.height() * .68),
            QPointF(inner.left() + inner.width() * .67, inner.top() + inner.height() * .32),
            QPointF(inner.right(), inner.bottom()),
        ]))
        painter.setBrush(QColor(42, 78, 76, 150))
        painter.drawPolygon(QPolygonF([
            QPointF(inner.left(), inner.bottom()),
            QPointF(inner.left() + inner.width() * .36, inner.top() + inner.height() * .66),
            QPointF(inner.left() + inner.width() * .72, inner.top() + inner.height() * .55),
            QPointF(inner.right(), inner.bottom()),
        ]))
    elif tid == "photo_album":
        painter.setPen(QPen(QColor(255, 248, 230, 150), 2))
        for offset in (0.68, 0.75, 0.82):
            y = inner.top() + inner.height() * offset
            painter.drawLine(int(inner.left()), int(y), int(inner.right()), int(y - 5))
    elif tid == "romantic_bokeh":
        painter.setPen(QPen(QColor(255, 245, 226, 160), 3))
        for xratio, yratio in ((.18,.28),(.42,.42),(.68,.24),(.82,.54)):
            r = min(inner.width(), inner.height()) * .14
            painter.drawEllipse(QRectF(inner.left()+inner.width()*xratio-r/2, inner.top()+inner.height()*yratio-r/2, r, r))
    painter.restore()

    shade = QColor(7, 19, 38, 92)
    painter.fillRect(inner, shade)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setBold(True)
    font.setPointSizeF(max(8.0, min(12.5, inner.width() / 17.0)))
    painter.setFont(font)
    painter.drawText(
        inner.adjusted(10, 20, -10, -8),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
        widget.name,
    )


def install_post_release_template_card_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateCard, TemplateThumbnailPlaceholder

    original_paint = TemplateThumbnailPlaceholder.paintEvent
    original_resize = TemplateThumbnailPlaceholder.resizeEvent
    original_card_init = TemplateCard.__init__

    def paint_rich_thumbnail(self, event) -> None:
        if not self._pixmap.isNull():
            original_paint(self, event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.fillRect(rect, QColor("#EAF3FF"))
        painter.setPen(QPen(QColor("#BFD6F4"), 1))
        painter.drawRoundedRect(rect, 7, 7)
        inner = rect.adjusted(4, 4, -4, -4)
        _paint_fallback(self, painter, inner)
        painter.end()

    def position_overlays(self) -> None:
        badge = getattr(self, "_post_template_badge", None)
        heart = getattr(self, "_post_template_heart", None)
        ratio = getattr(self, "_post_template_ratio", None)
        if badge is not None:
            badge.move(9, 8)
        if heart is not None:
            heart.move(max(8, self.width() - heart.width() - 8), 6)
        if ratio is not None:
            ratio.move(max(8, self.width() - ratio.width() - 8), max(8, self.height() - ratio.height() - 7))

    def resize_with_overlays(self, event) -> None:
        original_resize(self, event)
        position_overlays(self)

    def compact_card_init(self, descriptor, *args, **kwargs) -> None:
        original_card_init(self, descriptor, *args, **kwargs)
        root = self.layout()
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(3)
        self.setMinimumWidth(190)
        self.setMaximumWidth(300)
        self.thumbnail.setMinimumHeight(106)
        self.thumbnail.setMaximumHeight(112)

        top_item = root.itemAt(1)
        top_layout = top_item.layout() if top_item is not None else None
        badge = None
        if top_layout is not None:
            first = top_layout.itemAt(0)
            badge = first.widget() if first is not None else None
            if badge is not None:
                top_layout.removeWidget(badge)
            top_layout.removeWidget(self.heart)
            root.takeAt(1)

        if badge is not None:
            badge.setParent(self.thumbnail)
            badge.setStyleSheet("background:#1782F5;color:white;border-radius:8px;padding:2px 7px;font-size:10px;font-weight:700;")
            badge.adjustSize()
            self.thumbnail._post_template_badge = badge
            badge.show()

        self.heart.setParent(self.thumbnail)
        self.heart.setText("♥" if self._favorite else "♡")
        self.heart.setFixedSize(26, 26)
        self.heart.setStyleSheet("QPushButton{background:rgba(20,34,52,110);border:none;border-radius:13px;color:white;font-size:18px;}")
        self.thumbnail._post_template_heart = self.heart
        self.heart.show()

        ratio = QLabel(descriptor.ratios[0], self.thumbnail)
        ratio.setStyleSheet("background:rgba(10,20,34,165);color:white;border-radius:5px;padding:2px 5px;font-size:9px;")
        ratio.adjustSize()
        self.thumbnail._post_template_ratio = ratio
        ratio.show()
        position_overlays(self.thumbnail)

        self.preview.setMinimumHeight(29)
        self.use.setMinimumHeight(29)
        self.preview.setText("Preview")
        self.use.setText("▷  Gunakan")

    TemplateThumbnailPlaceholder.paintEvent = paint_rich_thumbnail
    TemplateThumbnailPlaceholder.resizeEvent = resize_with_overlays
    TemplateCard.__init__ = compact_card_init
    _installed = True
