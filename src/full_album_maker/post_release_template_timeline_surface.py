from __future__ import annotations

"""UI-06 Template timeline surface.

The Template workspace needs a compact Video / Audio / Teks overview that is
visually different from the seven-lane precision editor. The surface paints a
real disposable template preview built through STEP07's production preview
contract. The live ProjectDocument is never mutated merely to render the
Template timeline.

Toolbar actions that edit the project (Split/Hapus) dispatch normal editor
commands. Volume and Zoom are presentation/session controls only.
"""

from copy import deepcopy
import hashlib
import math

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QSlider

from .editor_commands import SetPlaylistEntries
from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .post_release_ai_preview_timeline_surface import (
    _cover_pixmap,
    _format_tick,
    _timeline_segments,
)
from .template_studio_step07 import preview_template_document
from .timeline_audio_commands import SplitSongAtTick

_installed = False


def _clip_color(song_id: str) -> QColor:
    digest = hashlib.sha256(str(song_id).encode("utf-8", errors="ignore")).digest()
    palette = ("#6788A8", "#648A73", "#9A745E", "#697E9B")
    return QColor(palette[digest[0] % len(palette)])


class TemplateTimelineCanvas(QFrame):
    """Compact production-backed UI-06 timeline painter."""

    playhead_requested = Signal(int)
    song_selected = Signal(str)

    LABEL_W = 140
    RULER_H = 18

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("templateUi06TimelineCanvas")
        self.setMinimumHeight(92)
        self.setSizePolicy(
            __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Policy.Expanding,
            __import__("PySide6.QtWidgets", fromlist=["QSizePolicy"]).QSizePolicy.Policy.Expanding,
        )
        self._document = None
        self._playhead_tick = 0
        self._selected_song_id = ""
        self._zoom = 1.0
        self._hits: list[tuple[str, QRectF, int]] = []

    def sizeHint(self) -> QSize:
        return QSize(1000, 100)

    def set_document(self, document) -> None:
        self._document = document.clone()
        if self._selected_song_id not in self._document.song_map():
            self._selected_song_id = ""
        self.update()

    def set_playhead(self, tick: int) -> None:
        self._playhead_tick = max(0, int(tick))
        self.update()

    def set_selected_song(self, song_id: str) -> None:
        self._selected_song_id = str(song_id or "")
        self.update()

    def set_zoom_percent(self, value: int) -> None:
        self._zoom = max(0.5, min(1.8, int(value) / 100.0))
        self.update()

    def _view_total(self, total: int, timebase: int) -> int:
        # 100% = fit project. Zooming in shortens the visible window while
        # preserving real project ticks and clip positions.
        return max(timebase, int(round(total / max(0.5, self._zoom))))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        left = self.LABEL_W
        right = 5
        width = max(1.0, float(self.width() - left - right))
        lane_area = max(60.0, float(self.height() - self.RULER_H - 1))
        lane_h = lane_area / 3.0
        names = (("▣", "Video"), ("♪", "Audio"), ("T", "Teks"))
        fills = (QColor("#F7FAFE"), QColor("#F5FCFA"), QColor("#FBF8FE"))

        painter.setPen(QPen(QColor("#D7E2EF"), 1))
        painter.drawLine(left, self.RULER_H, self.width() - right, self.RULER_H)
        for index, (icon, label) in enumerate(names):
            y = self.RULER_H + index * lane_h
            painter.fillRect(QRectF(0, y, left, lane_h), QColor("#FFFFFF"))
            painter.fillRect(QRectF(left, y, width, lane_h), fills[index])
            painter.setPen(QPen(QColor("#E1E9F3"), 1))
            painter.drawLine(0, int(y + lane_h), self.width() - right, int(y + lane_h))
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(
                QRectF(17, y, 22, lane_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                icon,
            )
            painter.drawText(
                QRectF(47, y, left - 52, lane_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

        document = self._document
        self._hits = []
        if document is None or not document.playlist.entries:
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(
                QRectF(left, self.RULER_H, width, lane_area),
                Qt.AlignmentFlag.AlignCenter,
                "Timeline preview belum tersedia",
            )
            painter.end()
            return

        segments, total = _timeline_segments(document)
        timebase = max(1, int(document.timebase))
        view_total = self._view_total(total, timebase)

        # Thin ruler like UI-06.
        for index in range(10):
            ratio = index / 9.0
            x = left + width * ratio
            tick = int(view_total * ratio)
            painter.setPen(QPen(QColor("#D8E4F2"), 1))
            painter.drawLine(int(x), self.RULER_H - 4, int(x), self.RULER_H)
            painter.setPen(QColor("#65748A"))
            painter.drawText(
                QRectF(x - 25, 0, 50, self.RULER_H - 2),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                _format_tick(tick, timebase),
            )

        video_y = self.RULER_H + 2
        audio_y = self.RULER_H + lane_h + 2
        text_y = self.RULER_H + lane_h * 2 + 2
        clip_h = max(13.0, lane_h - 4.0)

        for index, (song, start, end) in enumerate(segments):
            if start >= view_total:
                continue
            draw_end = min(end, view_total)
            x0 = left + width * (start / view_total)
            x1 = left + width * (draw_end / view_total)
            clip_w = max(3.0, x1 - x0 - 2.0)
            rect = QRectF(x0 + 1, video_y, clip_w, clip_h)

            pixmap = _cover_pixmap(document, song, max(1, int(rect.width())), max(1, int(rect.height())))
            if pixmap is not None:
                painter.save()
                painter.setClipRect(rect)
                painter.drawPixmap(rect.toRect(), pixmap)
                tint = _clip_color(song.song_id)
                tint.setAlpha(42 + index * 5)
                painter.fillRect(rect, tint)
                painter.restore()
            else:
                painter.fillRect(rect, _clip_color(song.song_id))

            selected = song.song_id == self._selected_song_id
            painter.setPen(QPen(QColor("#1766E8" if selected else "#83AEEA"), 2 if selected else 1))
            painter.drawRoundedRect(rect, 3, 3)
            if rect.width() >= 64:
                title = str(song.display_title or f"Lagu {index + 1}")
                painter.setPen(QColor("#173D69"))
                text = QFontMetrics(painter.font()).elidedText(
                    title,
                    Qt.TextElideMode.ElideRight,
                    max(12, int(rect.width()) - 8),
                )
                title_rect = QRectF(rect.left() + 5, rect.top() + 1, rect.width() - 8, rect.height() * 0.58)
                painter.drawText(
                    title_rect,
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                    text,
                )
                original_font = painter.font()
                duration_font = painter.font()
                if duration_font.pointSizeF() > 0:
                    duration_font.setPointSizeF(max(7.0, duration_font.pointSizeF() - 1.0))
                painter.setFont(duration_font)
                painter.setPen(QColor("#526A86"))
                duration_rect = QRectF(rect.left() + 5, rect.top() + rect.height() * 0.52, rect.width() - 8, rect.height() * 0.42)
                painter.drawText(
                    duration_rect,
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    _format_tick(max(0, end - start), timebase),
                )
                painter.setFont(original_font)
            self._hits.append((song.song_id, rect, start))

        # Album audio overview: real packed/free song segments drive a continuous
        # waveform cue. Boundaries remain visible without fabricating media.
        if segments:
            start_tick = min(start for _song, start, _end in segments)
            end_tick = min(view_total, max(end for _song, _start, end in segments))
            if end_tick > start_tick:
                x0 = left + width * (start_tick / view_total)
                x1 = left + width * (end_tick / view_total)
                rect = QRectF(x0 + 1, audio_y, max(3.0, x1 - x0 - 2), clip_h)
                painter.setPen(QPen(QColor("#41BFA0"), 1))
                painter.setBrush(QColor("#CFF4E8"))
                painter.drawRoundedRect(rect, 3, 3)
                mid = rect.center().y()
                bars = max(30, min(380, int(rect.width() / 3)))
                seed = len(segments) * 17 + int(total // timebase)
                for sample in range(bars):
                    ratio = sample / max(1, bars - 1)
                    x = rect.left() + ratio * rect.width()
                    phase = (sample + seed) * 0.61
                    amplitude = (0.14 + 0.78 * abs(math.sin(phase))) * rect.height() * 0.34
                    painter.drawLine(int(x), int(mid - amplitude), int(x), int(mid + amplitude))
                if rect.width() >= 115:
                    painter.setPen(QColor("#226C5A"))
                    painter.drawText(
                        rect.adjusted(5, 0, -3, 0),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        "Album Full.mp3",
                    )

        # Dynamic song-title layers are represented as one real title event per
        # playlist segment. This is how a song_title template layer behaves over
        # the resolved album, rather than a fabricated static lane.
        has_dynamic_title = any(
            str(getattr(layer, "type", "")).casefold() in {"song_title", "text"}
            for layer in document.layers
        )
        if has_dynamic_title:
            for index, (song, start, end) in enumerate(segments):
                if start >= view_total:
                    continue
                draw_end = min(end, view_total)
                x0 = left + width * (start / view_total)
                x1 = left + width * (draw_end / view_total)
                inset = 10 if (x1 - x0) > 38 else 2
                rect = QRectF(x0 + inset, text_y + 2, max(3.0, x1 - x0 - inset * 2), max(11.0, clip_h - 4))
                painter.setPen(QPen(QColor("#B68BE5"), 1))
                painter.setBrush(QColor("#EADAF9"))
                painter.drawRoundedRect(rect, 3, 3)
                if rect.width() >= 55:
                    title = str(song.display_title or f"Lagu {index + 1}")
                    painter.setPen(QColor("#69458E"))
                    text = QFontMetrics(painter.font()).elidedText(
                        title,
                        Qt.TextElideMode.ElideRight,
                        max(10, int(rect.width()) - 8),
                    )
                    painter.drawText(
                        rect.adjusted(5, 0, -3, 0),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        text,
                    )

        playhead = min(view_total, max(0, self._playhead_tick))
        playhead_x = left + width * (playhead / view_total)
        painter.setPen(QPen(QColor("#1766E8"), 2))
        painter.drawLine(int(playhead_x), self.RULER_H - 2, int(playhead_x), self.height() - 2)
        painter.setBrush(QColor("#1766E8"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(
            __import__("PySide6.QtGui", fromlist=["QPolygonF"]).QPolygonF(
                [
                    __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(playhead_x - 4, self.RULER_H - 4),
                    __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(playhead_x + 4, self.RULER_H - 4),
                    __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(playhead_x, self.RULER_H + 1),
                ]
            )
        )
        painter.end()

    def mousePressEvent(self, event) -> None:
        document = self._document
        if document is None:
            return super().mousePressEvent(event)
        _segments, total = _timeline_segments(document)
        view_total = self._view_total(total, max(1, int(document.timebase)))
        pos = event.position()
        for song_id, rect, _start in reversed(self._hits):
            if rect.contains(pos):
                self._selected_song_id = song_id
                self.song_selected.emit(song_id)
                break
        if pos.x() >= self.LABEL_W:
            width = max(1.0, float(self.width() - self.LABEL_W - 5))
            ratio = min(1.0, max(0.0, (pos.x() - self.LABEL_W) / width))
            self.playhead_requested.emit(int(round(view_total * ratio)))
        self.update()
        super().mousePressEvent(event)


def _preview_document(window):
    live = window.editor_workspace.document()
    try:
        descriptor = window._s07_current_descriptor()
        draft = window._s07_inspector_draft()
        targets = window._s07_scope_targets()
        custom = window._s07_custom_for_descriptor(descriptor)
        return preview_template_document(
            live,
            draft,
            targets,
            custom_template=custom,
        )
    except Exception:
        return live.clone()


def _head_layout(window):
    timeline = window.foundation_shell.timeline
    root = timeline.layout()
    item = root.itemAt(0) if root is not None else None
    return item.layout() if item is not None else None


def _hide_legacy_body_toolbar(window) -> None:
    body_layout = window.foundation_shell.timeline.body.layout()
    if body_layout is None or body_layout.count() == 0:
        return
    first = body_layout.itemAt(0)
    toolbar = first.layout() if first is not None else None
    if toolbar is None:
        return
    for index in range(toolbar.count()):
        item = toolbar.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.hide()


def _install_toolbar(window) -> None:
    if getattr(window, "_post_template_ui06_toolbar", None):
        return
    timeline = window.foundation_shell.timeline
    head = _head_layout(window)
    if head is None:
        return

    split = FAMButton("Split", kind="ghost")
    delete = FAMButton("Hapus", kind="ghost")
    volume_label = QLabel("Volume")
    volume_label.setObjectName("metadata")
    volume = QSlider(Qt.Orientation.Horizontal)
    volume.setRange(0, 100)
    volume.setValue(72)
    volume.setFixedWidth(78)
    zoom_label = QLabel("Zoom")
    zoom_label.setObjectName("metadata")
    zoom = QSlider(Qt.Orientation.Horizontal)
    zoom.setRange(50, 180)
    zoom.setValue(100)
    zoom.setFixedWidth(105)
    previous = FAMButton("◀|", kind="ghost")
    play = FAMButton("▶", kind="primary")
    next_button = FAMButton("|▶", kind="ghost")

    controls = [split, delete, volume_label, volume, zoom_label, zoom, previous, play, next_button]
    for widget in (split, delete, previous, play, next_button):
        widget.setMinimumHeight(25)
        widget.setMaximumHeight(27)
    previous.setFixedWidth(34)
    play.setFixedWidth(34)
    next_button.setFixedWidth(34)

    # Existing head order: collapse, title, message, stretch, zoom controls.
    # Insert UI-06 controls directly after title, eliminating the second toolbar.
    insert_at = 2
    for widget in controls:
        head.insertWidget(insert_at, widget)
        insert_at += 1

    split.clicked.connect(lambda: _split_current(window))
    delete.clicked.connect(lambda: _delete_current(window))
    volume.valueChanged.connect(lambda value: setattr(window, "_post_template_monitor_volume", int(value)))
    zoom.valueChanged.connect(lambda value: _set_zoom(window, int(value)))
    previous.clicked.connect(lambda: _step_playhead(window, -1))
    next_button.clicked.connect(lambda: _step_playhead(window, 1))
    play.clicked.connect(window.editor_workspace.toggle_playback)

    window._post_template_ui06_toolbar = controls
    _hide_legacy_body_toolbar(window)


def _set_route_chrome(window, route: str) -> None:
    active = str(route) == "template"
    timeline = window.foundation_shell.timeline
    _install_toolbar(window)
    for widget in getattr(window, "_post_template_ui06_toolbar", []):
        widget.setVisible(active)
    timeline.collapse_button.setVisible(not active)
    timeline.message.setVisible(not active)
    if active:
        _hide_legacy_body_toolbar(window)


def _install_surface(window) -> None:
    old = getattr(window, "template_timeline_s07", None)
    if old is None or getattr(old, "_post_release_template_ui06", False):
        return
    parent = old.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return

    index = layout.indexOf(old)
    layout.removeWidget(old)
    old.hide()
    old.setParent(None)

    canvas = TemplateTimelineCanvas(parent)
    canvas._post_release_template_ui06 = True
    if index < 0:
        layout.addWidget(canvas, 1)
    else:
        layout.insertWidget(index, canvas, 1)
    window.template_timeline_s07 = canvas

    canvas.playhead_requested.connect(window.editor_workspace.set_playhead)
    canvas.song_selected.connect(lambda song_id: setattr(window, "_post_template_selected_song_id", str(song_id)))


def _refresh_surface(window) -> None:
    _install_surface(window)
    _install_toolbar(window)
    canvas = getattr(window, "template_timeline_s07", None)
    if canvas is None or not getattr(canvas, "_post_release_template_ui06", False):
        return
    document = _preview_document(window)
    canvas.set_document(document)
    canvas.set_playhead(window.editor_workspace.session.playhead_tick)

    valid = set(document.song_map())
    selected = str(getattr(window, "_post_template_selected_song_id", "") or "")
    if selected not in valid:
        selected = str(getattr(window, "_s06_primary_song_id", "") or "")
    if selected not in valid:
        selected = document.playlist.entries[0].song_id if document.playlist.entries else ""
    window._post_template_selected_song_id = selected
    canvas.set_selected_song(selected)


def _set_zoom(window, value: int) -> None:
    canvas = getattr(window, "template_timeline_s07", None)
    if canvas is not None and getattr(canvas, "_post_release_template_ui06", False):
        canvas.set_zoom_percent(value)


def _song_at_playhead(window):
    document = window.editor_workspace.document()
    tick = int(window.editor_workspace.session.playhead_tick)
    segments, _total = _timeline_segments(document)
    for song, start, end in segments:
        if start <= tick < end:
            return song
    return document.playlist.entries[0] if document.playlist.entries else None


def _split_current(window) -> None:
    song = _song_at_playhead(window)
    if song is None:
        return
    tick = int(window.editor_workspace.session.playhead_tick)
    try:
        window.editor_workspace.session.controller.dispatch(SplitSongAtTick(song.song_id, tick))
        window.editor_workspace._after_edit()
        window._post_template_selected_song_id = song.song_id
    except Exception:
        # Existing command validation remains authoritative; invalid boundary
        # splits are simply rejected without partial mutation.
        _refresh_surface(window)


def _delete_current(window) -> None:
    document = window.editor_workspace.document()
    if not document.playlist.entries:
        return
    selected = str(getattr(window, "_post_template_selected_song_id", "") or "")
    if selected not in document.song_map():
        song = _song_at_playhead(window)
        selected = song.song_id if song is not None else ""
    if not selected:
        return
    entries = deepcopy([song for song in document.playlist.entries if song.song_id != selected])
    try:
        window.editor_workspace.session.controller.dispatch(SetPlaylistEntries(entries))
        window.editor_workspace._after_edit()
        window._post_template_selected_song_id = entries[0].song_id if entries else ""
    except Exception:
        _refresh_surface(window)


def _step_playhead(window, direction: int) -> None:
    document = window.editor_workspace.document()
    segments, total = _timeline_segments(document)
    if not segments:
        return
    current = int(window.editor_workspace.session.playhead_tick)
    boundaries = sorted({0, total, *(start for _song, start, _end in segments)})
    if direction < 0:
        choices = [tick for tick in boundaries if tick < current]
        target = choices[-1] if choices else 0
    else:
        choices = [tick for tick in boundaries if tick > current]
        target = choices[0] if choices else total
    window.editor_workspace.set_playhead(int(target))


def install_post_release_template_timeline_surface() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_refresh_timeline = Window._s07_refresh_timeline

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_toolbar(self)
        _install_surface(self)
        self.foundation_state.workspace_changed.connect(lambda route: _set_route_chrome(self, str(route)))
        _set_route_chrome(self, getattr(self.foundation_state, "workspace", ""))
        _refresh_surface(self)

    def refresh_ui06_timeline(self) -> None:
        _install_surface(self)
        canvas = getattr(self, "template_timeline_s07", None)
        if canvas is None or not getattr(canvas, "_post_release_template_ui06", False):
            previous_refresh_timeline(self)
            return
        _refresh_surface(self)

    Window.__init__ = wrapped_init
    Window._s07_refresh_timeline = refresh_ui06_timeline
    _installed = True
