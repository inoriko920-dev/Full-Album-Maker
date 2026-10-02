from __future__ import annotations

from .editor_models import ProjectDocument
from .legacy_sync_v2 import sync_legacy_media
from .playlist_service_v2 import PlaylistServiceV2


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
    from .foundation_window import FoundationMainWindow as Window

    Window._s04_restore_document = _restore_document
