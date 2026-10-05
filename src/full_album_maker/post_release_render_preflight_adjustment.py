from __future__ import annotations

"""Presentation-only geometry tuning for the UI-09 preflight surface.

This module only changes the visual chrome around existing preflight cards. The
STEP10 report, PASS/WARN/BLOCK result, messages, snapshot and render decisions
remain owned by the original render domain layer.
"""

import math
from types import MethodType

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .render_preflight_step10 import PreflightLevel

_installed = False


def _line_pixmap(kind: str, color: str = "#1766E8", size: int = 30) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.7, size / 13.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * .16
    x0, y0, x1, y1 = m, m, size - m, size - m

    if kind == "media":
        path = QPainterPath()
        path.moveTo(x0 + 2, y0)
        path.lineTo(x1 - size * .20, y0)
        path.lineTo(x1, y0 + size * .20)
        path.lineTo(x1, y1)
        path.lineTo(x0 + 2, y1)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(x1 - size * .20, y0), QPointF(x1 - size * .20, y0 + size * .20))
        p.drawLine(QPointF(x1 - size * .20, y0 + size * .20), QPointF(x1, y0 + size * .20))
    elif kind == "timeline":
        for yy in (size * .30, size * .50, size * .70):
            p.drawEllipse(QPointF(size * .22, yy), size * .025, size * .025)
            p.drawLine(QPointF(size * .34, yy), QPointF(size * .82, yy))
    elif kind == "ffmpeg":
        body = QRectF(size * .24, size * .24, size * .52, size * .52)
        p.drawRoundedRect(body, 3, 3)
        p.drawRoundedRect(QRectF(size * .36, size * .36, size * .28, size * .28), 2, 2)
        for v in (.31, .44, .57, .70):
            p.drawLine(QPointF(size * v, size * .10), QPointF(size * v, size * .22))
            p.drawLine(QPointF(size * v, size * .78), QPointF(size * v, size * .90))
            p.drawLine(QPointF(size * .10, size * v), QPointF(size * .22, size * v))
            p.drawLine(QPointF(size * .78, size * v), QPointF(size * .90, size * v))
    elif kind == "output":
        path = QPainterPath()
        path.moveTo(x0, size * .34)
        path.lineTo(size * .42, size * .34)
        path.lineTo(size * .49, size * .26)
        path.lineTo(x1, size * .26)
        path.lineTo(x1, y1)
        path.lineTo(x0, y1)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(x0, size * .40), QPointF(x1, size * .40))
    elif kind == "disk":
        path = QPainterPath()
        path.moveTo(size * .27, size * .20)
        path.lineTo(size * .73, size * .20)
        path.lineTo(size * .82, size * .80)
        path.lineTo(size * .18, size * .80)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(size * .25, size * .58), QPointF(size * .75, size * .58))
        p.drawEllipse(QPointF(size * .68, size * .69), size * .025, size * .025)
    p.end()
    return pix


def _status_pixmap(level: PreflightLevel | None, size: int = 29) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if level == PreflightLevel.WARN:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F59E0B"))
        path = QPainterPath()
        path.moveTo(size * .50, size * .10)
        path.lineTo(size * .90, size * .84)
        path.quadTo(size * .92, size * .90, size * .82, size * .90)
        path.lineTo(size * .18, size * .90)
        path.quadTo(size * .08, size * .90, size * .10, size * .84)
        path.closeSubpath()
        p.drawPath(path)
        pen = QPen(QColor("#FFFFFF"), max(1.8, size / 12))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(size * .50, size * .35), QPointF(size * .50, size * .61))
        p.drawPoint(QPointF(size * .50, size * .73))
    elif level == PreflightLevel.BLOCK:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E14949"))
        p.drawEllipse(QRectF(size * .08, size * .08, size * .84, size * .84))
        pen = QPen(QColor("#FFFFFF"), max(2.0, size / 11))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(size * .34, size * .34), QPointF(size * .66, size * .66))
        p.drawLine(QPointF(size * .66, size * .34), QPointF(size * .34, size * .66))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1FAF5A") if level == PreflightLevel.PASS else QColor("#C7D2E2"))
        p.drawEllipse(QRectF(size * .08, size * .08, size * .84, size * .84))
        if level == PreflightLevel.PASS:
            pen = QPen(QColor("#FFFFFF"), max(2.0, size / 11))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPointF(size * .31, size * .51), QPointF(size * .44, size * .65))
            p.drawLine(QPointF(size * .44, size * .65), QPointF(size * .70, size * .35))
    p.end()
    return pix


