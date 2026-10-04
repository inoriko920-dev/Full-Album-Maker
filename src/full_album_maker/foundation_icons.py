from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from .foundation_tokens import TOKENS


def foundation_icon(name: str, *, color: str | None = None, size: int = 22) -> QIcon:
    """Small self-drawn line icon family: no Unicode/font-icon dependency."""
    color = color or TOKENS.text_primary
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.4, size / 12.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m, c = size * 0.18, size / 2
    x0, y0, x1, y1 = m, m, size - m, size - m

    if name == "home":
        p.drawPolyline(QPolygonF([QPointF(x0, c), QPointF(c, y0), QPointF(x1, c)]))
        p.drawRoundedRect(QRectF(x0 + 2, c - 1, x1 - x0 - 4, y1 - c + 1), 2, 2)
    elif name in {"media", "visual"}:
        p.drawRoundedRect(QRectF(x0, y0, x1 - x0, y1 - y0), 2, 2)
        p.drawEllipse(QPointF(x1 - size * .18, y0 + size * .18), size * .05, size * .05)
        p.drawPolyline(QPolygonF([QPointF(x0 + 2, y1 - 3), QPointF(c - 1, c), QPointF(x1 - 2, c - 2)]))
    elif name == "album":
        p.drawLine(QPointF(c, y0), QPointF(c, y1 - size * .18))
        p.drawLine(QPointF(c, y0), QPointF(x1, y0 - 1))
        p.drawEllipse(QPointF(c - size * .12, y1 - size * .10), size * .12, size * .09)
    elif name == "timeline":
        p.drawRoundedRect(QRectF(x0, y0, x1 - x0, y1 - y0), 2, 2)
        for yy in (y0 + size * .2, y1 - size * .2): p.drawLine(QPointF(x0, yy), QPointF(x1, yy))
        for xx in (x0 + size * .18, x1 - size * .18): p.drawLine(QPointF(xx, y0), QPointF(xx, y1))
    elif name == "template":
        d = size * .24
        for xx in (x0, c + size * .03):
            for yy in (y0, c + size * .03): p.drawRoundedRect(QRectF(xx, yy, d, d), 1.5, 1.5)
    elif name == "spectrum":
        for i, h in enumerate((.3, .55, .8, .5, .65)):
            xx = x0 + i * (x1 - x0) / 4; p.drawLine(QPointF(xx, y1), QPointF(xx, y1 - size * h * .65))
    elif name == "ai_agent" or name == "ai":
        p.drawRoundedRect(QRectF(x0, c - size * .18, x1 - x0, size * .38), 3, 3)
        p.drawEllipse(QPointF(c - size * .14, c), size * .035, size * .035)
        p.drawEllipse(QPointF(c + size * .14, c), size * .035, size * .035)
        p.drawLine(QPointF(c, c - size * .18), QPointF(c, y0))
    elif name in {"render", "import"}:
        up = name == "render"; tip = y0 if up else y1; wing = tip + (size * .18 if up else -size * .18)
        p.drawLine(QPointF(c, c), QPointF(c, tip)); p.drawLine(QPointF(c, tip), QPointF(c - size * .14, wing)); p.drawLine(QPointF(c, tip), QPointF(c + size * .14, wing))
        p.drawPolyline(QPolygonF([QPointF(x0, c), QPointF(x0, y1), QPointF(x1, y1), QPointF(x1, c)]))
    elif name == "new":
        p.drawEllipse(QRectF(x0, y0, x1 - x0, y1 - y0)); p.drawLine(QPointF(c, y0 + 3), QPointF(c, y1 - 3)); p.drawLine(QPointF(x0 + 3, c), QPointF(x1 - 3, c))
    elif name == "open":
        path = QPainterPath(); path.moveTo(x0, c); path.lineTo(x0 + size*.15, c); path.lineTo(x0+size*.25,y0); path.lineTo(c+size*.06,y0); path.lineTo(c+size*.14,c); path.lineTo(x1,c); path.lineTo(x1-size*.10,y1); path.lineTo(x0+size*.05,y1); path.closeSubpath(); p.drawPath(path)
    elif name == "save":
        p.drawRoundedRect(QRectF(x0,y0,x1-x0,y1-y0),1.5,1.5); p.drawRect(QRectF(x0+size*.15,y0,size*.28,size*.20)); p.drawRoundedRect(QRectF(x0+size*.15,c+1,x1-x0-size*.30,size*.23),1,1)
    elif name in {"undo", "redo"}:
        flip = -1 if name == "undo" else 1; p.drawArc(QRectF(x0,y0+2,x1-x0,y1-y0-2), (30 if flip < 0 else 150)*16, 230*16*flip)
    elif name == "auto":
        for yy in (y0+2,c,y1-2): p.drawLine(QPointF(x0,yy),QPointF(x1,yy))
    elif name == "preview":
        p.drawPolygon(QPolygonF([QPointF(x0+2,y0),QPointF(x1,c),QPointF(x0+2,y1)]))
    elif name in {"properties", "settings"}:
        p.drawEllipse(QPointF(c,c),size*.12,size*.12); p.drawEllipse(QPointF(c,c),size*.30,size*.30)
        for a in range(0,360,90):
            r=math.radians(a); p.drawLine(QPointF(c+math.cos(r)*size*.30,c+math.sin(r)*size*.30),QPointF(c+math.cos(r)*size*.40,c+math.sin(r)*size*.40))
    elif name in {"collapse", "expand"}:
        dy = -size*.08 if name == "collapse" else size*.08; p.drawPolyline(QPolygonF([QPointF(x0,c+dy),QPointF(c,c-dy),QPointF(x1,c+dy)]))
    elif name in {"zoom_in", "zoom_out"}:
        p.drawEllipse(QRectF(x0,y0,size*.42,size*.42)); p.drawLine(QPointF(c,c),QPointF(x1,y1)); p.drawLine(QPointF(x0+size*.13,y0+size*.21),QPointF(x0+size*.29,y0+size*.21))
        if name == "zoom_in": p.drawLine(QPointF(x0+size*.21,y0+size*.13),QPointF(x0+size*.21,y0+size*.29))
    else:
        p.drawRoundedRect(QRectF(x0, y0, x1-x0, y1-y0), 3, 3)
    p.end()
    return QIcon(pix)
