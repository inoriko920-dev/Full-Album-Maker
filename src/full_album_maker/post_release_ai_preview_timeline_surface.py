from __future__ import annotations

"""Three-lane, non-destructive timeline preview for the AI Agent workspace.

UI-08 uses a compact Video / Audio / Teks overview rather than the full seven
lane precision editor. This module replaces only the AI Agent timeline canvas.
When an AgentPlan reaches PREVIEW_READY, the exact dry-run domain commands are
replayed against a clone and that clone is painted here. The live project,
revision, command history, undo stack and execution state are never mutated.
"""

import hashlib
import math
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel

from .foundation_tokens import TOKENS

_installed = False


def _song_duration_tick(song, assets: dict[str, object], timebase: int) -> int:
    if song.source_out_tick is not None and int(song.source_out_tick) > int(song.source_in_tick):
        return int(song.source_out_tick) - int(song.source_in_tick)
    asset = assets.get(song.asset_id)
    duration = int(getattr(asset, "source_duration_tick", 0) or 0) if asset is not None else 0
    return max(int(timebase), duration)


def _timeline_segments(document) -> tuple[list[tuple[object, int, int]], int]:
    assets = document.asset_map()
    timebase = max(1, int(document.timebase))
    segments: list[tuple[object, int, int]] = []
    cursor = 0
    for song in document.playlist.entries:
        duration = _song_duration_tick(song, assets, timebase)
        if document.playlist.mode == "free" and song.free_start_tick is not None:
            start = max(0, int(song.free_start_tick))
        else:
            start = cursor
        end = start + max(1, duration)
        segments.append((song, start, end))
        cursor = max(cursor, end)
    total = max((end for _song, _start, end in segments), default=timebase)
    return segments, max(timebase, total)


def _format_tick(tick: int, timebase: int) -> str:
    seconds = max(0, int(round(tick / max(1, timebase))))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def _fallback_color(seed: str) -> QColor:
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).digest()
    palette = (
        "#557AA8",
        "#668F9D",
        "#7D719B",
        "#8B785F",
        "#5F8B77",
        "#6F83A9",
        "#8A6F83",
    )
    return QColor(palette[digest[0] % len(palette)])


def _cover_pixmap(document, song, width: int, height: int) -> QPixmap | None:
    asset_id = song.visual_asset_id or song.cover_asset_id
    if not asset_id:
        return None
    asset = document.asset_map().get(asset_id)
    if asset is None:
        return None
    locator = Path(str(getattr(asset, "locator", "") or ""))
    if not locator.is_file():
        return None
    pixmap = QPixmap(str(locator))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        max(1, width),
        max(1, height),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )


