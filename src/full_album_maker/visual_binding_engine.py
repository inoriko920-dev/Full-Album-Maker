from __future__ import annotations

import math

from .animation_signal_contract import AnimationSignalChannel
from .animation_signal_engine import AnimationSignalEngine
from .editor_models import Transform
from .visual_binding_contract import (
    CoreBeatPreset,
    EffectiveLayerVisual,
    VisualBinding,
    VisualBindingSet,
    VisualProperty,
    VisualPropertyState,
    visual_binding_sort_key,
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _response(signal: float, binding: VisualBinding) -> float:
    binding.validate()
    value = _clamp(signal, 0.0, 1.0)
    threshold = float(binding.min_signal)
    if value + 1e-12 < threshold:
        return 0.0
    if threshold >= 1.0:
        normalized = 1.0 if value >= 1.0 else 0.0
    else:
        normalized = _clamp((value - threshold) / (1.0 - threshold), 0.0, 1.0)
    return normalized ** float(binding.response_gamma)


def core_binding_set(preset: CoreBeatPreset | str) -> VisualBindingSet:
    try:
        selected = preset if isinstance(preset, CoreBeatPreset) else CoreBeatPreset(str(preset))
    except ValueError as exc:
        raise KeyError(preset) from exc

    mapping: dict[CoreBeatPreset, tuple[VisualBinding, ...]] = {
        CoreBeatPreset.SUBTLE_BEAT_PULSE: (
            VisualBinding(AnimationSignalChannel.BEAT, VisualProperty.SCALE_MULTIPLIER, 0.025),
        ),
        CoreBeatPreset.BASS_PULSE: (
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.SCALE_MULTIPLIER, 0.060),
        ),
        CoreBeatPreset.STRONG_PUNCH: (
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.SCALE_MULTIPLIER, 0.080),
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.ZOOM_MULTIPLIER, 0.060),
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.GLOW_AMOUNT, 0.350),
        ),
        CoreBeatPreset.ONSET_FLASH: (
            VisualBinding(AnimationSignalChannel.ONSET, VisualProperty.GLOW_AMOUNT, 0.280),
        ),
        CoreBeatPreset.ROTATION_NUDGE: (
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.ROTATION_OFFSET_DEG, 2.0),
        ),
        CoreBeatPreset.ENERGY_BREATHE: (
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.SCALE_MULTIPLIER, 0.030),
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.GLOW_AMOUNT, 0.200),
        ),
        CoreBeatPreset.BEAT_ZOOM: (
            VisualBinding(AnimationSignalChannel.BEAT, VisualProperty.ZOOM_MULTIPLIER, 0.035),
        ),
        CoreBeatPreset.BASS_ZOOM: (
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.ZOOM_MULTIPLIER, 0.070),
        ),
        CoreBeatPreset.GLOW_PUMP: (
            VisualBinding(AnimationSignalChannel.BEAT, VisualProperty.GLOW_AMOUNT, 0.220),
        ),
        CoreBeatPreset.BASS_GLOW: (
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.GLOW_AMOUNT, 0.420),
        ),
        CoreBeatPreset.STRONG_GLOW: (
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.GLOW_AMOUNT, 0.600),
        ),
        CoreBeatPreset.BEAT_TILT: (
            VisualBinding(AnimationSignalChannel.BEAT, VisualProperty.ROTATION_OFFSET_DEG, 1.200),
        ),
        CoreBeatPreset.BASS_TILT: (
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.ROTATION_OFFSET_DEG, 2.500),
        ),
        CoreBeatPreset.ENERGY_ZOOM: (
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.ZOOM_MULTIPLIER, 0.045),
        ),
        CoreBeatPreset.ENERGY_GLOW: (
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.GLOW_AMOUNT, 0.350),
        ),
        CoreBeatPreset.CLUB_PUNCH: (
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.SCALE_MULTIPLIER, 0.110, response_gamma=0.82, min_signal=0.10),
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.ZOOM_MULTIPLIER, 0.090, response_gamma=0.82, min_signal=0.10),
            VisualBinding(AnimationSignalChannel.STRONG_BEAT, VisualProperty.GLOW_AMOUNT, 0.550, response_gamma=0.82, min_signal=0.10),
        ),
        CoreBeatPreset.BASS_PUNCH: (
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.SCALE_MULTIPLIER, 0.085),
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.ZOOM_MULTIPLIER, 0.045),
            VisualBinding(AnimationSignalChannel.BASS, VisualProperty.GLOW_AMOUNT, 0.300),
        ),
        CoreBeatPreset.CINEMATIC_SWELL: (
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.SCALE_MULTIPLIER, 0.050),
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.ZOOM_MULTIPLIER, 0.040),
            VisualBinding(AnimationSignalChannel.ENERGY_UP, VisualProperty.GLOW_AMOUNT, 0.280),
        ),
    }
    result = VisualBindingSet(selected.value, mapping[selected])
    result.validate()
    return result


def combine_binding_sets(*sets: VisualBindingSet, binding_set_id: str | None = None) -> VisualBindingSet:
    for value in sets:
        value.validate()
    if binding_set_id is None:
        names = sorted(value.binding_set_id for value in sets)
        binding_set_id = "combo:" + "+".join(names) if names else "combo:empty"
    bindings = tuple(sorted((binding for value in sets for binding in value.bindings), key=visual_binding_sort_key))
    result = VisualBindingSet(binding_set_id, bindings)
    result.validate()
    return result


