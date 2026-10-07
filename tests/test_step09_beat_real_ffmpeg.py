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
from full_album_maker.song_visuals import make_song_visual_layer, normalize_song_visual_properties
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler


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
        "-f","lavfi","-i","color=c=#c03030:s=320x240:d=0.1",
        "-frames:v","1",str(path),
    ],check=True)
    return path


def _doc(tmp_path: Path, *, real_audio=False):
    doc=ProjectDocument.new_empty("STEP09 real")
    doc.canvas.width=320; doc.canvas.height=240
    doc.canvas.fps_num=30; doc.canvas.fps_den=1
    duration=TIMEBASE
    audio_path=tmp_path/"song.wav" if real_audio else tmp_path/"unused.wav"
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


def _runtime(doc,layer):
    event=ProjectedMusicEvent(
        project_tick=int(.30*TIMEBASE),source_tick=int(.30*TIMEBASE),
        song_id=doc.playlist.entries[0].song_id,asset_id=doc.playlist.entries[0].asset_id,
        event_type=MusicEventType.STRONG_BEAT,strength=1,confidence=1,source="real-smoke",
    )
    program=build_animation_signal_program((event,),TIMEBASE)
    assignment=assignment_for_layer(layer)
    return BeatVisualRuntime(
        doc.content_signature(),TIMEBASE,AnimationSignalEngine(program),
        {layer.layer_id:assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,1,len(program.triggers)),
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


def test_real_ffmpeg_background_beat_modulation(tmp_path):
    doc,_,_,_=_doc(tmp_path)
    layer=Layer(
        track_id=doc.tracks[0].track_id,type="background",name="BG",
        transform=Transform(x=0,y=0,width=1,height=1,pivot_x=.5,pivot_y=.5),
        properties={"mode":"solid","color":"#204060"},
        animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}},
    )
    doc.layers.append(layer); doc.validate()
    video=_render(doc,_runtime(doc,layer),tmp_path,"background")
    hashes=_hashes(video)
    assert len(set(hashes))>1


def test_real_ffmpeg_song_visual_beat_modulation(tmp_path):
    doc,_,_,_=_doc(tmp_path)
    layer=make_song_visual_layer(doc.tracks[0].track_id,2)
    layer.properties=normalize_song_visual_properties({
        "fit":"fill","image_motion":"static","video_playback":"loop",
        "transition":"cut","transition_seconds":0,
    })
    layer.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    doc.layers.append(layer); doc.validate()
    video=_render(doc,_runtime(doc,layer),tmp_path,"songvisual")
    hashes=_hashes(video)
    assert len(set(hashes))>1


def test_real_ffmpeg_spectrum_beat_modulation(tmp_path):
    doc,_,_,_=_doc(tmp_path,real_audio=True)
    layer=make_spectrum_layer(doc.tracks[0].track_id,2)
    layer.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    doc.layers.append(layer); doc.validate()
    video=_render(doc,_runtime(doc,layer),tmp_path,"spectrum")
    hashes=_hashes(video)
    assert len(set(hashes))>1


def test_real_ffmpeg_drawtext_beat_modulation(tmp_path):
    doc,_,_,_=_doc(tmp_path)
    layer=Layer(
        track_id=doc.tracks[0].track_id,type="text",name="Text",
        transform=Transform(x=.15,y=.35,width=.7,height=.2,pivot_x=.5,pivot_y=.5),
        properties={"text":"BEAT","font_size":28,"color":"#ffffff"},
        animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}},
    )
    doc.layers.append(layer); doc.validate()
    video=_render(doc,_runtime(doc,layer),tmp_path,"text")
    hashes=_hashes(video)
    assert len(set(hashes))>1
