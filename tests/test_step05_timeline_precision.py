from __future__ import annotations

import pytest

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TimeBinding, TIMEBASE
from full_album_maker.timeline_precision import (
    AddTimelineMarker,
    DeleteGapAtTick,
    RippleMoveSong,
    SetSongMix,
    SplitLayerAtTick,
    song_mix,
    timeline_gaps,
    timeline_markers,
)


def _document() -> ProjectDocument:
    doc = ProjectDocument.new_empty("Timeline STEP05")
    audio_track = next(track for track in doc.tracks if track.kind == "audio")
    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    for index in range(3):
        audio = MediaAsset(
            kind="audio",
            locator=f"/tmp/song-{index + 1}.mp3",
            original_name=f"song-{index + 1}.mp3",
            source_duration_tick=10 * TIMEBASE,
        )
        doc.media.append(audio)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Song {index + 1}",
                source_out_tick=10 * TIMEBASE,
            )
        )
    doc.layers.append(
        Layer(
            track_id=visual_track.track_id,
            type="text",
            name="Title",
            time_binding=TimeBinding(kind="absolute", start_tick=0, duration_tick=8 * TIMEBASE),
        )
    )
    doc.validate()
    return doc


def _free_with_gap() -> ProjectDocument:
    doc = _document()
    doc.playlist.mode = "free"
    starts = (0, 12 * TIMEBASE, 22 * TIMEBASE)
    for song, start in zip(doc.playlist.entries, starts):
        song.free_start_tick = start
    doc.validate()
    return doc


def test_marker_persists_and_undoes():
    controller = EditorController(_document())
    command = AddTimelineMarker(3 * TIMEBASE, "Intro", "#1766E8")
    controller.dispatch(command)
    markers = timeline_markers(controller.snapshot())
    assert len(markers) == 1
    assert markers[0].label == "Intro"
    assert markers[0].tick == 3 * TIMEBASE
    restored = ProjectDocument.from_dict(controller.snapshot().to_dict())
    assert timeline_markers(restored)[0].label == "Intro"
    controller.undo()
    assert timeline_markers(controller.snapshot()) == ()
    controller.redo()
    assert timeline_markers(controller.snapshot())[0].marker_id == command.marker_id


def test_song_mix_is_persisted_and_atomic_undo():
    doc = _document()
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    controller.dispatch(SetSongMix(song_id, 0.75, TIMEBASE, 2 * TIMEBASE, True))
    current = controller.snapshot()
    assert current.song_map()[song_id].gain == pytest.approx(0.75)
    assert song_mix(current, song_id) == {
        "fade_in_tick": TIMEBASE,
        "fade_out_tick": 2 * TIMEBASE,
        "locked": True,
    }
    reopened = ProjectDocument.from_dict(current.to_dict())
    assert song_mix(reopened, song_id)["locked"] is True
    controller.undo()
    previous = controller.snapshot()
    assert previous.song_map()[song_id].gain == pytest.approx(1.0)
    assert song_mix(previous, song_id)["fade_in_tick"] == 0


def test_delete_gap_shifts_downstream_once_and_undoes():
    controller = EditorController(_free_with_gap())
    before = controller.snapshot()
    gap = timeline_gaps(before)[0]
    assert gap.duration_tick == 2 * TIMEBASE
    controller.dispatch(DeleteGapAtTick(gap.start_tick + TIMEBASE))
    after = controller.snapshot()
    starts = [song.free_start_tick for song in after.playlist.entries]
    assert starts == [0, 10 * TIMEBASE, 20 * TIMEBASE]
    assert timeline_gaps(after) == ()
    controller.undo()
    assert [song.free_start_tick for song in controller.snapshot().playlist.entries] == [
        0,
        12 * TIMEBASE,
        22 * TIMEBASE,
    ]


def test_ripple_move_moves_selected_and_downstream_as_one_transaction():
    doc = _free_with_gap()
    second_id = doc.playlist.entries[1].song_id
    controller = EditorController(doc)
    controller.dispatch(RippleMoveSong(second_id, 14 * TIMEBASE))
    assert [song.free_start_tick for song in controller.snapshot().playlist.entries] == [
        0,
        14 * TIMEBASE,
        24 * TIMEBASE,
    ]
    controller.undo()
    assert [song.free_start_tick for song in controller.snapshot().playlist.entries] == [
        0,
        12 * TIMEBASE,
        22 * TIMEBASE,
    ]


def test_split_absolute_layer_at_playhead_and_undo():
    doc = _document()
    layer_id = doc.layers[0].layer_id
    controller = EditorController(doc)
    command = SplitLayerAtTick(layer_id, 3 * TIMEBASE)
    controller.dispatch(command)
    after = controller.snapshot()
    assert len(after.layers) == 2
    first, second = after.layers
    assert first.time_binding.duration_tick == 3 * TIMEBASE
    assert second.layer_id == command.new_layer_id
    assert second.time_binding.start_tick == 3 * TIMEBASE
    assert second.time_binding.duration_tick == 5 * TIMEBASE
    controller.undo()
    restored = controller.snapshot()
    assert len(restored.layers) == 1
    assert restored.layers[0].time_binding.duration_tick == 8 * TIMEBASE
