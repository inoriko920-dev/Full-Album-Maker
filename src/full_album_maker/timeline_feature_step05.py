from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog

from .editor_commands import SetPlaylistEntries
from .editor_interaction_commands import SetLayerEnabled, SetLayerLocked
from .free_timeline import SetPlaylistTimingMode, SetSongFreeTiming
from .timeline_audio_commands import ApplySongClipProperties, SplitSongAtTick
from .timeline_layer_commands import ApplyLayerClipProperties
from .timeline_precision import (
    AddTimelineMarker,
    DeleteGapAtTick,
    RippleMoveSong,
    SetSongMix,
    SplitLayerAtTick,
    song_mix,
    timeline_markers,
)
from .timeline_resolver import TimelineResolver
from .timeline_workspace_step05 import (
    TimelineClipInspector,
    TimelineContextWidget,
    TimelinePrecisionPanel,
    TimelinePreviewWorkspace,
    lane_for_layer,
)

_installed = False
_original_init: Any = None


def _install_widgets(self) -> None:
    self._s05_selected_song_id = ""
    self._s05_selected_layer_id = ""
    self._s05_ripple = False

    self.timeline_workspace_s05 = TimelinePreviewWorkspace()
    index = self.foundation_shell.workspace_stack._index["timeline"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.timeline_workspace_s05)

    context_layout = self.foundation_shell.context.layout()
    self._s05_context_old = [
        context_layout.itemAt(i).widget()
        for i in range(context_layout.count())
        if context_layout.itemAt(i).widget() is not None
    ]
    self.timeline_context_s05 = TimelineContextWidget()
    self.timeline_context_s05.hide()
    context_layout.addWidget(self.timeline_context_s05, 1)

    self.timeline_inspector_s05 = TimelineClipInspector()
    self._inspector_router.addWidget(self.timeline_inspector_s05)

    self.timeline_precision_s05 = TimelinePrecisionPanel()
    body_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    body_layout.addWidget(self.timeline_precision_s05, 1)
    self.timeline_precision_s05.hide()


def _connect_widgets(self) -> None:
    panel = self.timeline_precision_s05
    canvas = panel.canvas
    panel.mode_requested.connect(self._s05_mode)
    panel.split_requested.connect(self._s05_split)
    panel.delete_gap_requested.connect(self._s05_delete_gap)
    panel.ripple_changed.connect(self._s05_ripple_changed)
    panel.snap_changed.connect(self._s05_snap_changed)
    panel.marker_requested.connect(self._s05_add_marker)
    panel.zoom_requested.connect(self._s05_zoom)
    panel.fit_requested.connect(canvas.fit_project)

    canvas.playhead_requested.connect(self._s05_set_playhead)
    canvas.song_selected.connect(self._s05_select_song)
    canvas.layer_selected.connect(self._s05_select_layer)
    canvas.song_move_requested.connect(self._s05_move_song)

    self.timeline_context_s05.lane_action_requested.connect(self._s05_lane_action)
    self.timeline_context_s05.marker_selected.connect(self._s05_select_marker)
    self.timeline_context_s05.clip_selected.connect(self._s05_select_clip)
    self.timeline_inspector_s05.song_changed.connect(self._s05_apply_song)
    self.timeline_inspector_s05.layer_changed.connect(self._s05_apply_layer)

    self.timeline_workspace_s05.previous_requested.connect(lambda: self._s05_step_song(-1))
    self.timeline_workspace_s05.next_requested.connect(lambda: self._s05_step_song(1))
    self.timeline_workspace_s05.play_requested.connect(self.editor_workspace.toggle_playback)
    self.timeline_workspace_s05.fullscreen_requested.connect(self._s05_fullscreen)

    self.foundation_state.workspace_changed.connect(self._s05_route)
    self.editor_workspace.documentChanged.connect(self._s05_document_changed)
    self.editor_workspace.play_timer.timeout.connect(self._s05_playback_sync)


def _hide_older_timeline_surfaces(self) -> None:
    self.foundation_shell.timeline.canvas.setVisible(False)
    if hasattr(self, "media_timeline_canvas"):
        self.media_timeline_canvas.setVisible(False)
    if hasattr(self, "album_timeline_canvas"):
        self.album_timeline_canvas.setVisible(False)
    if hasattr(self, "_s03_timeline_old"):
        self._s03_timeline_old.setVisible(False)
    # STEP01 placeholder controls must not sit above the precision toolbar.
    mode = getattr(self.foundation_shell.timeline, "mode", None)
    if mode is not None:
        mode.setVisible(False)
    parent = self.foundation_shell.timeline.canvas.parentWidget()
    for button in parent.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton):
        if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
            button.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "timeline"
    self.timeline_context_s05.setVisible(active)
    self.timeline_precision_s05.setVisible(active)
    if not active:
        if self._inspector_router.currentWidget() is self.timeline_inspector_s05:
            self._inspector_router.setCurrentIndex(1)
        return

    for widget in self._s05_context_old:
        widget.setVisible(False)
    if hasattr(self, "media_context"):
        self.media_context.setVisible(False)
    if hasattr(self, "album_context"):
        self.album_context.setVisible(False)
    _hide_older_timeline_surfaces(self)
    self._inspector_router.setCurrentWidget(self.timeline_inspector_s05)
    self.foundation_shell.timeline.set_collapsed(False)
    self._s05_refresh()


