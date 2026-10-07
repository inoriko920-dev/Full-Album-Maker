from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from full_album_maker.audio_analysis_contract import (
    ANALYZER_VERSION,
    AnalysisCurve,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisQuality,
    AudioAnalysisResult,
    HOP_LENGTH,
    SAMPLE_RATE,
    TICKS_PER_FRAME,
    TempoSummary,
)
from full_album_maker.audio_analysis_fingerprint import AnalyzerSettings
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.music_event_contract import (
    DERIVED_EVENT_ENGINE_VERSION,
    DerivedEventSettings,
    MusicEvent,
    MusicEventTimeline,
    MusicEventType,
    ProjectedMusicEvent,
    milliseconds_to_ticks,
    music_event_sort_key,
)
from full_album_maker.music_event_engine import (
    build_music_event_timeline,
    derive_bass_hits,
    derive_energy_events,
    derive_strong_beats,
)
from full_album_maker.music_event_projection import project_album_events, project_song_events
from full_album_maker.timeline_resolver import TimelineResolver


def _unit_curve(name: str, values: list[float] | tuple[float, ...]) -> AnalysisCurve:
    return AnalysisCurve(name=name, values=tuple(float(x) for x in values))


def _analysis(
    *,
    quality: AnalysisQuality = AnalysisQuality.HIGH,
    curves: dict[str, list[float]] | None = None,
    beat_frames: tuple[int, ...] = (2, 5, 8, 11),
    onset_frames: tuple[int, ...] = (2, 5, 8, 11),
    tempo_confidence: float | None = None,
    asset_id: str | None = None,
) -> AudioAnalysisResult:
    size = max(16, max(beat_frames + onset_frames + (0,)) + 3)
    base = [0.1] * size
    data = {
        "energy": base.copy(),
        "bass": base.copy(),
        "mid": base.copy(),
        "high": base.copy(),
        "onset": base.copy(),
    }
    if curves:
        for name, values in curves.items():
            if len(values) != size:
                raise AssertionError(f"{name} must contain {size} frames")
            data[name] = list(values)
    confidence = tempo_confidence
    if confidence is None:
        confidence = {
            AnalysisQuality.HIGH: 0.90,
            AnalysisQuality.MEDIUM: 0.65,
            AnalysisQuality.LOW: 0.30,
            AnalysisQuality.SILENT: 0.0,
        }[quality]
    bpm = 120.0 if quality != AnalysisQuality.SILENT else 0.0
    beats = tuple(
        AnalysisEvent(frame * TICKS_PER_FRAME, AnalysisEventType.BEAT, 0.8, confidence)
        for frame in beat_frames
    )
    onsets = tuple(
        AnalysisEvent(frame * TICKS_PER_FRAME, AnalysisEventType.ONSET, data["onset"][frame], data["onset"][frame])
        for frame in onset_frames
        if data["onset"][frame] > 0
    )
    result = AudioAnalysisResult(
        asset_id=asset_id or str(uuid4()),
        content_sha256="a" * 64,
        settings_signature=AnalyzerSettings().signature(),
        analyzer_version=ANALYZER_VERSION,
        duration_tick=size * TICKS_PER_FRAME,
        sample_rate=SAMPLE_RATE,
        hop_length=HOP_LENGTH,
        tempo=TempoSummary(bpm, confidence, quality, 0.03 if quality in {AnalysisQuality.HIGH, AnalysisQuality.MEDIUM} else 0.5),
        quality_flags=(),
        beats=beats,
        onsets=onsets,
        curves=tuple(_unit_curve(name, data[name]) for name in ("energy", "bass", "mid", "high", "onset")),
        source_name="song.wav",
    )
    result.validate()
    return result


def _high_signal_result(*, quality=AnalysisQuality.HIGH) -> AudioAnalysisResult:
    size = 16
    energy = [0.15] * size
    bass = [0.10] * size
    onset = [0.10] * size
    # Four beat frames with increasing salience.
    for frame, values in {
        2: (0.35, 0.25, 0.30),
        5: (0.55, 0.50, 0.55),
        8: (0.85, 0.80, 0.95),
        11: (1.00, 0.90, 1.00),
    }.items():
        onset[frame], energy[frame], bass[frame] = values
    return _analysis(
        quality=quality,
        curves={"energy": energy, "bass": bass, "onset": onset},
    )


