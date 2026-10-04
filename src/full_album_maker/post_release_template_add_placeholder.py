from __future__ import annotations

"""UI-06 trailing add-clip placeholder for Template timeline.

Presentation only. The authoritative playlist and project state are unchanged;
this layer paints a small add affordance after the last visible video clip when
there is enough free timeline space.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .post_release_ai_preview_timeline_surface import _timeline_segments
from .post_release_template_timeline_surface import TemplateTimelineCanvas

_installed = False


def install_post_release_template_add_placeholder() -> None:
    global _installed
    if _installed:
        return

    previous_paint = TemplateTimelineCanvas.paintEvent

    def paint_with_placeholder(self, event) -> None:
        previous_paint(self, event)
        document = getattr(self, "_document", None)
        if document is None or not document.playlist.entries:
            return

        segments, total = _timeline_segments(document)
        if not segments:
            return

        timebase = max(1, int(document.timebase))
        view_total = self._view_total(total, timebase)
        visible_end = min(view_total, max(end for _song, _start, end in segments))
        left = float(self.LABEL_W)
        right = 5.0
        width = max(1.0, float(self.width()) - left - right)
        end_x = left + width * (visible_end / max(1, view_total))

        lane_area = max(60.0, float(self.height() - self.RULER_H - 1))
        lane_h = lane_area / 3.0
        clip_h = max(13.0, lane_h - 4.0)
        size = min(24.0, clip_h)
        gap = 7.0
        x = end_x + gap
        y = float(self.RULER_H) + 2.0 + (clip_h - size) / 2.0

        # Keep the affordance off-screen when the last clip already fills the view.
        if x + size > float(self.width()) - right - 2.0:
            return

        rect = QRectF(x, y, size, size)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#B9C9DC"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        cx = rect.center().x()
        cy = rect.center().y()
        arm = max(3.0, size * 0.22)
        painter.setPen(QPen(QColor("#71859D"), 1.4))
        painter.drawLine(int(cx - arm), int(cy), int(cx + arm), int(cy))
        painter.drawLine(int(cx), int(cy - arm), int(cx), int(cy + arm))
        painter.end()

    TemplateTimelineCanvas.paintEvent = paint_with_placeholder
    _installed = True
