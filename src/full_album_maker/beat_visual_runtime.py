from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import threading

from .audio_analysis_cache import AudioAnalysisCache
from .audio_analysis_service import AudioAnalysisService
from .editor_models import Layer, ProjectDocument, Transform
from .music_event_engine import build_music_event_timeline
from .music_event_projection import project_album_events
from .animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from .timeline_resolver import TimelineResolver
from .visual_binding_contract import VisualBindingSet, VisualPropertyState
from .visual_binding_engine import VisualPropertyBindingEngine, apply_visual_state
from .beat_animation_assignment import assignment_for_layer, beat_enabled_layer_ids, document_has_beat_animation


class BeatRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BeatRuntimeDiagnostics:
    analyzed_assets: int
    beat_layers: int
    event_count: int
    trigger_count: int


class BeatVisualRuntime:
    def __init__(
        self,
        document_signature: str,
        duration_tick: int,
        signal_engine: AnimationSignalEngine,
        bindings_by_layer_id: dict[str, VisualBindingSet],
        diagnostics: BeatRuntimeDiagnostics,
    ) -> None:
        self.document_signature = document_signature
        self.duration_tick = int(duration_tick)
        self.signal_engine = signal_engine
        self.bindings_by_layer_id = dict(bindings_by_layer_id)
        self._engines = {
            layer_id: VisualPropertyBindingEngine(signal_engine, binding_set)
            for layer_id, binding_set in bindings_by_layer_id.items()
        }
        self.diagnostics = diagnostics

    def has_layer(self, layer_id: str) -> bool:
        return layer_id in self._engines

    def binding_set(self, layer_id: str) -> VisualBindingSet:
        try:
            return self.bindings_by_layer_id[layer_id]
        except KeyError as exc:
            raise KeyError(layer_id) from exc

    def state_for_layer(self, layer_id: str, tick: int) -> VisualPropertyState:
        try:
            engine = self._engines[layer_id]
        except KeyError as exc:
            raise KeyError(layer_id) from exc
        return engine.state(tick)

    def effective_for_layer(self, layer: Layer, tick: int, *, render_geometry: bool = True):
        state = self.state_for_layer(layer.layer_id, tick)
        if render_geometry and abs(state.zoom_multiplier - 1.0) > 1e-12:
            state = replace(
                state,
                scale_multiplier=max(0.75, min(1.35, state.scale_multiplier * state.zoom_multiplier)),
                zoom_multiplier=1.0,
            )
        return apply_visual_state(layer.transform, layer.opacity, state), state


def _active_audio_assets(document: ProjectDocument):
    assets = document.asset_map()
    seen: set[str] = set()
    result = []
    for song in document.playlist.entries:
        if not song.enabled or song.asset_id in seen:
            continue
        asset = assets[song.asset_id]
        if asset.kind != "audio":
            continue
        seen.add(song.asset_id)
        result.append(asset)
    return tuple(result)


def ensure_beat_analysis(
    document: ProjectDocument,
    *,
    cache: AudioAnalysisCache | None = None,
    ffmpeg_executable: str | None = None,
    cancel_event: threading.Event | None = None,
    timeout: float = 900.0,
) -> dict[str, object]:
    document.validate()
    if not document_has_beat_animation(document):
        return {}
    cache_obj = cache or AudioAnalysisCache()
    service = AudioAnalysisService(cache=cache_obj, ffmpeg_executable=ffmpeg_executable)
    errors: list[tuple[str, str]] = []
    service.request_failed.connect(lambda ticket, error: errors.append((error.code, error.message)))
    try:
        assets = _active_audio_assets(document)
        for asset in assets:
            if cancel_event is not None and cancel_event.is_set():
                raise BeatRuntimeError("CANCELLED", "Persiapan Beat Animation dibatalkan.")
            cached = service.peek_cached(asset)
            if cached is None:
                service.request(asset)
        if not service.wait_for_idle(timeout):
            service.cancel()
            raise BeatRuntimeError("ANALYSIS_TIMEOUT", "Analisis Beat Animation melewati batas waktu.")
        if errors:
            code, message = errors[0]
            raise BeatRuntimeError(code, message)
        results: dict[str, object] = {}
        for asset in assets:
            if cancel_event is not None and cancel_event.is_set():
                raise BeatRuntimeError("CANCELLED", "Persiapan Beat Animation dibatalkan.")
            result = service.peek_cached(asset)
            if result is None:
                raise BeatRuntimeError("CACHE_MISS_AFTER_ANALYSIS", f"Cache analisis belum tersedia: {asset.original_name or Path(asset.locator).name}")
            results[asset.asset_id] = result
        return results
    finally:
        service.close()


