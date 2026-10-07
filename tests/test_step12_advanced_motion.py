from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from full_album_maker.advanced_motion_contract import (
    AdvancedMotionPreset,
    motion_supported_for_layer,
)
from full_album_maker.advanced_motion_engine import AdvancedMotionEngine, merge_visual_and_motion
from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.editor_models import Layer, ProjectDocument, TIMEBASE, Transform
from full_album_maker.editor_session import EditorSession
from full_album_maker.event_phase_modulator import EventPhaseEngine
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.property_inspector import PropertyInspector
from full_album_maker.visual_binding_contract import VisualPropertyState


def _app():
    return QApplication.instance() or QApplication([])


def ev(event_type,tick=TIMEBASE):
    return ProjectedMusicEvent(
        project_tick=tick,source_tick=tick,song_id="song",asset_id="asset",
        event_type=event_type,strength=1,confidence=1,source="step12",
    )


def engines(event_type,tick=TIMEBASE):
    program=build_animation_signal_program((ev(event_type,tick),),3*TIMEBASE)
    signal=AnimationSignalEngine(program)
    return signal,EventPhaseEngine(program)


@pytest.mark.parametrize("preset,event_type",[
    (AdvancedMotionPreset.ALTERNATING_WOBBLE,MusicEventType.STRONG_BEAT),
    (AdvancedMotionPreset.BASS_SWAY,MusicEventType.BASS_HIT),
    (AdvancedMotionPreset.CAMERA_SHAKE,MusicEventType.STRONG_BEAT),
    (AdvancedMotionPreset.BEAT_BOUNCE,MusicEventType.BEAT),
    (AdvancedMotionPreset.FOUR_WAY_KICK,MusicEventType.STRONG_BEAT),
])
def test_motion_is_seek_deterministic(preset,event_type):
    signal,phase=engines(event_type)
    engine=AdvancedMotionEngine(signal,phase,preset,1)
    a=engine.state(TIMEBASE)
    engine.state(TIMEBASE+30_000)
    assert engine.state(TIMEBASE)==a


def test_alternating_wobble_changes_sign_on_next_event():
    events=(ev(MusicEventType.STRONG_BEAT,TIMEBASE),ev(MusicEventType.STRONG_BEAT,2*TIMEBASE))
    program=build_animation_signal_program(events,4*TIMEBASE)
    engine=AdvancedMotionEngine(AnimationSignalEngine(program),EventPhaseEngine(program),AdvancedMotionPreset.ALTERNATING_WOBBLE,1)
    assert engine.state(TIMEBASE).rotation_offset_deg < 0
    assert engine.state(2*TIMEBASE).rotation_offset_deg > 0


def test_bass_sway_changes_sign_on_next_bass_event():
    events=(ev(MusicEventType.BASS_HIT,TIMEBASE),ev(MusicEventType.BASS_HIT,2*TIMEBASE))
    program=build_animation_signal_program(events,4*TIMEBASE)
    engine=AdvancedMotionEngine(AnimationSignalEngine(program),EventPhaseEngine(program),AdvancedMotionPreset.BASS_SWAY,1)
    assert engine.state(TIMEBASE).x_offset_normalized < 0
    assert engine.state(2*TIMEBASE).x_offset_normalized > 0


def test_beat_bounce_is_upward_and_returns_neutral():
    signal,phase=engines(MusicEventType.BEAT)
    engine=AdvancedMotionEngine(signal,phase,AdvancedMotionPreset.BEAT_BOUNCE,1)
    assert engine.state(TIMEBASE).y_offset_normalized < 0
    assert engine.state(2*TIMEBASE).y_offset_normalized == pytest.approx(0)


def test_four_way_first_two_directions():
    events=(ev(MusicEventType.STRONG_BEAT,TIMEBASE),ev(MusicEventType.STRONG_BEAT,2*TIMEBASE))
    program=build_animation_signal_program(events,4*TIMEBASE)
    engine=AdvancedMotionEngine(AnimationSignalEngine(program),EventPhaseEngine(program),AdvancedMotionPreset.FOUR_WAY_KICK,1)
    first=engine.state(TIMEBASE); second=engine.state(2*TIMEBASE)
    assert first.x_offset_normalized < 0 and first.y_offset_normalized == 0
    assert second.y_offset_normalized < 0 and second.x_offset_normalized == 0


