from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer

from .editor_models import ProjectDocument
from .legacy_sync_v2 import sync_legacy_media
from .media_library_services import canonical_path_key
from .playlist_feature import set_active_audio_paths
from .playlist_service_v2 import PlaylistServiceV2


_original_init: Any = None


def _mirror_legacy_active_audio(self, document: ProjectDocument) -> None:
    """Mirror only playlist paths that are valid in the legacy media library.

    The complete Album order is persisted in album_document_v2. The recovered
    legacy Project format has a stricter invariant: every active_audio_paths item
    must also exist in project.audios. Keep that invariant instead of inventing
    legacy media records for v2-only assets.
    """

    assets = document.asset_map()
    legacy_keys = {
        canonical_path_key(str(getattr(item, "path", "")))
        for item in getattr(self.project, "audios", ())
        if str(getattr(item, "path", "")).strip()
    }
    active_paths: list[str] = []
    for song in document.playlist.entries:
        asset = assets.get(song.asset_id)
        if asset is None or asset.kind != "audio":
            continue
        path = str(asset.locator or "")
        if path and canonical_path_key(path) in legacy_keys:
            active_paths.append(path)
    set_active_audio_paths(self.project, active_paths)


def _capture_document(self) -> None:
    if not hasattr(self, "editor_workspace"):
        return
    document = self.editor_workspace.document()
    self.project._album_document_v2 = document.to_dict()
    _mirror_legacy_active_audio(self, document)


def _document_changed(self, document: ProjectDocument) -> None:
    if getattr(self, "_s04_restoring", False):
        return
    self.project._album_document_v2 = document.to_dict()
    _mirror_legacy_active_audio(self, document)
    if hasattr(self, "album_workspace"):
        self._s04_refresh()
    if hasattr(self, "foundation_shell"):
        self.foundation_shell.refresh_commands()


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
        merged.playlist.entries = PlaylistServiceV2.use_all_audio(merged)
        merged.validate()

    self.editor_workspace.set_document(merged)
    self._s04_capture_document()


def install_step04_album_restore_fix() -> None:
    """Install STEP04 compatibility fixes after the Media compatibility layers."""

    global _original_init
    from .foundation_window import FoundationMainWindow as Window

    # Install before any instance is created so _connect_album binds these safe
    # methods instead of the earlier bridge implementations.
    Window._s04_capture_document = _capture_document
    Window._s04_document_changed = _document_changed
    Window._s04_restore_document = _restore_document
    if _original_init is not None:
        return

    _original_init = Window.__init__

    def guarded_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        shell = getattr(self, "foundation_shell", None)
        state = getattr(self, "foundation_state", None)
        if shell is None or state is None:
            return

        def reactivate_current_route() -> None:
            route = state.workspace
            shell._apply_workspace(route)
            route_sync = getattr(self, "_s04_route", None)
            if callable(route_sync):
                route_sync(route)

        # STEP03 schedules its activation during the wrapped init. Scheduling
        # here means STEP04 deterministically owns the final route state.
        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = guarded_init
