from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import threading
from typing import Callable, Iterable

from .ai_agent_core_step09 import (
    AgentActionCall,
    AgentContextSnapshot,
    AgentPermission,
    AgentPlan,
    PermissionGrant,
)
from .auto_arrange import AutoArrange, AutoArrangeRecipe
from .editor_commands import EditorCommand, ReorderSongs
from .editor_controller import EditorController, RevisionConflict
from .editor_models import ProjectDocument
from .free_timeline import SetPlaylistTimingMode, SetSongFreeTiming
from .playlist_commands import SetSongCover, SetSongVisual
from .spectrum_step08 import build_preset_command
from .template_studio_step07 import TemplateStudioDraft, build_template_apply_commands, builtin_descriptors
from .visual_precision import SetSongVideoSpeed


class Step09ActionError(ValueError):
    pass


class Step09PermissionError(Step09ActionError):
    pass


class Step09StalePlan(Step09ActionError):
    pass


Resolver = Callable[[ProjectDocument, AgentActionCall, AgentPlan, AgentContextSnapshot], tuple[EditorCommand, ...]]


@dataclass(frozen=True)
class ActionSpec:
    name: str
    permission: str
    description: str
    resolver: Resolver


@dataclass(frozen=True)
class ImpactSummary:
    changed_song_ids: tuple[str, ...]
    changed_layer_ids: tuple[str, ...]
    playlist_order_changed: bool
    canvas_changed: bool
    extensions_changed: bool

    @property
    def change_count(self) -> int:
        return (
            len(self.changed_song_ids)
            + len(self.changed_layer_ids)
            + int(self.playlist_order_changed)
            + int(self.canvas_changed)
            + int(self.extensions_changed)
        )


@dataclass(frozen=True)
class PlanPreview:
    plan_id: str
    before_signature: str
    after_signature: str
    command_count: int
    action_summaries: tuple[str, ...]
    impact: ImpactSummary
    commands: tuple[EditorCommand, ...]

    @property
    def has_changes(self) -> bool:
        return self.before_signature != self.after_signature


@dataclass
class AIExecutionRecord:
    plan_id: str
    result_revision: int
    before_signature: str
    after_signature: str
    duplicate: bool = False
    undone: bool = False