def _document_changed(self, _document) -> None:
    if hasattr(self, "timeline_precision_s05"):
        self._s05_refresh()


def _refresh(self) -> None:
    if not hasattr(self, "timeline_precision_s05"):
        return
    document = self.editor_workspace.document()
    session = self.editor_workspace.session
    self.timeline_workspace_s05.apply_document(document)
    self.timeline_workspace_s05.set_playhead(document, session.playhead_tick)
    self.timeline_context_s05.apply_document(document)
    self.timeline_precision_s05.apply_document(
        document,
        session.playhead_tick,
        ripple=self._s05_ripple,
        snap=session.snap_enabled,
    )
    self.timeline_precision_s05.canvas.set_selection(
        song_id=self._s05_selected_song_id,
        layer_id=self._s05_selected_layer_id,
    )
    if self._s05_selected_song_id in document.song_map():
        self.timeline_inspector_s05.set_song(document, self._s05_selected_song_id)
    elif self._s05_selected_layer_id in document.layer_map():
        self.timeline_inspector_s05.set_layer(document, self._s05_selected_layer_id)
        self.timeline_workspace_s05.preview.set_selected_layer(self._s05_selected_layer_id)
    else:
        self._s05_selected_song_id = ""
        self._s05_selected_layer_id = ""
        self.timeline_inspector_s05.set_none()
        self.timeline_workspace_s05.preview.set_selected_layer(None)
    self.foundation_shell.refresh_commands()


def _set_playhead(self, tick: int) -> None:
    self.editor_workspace.set_playhead(int(tick))
    document = self.editor_workspace.document()
    current = self.editor_workspace.session.playhead_tick
    self.timeline_workspace_s05.set_playhead(document, current)
    self.timeline_precision_s05.canvas.set_playhead(current)
    end = TimelineResolver().resolve(document).duration_tick
    from .timeline_workspace_step05 import _timecode
    self.timeline_precision_s05.playhead_label.setText(f"{_timecode(current)} / {_timecode(end)}")


def _select_song(self, song_id: str) -> None:
    document = self.editor_workspace.document()
    if song_id not in document.song_map():
        return
    self._s05_selected_song_id = song_id
    self._s05_selected_layer_id = ""
    self.editor_workspace.session.select_one(None)
    self.timeline_inspector_s05.set_song(document, song_id)
    self.timeline_precision_s05.canvas.set_selection(song_id=song_id)
    self.timeline_workspace_s05.preview.set_selected_layer(None)


def _select_layer(self, layer_id: str) -> None:
    document = self.editor_workspace.document()
    if layer_id not in document.layer_map():
        return
    self._s05_selected_layer_id = layer_id
    self._s05_selected_song_id = ""
    self.editor_workspace.session.select_one(layer_id)
    self.timeline_inspector_s05.set_layer(document, layer_id)
    self.timeline_precision_s05.canvas.set_selection(layer_id=layer_id)
    self.timeline_workspace_s05.preview.set_selected_layer(layer_id)


def _select_marker(self, marker_id: str) -> None:
    marker = next((item for item in timeline_markers(self.editor_workspace.document()) if item.marker_id == marker_id), None)
    if marker is not None:
        self._s05_set_playhead(marker.tick)


def _select_clip(self, value: str) -> None:
    if value.startswith("layer:"):
        self._s05_select_layer(value.split(":", 1)[1])
    else:
        self._s05_select_song(value)


def _mode(self, mode: str) -> None:
    document = self.editor_workspace.document()
    if mode == document.playlist.mode:
        return
    try:
        self.editor_workspace.session.controller.dispatch(SetPlaylistTimingMode(mode))
        self.editor_workspace._after_edit()
        self._s05_status("Free Timeline aktif; posisi lama dipertahankan." if mode == "free" else "Packed aktif; gap dan crossfade dikompakkan.")
    except Exception as exc:
        self._s05_status(f"Ubah mode Timeline gagal: {exc}")
        self._s05_refresh()


