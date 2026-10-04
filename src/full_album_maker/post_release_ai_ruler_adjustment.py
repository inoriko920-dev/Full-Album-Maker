from __future__ import annotations

"""UI-08 ruler refinement for long-form AI preview timelines.

The underlying duration and clip geometry stay authoritative. After the normal
preview canvas paints, this layer redraws only the ruler using fixed 5-minute
ticks for long-form projects, matching the approved full-album reference.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

_installed = False


def install_post_release_ai_ruler_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_ai_preview_timeline_surface import (
        AIPreviewTimelineCanvas,
        _format_tick,
        _timeline_segments,
    )

    original_paint = AIPreviewTimelineCanvas.paintEvent

    def paint_with_five_minute_ruler(self, event) -> None:
        original_paint(self, event)
        document = getattr(self, "_document", None)
        if document is None or not document.playlist.entries:
            return

        _segments, total = _timeline_segments(document)
        timebase = max(1, int(document.timebase))
        total_seconds = total / timebase
        if total_seconds < 20 * 60:
            return

        left = self.LABEL_W
        right = 8
        width = max(1, self.width() - left - right)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Cover only the original ruler strip; the three timeline lanes below it
        # remain exactly as rendered by the production preview surface.
        painter.fillRect(QRectF(left, 0, width, self.RULER_H), QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#DCE6F2"), 1))
        painter.drawLine(left, self.RULER_H, self.width() - right, self.RULER_H)

        tick_seconds = 5 * 60
        second = 0
        while second <= int(total_seconds):
            tick = second * timebase
            ratio = tick / max(1, total)
            x = left + width * ratio
            painter.setPen(QPen(QColor("#D5E1EF"), 1))
            painter.drawLine(int(x), self.RULER_H - 4, int(x), self.RULER_H)
            painter.setPen(QColor("#526A86"))
            label_rect = QRectF(x - 25, 1, 50, self.RULER_H - 3)
            if second == 0:
                label_rect = QRectF(x, 1, 50, self.RULER_H - 3)
                alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            else:
                alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            painter.drawText(label_rect, alignment, _format_tick(tick, timebase))
            second += tick_seconds
        painter.end()

    AIPreviewTimelineCanvas.paintEvent = paint_with_five_minute_ruler
    _installed = True
