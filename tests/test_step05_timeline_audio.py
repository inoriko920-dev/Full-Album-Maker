from __future__ import annotations

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.timeline_audio_commands import SetSongDuration, SplitSongAtTick
from full_album_maker.timeline_precision import SetSongMix, song_mix
from full_album_maker.timeline_resolver import TimelineResolver


def _document(mode: str = "free") -> ProjectDocument:
    doc = ProjectDocument.new_empty("Timeline Audio")
    audio = MediaAsset(
        kind="audio",
        locator="/tmp/lagu.mp3",
        original_name="lagu.mp3",
        source_duration_tick=20 * TIMEBASE,
    )
    doc.media.append(audio)
    song = SongInstance(
        asset_id=audio.asset_id,
        display_title="Lagu Utama",
        source_out_tick=20 * TIMEBASE,
    )
    if mode == "free":
        song.free_start_tick = 2 * TIMEBASE
    doc.playlist.mode = mode
    doc.playlist.entries.append(song)
    doc.validate()
    return doc


def test_set_song_duration_is_undoable_and_preserves_free_start():
    doc = _document()
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    controller.dispatch(SetSongDuration(song_id, 12 * TIMEBASE))
    current = controller.snapshot().song_map()[song_id]
    assert current.source_out_tick == 12 * TIMEBASE
    assert current.free_start_tick == 2 * TIMEBASE
    controller.undo()
    assert controller.snapshot().song_map()[song_id].source_out_tick == 20 * TIMEBASE


def test_split_song_free_keeps_total_resolved_span_and_is_one_undo():
    doc = _document()
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    controller.dispatch(SetSongMix(song_id, 0.8, TIMEBASE, 2 * TIMEBASE, True))
    # unlock before the split so the command is allowed, still exercising mix copy.
    controller.dispatch(SetSongMix(song_id, 0.8, TIMEBASE, 2 * TIMEBASE, False))
    before = controller.snapshot()
    before_span = TimelineResolver().resolve(before).duration_tick
    command = SplitSongAtTick(song_id, 10 * TIMEBASE)
    controller.dispatch(command)
    after = controller.snapshot()
    assert len(after.playlist.entries) == 2
    first, second = after.playlist.entries
    assert first.source_out_tick == 8 * TIMEBASE
    assert second.source_in_tick == 8 * TIMEBASE
    assert second.free_start_tick == 10 * TIMEBASE
    assert second.song_id == command.new_song_id
    assert TimelineResolver().resolve(after).duration_tick == before_span
    assert song_mix(after, second.song_id)["locked"] is False
    controller.undo()
    restored = controller.snapshot()
    assert len(restored.playlist.entries) == 1
    assert restored.playlist.entries[0].source_out_tick == 20 * TIMEBASE


def test_split_song_packed_stays_contiguous():
    doc = _document("packed")
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    controller.dispatch(SplitSongAtTick(song_id, 7 * TIMEBASE))
    after = controller.snapshot()
    assert len(after.playlist.entries) == 2
    resolved = TimelineResolver().resolve(after)
    assert not resolved.errors
    assert resolved.songs[0].end_tick == resolved.songs[1].start_tick
    assert resolved.duration_tick == 20 * TIMEBASE
