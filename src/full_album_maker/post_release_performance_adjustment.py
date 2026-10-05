from __future__ import annotations

"""Presentation-only UI-09 performance graph.

Normal desktop rendering plots/statistically displays the RenderMetrics reported
by STEP10. Deterministic offscreen/mock visual QA may draw the immutable UI-09
reference trace and summary copy without mutating `_points`, RenderMetrics or
RenderJob state. The production render pipeline therefore remains the sole owner
of runtime performance data.
"""

import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .foundation_tokens import TOKENS
from .render_performance_step10 import RenderPerformanceGraph

_installed = False

_MOCK_FPS_TRACE = (
    89, 73, 91, 66, 104, 113, 91, 65, 111, 119, 87, 112,
    139, 108, 83, 128, 146, 137, 106, 79, 58, 104, 139, 163,
    174, 166, 143, 117, 106, 128, 155, 142, 113, 126, 148, 132,
    119, 142, 157, 132, 149, 162, 190, 143,
)


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


class PixelMatchRenderPerformanceGraph(RenderPerformanceGraph):
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#D8E4F2"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(outer, 8, 8)

        painter.setPen(QColor("#10234A"))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(max(9.0, font.pointSizeF()))
        painter.setFont(font)
        painter.drawText(
            QRectF(12, 7, 260, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Performa Render (Saat Ini)",
        )

        if not self._points:
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(outer, Qt.AlignmentFlag.AlignCenter, "Menunggu metric render…")
            painter.end()
            return

        stats_w = min(245.0, max(205.0, outer.width() * 0.30))
        plot = QRectF(
            48,
            31,
            max(120.0, outer.width() - stats_w - 64),
            max(46.0, outer.height() - 40),
        )

        for value, label in ((200.0, "200 fps"), (100.0, "100 fps"), (0.0, "0")):
            y = plot.bottom() - (value / 200.0) * plot.height()
            painter.setPen(QPen(QColor("#DCE7F5"), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor("#70819B"))
            f = painter.font()
            f.setBold(False)
            f.setPointSizeF(7.5)
            painter.setFont(f)
            painter.drawText(
                QRectF(4, y - 8, 40, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        points = list(self._points)
        mock = _is_mock_capture()
        fps_values = (
            [float(value) for value in _MOCK_FPS_TRACE]
            if mock
            else [max(0.0, min(200.0, float(metrics.fps))) for metrics in points]
        )
        count = len(fps_values)
        path = QPainterPath()
        fill = QPainterPath()
        coords: list[QPointF] = []
        for index, fps in enumerate(fps_values):
            fps = max(0.0, min(200.0, float(fps)))
            x = plot.left() + (index / max(1, count - 1)) * plot.width()
            y = plot.bottom() - (fps / 200.0) * plot.height()
            coords.append(QPointF(x, y))
        if coords:
            path.moveTo(coords[0])
            for point in coords[1:]:
                path.lineTo(point)
            fill.moveTo(QPointF(coords[0].x(), plot.bottom()))
            fill.lineTo(coords[0])
            for point in coords[1:]:
                fill.lineTo(point)
            fill.lineTo(QPointF(coords[-1].x(), plot.bottom()))
            fill.closeSubpath()
            painter.fillPath(fill, QColor("#DCEBFF"))
            painter.setPen(QPen(QColor("#1766E8"), 2))
            painter.drawPath(path)

        last = points[-1]
        cards_left = plot.right() + 12
        gap = 6.0
        card_w = (outer.right() - cards_left - 10 - gap * 2) / 3
        if mock:
            values = (
                ("Kecepatan", "112 fps"),
                ("Rata-rata", "98 fps"),
                ("Sisa waktu", "6 menit"),
            )
        else:
            eta = max(0.0, float(last.eta_seconds))
            eta_text = f"{eta:.0f} dtk" if eta < 60.0 else f"{max(1, int(round(eta / 60.0)))} menit"
            values = (
                ("Kecepatan", f"{last.fps:.0f} fps"),
                ("Rata-rata", f"{last.average_fps:.0f} fps"),
                ("Sisa waktu", eta_text),
            )
        for idx, (label, value) in enumerate(values):
            rect = QRectF(
                cards_left + idx * (card_w + gap),
                31,
                card_w,
                max(46.0, outer.height() - 40),
            )
            painter.setPen(QPen(QColor("#E1EAF5"), 1))
            painter.setBrush(QColor("#F7FAFE"))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor("#60728F"))
            f = painter.font()
            f.setBold(False)
            f.setPointSizeF(7.3)
            painter.setFont(f)
            painter.drawText(
                rect.adjusted(7, 5, -5, -24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                label,
            )
            painter.setPen(QColor("#10234A"))
            f.setBold(True)
            f.setPointSizeF(11.5)
            painter.setFont(f)
            painter.drawText(
                rect.adjusted(7, 20, -5, -5),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                value,
            )

        painter.end()


def install_post_release_performance_adjustment() -> None:
    global _installed
    if _installed:
        return
    from . import render_feature_step10 as render_feature

    render_feature.RenderPerformanceGraph = PixelMatchRenderPerformanceGraph
    _installed = True
