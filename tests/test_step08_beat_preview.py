from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_visual_runtime import BeatRuntimeDiagnostics, BeatVisualRuntime
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.preview_scene import PreviewCanvas


def _app():
    return QApplication.instance() or QApplication([])


def _fixture():
    doc=ProjectDocument.new_empty("STEP08 preview")
    audio=MediaAsset(kind="audio",locator="song.wav",source_duration_tick=2*TIMEBASE)
    doc.media.append(audio)
    song=SongInstance(asset_id=audio.asset_id,display_title="Song",source_out_tick=2*TIMEBASE)
    doc.playlist.entries.append(song)
    layer=Layer(
        track_id=doc.tracks[0].track_id,
        type="song_cover",
        name="Cover",
        transform=Transform(x=.3,y=.25,width=.3,height=.3,pivot_x=.5,pivot_y=.5),
        animation={"beat_v1":{"enabled":True,"presets":["strong_punch"]}},
    )
    doc.layers.append(layer)
    doc.validate()
    event=ProjectedMusicEvent(
        project_tick=TIMEBASE,
        source_tick=TIMEBASE,
        song_id=song.song_id,
        asset_id=audio.asset_id,
        event_type=MusicEventType.STRONG_BEAT,
        strength=1.0,
        confidence=1.0,
        source="test",
    )
    program=build_animation_signal_program((event,),2*TIMEBASE)
    assignment=assignment_for_layer(layer)
    runtime=BeatVisualRuntime(
        doc.content_signature(),
        2*TIMEBASE,
        AnimationSignalEngine(program),
        {layer.layer_id: assignment.binding_set()},
        BeatRuntimeDiagnostics(1,1,1,len(program.triggers)),
    )
    return doc,layer,runtime


def _image_bytes(image):
    ptr=image.bits()
    return bytes(ptr[: image.sizeInBytes()])


def test_fast_preview_changes_pixels_at_strong_beat():
    _app()
    doc,layer,runtime=_fixture()
    canvas=PreviewCanvas()
    canvas.resize(640,360)
    canvas.set_document(doc)
    canvas.set_playhead(TIMEBASE)
    canvas.show()
    QApplication.processEvents()
    before=canvas.grab().toImage().convertToFormat(canvas.grab().toImage().Format.Format_RGBA8888)
    canvas.set_beat_runtime(runtime)
    QApplication.processEvents()
    after=canvas.grab().toImage().convertToFormat(canvas.grab().toImage().Format.Format_RGBA8888)
    assert _image_bytes(before) != _image_bytes(after)


def test_fast_preview_selection_keeps_base_transform_geometry():
    _app()
    doc,layer,runtime=_fixture()
    canvas=PreviewCanvas()
    canvas.resize(640,360)
    canvas.set_document(doc)
    canvas.set_selected_layer(layer.layer_id)
    canvas.set_playhead(TIMEBASE)
    canvas.set_beat_runtime(runtime)
    base=canvas._rect_for_transform(canvas._canvas_rect(),layer.transform)
    geometry=canvas._selected_geometry()
    assert geometry is not None
    _selected,_track,rect,_handle=geometry
    assert rect == base


def test_fast_preview_zero_signal_returns_neutral_geometry():
    _app()
    doc,layer,runtime=_fixture()
    canvas=PreviewCanvas()
    canvas.resize(640,360)
    canvas.set_document(doc)
    canvas.set_playhead(0)
    canvas.set_beat_runtime(runtime)
    state=runtime.state_for_layer(layer.layer_id,0)
    assert state.scale_multiplier == 1.0
    assert state.zoom_multiplier == 1.0
    assert state.glow_amount == 0.0
