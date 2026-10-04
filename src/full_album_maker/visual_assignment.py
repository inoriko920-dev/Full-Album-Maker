from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .editor_commands import CommandError, EditorCommand
from .editor_models import MediaAsset, ProjectDocument
from .playlist_commands import SetSongVisual


VISUAL_FILTERS = {"all", "empty", "image", "video", "missing"}


@dataclass(frozen=True)
class VisualAssignmentStatus:
    song_id: str
    state: str
    source_kind: str
    asset_id: str | None
    source_name: str
    locator: str
    exists: bool

    @property
    def label(self) -> str:
        return {
            "empty": "Tanpa Visual",
            "image": "Foto",
            "video": "Video",
            "missing": "Missing",
        }.get(self.state, self.state.title())


def _source_exists(asset: MediaAsset | None) -> bool:
    if asset is None or not str(asset.locator or "").strip():
        return False
    try:
        return Path(asset.locator).expanduser().is_file()
    except OSError:
        return False


def assignment_status(document: ProjectDocument, song_id: str) -> VisualAssignmentStatus:
    song = document.song_map().get(song_id)
    if song is None:
        raise ValueError("Lagu tidak ditemukan.")
    asset_id = song.visual_asset_id
    if not asset_id:
        return VisualAssignmentStatus(song_id, "empty", "none", None, "", "", False)
    asset = document.asset_map().get(asset_id)
    if asset is None:
        return VisualAssignmentStatus(song_id, "missing", "unknown", asset_id, "Asset tidak ditemukan", "", False)
    name = asset.original_name or Path(asset.locator).name or "Visual"
    exists = _source_exists(asset)
    if asset.kind not in {"image", "video"}:
        return VisualAssignmentStatus(song_id, "missing", asset.kind, asset_id, name, asset.locator, exists)
    state = asset.kind if exists else "missing"
    return VisualAssignmentStatus(song_id, state, asset.kind, asset_id, name, asset.locator, exists)


def assignment_counts(document: ProjectDocument) -> dict[str, int]:
    counts = {"all": 0, "empty": 0, "image": 0, "video": 0, "missing": 0}
    for song in document.playlist.entries:
        status = assignment_status(document, song.song_id)
        counts["all"] += 1
        counts[status.state] += 1
    return counts


def filtered_song_ids(document: ProjectDocument, filter_key: str) -> tuple[str, ...]:
    key = str(filter_key or "all")
    if key not in VISUAL_FILTERS:
        raise ValueError("Filter Visual tidak valid.")
    if key == "all":
        return tuple(song.song_id for song in document.playlist.entries)
    return tuple(
        song.song_id
        for song in document.playlist.entries
        if assignment_status(document, song.song_id).state == key
    )


def available_visual_assets(document: ProjectDocument, kind: str | None = None, *, require_existing: bool = True) -> tuple[MediaAsset, ...]:
    if kind not in {None, "image", "video"}:
        raise ValueError("Jenis asset Visual harus image/video.")
    result: list[MediaAsset] = []
    for asset in document.media:
        if asset.kind not in {"image", "video"}:
            continue
        if kind is not None and asset.kind != kind:
            continue
        if require_existing and not _source_exists(asset):
            continue
        result.append(asset)
    result.sort(key=lambda item: ((item.original_name or Path(item.locator).name).casefold(), item.asset_id))
    return tuple(result)


@dataclass
class RelinkMediaAsset(EditorCommand):
    asset_id: str
    locator: str
    original_name: str | None = None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        asset = document.asset_map().get(self.asset_id)
        if asset is None:
            raise CommandError("Asset yang akan direlink tidak ditemukan.")
        if asset.kind not in {"image", "video"}:
            raise CommandError("Relink STEP06 hanya menerima asset image/video.")
        path = Path(str(self.locator or "")).expanduser()
        if not path.is_file():
            raise CommandError("File pengganti tidak ditemukan.")
        allowed = {
            "image": {".jpg", ".jpeg", ".png", ".webp", ".bmp"},
            "video": {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"},
        }
        if path.suffix.casefold() not in allowed[asset.kind]:
            raise CommandError(f"File pengganti bukan {asset.kind} yang didukung.")
        old_locator = asset.locator
        old_name = asset.original_name
        old_relative = asset.relative_path
        old_fingerprint = deepcopy(asset.fingerprint)
        asset.locator = str(path)
        asset.original_name = str(self.original_name or path.name)
        asset.relative_path = ""
        try:
            stat = path.stat()
            asset.fingerprint = {"size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}
        except OSError:
            asset.fingerprint = {}
        return RestoreMediaAssetLocation(
            self.asset_id,
            old_locator,
            old_name,
            old_relative,
            old_fingerprint,
        )


@dataclass
class RestoreMediaAssetLocation(EditorCommand):
    asset_id: str
    locator: str
    original_name: str
    relative_path: str
    fingerprint: dict

    def apply(self, document: ProjectDocument) -> EditorCommand:
        asset = document.asset_map().get(self.asset_id)
        if asset is None:
            raise CommandError("Asset yang akan dipulihkan tidak ditemukan.")
        inverse = RestoreMediaAssetLocation(
            self.asset_id,
            asset.locator,
            asset.original_name,
            asset.relative_path,
            deepcopy(asset.fingerprint),
        )
        asset.locator = self.locator
        asset.original_name = self.original_name
        asset.relative_path = self.relative_path
        asset.fingerprint = deepcopy(self.fingerprint)
        return inverse


def deterministic_auto_match_commands(
    document: ProjectDocument,
    song_ids: Iterable[str],
    *,
    overwrite_existing: bool = False,
) -> tuple[SetSongVisual, ...]:
    """Build deterministic assignment commands without mutating the project.

    Matching is intentionally conservative: existing explicit assignments are
    preserved unless overwrite_existing=True. Available non-missing visual media
    are sorted by stable display name + asset_id and assigned in playlist order.
    No random or AI guess is used at STEP06.
    """

    requested = {str(value) for value in song_ids if str(value)}
    assets = available_visual_assets(document, require_existing=True)
    if not assets or not requested:
        return ()
    commands: list[SetSongVisual] = []
    asset_index = 0
    for song in document.playlist.entries:
        if song.song_id not in requested:
            continue
        if song.visual_asset_id and not overwrite_existing:
            continue
        commands.append(SetSongVisual(song.song_id, assets[asset_index % len(assets)].asset_id))
        asset_index += 1
    return tuple(commands)


def validate_playback_eligibility(document: ProjectDocument, song_id: str, *, loop_video: bool, freeze_end: bool) -> None:
    if loop_video and freeze_end:
        raise CommandError("Loop Video dan Freeze di Akhir tidak boleh aktif bersamaan.")
    if not loop_video and not freeze_end:
        return
    status = assignment_status(document, song_id)
    if status.source_kind != "video" or status.state not in {"video", "missing"}:
        raise CommandError("Loop Video/Freeze End hanya tersedia untuk sumber Video.")
