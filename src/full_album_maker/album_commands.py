from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .album_model import ALBUM_COVER_KEY, DEFAULT_TRANSITION_KEY, TRANSITIONS_KEY, AlbumTransition
from .editor_commands import CommandError, EditorCommand
from .editor_models import ProjectDocument


@dataclass
class SetAlbumTitle(EditorCommand):
    title: str

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if not isinstance(self.title, str):
            raise CommandError("Judul album harus berupa teks.")
        old = document.album_title
        document.album_title = self.title.strip()
        return SetAlbumTitle(old)


@dataclass
class SetAlbumCover(EditorCommand):
    asset_id: str | None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        old = document.extensions.get(ALBUM_COVER_KEY)
        if self.asset_id is None:
            document.extensions.pop(ALBUM_COVER_KEY, None)
        else:
            asset = document.asset_map().get(self.asset_id)
            if asset is None or asset.kind != "image":
                raise CommandError("Cover album harus berupa image yang valid.")
            document.extensions[ALBUM_COVER_KEY] = self.asset_id
        return SetAlbumCover(old if isinstance(old, str) else None)


@dataclass
class SetAlbumDefaultTransition(EditorCommand):
    kind: str
    duration_seconds: float
    _missing: bool = False

    def apply(self, document: ProjectDocument) -> EditorCommand:
        old_exists = DEFAULT_TRANSITION_KEY in document.extensions
        old = deepcopy(document.extensions.get(DEFAULT_TRANSITION_KEY))
        if self._missing:
            document.extensions.pop(DEFAULT_TRANSITION_KEY, None)
        else:
            value = AlbumTransition(self.kind, self.duration_seconds).normalized()
            document.extensions[DEFAULT_TRANSITION_KEY] = {
                "kind": value.kind,
                "duration_seconds": value.duration_seconds,
            }
        if not old_exists:
            return SetAlbumDefaultTransition("fade", 2.0, _missing=True)
        if not isinstance(old, dict):
            return SetAlbumDefaultTransition("fade", 2.0, _missing=True)
        return SetAlbumDefaultTransition(
            str(old.get("kind", "fade")),
            float(old.get("duration_seconds", 2.0) or 0.0),
        )


@dataclass
class SetSongTransition(EditorCommand):
    song_id: str
    kind: str
    duration_seconds: float
    _missing: bool = False

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if self.song_id not in document.song_map():
            raise CommandError("Lagu tidak ditemukan.")
        raw = document.extensions.get(TRANSITIONS_KEY)
        mapping = deepcopy(raw) if isinstance(raw, dict) else {}
        old_exists = self.song_id in mapping
        old = deepcopy(mapping.get(self.song_id))
        if self._missing:
            mapping.pop(self.song_id, None)
        else:
            value = AlbumTransition(self.kind, self.duration_seconds).normalized()
            mapping[self.song_id] = {
                "kind": value.kind,
                "duration_seconds": value.duration_seconds,
            }
        if mapping:
            document.extensions[TRANSITIONS_KEY] = mapping
        else:
            document.extensions.pop(TRANSITIONS_KEY, None)
        if not old_exists or not isinstance(old, dict):
            return SetSongTransition(self.song_id, "fade", 2.0, _missing=True)
        return SetSongTransition(
            self.song_id,
            str(old.get("kind", "fade")),
            float(old.get("duration_seconds", 2.0) or 0.0),
        )
