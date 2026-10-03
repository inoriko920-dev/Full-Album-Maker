from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Callable, Iterable, Mapping

from .editor_models import ProjectDocument


class DomainEventType(str, Enum):
    PROJECT_OPENED = "PROJECT_OPENED"
    PROJECT_CLOSING = "PROJECT_CLOSING"
    PROJECT_REVISION_CHANGED = "PROJECT_REVISION_CHANGED"
    DIRTY_CHANGED = "DIRTY_CHANGED"
    SELECTION_CHANGED = "SELECTION_CHANGED"
    MEDIA_CHANGED = "MEDIA_CHANGED"
    ALBUM_CHANGED = "ALBUM_CHANGED"
    TIMELINE_CHANGED = "TIMELINE_CHANGED"
    VISUAL_CHANGED = "VISUAL_CHANGED"
    TEMPLATE_APPLIED = "TEMPLATE_APPLIED"
    SPECTRUM_CHANGED = "SPECTRUM_CHANGED"
    UNDO_STACK_CHANGED = "UNDO_STACK_CHANGED"
    AUTOSAVE_STATUS = "AUTOSAVE_STATUS"
    PREVIEW_STATE = "PREVIEW_STATE"
    AI_STATE = "AI_STATE"
    RENDER_JOB_CHANGED = "RENDER_JOB_CHANGED"


@dataclass(frozen=True)
class DomainEvent:
    type: DomainEventType
    project_token: str
    revision: int
    payload: Mapping[str, object] = field(default_factory=dict)
    command_id: str = ""


EventHandler = Callable[[DomainEvent], None]


