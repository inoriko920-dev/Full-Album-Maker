from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from .editor_models import ProjectDocument, TIMEBASE
from .playlist_service_v2 import PlaylistServiceV2


TRANSITIONS_KEY = "album_song_transitions"
DEFAULT_TRANSITION_KEY = "album_default_transition"
ALBUM_COVER_KEY = "album_cover_asset_id"
PAGE_SIZE = 10

TRANSITION_LABELS = {
    "cut": "Cut",
    "fade": "Fade",
    "cross_fade": "Cross Fade",
    "zoom": "Zoom",
    "slide": "Slide",
}


@dataclass(frozen=True)
class AlbumTransition:
    kind: str = "fade"
    duration_seconds: float = 2.0

    def normalized(self) -> "AlbumTransition":
        kind = self.kind if self.kind in TRANSITION_LABELS else "fade"
        duration = min(10.0, max(0.0, float(self.duration_seconds)))
        return AlbumTransition(kind=kind, duration_seconds=duration)

    @property
    def label(self) -> str:
        return TRANSITION_LABELS.get(self.kind, "Fade")


@dataclass(frozen=True)
class AlbumSongRow:
    position: int
    song_id: str
    asset_id: str
    title: str
    artist: str
    original_name: str
    duration_seconds: float
    cover_asset_id: str | None
    visual_asset_id: str | None
    visual_label: str
    transition: AlbumTransition
    status: str
    status_state: str


@dataclass(frozen=True)
class AlbumSummary:
    song_count: int
    duration_seconds: float
    missing_cover: int
    missing_visual: int
    needs_review: int


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = Path(text).stem.casefold().replace("&", " and ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _transition_payload(document: ProjectDocument) -> dict:
    value = document.extensions.get(TRANSITIONS_KEY, {})
    return value if isinstance(value, dict) else {}


def default_transition(document: ProjectDocument) -> AlbumTransition:
    raw = document.extensions.get(DEFAULT_TRANSITION_KEY, {})
    if not isinstance(raw, dict):
        return AlbumTransition()
    return AlbumTransition(
        kind=str(raw.get("kind", "fade")),
        duration_seconds=float(raw.get("duration_seconds", 2.0) or 0.0),
    ).normalized()


def song_transition(document: ProjectDocument, song_id: str) -> AlbumTransition:
    raw = _transition_payload(document).get(song_id)
    if not isinstance(raw, dict):
        return default_transition(document)
    return AlbumTransition(
        kind=str(raw.get("kind", "fade")),
        duration_seconds=float(raw.get("duration_seconds", 2.0) or 0.0),
    ).normalized()


def album_cover_asset_id(document: ProjectDocument) -> str | None:
    value = document.extensions.get(ALBUM_COVER_KEY)
    if isinstance(value, str) and value in document.asset_map():
        return value
    for song in document.playlist.entries:
        if song.cover_asset_id and song.cover_asset_id in document.asset_map():
            return song.cover_asset_id
    return None


def _status(cover_id: str | None, visual_id: str | None) -> tuple[str, str]:
    if not visual_id:
        return "Belum Ada Visual", "error"
    if not cover_id:
        return "Perlu Ditinjau", "warning"
    return "Siap", "success"


def rows(document: ProjectDocument, filter_key: str = "all") -> list[AlbumSongRow]:
    base_rows = PlaylistServiceV2.rows(document)
    assets = document.asset_map()
    output: list[AlbumSongRow] = []
    for row in base_rows:
        visual = assets.get(row.visual_asset_id) if row.visual_asset_id else None
        visual_label = "Belum Ada"
        if visual is not None:
            visual_label = "Video" if visual.kind == "video" else "Foto" if visual.kind == "image" else visual.kind.title()
        status, status_state = _status(row.cover_asset_id, row.visual_asset_id)
        item = AlbumSongRow(
            position=row.position,
            song_id=row.song_id,
            asset_id=row.asset_id,
            title=row.title,
            artist=row.artist,
            original_name=row.original_name,
            duration_seconds=max(0.0, row.duration_tick / TIMEBASE),
            cover_asset_id=row.cover_asset_id,
            visual_asset_id=row.visual_asset_id,
            visual_label=visual_label,
            transition=song_transition(document, row.song_id),
            status=status,
            status_state=status_state,
        )
        if filter_key == "missing_cover" and item.cover_asset_id:
            continue
        if filter_key == "missing_visual" and item.visual_asset_id:
            continue
        if filter_key == "review" and item.status != "Perlu Ditinjau":
            continue
        output.append(item)
    return output


def summary(document: ProjectDocument) -> AlbumSummary:
    all_rows = rows(document)
    return AlbumSummary(
        song_count=len(all_rows),
        duration_seconds=sum(item.duration_seconds for item in all_rows),
        missing_cover=sum(1 for item in all_rows if not item.cover_asset_id),
        missing_visual=sum(1 for item in all_rows if not item.visual_asset_id),
        needs_review=sum(1 for item in all_rows if item.status == "Perlu Ditinjau"),
    )


def page_count(document: ProjectDocument, filter_key: str = "all") -> int:
    count = len(rows(document, filter_key))
    return max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)


def page_rows(document: ProjectDocument, filter_key: str, page: int) -> tuple[list[AlbumSongRow], int]:
    values = rows(document, filter_key)
    pages = max(1, (len(values) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(pages, max(1, int(page)))
    start = (page - 1) * PAGE_SIZE
    return values[start : start + PAGE_SIZE], pages


def move_selection_to_edge(document: ProjectDocument, selected_ids: set[str], *, top: bool) -> list[str]:
    current = [song.song_id for song in document.playlist.entries]
    selected = [song_id for song_id in current if song_id in selected_ids]
    remaining = [song_id for song_id in current if song_id not in selected_ids]
    return selected + remaining if top else remaining + selected


def safe_cover_matches(document: ProjectDocument, song_ids: set[str]) -> dict[str, str]:
    """Return only unambiguous exact-title image matches; never guess."""
    assets = document.asset_map()
    images = [asset for asset in document.media if asset.kind == "image"]
    by_name: dict[str, list[str]] = {}
    for asset in images:
        candidates = {
            _normalize_text(asset.original_name),
            _normalize_text(asset.locator),
            _normalize_text(str(asset.metadata.get("title", ""))),
        }
        for key in {x for x in candidates if x}:
            by_name.setdefault(key, []).append(asset.asset_id)

    result: dict[str, str] = {}
    for song in document.playlist.entries:
        if song.song_id not in song_ids:
            continue
        audio = assets.get(song.asset_id)
        if audio is None:
            continue
        keys = {
            _normalize_text(song.display_title),
            _normalize_text(audio.original_name),
            _normalize_text(str(audio.metadata.get("title", ""))),
        }
        matches: set[str] = set()
        for key in {x for x in keys if x}:
            matches.update(by_name.get(key, []))
        if len(matches) == 1:
            result[song.song_id] = next(iter(matches))
    return result


def format_duration(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def album_duration_text(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}j {minutes:02d}m"
    return f"{minutes}m"
