from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QInputDialog, QMessageBox

from .album_commands import SetAlbumCover, SetAlbumDefaultTransition, SetAlbumTitle, SetSongTransition
from .album_model import move_selection_to_edge, safe_cover_matches
from .album_workspace import AlbumContextWidget, AlbumMassToolsWidget, AlbumTimelineOverviewCanvas, AlbumWorkspace
from .editor_commands import ReorderSongs, SetPlaylistEntries
from .editor_models import ProjectDocument
from .legacy_sync_v2 import sync_legacy_media
from .playlist_commands import MoveSong, SetSongCover, SetSongVisual
from .playlist_feature import set_active_audio_paths
from .playlist_service_v2 import PlaylistServiceV2
from .project import Project


_installed = False
_originals: dict[str, Any] = {}
ALBUM_DOCUMENT_KEY = "album_document_v2"


def _project_to_dict(self: Project) -> dict:
    data = _originals["project_to_dict"](self)
    raw = getattr(self, "_album_document_v2", None)
    if isinstance(raw, ProjectDocument):
        raw = raw.to_dict()
    if isinstance(raw, dict):
        # Validate before persistence so a corrupt editor payload never gets silently saved.
        document = ProjectDocument.from_dict(raw)
        data[ALBUM_DOCUMENT_KEY] = document.to_dict()
    return data


def _project_from_dict(cls, data: dict) -> Project:
    project = _originals["project_from_dict_bound"](data)
    raw = data.get(ALBUM_DOCUMENT_KEY) if isinstance(data, dict) else None
    if raw is not None:
        if not isinstance(raw, dict):
            raise ValueError("album_document_v2 proyek tidak valid.")
        project._album_document_v2 = ProjectDocument.from_dict(raw).to_dict()
    return project


def _active_document(self) -> ProjectDocument:
    return self.editor_workspace.document()


def _capture_document(self) -> None:
    if not hasattr(self, "editor_workspace"):
        return
    document = self.editor_workspace.document()
    self.project._album_document_v2 = document.to_dict()
    assets = document.asset_map()
    active_paths: list[str] = []
    for song in document.playlist.entries:
        asset = assets.get(song.asset_id)
        if asset is not None and asset.kind == "audio":
            active_paths.append(asset.locator)
    set_active_audio_paths(self.project, active_paths)


def _restore_document(self) -> None:
    if not hasattr(self, "editor_workspace"):
        return
    raw = getattr(self.project, "_album_document_v2", None)
    if isinstance(raw, ProjectDocument):
        candidate = raw.clone()
    elif isinstance(raw, dict):
        candidate = ProjectDocument.from_dict(raw)
    else:
        candidate = self.editor_workspace.document()
    merged, _changed = sync_legacy_media(candidate, self.project)
    if not merged.playlist.entries:
        entries = PlaylistServiceV2.use_all_audio(merged)
        merged.playlist.entries = entries
        merged.validate()
    self.editor_workspace.set_document(merged)
    self._capture_document()


def _replace_workspace(self) -> None:
    self.album_workspace = AlbumWorkspace()
    index = self.foundation_shell.workspace_stack._index["album"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.album_workspace)

    context_layout = self.foundation_shell.context.layout()
    self._s04_context_old = [
        context_layout.itemAt(i).widget()
        for i in range(context_layout.count())
        if context_layout.itemAt(i).widget() is not None
    ]
    self.album_context = AlbumContextWidget()
    self.album_context.hide()
    context_layout.addWidget(self.album_context, 1)

    self.album_tools = AlbumMassToolsWidget()
    self._inspector_router.addWidget(self.album_tools)

    self.album_timeline_canvas = AlbumTimelineOverviewCanvas()
    timeline_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    timeline_layout.addWidget(self.album_timeline_canvas, 1)
    self.album_timeline_canvas.hide()


