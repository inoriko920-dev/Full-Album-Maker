from __future__ import annotations

from dataclasses import dataclass
import math

from .audio_analysis_contract import AnalysisQuality
from .beat_animation_assignment import document_has_beat_animation
from .editor_models import ProjectDocument, TIMEBASE
from .timeline_resolver import ResolvedTimeline, TimelineResolver

_ALLOWED_BPR=(1.0,2.0,4.0,8.0)


@dataclass(frozen=True)
class TempoSegment:
    song_id: str
    asset_id: str
    start_tick: int
    end_tick: int
    bpm: float
    confidence: float
    quality: AnalysisQuality

    def validate(self) -> None:
        if not self.song_id or not self.asset_id or self.start_tick < 0 or self.end_tick <= self.start_tick:
            raise ValueError("tempo segment identity/timing invalid")
        if not math.isfinite(self.bpm) or self.bpm < 0:
            raise ValueError("tempo segment bpm invalid")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("tempo segment confidence invalid")


def normalize_beats_per_rotation(value: float) -> float:
    value=float(value)
    if value not in _ALLOWED_BPR:
        raise ValueError("beats_per_rotation must be one of 1, 2, 4, 8")
    return value


def vinyl_bpm_sync_enabled(document: ProjectDocument) -> bool:
    tracks={t.track_id:t for t in document.tracks}
    for layer in document.layers:
        track=tracks.get(layer.track_id)
        if layer.enabled and track is not None and track.enabled and layer.type=="vinyl" and bool(layer.properties.get("bpm_sync",False)):
            return True
    return False


def document_needs_beat_runtime(document: ProjectDocument) -> bool:
    return document_has_beat_animation(document) or vinyl_bpm_sync_enabled(document)


def build_tempo_segments(
    document: ProjectDocument,
    analysis_results: dict[str, object],
    *,
    resolved: ResolvedTimeline | None=None,
) -> tuple[TempoSegment, ...]:
    timeline=resolved or TimelineResolver().resolve(document)
    songs=document.song_map()
    values=[]
    for item in timeline.songs:
        result=analysis_results.get(item.asset_id)
        if result is None:
            continue
        tempo=result.tempo
        seg=TempoSegment(item.song_id,item.asset_id,item.start_tick,item.end_tick,float(tempo.bpm),float(tempo.confidence),tempo.quality)
        seg.validate()
        values.append(seg)
    return tuple(sorted(values,key=lambda x:(x.start_tick,x.end_tick,x.song_id)))


def _valid(segment: TempoSegment, min_confidence: float) -> bool:
    return (
        segment.bpm > 0.0
        and segment.quality in {AnalysisQuality.MEDIUM,AnalysisQuality.HIGH}
        and segment.confidence >= float(min_confidence)
    )


def tempo_at_tick(segments: tuple[TempoSegment,...], tick: int) -> TempoSegment | None:
    active=[s for s in segments if s.start_tick <= int(tick) < s.end_tick]
    if not active:
        return None
    return max(active,key=lambda s:(s.start_tick,s.end_tick,s.song_id))


def synced_spin_seconds(bpm: float, beats_per_rotation: float) -> float:
    bpr=normalize_beats_per_rotation(beats_per_rotation)
    bpm=float(bpm)
    if not math.isfinite(bpm) or bpm <= 0:
        raise ValueError("BPM must be > 0")
    return 60.0*bpr/bpm


def vinyl_spin_seconds_at(
    segments: tuple[TempoSegment,...],
    tick: int,
    *,
    fallback_spin_seconds: float,
    beats_per_rotation: float=4.0,
    min_confidence: float=.55,
) -> float:
    fallback=float(fallback_spin_seconds)
    segment=tempo_at_tick(segments,tick)
    if segment is None or not _valid(segment,min_confidence):
        return fallback
    return synced_spin_seconds(segment.bpm,beats_per_rotation)


def vinyl_phase_cycles_at(
    segments: tuple[TempoSegment,...],
    tick: int,
    *,
    fallback_spin_seconds: float,
    beats_per_rotation: float=4.0,
    min_confidence: float=.55,
) -> float:
    tick=max(0,int(tick))
    segment=tempo_at_tick(segments,tick)
    if segment is None or not _valid(segment,min_confidence):
        return (tick/TIMEBASE)/float(fallback_spin_seconds)
    spin=synced_spin_seconds(segment.bpm,beats_per_rotation)
    return ((tick-segment.start_tick)/TIMEBASE)/spin


def vinyl_phase_expression(
    segments: tuple[TempoSegment,...],
    *,
    fallback_spin_seconds: float,
    beats_per_rotation: float=4.0,
    min_confidence: float=.55,
) -> str:
    fallback=float(fallback_spin_seconds)
    expr=f"(T/{fallback:.9f})"
    bpr=normalize_beats_per_rotation(beats_per_rotation)
    for segment in sorted(segments,key=lambda s:(s.start_tick,s.end_tick,s.song_id)):
        if not _valid(segment,min_confidence):
            continue
        start=segment.start_tick/TIMEBASE
        end=segment.end_tick/TIMEBASE
        spin=synced_spin_seconds(segment.bpm,bpr)
        phase=f"((T-{start:.9f})/{spin:.9f})"
        expr=f"if(between(T,{start:.9f},{end:.9f}),{phase},{expr})"
    return expr