def test_camera_shake_is_bounded_and_zero_after_envelope():
    signal,phase=engines(MusicEventType.STRONG_BEAT)
    engine=AdvancedMotionEngine(signal,phase,AdvancedMotionPreset.CAMERA_SHAKE,2)
    state=engine.state(TIMEBASE+20_000)
    assert abs(state.x_offset_normalized) <= .028
    assert abs(state.y_offset_normalized) <= .022
    assert abs(state.rotation_offset_deg) <= 1.6
    assert engine.state(2*TIMEBASE).x_offset_normalized == 0


def test_merge_visual_and_motion_clamps_safe_ranges():
    from full_album_maker.advanced_motion_contract import AdvancedMotionState
    visual=VisualPropertyState(x_offset_normalized=.14,y_offset_normalized=.14,rotation_offset_deg=11)
    motion=AdvancedMotionState(.05,.05,3)
    merged=merge_visual_and_motion(visual,motion)
    assert merged.x_offset_normalized==.15
    assert merged.y_offset_normalized==.15
    assert merged.rotation_offset_deg==12


def test_legacy_assignment_defaults_to_no_motion():
    layer=Layer(track_id="t",type="song_cover",name="cover",animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}})
    a=assignment_for_layer(layer)
    assert a.motion_preset is None
    assert a.motion_intensity==1


def test_motion_assignment_parses_and_validates():
    layer=Layer(track_id="t",type="song_cover",name="cover",animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"motion_preset":"camera_shake","motion_intensity":.8}})
    a=assignment_for_layer(layer)
    assert a.motion_preset==AdvancedMotionPreset.CAMERA_SHAKE
    assert a.motion_intensity==pytest.approx(.8)


def test_text_supports_only_beat_bounce_from_motion_catalog():
    layer=Layer(track_id="t",type="text",name="text")
    allowed={p for p in AdvancedMotionPreset if motion_supported_for_layer(layer,p)}
    assert allowed=={AdvancedMotionPreset.BEAT_BOUNCE}


def test_song_visual_slide_filters_positional_motion():
    layer=Layer(track_id="t",type="song_visual",name="visual",properties={"transition":"slide"})
    for p in (AdvancedMotionPreset.BASS_SWAY,AdvancedMotionPreset.CAMERA_SHAKE,AdvancedMotionPreset.BEAT_BOUNCE,AdvancedMotionPreset.FOUR_WAY_KICK):
        assert not motion_supported_for_layer(layer,p)
    assert motion_supported_for_layer(layer,AdvancedMotionPreset.ALTERNATING_WOBBLE)


def test_editor_session_motion_payload_is_undoable():
    doc=ProjectDocument.new_empty("motion undo")
    layer=Layer(track_id=doc.tracks[0].track_id,type="song_cover",name="cover",transform=Transform(pivot_x=.5,pivot_y=.5))
    doc.layers.append(layer); doc.validate()
    session=EditorSession(doc)
    session.set_beat_animation_payload(layer.layer_id,{"enabled":True,"presets":["strong_punch"],"intensity":1,"motion_preset":"beat_bounce","motion_intensity":.75})
    assert assignment_for_layer(session.snapshot().layer_map()[layer.layer_id]).motion_preset==AdvancedMotionPreset.BEAT_BOUNCE
    session.undo()
    assert assignment_for_layer(session.snapshot().layer_map()[layer.layer_id]) is None


def test_inspector_loads_legacy_motion_none_and_filters_text():
    _app()
    layer=Layer(track_id="t",type="text",name="text",animation={"beat_v1":{"enabled":True,"presets":["strong_punch"]}})
    inspector=PropertyInspector(); inspector.set_layer(layer)
    assert inspector.beat_motion.currentData()=="none"
    values={inspector.beat_motion.itemData(i) for i in range(inspector.beat_motion.count())}
    assert AdvancedMotionPreset.BEAT_BOUNCE.value in values
    assert AdvancedMotionPreset.CAMERA_SHAKE.value not in values
    assert AdvancedMotionPreset.SPARK_BURST.value not in values