def _ids(value, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise Step09ActionError(f"{label} harus daftar ID yang tidak kosong.")
    result: list[str] = []
    for item in value:
        text = str(item)
        if not text or text in result:
            continue
        result.append(text)
    if not result:
        raise Step09ActionError(f"{label} tidak memiliki ID valid.")
    return tuple(result)


def _float(value, label: str) -> float:
    if isinstance(value, bool):
        raise Step09ActionError(f"{label} tidak valid.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Step09ActionError(f"{label} tidak valid.") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise Step09ActionError(f"{label} tidak valid.")
    return result


def _allowed_song_ids(document: ProjectDocument, context: AgentContextSnapshot) -> set[str]:
    selected = set(context.selected_song_ids)
    return selected if selected else set(document.song_map())


def _assert_song_scope(
    document: ProjectDocument,
    song_ids: Iterable[str],
    plan: AgentPlan,
    context: AgentContextSnapshot,
) -> tuple[str, ...]:
    ids = tuple(str(value) for value in song_ids)
    valid = set(document.song_map())
    if any(song_id not in valid for song_id in ids):
        raise Step09ActionError("Action memuat song_id yang tidak ada pada revision sekarang.")
    allowed = _allowed_song_ids(document, context)
    if any(song_id not in allowed for song_id in ids):
        raise Step09PermissionError("Action mencoba lagu di luar scope/context yang diizinkan.")
    if plan.scope_song_ids and any(song_id not in set(plan.scope_song_ids) for song_id in ids):
        raise Step09PermissionError("Action mencoba lagu di luar scope AgentPlan.")
    return ids


def _resolve_set_song_visual(document, action, plan, context):
    song_ids = _assert_song_scope(document, _ids(action.args.get("song_ids"), "song_ids"), plan, context)
    asset_id = str(action.args.get("asset_id", ""))
    if asset_id not in set(context.allowed_media_ids):
        raise Step09PermissionError("Visual asset berada di luar media yang diizinkan context.")
    asset = document.asset_map().get(asset_id)
    if asset is None or asset.kind not in {"image", "video"}:
        raise Step09ActionError("asset_id Visual harus image/video yang valid.")
    return tuple(SetSongVisual(song_id, asset_id) for song_id in song_ids)


def _resolve_set_song_cover(document, action, plan, context):
    song_ids = _assert_song_scope(document, _ids(action.args.get("song_ids"), "song_ids"), plan, context)
    asset_id = str(action.args.get("asset_id", ""))
    if asset_id not in set(context.allowed_media_ids):
        raise Step09PermissionError("Cover asset berada di luar media yang diizinkan context.")
    asset = document.asset_map().get(asset_id)
    if asset is None or asset.kind != "image":
        raise Step09ActionError("asset_id Cover harus image yang valid.")
    return tuple(SetSongCover(song_id, asset_id) for song_id in song_ids)


def _resolve_video_speed(document, action, plan, context):
    song_ids = _assert_song_scope(document, _ids(action.args.get("song_ids"), "song_ids"), plan, context)
    speed = _float(action.args.get("speed"), "speed")
    return (SetSongVideoSpeed(song_ids, speed),)


def _resolve_auto_arrange(document, action, plan, context):
    if action.args:
        unknown = set(action.args) - {"background_fit"}
        if unknown:
            raise Step09ActionError("auto_arrange_timeline menerima hanya background_fit.")
    fit = str(action.args.get("background_fit", "fill"))
    if fit not in {"fit", "fill", "fit_blur"}:
        raise Step09ActionError("background_fit Auto Susun tidak valid.")
    return (AutoArrange(AutoArrangeRecipe(background_fit=fit)),)


def _resolve_timeline_mode(document, action, plan, context):
    mode = str(action.args.get("mode", ""))
    if mode not in {"packed", "free"}:
        raise Step09ActionError("Mode Timeline harus packed/free.")
    return (SetPlaylistTimingMode(mode),)


def _resolve_song_timing(document, action, plan, context):
    song_id = _assert_song_scope(document, (str(action.args.get("song_id", "")),), plan, context)[0]
    start = _float(action.args.get("start_seconds"), "start_seconds")
    crossfade = _float(action.args.get("crossfade_seconds", 0.0), "crossfade_seconds")
    if not 0.0 <= start <= 86_400.0:
        raise Step09ActionError("start_seconds harus 0..86400.")
    if not 0.0 <= crossfade <= 60.0:
        raise Step09ActionError("crossfade_seconds harus 0..60.")
    commands: list[EditorCommand] = []
    if document.playlist.mode != "free":
        commands.append(SetPlaylistTimingMode("free"))
    commands.append(
        SetSongFreeTiming(
            song_id,
            int(round(start * document.timebase)),
            int(round(crossfade * document.timebase)),
        )
    )
    return tuple(commands)


def _resolve_reorder_playlist(document, action, plan, context):
    ids = _ids(action.args.get("song_ids"), "song_ids")
    current = [song.song_id for song in document.playlist.entries]
    if set(ids) != set(current) or len(ids) != len(current):
        raise Step09ActionError("reorder_playlist harus memuat semua song_id tepat satu kali.")
    return (ReorderSongs(list(ids)),)


def _resolve_apply_template(document, action, plan, context):
    template_id = str(action.args.get("template_id", ""))
    available = {item.template_id for item in builtin_descriptors()}
    if template_id not in available:
        raise Step09ActionError("STEP09 hanya mengizinkan template built-in yang terdaftar pada plan ini.")
    targets = plan.scope_song_ids or tuple(song.song_id for song in document.playlist.entries)
    _assert_song_scope(document, targets, plan, context)
    return build_template_apply_commands(
        document,
        TemplateStudioDraft(template_id=template_id),
        targets,
    )


def _resolve_spectrum_preset(document, action, plan, context):
    layer_id = str(action.args.get("layer_id", ""))
    preset_id = str(action.args.get("preset_id", ""))
    if layer_id not in set(context.selected_layer_ids):
        raise Step09PermissionError("Spectrum layer harus termasuk layer context yang dipilih.")
    return (build_preset_command(document, layer_id, preset_id),)


ACTION_SPECS: dict[str, ActionSpec] = {
    "set_song_visual": ActionSpec(
        "set_song_visual", AgentPermission.VISUAL_WRITE.value,
        "Pasang image/video yang sudah diizinkan ke lagu dalam scope.", _resolve_set_song_visual,
    ),
    "set_song_cover": ActionSpec(
        "set_song_cover", AgentPermission.VISUAL_WRITE.value,
        "Pasang image cover yang sudah diizinkan ke lagu dalam scope.", _resolve_set_song_cover,
    ),
    "set_song_video_speed": ActionSpec(
        "set_song_video_speed", AgentPermission.VISUAL_WRITE.value,
        "Atur playback speed Visual video tanpa mengubah audio timing.", _resolve_video_speed,
    ),
    "auto_arrange_timeline": ActionSpec(
        "auto_arrange_timeline", AgentPermission.TIMELINE_WRITE.value,
        "Jalankan Auto Susun engine lokal sebagai command undoable.", _resolve_auto_arrange,
    ),
    "set_timeline_mode": ActionSpec(
        "set_timeline_mode", AgentPermission.TIMELINE_WRITE.value,
        "Atur mode Packed/Free Timeline.", _resolve_timeline_mode,
    ),
    "set_song_timing": ActionSpec(
        "set_song_timing", AgentPermission.TIMELINE_WRITE.value,
        "Atur start/crossfade lagu pada Free Timeline.", _resolve_song_timing,
    ),
    "reorder_playlist": ActionSpec(
        "reorder_playlist", AgentPermission.PLAYLIST_WRITE.value,
        "Ubah urutan playlist dengan stable song_id.", _resolve_reorder_playlist,
    ),
    "apply_template": ActionSpec(
        "apply_template", AgentPermission.TEMPLATE_WRITE.value,
        "Terapkan template built-in melalui command Template Studio.", _resolve_apply_template,
    ),
    "set_spectrum_preset": ActionSpec(
        "set_spectrum_preset", AgentPermission.SPECTRUM_WRITE.value,
        "Terapkan preset Spectrum parity-safe pada layer context terpilih.", _resolve_spectrum_preset,
    ),
}


def registered_action_names() -> tuple[str, ...]:
    return tuple(ACTION_SPECS)


def required_permissions_for_actions(actions: Iterable[AgentActionCall]) -> tuple[str, ...]:
    result: list[str] = []
    for action in actions:
        action.validate()
        spec = ACTION_SPECS.get(action.name)
        if spec is None:
            raise Step09ActionError(f"Action tidak ada di registry STEP09: {action.name}")
        if spec.permission not in result:
            result.append(spec.permission)
    return tuple(result)


def _impact(before: ProjectDocument, after: ProjectDocument) -> ImpactSummary:
    before_songs = {song.song_id: deepcopy(song.__dict__) for song in before.playlist.entries}
    after_songs = {song.song_id: deepcopy(song.__dict__) for song in after.playlist.entries}
    changed_songs = tuple(
        song_id for song_id in dict.fromkeys([*before_songs, *after_songs])
        if before_songs.get(song_id) != after_songs.get(song_id)
    )
    before_layers = {layer.layer_id: layer.to_dict() if hasattr(layer, "to_dict") else deepcopy(layer.__dict__) for layer in before.layers}
    after_layers = {layer.layer_id: layer.to_dict() if hasattr(layer, "to_dict") else deepcopy(layer.__dict__) for layer in after.layers}
    changed_layers = tuple(
        layer_id for layer_id in dict.fromkeys([*before_layers, *after_layers])
        if before_layers.get(layer_id) != after_layers.get(layer_id)
    )
    before_order = [song.song_id for song in before.playlist.entries]
    after_order = [song.song_id for song in after.playlist.entries]
    return ImpactSummary(
        changed_song_ids=changed_songs,
        changed_layer_ids=changed_layers,
        playlist_order_changed=before_order != after_order,
        canvas_changed=before.canvas != after.canvas,
        extensions_changed=before.extensions != after.extensions,
    )


class Step09TransactionEngine:
    def __init__(self, controller: EditorController) -> None:
        self.controller = controller
        self._executed_plan_ids: set[str] = set()
        self.last_execution: AIExecutionRecord | None = None

    @staticmethod
    def _validate_plan_context(
        document: ProjectDocument,
        plan: AgentPlan,
        context: AgentContextSnapshot,
    ) -> None:
        plan.validate()
        context.validate()
        if plan.project_id != document.project_id or context.project_id != document.project_id:
            raise Step09StalePlan("Plan/context berasal dari proyek berbeda.")
        if plan.expected_revision != document.revision or context.revision != document.revision:
            raise Step09StalePlan("Plan/context stale karena revision proyek berubah.")
        if plan.context_fingerprint != context.fingerprint:
            raise Step09StalePlan("Context fingerprint berubah; interpretasi harus diulang.")
        if plan.scope_song_ids:
            allowed = _allowed_song_ids(document, context)
            if any(song_id not in allowed for song_id in plan.scope_song_ids):
                raise Step09PermissionError("Scope AgentPlan melewati context lagu yang diizinkan.")

    def dry_run(
        self,
        plan: AgentPlan,
        context: AgentContextSnapshot,
        grant: PermissionGrant,
        *,
        cancel_event: threading.Event | None = None,
    ) -> PlanPreview:
        current = self.controller.snapshot()
        self._validate_plan_context(current, plan, context)
        computed_permissions = required_permissions_for_actions(plan.actions)
        if not set(computed_permissions).issubset(set(plan.required_permissions)):
            raise Step09PermissionError("AgentPlan tidak mendeklarasikan seluruh permission action.")
        if not grant.allows(computed_permissions):
            raise Step09PermissionError("Permission pengguna belum mencakup seluruh action plan.")

        simulation = current.clone()
        commands: list[EditorCommand] = []
        summaries: list[str] = []
        for action in plan.actions:
            if cancel_event is not None and cancel_event.is_set():
                raise Step09ActionError("Dry-run dibatalkan.")
            spec = ACTION_SPECS.get(action.name)
            if spec is None:
                raise Step09ActionError(f"Action tidak ada di registry STEP09: {action.name}")
            action_commands = tuple(spec.resolver(simulation, action, plan, context))
            if not action_commands:
                raise Step09ActionError(f"Action {action.name} tidak menghasilkan domain command.")
            simulation, _inverse = EditorController._apply_transaction(simulation, action_commands)
            commands.extend(action_commands)
            summaries.append(f"{action.name}: {spec.description}")

        return PlanPreview(
            plan_id=plan.plan_id,
            before_signature=current.content_signature(),
            after_signature=simulation.content_signature(),
            command_count=len(commands),
            action_summaries=tuple(summaries),
            impact=_impact(current, simulation),
            commands=tuple(commands),
        )

    def execute(
        self,
        plan: AgentPlan,
        context: AgentContextSnapshot,
        grant: PermissionGrant,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AIExecutionRecord:
        if plan.plan_id in self._executed_plan_ids:
            current = self.controller.snapshot()
            return AIExecutionRecord(
                plan.plan_id,
                current.revision,
                current.content_signature(),
                current.content_signature(),
                duplicate=True,
            )
        preview = self.dry_run(plan, context, grant, cancel_event=cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            raise Step09ActionError("Eksekusi dibatalkan sebelum commit.")
        if not preview.has_changes:
            raise Step09ActionError("Plan tidak menghasilkan perubahan proyek.")
        changed = self.controller.dispatch(
            preview.commands,
            expected_revision=plan.expected_revision,
        )
        record = AIExecutionRecord(
            plan_id=plan.plan_id,
            result_revision=changed.revision,
            before_signature=preview.before_signature,
            after_signature=changed.content_signature(),
        )
        self._executed_plan_ids.add(plan.plan_id)
        self.last_execution = record
        return record

    def can_undo_ai(self) -> bool:
        record = self.last_execution
        if record is None or record.undone or not self.controller.can_undo:
            return False
        current = self.controller.snapshot()
        return (
            current.revision == record.result_revision
            and current.content_signature() == record.after_signature
        )

    def undo_ai(self) -> ProjectDocument:
        record = self.last_execution
        if record is None or not self.can_undo_ai():
            raise Step09ActionError(
                "Undo AI tidak aman karena transaction AI bukan lagi edit terakhir. Gunakan Undo normal sesuai urutan history."
            )
        restored = self.controller.undo()
        if restored.content_signature() != record.before_signature:
            raise Step09ActionError("Undo AI tidak memulihkan signature sebelum transaction.")
        record.undone = True
        return restored