def _connect_album(self) -> None:
    self.album_context.filter_requested.connect(self._s04_filter)
    self.album_context.edit_title_requested.connect(self._s04_edit_title)
    self.album_context.edit_album_cover_requested.connect(self._s04_edit_album_cover)
    self.album_workspace.selection_changed.connect(self._s04_selection)
    self.album_workspace.auto_arrange_requested.connect(self._s04_auto_arrange)
    self.album_workspace.set_cover_requested.connect(self._s04_set_cover)
    self.album_workspace.assign_visual_requested.connect(self._s04_assign_visual)
    self.album_workspace.clear_visual_requested.connect(self._s04_clear_visual)
    self.album_workspace.transition_requested.connect(self._s04_transition)
    self.album_workspace.delete_requested.connect(self._s04_delete)
    self.album_workspace.move_top_requested.connect(lambda: self._s04_move_edge(True))
    self.album_workspace.move_bottom_requested.connect(lambda: self._s04_move_edge(False))
    self.album_workspace.reorder_requested.connect(self._s04_reorder)

    self.album_tools.set_cover_requested.connect(self._s04_set_cover)
    self.album_tools.auto_match_cover_requested.connect(self._s04_auto_match_cover)
    self.album_tools.assign_visual_requested.connect(self._s04_assign_visual)
    self.album_tools.clear_visual_requested.connect(self._s04_clear_visual)
    self.album_tools.default_transition_requested.connect(self._s04_transition)
    self.album_tools.delete_requested.connect(self._s04_delete)

    self.foundation_state.workspace_changed.connect(self._s04_route)
    self.editor_workspace.documentChanged.connect(self._s04_document_changed)


def _init(self, *args, **kwargs):
    _originals["window_init"](self, *args, **kwargs)
    _replace_workspace(self)
    _connect_album(self)
    self._s04_restoring = True
    try:
        self._s04_restore_document()
    finally:
        self._s04_restoring = False
    self._s04_refresh()
    self._s04_route(self.foundation_state.workspace)


def _save(self) -> None:
    self._s04_capture_document()
    return _originals["window_save"](self)


def _adopt(self, project, result, *, route="media", add_recent=True):
    output = _originals["window_adopt"](self, project, result, route=route, add_recent=add_recent)
    if hasattr(self, "album_workspace"):
        self._s04_restoring = True
        try:
            self._s04_restore_document()
        finally:
            self._s04_restoring = False
        self._s04_refresh()
    return output


def _refresh_window(self, *args, **kwargs):
    result = _originals["window_refresh"](self, *args, **kwargs)
    if hasattr(self, "album_workspace"):
        self._s04_capture_document()
        self._s04_refresh()
    return result


def _route(self, route: str) -> None:
    active = route == "album"
    self.album_context.setVisible(active)
    self.album_timeline_canvas.setVisible(active)
    if active:
        for widget in self._s04_context_old:
            widget.setVisible(False)
        if hasattr(self, "media_context"):
            self.media_context.setVisible(False)
        if hasattr(self, "media_timeline_canvas"):
            self.media_timeline_canvas.setVisible(False)
        if hasattr(self, "_s03_timeline_old"):
            self._s03_timeline_old.setVisible(False)
        else:
            self.foundation_shell.timeline.canvas.setVisible(False)
        self._inspector_router.setCurrentWidget(self.album_tools)
        self._s04_consume_media_handoff()
        self._s04_refresh()
    elif route != "home":
        # Earlier STEP handlers own their own inspector selection. Only leave Album page.
        if self._inspector_router.currentWidget() is self.album_tools:
            self._inspector_router.setCurrentIndex(1)


def _document_changed(self, document: ProjectDocument) -> None:
    if getattr(self, "_s04_restoring", False):
        return
    self.project._album_document_v2 = document.to_dict()
    assets = document.asset_map()
    set_active_audio_paths(
        self.project,
        [assets[song.asset_id].locator for song in document.playlist.entries if song.asset_id in assets],
    )
    if hasattr(self, "album_workspace"):
        self._s04_refresh()
    self.foundation_shell.refresh_commands()


def _refresh_album(self) -> None:
    if not hasattr(self, "album_workspace"):
        return
    document = _active_document(self)
    self.album_workspace.apply_document(document)
    self.album_context.apply_document(document, self.album_workspace.filter_key)
    self.album_tools.apply_document(document)
    selected = self.album_workspace.selected_song_ids
    self.album_tools.set_selection_count(len(selected))
    self.album_timeline_canvas.set_document(document, selected)


