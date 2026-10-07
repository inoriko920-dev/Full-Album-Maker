from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.audio_analysis_contract import AnalysisQuality
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.vinyl_bpm_sync import TempoSegment

FFMPEG=shutil.which("ffmpeg")


def _ffmpeg():
    if not FFMPEG:
        pytest.skip("ffmpeg unavailable")
    return FFMPEG


def _audio(path: Path, duration=1.0):
    subprocess.run([
        _ffmpeg(),"-y","-hide_banner","-loglevel","error",
        "-f","lavfi","-i",f"sine=frequency=120:duration={duration}",
        "-ar","48000","-ac","2",str(path),
    ],check=True)
    return path


def _image(path: Path):
    subprocess.run([
        _ffmpeg(),"-y","-hide_banner","-loglevel","error",
        "-f","lavfi","-i","testsrc2=size=320x240:rate=1:duration=0.1",
        "-frames:v","1",str(path),
    ],check=True)
    return path


def _doc(tmp_path: Path, *, real_audio=False):
    doc=ProjectDocument.new_empty("STEP10 real")
    doc.canvas.width=320; doc.canvas.height=240
    doc.canvas.fps_num=30; doc.canvas.fps_den=1
    duration=TIMEBASE
    audio_path=tmp_path/"song.wav"
    if real_audio:
        _audio(audio_path)
    audio=MediaAsset(kind="audio",locator=str(audio_path),original_name="song.wav",source_duration_tick=duration)
    image_path=_image(tmp_path/"visual.png")
    image=MediaAsset(kind="image",locator=str(image_path),original_name="visual.png")
    doc.media.extend([audio,image])
    song=SongInstance(
        asset_id=audio.asset_id,source_out_tick=duration,
        display_title="Beat",display_artist="Artist",
        cover_asset_id=image.asset_id,visual_asset_id=image.asset_id,
    )
    doc.playlist.entries.append(song)
    return doc,audio,image,song


def _event_runtime(doc,layer,event_type):
    event=ProjectedMusicEvent(
        project_tick=int(.30*TIMEBASE),source_tick=int(.30*TIMEBASE),
        song_id=doc.playlist.entries[0].song_id,asset_id=doc.playlist.entries[0].asset_id,
        event_type=event_type,strength=1,confidence=1,source="step10-real",
    )
    program=build_animation_signal_program((event,),TIMEBASE)
    assignment=assignment_for_layer(layer)
    assert assignment is not None
    return BeatVisualRuntime(
        doc.content_signature(),TIMEBASE,AnimationSignalEngine(program),
        {layer.layer_id:assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,1,len(program.triggers)),
    )


def _bpm_runtime(doc,audio,song,bpm=120):
    program=build_animation_signal_program((),TIMEBASE)
    segment=TempoSegment(
        song.song_id,audio.asset_id,0,TIMEBASE,float(bpm),.95,AnalysisQuality.HIGH
    )
    return BeatVisualRuntime(
        doc.content_signature(),TIMEBASE,AnimationSignalEngine(program),{},
        BeatRuntimeDiagnostics(1,0,0,0),
        tempo_segments=(segment,),
    )


def _render(doc,runtime,tmp_path,name):
    out=tmp_path/f"{name}.mp4"
    work=tmp_path/f"work-{name}"
    compiled=Step08FFmpegCompiler(_ffmpeg(),beat_runtime=runtime).compile_video(
        doc,out,work,include_audio=False,
    )
    proc=subprocess.run(compiled.args,capture_output=True,text=True,timeout=60)
    assert proc.returncode==0,proc.stderr
    assert out.exists() and out.stat().st_size>0
    return out


def _hashes(video: Path):
    proc=subprocess.run(
        [_ffmpeg(),"-hide_banner","-loglevel","error","-i",str(video),"-f","framemd5","-"],
        capture_output=True,text=True,timeout=30,
    )
    assert proc.returncode==0,proc.stderr
    return [
        line.rsplit(",",1)[-1].strip()
        for line in proc.stdout.splitlines()
        if line and not line.startswith("#")
    ]


def test_real_ffmpeg_vinyl_bpm_sync_changes_phase_speed(tmp_path):
    doc,audio,image,song=_doc(tmp_path)
    vinyl=Layer(
        track_id=doc.tracks[0].track_id,type="vinyl",name="Vinyl BPM",
        transform=Transform(x=.25,y=.18,width=.5,height=.64,pivot_x=.5,pivot_y=.5),
        properties={
            "color":"#151515","groove_color":"#666666","center_color":"#d9d9d9",
            "spin_seconds":60.0,"center_ratio":.18,
            "bpm_sync":True,"beats_per_rotation":4.0,"bpm_sync_min_confidence":.55,
        },
    )
    doc.layers.append(vinyl); doc.validate()
    synced=_render(doc,_bpm_runtime(doc,audio,song,120),tmp_path,"vinyl-sync")
    vinyl.properties["bpm_sync"]=False
    static=_render(doc,None,tmp_path,"vinyl-static")
    assert _hashes(synced) != _hashes(static)


def test_real_ffmpeg_advanced_club_punch_cover(tmp_path):
    doc,audio,image,song=_doc(tmp_path)
    cover=Layer(
        track_id=doc.tracks[0].track_id,type="song_cover",name="Cover",
        transform=Transform(x=.2,y=.15,width=.6,height=.7,pivot_x=.5,pivot_y=.5),
        properties={"fit":"fill","fallback_asset_id":image.asset_id},
        animation={"beat_v1":{"enabled":True,"presets":["club_punch"],"intensity":1}},
    )
    doc.layers.append(cover); doc.validate()
    video=_render(doc,_event_runtime(doc,cover,MusicEventType.STRONG_BEAT),tmp_path,"club-cover")
    assert len(set(_hashes(video)))>1


def test_real_ffmpeg_advanced_spectrum_bass_punch(tmp_path):
    doc,audio,image,song=_doc(tmp_path,real_audio=True)
    spectrum=make_spectrum_layer(doc.tracks[0].track_id,2)
    spectrum.animation={"beat_v1":{"enabled":True,"presets":["bass_punch"],"intensity":1}}
    doc.layers.append(spectrum); doc.validate()
    video=_render(doc,_event_runtime(doc,spectrum,MusicEventType.BASS_HIT),tmp_path,"bass-spectrum")
    assert len(set(_hashes(video)))>1