class DomainEventHub:
    """Small typed, non-reentrant event dispatcher for STEP11.

    Nested emits are queued until the current handler pass finishes. This keeps
    event delivery one-directional and prevents a refresh listener from growing
    the Python call stack into a re-entrant signal loop. The hub does not mutate
    project state; commands/controllers remain the only mutation owners.
    """

    def __init__(self) -> None:
        self._handlers: dict[DomainEventType, list[EventHandler]] = {}
        self._queue: deque[DomainEvent] = deque()
        self._dispatching = False

    def subscribe(self, event_type: DomainEventType, handler: EventHandler) -> Callable[[], None]:
        handlers = self._handlers.setdefault(event_type, [])
        if handler not in handlers:
            handlers.append(handler)

        def unsubscribe() -> None:
            current = self._handlers.get(event_type, [])
            if handler in current:
                current.remove(handler)

        return unsubscribe

    def emit(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("DomainEventHub hanya menerima DomainEvent.")
        self._queue.append(event)
        if self._dispatching:
            return
        self._dispatching = True
        try:
            while self._queue:
                current = self._queue.popleft()
                for handler in tuple(self._handlers.get(current.type, ())):
                    handler(current)
        finally:
            self._dispatching = False


@dataclass(frozen=True)
class SelectionSnapshot:
    song_ids: tuple[str, ...] = ()
    media_ids: tuple[str, ...] = ()
    clip_ids: tuple[str, ...] = ()
    layer_ids: tuple[str, ...] = ()
    primary_song_id: str = ""
    primary_media_id: str = ""
    primary_clip_id: str = ""
    primary_layer_id: str = ""
    time_tick: int = 0
    range_start_tick: int | None = None
    range_end_tick: int | None = None


class SelectionStore:
    """Transient stable-ID selection shared across workspaces.

    Domain objects are never copied into the store. Consumers always resolve IDs
    against the current ProjectDocument revision.
    """

    def __init__(self, event_hub: DomainEventHub, project_token: str = "") -> None:
        self._hub = event_hub
        self._project_token = str(project_token)
        self._snapshot = SelectionSnapshot()

    @property
    def snapshot(self) -> SelectionSnapshot:
        return self._snapshot

    def bind_project(self, project_token: str, *, clear: bool = True) -> None:
        self._project_token = str(project_token)
        if clear:
            self._snapshot = SelectionSnapshot()

    @staticmethod
    def _unique(values: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        for value in values:
            item = str(value)
            if item and item not in result:
                result.append(item)
        return tuple(result)

    def update(
        self,
        *,
        revision: int,
        song_ids: Iterable[str] | None = None,
        media_ids: Iterable[str] | None = None,
        clip_ids: Iterable[str] | None = None,
        layer_ids: Iterable[str] | None = None,
        primary_song_id: str | None = None,
        primary_media_id: str | None = None,
        primary_clip_id: str | None = None,
        primary_layer_id: str | None = None,
        time_tick: int | None = None,
        range_start_tick: int | None = None,
        range_end_tick: int | None = None,
        emit: bool = True,
    ) -> SelectionSnapshot:
        old = self._snapshot
        snapshot = SelectionSnapshot(
            song_ids=self._unique(song_ids) if song_ids is not None else old.song_ids,
            media_ids=self._unique(media_ids) if media_ids is not None else old.media_ids,
            clip_ids=self._unique(clip_ids) if clip_ids is not None else old.clip_ids,
            layer_ids=self._unique(layer_ids) if layer_ids is not None else old.layer_ids,
            primary_song_id=str(primary_song_id) if primary_song_id is not None else old.primary_song_id,
            primary_media_id=str(primary_media_id) if primary_media_id is not None else old.primary_media_id,
            primary_clip_id=str(primary_clip_id) if primary_clip_id is not None else old.primary_clip_id,
            primary_layer_id=str(primary_layer_id) if primary_layer_id is not None else old.primary_layer_id,
            time_tick=max(0, int(time_tick)) if time_tick is not None else old.time_tick,
            range_start_tick=(None if range_start_tick is None else max(0, int(range_start_tick))),
            range_end_tick=(None if range_end_tick is None else max(0, int(range_end_tick))),
        )
        if snapshot.range_start_tick is not None and snapshot.range_end_tick is not None:
            if snapshot.range_end_tick < snapshot.range_start_tick:
                raise ValueError("Selection range end tidak boleh sebelum start.")
        self._snapshot = snapshot
        if emit and snapshot != old:
            self._hub.emit(
                DomainEvent(
                    DomainEventType.SELECTION_CHANGED,
                    self._project_token,
                    int(revision),
                    {
                        "song_ids": snapshot.song_ids,
                        "media_ids": snapshot.media_ids,
                        "clip_ids": snapshot.clip_ids,
                        "layer_ids": snapshot.layer_ids,
                        "primary_song_id": snapshot.primary_song_id,
                        "primary_layer_id": snapshot.primary_layer_id,
                        "time_tick": snapshot.time_tick,
                    },
                )
            )
        return snapshot

    def prune(self, document: ProjectDocument, *, emit: bool = True) -> SelectionSnapshot:
        songs = set(document.song_map())
        media = set(document.asset_map())
        layers = set(document.layer_map())
        old = self._snapshot
        song_ids = tuple(value for value in old.song_ids if value in songs)
        media_ids = tuple(value for value in old.media_ids if value in media)
        layer_ids = tuple(value for value in old.layer_ids if value in layers)
        snapshot = SelectionSnapshot(
            song_ids=song_ids,
            media_ids=media_ids,
            clip_ids=old.clip_ids,
            layer_ids=layer_ids,
            primary_song_id=old.primary_song_id if old.primary_song_id in songs else (song_ids[0] if song_ids else ""),
            primary_media_id=old.primary_media_id if old.primary_media_id in media else (media_ids[0] if media_ids else ""),
            primary_clip_id=old.primary_clip_id if old.primary_clip_id in old.clip_ids else (old.clip_ids[0] if old.clip_ids else ""),
            primary_layer_id=old.primary_layer_id if old.primary_layer_id in layers else (layer_ids[0] if layer_ids else ""),
            time_tick=min(max(0, old.time_tick), max(0, document.duration_tick())),
            range_start_tick=old.range_start_tick,
            range_end_tick=old.range_end_tick,
        )
        self._snapshot = snapshot
        if emit and snapshot != old:
            self._hub.emit(
                DomainEvent(
                    DomainEventType.SELECTION_CHANGED,
                    self._project_token,
                    document.revision,
                    {"pruned": True, "song_ids": song_ids, "media_ids": media_ids, "layer_ids": layer_ids},
                )
            )
        return snapshot


OWNERSHIP_MAP: dict[str, tuple[str, bool]] = {
    "project_document": ("EditorSession/EditorController(ProjectDocument)", True),
    "legacy_project_envelope": ("Persistence compatibility bridge only", True),
    "media_registry": ("ProjectDocument.media + source-integrity services", True),
    "album_song_order": ("ProjectDocument.playlist", True),
    "timeline": ("ProjectDocument playlist/layers/timeline extensions", True),
    "visual_assignment": ("ProjectDocument SongInstance + media registry", True),
    "template_applied_state": ("Normal ProjectDocument layers/properties", True),
    "spectrum_layers": ("ProjectDocument layers", True),
    "selection": ("SelectionStore stable IDs", False),
    "undo_redo": ("EditorController history", False),
    "active_workspace": ("FoundationUiState/app preference", False),
    "preview": ("EditorSession playhead + preview owner", False),
    "ai_runtime": ("STEP09 AI controller/history policy", False),
    "render_jobs": ("STEP10 RenderQueue/JobStore", False),
}


def normalized_project_payload(document: ProjectDocument) -> dict:
    """Return deterministic persistent domain state for Save/Reopen tests.

    Runtime widget state, preview frames, AI transient responses, and render-job
    progress are absent because ProjectDocument never owns them.
    """

    document.validate()
    payload = document.to_dict()
    # to_dict is already domain-only. Round-trip through JSON normalizes tuples,
    # integer/string formatting, and nested dict order for deterministic evidence.
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def normalized_project_json(document: ProjectDocument) -> str:
    return json.dumps(
        normalized_project_payload(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def normalized_project_hash(document: ProjectDocument) -> str:
    return hashlib.sha256(normalized_project_json(document).encode("utf-8")).hexdigest()


def project_token(document: ProjectDocument, project_path: str = "") -> str:
    """Stable-enough runtime project identity without becoming persistent truth."""

    seed = f"{project_path}|{document.project_id}" if getattr(document, "project_id", "") else f"{project_path}|{document.name}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def classify_document_changes(before: ProjectDocument, after: ProjectDocument) -> tuple[DomainEventType, ...]:
    """Derive coarse event categories from authoritative snapshots.

    This is intentionally diagnostic/coalesced rather than an alternate mutation
    model. Workspaces may refresh lazily from the current document after receiving
    these categories.
    """

    events: list[DomainEventType] = []
    before_media = [(x.asset_id, x.kind, x.locator) for x in before.media]
    after_media = [(x.asset_id, x.kind, x.locator) for x in after.media]
    if before_media != after_media:
        events.append(DomainEventType.MEDIA_CHANGED)

    before_songs = [x.to_dict() for x in before.playlist.entries]
    after_songs = [x.to_dict() for x in after.playlist.entries]
    if before_songs != after_songs or before.album_title != after.album_title or before.album_cover_asset_id != after.album_cover_asset_id:
        events.append(DomainEventType.ALBUM_CHANGED)

    before_layers = {x.layer_id: x.to_dict() for x in before.layers}
    after_layers = {x.layer_id: x.to_dict() for x in after.layers}
    if before_layers != after_layers or before.timeline_mode != after.timeline_mode:
        events.append(DomainEventType.TIMELINE_CHANGED)

    before_visual = [(x.song_id, x.visual_asset_id, x.cover_asset_id) for x in before.playlist.entries]
    after_visual = [(x.song_id, x.visual_asset_id, x.cover_asset_id) for x in after.playlist.entries]
    if before_visual != after_visual:
        events.append(DomainEventType.VISUAL_CHANGED)

    before_template = [x.to_dict() for x in before.layers if x.origin == "template"]
    after_template = [x.to_dict() for x in after.layers if x.origin == "template"]
    if before_template != after_template:
        events.append(DomainEventType.TEMPLATE_APPLIED)

    before_spectrum = [x.to_dict() for x in before.layers if x.type == "spectrum"]
    after_spectrum = [x.to_dict() for x in after.layers if x.type == "spectrum"]
    if before_spectrum != after_spectrum:
        events.append(DomainEventType.SPECTRUM_CHANGED)

    # Preserve declaration order while removing duplicates.
    return tuple(dict.fromkeys(events))
