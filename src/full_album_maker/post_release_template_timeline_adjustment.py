from __future__ import annotations

"""Presentation-only UI-06 Template timeline alignment.

The Template workspace already owns a real ProjectDocument and non-destructive
preview path. This layer only replaces the cramped STEP06 alignment canvas with
an UI-06 specific three-lane overview and hides the generic Packed/Free toolbar
while Template is active. Project state, template commands and history are not
mutated.
"""

import hashlib
import math
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from .editor_models import ProjectDocument, TIMEBASE
from .foundation_tokens import TOKENS
from .timeline_resolver import TimelineResolver

_installed = False


def _title(document: ProjectDocument, song_id: str) -> str:
    song = document.song_map().get(song_id)
    return (song.display_title.strip() if song and song.display_title.strip() else "Lagu")


def _cover_image(document: ProjectDocument, song_id: str) -> QImage | None:
    song = document.song_map().get(song_id)
    if song is None:
        return None
    asset_id = song.visual_asset_id or song.cover_asset_id
    if not asset_id:
        return None
    asset = document.asset_map().get(asset_id)
    if asset is None:
        return None
    path = Path(str(getattr(asset, "locator", "") or ""))
    if not path.is_file():
        return None
    image = QImage(str(path))
    return None if image.isNull() else image


