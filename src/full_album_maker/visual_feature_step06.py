from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .playlist_commands import SetSongVisual
from .timeline_resolver import TimelineResolver
from .visual_assignment import (
    RelinkMediaAsset,
    assignment_status,
    available_visual_assets,
    deterministic_auto_match_commands,
    validate_playback_eligibility,
)
from .visual_precision import ApplySongVisualSettings, SetSongVisualSettings, visual_settings_for_song
from .visual_workspace_step06 import (
    VisualAlignmentCanvas,
    VisualInspector,
    VisualPreviewWorkspace,
    VisualSongContext,
)


_installed = False
_original_init: Any = None


def _install_widgets(self) -> None:
    self._s06_selected_ids: set[str] = set()
    self._s06_primary_song_id = ""

    self.visual_workspace_s06 = VisualPreviewWorkspace()
    index = self.foundation_shell.workspace_stack._index["visual"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.visual_workspace_s06)

    context_layout = self.foundation_shell.context.layout()
    self._s06_context_old = [
        context_layout.itemAt(i).widget()
        for i in range(context_layout.count())
        if context_layout.itemAt(i).widget() is not None
    ]
    self.visual_context_s06 = VisualSongContext()
    self.visual_context_s06.hide()
    context_layout.addWidget(self.visual_context_s06, 1)

    self.visual_inspector_s06 = VisualInspector()
    self._inspector_router.addWidget(self.visual_inspector_s06)

    self.visual_timeline_s06 = VisualAlignmentCanvas()
    timeline_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    timeline_layout.addWidget(self.visual_timeline_s06, 1)
    self.visual_timeline_s06.hide()


def _connect_widgets(self) -> None:
    self.visual_context_s06.selection_changed.connect(self._s06_selection_changed)
    self.visual_context_s06.filter_changed.connect(lambda _key: self._s06_refresh())
    self.visual_inspector_s06.choose_image_requested.connect(lambda: self._s06_choose_visual("image"))
    self.visual_inspector_s06.choose_video_requested.connect(lambda: self._s06_choose_visual("video"))
    self.visual_inspector_s06.clear_requested.connect(self._s06_clear_visual)
    self.visual_inspector_s06.relink_requested.connect(self._s06_relink)
    self.visual_inspector_s06.auto_match_requested.connect(self._s06_auto_match)
    self.visual_inspector_s06.apply_requested.connect(self._s06_apply_current)
    self.visual_inspector_s06.apply_selected_requested.connect(self._s06_apply_selected)
    self.visual_workspace_s06.previous_requested.connect(lambda: self._s06_step_song(-1))
    self.visual_workspace_s06.next_requested.connect(lambda: self._s06_step_song(1))
    self.visual_workspace_s06.play_requested.connect(self.editor_workspace.toggle_playback)
    self.foundation_state.workspace_changed.connect(self._s06_route)
    self.editor_workspace.documentChanged.connect(self._s06_document_changed)
    self.editor_workspace.play_timer.timeout.connect(self._s06_playback_sync)


