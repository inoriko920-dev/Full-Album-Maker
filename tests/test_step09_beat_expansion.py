from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_layer_capabilities import BeatRenderLevel, beat_capability_for_layer
from full_album_maker.beat_text_render_control import BeatTextRenderControlError, build_beat_text_render_control
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime, apply_beat_snapshot
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.editor_session import EditorSession
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.property_inspector import PropertyInspector
from full_album_maker.song_visuals import make_song_visual_layer, normalize_song_visual_properties
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.visual_binding_contract import CoreBeatPreset, VisualProperty


def _app():
    return QApplication.instance() or QApplication([])


def _base_doc(duration=2*TIMEBASE):
    doc=ProjectDocument.new_empty("STEP09")
    doc.canvas.width=320; doc.canvas.height=240
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=duration)
    image=MediaAsset(kind="image",locator="visual.png",original_name="visual.png")
    doc.media.extend([audio,image])
    song=SongInstance(
        asset_id=audio.asset_id,source_out_tick=duration,
        display_title="Beat Song",display_artist="Artist",
        cover_asset_id=image.asset_id,visual_asset_id=image.asset_id,
    )
    doc.playlist.entries.append(song)
    return doc,audio,image,song


def _runtime(doc, layer, event_type=MusicEventType.STRONG_BEAT):
    event=ProjectedMusicEvent(
        project_tick=TIMEBASE//2,
        source_tick=TIMEBASE//2,
        song_id=doc.playlist.entries[0].song_id,
        asset_id=doc.playlist.entries[0].asset_id,
        event_type=event_type,
        strength=1.0,confidence=1.0,source="step09-test",
    )
    program=build_animation_signal_program((event,),2*TIMEBASE)
    assignment=assignment_for_layer(layer)
    assert assignment is not None
    return BeatVisualRuntime(
        doc.content_signature(),2*TIMEBASE,AnimationSignalEngine(program),
        {layer.layer_id:assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,1,len(program.triggers)),
    )


def _graph(compiled):
    args=list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex")+1]
    if "-/filter_complex" in args:
        return Path(args[args.index("-/filter_complex")+1]).read_text(encoding="utf-8")
    if "-filter_complex_script" in args:
        return Path(args[args.index("-filter_complex_script")+1]).read_text(encoding="utf-8")
    raise AssertionError("filter graph missing")


def _beat_layer(doc, layer_type, presets=("strong_punch",), intensity=1.0):
    layer=Layer(
        track_id=doc.tracks[0].track_id,
        type=layer_type,
        name=f"Beat {layer_type}",
        transform=Transform(x=.2,y=.2,width=.5,height=.5,pivot_x=.5,pivot_y=.5),
        animation={"beat_v1":{"enabled":True,"presets":list(presets),"intensity":intensity}},
    )
    doc.layers.append(layer)
    return layer


def test_legacy_assignment_defaults_intensity_one():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    del layer.animation["beat_v1"]["intensity"]
    assert assignment_for_layer(layer).intensity == 1.0


@pytest.mark.parametrize("value",[-.01,2.01,float("inf")])
def test_assignment_rejects_invalid_intensity(value):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text",intensity=value)
    with pytest.raises(ValueError):
        assignment_for_layer(layer)


def test_intensity_scales_binding_amount_not_signal_time():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"song_cover",intensity=.5)
    assignment=assignment_for_layer(layer)
    scale=[b for b in assignment.binding_set().bindings if b.property==VisualProperty.SCALE_MULTIPLIER][0]
    assert scale.amount == pytest.approx(.04)


def test_text_capability_excludes_rotation():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    cap=beat_capability_for_layer(layer)
    assert cap.final_render_level == BeatRenderLevel.LIMITED
    assert CoreBeatPreset.ROTATION_NUDGE not in cap.supported_presets
    assert CoreBeatPreset.STRONG_PUNCH in cap.supported_presets


def test_visual_capability_hides_rotation_when_not_safe():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"background")
    layer.transform.rotation=5
    cap=beat_capability_for_layer(layer)
    assert CoreBeatPreset.ROTATION_NUDGE not in cap.supported_presets
    assert CoreBeatPreset.STRONG_PUNCH in cap.supported_presets


def test_editor_session_beat_assignment_is_undo_redo_safe():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"background")
    layer.animation.clear()
    doc.validate()
    session=EditorSession(doc)
    start=session.revision
    session.set_beat_animation(layer.layer_id,enabled=True,preset=CoreBeatPreset.STRONG_PUNCH,intensity=1.25)
    changed=session.snapshot().layer_map()[layer.layer_id]
    assert changed.animation["beat_v1"]["intensity"] == 1.25
    assert session.revision == start+1
    session.undo()
    assert "beat_v1" not in session.snapshot().layer_map()[layer.layer_id].animation
    session.redo()
    assert session.snapshot().layer_map()[layer.layer_id].animation["beat_v1"]["presets"] == ["strong_punch"]


def test_editor_session_rejects_text_rotation_nudge():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    layer.animation.clear(); doc.validate()
    session=EditorSession(doc)
    with pytest.raises(ValueError):
        session.set_beat_animation(layer.layer_id,enabled=True,preset=CoreBeatPreset.ROTATION_NUDGE,intensity=1)


def test_property_inspector_filters_text_presets():
    _app()
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    inspector=PropertyInspector()
    inspector.set_layer(layer)
    values=[inspector.beat_preset.itemData(i) for i in range(inspector.beat_preset.count())]
    assert "rotation_nudge" not in values
    assert "strong_punch" in values
    assert inspector.beat_intensity.value() == 100