def _project_doc(*, mode="packed", source_in=0, source_out=None, start=None, asset_id=None):
    doc = ProjectDocument.new_empty("music events")
    asset = MediaAsset(
        asset_id=asset_id or str(uuid4()),
        kind="audio",
        locator="C:/music/song.wav",
        original_name="song.wav",
        source_duration_tick=12 * TIMEBASE,
    )
    doc.media.append(asset)
    doc.playlist.mode = mode
    song = SongInstance(
        asset_id=asset.asset_id,
        display_title="Song",
        source_in_tick=source_in,
        source_out_tick=source_out,
        free_start_tick=start if mode == "free" else None,
    )
    doc.playlist.entries.append(song)
    doc.validate()
    return doc, asset, song


# 1
def test_music_event_accepts_valid_event():
    MusicEvent(0, MusicEventType.BEAT, 0.5, 0.7, "analysis.beat").validate()


# 2
def test_music_event_rejects_negative_tick():
    with pytest.raises(ValueError):
        MusicEvent(-1, MusicEventType.BEAT, 0.5, 0.7, "analysis.beat").validate()


# 3
@pytest.mark.parametrize("strength,confidence", [(-0.1, 0.2), (1.1, 0.2), (0.2, -0.1), (0.2, 1.1)])
def test_music_event_rejects_out_of_range_units(strength, confidence):
    with pytest.raises(ValueError):
        MusicEvent(0, MusicEventType.ONSET, strength, confidence, "analysis.onset").validate()


# 4
def test_settings_signature_is_stable_and_changes():
    a = DerivedEventSettings()
    assert a.signature() == DerivedEventSettings().signature()
    assert a.signature() != replace(a, bass_peak_min=0.6).signature()


# 5
def test_milliseconds_to_ticks_exact_enough():
    assert milliseconds_to_ticks(1000) == TIMEBASE
    assert milliseconds_to_ticks(120) == 28_800


# 6
def test_raw_passthrough_on_high_quality():
    result = _high_signal_result()
    timeline = build_music_event_timeline(result)
    kinds = [e.event_type for e in timeline.events]
    assert MusicEventType.BEAT in kinds
    assert MusicEventType.ONSET in kinds


# 7
def test_low_quality_fails_closed_raw_and_strong_beats():
    result = _high_signal_result(quality=AnalysisQuality.LOW)
    timeline = build_music_event_timeline(result)
    assert not any(e.event_type == MusicEventType.BEAT for e in timeline.events)
    assert not any(e.event_type == MusicEventType.STRONG_BEAT for e in timeline.events)


# 8
def test_silent_produces_no_music_events():
    result = _analysis(quality=AnalysisQuality.SILENT, beat_frames=(), onset_frames=())
    assert build_music_event_timeline(result).events == ()


# 9
def test_strong_beat_uses_adaptive_threshold():
    result = _high_signal_result()
    strong = derive_strong_beats(result, DerivedEventSettings())
    assert strong
    assert all(e.event_type == MusicEventType.STRONG_BEAT for e in strong)
    assert strong[-1].tick == 11 * TICKS_PER_FRAME
    assert len(strong) < len(result.beats)


# 10
def test_strong_beat_hard_floor_blocks_weak_beats():
    result = _analysis()
    assert derive_strong_beats(result, DerivedEventSettings(strong_beat_min_score=0.9)) == ()


# 11
def test_strong_beat_confidence_never_exceeds_tempo():
    result = _high_signal_result()
    strong = derive_strong_beats(result, DerivedEventSettings())
    assert strong
    assert max(e.confidence for e in strong) <= result.tempo.confidence


# 12
def test_bass_local_peak_yields_hit():
    size = 16
    bass = [0.1] * size
    onset = [0.1] * size
    bass[7] = 0.9
    onset[7] = 0.8
    result = _analysis(curves={"bass": bass, "onset": onset})
    hits = derive_bass_hits(result, DerivedEventSettings())
    assert [e.tick for e in hits] == [7 * TICKS_PER_FRAME]


