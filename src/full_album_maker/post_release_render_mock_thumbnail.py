from __future__ import annotations

"""Deterministic vector thumbnails used only by post-release Render presentation.

No external image assets are needed.  The scenes are intentionally lightweight
and generic; they provide the same visual read as the immutable UI-09 reference
while remaining resolution-independent and safe for offscreen CI capture.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame


class RenderMockThumbnail(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = str(title or "")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setClipPath(self._rounded_clip(rect))
        key = self.title.casefold()
        if "jalan pulang" in key:
            self._paint_mountains(painter, rect)
        elif "perjalanan" in key:
            self._paint_van(painter, rect)
        elif "cerita baru" in key:
            self._paint_city(painter, rect)
        else:
            self._paint_sunset_portrait(painter, rect)
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#B9C9DC"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 5, 5)
        painter.end()

    @staticmethod
    def _rounded_clip(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(rect, 5, 5)
        return path

    @staticmethod
    def _gradient(rect: QRectF, top: str, middle: str, bottom: str) -> QLinearGradient:
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(top))
        gradient.setColorAt(.58, QColor(middle))
        gradient.setColorAt(1.0, QColor(bottom))
        return gradient

    def _paint_sunset_portrait(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._gradient(rect, "#405777", "#E99563", "#E8B56F"))
        # distant water / haze
        horizon = rect.top() + rect.height() * .67
        painter.fillRect(QRectF(rect.left(), horizon, rect.width(), rect.bottom() - horizon), QColor("#5C5360"))
        # sun
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 198, 117, 220))
        radius = max(2.0, rect.height() * .09)
        painter.drawEllipse(QPointF(rect.left() + rect.width() * .27, horizon - rect.height() * .13), radius, radius)
        # foreground shoulder/head silhouette on the right
        dark = QColor("#202939")
        painter.setBrush(dark)
        head_r = rect.height() * .115
        head = QPointF(rect.left() + rect.width() * .67, rect.top() + rect.height() * .43)
        painter.drawEllipse(head, head_r, head_r * 1.05)
        hair = QPainterPath()
        hair.moveTo(head.x() - head_r * .65, head.y() - head_r * .6)
        hair.cubicTo(
            head.x() - head_r * 1.2, head.y() + head_r * .7,
            head.x() - head_r * .55, head.y() + head_r * 2.2,
            head.x() - head_r * .2, head.y() + head_r * 2.7,
        )
        hair.lineTo(head.x() + head_r * .45, head.y() + head_r * 2.6)
        hair.lineTo(head.x() + head_r * .7, head.y() + head_r * .2)
        hair.closeSubpath()
        painter.drawPath(hair)
        shoulder = QPolygonF([
            QPointF(rect.left() + rect.width() * .48, rect.bottom()),
            QPointF(rect.left() + rect.width() * .57, rect.top() + rect.height() * .66),
            QPointF(rect.left() + rect.width() * .78, rect.top() + rect.height() * .63),
            QPointF(rect.left() + rect.width() * .92, rect.bottom()),
        ])
        painter.drawPolygon(shoulder)

    def _paint_mountains(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._gradient(rect, "#5C91B4", "#9EC7D0", "#54706B"))
        painter.setPen(Qt.PenStyle.NoPen)
        back = QColor("#31556C")
        painter.setBrush(back)
        painter.drawPolygon(QPolygonF([
            QPointF(rect.left(), rect.top() + rect.height() * .63),
            QPointF(rect.left() + rect.width() * .24, rect.top() + rect.height() * .32),
            QPointF(rect.left() + rect.width() * .48, rect.top() + rect.height() * .63),
            QPointF(rect.left() + rect.width() * .69, rect.top() + rect.height() * .38),
            QPointF(rect.right(), rect.top() + rect.height() * .70),
            QPointF(rect.right(), rect.bottom()),
            QPointF(rect.left(), rect.bottom()),
        ]))
        painter.setBrush(QColor("#203F45"))
        painter.drawPolygon(QPolygonF([
            QPointF(rect.left(), rect.top() + rect.height() * .73),
            QPointF(rect.left() + rect.width() * .25, rect.top() + rect.height() * .55),
            QPointF(rect.left() + rect.width() * .53, rect.top() + rect.height() * .78),
            QPointF(rect.left() + rect.width() * .78, rect.top() + rect.height() * .58),
            QPointF(rect.right(), rect.top() + rect.height() * .72),
            QPointF(rect.right(), rect.bottom()),
            QPointF(rect.left(), rect.bottom()),
        ]))
        # pale winding road
        road = QPainterPath()
        road.moveTo(rect.left() + rect.width() * .46, rect.bottom())
        road.cubicTo(
            rect.left() + rect.width() * .51, rect.top() + rect.height() * .82,
            rect.left() + rect.width() * .66, rect.top() + rect.height() * .73,
            rect.left() + rect.width() * .61, rect.top() + rect.height() * .63,
        )
        painter.setPen(QPen(QColor("#D5D8C8"), max(1.5, rect.height() * .055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(road)

    def _paint_van(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._gradient(rect, "#537044", "#8BA66E", "#53623B"))
        painter.setPen(Qt.PenStyle.NoPen)
        # loose foliage blobs
        for px, py, radius, color in (
            (.10,.28,.20,"#355B37"), (.29,.16,.17,"#416843"), (.76,.18,.22,"#385D36"),
            (.91,.37,.19,"#2C5130"), (.16,.70,.20,"#627847"), (.80,.72,.21,"#566C3E"),
        ):
            painter.setBrush(QColor(color))
            r = rect.height() * radius
            painter.drawEllipse(QPointF(rect.left()+rect.width()*px, rect.top()+rect.height()*py), r, r)
        # dirt track
        painter.setBrush(QColor("#B9A56F"))
        painter.drawPolygon(QPolygonF([
            QPointF(rect.left()+rect.width()*.35, rect.bottom()),
            QPointF(rect.left()+rect.width()*.47, rect.top()+rect.height()*.55),
            QPointF(rect.left()+rect.width()*.61, rect.top()+rect.height()*.55),
            QPointF(rect.left()+rect.width()*.77, rect.bottom()),
        ]))
        # compact camper van
        body = QRectF(
            rect.left()+rect.width()*.34,
            rect.top()+rect.height()*.46,
            rect.width()*.35,
            rect.height()*.30,
        )
        painter.setBrush(QColor("#EFE9D5"))
        painter.drawRoundedRect(body, 2.5, 2.5)
        painter.setBrush(QColor("#73939A"))
        painter.drawRect(QRectF(body.left()+body.width()*.10, body.top()+body.height()*.16, body.width()*.25, body.height()*.34))
        painter.drawRect(QRectF(body.left()+body.width()*.43, body.top()+body.height()*.16, body.width()*.30, body.height()*.34))
        painter.setBrush(QColor("#25343B"))
        wheel_r = max(1.5, rect.height()*.045)
        painter.drawEllipse(QPointF(body.left()+body.width()*.23, body.bottom()), wheel_r, wheel_r)
        painter.drawEllipse(QPointF(body.left()+body.width()*.78, body.bottom()), wheel_r, wheel_r)

    def _paint_city(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._gradient(rect, "#687994", "#E6A16D", "#E6BE83"))
        painter.setPen(Qt.PenStyle.NoPen)
        base = rect.bottom()
        for x, w, h, color in (
            (.02,.15,.28,"#3A4652"), (.15,.12,.42,"#39434D"), (.28,.18,.31,"#4B4A48"),
            (.47,.10,.50,"#414652"), (.58,.18,.37,"#554A45"), (.76,.12,.46,"#3E4650"), (.88,.10,.30,"#49505A"),
        ):
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(rect.left()+rect.width()*x, base-rect.height()*h, rect.width()*w, rect.height()*h))
        painter.setBrush(QColor("#FFD488"))
        for x, y in ((.20,.72),(.34,.78),(.52,.64),(.67,.76),(.82,.66)):
            painter.drawRect(QRectF(rect.left()+rect.width()*x, rect.top()+rect.height()*y, 2.0, 1.4))
