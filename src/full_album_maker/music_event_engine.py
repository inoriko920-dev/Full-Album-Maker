from __future__ import annotations

from bisect import bisect_left, insort
import math

import numpy as np

from .audio_analysis_contract import AnalysisQuality, AudioAnalysisResult
from .music_event_contract import (
    DERIVED_EVENT_ENGINE_VERSION,
    DerivedEventSettings,
    MusicEvent,
    MusicEventTimeline,
    MusicEventType,
    clamp_unit,
    milliseconds_to_ticks,
    music_event_sort_key,
)


def _curve_arrays(result: AudioAnalysisResult) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    onset = np.asarray(result.curve("onset").values, dtype=np.float32)
    energy = np.asarray(result.curve("energy").values, dtype=np.float32)
    bass = np.asarray(result.curve("bass").values, dtype=np.float32)
    if not (len(onset) == len(energy) == len(bass)):
        raise ValueError("onset, energy, and bass curves must have identical lengths")
    if len(onset) == 0:
        raise ValueError("analysis curves must not be empty")
    for name, values in (("onset", onset), ("energy", energy), ("bass", bass)):
        if not np.isfinite(values).all():
            raise ValueError(f"{name} curve contains non-finite values")
        if ((values < 0.0) | (values > 1.0)).any():
            raise ValueError(f"{name} curve contains values outside 0..1")
    return onset, energy, bass


def _frame_for_tick(result: AudioAnalysisResult, tick: int, frame_count: int) -> int:
    curve = result.curve("energy")
    if curve.tick_step <= 0:
        raise ValueError("curve tick_step must be positive")
    relative = max(0, int(tick) - int(curve.start_tick))
    index = int(round(relative / curve.tick_step))
    return max(0, min(frame_count - 1, index))


def _nms_candidates(
    candidates: list[tuple[int, float, float, str]],
    min_separation_tick: int,
    event_type: MusicEventType,
) -> list[MusicEvent]:
    if not candidates:
        return []
    selected_ticks: list[int] = []
    selected: list[tuple[int, float, float, str]] = []
    for tick, strength, confidence, source in sorted(candidates, key=lambda x: (-x[1], x[0], x[3])):
        pos = bisect_left(selected_ticks, tick)
        left_ok = pos == 0 or tick - selected_ticks[pos - 1] >= min_separation_tick
        right_ok = pos == len(selected_ticks) or selected_ticks[pos] - tick >= min_separation_tick
        if left_ok and right_ok:
            insort(selected_ticks, tick)
            selected.append((tick, strength, confidence, source))
    return [
        MusicEvent(tick, event_type, clamp_unit(strength), clamp_unit(confidence), source)
        for tick, strength, confidence, source in sorted(selected, key=lambda x: (x[0], x[3]))
    ]


def derive_strong_beats(
    result: AudioAnalysisResult,
    settings: DerivedEventSettings,
) -> tuple[MusicEvent, ...]:
    if result.tempo.quality not in {AnalysisQuality.MEDIUM, AnalysisQuality.HIGH}:
        return ()
    if not result.beats:
        return ()

    onset, energy, bass = _curve_arrays(result)
    scores: list[tuple[object, float]] = []
    for beat in result.beats:
        frame = _frame_for_tick(result, beat.tick, len(onset))
        score = clamp_unit(
            settings.strong_beat_onset_weight * float(onset[frame])
            + settings.strong_beat_energy_weight * float(energy[frame])
            + settings.strong_beat_bass_weight * float(bass[frame])
        )
        scores.append((beat, score))

    adaptive = (
        float(np.quantile([score for _, score in scores], settings.strong_beat_quantile))
        if len(scores) >= 4
        else 0.0
    )
    threshold = max(float(settings.strong_beat_min_score), adaptive)
    events: list[MusicEvent] = []
    for beat, score in scores:
        if score + 1e-12 < threshold:
            continue
        confidence = min(float(result.tempo.confidence), 0.55 + 0.45 * score)
        events.append(
            MusicEvent(
                tick=beat.tick,
                event_type=MusicEventType.STRONG_BEAT,
                strength=score,
                confidence=clamp_unit(confidence),
                source="derived.strong_beat",
            )
        )
    return tuple(events)