# 13
def test_bass_plateau_does_not_spam():
    size = 16
    bass = [0.1] * size
    onset = [0.1] * size
    for i in (6, 7, 8):
        bass[i] = 0.9
        onset[i] = 0.8
    result = _analysis(curves={"bass": bass, "onset": onset})
    hits = derive_bass_hits(result, DerivedEventSettings())
    assert len(hits) == 1


# 14
def test_bass_without_onset_is_rejected():
    size = 16
    bass = [0.1] * size
    onset = [0.05] * size
    bass[7] = 1.0
    result = _analysis(curves={"bass": bass, "onset": onset}, onset_frames=())
    assert derive_bass_hits(result, DerivedEventSettings()) == ()


# 15
def test_bass_nms_keeps_stronger_candidate():
    size = 16
    bass = [0.1] * size
    onset = [0.1] * size
    bass[5], onset[5] = 0.75, 0.7
    bass[7], onset[7] = 1.0, 1.0
    result = _analysis(curves={"bass": bass, "onset": onset})
    settings = DerivedEventSettings(bass_min_separation_ms=100)
    hits = derive_bass_hits(result, settings)
    assert len(hits) == 1
    assert hits[0].tick == 7 * TICKS_PER_FRAME


# 16
def test_low_quality_can_keep_valid_bass_hit():
    size = 16
    bass = [0.1] * size
    onset = [0.1] * size
    bass[7], onset[7] = 0.95, 0.9
    result = _analysis(quality=AnalysisQuality.LOW, curves={"bass": bass, "onset": onset})
    hits = derive_bass_hits(result, DerivedEventSettings())
    assert len(hits) == 1


def _energy_result(values):
    size = 16
    assert len(values) == size
    return _analysis(curves={"energy": list(values)}, beat_frames=(), onset_frames=())


# 17
def test_energy_rise_detected():
    result = _energy_result([0.1] * 6 + [0.2, 0.4, 0.65, 0.85, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9])
    settings = DerivedEventSettings(energy_window_ms=64, energy_event_separation_ms=100)
    events = derive_energy_events(result, settings)
    assert any(e.event_type == MusicEventType.ENERGY_RISE for e in events)


# 18
def test_energy_fall_detected():
    result = _energy_result([0.9] * 7 + [0.8, 0.6, 0.35, 0.15, 0.1, 0.1, 0.1, 0.1, 0.1])
    settings = DerivedEventSettings(energy_window_ms=64, energy_event_separation_ms=100)
    events = derive_energy_events(result, settings)
    assert any(e.event_type == MusicEventType.ENERGY_FALL for e in events)


# 19
def test_flat_energy_has_no_rise_or_fall():
    result = _energy_result([0.5] * 16)
    assert derive_energy_events(result, DerivedEventSettings(energy_window_ms=64)) == ()


