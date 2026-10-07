from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.audio_analysis_contract import (
    ANALYZER_VERSION, AnalysisCurve, AnalysisEvent, AnalysisEventType,
    AnalysisQuality, AudioAnalysisResult, HOP_LENGTH, SAMPLE_RATE,
    TICKS_PER_FRAME, TempoSummary,
)
from full_album_maker.audio_analysis_fingerprint import AnalyzerSettings
from full_album_maker.beat_animation_assignment import (
    assignment_for_layer, document_has_beat_animation,
)
from full_album_maker.beat_render_control import (
    BeatRenderControlError, build_beat_render_control, render_filter_suffix,
)
from full_album_maker.beat_visual_runtime import (
    BeatRuntimeDiagnostics, BeatVisualRuntime, apply_beat_snapshot,
    build_beat_visual_runtime,
)
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.visual_binding_contract import CoreBeatPreset
from full_album_maker.visual_binding_engine import combine_binding_sets, core_binding_set


def _analysis(asset_id: str) -> AudioAnalysisResult:
    size=120
    energy=[0.1]*size; bass=[0.1]*size; onset=[0.05]*size
    for frame in (20, 45, 70, 95):
        energy[frame]=0.9; bass[frame]=1.0; onset[frame]=1.0
    curves=tuple(
        AnalysisCurve(name, tuple(vals))
        for name,vals in (
            ("energy",energy),("bass",bass),("mid",[0.1]*size),
            ("high",[0.1]*size),("onset",onset),
        )
    )
    beats=tuple(AnalysisEvent(f*TICKS_PER_FRAME,AnalysisEventType.BEAT,.9,.9) for f in (20,45,70,95))
    onsets=tuple(AnalysisEvent(f*TICKS_PER_FRAME,AnalysisEventType.ONSET,1.0,1.0) for f in (20,45,70,95))
    result=AudioAnalysisResult(
        asset_id=asset_id,content_sha256="a"*64,
        settings_signature=AnalyzerSettings().signature(),
        analyzer_version=ANALYZER_VERSION,duration_tick=size*TICKS_PER_FRAME,
        sample_rate=SAMPLE_RATE,hop_length=HOP_LENGTH,
        tempo=TempoSummary(120.0,.9,AnalysisQuality.HIGH,.03),
        quality_flags=(),beats=beats,onsets=onsets,curves=curves,source_name="song.wav",
    )
    result.validate()
    return result


def _document(layer_type="song_cover", presets=("strong_punch",), duration=3*TIMEBASE):
    doc=ProjectDocument.new_empty("Beat STEP08")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=duration)
    image=MediaAsset(kind="image",locator="cover.png",original_name="cover.png")
    doc.media.extend([audio,image])
    song=SongInstance(asset_id=audio.asset_id,display_title="Song",cover_asset_id=image.asset_id,source_out_tick=duration)
    doc.playlist.entries.append(song)
    layer=Layer(
        track_id=doc.tracks[0].track_id,type=layer_type,name="Beat Layer",
        transform=Transform(x=.25,y=.2,width=.4,height=.4,pivot_x=.5,pivot_y=.5),
        properties={"fallback_asset_id": image.asset_id, "fit": "fill"} if layer_type=="song_cover" else {},
        animation={"beat_v1":{"enabled":True,"presets":list(presets)}},
    )
    doc.layers.append(layer)
    doc.validate()
    return doc,audio,image,song,layer


def _runtime_for(doc, audio, layer):
    return build_beat_visual_runtime(
        doc,
        analysis_results={audio.asset_id:_analysis(audio.asset_id)},
        ensure_analysis=False,
    )


def _graph(compiled):
    args=list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex")+1]
    if "-filter_complex_script" in args:
        return Path(args[args.index("-filter_complex_script")+1]).read_text(encoding="utf-8")
    raise AssertionError("filter graph missing")


def test_assignment_parser_and_document_detection():
    doc,audio,image,song,layer=_document()
    assignment=assignment_for_layer(layer)
    assert assignment is not None
    assert assignment.presets==(CoreBeatPreset.STRONG_PUNCH,)
    assert document_has_beat_animation(doc)


def test_disabled_assignment_returns_none():
    doc,audio,image,song,layer=_document()
    layer.animation["beat_v1"]["enabled"]=False
    assert assignment_for_layer(layer) is None
    assert not document_has_beat_animation(doc)


def test_unknown_preset_rejected():
    doc,audio,image,song,layer=_document()
    layer.animation["beat_v1"]["presets"]=["wat"]
    with pytest.raises(ValueError):
        assignment_for_layer(layer)


def test_runtime_builds_from_supplied_analysis_without_mutation():
    doc,audio,image,song,layer=_document()
    before=doc.content_signature()
    runtime=_runtime_for(doc,audio,layer)
    assert runtime is not None and runtime.has_layer(layer.layer_id)
    assert runtime.diagnostics.trigger_count > 0
    assert doc.content_signature()==before


