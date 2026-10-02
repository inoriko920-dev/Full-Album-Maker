from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
from pathlib import Path
from typing import Iterable, Sequence


class MediaType(str, Enum):
    AUDIO = "audio"
    PHOTO = "photo"
    VIDEO = "video"


class MediaStatus(str, Enum):
    READY = "ready"
    MISSING = "missing"
    METADATA_ERROR = "metadata_error"


class MediaSort(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"


class MediaViewMode(str, Enum):
    GRID = "grid"
    LIST = "list"


@dataclass(frozen=True)
class MediaMetadata:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    size_bytes: int | None = None
    created_at: float | None = None
    container: str = ""
    codec: str = ""
    detail: str = ""


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    path: str
    display_name: str
    media_type: MediaType
    status: MediaStatus = MediaStatus.READY
    favorite: bool = False
    tags: tuple[str, ...] = ()
    description: str = ""
    collections: tuple[str, ...] = ()
    metadata: MediaMetadata = field(default_factory=MediaMetadata)
    imported_at: float = 0.0

    @property
    def search_text(self) -> str:
        return " ".join((self.display_name, *self.tags, self.description)).casefold()

    @property
    def exists(self) -> bool:
        return self.status != MediaStatus.MISSING


@dataclass(frozen=True)
class MediaQuery:
    category: str = "all"
    search: str = ""
    status: MediaStatus | None = None
    favorite_only: bool = False
    collection: str = ""
    sort: MediaSort = MediaSort.NEWEST
    view_mode: MediaViewMode = MediaViewMode.GRID

    def normalized(self) -> "MediaQuery":
        return replace(self, search=self.search.strip().casefold(), collection=self.collection.strip())


@dataclass
class MediaSelection:
    selected_ids: list[str] = field(default_factory=list)
    anchor_id: str | None = None

    def clear(self) -> None:
        self.selected_ids.clear()
        self.anchor_id = None

    def select_only(self, asset_id: str) -> None:
        self.selected_ids[:] = [asset_id]
        self.anchor_id = asset_id

    def toggle(self, asset_id: str) -> None:
        if asset_id in self.selected_ids:
            self.selected_ids.remove(asset_id)
            if self.anchor_id == asset_id:
                self.anchor_id = self.selected_ids[-1] if self.selected_ids else None
        else:
            self.selected_ids.append(asset_id)
            self.anchor_id = asset_id

    def select_range(self, ordered_ids: Sequence[str], asset_id: str, *, additive: bool = False) -> None:
        if asset_id not in ordered_ids:
            return
        if self.anchor_id not in ordered_ids:
            self.select_only(asset_id)
            return
        left = ordered_ids.index(self.anchor_id)
        right = ordered_ids.index(asset_id)
        if left > right:
            left, right = right, left
        values = list(ordered_ids[left : right + 1])
        if additive:
            for value in values:
                if value not in self.selected_ids:
                    self.selected_ids.append(value)
        else:
            self.selected_ids[:] = values

    def select_all(self, ordered_ids: Iterable[str]) -> None:
        self.selected_ids[:] = list(dict.fromkeys(ordered_ids))
        if self.selected_ids:
            self.anchor_id = self.selected_ids[0]


class MediaLibraryIndex:
    """In-memory projection for STEP 03; never scans disk while filtering/searching."""

    def __init__(self, assets: Iterable[MediaAsset] = ()) -> None:
        self._assets: dict[str, MediaAsset] = {asset.asset_id: asset for asset in assets}

    def replace_all(self, assets: Iterable[MediaAsset]) -> None:
        self._assets = {asset.asset_id: asset for asset in assets}

    def upsert(self, asset: MediaAsset) -> None:
        self._assets[asset.asset_id] = asset

    def remove(self, asset_id: str) -> None:
        self._assets.pop(asset_id, None)

    def get(self, asset_id: str) -> MediaAsset | None:
        return self._assets.get(asset_id)

    def all(self) -> tuple[MediaAsset, ...]:
        return tuple(self._assets.values())

    def counts(self) -> dict[str, int]:
        values = self._assets.values()
        result = {
            "all": len(self._assets),
            "audio": 0,
            "photo": 0,
            "video": 0,
            "favorite": 0,
            "missing": 0,
        }
        for asset in values:
            result[asset.media_type.value] += 1
            if asset.favorite:
                result["favorite"] += 1
            if asset.status == MediaStatus.MISSING:
                result["missing"] += 1
        return result

    def project(self, query: MediaQuery) -> list[MediaAsset]:
        q = query.normalized()
        values = list(self._assets.values())
        category = q.category.casefold()
        if category in {"audio", "photo", "video"}:
            values = [a for a in values if a.media_type.value == category]
        elif category == "favorite":
            values = [a for a in values if a.favorite]
        elif category == "missing":
            values = [a for a in values if a.status == MediaStatus.MISSING]
        if q.status is not None:
            values = [a for a in values if a.status == q.status]
        if q.favorite_only:
            values = [a for a in values if a.favorite]
        if q.collection:
            values = [a for a in values if q.collection in a.collections]
        if q.search:
            values = [a for a in values if q.search in a.search_text]

        # Python sort is stable; asset_id is only a deterministic tie breaker.
        if q.sort == MediaSort.NEWEST:
            values.sort(key=lambda a: (a.imported_at, a.asset_id), reverse=True)
        elif q.sort == MediaSort.OLDEST:
            values.sort(key=lambda a: (a.imported_at, a.asset_id))
        elif q.sort == MediaSort.NAME_DESC:
            values.sort(key=lambda a: (a.display_name.casefold(), a.asset_id), reverse=True)
        else:
            values.sort(key=lambda a: (a.display_name.casefold(), a.asset_id))
        return values


def stable_asset_id(path: str, media_type: MediaType | str) -> str:
    kind = media_type.value if isinstance(media_type, MediaType) else str(media_type)
    source = str(Path(path).expanduser().resolve(strict=False))
    digest = hashlib.sha256(f"{kind}\0{source}".encode("utf-8")).hexdigest()
    return digest[:24]


def normalize_tags(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


@dataclass(frozen=True)
class MediaAddToAlbumCommand:
    asset_ids: tuple[str, ...]
    source_workspace: str = "media"

    def validate(self) -> None:
        if not self.asset_ids or any(not str(value).strip() for value in self.asset_ids):
            raise ValueError("Media Add-to-Album command membutuhkan minimal satu asset ID valid.")
        if self.source_workspace != "media":
            raise ValueError("Source workspace Add-to-Album harus media.")