def _filter(self, filter_key: str) -> None:
    self.album_workspace.set_filter(filter_key)
    self.album_context.apply_document(_active_document(self), self.album_workspace.filter_key)


def _selection(self, song_ids) -> None:
    selected = set(song_ids or ())
    self.album_tools.set_selection_count(len(selected))
    self.album_timeline_canvas.set_document(_active_document(self), selected)


def _dispatch(self, commands, message: str) -> bool:
    try:
        self.editor_workspace.dispatch_external(commands, message=message)
        self._s04_capture_document()
        self.foundation_shell.refresh_commands()
        return True
    except Exception as exc:
        QMessageBox.warning(self, "Album", f"Perubahan tidak dapat diterapkan:\n{exc}")
        return False


def _choose_asset(self, kinds: set[str], title: str) -> str | None:
    document = _active_document(self)
    assets = [asset for asset in document.media if asset.kind in kinds]
    if not assets:
        QMessageBox.information(self, title, "Belum ada media yang sesuai. Impor media terlebih dahulu.")
        return None
    labels = []
    lookup: dict[str, str] = {}
    for index, asset in enumerate(assets, start=1):
        label = f"{index:03d} • {asset.original_name or Path(asset.locator).name}"
        labels.append(label)
        lookup[label] = asset.asset_id
    value, ok = QInputDialog.getItem(self, title, "Pilih media:", labels, 0, False)
    return lookup.get(str(value)) if ok else None


def _edit_title(self) -> None:
    document = _active_document(self)
    current = document.album_title or document.name
    value, ok = QInputDialog.getText(self, "Nama Album", "Nama album:", text=current)
    if ok:
        self._s04_dispatch(SetAlbumTitle(str(value)), "Nama album diperbarui.")


def _edit_album_cover(self) -> None:
    asset_id = self._s04_choose_asset({"image"}, "Cover Album")
    if asset_id:
        self._s04_dispatch(SetAlbumCover(asset_id), "Cover album diperbarui.")


def _selected_ids(self) -> set[str]:
    return self.album_workspace.selected_song_ids


def _set_cover(self) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    asset_id = self._s04_choose_asset({"image"}, "Set Cover")
    if not asset_id:
        return
    commands = [SetSongCover(song_id, asset_id) for song_id in selected]
    self._s04_dispatch(commands, f"Cover diterapkan ke {len(commands)} lagu.")


def _assign_visual(self) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    asset_id = self._s04_choose_asset({"image", "video"}, "Assign Visual")
    if not asset_id:
        return
    commands = [SetSongVisual(song_id, asset_id) for song_id in selected]
    self._s04_dispatch(commands, f"Visual diterapkan ke {len(commands)} lagu.")


