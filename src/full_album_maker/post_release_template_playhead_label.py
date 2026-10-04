from __future__ import annotations

"""UI-06 playhead time bubble for the Template timeline.

Presentation only: the authoritative playhead tick and timeline resolver remain
owned by EditorWorkspace. This layer simply paints the current time above the
existing ruler so Template matches the reference editor chrome.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .post_release_ai_preview_timeline_surface import _timeline_segments
from .post_release_template_timeline_surface import TemplateTimelineCanvas

_installed = False


def _clock_label(tick: int, timebase: int) -> str:
    seconds = max(0.0, float(tick) / max(1, int(timebase)))
    whole = int(seconds)
    hundredths = int(round((seconds - whole) * 100.0))
    if hundredths >= 100:
        whole += 1
        hundredths = 0
    minutes, second = divmod(whole, 60)
    return f"{minutes:02d}:{second:02d}.{hundredths:02d}"


def install_post_release_template_playhead_label() -> None:
    global _installed
    if _installed:
        return

    previous_paint = TemplateTimelineCanvas.paintEvent

    def paint_with_time_label(self, event) -> None:
        previous_paint(self, event)
        document = getattr(self, "_document", None)
        if document is None or not document.playlist.entries:
            return

        _segments, total = _timeline_segments(document)
        timebase = max(1, int(document.timebase))
        view_total = self._view_total(total, timebase)
        playhead = min(view_total, max(0, int(self._playhead_tick)))
        width = max(1.0, float(self.width() - self.LABEL_W - 5))
        x = self.LABEL_W + width * (playhead / max(1, view_total))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        label = _clock_label(playhead, timebase)
        bubble_w = 61.0
        bubble_h = 17.0
        rect = QRectF(x - bubble_w / 2.0, 0.0, bubble_w, bubble_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1766E8"))
        painter.drawRoundedRect(rect, 4.0, 4.0)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.end()

    TemplateTimelineCanvas.paintEvent = paint_with_time_label
    _installed = True
