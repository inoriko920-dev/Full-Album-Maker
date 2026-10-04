from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .foundation_tokens import TOKENS
from .render_center_model_step10 import RenderMetrics


class RenderPerformanceGraph(QWidget):
    """UI-only graph for metrics already reported by the render engine.

    The widget never estimates progress and never changes RenderJob state. It
    only visualizes the latest FFmpeg metrics, so this post-release fidelity
    work cannot alter render semantics.
    """

    def __init__(self, parent=None, *, max_points: int = 90) -> None:
        super().__init__(parent)
        self.setObjectName("renderPerformanceGraph")
        self.setMinimumHeight(104)
        self.setMaximumHeight(116)
        self._points: deque[RenderMetrics] = deque(maxlen=max(8, int(max_points)))

    def clear(self) -> None:
        self._points.clear()
        self.update()

    def append_metrics(self, metrics: RenderMetrics) -> None:
        metrics.validate()
        self._points.append(metrics)
        self.update()

    @property
    def point_count(self) -> int:
        return len(self._points)

    @staticmethod
    def _format_eta(seconds: float | None) -> str:
        if seconds is None:
            return "—"
        value = max(0, int(round(seconds)))
        if value >= 60:
            minutes = max(1, int(round(value / 60.0)))
            return f"{minutes} menit"
        return f"{value} dtk"

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(TOKENS.surface))

        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.setBrush(QColor(TOKENS.surface))
        painter.drawRoundedRect(outer, 7, 7)

        title_rect = QRectF(12, 5, max(1.0, outer.width() - 24), 19)
        painter.setPen(QColor(TOKENS.text_primary))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Performa Render (Saat Ini)")
        font.setBold(False)
        painter.setFont(font)

        if not self._points:
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(outer.adjusted(12, 26, -12, -8), Qt.AlignmentFlag.AlignCenter, "Menunggu metric render…")
            painter.end()
            return

        stats_width = min(236.0, max(198.0, outer.width() * 0.27))
        chart = QRectF(12, 29, max(120.0, outer.width() - stats_width - 28), max(52.0, outer.height() - 39))
        stats = QRectF(chart.right() + 9, chart.top(), stats_width, chart.height())

        # Light guide lines matching the immutable UI-09 chart rhythm.
        painter.setPen(QPen(QColor("#E3EAF4"), 1, Qt.PenStyle.DotLine))
        for ratio in (0.0, 0.5, 1.0):
            y = chart.bottom() - ratio * chart.height()
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
        painter.setPen(QColor(TOKENS.text_muted))
        painter.drawText(QRectF(chart.left(), chart.top() - 1, 42, 15), Qt.AlignmentFlag.AlignLeft, "200 fps")
        painter.drawText(QRectF(chart.left(), chart.center().y() - 7, 42, 15), Qt.AlignmentFlag.AlignLeft, "100 fps")
        painter.drawText(QRectF(chart.left(), chart.bottom() - 14, 42, 15), Qt.AlignmentFlag.AlignLeft, "0")

        plot = chart.adjusted(50, 2, -2, -2)
        values = [max(0.0, min(200.0, float(item.fps or 0.0))) for item in self._points]
        count = len(values)
        points: list[QPointF] = []
        for index, value in enumerate(values):
            x = plot.left() + (index / max(1, count - 1)) * plot.width()
            y = plot.bottom() - (value / 200.0) * plot.height()
            points.append(QPointF(x, y))

        if points:
            fill = QPainterPath()
            fill.moveTo(points[0].x(), plot.bottom())
            fill.lineTo(points[0])
            for point in points[1:]:
                fill.lineTo(point)
            fill.lineTo(points[-1].x(), plot.bottom())
            fill.closeSubpath()
            painter.fillPath(fill, QColor("#DCEBFF"))

            line = QPainterPath(points[0])
            for point in points[1:]:
                line.lineTo(point)
            painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
            painter.drawPath(line)

        latest = self._points[-1]
        fps = "—" if latest.fps is None else f"{latest.fps:.0f} fps"
        average = "—" if latest.average_fps is None else f"{latest.average_fps:.0f} fps"
        eta = self._format_eta(latest.eta_seconds)
        cards = (("Kecepatan", fps), ("Rata-rata", average), ("Sisa waktu", eta))
        gap = 6.0
        card_w = (stats.width() - gap * 2) / 3
        for index, (label, value) in enumerate(cards):
            card = QRectF(stats.left() + index * (card_w + gap), stats.top(), card_w, stats.height())
            painter.setPen(QPen(QColor(TOKENS.border), 1))
            painter.setBrush(QColor("#F7FAFE"))
            painter.drawRoundedRect(card, 5, 5)
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(card.adjusted(7, 5, -5, -24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)
            value_font = painter.font()
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(card.adjusted(7, 23, -5, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)
            value_font.setBold(False)
            painter.setFont(value_font)

        painter.end()