def _split(self) -> None:
    tick = self.editor_workspace.session.playhead_tick
    try:
        if self._s05_selected_song_id:
            command = SplitSongAtTick(self._s05_selected_song_id, tick)
            self.editor_workspace.session.controller.dispatch(command)
            self._s05_selected_song_id = command.new_song_id or self._s05_selected_song_id
        elif self._s05_selected_layer_id:
            command = SplitLayerAtTick(self._s05_selected_layer_id, tick)
            self.editor_workspace.session.controller.dispatch(command)
            self._s05_selected_layer_id = command.new_layer_id or self._s05_selected_layer_id
        else:
            self._s05_status("Pilih clip terlebih dahulu sebelum Split.")
            return
        self.editor_workspace._after_edit()
        self._s05_status("Split selesai sebagai satu transaksi Undo.")
    except Exception as exc:
        self._s05_status(f"Split gagal: {exc}")
        self._s05_refresh()


def _delete_gap(self) -> None:
    try:
        self.editor_workspace.session.controller.dispatch(
            DeleteGapAtTick(self.editor_workspace.session.playhead_tick)
        )
        self.editor_workspace._after_edit()
        self._s05_status("Gap di playhead dihapus; clip downstream digeser satu transaksi Undo.")
    except Exception as exc:
        self._s05_status(f"Delete Gap gagal: {exc}")
        self._s05_refresh()


def _ripple_changed(self, enabled: bool) -> None:
    self._s05_ripple = bool(enabled)


def _snap_changed(self, enabled: bool) -> None:
    self.editor_workspace.session.snap_enabled = bool(enabled)


def _add_marker(self) -> None:
    document = self.editor_workspace.document()
    default = f"Marker {len(timeline_markers(document)) + 1}"
    label, ok = QInputDialog.getText(self, "Tambah Marker", "Nama marker:", text=default)
    if not ok or not label.strip():
        return
    try:
        self.editor_workspace.session.controller.dispatch(
            AddTimelineMarker(self.editor_workspace.session.playhead_tick, label.strip())
        )
        self.editor_workspace._after_edit()
        self._s05_status(f"Marker '{label.strip()}' ditambahkan.")
    except Exception as exc:
        self._s05_status(f"Tambah marker gagal: {exc}")


def _zoom(self, direction: int) -> None:
    canvas = self.timeline_precision_s05.canvas
    factor = 1.22 if int(direction) > 0 else 1 / 1.22
    canvas.set_pixels_per_second(canvas._pixels_per_second * factor)


def _snap_song_tick(self, song_id: str, target_tick: int, gesture_pps: float) -> int:
    value = max(0, int(target_tick))
    session = self.editor_workspace.session
    if not session.snap_enabled:
        return value
    document = self.editor_workspace.document()
    resolved = TimelineResolver().resolve(document)
    candidates = {0, resolved.duration_tick, session.playhead_tick}
    for song in resolved.songs:
        if song.song_id == song_id:
            continue
        candidates.add(song.start_tick)
        candidates.add(song.end_tick)
    for layer in resolved.layers:
        for interval in layer.intervals:
            candidates.add(interval.start_tick)
            candidates.add(interval.end_tick)
    candidates.update(marker.tick for marker in timeline_markers(document))
    threshold = int(round((session.snap_threshold_px / max(1.0, float(gesture_pps))) * document.timebase))
    nearest = min(candidates, key=lambda tick: abs(tick - value)) if candidates else value
    return nearest if abs(nearest - value) <= threshold else value


def _move_song(self, song_id: str, target_tick: int, gesture_pps: float) -> None:
    document = self.editor_workspace.document()
    song = document.song_map().get(song_id)
    if song is None or document.playlist.mode != "free":
        self._s05_status("Drag lagu hanya tersedia pada Free Timeline.")
        return
    target = self._s05_snap_song_tick(song_id, target_tick, gesture_pps)
    try:
        command = (
            RippleMoveSong(song_id, target)
            if self._s05_ripple
            else SetSongFreeTiming(song_id, target, song.crossfade_in_tick)
        )
        self.editor_workspace.session.controller.dispatch(command)
        self.editor_workspace._after_edit()
        self._s05_selected_song_id = song_id
        self._s05_status("Posisi lagu dipindahkan" + (" dengan Ripple." if self._s05_ripple else "."))
    except Exception as exc:
        self._s05_status(f"Pindah lagu gagal: {exc}")
        self._s05_refresh()