def _clear_visual(self) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    answer = QMessageBox.question(
        self,
        "Clear Visual",
        f"Hapus visual dari {len(selected)} lagu terpilih?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    commands = [SetSongVisual(song_id, None) for song_id in selected]
    self._s04_dispatch(commands, f"Visual dibersihkan dari {len(commands)} lagu.")


def _transition(self, kind: str, duration: float) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    commands = [SetAlbumDefaultTransition(kind, duration)]
    commands.extend(SetSongTransition(song_id, kind, duration) for song_id in selected)
    self._s04_dispatch(commands, f"Transisi diterapkan ke {len(selected)} lagu.")


def _auto_match_cover(self) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    matches = safe_cover_matches(_active_document(self), selected)
    if not matches:
        QMessageBox.information(
            self,
            "Auto Match Cover",
            "Tidak ada exact match yang aman. Tidak ada cover yang ditebak atau diubah.",
        )
        return
    commands = [SetSongCover(song_id, asset_id) for song_id, asset_id in matches.items()]
    self._s04_dispatch(commands, f"Auto Match menerapkan {len(commands)} cover exact-match.")


def _delete(self) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    answer = QMessageBox.question(
        self,
        "Hapus dari Album",
        f"Hapus {len(selected)} lagu dari Album? Media sumber tidak akan dihapus.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    document = _active_document(self)
    entries = [song for song in document.playlist.entries if song.song_id not in selected]
    self.album_workspace.set_selection(set())
    self._s04_dispatch(SetPlaylistEntries(entries), f"{len(selected)} lagu dihapus dari Album; Media tetap aman.")


def _move_edge(self, top: bool) -> None:
    selected = self._s04_selected_ids()
    if not selected:
        return
    order = move_selection_to_edge(_active_document(self), selected, top=top)
    label = "atas" if top else "bawah"
    self._s04_dispatch(ReorderSongs(order), f"{len(selected)} lagu dipindah ke {label}.")


def _reorder(self, song_id: str, target_position: int) -> None:
    self._s04_dispatch(MoveSong(song_id, target_position=int(target_position)), "Urutan Album diperbarui.")


def _auto_arrange(self) -> None:
    before = _active_document(self).content_signature()
    self.editor_workspace.auto_arrange()
    after = _active_document(self).content_signature()
    self._s04_capture_document()
    self._s04_refresh()
    if before == after and hasattr(self, "log"):
        self.log.appendPlainText("Auto Susun Album: state sudah sesuai; tidak ada layer duplikat dibuat.")


def _consume_media_handoff(self) -> None:
    command = getattr(self, "_step03_album_handoff", None)
    if command is None or not hasattr(self, "_s03_index"):
        return
    self._step03_album_handoff = None
    document = _active_document(self)
    by_path = {
        str(Path(asset.locator).expanduser()).replace("\\", "/").casefold(): asset
        for asset in document.media
        if asset.kind == "audio"
    }
    existing_asset_ids = {song.asset_id for song in document.playlist.entries}
    additions: list[str] = []
    for media_id in tuple(getattr(command, "asset_ids", ())):
        media_asset = self._s03_index.get(str(media_id))
        if media_asset is None or getattr(media_asset.media_type, "value", "") != "audio":
            continue
        key = str(Path(media_asset.path).expanduser()).replace("\\", "/").casefold()
        asset = by_path.get(key)
        if asset is not None and asset.asset_id not in existing_asset_ids:
            additions.append(asset.asset_id)
            existing_asset_ids.add(asset.asset_id)
    if not additions:
        return
    entries = list(document.playlist.entries) + PlaylistServiceV2.build_entries(document, additions)
    self._s04_dispatch(SetPlaylistEntries(entries), f"{len(additions)} lagu dari Media ditambahkan ke Album.")


def install_step04_album() -> None:
    global _installed
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _originals.update(
        project_to_dict=Project.to_dict,
        project_from_dict_descriptor=Project.__dict__["from_dict"],
        project_from_dict_bound=Project.from_dict,
        window_init=Window.__init__,
        window_save=Window._foundation_save_project,
        window_adopt=Window._adopt_home_project,
        window_refresh=Window.refresh,
    )

    Project.to_dict = _project_to_dict
    Project.from_dict = classmethod(_project_from_dict)
    Window.__init__ = _init
    Window._foundation_save_project = _save
    Window._adopt_home_project = _adopt
    Window.refresh = _refresh_window

    methods = {
        "_s04_active_document": _active_document,
        "_s04_capture_document": _capture_document,
        "_s04_restore_document": _restore_document,
        "_s04_route": _route,
        "_s04_document_changed": _document_changed,
        "_s04_refresh": _refresh_album,
        "_s04_filter": _filter,
        "_s04_selection": _selection,
        "_s04_dispatch": _dispatch,
        "_s04_choose_asset": _choose_asset,
        "_s04_edit_title": _edit_title,
        "_s04_edit_album_cover": _edit_album_cover,
        "_s04_selected_ids": _selected_ids,
        "_s04_set_cover": _set_cover,
        "_s04_assign_visual": _assign_visual,
        "_s04_clear_visual": _clear_visual,
        "_s04_transition": _transition,
        "_s04_auto_match_cover": _auto_match_cover,
        "_s04_delete": _delete,
        "_s04_move_edge": _move_edge,
        "_s04_reorder": _reorder,
        "_s04_auto_arrange": _auto_arrange,
        "_s04_consume_media_handoff": _consume_media_handoff,
    }
    for name, method in methods.items():
        setattr(Window, name, method)
    _installed = True
