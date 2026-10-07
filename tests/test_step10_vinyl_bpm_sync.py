from __future__ import annotations

from types import SimpleNamespace

import pytest

from full_album_maker.album_visuals import make_vinyl_layer, normalize_visual_properties
from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.audio_analysis_contract import AnalysisQuality, TempoSummary
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime, apply_beat_snapshot, build_beat_visual_runtime
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.vinyl_bpm_sync import (
    TempoSegment,
    build_tempo_segments,
    document_needs_beat_runtime,
    normalize_beats_per_rotation,
    synced_spin_seconds,
    tempo_at_tick,
    vinyl_phase_cycles_at,
    vinyl_phase_expression,
    vinyl_spin_seconds_at,
)


def _segment(bpm=120,confidence=.9,quality=AnalysisQuality.HIGH,start=0,end=4*TIMEBASE,song="s"):
    seg=TempoSegment(song,"a",start,end,float(bpm),float(confidence),quality)
    seg.validate()
    return seg


def _doc():
    doc=ProjectDocument.new_empty("STEP10 BPM")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=4*TIMEBASE)
    doc.media.append(audio)
    song=SongInstance(asset_id=audio.asset_id,source_out_tick=4*TIMEBASE,display_title="Song")
    doc.playlist.entries.append(song)
    vinyl=make_vinyl_layer(doc.tracks[0].track_id,1)
    vinyl.properties["bpm_sync"]=True
    vinyl.properties["beats_per_rotation"]=4.0
    doc.layers.append(vinyl)
    doc.validate()
    return doc,audio,song,vinyl


@pytest.mark.parametrize("value",[1,2,4,8])
def test_allowed_beats_per_rotation(value):
    assert normalize_beats_per_rotation(value)==float(value)


@pytest.mark.parametrize("value",[0,3,16])
def test_invalid_beats_per_rotation_rejected(value):
    with pytest.raises(ValueError):
        normalize_beats_per_rotation(value)


def test_synced_spin_seconds_known_values():
    assert synced_spin_seconds(120,4)==pytest.approx(2.0)
    assert synced_spin_seconds(90,4)==pytest.approx(8/3)


def test_low_confidence_falls_back():
    seg=(_segment(confidence=.4),)
    assert vinyl_spin_seconds_at(seg,TIMEBASE,fallback_spin_seconds=8,beats_per_rotation=4,min_confidence=.55)==8


def test_low_quality_falls_back_even_high_confidence():
    seg=(_segment(confidence=.99,quality=AnalysisQuality.LOW),)
    assert vinyl_spin_seconds_at(seg,TIMEBASE,fallback_spin_seconds=8)==8


def test_high_quality_uses_detected_tempo():
    seg=(_segment(bpm=120),)
    assert vinyl_spin_seconds_at(seg,TIMEBASE,fallback_spin_seconds=8)==pytest.approx(2.0)


def test_overlap_chooses_latest_start_segment():
    a=_segment(100,start=0,end=3*TIMEBASE,song="a")
    b=_segment(140,start=2*TIMEBASE,end=4*TIMEBASE,song="b")
    assert tempo_at_tick((a,b),int(2.5*TIMEBASE)).song_id=="b"


def test_phase_is_seek_deterministic_and_resets_at_song_start():
    a=_segment(120,start=TIMEBASE,end=5*TIMEBASE)
    x=vinyl_phase_cycles_at((a,),2*TIMEBASE,fallback_spin_seconds=8,beats_per_rotation=4)
    y=vinyl_phase_cycles_at((a,),2*TIMEBASE,fallback_spin_seconds=8,beats_per_rotation=4)
    assert x==y==pytest.approx(.5)
    assert vinyl_phase_cycles_at((a,),TIMEBASE,fallback_spin_seconds=8)==0


def test_phase_expression_contains_valid_segment_interval():
    expr=vinyl_phase_expression((_segment(120),),fallback_spin_seconds=8,beats_per_rotation=4)
    assert "between(T,0.000000000,4.000000000)" in expr
    assert "/2.000000000" in expr