def derive_bass_hits(
    result: AudioAnalysisResult,
    settings: DerivedEventSettings,
) -> tuple[MusicEvent, ...]:
    if result.tempo.quality == AnalysisQuality.SILENT:
        return ()
    onset, _energy, bass = _curve_arrays(result)
    curve = result.curve("bass")
    radius = max(1, int(settings.bass_peak_radius_frames))
    candidates: list[tuple[int, float, float, str]] = []

    for index, bass_value in enumerate(bass):
        bass_value = float(bass_value)
        onset_value = float(onset[index])
        if bass_value < settings.bass_peak_min or onset_value < settings.bass_onset_min:
            continue
        left = max(0, index - radius)
        right = min(len(bass), index + radius + 1)
        window = bass[left:right]
        local_max_offset = int(np.argmax(window))
        local_max_index = left + local_max_offset
        if local_max_index != index:
            continue
        score = clamp_unit(0.72 * bass_value + 0.28 * onset_value)
        confidence = clamp_unit(0.60 * bass_value + 0.40 * onset_value)
        tick = int(curve.start_tick + index * curve.tick_step)
        if tick >= result.duration_tick:
            continue
        candidates.append((tick, score, confidence, "derived.bass_hit"))

    separation = milliseconds_to_ticks(settings.bass_min_separation_ms)
    return tuple(_nms_candidates(candidates, separation, MusicEventType.BASS_HIT))


def derive_energy_events(
    result: AudioAnalysisResult,
    settings: DerivedEventSettings,
) -> tuple[MusicEvent, ...]:
    if result.tempo.quality == AnalysisQuality.SILENT:
        return ()
    energy = np.asarray(result.curve("energy").values, dtype=np.float64)
    curve = result.curve("energy")
    if energy.size == 0:
        return ()
    if not np.isfinite(energy).all() or ((energy < 0.0) | (energy > 1.0)).any():
        raise ValueError("energy curve contains invalid values")

    window_tick = milliseconds_to_ticks(settings.energy_window_ms)
    window = max(1, int(round(window_tick / curve.tick_step)))
    if len(energy) < 2 * window + 1:
        return ()

    prefix = np.concatenate(([0.0], np.cumsum(energy, dtype=np.float64)))
    rise: list[tuple[int, float, float, str]] = []
    fall: list[tuple[int, float, float, str]] = []

    for index in range(window, len(energy) - window + 1):
        past = float((prefix[index] - prefix[index - window]) / window)
        future = float((prefix[index + window] - prefix[index]) / window)
        delta = future - past
        tick = int(curve.start_tick + index * curve.tick_step)
        if tick >= result.duration_tick:
            continue
        if delta >= settings.energy_delta_min and future >= settings.energy_level_min:
            strength = clamp_unit(abs(delta) / 0.45)
            confidence = clamp_unit(0.55 + 0.45 * strength)
            rise.append((tick, strength, confidence, "derived.energy_rise"))
        elif delta <= -settings.energy_delta_min and past >= settings.energy_level_min:
            strength = clamp_unit(abs(delta) / 0.45)
            confidence = clamp_unit(0.55 + 0.45 * strength)
            fall.append((tick, strength, confidence, "derived.energy_fall"))

    separation = milliseconds_to_ticks(settings.energy_event_separation_ms)
    events = [
        *_nms_candidates(rise, separation, MusicEventType.ENERGY_RISE),
        *_nms_candidates(fall, separation, MusicEventType.ENERGY_FALL),
    ]
    return tuple(sorted(events, key=music_event_sort_key))


def build_music_event_timeline(
    result: AudioAnalysisResult,
    settings: DerivedEventSettings | None = None,
) -> MusicEventTimeline:
    result.validate()
    cfg = settings or DerivedEventSettings()
    cfg.validate()
    _curve_arrays(result)

    events: list[MusicEvent] = []
    if result.tempo.quality != AnalysisQuality.SILENT:
        events.extend(
            MusicEvent(
                beat.tick,
                MusicEventType.BEAT,
                clamp_unit(beat.strength),
                clamp_unit(beat.confidence),
                "analysis.beat",
            )
            for beat in result.beats
        )
        events.extend(
            MusicEvent(
                onset.tick,
                MusicEventType.ONSET,
                clamp_unit(onset.strength),
                clamp_unit(onset.confidence),
                "analysis.onset",
            )
            for onset in result.onsets
        )
        events.extend(derive_strong_beats(result, cfg))
        events.extend(derive_bass_hits(result, cfg))
        events.extend(derive_energy_events(result, cfg))

    timeline = MusicEventTimeline(
        asset_id=result.asset_id,
        content_sha256=result.content_sha256,
        analysis_settings_signature=result.settings_signature,
        derived_settings_signature=cfg.signature(),
        analyzer_version=result.analyzer_version,
        engine_version=DERIVED_EVENT_ENGINE_VERSION,
        duration_tick=result.duration_tick,
        quality=result.tempo.quality,
        events=tuple(sorted(events, key=music_event_sort_key)),
    )
    timeline.validate()
    return timeline