def _hide_other_surfaces(self) -> None:
    for widget in self._s06_context_old:
        widget.setVisible(False)
    for name in (
        "media_context",
        "album_context",
        "timeline_context_s05",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    for name in (
        "media_timeline_canvas",
        "album_timeline_canvas",
        "timeline_precision_s05",
        "_s03_timeline_old",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    self.foundation_shell.timeline.canvas.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "visual"
    self.visual_context_s06.setVisible(active)
    self.visual_timeline_s06.setVisible(active)
    if not active:
        if self._inspector_router.currentWidget() is self.visual_inspector_s06:
            self._inspector_router.setCurrentIndex(1)
        return
    _hide_other_surfaces(self)
    self._inspector_router.setCurrentWidget(self.visual_inspector_s06)
    self.foundation_shell.timeline.set_collapsed(False)
    document = self.editor_workspace.document()
    if self._s06_primary_song_id not in document.song_map() and document.playlist.entries:
        self._s06_primary_song_id = document.playlist.entries[0].song_id
        self._s06_selected_ids = {self._s06_primary_song_id}
    self._s06_refresh()


def _document_changed(self, _document) -> None:
    if hasattr(self, "visual_workspace_s06"):
        self._s06_refresh()


def _refresh(self) -> None:
    if not hasattr(self, "visual_workspace_s06"):
        return
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    self._s06_selected_ids.intersection_update(valid)
    if self._s06_primary_song_id not in valid:
        self._s06_primary_song_id = next(iter(self._s06_selected_ids), "")
    if not self._s06_primary_song_id and document.playlist.entries:
        self._s06_primary_song_id = document.playlist.entries[0].song_id
        self._s06_selected_ids.add(self._s06_primary_song_id)
    self.visual_context_s06.apply_document(document)
    self.visual_context_s06.set_selection(self._s06_selected_ids, self._s06_primary_song_id)
    tick = self.editor_workspace.session.playhead_tick
    self.visual_workspace_s06.apply_state(document, self._s06_primary_song_id, tick)
    self.visual_inspector_s06.set_song(document, self._s06_primary_song_id, len(self._s06_selected_ids))
    self.visual_timeline_s06.set_state(document, self._s06_selected_ids, tick)
    self.foundation_shell.refresh_commands()


def _selection_changed(self, song_ids, primary: str) -> None:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    selected = {str(value) for value in (song_ids or ()) if str(value) in valid}
    if primary in valid:
        self._s06_primary_song_id = primary
    elif self._s06_primary_song_id not in valid:
        self._s06_primary_song_id = next(iter(selected), "")
    if self._s06_primary_song_id:
        selected.add(self._s06_primary_song_id)
    self._s06_selected_ids = selected
    if self._s06_primary_song_id:
        event = next(
            (item for item in TimelineResolver().resolve(document).songs if item.song_id == self._s06_primary_song_id),
            None,
        )
        if event is not None:
            self.editor_workspace.set_playhead(event.start_tick)
    self._s06_refresh()


def _dispatch(self, commands, message: str) -> bool:
    try:
        self.editor_workspace.dispatch_external(commands, message=message)
        self.foundation_shell.refresh_commands()
        return True
    except Exception as exc:
        QMessageBox.warning(self, "Visual", f"Perubahan tidak dapat diterapkan:\n{exc}")
        self._s06_refresh()
        return False


def _choose_asset_id(self, kind: str) -> str | None:
    document = self.editor_workspace.document()
    assets = available_visual_assets(document, kind, require_existing=True)
    if not assets:
        QMessageBox.information(
            self,
            "Visual",
            "Belum ada media yang sesuai dan tersedia. Impor media melalui workspace Media terlebih dahulu.",
        )
        return None
    labels: list[str] = []
    lookup: dict[str, str] = {}
    for index, asset in enumerate(assets, start=1):
        label = f"{index:03d} • {asset.original_name or Path(asset.locator).name}"
        labels.append(label)
        lookup[label] = asset.asset_id
    title = "Pilih Foto" if kind == "image" else "Pilih Video"
    value, ok = QInputDialog.getItem(self, title, "Media:", labels, 0, False)
    return lookup.get(str(value)) if ok else None


def _choose_visual(self, kind: str) -> None:
    song_id = self._s06_primary_song_id
    document = self.editor_workspace.document()
    if song_id not in document.song_map():
        return
    asset_id = self._s06_choose_asset_id(kind)
    if not asset_id:
        return
    commands = [SetSongVisual(song_id, asset_id)]
    if kind == "image":
        settings = visual_settings_for_song(document, song_id)
        if settings["loop_video"] or settings["freeze_end"]:
            settings["loop_video"] = False
            settings["freeze_end"] = False
            commands.append(SetSongVisualSettings(song_id, settings))
    self._s06_dispatch(commands, "Visual lagu diperbarui.")


def _clear_visual(self) -> None:
    song_id = self._s06_primary_song_id
    if song_id:
        self._s06_dispatch(SetSongVisual(song_id, None), "Visual lagu dilepas tanpa menghapus media sumber.")


def _relink(self) -> None:
    document = self.editor_workspace.document()
    song_id = self._s06_primary_song_id
    if song_id not in document.song_map():
        return
    status = assignment_status(document, song_id)
    if status.state != "missing" or not status.asset_id:
        QMessageBox.information(self, "Relink Visual", "Source Visual saat ini tidak berstatus Missing.")
        return
    if status.source_kind == "video":
        file_filter = "Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)"
    else:
        file_filter = "Gambar (*.jpg *.jpeg *.png *.webp *.bmp)"
    start = str(Path(status.locator).parent) if status.locator else ""
    path, _ = QFileDialog.getOpenFileName(self, "Relink Visual", start, file_filter)
    if path:
        self._s06_dispatch(RelinkMediaAsset(status.asset_id, path), "Source Visual berhasil direlink dengan identity yang sama.")


def _auto_match(self) -> None:
    document = self.editor_workspace.document()
    targets = self._s06_selected_ids or ({self._s06_primary_song_id} if self._s06_primary_song_id else set())
    commands = deterministic_auto_match_commands(document, targets, overwrite_existing=False)
    if not commands:
        QMessageBox.information(self, "Auto Match Visual", "Tidak ada target kosong atau media valid yang dapat dipasangkan.")
        return
    self._s06_dispatch(list(commands), f"Auto Match deterministik diterapkan ke {len(commands)} lagu kosong.")


def _apply_current(self, settings) -> None:
    song_id = self._s06_primary_song_id
    if not song_id:
        return
    document = self.editor_workspace.document()
    try:
        validate_playback_eligibility(
            document,
            song_id,
            loop_video=bool(settings.get("loop_video")),
            freeze_end=bool(settings.get("freeze_end")),
        )
    except Exception as exc:
        QMessageBox.warning(self, "Visual", str(exc))
        return
    self._s06_dispatch(SetSongVisualSettings(song_id, dict(settings)), "Properti Visual lagu diterapkan sebagai satu Undo unit.")


def _apply_selected(self, settings) -> None:
    document = self.editor_workspace.document()
    targets = tuple(song.song_id for song in document.playlist.entries if song.song_id in self._s06_selected_ids)
    if not targets and self._s06_primary_song_id:
        targets = (self._s06_primary_song_id,)
    if not targets:
        return
    try:
        for song_id in targets:
            validate_playback_eligibility(
                document,
                song_id,
                loop_video=bool(settings.get("loop_video")),
                freeze_end=bool(settings.get("freeze_end")),
            )
    except Exception as exc:
        QMessageBox.warning(
            self,
            "Apply to Selected",
            f"Bulk Apply dibatalkan sebelum mutation karena satu target tidak valid:\n{exc}",
        )
        return
    self._s06_dispatch(
        ApplySongVisualSettings(targets, dict(settings)),
        f"Properti Visual diterapkan atomically ke {len(targets)} lagu. Source visual tidak dicopy.",
    )


def _step_song(self, direction: int) -> None:
    document = self.editor_workspace.document()
    entries = document.playlist.entries
    if not entries:
        return
    ids = [song.song_id for song in entries]
    try:
        index = ids.index(self._s06_primary_song_id)
    except ValueError:
        index = 0
    index = max(0, min(len(ids) - 1, index + int(direction)))
    target = ids[index]
    self._s06_selected_ids = {target}
    self._s06_primary_song_id = target
    event = next((item for item in TimelineResolver().resolve(document).songs if item.song_id == target), None)
    if event is not None:
        self.editor_workspace.set_playhead(event.start_tick)
    self._s06_refresh()


def _playback_sync(self) -> None:
    if getattr(self, "foundation_state", None) is None or self.foundation_state.workspace != "visual":
        return
    document = self.editor_workspace.document()
    tick = self.editor_workspace.session.playhead_tick
    resolved = TimelineResolver().resolve(document)
    primary_event = next((item for item in resolved.songs if item.song_id == self._s06_primary_song_id), None)
    if primary_event is None or not (primary_event.start_tick <= tick <= primary_event.end_tick):
        active = next((item for item in resolved.songs if item.start_tick <= tick < item.end_tick), None)
        if active is not None:
            self._s06_primary_song_id = active.song_id
            self._s06_selected_ids = {active.song_id}
            self.visual_context_s06.set_selection(self._s06_selected_ids, active.song_id)
    self.visual_workspace_s06.apply_state(document, self._s06_primary_song_id, tick)
    self.visual_timeline_s06.set_state(document, self._s06_selected_ids, tick)


def install_step06_visual() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s06_refresh()
        self._s06_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s06_route(route)

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s06_refresh = _refresh
    Window._s06_route = _route
    Window._s06_document_changed = _document_changed
    Window._s06_selection_changed = _selection_changed
    Window._s06_dispatch = _dispatch
    Window._s06_choose_asset_id = _choose_asset_id
    Window._s06_choose_visual = _choose_visual
    Window._s06_clear_visual = _clear_visual
    Window._s06_relink = _relink
    Window._s06_auto_match = _auto_match
    Window._s06_apply_current = _apply_current
    Window._s06_apply_selected = _apply_selected
    Window._s06_step_song = _step_song
    Window._s06_playback_sync = _playback_sync
    _installed = True
