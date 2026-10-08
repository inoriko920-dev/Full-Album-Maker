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
        """Plot observed FFmpeg percent and FPS only; never predict job state."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(TOKENS.surface))

        area = QRectF(self.rect()).adjusted(9, 6, -9, -7)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(area, 7, 7)

        title = area.adjusted(11, 2, -11, -2)
        painter.setPen(QColor("#25486F"))
        painter.drawText(
            title,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "Performa Render (Saat Ini)",
        )
        if len(self._points) < 2:
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(
                area,
                Qt.AlignmentFlag.AlignCenter,
                "Menunggu metrik FFmpeg…",
            )
            painter.end()
            return

        latest = self._points[-1]
        summary = f"Progres {latest.percent:.0f}%"
        if latest.fps is not None:
            summary += f"  •  {latest.fps:.0f} FPS"
        show_summary = area.width() >= 650
        if not show_summary:
            painter.setPen(QColor("#5B7598"))
            painter.drawText(
                title,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                summary,
            )

        # Desktop golden uses a chart plus three real telemetry columns.
        # Compact view remains a full-width chart; no extrapolated metrics.
        plot = QRectF(
            area.left() + 12,
            area.top() + 25,
            max(1.0, area.width() - (246 if show_summary else 24)),
            max(1.0, area.height() - 47),
        )
        for fraction in (0.25, 0.50, 0.75):
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(QPen(QColor("#E7EEF7"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        def draw_metrics(values, max_value: float, color: str) -> None:
            painter.setPen(QPen(QColor(color), 2))
            previous = None
            for index, value in enumerate(values):
                if value is None:
                    previous = None
                    continue
                x = plot.left() + index / max(1, len(values) - 1) * plot.width()
                y = plot.bottom() - max(0.0, min(float(value) / max_value, 1.0)) * plot.height()
                current = QPointF(x, y)
                if previous is not None:
                    painter.drawLine(previous, current)
                previous = current

        # The blue curve is output percent. The green curve is observed FPS
        # normalized only to the maximum *already observed* sample.
        draw_metrics([point.percent for point in self._points], 100.0, "#146CE5")
        fps = [point.fps for point in self._points]
        observed_fps = [float(v) for v in fps if v is not None]
        if observed_fps:
            draw_metrics(fps, max(1.0, max(observed_fps)), "#14A88A")

        if show_summary:
            summary_left = plot.right() + 12
            summary_width = max(20.0, (area.right() - summary_left - 8) / 3)
            observed = (
                ("Kecepatan", "—" if latest.fps is None else f"{latest.fps:.0f} fps"),
                ("Rata-rata", "—" if latest.average_fps is None
                 else f"{latest.average_fps:.0f} fps"),
                ("Sisa waktu", "—" if latest.eta_seconds is None
                 else f"{max(0, round(latest.eta_seconds)) // 60} mnt "
                      f"{max(0, round(latest.eta_seconds)) % 60} dtk"),
            )
            for index, (label, value) in enumerate(observed):
                cell = QRectF(
                    summary_left + index * summary_width,
                    area.top() + 31,
                    summary_width - 5,
                    max(24.0, area.height() - 43),
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#F4F8FD"))
                painter.drawRoundedRect(cell, 4, 4)
                painter.setPen(QColor("#647D9E"))
                painter.drawText(
                    cell.adjusted(4, 5, -3, -24),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    label,
                )
                painter.setPen(QColor("#152954"))
                painter.drawText(
                    cell.adjusted(4, 25, -2, -4),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    value,
                )

        legend = QRectF(
            plot.left(), area.bottom() - 16, plot.width(), 13
        )
        painter.setPen(QColor("#146CE5"))
        painter.drawText(
            legend,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            "● Progres",
        )
        if observed_fps:
            painter.setPen(QColor("#14A88A"))
            painter.drawText(
                legend,
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                "● FPS aktual",
            )
        painter.end()