# 20
def test_energy_debounce_limits_cluster():
    result = _energy_result([0.1] * 5 + [0.2, 0.35, 0.55, 0.75, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    settings = DerivedEventSettings(energy_window_ms=64, energy_event_separation_ms=500)
    rises = [e for e in derive_energy_events(result, settings) if e.event_type == MusicEventType.ENERGY_RISE]
    assert len(rises) <= 1


# 21
def test_build_is_deterministic():
    result = _high_signal_result()
    settings = DerivedEventSettings()
    assert build_music_event_timeline(result, settings) == build_music_event_timeline(result, settings)


# 22
def test_same_tick_priority_is_stable():
    result = _high_signal_result()
    timeline = build_music_event_timeline(result)
    same = [e for e in timeline.events if e.tick == 11 * TICKS_PER_FRAME]
    assert same == sorted(same, key=music_event_sort_key)


# 23
def test_engine_does_not_mutate_analysis_result():
    result = _high_signal_result()
    before = result
    build_music_event_timeline(result)
    assert result == before


# 24
def test_timeline_records_versions_and_signatures():
    result = _high_signal_result()
    settings = DerivedEventSettings()
    timeline = build_music_event_timeline(result, settings)
    assert timeline.engine_version == DERIVED_EVENT_ENGINE_VERSION
    assert timeline.derived_settings_signature == settings.signature()
    timeline.validate()


def _timeline_for_asset(asset_id: str, event_ticks: tuple[int, ...]) -> MusicEventTimeline:
    events = tuple(
        MusicEvent(t, MusicEventType.ONSET, 0.7, 0.8, "analysis.onset")
        for t in event_ticks
    )
    timeline = MusicEventTimeline(
        asset_id=asset_id,
        content_sha256="b" * 64,
        analysis_settings_signature="c" * 64,
        derived_settings_signature="d" * 64,
        analyzer_version=ANALYZER_VERSION,
        engine_version=DERIVED_EVENT_ENGINE_VERSION,
        duration_tick=12 * TIMEBASE,
        quality=AnalysisQuality.HIGH,
        events=events,
    )
    timeline.validate()
    return timeline


# 25
def test_packed_projection_exact_tick():
    doc, asset, song = _project_doc()
    timeline = _timeline_for_asset(asset.asset_id, (2 * TIMEBASE,))
    resolved = TimelineResolver().resolve(doc)
    values = project_song_events(doc, resolved, song.song_id, timeline)
    assert values[0].project_tick == 2 * TIMEBASE


# 26
def test_projection_respects_source_in_trim():
    doc, asset, song = _project_doc(source_in=2 * TIMEBASE, source_out=8 * TIMEBASE)
    timeline = _timeline_for_asset(asset.asset_id, (1 * TIMEBASE, 3 * TIMEBASE))
    values = project_song_events(doc, TimelineResolver().resolve(doc), song.song_id, timeline)
    assert len(values) == 1
    assert values[0].source_tick == 3 * TIMEBASE
    assert values[0].project_tick == 1 * TIMEBASE


# 27
def test_projection_source_out_is_exclusive():
    doc, asset, song = _project_doc(source_out=5 * TIMEBASE)
    timeline = _timeline_for_asset(asset.asset_id, (4 * TIMEBASE, 5 * TIMEBASE))
    values = project_song_events(doc, TimelineResolver().resolve(doc), song.song_id, timeline)
    assert [x.source_tick for x in values] == [4 * TIMEBASE]


# 28
def test_free_timeline_projection_uses_resolved_start():
    doc, asset, song = _project_doc(mode="free", start=3 * TIMEBASE)
    timeline = _timeline_for_asset(asset.asset_id, (2 * TIMEBASE,))
    values = project_song_events(doc, TimelineResolver().resolve(doc), song.song_id, timeline)
    assert values[0].project_tick == 5 * TIMEBASE


# 29
def test_same_asset_reused_projects_twice():
    doc = ProjectDocument.new_empty("reuse")
    asset = MediaAsset(kind="audio", locator="C:/music/song.wav", source_duration_tick=10 * TIMEBASE)
    doc.media.append(asset)
    first = SongInstance(asset_id=asset.asset_id, source_out_tick=10 * TIMEBASE)
    second = SongInstance(asset_id=asset.asset_id, source_out_tick=10 * TIMEBASE)
    doc.playlist.entries.extend([first, second])
    doc.validate()
    timeline = _timeline_for_asset(asset.asset_id, (1 * TIMEBASE,))
    values = project_album_events(doc, {asset.asset_id: timeline})
    assert len(values) == 2
    assert [x.project_tick for x in values] == [1 * TIMEBASE, 11 * TIMEBASE]


# 30
def test_disabled_song_is_not_projected():
    doc, asset, song = _project_doc()
    song.enabled = False
    doc.validate()
    timeline = _timeline_for_asset(asset.asset_id, (TIMEBASE,))
    assert project_album_events(doc, {asset.asset_id: timeline}) == ()


# 31
def test_projection_rejects_wrong_asset_timeline():
    doc, _asset, song = _project_doc()
    wrong = _timeline_for_asset(str(uuid4()), (TIMEBASE,))
    with pytest.raises(ValueError):
        project_song_events(doc, TimelineResolver().resolve(doc), song.song_id, wrong)


# 32
def test_projected_event_validation():
    ProjectedMusicEvent(
        project_tick=TIMEBASE,
        source_tick=TIMEBASE,
        song_id=str(uuid4()),
        asset_id=str(uuid4()),
        event_type=MusicEventType.BASS_HIT,
        strength=0.8,
        confidence=0.8,
        source="derived.bass_hit",
    ).validate()