def test_property_inspector_loads_intensity_and_multi_state():
    _app()
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"song_cover",presets=("strong_punch","bass_pulse"),intensity=1.5)
    inspector=PropertyInspector()
    inspector.set_layer(layer)
    assert inspector.beat_preset.currentData() == "__multi__"
    assert inspector.beat_intensity.value() == 150


def test_background_compiler_injects_beat_controls(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"background")
    layer.properties={"mode":"solid","color":"#204060"}
    doc.validate()
    runtime=_runtime(doc,layer)
    compiled=Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path)
    graph=_graph(compiled)
    assert "beat_size_" in graph and "beat_glow_" in graph
    assert list(tmp_path.glob("beat-*.sendcmd"))


def test_background_without_runtime_preserves_no_beat_graph(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"background")
    layer.properties={"mode":"solid","color":"#204060"}
    doc.validate()
    graph=_graph(Step08FFmpegCompiler("ffmpeg").compile_video(doc,tmp_path/"out.mp4",tmp_path))
    assert "beat_size_" not in graph


def test_song_visual_compiler_uses_global_pts_then_beat_controls(tmp_path):
    doc,_,_,_=_base_doc()
    layer=make_song_visual_layer(doc.tracks[0].track_id,3)
    layer.properties=normalize_song_visual_properties({
        "fit":"fill","image_motion":"static","video_playback":"loop",
        "transition":"cut","transition_seconds":0,
    })
    layer.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    doc.layers.append(layer); doc.validate()
    runtime=_runtime(doc,layer)
    graph=_graph(Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path))
    assert "beat_size_" in graph and "beat_glow_" in graph
    assert "svsrc" in graph


def test_spectrum_compiler_keeps_audio_reactive_chain_and_adds_beat(tmp_path):
    doc,_,_,_=_base_doc()
    layer=make_spectrum_layer(doc.tracks[0].track_id,2)
    layer.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    doc.layers.append(layer); doc.validate()
    runtime=_runtime(doc,layer)
    graph=_graph(Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path))
    assert "showfreqs" in graph or "showwaves" in graph
    assert "beat_size_" in graph and "sendcmd=f=" in graph


def test_text_render_control_writes_fontsize_and_borderw(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    runtime=_runtime(doc,layer)
    control=build_beat_text_render_control(
        runtime,layer,base_fontsize=40,fps=30,
        intervals=[(0,2*TIMEBASE)],work_dir=tmp_path,stream_key="text",
    )
    assert control is not None
    body=control.command_file.read_text(encoding="utf-8")
    assert " fontsize " in body and " borderw " in body
    assert "drawtext@beat_text_" in body


def test_text_rotation_nudge_fails_closed(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text",presets=("rotation_nudge",))
    runtime=_runtime(doc,layer)
    with pytest.raises(BeatTextRenderControlError):
        build_beat_text_render_control(
            runtime,layer,base_fontsize=40,fps=30,
            intervals=[(0,2*TIMEBASE)],work_dir=tmp_path,stream_key="text",
        )


def test_text_compiler_injects_named_drawtext_and_sendcmd(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    layer.properties={"text":"Beat Text","font_size":40,"color":"#ffffff"}
    doc.validate()
    runtime=_runtime(doc,layer)
    graph=_graph(Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path))
    assert "drawtext@beat_text_" in graph
    assert "sendcmd=f=" in graph
    assert "borderw=0" in graph
    assert list(tmp_path.glob("beat-text-*.sendcmd"))


def test_song_title_compiler_scopes_commands_to_song(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"song_title")
    layer.properties={"template":"{title}","font_size":42,"color":"#ffffff"}
    doc.validate()
    runtime=_runtime(doc,layer)
    graph=_graph(Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path))
    assert "drawtext@beat_text_" in graph
    assert "enable='between(t," in graph


def test_accurate_snapshot_sets_font_scale_and_removes_assignment():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    layer.properties={"text":"Beat","font_size":40,"color":"#ffffff"}
    doc.validate()
    runtime=_runtime(doc,layer)
    snap=apply_beat_snapshot(doc,runtime,TIMEBASE//2)
    sl=snap.layer_map()[layer.layer_id]
    assert sl.properties["_beat_snapshot_font_scale"] > 1
    assert sl.properties["_beat_snapshot_glow"] > 0
    assert "beat_v1" not in sl.animation
    assert "beat_v1" in doc.layer_map()[layer.layer_id].animation


def test_snapshot_text_compiler_uses_static_scaled_font_not_sendcmd(tmp_path):
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"text")
    layer.properties={"text":"Beat","font_size":40,"color":"#ffffff"}
    doc.validate()
    runtime=_runtime(doc,layer)
    snap=apply_beat_snapshot(doc,runtime,TIMEBASE//2)
    graph=_graph(Step08FFmpegCompiler("ffmpeg").compile_video(snap,tmp_path/"out.mp4",tmp_path))
    assert "sendcmd=f=" not in graph
    assert "fontsize=40" not in graph
    assert "borderw=0" not in graph


def test_intensity_zero_keeps_runtime_but_visual_neutral():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"song_cover",intensity=0)
    runtime=_runtime(doc,layer)
    state=runtime.state_for_layer(layer.layer_id,TIMEBASE//2)
    assert state.scale_multiplier == 1
    assert state.zoom_multiplier == 1
    assert state.glow_amount == 0


def test_intensity_changes_document_signature():
    doc,_,_,_=_base_doc()
    layer=_beat_layer(doc,"background",intensity=1)
    a=doc.content_signature()
    layer.animation["beat_v1"]["intensity"]=1.25
    b=doc.content_signature()
    assert a != b
