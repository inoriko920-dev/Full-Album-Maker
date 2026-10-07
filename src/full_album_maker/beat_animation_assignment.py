from __future__ import annotations

from dataclasses import dataclass
import math

from .editor_models import Layer
from .advanced_motion_contract import AdvancedMotionPreset
from .visual_binding_contract import (
    CoreBeatPreset,
    VisualBinding,
    VisualBindingSet,
    visual_property_amount_bounds,
)
from .visual_binding_engine import combine_binding_sets, core_binding_set

BEAT_ASSIGNMENT_KEY = "beat_v1"


@dataclass(frozen=True)
class BeatAnimationAssignment:
    enabled: bool
    presets: tuple[CoreBeatPreset, ...]
    intensity: float = 1.0
    motion_preset: AdvancedMotionPreset | None = None
    motion_intensity: float = 1.0

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("beat_v1.enabled must be boolean")
        if not self.presets:
            raise ValueError("beat_v1 requires at least one preset")
        if len(set(self.presets)) != len(self.presets):
            raise ValueError("beat_v1 presets must be unique")
        if len(self.presets) > len(CoreBeatPreset):
            raise ValueError("too many beat_v1 presets")
        value = float(self.intensity)
        if not math.isfinite(value) or not 0.0 <= value <= 2.0:
            raise ValueError("beat_v1.intensity must be in 0..2")
        if self.motion_preset is not None and not isinstance(self.motion_preset, AdvancedMotionPreset):
            raise ValueError("beat_v1.motion_preset invalid")
        motion_value = float(self.motion_intensity)
        if not math.isfinite(motion_value) or not 0.0 <= motion_value <= 2.0:
            raise ValueError("beat_v1.motion_intensity must be in 0..2")

    def binding_set(self) -> VisualBindingSet:
        self.validate()
        base = combine_binding_sets(
            *(core_binding_set(preset) for preset in self.presets),
            binding_set_id="beat_v1:" + "+".join(p.value for p in self.presets),
        )
        scaled = VisualBindingSet(
            binding_set_id=f"{base.binding_set_id}:intensity={float(self.intensity):.6f}",
            bindings=tuple(
                VisualBinding(
                    channel=binding.channel,
                    property=binding.property,
                    amount=max(
                        visual_property_amount_bounds(binding.property)[0],
                        min(
                            visual_property_amount_bounds(binding.property)[1],
                            float(binding.amount) * float(self.intensity),
                        ),
                    ),
                    response_gamma=binding.response_gamma,
                    min_signal=binding.min_signal,
                )
                for binding in base.bindings
            ),
        )
        scaled.validate()
        return scaled


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
    try:
        intensity = float(raw.get("intensity", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("beat_v1.intensity must be numeric") from exc
    raw_motion = raw.get("motion_preset")
    motion_preset = None
    if raw_motion not in {None, "", "none"}:
        try:
            motion_preset = raw_motion if isinstance(raw_motion, AdvancedMotionPreset) else AdvancedMotionPreset(str(raw_motion))
        except ValueError as exc:
            raise ValueError(f"unknown beat_v1 motion preset: {raw_motion}") from exc
    try:
        motion_intensity = float(raw.get("motion_intensity", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("beat_v1.motion_intensity must be numeric") from exc
    result = BeatAnimationAssignment(True, tuple(presets), intensity, motion_preset, motion_intensity)
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
