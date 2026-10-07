from __future__ import annotations

from dataclasses import dataclass

from .editor_models import Layer
from .visual_binding_contract import CoreBeatPreset, VisualBindingSet
from .visual_binding_engine import combine_binding_sets, core_binding_set

BEAT_ASSIGNMENT_KEY = "beat_v1"


@dataclass(frozen=True)
class BeatAnimationAssignment:
    enabled: bool
    presets: tuple[CoreBeatPreset, ...]

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("beat_v1.enabled must be boolean")
        if not self.presets:
            raise ValueError("beat_v1 requires at least one preset")
        if len(set(self.presets)) != len(self.presets):
            raise ValueError("beat_v1 presets must be unique")
        if len(self.presets) > len(CoreBeatPreset):
            raise ValueError("too many beat_v1 presets")

    def binding_set(self) -> VisualBindingSet:
        self.validate()
        return combine_binding_sets(
            *(core_binding_set(preset) for preset in self.presets),
            binding_set_id="beat_v1:" + "+".join(p.value for p in self.presets),
        )


def assignment_for_layer(layer: Layer) -> BeatAnimationAssignment | None:
    raw = layer.animation.get(BEAT_ASSIGNMENT_KEY)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("layer.animation.beat_v1 must be an object")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("beat_v1.enabled must be boolean")
    if not enabled:
        return None
    raw_presets = raw.get("presets", ())
    if not isinstance(raw_presets, (list, tuple)):
        raise ValueError("beat_v1.presets must be a list")
    presets: list[CoreBeatPreset] = []
    for value in raw_presets:
        try:
            preset = value if isinstance(value, CoreBeatPreset) else CoreBeatPreset(str(value))
        except ValueError as exc:
            raise ValueError(f"unknown beat_v1 preset: {value}") from exc
        presets.append(preset)
    result = BeatAnimationAssignment(True, tuple(presets))
    result.validate()
    return result


def document_has_beat_animation(document) -> bool:
    track_map = {track.track_id: track for track in document.tracks}
    for layer in document.layers:
        track = track_map.get(layer.track_id)
        if not layer.enabled or track is None or not track.enabled:
            continue
        if assignment_for_layer(layer) is not None:
            return True
    return False


def beat_enabled_layer_ids(document) -> tuple[str, ...]:
    track_map = {track.track_id: track for track in document.tracks}
    values: list[str] = []
    for layer in document.layers:
        track = track_map.get(layer.track_id)
        if not layer.enabled or track is None or not track.enabled:
            continue
        if assignment_for_layer(layer) is not None:
            values.append(layer.layer_id)
    return tuple(values)
