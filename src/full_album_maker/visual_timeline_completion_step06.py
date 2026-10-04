from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .editor_models import TIMEBASE
from .timeline_resolver import TimelineResolver
from .visual_precision import visual_settings_for_song
from .visual_workspace_step06 import TRANSITION_LABELS, VisualAlignmentCanvas


class TransitionVisualAlignmentCanvas(VisualAlignmentCanvas):
    """Adds model-derived transition badges without changing timeline geometry."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        resolved = TimelineResolver().resolve(self._document)
        if not resolved.songs:
            return
        left = 102
        duration = max(TIMEBASE, resolved.duration_tick)
        pps = max(0.01, (max(120, self.width() - left - 12)) / (duration / TIMEBASE))
        painter = QPainter(self)
        painter.setPen(QColor("#41566F"))
        for item in resolved.songs:
            song = self._document.song_map().get(item.song_id)
            if song is None or not song.visual_asset_id:
                continue
            try:
                settings = visual_settings_for_song(self._document, item.song_id)
            except Exception:
                continue
            transition = str(settings.get("transition", "cut"))
            seconds = float(settings.get("transition_seconds", 0.0) or 0.0)
            label = TRANSITION_LABELS.get(transition, transition.title())
            if transition != "cut":
                label = f"{label} {seconds:.1f}s"
            x = left + (item.start_tick / TIMEBASE) * pps
            width = max(4.0, ((item.end_tick - item.start_tick) / TIMEBASE) * pps)
            rect = QRectF(x + 3, 24, max(1.0, width - 6), 30)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        painter.end()


def install_step06_visual_timeline_completion() -> None:
    # visual_feature_step06 resolves this class when a window instance is built.
    from . import visual_feature_step06 as feature

    feature.VisualAlignmentCanvas = TransitionVisualAlignmentCanvas
