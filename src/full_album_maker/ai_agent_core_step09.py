from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable

from .ai_editor_v14 import V14EditorAIContextBuilder
from .editor_models import ProjectDocument


PLAN_FORMAT = "full-album-maker-agent-plan-v1"
CONTEXT_FORMAT = "full-album-maker-agent-context-v1"
MAX_PLAN_ACTIONS = 100
MAX_PROMPT_CHARS = 4000


class AgentState(str, Enum):
    IDLE = "IDLE"
    INTERPRETING = "INTERPRETING"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    PLAN_READY = "PLAN_READY"
    PREVIEW_READY = "PREVIEW_READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentPermission(str, Enum):
    VISUAL_WRITE = "visual.write"
    TIMELINE_WRITE = "timeline.write"
    PLAYLIST_WRITE = "playlist.write"
    TEMPLATE_WRITE = "template.write"
    SPECTRUM_WRITE = "spectrum.write"


_ALLOWED_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.INTERPRETING},
    AgentState.INTERPRETING: {
        AgentState.NEEDS_CLARIFICATION,
        AgentState.PLAN_READY,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.NEEDS_CLARIFICATION: {
        AgentState.INTERPRETING,
        AgentState.CANCELLED,
        AgentState.IDLE,
    },
    AgentState.PLAN_READY: {
        AgentState.PREVIEW_READY,
        AgentState.INTERPRETING,
        AgentState.CANCELLED,
        AgentState.FAILED,
    },
    AgentState.PREVIEW_READY: {
        AgentState.EXECUTING,
        AgentState.INTERPRETING,
        AgentState.CANCELLED,
        AgentState.FAILED,
    },
    AgentState.EXECUTING: {
        AgentState.COMPLETED,
        AgentState.FAILED,
        AgentState.CANCELLED,
    },
    AgentState.COMPLETED: {AgentState.IDLE, AgentState.INTERPRETING},
    AgentState.FAILED: {AgentState.IDLE, AgentState.INTERPRETING},
    AgentState.CANCELLED: {AgentState.IDLE, AgentState.INTERPRETING},
}


@dataclass
class AgentStateMachine:
    state: AgentState = AgentState.IDLE
    error: str = ""

    def transition(self, target: AgentState, *, error: str = "") -> AgentState:
        target = AgentState(target)
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"Transisi state AI tidak valid: {self.state.value} -> {target.value}")
        self.state = target
        self.error = str(error) if target == AgentState.FAILED else ""
        return self.state

    def reset(self) -> None:
        self.state = AgentState.IDLE
        self.error = ""


@dataclass(frozen=True)
class AgentActionCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.name):
            raise ValueError("Nama action AI tidak valid.")
        if not isinstance(self.args, dict):
            raise ValueError("Argumen action AI harus object.")
        raw = json.dumps(self.args, ensure_ascii=False, sort_keys=True, default=str)
        if len(raw) > 16_000:
            raise ValueError("Argumen action AI terlalu besar.")