class TemplateTimelineCanvas(QWidget):
    LABEL_W = 88
    RULER_H = 20

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("postReleaseTemplateTimeline")
        self.setMinimumHeight(112)
        self._document = ProjectDocument.new_empty()
        self._selected_ids: set[str] = set()
        self._playhead_tick = 0

    def set_state(self, document: ProjectDocument, selected_ids: set[str], playhead_tick: int) -> None:
        self._document = document.clone()
        self._selected_ids = set(selected_ids)
        self._playhead_tick = max(0, int(playhead_tick))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        left = self.LABEL_W
        right = 8
        width = max(1, self.width() - left - right)
        lane_h = max(22.0, (self.height() - self.RULER_H - 2) / 3.0)
        lane_names = ("Video", "Audio", "Teks")
        lane_fills = (QColor("#F5F8FC"), QColor("#F2FBF8"), QColor("#FAF7FD"))

        painter.setPen(QPen(QColor("#D9E4F2"), 1))
        painter.drawLine(left, self.RULER_H, self.width() - right, self.RULER_H)
        for idx, name in enumerate(lane_names):
            y = self.RULER_H + idx * lane_h
            painter.fillRect(QRectF(left, y, width, lane_h), lane_fills[idx])
            painter.fillRect(QRectF(0, y, left, lane_h), QColor("#F8FBFF"))
            painter.setPen(QPen(QColor("#E0E8F2"), 1))
            painter.drawLine(0, int(y + lane_h), self.width() - right, int(y + lane_h))
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(QRectF(9, y, left - 14, lane_h), Qt.AlignmentFlag.AlignVCenter, name)

        resolved = TimelineResolver().resolve(self._document)
        total = max(TIMEBASE, int(resolved.duration_tick))
        timebase = max(1, int(self._document.timebase))

        painter.setPen(QColor("#526A86"))
        for idx in range(7):
            ratio = idx / 6.0
            x = left + width * ratio
            tick = int(total * ratio)
            seconds = int(round(tick / timebase))
            minute, second = divmod(seconds, 60)
            painter.setPen(QPen(QColor("#D5E1EF"), 1))
            painter.drawLine(int(x), self.RULER_H - 4, int(x), self.RULER_H)
            painter.setPen(QColor("#607089"))
            painter.drawText(QRectF(x - 24, 1, 48, self.RULER_H - 3), Qt.AlignmentFlag.AlignCenter, f"{minute:02d}:{second:02d}")

        video_y = self.RULER_H + 2
        audio_y = self.RULER_H + lane_h + 2
        text_y = self.RULER_H + lane_h * 2 + 2
        clip_h = max(14.0, lane_h - 4)

        for event in resolved.songs:
            x0 = left + width * (event.start_tick / total)
            x1 = left + width * (event.end_tick / total)
            clip_w = max(3.0, x1 - x0 - 1.0)
            selected = event.song_id in self._selected_ids
            title = _title(self._document, event.song_id)

            video_rect = QRectF(x0, video_y, clip_w, clip_h)
            image = _cover_image(self._document, event.song_id)
            if image is not None:
                painter.save()
                painter.setClipRect(video_rect)
                target = video_rect.toRect()
                scaled = image.scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                px = target.x() - max(0, (scaled.width() - target.width()) // 2)
                py = target.y() - max(0, (scaled.height() - target.height()) // 2)
                painter.drawImage(px, py, scaled)
                painter.fillRect(video_rect, QColor(18, 35, 62, 35))
                painter.restore()
            else:
                digest = hashlib.sha256(event.song_id.encode("utf-8")).digest()
                palette = ("#7E9EC8", "#86A58F", "#B08A72", "#788AA8")
                painter.fillRect(video_rect, QColor(palette[digest[0] % len(palette)]))
            painter.setPen(QPen(QColor("#1766E8" if selected else "#CBD9EA"), 2 if selected else 1))
            painter.drawRoundedRect(video_rect, 2.5, 2.5)
            if clip_w >= 58:
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(video_rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

            audio_rect = QRectF(x0, audio_y, clip_w, clip_h)
            painter.fillRect(audio_rect, QColor("#CFF3E7"))
            painter.setPen(QPen(QColor("#39B79E"), 1))
            mid = audio_rect.center().y()
            seed = int(hashlib.sha256(event.song_id.encode("utf-8")).hexdigest()[:8], 16)
            samples = max(3, min(32, int(audio_rect.width() / 4)))
            for sample in range(samples):
                ratio = sample / max(1, samples - 1)
                x = audio_rect.left() + ratio * audio_rect.width()
                amp = (0.18 + 0.70 * abs(math.sin((sample + seed % 17) * 0.71))) * audio_rect.height() * 0.34
                painter.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))

            # Template preview always has a title treatment per song. Render the
            # non-destructive preview intent as a text lane without creating layers.
            text_rect = QRectF(x0, text_y, clip_w, clip_h)
            painter.fillRect(text_rect, QColor("#EADDFC"))
            painter.setPen(QPen(QColor("#B994E2"), 1))
            painter.drawRoundedRect(text_rect, 2.5, 2.5)
            if clip_w >= 58:
                painter.setPen(QColor("#65448A"))
                painter.drawText(text_rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

        play_x = left + width * min(1.0, max(0.0, self._playhead_tick / max(1, total)))
        painter.setPen(QPen(QColor("#1766E8"), 2))
        painter.drawLine(int(play_x), self.RULER_H, int(play_x), self.height() - 2)
        painter.end()


def _install_canvas(window) -> None:
    old = getattr(window, "template_timeline_s07", None)
    if old is None or isinstance(old, TemplateTimelineCanvas):
        return
    layout = old.parentWidget().layout()
    index = layout.indexOf(old)
    layout.removeWidget(old)
    old.hide()
    canvas = TemplateTimelineCanvas(old.parentWidget())
    if index < 0:
        layout.addWidget(canvas, 1)
    else:
        layout.insertWidget(index, canvas, 1)
    window.template_timeline_s07 = canvas


def _template_project_context(window) -> str:
    document = window.editor_workspace.document()
    songs = len(document.playlist.entries)
    footage = sum(1 for asset in document.media if str(getattr(asset, "kind", "")) == "video")
    settings = window.project.settings
    return f"Proyek aktif • {songs} lagu • {footage} footage • {settings.width}×{settings.height}"


def _set_template_shell(window, active: bool) -> None:
    timeline = window.foundation_shell.timeline
    timeline.mode.setVisible(not active)
    for button in timeline.body.findChildren(QAbstractButton):
        if button.text().strip() in {"Split", "Ripple", "Snap", "Marker"}:
            button.setVisible(not active)
    timeline.message.setVisible(not active)
    body_layout = timeline.body.layout()
    if active:
        body_layout.setContentsMargins(0, 0, 0, 2)
        body_layout.setSpacing(0)
        context = _template_project_context(window)
        window.foundation_state.set_status(project_context=context)
        timeline.set_project_context(context)
    else:
        body_layout.setContentsMargins(TOKENS.space_2, 0, TOKENS.space_2, TOKENS.space_2)
        body_layout.setSpacing(2)
        sync_foundation_state = getattr(window, "_sync_foundation_state", None)
        if callable(sync_foundation_state):
            sync_foundation_state()


def install_post_release_template_timeline_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_route = Window._s07_route

    def route_with_template_timeline(self, route: str) -> None:
        _install_canvas(self)
        _set_template_shell(self, route == "template")
        previous_route(self, route)
        if route == "template":
            self._s07_refresh_timeline()

    Window._s07_route = route_with_template_timeline
    _installed = True
