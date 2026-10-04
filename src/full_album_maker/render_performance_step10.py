from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .foundation_tokens import TOKENS
from .render_center_model_step10 import RenderMetrics


class RenderPerformanceGraph(QWidget):
    """Lightweight UI-only graph for observed render metrics.

    The graph never estimates or drives render progress. It only visualizes
    values already reported by FFmpeg's progress protocol and therefore cannot
    alter RenderJob state or verification semantics.
    """

    def __init__(self, parent=None, *, max_points: int = 90) -> None:
        super().__init__(parent)
        self.setObjectName("renderPerformanceGraph")
        self.setMinimumHeight(82)
        self.setMaximumHeight(110)
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

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(TOKENS.surface))
        area = QRectF(self.rect()).adjusted(10, 9, -10, -15)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawRoundedRect(area, 7, 7)
        painter.setPen(QColor(TOKENS.text_muted))
        painter.drawText(area.adjusted(8, 2, -8, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "Performance • FFmpeg metrics")
        if len(self._points) < 2:
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Menunggu metric render…")
            painter.end()
            return

        plot = area.adjusted(8, 22, -8, -7)
        values = [max(0.0, min(100.0, item.percent)) for item in self._points]
        count = len(values)
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        previous = None
        for index, value in enumerate(values):
            x = plot.left() + (index / max(1, count - 1)) * plot.width()
            y = plot.bottom() - (value / 100.0) * plot.height()
            point = QPointF(x, y)
            if previous is not None:
                painter.drawLine(previous, point)
            previous = point
        painter.end()
