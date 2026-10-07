from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.advanced_motion_contract import AdvancedMotionPreset
from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_render_control import build_beat_render_control
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime, apply_beat_snapshot
from full_album_maker.editor_models import Layer, ProjectDocument, TIMEBASE, Transform
from full_album_maker.event_phase_modulator import EventPhaseEngine
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.spark_burst_engine import SPARK_LIFETIME_TICK, SparkBurstEngine


def ev(tick=TIMEBASE):
    return ProjectedMusicEvent(
        project_tick=tick,source_tick=tick,song_id="song",asset_id="asset",
        event_type=MusicEventType.STRONG_BEAT,strength=1,confidence=1,source="step12",
    )


def spark_engine(events=(None,),intensity=1):
    values=(ev(),) if events==(None,) else tuple(events)
    program=build_animation_signal_program(values,4*TIMEBASE)
    return SparkBurstEngine(EventPhaseEngine(program),intensity),program


def layer_with_motion(motion="spark_burst"):
    return Layer(
        track_id="track",type="song_cover",name="cover",
        transform=Transform(x=.2,y=.2,width=.4,height=.4,pivot_x=.5,pivot_y=.5),
        animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"motion_preset":motion,"motion_intensity":1}},
    )


def runtime_for(layer,events=(None,)):
    values=(ev(),) if events==(None,) else tuple(events)
    program=build_animation_signal_program(values,4*TIMEBASE)
    assignment=assignment_for_layer(layer)
    motions={}
    if assignment.motion_preset is not None:
        motions[layer.layer_id]=(assignment.motion_preset,assignment.motion_intensity)
    return BeatVisualRuntime(
        "sig",4*TIMEBASE,AnimationSignalEngine(program),
        {layer.layer_id:assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,len(values),len(program.triggers),len(motions)),
        motions_by_layer_id=motions,
    )


def test_spark_has_exactly_six_deterministic_particles():
    engine,_=spark_engine()
    a=engine.particles(TIMEBASE)
    b=engine.particles(TIMEBASE)
    assert len(a)==6
    assert a==b
    assert [p.particle_index for p in a]==list(range(6))


def test_spark_alpha_decays_and_ends_after_lifetime():
    engine,_=spark_engine()
    start=engine.particles(TIMEBASE)
    mid=engine.particles(TIMEBASE+SPARK_LIFETIME_TICK//2)
    assert sum(p.alpha for p in mid) < sum(p.alpha for p in start)
    assert engine.particles(TIMEBASE+SPARK_LIFETIME_TICK+1)==()


def test_different_event_identity_changes_particle_plan():
    e1=ev(TIMEBASE); e2=ProjectedMusicEvent(2*TIMEBASE,2*TIMEBASE,"song","asset",MusicEventType.STRONG_BEAT,1,1,"step12")
    a,_=spark_engine((e1,))
    b,_=spark_engine((e2,))
    assert a.particles(TIMEBASE) != b.particles(2*TIMEBASE)


def test_overlapping_bursts_remain_bounded_to_six_slots():
    e1=ev(TIMEBASE)
    e2=ProjectedMusicEvent(TIMEBASE+10_000,TIMEBASE+10_000,"song","asset",MusicEventType.STRONG_BEAT,1,1,"step12b")
    engine,_=spark_engine((e1,e2))
    assert len(engine.particles(TIMEBASE+20_000))==6


def test_snapshot_particle_marker_is_clone_only():
    doc=ProjectDocument.new_empty("spark snapshot")
    layer=Layer(
        track_id=doc.tracks[0].track_id,type="song_cover",name="cover",
        transform=Transform(x=.2,y=.2,width=.4,height=.4,pivot_x=.5,pivot_y=.5),
        animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"motion_preset":"spark_burst","motion_intensity":1}},
    )
    doc.layers.append(layer); doc.validate()
    runtime=runtime_for(layer)
    snap=apply_beat_snapshot(doc,runtime,TIMEBASE)
    assert len(snap.layer_map()[layer.layer_id].properties["_beat_snapshot_particles"])==6
    assert "_beat_snapshot_particles" not in doc.layer_map()[layer.layer_id].properties


def test_render_control_emits_named_dynamic_overlay_commands(tmp_path):
    layer=layer_with_motion("bass_sway")
    event=ProjectedMusicEvent(TIMEBASE,TIMEBASE,"song","asset",MusicEventType.BASS_HIT,1,1,"step12")
    runtime=runtime_for(layer,(event,))
    control=build_beat_render_control(runtime,layer,base_width=320,base_height=180,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="sway")
    assert control is not None
    assert control.overlay_filter.startswith("overlay@beat_overlay_")
    text=control.command_file.read_text()
    assert f"{control.overlay_filter} x " in text


def test_spark_render_control_uses_six_bounded_drawbox_slots(tmp_path):
    layer=layer_with_motion("spark_burst")
    runtime=runtime_for(layer)
    control=build_beat_render_control(runtime,layer,base_width=320,base_height=180,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="spark")
    assert control is not None
    assert control.spark_filter_suffix.count("drawbox@beat_spark_")==6
    assert control.command_rows <= 250_000


def test_text_spark_is_not_supported_v1():
    from full_album_maker.advanced_motion_contract import motion_supported_for_layer
    layer=Layer(track_id="t",type="text",name="text")
    assert not motion_supported_for_layer(layer,AdvancedMotionPreset.SPARK_BURST)