def supported_properties_for_layer(layer_type: str) -> tuple[VisualProperty, ...]:
    common = (
        VisualProperty.SCALE_MULTIPLIER,
        VisualProperty.OPACITY_MULTIPLIER,
        VisualProperty.ROTATION_OFFSET_DEG,
        VisualProperty.X_OFFSET_NORMALIZED,
        VisualProperty.Y_OFFSET_NORMALIZED,
    )
    full = common + (VisualProperty.ZOOM_MULTIPLIER, VisualProperty.GLOW_AMOUNT)
    policies = {
        "song_cover": full,
        "vinyl": full,
        "song_visual": full,
        "background": full,
        "spectrum": common + (VisualProperty.GLOW_AMOUNT,),
        "text": common + (VisualProperty.GLOW_AMOUNT,),
        "song_title": common + (VisualProperty.GLOW_AMOUNT,),
        "playlist_visual": common + (VisualProperty.GLOW_AMOUNT,),
        "progress": (VisualProperty.OPACITY_MULTIPLIER,),
        "song_time": (VisualProperty.OPACITY_MULTIPLIER,),
    }
    return policies.get(str(layer_type), ())


class VisualPropertyBindingEngine:
    def __init__(self, signal_engine: AnimationSignalEngine, binding_set: VisualBindingSet) -> None:
        binding_set.validate()
        self.signal_engine = signal_engine
        self.binding_set = binding_set
        self._ordered = tuple(sorted(binding_set.bindings, key=visual_binding_sort_key))
        self._channels = tuple(sorted({binding.channel for binding in self._ordered}, key=lambda c: c.value))

    def state(self, tick: int) -> VisualPropertyState:
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if not self._ordered:
            return VisualPropertyState.neutral()
        sample = self.signal_engine.sample(tick, self._channels)
        values = {channel: value for channel, value in sample.values}
        scale_delta = 0.0
        zoom_delta = 0.0
        opacity_delta = 0.0
        rotation = 0.0
        x_offset = 0.0
        y_offset = 0.0
        glow_remainder = 1.0

        for binding in self._ordered:
            response = _response(values[binding.channel], binding)
            contribution = float(binding.amount) * response
            prop = binding.property
            if prop == VisualProperty.SCALE_MULTIPLIER:
                scale_delta += contribution
            elif prop == VisualProperty.ZOOM_MULTIPLIER:
                zoom_delta += contribution
            elif prop == VisualProperty.OPACITY_MULTIPLIER:
                opacity_delta += contribution
            elif prop == VisualProperty.ROTATION_OFFSET_DEG:
                rotation += contribution
            elif prop == VisualProperty.X_OFFSET_NORMALIZED:
                x_offset += contribution
            elif prop == VisualProperty.Y_OFFSET_NORMALIZED:
                y_offset += contribution
            elif prop == VisualProperty.GLOW_AMOUNT:
                glow_remainder *= 1.0 - _clamp(contribution, 0.0, 1.0)
            else:
                raise ValueError(f"unsupported visual property: {prop}")

        state = VisualPropertyState(
            scale_multiplier=_clamp(1.0 + scale_delta, 0.75, 1.35),
            zoom_multiplier=_clamp(1.0 + zoom_delta, 1.0, 1.25),
            opacity_multiplier=_clamp(1.0 + opacity_delta, 0.0, 1.25),
            rotation_offset_deg=_clamp(rotation, -12.0, 12.0),
            x_offset_normalized=_clamp(x_offset, -0.15, 0.15),
            y_offset_normalized=_clamp(y_offset, -0.15, 0.15),
            glow_amount=_clamp(1.0 - glow_remainder, 0.0, 1.0),
        )
        state.validate()
        return state


def apply_visual_state(base_transform: Transform, base_opacity: float, state: VisualPropertyState) -> EffectiveLayerVisual:
    state.validate()
    base = Transform(**vars(base_transform))
    base.validate()
    opacity = float(base_opacity)
    if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
        raise ValueError("base_opacity must be in 0..1")

    width = _clamp(base.width * state.scale_multiplier, 0.02, 3.0)
    height = _clamp(base.height * state.scale_multiplier, 0.02, 3.0)
    pivot_abs_x = base.x + base.pivot_x * base.width
    pivot_abs_y = base.y + base.pivot_y * base.height
    x = pivot_abs_x - base.pivot_x * width + state.x_offset_normalized
    y = pivot_abs_y - base.pivot_y * height + state.y_offset_normalized

    result = EffectiveLayerVisual(
        x=_clamp(x, -2.0, 2.0),
        y=_clamp(y, -2.0, 2.0),
        width=width,
        height=height,
        rotation=_clamp(base.rotation + state.rotation_offset_deg, -180.0, 180.0),
        opacity=_clamp(opacity * state.opacity_multiplier, 0.0, 1.0),
        pivot_x=base.pivot_x,
        pivot_y=base.pivot_y,
        zoom_multiplier=state.zoom_multiplier,
        glow_amount=state.glow_amount,
    )
    result.validate()
    return result