def test_bpm_sync_alone_requests_runtime():
    doc,audio,song,vinyl=_doc()
    assert document_needs_beat_runtime(doc)


def test_without_bpm_sync_or_beat_assignment_runtime_not_needed():
    doc,audio,song,vinyl=_doc()
    vinyl.properties["bpm_sync"]=False
    assert not document_needs_beat_runtime(doc)


def test_build_tempo_segments_uses_resolved_song_timing():
    doc,audio,song,vinyl=_doc()
    fake=SimpleNamespace(tempo=TempoSummary(120,.9,AnalysisQuality.HIGH,.02))
    segments=build_tempo_segments(doc,{audio.asset_id:fake})
    assert len(segments)==1
    assert segments[0].song_id==song.song_id
    assert segments[0].asset_id==audio.asset_id
    assert segments[0].start_tick==0
    assert segments[0].end_tick==4*TIMEBASE


def test_runtime_can_exist_for_bpm_sync_without_visual_binding():
    doc,audio,song,vinyl=_doc()
    # A minimal analysis object with only the fields consumed by both
    # event builder and tempo builder would be insufficient, so instantiate
    # BeatVisualRuntime directly to verify the contract for zero beat layers.
    program=build_animation_signal_program((),4*TIMEBASE)
    runtime=BeatVisualRuntime(
        doc.content_signature(),4*TIMEBASE,AnimationSignalEngine(program),{},
        BeatRuntimeDiagnostics(1,0,0,0),
        tempo_segments=(_segment(120,end=4*TIMEBASE,song=song.song_id),),
    )
    assert runtime.diagnostics.beat_layers==0
    assert runtime.vinyl_spin_seconds_at(TIMEBASE,fallback_spin_seconds=8)==pytest.approx(2)


def test_invalid_latest_overlap_overrides_old_valid_tempo_with_fallback():
    old=_segment(120,confidence=.95,quality=AnalysisQuality.HIGH,start=0,end=4*TIMEBASE,song="old")
    new=_segment(140,confidence=.20,quality=AnalysisQuality.LOW,start=2*TIMEBASE,end=4*TIMEBASE,song="new")
    tick=int(2.5*TIMEBASE)
    assert vinyl_spin_seconds_at(
        (old,new),tick,fallback_spin_seconds=8,beats_per_rotation=4,min_confidence=.55
    )==8
    expr=vinyl_phase_expression(
        (old,new),fallback_spin_seconds=8,beats_per_rotation=4,min_confidence=.55
    )
    # The newer invalid segment must be represented explicitly with fallback,
    # not skipped in a way that lets the older 120 BPM segment leak through.
    assert "if(between(T,2.000000000,4.000000000),(T/8.000000000)" in expr


def test_accurate_snapshot_bakes_exact_bpm_phase(tmp_path):
    doc,audio,song,vinyl=_doc()
    program=build_animation_signal_program((),4*TIMEBASE)
    runtime=BeatVisualRuntime(
        doc.content_signature(),4*TIMEBASE,AnimationSignalEngine(program),{},
        BeatRuntimeDiagnostics(1,0,0,0),
        tempo_segments=(_segment(120,end=4*TIMEBASE,song=song.song_id),),
    )
    snap=apply_beat_snapshot(doc,runtime,TIMEBASE)
    sl=snap.layer_map()[vinyl.layer_id]
    assert sl.properties["_beat_snapshot_vinyl_phase_cycles"]==pytest.approx(.5)
    assert "_beat_snapshot_vinyl_phase_cycles" not in doc.layer_map()[vinyl.layer_id].properties
    compiled=Step08FFmpegCompiler("ffmpeg").compile_video(
        snap,tmp_path/"out.mp4",tmp_path,include_audio=False
    )
    args=list(compiled.args)
    graph=args[args.index("-filter_complex")+1]
    assert "cos(2*PI*(0.500000000))" in graph