@dataclass(frozen=True)
class AgentPlan:
    plan_id: str
    project_id: str
    expected_revision: int
    context_fingerprint: str
    prompt_summary: str
    scope_song_ids: tuple[str, ...]
    actions: tuple[AgentActionCall, ...]
    required_permissions: tuple[str, ...]
    provider: str = "mock"
    format: str = PLAN_FORMAT

    def validate(self) -> None:
        if self.format != PLAN_FORMAT:
            raise ValueError("Format AgentPlan tidak didukung.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.plan_id):
            raise ValueError("plan_id harus SHA-256 lowercase.")
        if not self.project_id:
            raise ValueError("project_id AgentPlan kosong.")
        if int(self.expected_revision) < 0:
            raise ValueError("expected_revision AgentPlan tidak valid.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.context_fingerprint):
            raise ValueError("context_fingerprint AgentPlan tidak valid.")
        if len(self.prompt_summary) > 500:
            raise ValueError("Ringkasan prompt terlalu panjang.")
        if len(self.actions) > MAX_PLAN_ACTIONS:
            raise ValueError("AgentPlan memiliki terlalu banyak action.")
        if len(set(self.scope_song_ids)) != len(self.scope_song_ids):
            raise ValueError("scope_song_ids AgentPlan duplikat.")
        allowed_permissions = {item.value for item in AgentPermission}
        if any(value not in allowed_permissions for value in self.required_permissions):
            raise ValueError("AgentPlan meminta permission yang tidak dikenal.")
        for action in self.actions:
            action.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "format": self.format,
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "expected_revision": self.expected_revision,
            "context_fingerprint": self.context_fingerprint,
            "prompt_summary": self.prompt_summary,
            "scope_song_ids": list(self.scope_song_ids),
            "actions": [
                {"name": action.name, "args": action.args}
                for action in self.actions
            ],
            "required_permissions": list(self.required_permissions),
            "provider": self.provider,
        }


@dataclass(frozen=True)
class AgentContextSnapshot:
    project_id: str
    revision: int
    selected_song_ids: tuple[str, ...]
    selected_layer_ids: tuple[str, ...]
    allowed_media_ids: tuple[str, ...]
    enabled_contexts: tuple[str, ...]
    payload: dict[str, Any]
    fingerprint: str
    format: str = CONTEXT_FORMAT

    def validate(self) -> None:
        if self.format != CONTEXT_FORMAT:
            raise ValueError("Format context AI tidak didukung.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("Fingerprint context AI tidak valid.")
        raw = json.dumps(self.payload, ensure_ascii=False, sort_keys=True)
        forbidden = ("api_key", "authorization", "bearer ", "locator", "vault_path")
        lowered = raw.casefold()
        if any(marker in lowered for marker in forbidden):
            raise ValueError("Context AI mengandung field sensitif/path yang dilarang.")


@dataclass(frozen=True)
class ProviderInterpretation:
    message: str
    plan: AgentPlan | None = None
    clarification: str = ""

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarification) or self.plan is None


@dataclass(frozen=True)
class PermissionGrant:
    permissions: frozenset[str]

    def allows(self, required: Iterable[str]) -> bool:
        requested = set(required)
        return requested.issubset(self.permissions)

    @classmethod
    def all_editor_writes(cls) -> "PermissionGrant":
        return cls(frozenset(item.value for item in AgentPermission))


def _stable_unique(values: Iterable[str], valid: set[str] | None = None) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value)
        if not item or item in seen:
            continue
        if valid is not None and item not in valid:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)


def build_agent_context_snapshot(
    document: ProjectDocument,
    *,
    selected_song_ids: Iterable[str] = (),
    selected_layer_ids: Iterable[str] = (),
    allowed_media_ids: Iterable[str] = (),
    enabled_contexts: Iterable[str] = ("media", "timeline", "template", "spectrum"),
    user_text: str = "",
    template_ids: Iterable[str] = (),
) -> AgentContextSnapshot:
    """Build bounded, path-free context using the recovered V1.4 builder.

    Selection and allowed-media lists are explicit capabilities: the provider may
    refer only to IDs present here. Paths, keys and raw arbitrary metadata never
    enter the payload.
    """

    songs = set(document.song_map())
    layers = set(document.layer_map())
    media = set(document.asset_map())
    selected_songs = _stable_unique(selected_song_ids, songs)
    selected_layers = _stable_unique(selected_layer_ids, layers)
    allowed_media = _stable_unique(allowed_media_ids, media)
    contexts = _stable_unique(enabled_contexts)

    payload = V14EditorAIContextBuilder().build(
        document,
        selected_layer_ids=selected_layers,
        user_text=str(user_text)[:MAX_PROMPT_CHARS],
        template_ids=template_ids,
    )
    allowed = set(allowed_media)
    if allowed:
        payload["media_candidates"] = [
            item for item in payload.get("media_candidates", [])
            if str(item.get("asset_id", "")) in allowed
        ]
    else:
        payload["media_candidates"] = []
    payload["selected_song_ids"] = list(selected_songs)
    payload["enabled_contexts"] = list(contexts)
    payload["permission_boundary"] = {
        "media_asset_ids": list(allowed_media),
        "song_ids": list(selected_songs),
    }
    payload["format"] = CONTEXT_FORMAT

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    snapshot = AgentContextSnapshot(
        project_id=document.project_id,
        revision=document.revision,
        selected_song_ids=selected_songs,
        selected_layer_ids=selected_layers,
        allowed_media_ids=allowed_media,
        enabled_contexts=contexts,
        payload=payload,
        fingerprint=fingerprint,
    )
    snapshot.validate()
    return snapshot


def deterministic_plan_id(
    *,
    project_id: str,
    revision: int,
    context_fingerprint: str,
    prompt: str,
    actions: Iterable[AgentActionCall],
) -> str:
    normalized_prompt = " ".join(str(prompt).split())[:MAX_PROMPT_CHARS]
    action_list = tuple(actions)
    for action in action_list:
        action.validate()
    payload = {
        "project_id": project_id,
        "revision": int(revision),
        "context_fingerprint": context_fingerprint,
        "prompt": normalized_prompt,
        "actions": [
            {"name": action.name, "args": action.args}
            for action in action_list
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