def _apply_song(self, song_id: str, start: int, duration: int, fade_in: int, fade_out: int, crossfade: int, gain: float, locked: bool) -> None:
    try:
        self.editor_workspace.session.controller.dispatch(
            ApplySongClipProperties(song_id, start, duration, fade_in, fade_out, crossfade, gain, locked)
        )
        self.editor_workspace._after_edit()
        self._s05_selected_song_id = song_id
        self._s05_status("Properti clip audio diterapkan sebagai satu transaksi Undo.")
    except Exception as exc:
        self._s05_status(f"Properti clip audio ditolak: {exc}")
        self._s05_refresh()


def _apply_layer(self, layer_id: str, start: int, duration: int, locked: bool) -> None:
    try:
        self.editor_workspace.session.controller.dispatch(
            ApplyLayerClipProperties(layer_id, start, duration, locked)
        )
        self.editor_workspace._after_edit()
        self._s05_selected_layer_id = layer_id
        self._s05_status("Properti layer diterapkan sebagai satu transaksi Undo.")
    except Exception as exc:
        self._s05_status(f"Properti layer ditolak: {exc}")
        self._s05_refresh()


def _lane_action(self, lane: str, action: str, value: bool) -> None:
    document = self.editor_workspace.document()
    commands = []
    if lane == "A1":
        if action == "visible":
            entries = deepcopy(document.playlist.entries)
            for song in entries:
                song.enabled = bool(value)
            commands = [SetPlaylistEntries(entries)]
        elif action == "lock":
            for song in document.playlist.entries:
                mix = song_mix(document, song.song_id)
                commands.append(
                    SetSongMix(
                        song.song_id,
                        song.gain,
                        mix["fade_in_tick"],
                        mix["fade_out_tick"],
                        bool(value),
                    )
                )
    elif lane != "A2":
        layers = [layer for layer in document.layers if lane_for_layer(layer) == lane]
        if action == "visible":
            commands = [SetLayerEnabled(layer.layer_id, bool(value)) for layer in layers]
        elif action == "lock":
            commands = [SetLayerLocked(layer.layer_id, bool(value)) for layer in layers]
    if not commands:
        return
    try:
        self.editor_workspace.session.controller.dispatch(commands)
        self.editor_workspace._after_edit()
        self._s05_status(f"{lane}: {'lock' if action == 'lock' else 'visibility'} diperbarui satu transaksi Undo.")
    except Exception as exc:
        self._s05_status(f"Ubah track {lane} gagal: {exc}")
        self._s05_refresh()


def _step_song(self, direction: int) -> None:
    resolved = TimelineResolver().resolve(self.editor_workspace.document())
    if not resolved.songs:
        return
    current = self.editor_workspace.session.playhead_tick
    starts = [song.start_tick for song in resolved.songs]
    if direction > 0:
        target = next((tick for tick in starts if tick > current), starts[-1])
    else:
        prior = [tick for tick in starts if tick < current]
        target = prior[-1] if prior else starts[0]
    self._s05_set_playhead(target)


def _fullscreen(self) -> None:
    if self.isFullScreen():
        self.showNormal()
    else:
        self.showFullScreen()


def _playback_sync(self) -> None:
    if getattr(self, "foundation_state", None) is None or self.foundation_state.workspace != "timeline":
        return
    document = self.editor_workspace.document()
    tick = self.editor_workspace.session.playhead_tick
    self.timeline_workspace_s05.set_playhead(document, tick)
    self.timeline_precision_s05.canvas.set_playhead(tick)


def _status(self, message: str) -> None:
    try:
        self.editor_workspace._set_status(message)
    except Exception:
        pass
    self.foundation_state.set_status(project_context=message)


def install_step05_timeline() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s05_refresh()
        self._s05_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s05_route(route)

        # STEP03 and STEP04 install their own deferred route guards. Timeline is
        # layered last, therefore this callback intentionally runs after them.
        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s05_refresh = _refresh
    Window._s05_route = _route
    Window._s05_document_changed = _document_changed
    Window._s05_set_playhead = _set_playhead
    Window._s05_select_song = _select_song
    Window._s05_select_layer = _select_layer
    Window._s05_select_marker = _select_marker
    Window._s05_select_clip = _select_clip
    Window._s05_mode = _mode
    Window._s05_split = _split
    Window._s05_delete_gap = _delete_gap
    Window._s05_ripple_changed = _ripple_changed
    Window._s05_snap_changed = _snap_changed
    Window._s05_add_marker = _add_marker
    Window._s05_zoom = _zoom
    Window._s05_snap_song_tick = _snap_song_tick
    Window._s05_move_song = _move_song
    Window._s05_apply_song = _apply_song
    Window._s05_apply_layer = _apply_layer
    Window._s05_lane_action = _lane_action
    Window._s05_step_song = _step_song
    Window._s05_fullscreen = _fullscreen
    Window._s05_playback_sync = _playback_sync
    Window._s05_status = _status
    _installed = True
