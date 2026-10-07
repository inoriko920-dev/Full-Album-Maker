from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler

FFMPEG=shutil.which("ffmpeg")


def _ffmpeg():
    if not FFMPEG:
        pytest.skip("ffmpeg unavailable")
    return FFMPEG


def _image(path: Path):
    subprocess.run([
        _ffmpeg(),"-y","-hide_banner","-loglevel","error",
        "-f","lavfi","-i","testsrc2=size=320x240:rate=1:duration=0.1",
        "-frames:v","1",str(path),
    ],check=True)
    return path


def _doc(tmp_path: Path):
    doc=ProjectDocument.new_empty("STEP12 real")
    doc.canvas.width=320; doc.canvas.height=240
    doc.canvas.fps_num=30; doc.canvas.fps_den=1
    duration=2*TIMEBASE
    audio=MediaAsset(kind="audio",locator=str(tmp_path/"unused.wav"),original_name="unused.wav",source_duration_tick=duration)
    image_path=_image(tmp_path/"visual.png")
    image=MediaAsset(kind="image",locator=str(image_path),original_name="visual.png")
    doc.media.extend([audio,image])
    song=SongInstance(asset_id=audio.asset_id,source_out_tick=duration,display_title="Motion",cover_asset_id=image.asset_id)
    doc.playlist.entries.append(song)
    return doc,image,song


def _cover(doc,image,motion):
    layer=Layer(
        track_id=doc.tracks[0].track_id,type="song_cover",name="Cover",
        transform=Transform(x=.2,y=.18,width=.55,height=.62,pivot_x=.5,pivot_y=.5),
        properties={"fit":"fill","fallback_asset_id":image.asset_id},
        animation={"beat_v1":{
            "enabled":True,"presets":["subtle_beat_pulse"],"intensity":.4,
            "motion_preset":motion,"motion_intensity":1.0,
        }},
    )
    doc.layers.append(layer); doc.validate()
    return layer


def _runtime(doc,layer,event_type):
    event=ProjectedMusicEvent(
        project_tick=int(.40*TIMEBASE),source_tick=int(.40*TIMEBASE),
        song_id=doc.playlist.entries[0].song_id,asset_id=doc.playlist.entries[0].asset_id,
        event_type=event_type,strength=1,confidence=1,source="step12-real",
    )
    program=build_animation_signal_program((event,),2*TIMEBASE)
    assignment=assignment_for_layer(layer); assert assignment is not None
    motions={}
    if assignment.motion_preset is not None:
        motions[layer.layer_id]=(assignment.motion_preset,assignment.motion_intensity)
    return BeatVisualRuntime(
        doc.content_signature(),2*TIMEBASE,AnimationSignalEngine(program),
        {layer.layer_id:assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,1,len(program.triggers),len(motions)),
        motions_by_layer_id=motions,
    )


def _render(doc,runtime,tmp_path,name):
    out=tmp_path/f"{name}.mp4"; work=tmp_path/f"work-{name}"
    compiled=Step08FFmpegCompiler(_ffmpeg(),beat_runtime=runtime).compile_video(doc,out,work,include_audio=False)
    proc=subprocess.run(compiled.args,capture_output=True,text=True,timeout=60)
    assert proc.returncode==0,proc.stderr
    assert out.exists() and out.stat().st_size>0
    return out


def _hashes(video):
    proc=subprocess.run([_ffmpeg(),"-hide_banner","-loglevel","error","-i",str(video),"-f","framemd5","-"],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr
    return [line.rsplit(",",1)[-1].strip() for line in proc.stdout.splitlines() if line and not line.startswith("#")]


def test_real_ffmpeg_bass_sway_moves_cover(tmp_path):
    doc,image,song=_doc(tmp_path); layer=_cover(doc,image,"bass_sway")
    video=_render(doc,_runtime(doc,layer,MusicEventType.BASS_HIT),tmp_path,"sway")
    assert len(set(_hashes(video)))>1


def test_real_ffmpeg_camera_shake_moves_cover(tmp_path):
    doc,image,song=_doc(tmp_path); layer=_cover(doc,image,"camera_shake")
    video=_render(doc,_runtime(doc,layer,MusicEventType.STRONG_BEAT),tmp_path,"shake")
    assert len(set(_hashes(video)))>1


def test_real_ffmpeg_spark_burst_changes_frames(tmp_path):
    doc,image,song=_doc(tmp_path); layer=_cover(doc,image,"spark_burst")
    video=_render(doc,_runtime(doc,layer,MusicEventType.STRONG_BEAT),tmp_path,"spark")
    hashes=_hashes(video)
    assert len(set(hashes))>1
