from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math

from .audio_analysis_contract import AnalysisQuality
from .editor_models import TIMEBASE

MUSIC_EVENT_SCHEMA = "full-album-maker-music-event-timeline"
MUSIC_EVENT_SCHEMA_VERSION = 1
DERIVED_EVENT_ENGINE_VERSION = "music-events-v1"


class MusicEventType(str, Enum):
    BEAT = "beat"
    ONSET = "onset"
    STRONG_BEAT = "strong_beat"
    BASS_HIT = "bass_hit"
    ENERGY_RISE = "energy_rise"
    ENERGY_FALL = "energy_fall"


_EVENT_PRIORITY = {
    MusicEventType.STRONG_BEAT: 0,
    MusicEventType.BASS_HIT: 1,
    MusicEventType.BEAT: 2,
    MusicEventType.ONSET: 3,
    MusicEventType.ENERGY_RISE: 4,
    MusicEventType.ENERGY_FALL: 5,
}


@dataclass(frozen=True)
class DerivedEventSettings:
    strong_beat_quantile: float = 0.75
    strong_beat_min_score: float = 0.60
    strong_beat_onset_weight: float = 0.45
    strong_beat_energy_weight: float = 0.25
    strong_beat_bass_weight: float = 0.30
    bass_peak_min: float = 0.58
    bass_onset_min: float = 0.20
    bass_peak_radius_frames: int = 2
    bass_min_separation_ms: int = 120
    energy_window_ms: int = 360
    energy_delta_min: float = 0.18
    energy_level_min: float = 0.45
    energy_event_separation_ms: int = 800

    def validate(self) -> None:
        unit_names = (
            "strong_beat_quantile",
            "strong_beat_min_score",
            "strong_beat_onset_weight",
            "strong_beat_energy_weight",
            "strong_beat_bass_weight",
            "bass_peak_min",
            "bass_onset_min",
            "energy_delta_min",
            "energy_level_min",
        )
        for name in unit_names:
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in 0..1")
        weight_sum = (
            self.strong_beat_onset_weight
            + self.strong_beat_energy_weight
            + self.strong_beat_bass_weight
        )
        if not math.isclose(weight_sum, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("strong beat weights must sum to 1")
        if int(self.bass_peak_radius_frames) < 1:
            raise ValueError("bass_peak_radius_frames must be >= 1")
        if int(self.bass_min_separation_ms) < 0:
            raise ValueError("bass_min_separation_ms must be >= 0")
        if int(self.energy_window_ms) <= 0:
            raise ValueError("energy_window_ms must be > 0")
        if int(self.energy_event_separation_ms) < 0:
            raise ValueError("energy_event_separation_ms must be >= 0")

    def signature(self) -> str:
        self.validate()
        payload = {
            "engine": DERIVED_EVENT_ENGINE_VERSION,
            "strong_beat_quantile": self.strong_beat_quantile,
            "strong_beat_min_score": self.strong_beat_min_score,
            "strong_beat_onset_weight": self.strong_beat_onset_weight,
            "strong_beat_energy_weight": self.strong_beat_energy_weight,
            "strong_beat_bass_weight": self.strong_beat_bass_weight,
            "bass_peak_min": self.bass_peak_min,
            "bass_onset_min": self.bass_onset_min,
            "bass_peak_radius_frames": self.bass_peak_radius_frames,
            "bass_min_separation_ms": self.bass_min_separation_ms,
            "energy_window_ms": self.energy_window_ms,
            "energy_delta_min": self.energy_delta_min,
            "energy_level_min": self.energy_level_min,
            "energy_event_separation_ms": self.energy_event_separation_ms,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class MusicEvent:
    tick: int
    event_type: MusicEventType
    strength: float
    confidence: float
    source: str

    def validate(self) -> None:
        if not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError("event.tick must be a non-negative integer")
        if not isinstance(self.event_type, MusicEventType):
            raise ValueError("event.event_type is invalid")
        for name, value in (("strength", self.strength), ("confidence", self.confidence)):
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"event.{name} must be in 0..1")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("event.source is required")


@dataclass(frozen=True)
class MusicEventTimeline:
    asset_id: str
    content_sha256: str
    analysis_settings_signature: str
    derived_settings_signature: str
    analyzer_version: str
    engine_version: str
    duration_tick: int
    quality: AnalysisQuality
    events: tuple[MusicEvent, ...]

    def validate(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")
        for name, value in (
            ("content_sha256", self.content_sha256),
            ("analysis_settings_signature", self.analysis_settings_signature),
            ("derived_settings_signature", self.derived_settings_signature),
        ):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise ValueError(f"{name} must be a SHA-256 hex digest")
        if not self.analyzer_version.strip() or not self.engine_version.strip():
            raise ValueError("analyzer/engine version is required")
        if self.duration_tick < 0:
            raise ValueError("duration_tick must be non-negative")
        if not isinstance(self.quality, AnalysisQuality):
            raise ValueError("quality is invalid")
        previous = None
        for event in self.events:
            event.validate()
            if self.duration_tick == 0 or event.tick >= self.duration_tick:
                raise ValueError("event tick must be inside source duration")
            key = music_event_sort_key(event)
            if previous is not None and key < previous:
                raise ValueError("events must be deterministically sorted")
            previous = key


@dataclass(frozen=True)
class ProjectedMusicEvent:
    project_tick: int
    source_tick: int
    song_id: str
    asset_id: str
    event_type: MusicEventType
    strength: float
    confidence: float
    source: str

    def validate(self) -> None:
        if not isinstance(self.project_tick, int) or self.project_tick < 0:
            raise ValueError("project_tick must be non-negative")
        if not isinstance(self.source_tick, int) or self.source_tick < 0:
            raise ValueError("source_tick must be non-negative")
        if not self.song_id.strip() or not self.asset_id.strip():
            raise ValueError("song_id and asset_id are required")
        MusicEvent(
            self.source_tick,
            self.event_type,
            self.strength,
            self.confidence,
            self.source,
        ).validate()


def music_event_sort_key(event: MusicEvent) -> tuple[int, int, str, str]:
    return (
        event.tick,
        _EVENT_PRIORITY[event.event_type],
        event.event_type.value,
        event.source,
    )


def projected_event_sort_key(event: ProjectedMusicEvent) -> tuple[int, int, str, int, str]:
    return (
        event.project_tick,
        _EVENT_PRIORITY[event.event_type],
        event.song_id,
        event.source_tick,
        event.source,
    )


def milliseconds_to_ticks(milliseconds: int | float) -> int:
    value = float(milliseconds)
    if not math.isfinite(value) or value < 0:
        raise ValueError("milliseconds must be finite and non-negative")
    return int(round(value * TIMEBASE / 1000.0))


def clamp_unit(value: float) -> float:
    if not math.isfinite(float(value)):
        raise ValueError("value must be finite")
    return float(max(0.0, min(1.0, float(value))))
