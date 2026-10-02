from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from .editor_models import ProjectDocument
from .legacy_sync_v2 import sync_legacy_media
from .playlist_service_v2 import PlaylistServiceV2


_original_init: Any = None


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
    """Install the STEP04 restore fix and final deferred route ownership.

    STEP03 intentionally queues a zero-delay route reactivation during startup.
    Because Album is layered after Media, STEP04 must queue its own shared-route
    reactivation after the earlier guard so the final inspector/context/timeline
    ownership matches FoundationUiState without modifying the STEP03 contract.
    """

    global _original_init
    from .foundation_window import FoundationMainWindow as Window

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

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = guarded_init