class AIPreviewTimelineCanvas(QFrame):
    LABEL_W = 86
    RULER_H = 20

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = None
        self._playhead_tick = 0
        self._selected_song_id = ""
        self._selected_layer_id = ""
        self.setObjectName("aiPreviewTimelineCanvas")
        self.setMinimumHeight(104)

    def sizeHint(self) -> QSize:
        return QSize(900, 112)

    def set_document(self, document) -> None:
        self._document = document
        self.update()

    def set_playhead(self, tick: int) -> None:
        self._playhead_tick = max(0, int(tick))
        self.update()

    def set_selection(self, *, song_id: str = "", layer_id: str = "") -> None:
        self._selected_song_id = str(song_id or "")
        self._selected_layer_id = str(layer_id or "")
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        document = self._document
        left = self.LABEL_W
        right = 8
        width = max(1, self.width() - left - right)
        available_h = max(66, self.height() - self.RULER_H - 2)
        lane_h = available_h / 3.0
        lane_names = ("Video", "Audio", "Teks")
        lane_fills = (QColor("#F4F8FD"), QColor("#F3FBF8"), QColor("#FAF7FD"))

        painter.setPen(QPen(QColor("#DCE6F2"), 1))
        painter.drawLine(left, self.RULER_H, self.width() - right, self.RULER_H)
        for index, name in enumerate(lane_names):
            y = self.RULER_H + index * lane_h
            lane_rect = QRectF(left, y, width, lane_h)
            painter.fillRect(lane_rect, lane_fills[index])
            painter.setPen(QPen(QColor("#E1E9F3"), 1))
            painter.drawLine(left, int(y + lane_h), self.width() - right, int(y + lane_h))
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(
                QRectF(8, y, left - 14, lane_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                name,
            )

        if document is None or not document.playlist.entries:
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(
                QRectF(left, self.RULER_H, width, available_h),
                Qt.AlignmentFlag.AlignCenter,
                "Preview timeline belum tersedia",
            )
            painter.end()
            return

        segments, total = _timeline_segments(document)
        timebase = max(1, int(document.timebase))

        painter.setPen(QColor("#526A86"))
        for index in range(7):
            ratio = index / 6.0
            x = left + width * ratio
            tick = int(total * ratio)
            painter.setPen(QPen(QColor("#D5E1EF"), 1))
            painter.drawLine(int(x), self.RULER_H - 4, int(x), self.RULER_H)
            painter.setPen(QColor("#526A86"))
            painter.drawText(
                QRectF(x - 25, 1, 50, self.RULER_H - 3),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                _format_tick(tick, timebase),
            )

        video_y = self.RULER_H + 2
        audio_y = self.RULER_H + lane_h + 2
        text_y = self.RULER_H + lane_h * 2 + 2
        clip_h = max(12.0, lane_h - 4)

        for index, (song, start, end) in enumerate(segments):
            x0 = left + width * (start / total)
            x1 = left + width * (end / total)
            clip_w = max(2.0, x1 - x0 - 1.0)
            video_rect = QRectF(x0, video_y, clip_w, clip_h)
            selected = song.song_id == self._selected_song_id

            thumb = _cover_pixmap(document, song, int(video_rect.width()), int(video_rect.height()))
            if thumb is not None:
                painter.save()
                painter.setClipRect(video_rect)
                painter.drawPixmap(video_rect.toRect(), thumb)
                painter.fillRect(video_rect, QColor(12, 30, 58, 70))
                painter.restore()
            else:
                painter.fillRect(video_rect, _fallback_color(song.song_id))

            painter.setPen(QPen(QColor("#2E6FBE" if selected else "#D8E4F3"), 2 if selected else 1))
            painter.drawRoundedRect(video_rect, 2.5, 2.5)
            if clip_w >= 34:
                painter.setPen(QColor("#FFFFFF"))
                label = song.display_title or f"Lagu {index + 1}"
                painter.drawText(
                    video_rect.adjusted(4, 0, -3, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    label,
                )

            audio_rect = QRectF(x0, audio_y, clip_w, clip_h)
            painter.fillRect(audio_rect, QColor("#DDF6EC"))
            painter.setPen(QPen(QColor("#36B89E"), 1))
            mid = audio_rect.center().y()
            seed = int(hashlib.sha256(song.song_id.encode()).hexdigest()[:8], 16)
            samples = max(4, min(36, int(audio_rect.width() / 3)))
            for sample in range(samples):
                ratio = sample / max(1, samples - 1)
                x = audio_rect.left() + ratio * audio_rect.width()
                phase = (sample + (seed % 29)) * 0.73
                amplitude = (0.18 + 0.72 * abs(math.sin(phase))) * audio_rect.height() * 0.36
                painter.drawLine(int(x), int(mid - amplitude), int(x), int(mid + amplitude))

        for layer in document.layers:
            kind = str(getattr(layer, "type", "") or "").casefold()
            name = str(getattr(layer, "name", "") or "")
            if not ("text" in kind or "title" in kind or "subtitle" in kind or "caption" in kind):
                continue
            binding = layer.time_binding
            start = max(0, int(getattr(binding, "start_tick", 0) or 0))
            duration = int(getattr(binding, "duration_tick", 0) or 0)
            if duration <= 0:
                duration = max(timebase, total // 6)
            end = min(total, start + duration)
            if end <= start:
                continue
            x0 = left + width * (start / total)
            x1 = left + width * (end / total)
            rect = QRectF(x0, text_y, max(3.0, x1 - x0 - 1.0), clip_h)
            painter.fillRect(rect, QColor("#EBDDFA"))
            painter.setPen(QPen(QColor("#B893E5"), 1))
            painter.drawRoundedRect(rect, 2.5, 2.5)
            if rect.width() >= 42:
                painter.setPen(QColor("#65438C"))
                painter.drawText(
                    rect.adjusted(4, 0, -3, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    name or "Teks",
                )

        playhead_x = left + width * min(1.0, max(0.0, self._playhead_tick / max(1, total)))
        painter.setPen(QPen(QColor("#E05252"), 1))
        painter.drawLine(int(playhead_x), self.RULER_H, int(playhead_x), self.height() - 2)
        painter.end()


def _set_foundation_toolbar_visible(window, visible: bool) -> None:
    timeline = window.foundation_shell.timeline
    timeline.mode.setVisible(bool(visible))
    body = timeline.body
    for button in body.findChildren(QAbstractButton):
        # The foundation toolbar owns only these commands. Descendant buttons in
        # the AI precision panel have already been disabled by _install_canvas.
        if button.text().strip() in {"Split", "Ripple", "Snap", "Marker"}:
            button.setVisible(bool(visible))


def _install_canvas(window) -> None:
    panel = getattr(window, "ai_timeline_s09", None)
    if panel is None or getattr(panel, "_post_release_ai_three_lane", False):
        return

    old = panel.canvas
    layout = panel.layout()
    index = layout.indexOf(old)
    layout.removeWidget(old)
    old.hide()

    canvas = AIPreviewTimelineCanvas(panel)
    if index < 0:
        layout.addWidget(canvas, 1)
    else:
        layout.insertWidget(index, canvas, 1)
    panel.canvas = canvas

    # Hide the STEP05 precision toolbar that belongs to this AI panel. The outer
    # foundation toolbar is controlled separately by route.
    mode = getattr(panel, "mode", None)
    if mode is not None:
        mode.hide()
    for name in ("split", "delete_gap", "ripple", "snap", "marker"):
        widget = getattr(panel, name, None)
        if widget is not None:
            widget.hide()
    playhead_label = getattr(panel, "playhead_label", None)
    if isinstance(playhead_label, QLabel):
        playhead_label.hide()
    for button in panel.findChildren(QAbstractButton):
        button.hide()
    layout.setSpacing(0)
    panel._post_release_ai_three_lane = True


def install_post_release_ai_preview_timeline_surface() -> None:
    global _installed
    if _installed:
        return

    from .ai_agent_core_step09 import AgentState
    from .editor_controller import EditorController
    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_refresh = Window._s09_refresh

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_canvas(self)
        _set_foundation_toolbar_visible(self, getattr(self.foundation_state, "workspace", "") != "ai_agent")
        self.foundation_state.workspace_changed.connect(
            lambda route: _set_foundation_toolbar_visible(self, str(route) != "ai_agent")
        )
        self._s09_refresh()

    def refresh_with_preview_surface(self) -> None:
        previous_refresh(self)
        _install_canvas(self)
        active = getattr(self.foundation_state, "workspace", "") == "ai_agent"
        _set_foundation_toolbar_visible(self, not active)
        if not active:
            return
        session = getattr(self, "_s09_agent_session", None)
        if session is None:
            return
        snapshot = session.snapshot()
        preview = snapshot.preview
        if snapshot.state != AgentState.PREVIEW_READY or preview is None or not preview.commands:
            return

        simulation = self.editor_workspace.document().clone()
        simulation, _inverse = EditorController._apply_transaction(simulation, preview.commands)
        self.ai_timeline_s09.apply_document(
            simulation,
            self.editor_workspace.session.playhead_tick,
            ripple=bool(getattr(self, "_s05_ripple", False)),
            snap=self.editor_workspace.session.snap_enabled,
        )
        selected = self._s09_selected_song_ids()
        layers = self._s09_selected_layer_ids()
        self.ai_timeline_s09.canvas.set_selection(
            song_id=(selected[0] if len(selected) == 1 else ""),
            layer_id=(layers[0] if len(layers) == 1 else ""),
        )

    Window.__init__ = wrapped_init
    Window._s09_refresh = refresh_with_preview_surface
    _installed = True