def test_snapshot_is_clone_and_removes_assignment():
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    tick=20*TICKS_PER_FRAME
    snap=apply_beat_snapshot(doc,runtime,tick)
    sl=snap.layer_map()[layer.layer_id]
    assert "beat_v1" not in sl.animation
    assert sl.properties["_beat_snapshot_glow"] > 0
    assert sl.transform.width > layer.transform.width
    assert "beat_v1" in doc.layer_map()[layer.layer_id].animation


def test_runtime_zero_tick_is_deterministic():
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    a=runtime.state_for_layer(layer.layer_id,20*TICKS_PER_FRAME)
    b=runtime.state_for_layer(layer.layer_id,20*TICKS_PER_FRAME)
    assert a==b


def test_render_control_writes_scale_glow_commands(tmp_path):
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    control=build_beat_render_control(
        runtime,layer,base_width=200,base_height=200,fps=30,
        intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="cover",
    )
    assert control is not None
    text=control.command_file.read_text(encoding="utf-8")
    assert "scale@beat_size_" in text
    assert " width " in text and " height " in text
    assert "eq@beat_glow_" in text
    assert control.command_rows > 0


def test_rotation_nudge_requires_center_pivot(tmp_path):
    doc,audio,image,song,layer=_document(presets=("rotation_nudge",))
    layer.transform.pivot_x=.2
    runtime=_runtime_for(doc,audio,layer)
    with pytest.raises(BeatRenderControlError):
        build_beat_render_control(runtime,layer,base_width=200,base_height=200,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="x")


def test_render_control_rejects_nonzero_base_rotation(tmp_path):
    doc,audio,image,song,layer=_document()
    layer.transform.rotation=10
    runtime=_runtime_for(doc,audio,layer)
    with pytest.raises(BeatRenderControlError):
        build_beat_render_control(runtime,layer,base_width=200,base_height=200,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="x")


def test_filter_suffix_names_runtime_filters(tmp_path):
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    control=build_beat_render_control(runtime,layer,base_width=200,base_height=200,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path,stream_key="x")
    suffix=render_filter_suffix(control,base_width=200,base_height=200)
    assert "sendcmd=f=" in suffix
    assert "scale@beat_size_" in suffix
    assert "eq@beat_glow_" in suffix


def test_compiler_without_runtime_has_no_beat_filters(tmp_path):
    doc,audio,image,song,layer=_document()
    compiled=Step08FFmpegCompiler("ffmpeg").compile_video(doc,tmp_path/"out.mp4",tmp_path)
    graph=_graph(compiled)
    assert "beat_size_" not in graph
    assert "sendcmd=f=" not in graph


def test_cover_compiler_injects_runtime_controls(tmp_path):
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    compiled=Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path)
    graph=_graph(compiled)
    assert "sendcmd=f=" in graph
    assert "scale@beat_size_" in graph
    assert "eq@beat_glow_" in graph
    assert list(tmp_path.glob("beat-*.sendcmd"))


def test_snapshot_compiler_injects_static_glow_not_sendcmd(tmp_path):
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    snap=apply_beat_snapshot(doc,runtime,20*TICKS_PER_FRAME)
    compiled=Step08FFmpegCompiler("ffmpeg").compile_video(snap,tmp_path/"out.mp4",tmp_path)
    graph=_graph(compiled)
    assert "eq=brightness=" in graph
    assert "sendcmd=f=" not in graph


def test_vinyl_compiler_injects_runtime_controls(tmp_path):
    doc,audio,image,song,cover=_document()
    cover.enabled=False
    vinyl=Layer(
        track_id=doc.tracks[0].track_id,type="vinyl",name="Vinyl",
        transform=Transform(x=.3,y=.25,width=.3,height=.3,pivot_x=.5,pivot_y=.5),
        properties={"color":"#151515","groove_color":"#333333","center_color":"#dddddd","spin_seconds":4.0,"center_ratio":0.16},
        animation={"beat_v1":{"enabled":True,"presets":["bass_pulse","rotation_nudge"]}},
    )
    doc.layers.append(vinyl); doc.validate()
    runtime=build_beat_visual_runtime(doc,analysis_results={audio.asset_id:_analysis(audio.asset_id)},ensure_analysis=False)
    compiled=Step08FFmpegCompiler("ffmpeg",beat_runtime=runtime).compile_video(doc,tmp_path/"out.mp4",tmp_path)
    graph=_graph(compiled)
    assert "beat_size_" in graph
    assert "beat_rotate_" in graph
    assert list(tmp_path.glob("beat-*.sendcmd"))


def test_command_sampling_is_deterministic(tmp_path):
    doc,audio,image,song,layer=_document()
    runtime=_runtime_for(doc,audio,layer)
    a=build_beat_render_control(runtime,layer,base_width=200,base_height=200,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path/"a",stream_key="same")
    b=build_beat_render_control(runtime,layer,base_width=200,base_height=200,fps=30,intervals=[(0,3*TIMEBASE)],work_dir=tmp_path/"b",stream_key="same")
    assert a.command_file.read_text()==b.command_file.read_text()
