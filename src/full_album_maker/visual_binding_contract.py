from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from .animation_signal_contract import AnimationSignalChannel

VISUAL_BINDING_ENGINE_VERSION = "visual-bindings-v1"


class VisualProperty(str, Enum):
    SCALE_MULTIPLIER = "scale_multiplier"
    ZOOM_MULTIPLIER = "zoom_multiplier"
    OPACITY_MULTIPLIER = "opacity_multiplier"
    ROTATION_OFFSET_DEG = "rotation_offset_deg"
    X_OFFSET_NORMALIZED = "x_offset_normalized"
    Y_OFFSET_NORMALIZED = "y_offset_normalized"
    GLOW_AMOUNT = "glow_amount"


class CoreBeatPreset(str, Enum):
    SUBTLE_BEAT_PULSE = "subtle_beat_pulse"
    BASS_PULSE = "bass_pulse"
    STRONG_PUNCH = "strong_punch"
    ONSET_FLASH = "onset_flash"
    ROTATION_NUDGE = "rotation_nudge"
    ENERGY_BREATHE = "energy_breathe"
    BEAT_ZOOM = "beat_zoom"
    BASS_ZOOM = "bass_zoom"
    GLOW_PUMP = "glow_pump"
    BASS_GLOW = "bass_glow"
    STRONG_GLOW = "strong_glow"
    BEAT_TILT = "beat_tilt"
    BASS_TILT = "bass_tilt"
    ENERGY_ZOOM = "energy_zoom"
    ENERGY_GLOW = "energy_glow"
    CLUB_PUNCH = "club_punch"
    BASS_PUNCH = "bass_punch"
    CINEMATIC_SWELL = "cinematic_swell"


_PROPERTY_AMOUNT_BOUNDS: dict[VisualProperty, tuple[float, float]] = {
    VisualProperty.SCALE_MULTIPLIER: (-0.25, 0.35),
    VisualProperty.ZOOM_MULTIPLIER: (0.0, 0.25),
    VisualProperty.OPACITY_MULTIPLIER: (-1.0, 0.25),
    VisualProperty.ROTATION_OFFSET_DEG: (-12.0, 12.0),
    VisualProperty.X_OFFSET_NORMALIZED: (-0.15, 0.15),
    VisualProperty.Y_OFFSET_NORMALIZED: (-0.15, 0.15),
    VisualProperty.GLOW_AMOUNT: (0.0, 1.0),
}


@dataclass(frozen=True)
class VisualBinding:
    channel: AnimationSignalChannel
    property: VisualProperty
    amount: float
    response_gamma: float = 1.0
    min_signal: float = 0.0

    def validate(self) -> None:
        if not isinstance(self.channel, AnimationSignalChannel):
            raise ValueError("binding channel is invalid")
        if not isinstance(self.property, VisualProperty):
            raise ValueError("binding property is invalid")
        amount = float(self.amount)
        if not math.isfinite(amount):
            raise ValueError("binding amount must be finite")
        low, high = _PROPERTY_AMOUNT_BOUNDS[self.property]
        if not low <= amount <= high:
            raise ValueError(f"binding amount for {self.property.value} must be in {low}..{high}")
        gamma = float(self.response_gamma)
        if not math.isfinite(gamma) or gamma <= 0.0:
            raise ValueError("response_gamma must be finite and > 0")
        threshold = float(self.min_signal)
        if not math.isfinite(threshold) or not 0.0 <= threshold <= 0.95:
            raise ValueError("min_signal must be in 0..0.95")


@dataclass(frozen=True)
class VisualBindingSet:
    binding_set_id: str
    bindings: tuple[VisualBinding, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.binding_set_id, str) or not self.binding_set_id.strip():
            raise ValueError("binding_set_id is required")
        for binding in self.bindings:
            binding.validate()

    def signature(self) -> str:
        self.validate()
        payload = {
            "engine_version": VISUAL_BINDING_ENGINE_VERSION,
            "binding_set_id": self.binding_set_id,
            "bindings": [
                {
                    "channel": b.channel.value,
                    "property": b.property.value,
                    "amount": float(b.amount),
                    "response_gamma": float(b.response_gamma),
                    "min_signal": float(b.min_signal),
                }
                for b in sorted(self.bindings, key=visual_binding_sort_key)
            ],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class VisualPropertyState:
    scale_multiplier: float = 1.0
    zoom_multiplier: float = 1.0
    opacity_multiplier: float = 1.0
    rotation_offset_deg: float = 0.0
    x_offset_normalized: float = 0.0
    y_offset_normalized: float = 0.0
    glow_amount: float = 0.0

    def validate(self) -> None:
        ranges = {
            "scale_multiplier": (0.75, 1.35),
            "zoom_multiplier": (1.0, 1.25),
            "opacity_multiplier": (0.0, 1.25),
            "rotation_offset_deg": (-12.0, 12.0),
            "x_offset_normalized": (-0.15, 0.15),
            "y_offset_normalized": (-0.15, 0.15),
            "glow_amount": (0.0, 1.0),
        }
        for name, (low, high) in ranges.items():
            value = float(getattr(self, name))
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be in {low}..{high}")

    @classmethod
    def neutral(cls) -> "VisualPropertyState":
        return cls()


@dataclass(frozen=True)
class EffectiveLayerVisual:
    x: float
    y: float
    width: float
    height: float
    rotation: float
    opacity: float
    pivot_x: float
    pivot_y: float
    zoom_multiplier: float
    glow_amount: float

    def validate(self) -> None:
        finite_names = ("x", "y", "width", "height", "rotation", "opacity", "pivot_x", "pivot_y", "zoom_multiplier", "glow_amount")
        for name in finite_names:
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"effective {name} must be finite")
        if not -2.0 <= self.x <= 2.0 or not -2.0 <= self.y <= 2.0:
            raise ValueError("effective position must be in -2..2")
        if not 0.02 <= self.width <= 3.0 or not 0.02 <= self.height <= 3.0:
            raise ValueError("effective size must be in 0.02..3")
        if not -180.0 <= self.rotation <= 180.0:
            raise ValueError("effective rotation must be in -180..180")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("effective opacity must be in 0..1")
        if not 0.0 <= self.pivot_x <= 1.0 or not 0.0 <= self.pivot_y <= 1.0:
            raise ValueError("effective pivot must be in 0..1")
        if not 1.0 <= self.zoom_multiplier <= 1.25:
            raise ValueError("effective zoom must be in 1..1.25")
        if not 0.0 <= self.glow_amount <= 1.0:
            raise ValueError("effective glow must be in 0..1")


def visual_binding_sort_key(binding: VisualBinding) -> tuple[str, str, float, float, float]:
    return (
        binding.property.value,
        binding.channel.value,
        float(binding.amount),
        float(binding.response_gamma),
        float(binding.min_signal),
    )
