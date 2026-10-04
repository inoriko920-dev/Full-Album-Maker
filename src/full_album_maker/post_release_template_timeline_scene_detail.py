from __future__ import annotations

"""Deterministic scene detail for UI-06 Template timeline video clips.

The timeline continues to use real playlist segments from TemplateTimelineCanvas.
This layer changes only how each visible video clip is painted: a compact scene
thumbnail on the left and real song title/duration on the right. No golden image
or external asset is embedded, and project state is untouched.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPen, QPolygonF

from .post_release_template_subject_detail import _paint_jalan_pulang, _paint_subject

_installed = False


def _paint_perjalanan(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setClipRect(rect)
    sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sky.setColorAt(0.0, QColor("#426E63"))
    sky.setColorAt(0.55, QColor("#7D9F7D"))
    sky.setColorAt(1.0, QColor("#C5BB7D"))
    painter.fillRect(rect, sky)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#315C4E"))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left(), rect.bottom()),
        QPointF(rect.left() + rect.width() * .25, rect.top() + rect.height() * .48),
        QPointF(rect.left() + rect.width() * .43, rect.top() + rect.height() * .66),
        QPointF(rect.left() + rect.width() * .66, rect.top() + rect.height() * .38),
        QPointF(rect.right(), rect.bottom()),
    ]))
    painter.setBrush(QColor("#D9D0A1"))
    road = QPolygonF([
        QPointF(rect.left() + rect.width() * .47, rect.bottom()),
        QPointF(rect.left() + rect.width() * .52, rect.top() + rect.height() * .57),
        QPointF(rect.left() + rect.width() * .57, rect.top() + rect.height() * .57),
        QPointF(rect.left() + rect.width() * .72, rect.bottom()),
    ])
    painter.drawPolygon(road)
    painter.restore()


def _paint_cerita(painter: QPainter, rect: QRectF) -> None:
    painter.save()
    painter.setClipRect(rect)
    sky = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sky.setColorAt(0.0, QColor("#9A6D58"))
    sky.setColorAt(0.55, QColor("#C59670"))
    sky.setColorAt(1.0, QColor("#E7C58D"))
    painter.fillRect(rect, sky)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(67, 71, 67, 185))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left(), rect.bottom()),
        QPointF(rect.left() + rect.width() * .20, rect.top() + rect.height() * .64),
        QPointF(rect.left() + rect.width() * .45, rect.top() + rect.height() * .45),
        QPointF(rect.left() + rect.width() * .66, rect.top() + rect.height() * .67),
        QPointF(rect.left() + rect.width() * .84, rect.top() + rect.height() * .50),
        QPointF(rect.right(), rect.bottom()),
    ]))
    sun = min(rect.width(), rect.height()) * .34
    painter.setBrush(QColor(244, 208, 148, 210))
    painter.drawEllipse(QRectF(rect.right() - sun * 1.25, rect.top() + 3, sun, sun))
    painter.restore()


def _duration_text(song, timebase: int) -> str:
    duration = 0
    if song.source_out_tick is not None:
        duration = max(0, int(song.source_out_tick) - int(song.source_in_tick))
    seconds = max(0, int(round(duration / max(1, timebase))))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def install_post_release_template_timeline_scene_detail() -> None:
    global _installed
    if _installed:
        return

    from .post_release_template_timeline_surface import TemplateTimelineCanvas

    previous_paint = TemplateTimelineCanvas.paintEvent

    def paint_with_scene_clips(self, event) -> None:
        previous_paint(self, event)
        document = getattr(self, "_document", None)
        if document is None:
            return
        songs = document.song_map()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        timebase = max(1, int(document.timebase))

        for song_id, rect, _start in getattr(self, "_hits", []):
            song = songs.get(song_id)
            if song is None or rect.width() < 22 or rect.height() < 9:
                continue
            inner = rect.adjusted(1.5, 1.5, -1.5, -1.5)
            thumb_w = max(14.0, min(inner.width() * 0.46, 118.0))
            thumb = QRectF(inner.left(), inner.top(), thumb_w, inner.height())
            detail = QRectF(thumb.right(), inner.top(), max(1.0, inner.width() - thumb.width()), inner.height())
            title = str(song.display_title or "Lagu")
            key = title.casefold()

            if "senja" in key:
                gradient = QLinearGradient(thumb.topLeft(), thumb.bottomLeft())
                gradient.setColorAt(0.0, QColor("#5B5268"))
                gradient.setColorAt(0.50, QColor("#BB775B"))
                gradient.setColorAt(1.0, QColor("#E0A36B"))
                painter.fillRect(thumb, gradient)
                _paint_subject(painter, thumb)
            elif "jalan pulang" in key:
                _paint_jalan_pulang(painter, thumb)
            elif "perjalanan" in key:
                _paint_perjalanan(painter, thumb)
            elif "cerita" in key:
                _paint_cerita(painter, thumb)
            else:
                painter.fillRect(thumb, QColor("#6F8FAA"))

            painter.fillRect(detail, QColor("#EAF4FF"))
            painter.setPen(QColor("#183E6A"))
            font = painter.font()
            font.setPointSizeF(max(6.5, min(9.0, rect.height() * .30)))
            font.setBold(False)
            painter.setFont(font)
            label = QFontMetrics(font).elidedText(
                title,
                Qt.TextElideMode.ElideRight,
                max(4, int(detail.width()) - 7),
            )
            painter.drawText(
                detail.adjusted(4, 1, -2, -inner.height() * .38),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            painter.setPen(QColor("#53708F"))
            small = painter.font()
            small.setPointSizeF(max(5.5, font.pointSizeF() - 1.5))
            painter.setFont(small)
            painter.drawText(
                detail.adjusted(4, inner.height() * .45, -2, -1),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                _duration_text(song, timebase),
            )
            selected = song_id == getattr(self, "_selected_song_id", "")
            painter.setPen(QPen(QColor("#1766E8" if selected else "#83AEEA"), 2 if selected else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 3, 3)

        painter.end()

    TemplateTimelineCanvas.paintEvent = paint_with_scene_clips
    _installed = True