def _clean_state_text(text: str) -> str:
    value = str(text or "").strip()
    for prefix in ("✓", "⚠", "✕"):
        value = value.removeprefix(prefix).strip()
    return value


def _decorate_preflight(window) -> None:
    workspace = window.render_workspace_s10
    if getattr(workspace, "_pixel_preflight_adjusted", False):
        return
    workspace._pixel_preflight_adjusted = True

    heading = next(
        (label for label in workspace.findChildren(QLabel) if label.text() == "Hasil Preflight"),
        None,
    )
    if heading is not None:
        host = heading.parentWidget()
        if host is not None:
            host.setMinimumHeight(55)
            host.setMaximumHeight(55)
            layout = host.layout()
            if layout is not None:
                layout.setContentsMargins(4, 0, 4, 0)
                layout.setSpacing(0)

    for key in ("media", "snapshot", "ffmpeg", "output", "disk"):
        card = workspace.preflight_cards[key]
        card.setMinimumHeight(166)
        card.setMaximumHeight(166)
        layout = card.layout()
        if layout is None:
            continue
        layout.setContentsMargins(12, 12, 10, 10)
        layout.setSpacing(6)
        card.title.setContentsMargins(37, 0, 0, 0)
        card.title.setMinimumHeight(30)
        card.state.setStyleSheet(card.state.styleSheet() + "font-size:15px;font-weight:700;")

        title_icon = QLabel(card)
        title_icon.setPixmap(_line_pixmap(key))
        title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_icon.setGeometry(11, 12, 31, 31)
        title_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_icon.show()
        title_icon.raise_()
        card._pixel_title_icon = title_icon

        state_index = layout.indexOf(card.state)
        if state_index >= 0:
            layout.removeWidget(card.state)
            state_host = QWidget(card)
            state_row = QHBoxLayout(state_host)
            state_row.setContentsMargins(0, 0, 0, 0)
            state_row.setSpacing(7)
            state_icon = QLabel(state_host)
            state_icon.setFixedSize(29, 29)
            state_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            state_row.addWidget(state_icon)
            state_row.addWidget(card.state)
            state_row.addStretch(1)
            layout.insertWidget(state_index, state_host)
            card._pixel_state_icon = state_icon
            card._pixel_state_host = state_host

            original_set_check = card.set_check

            def set_check_with_visual(self, level, detail, _orig=original_set_check, _icon=state_icon) -> None:
                _orig(level, detail)
                self.state.setText(_clean_state_text(self.state.text()))
                _icon.setPixmap(_status_pixmap(level))

            card.set_check = MethodType(set_check_with_visual, card)

            # Route decoration can run after an initial deterministic preflight.
            # Preserve that already-rendered state immediately.
            current = card.state.text()
            if "WARN" in current:
                level = PreflightLevel.WARN
            elif "BLOCK" in current:
                level = PreflightLevel.BLOCK
            elif "PASS" in current:
                level = PreflightLevel.PASS
            else:
                level = None
            card.state.setText(_clean_state_text(current))
            state_icon.setPixmap(_status_pixmap(level))


def install_post_release_render_preflight_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_preflight_alignment(self, route: str) -> None:
        original_route(self, route)
        if route == "render":
            _decorate_preflight(self)

    Window._s10_route = route_with_preflight_alignment
    _installed = True
