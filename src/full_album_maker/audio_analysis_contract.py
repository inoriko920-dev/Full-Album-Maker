from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

from .editor_models import TIMEBASE

ANALYSIS_SCHEMA = "full-album-maker-audio-analysis"
ANALYSIS_SCHEMA_VERSION = 1
ANALYZER_VERSION = "analysis-v1"
SAMPLE_RATE = 24_000
HOP_LENGTH = 512
N_FFT = 2048
TICKS_PER_SAMPLE = TIMEBASE // SAMPLE_RATE
TICKS_PER_FRAME = HOP_LENGTH * TICKS_PER_SAMPLE

if TIMEBASE % SAMPLE_RATE:
    raise RuntimeError("Analysis sample rate must divide project TIMEBASE exactly.")


class AnalysisQuality(str, Enum):
    SILENT = "silent"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisEventType(str, Enum):
    BEAT = "beat"
    ONSET = "onset"


@dataclass(frozen=True)
class AnalysisEvent:
    tick: int
    event_type: AnalysisEventType
    strength: float
    confidence: float

    def validate(self) -> None:
        if not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError("event.tick must be a non-negative integer")
        for name, value in (("strength", self.strength), ("confidence", self.confidence)):
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"event.{name} must be in 0..1")


@dataclass(frozen=True)
class AnalysisCurve:
    name: str
    values: tuple[float, ...]
    start_tick: int = 0
    tick_step: int = TICKS_PER_FRAME

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("curve.name is required")
        if self.start_tick < 0 or self.tick_step <= 0:
            raise ValueError("curve timing is invalid")
        for value in self.values:
            if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"curve {self.name!r} contains value outside 0..1")


@dataclass(frozen=True)
class TempoSummary:
    bpm: float
    confidence: float
    quality: AnalysisQuality
    beat_interval_cv: float = 1.0

    def validate(self) -> None:
        if not math.isfinite(float(self.bpm)) or self.bpm < 0:
            raise ValueError("tempo bpm must be finite and non-negative")
        if not math.isfinite(float(self.confidence)) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("tempo confidence must be in 0..1")
        if not math.isfinite(float(self.beat_interval_cv)) or self.beat_interval_cv < 0:
            raise ValueError("beat_interval_cv must be finite and non-negative")


@dataclass(frozen=True)
class AudioAnalysisResult:
    asset_id: str
    content_sha256: str
    settings_signature: str
    analyzer_version: str
    duration_tick: int
    sample_rate: int
    hop_length: int
    tempo: TempoSummary
    quality_flags: tuple[str, ...]
    beats: tuple[AnalysisEvent, ...]
    onsets: tuple[AnalysisEvent, ...]
    curves: tuple[AnalysisCurve, ...]
    source_name: str = ""

    def validate(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")
        if len(self.content_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.content_sha256.lower()):
            raise ValueError("content_sha256 must be a 64-character hex digest")
        if len(self.settings_signature) != 64:
            raise ValueError("settings_signature must be a SHA-256 digest")
        if not self.analyzer_version.strip():
            raise ValueError("analyzer_version is required")
        if self.duration_tick < 0:
            raise ValueError("duration_tick must be non-negative")
        if self.sample_rate != SAMPLE_RATE or self.hop_length != HOP_LENGTH:
            raise ValueError("analysis timing profile does not match V1 contract")
        self.tempo.validate()
        for values, expected_type in ((self.beats, AnalysisEventType.BEAT), (self.onsets, AnalysisEventType.ONSET)):
            previous_tick = -1
            for event in values:
                event.validate()
                if event.event_type != expected_type:
                    raise ValueError(f"unexpected event type in {expected_type.value} collection")
                if event.tick < previous_tick:
                    raise ValueError(f"{expected_type.value} events must be deterministically sorted")
                previous_tick = event.tick
        curve_names: set[str] = set()
        for curve in self.curves:
            curve.validate()
            if curve.name in curve_names:
                raise ValueError(f"duplicate curve: {curve.name}")
            curve_names.add(curve.name)
        required = {"energy", "bass", "mid", "high", "onset"}
        if not required.issubset(curve_names):
            raise ValueError(f"missing required curves: {sorted(required - curve_names)}")

    def curve(self, name: str) -> AnalysisCurve:
        for curve in self.curves:
            if curve.name == name:
                return curve
        raise KeyError(name)


@dataclass(frozen=True)
class AnalysisProgress:
    state: str
    fraction: float
    message: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.fraction)) or not 0.0 <= self.fraction <= 1.0:
            raise ValueError("progress fraction must be in 0..1")


@dataclass(frozen=True)
class AnalysisTicket:
    token: int
    asset_id: str


@dataclass(frozen=True)
class AnalysisError:
    code: str
    message: str
    retryable: bool = False


def event_tuple(values: Iterable[AnalysisEvent]) -> tuple[AnalysisEvent, ...]:
    return tuple(sorted(values, key=lambda event: (event.tick, event.event_type.value)))