def build_beat_visual_runtime(
    document: ProjectDocument,
    *,
    analysis_results: dict[str, object] | None = None,
    cache: AudioAnalysisCache | None = None,
    ffmpeg_executable: str | None = None,
    cancel_event: threading.Event | None = None,
    ensure_analysis: bool = True,
) -> BeatVisualRuntime | None:
    snapshot = document.clone()
    snapshot.validate()
    layer_ids = beat_enabled_layer_ids(snapshot)
    if not layer_ids:
        return None

    if analysis_results is None:
        if ensure_analysis:
            analysis_results = ensure_beat_analysis(
                snapshot,
                cache=cache,
                ffmpeg_executable=ffmpeg_executable,
                cancel_event=cancel_event,
            )
        else:
            analysis_results = {}
            cache_obj = cache or AudioAnalysisCache()
            service = AudioAnalysisService(cache=cache_obj, ffmpeg_executable=ffmpeg_executable)
            try:
                for asset in _active_audio_assets(snapshot):
                    result = service.peek_cached(asset)
                    if result is None:
                        raise BeatRuntimeError("ANALYSIS_CACHE_MISS", f"Analisis Beat belum tersedia: {asset.original_name or Path(asset.locator).name}")
                    analysis_results[asset.asset_id] = result
            finally:
                service.close()

    timelines = {}
    for asset_id, result in analysis_results.items():
        timelines[asset_id] = build_music_event_timeline(result)
    resolved = TimelineResolver().resolve(snapshot)
    if resolved.errors:
        raise BeatRuntimeError("TIMELINE_INVALID", " | ".join(resolved.errors))
    projected = project_album_events(snapshot, timelines, resolved=resolved)
    program = build_animation_signal_program(projected, resolved.duration_tick)
    signal_engine = AnimationSignalEngine(program)

    layer_map = snapshot.layer_map()
    bindings: dict[str, VisualBindingSet] = {}
    for layer_id in layer_ids:
        assignment = assignment_for_layer(layer_map[layer_id])
        if assignment is not None:
            bindings[layer_id] = assignment.binding_set()
    diagnostics = BeatRuntimeDiagnostics(
        analyzed_assets=len(analysis_results),
        beat_layers=len(bindings),
        event_count=len(projected),
        trigger_count=len(program.triggers),
    )
    return BeatVisualRuntime(
        snapshot.content_signature(),
        resolved.duration_tick,
        signal_engine,
        bindings,
        diagnostics,
    )


def apply_beat_snapshot(
    document: ProjectDocument,
    runtime: BeatVisualRuntime | None,
    tick: int,
) -> ProjectDocument:
    snapshot = document.clone()
    if runtime is None:
        return snapshot
    if tick < 0:
        raise ValueError("tick must be non-negative")
    for layer in snapshot.layers:
        if not runtime.has_layer(layer.layer_id):
            continue
        effective, state = runtime.effective_for_layer(layer, tick, render_geometry=True)
        layer.transform = Transform(
            x=effective.x,
            y=effective.y,
            width=effective.width,
            height=effective.height,
            rotation=effective.rotation,
            pivot_x=effective.pivot_x,
            pivot_y=effective.pivot_y,
        )
        layer.opacity = effective.opacity
        layer.properties = dict(layer.properties)
        layer.properties["_beat_snapshot_glow"] = float(state.glow_amount)
        layer.animation = dict(layer.animation)
        layer.animation.pop("beat_v1", None)
    snapshot.validate()
    return snapshot
