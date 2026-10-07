from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from .music_event_contract import MusicEventType, ProjectedMusicEvent, milliseconds_to_ticks

ANIMATION_SIGNAL_ENGINE_VERSION = "animation-signals-v1"
ANIMATION_SIGNAL_EASING_VERSION = "easing-v1"


class AnimationSignalChannel(str, Enum):
    BEAT = "beat"
    STRONG_BEAT = "strong_beat"
    BASS = "bass"
    ONSET = "onset"
    ENERGY_UP = "energy_up"
    ENERGY_DOWN = "energy_down"


class SignalShape(str, Enum):
    IMPULSE_DECAY = "impulse_decay"
    ATTACK_HOLD_DECAY = "attack_hold_decay"


class SignalBlendMode(str, Enum):
    MAX = "max"
    SATURATING_ADD = "saturating_add"


@dataclass(frozen=True)
class SignalProfile:
    channel: AnimationSignalChannel
    event_type: MusicEventType
    shape: SignalShape
    attack_ms: int
    hold_ms: int
    decay_ms: int
    strength_gamma: float
    confidence_floor: float
    amplitude: float
    blend_mode: SignalBlendMode
    max_value: float = 1.0

    def validate(self) -> None:
        if not isinstance(self.channel, AnimationSignalChannel):
            raise ValueError("profile channel is invalid")
        if not isinstance(self.event_type, MusicEventType):
            raise ValueError("profile event_type is invalid")
        if not isinstance(self.shape, SignalShape):
            raise ValueError("profile shape is invalid")
        if not isinstance(self.blend_mode, SignalBlendMode):
            raise ValueError("profile blend_mode is invalid")
        for name in ("attack_ms", "hold_ms", "decay_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) != value or int(value) < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.shape == SignalShape.IMPULSE_DECAY and (self.attack_ms or self.hold_ms):
            raise ValueError("impulse_decay does not accept attack/hold")
        if self.shape == SignalShape.IMPULSE_DECAY and self.decay_ms <= 0:
            raise ValueError("impulse_decay requires positive decay")
        if self.shape == SignalShape.ATTACK_HOLD_DECAY and self.decay_ms <= 0:
            raise ValueError("attack_hold_decay requires positive decay")
        if not math.isfinite(float(self.strength_gamma)) or self.strength_gamma <= 0:
            raise ValueError("strength_gamma must be finite and > 0")
        if not math.isfinite(float(self.confidence_floor)) or not 0.0 <= self.confidence_floor <= 1.0:
            raise ValueError("confidence_floor must be in 0..1")
        for name in ("amplitude", "max_value"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 2.0:
                raise ValueError(f"{name} must be in 0..2")
        if self.max_value <= 0:
            raise ValueError("max_value must be > 0")

    @property
    def attack_tick(self) -> int:
        return milliseconds_to_ticks(self.attack_ms)

    @property
    def hold_tick(self) -> int:
        return milliseconds_to_ticks(self.hold_ms)

    @property
    def decay_tick(self) -> int:
        return milliseconds_to_ticks(self.decay_ms)


DEFAULT_SIGNAL_PROFILES: tuple[SignalProfile, ...] = (
    SignalProfile(AnimationSignalChannel.BEAT, MusicEventType.BEAT, SignalShape.IMPULSE_DECAY, 0, 0, 180, 1.00, 0.45, 0.65, SignalBlendMode.MAX),
    SignalProfile(AnimationSignalChannel.STRONG_BEAT, MusicEventType.STRONG_BEAT, SignalShape.ATTACK_HOLD_DECAY, 12, 28, 320, 0.85, 0.50, 1.00, SignalBlendMode.MAX),
    SignalProfile(AnimationSignalChannel.BASS, MusicEventType.BASS_HIT, SignalShape.ATTACK_HOLD_DECAY, 8, 20, 260, 0.82, 0.35, 1.00, SignalBlendMode.MAX),
    SignalProfile(AnimationSignalChannel.ONSET, MusicEventType.ONSET, SignalShape.IMPULSE_DECAY, 0, 0, 120, 1.10, 0.20, 0.60, SignalBlendMode.SATURATING_ADD),
    SignalProfile(AnimationSignalChannel.ENERGY_UP, MusicEventType.ENERGY_RISE, SignalShape.ATTACK_HOLD_DECAY, 100, 180, 900, 1.00, 0.40, 0.80, SignalBlendMode.MAX),
    SignalProfile(AnimationSignalChannel.ENERGY_DOWN, MusicEventType.ENERGY_FALL, SignalShape.ATTACK_HOLD_DECAY, 80, 160, 760, 1.00, 0.40, 0.75, SignalBlendMode.MAX),
)


@dataclass(frozen=True)
class AnimationSignalSettings:
    profiles: tuple[SignalProfile, ...] = DEFAULT_SIGNAL_PROFILES
    sensitivity_by_channel: tuple[tuple[AnimationSignalChannel, float], ...] = ()
    intensity_by_channel: tuple[tuple[AnimationSignalChannel, float], ...] = ()
    easing_version: str = ANIMATION_SIGNAL_EASING_VERSION

    def validate(self) -> None:
        if not self.profiles:
            raise ValueError("at least one signal profile is required")
        channels: set[AnimationSignalChannel] = set()
        event_types: set[MusicEventType] = set()
        for profile in self.profiles:
            profile.validate()
            if profile.channel in channels:
                raise ValueError(f"duplicate channel profile: {profile.channel.value}")
            if profile.event_type in event_types:
                raise ValueError(f"duplicate event profile: {profile.event_type.value}")
            channels.add(profile.channel)
            event_types.add(profile.event_type)
        for label, values in (
            ("sensitivity", self.sensitivity_by_channel),
            ("intensity", self.intensity_by_channel),
        ):
            seen: set[AnimationSignalChannel] = set()
            for channel, value in values:
                if not isinstance(channel, AnimationSignalChannel):
                    raise ValueError(f"{label} channel is invalid")
                if channel in seen:
                    raise ValueError(f"duplicate {label} override: {channel.value}")
                seen.add(channel)
                if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 2.0:
                    raise ValueError(f"{label} must be in 0..2")
        if not isinstance(self.easing_version, str) or not self.easing_version.strip():
            raise ValueError("easing_version is required")

    def profile_for_event(self, event_type: MusicEventType) -> SignalProfile:
        for profile in self.profiles:
            if profile.event_type == event_type:
                return profile
        raise KeyError(event_type)

    def profile_for_channel(self, channel: AnimationSignalChannel) -> SignalProfile:
        for profile in self.profiles:
            if profile.channel == channel:
                return profile
        raise KeyError(channel)

    @staticmethod
    def _override(values: tuple[tuple[AnimationSignalChannel, float], ...], channel: AnimationSignalChannel) -> float:
        for key, value in values:
            if key == channel:
                return float(value)
        return 1.0

    def sensitivity(self, channel: AnimationSignalChannel) -> float:
        return self._override(self.sensitivity_by_channel, channel)

    def intensity(self, channel: AnimationSignalChannel) -> float:
        return self._override(self.intensity_by_channel, channel)

    def signature(self) -> str:
        self.validate()
        payload = {
            "engine_version": ANIMATION_SIGNAL_ENGINE_VERSION,
            "easing_version": self.easing_version,
            "profiles": [
                {
                    "channel": p.channel.value,
                    "event_type": p.event_type.value,
                    "shape": p.shape.value,
                    "attack_ms": p.attack_ms,
                    "hold_ms": p.hold_ms,
                    "decay_ms": p.decay_ms,
                    "strength_gamma": p.strength_gamma,
                    "confidence_floor": p.confidence_floor,
                    "amplitude": p.amplitude,
                    "blend_mode": p.blend_mode.value,
                    "max_value": p.max_value,
                }
                for p in self.profiles
            ],
            "sensitivity": sorted((c.value, float(v)) for c, v in self.sensitivity_by_channel),
            "intensity": sorted((c.value, float(v)) for c, v in self.intensity_by_channel),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SignalTrigger:
    channel: AnimationSignalChannel
    event_type: MusicEventType
    event_tick: int
    start_tick: int
    end_tick: int
    attack_tick: int
    hold_tick: int
    decay_tick: int
    amplitude: float
    shape: SignalShape
    blend_mode: SignalBlendMode
    song_id: str
    asset_id: str
    source_tick: int

    def validate(self) -> None:
        if not isinstance(self.channel, AnimationSignalChannel):
            raise ValueError("trigger channel is invalid")
        if not isinstance(self.event_type, MusicEventType):
            raise ValueError("trigger event type is invalid")
        if not isinstance(self.shape, SignalShape) or not isinstance(self.blend_mode, SignalBlendMode):
            raise ValueError("trigger shape/blend mode is invalid")
        for name in ("event_tick", "start_tick", "end_tick", "attack_tick", "hold_tick", "decay_tick", "source_tick"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"trigger {name} must be a non-negative integer")
        if self.start_tick > self.event_tick or self.end_tick < self.event_tick:
            raise ValueError("trigger time window is invalid")
        if not math.isfinite(float(self.amplitude)) or not 0.0 <= self.amplitude <= 1.0:
            raise ValueError("trigger amplitude must be in 0..1")
        if not self.song_id.strip() or not self.asset_id.strip():
            raise ValueError("trigger song_id/asset_id are required")


@dataclass(frozen=True)
class AnimationSignalProgram:
    duration_tick: int
    settings_signature: str
    channels: tuple[AnimationSignalChannel, ...]
    triggers: tuple[SignalTrigger, ...]
    intensity_by_channel: tuple[tuple[AnimationSignalChannel, float], ...]

    def validate(self) -> None:
        if not isinstance(self.duration_tick, int) or self.duration_tick < 0:
            raise ValueError("duration_tick must be a non-negative integer")
        if len(self.settings_signature) != 64 or any(c not in "0123456789abcdef" for c in self.settings_signature.lower()):
            raise ValueError("settings_signature must be a SHA-256 digest")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("program channels must be unique")
        for channel in self.channels:
            if not isinstance(channel, AnimationSignalChannel):
                raise ValueError("program channel is invalid")
        previous = None
        for trigger in self.triggers:
            trigger.validate()
            if trigger.channel not in self.channels:
                raise ValueError("trigger channel missing from program channels")
            if self.duration_tick == 0 or trigger.event_tick >= self.duration_tick:
                raise ValueError("trigger event tick must be inside program duration")
            key = signal_trigger_sort_key(trigger)
            if previous is not None and key < previous:
                raise ValueError("program triggers must be deterministically sorted")
            previous = key
        seen: set[AnimationSignalChannel] = set()
        for channel, value in self.intensity_by_channel:
            if channel in seen or channel not in self.channels:
                raise ValueError("invalid program intensity channel")
            seen.add(channel)
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 2.0:
                raise ValueError("program intensity must be in 0..2")

    def intensity(self, channel: AnimationSignalChannel) -> float:
        for key, value in self.intensity_by_channel:
            if key == channel:
                return float(value)
        return 1.0


@dataclass(frozen=True)
class AnimationSignalSample:
    tick: int
    values: tuple[tuple[AnimationSignalChannel, float], ...]

    def validate(self) -> None:
        if not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError("sample tick must be non-negative")
        seen: set[AnimationSignalChannel] = set()
        for channel, value in self.values:
            if channel in seen:
                raise ValueError("sample channel duplicated")
            seen.add(channel)
            if not isinstance(channel, AnimationSignalChannel):
                raise ValueError("sample channel invalid")
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("sample value must be in 0..1")

    def value(self, channel: AnimationSignalChannel) -> float:
        for key, value in self.values:
            if key == channel:
                return float(value)
        raise KeyError(channel)

    def as_dict(self) -> dict[str, float]:
        return {channel.value: float(value) for channel, value in self.values}


def signal_trigger_sort_key(trigger: SignalTrigger) -> tuple[str, int, int, str, str, int]:
    return (
        trigger.channel.value,
        trigger.start_tick,
        trigger.event_tick,
        trigger.event_type.value,
        trigger.song_id,
        trigger.source_tick,
    )


def projected_event_identity(event: ProjectedMusicEvent) -> tuple:
    return (
        event.project_tick,
        event.event_type.value,
        event.song_id,
        event.asset_id,
        event.source_tick,
        event.source,
        float(event.strength),
        float(event.confidence),
    )


def clamp_unit(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return max(0.0, min(1.0, value))
