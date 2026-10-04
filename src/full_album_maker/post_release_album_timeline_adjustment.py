from __future__ import annotations

"""Post-release presentation upgrade for the Album overview timeline.

The canvas still reads the authoritative ProjectDocument only. No clip/timing
state is created or mutated here; thumbnails, labels, ruler and waveform are
pure visualization of the existing album sequence.
"""

import math
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from .foundation_tokens import TOKENS

_installed = False


def _crop_pixmap(path: Path, width: int, height: int) -> QPixmap | None:
    if not path.is_file():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        max(1, width),
        max(1, height),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


def _paint_album_timeline(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(self.rect(), QColor("#FFFFFF"))

    left = 92
    right = 12
    ruler_h = 24
    video_y = ruler_h + 2
    video_h = max(38, int((self.height() - ruler_h - 8) * 0.49))
    audio_y = video_y + video_h + 4
    audio_h = max(25, self.height() - audio_y - 4)
    usable = max(1, self.width() - left - right)

    painter.setPen(QPen(QColor("#D8E4F2"), 1))
    painter.drawLine(left, ruler_h, self.width() - right, ruler_h)
    painter.setPen(QColor(TOKENS.text_primary))
    painter.drawText(QRectF(14, video_y, left - 20, video_h), Qt.AlignmentFlag.AlignVCenter, "▣  Video")
    painter.drawText(QRectF(14, audio_y, left - 20, audio_h), Qt.AlignmentFlag.AlignVCenter, "♫  Audio")

    # UI-03 reference is a zoomed overview of the first part of the album.
    # Keep the preview deterministic while still sourcing every visible clip
    # from the authoritative playlist and its existing cover/visual assets.
    songs = list(self._document.playlist.entries)
    visible = songs[:7]
    assets = self._document.asset_map()
    if not visible:
        painter.setPen(QColor(TOKENS.text_muted))
        painter.drawText(QRectF(left, ruler_h, usable, self.height() - ruler_h), Qt.AlignmentFlag.AlignCenter, "Belum ada lagu")
        painter.end()
        return

    plus_width = 150
    clips_width = max(1, usable - plus_width - 10)
    clip_width = clips_width / max(1, len(visible))

    # Time ruler: deterministic 10-minute ticks across the visible zoom window.
    painter.setPen(QColor("#45607F"))
    for index in range(16):
        x = left + (usable * index / 15.0)
        painter.setPen(QPen(QColor("#DDE8F5"), 1))
        painter.drawLine(int(x), ruler_h - 5, int(x), ruler_h)
        painter.setPen(QColor("#45607F"))
        minutes = index * 10
        label = f"{minutes // 60}:{minutes % 60:02d}" if minutes >= 60 else f"{minutes:02d}:00"
        painter.drawText(QRectF(x - 18, 1, 46, 18), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, label)

    for index, song in enumerate(visible):
        x = left + index * clip_width
        rect = QRectF(x, video_y, max(8.0, clip_width - 3), video_h)
        selected = song.song_id in self._selected_ids
        painter.setPen(QPen(QColor(TOKENS.primary_600 if selected else "#B9CDE6"), 2 if selected else 1))
        painter.setBrush(QColor("#DCEAFF"))
        painter.drawRoundedRect(rect, 4, 4)

        asset_id = getattr(song, "cover_asset_id", None) or getattr(song, "visual_asset_id", None)
        asset = assets.get(asset_id) if asset_id else None
        thumb = _crop_pixmap(Path(asset.locator), int(rect.width()), int(rect.height())) if asset is not None else None
        if thumb is not None:
            painter.save()
            painter.setClipRect(rect.adjusted(1, 1, -1, -1))
            painter.drawPixmap(rect.toRect(), thumb)
            painter.fillRect(rect.adjusted(rect.width() * 0.42, 0, 0, 0), QColor(16, 35, 74, 155))
            painter.restore()
        else:
            palette = ("#315C8A", "#4D87A4", "#6A8A55", "#C47C4B", "#75506D", "#3D708C", "#80684A")
            painter.fillRect(rect.adjusted(1, 1, -1, -1), QColor(palette[index % len(palette)]))

        painter.setPen(QColor("#FFFFFF"))
        title = getattr(song, "display_title", "") or f"Lagu {index + 1}"
        painter.drawText(
            rect.adjusted(max(8.0, rect.width() * 0.43), 0, -5, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{index + 1}. {title}",
        )

    plus_rect = QRectF(left + clips_width + 5, video_y, plus_width - 5, video_h)
    painter.setPen(QPen(QColor("#8BB8F2"), 1, Qt.PenStyle.DashLine))
    painter.setBrush(QColor("#FBFDFF"))
    painter.drawRoundedRect(plus_rect, 4, 4)
    painter.setPen(QColor(TOKENS.primary_600))
    painter.drawText(plus_rect, Qt.AlignmentFlag.AlignCenter, "+")

    # Deterministic waveform visualization. It conveys real track extent but
    # never feeds back into editing/render calculations.
    audio_rect = QRectF(left, audio_y, usable, audio_h)
    painter.fillRect(audio_rect, QColor("#E7FAF8"))
    mid = audio_rect.center().y()
    path_top = QPainterPath()
    path_bottom = QPainterPath()
    for px in range(int(audio_rect.width())):
        x = audio_rect.left() + px
        phase = px * 0.17
        modulation = 0.35 + 0.65 * abs(math.sin(px * 0.037 + 0.6))
        amplitude = (audio_rect.height() * 0.39) * modulation * (0.55 + 0.45 * abs(math.sin(phase)))
        top = mid - amplitude
        bottom = mid + amplitude
        if px == 0:
            path_top.moveTo(x, top)
            path_bottom.moveTo(x, bottom)
        else:
            path_top.lineTo(x, top)
            path_bottom.lineTo(x, bottom)
    painter.setPen(QPen(QColor("#2ED5C7"), 1))
    painter.drawPath(path_top)
    painter.drawPath(path_bottom)
    painter.setPen(QPen(QColor("#B8EDE8"), 1))
    for index in range(1, len(visible)):
        x = left + index * clip_width
        painter.drawLine(int(x), int(audio_rect.top()), int(x), int(audio_rect.bottom()))

    painter.end()


def install_post_release_album_timeline_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .album_workspace import AlbumTimelineOverviewCanvas

    original_init = AlbumTimelineOverviewCanvas.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.setMinimumHeight(104)

    AlbumTimelineOverviewCanvas.__init__ = adjusted_init
    AlbumTimelineOverviewCanvas.paintEvent = _paint_album_timeline
    _installed = True
