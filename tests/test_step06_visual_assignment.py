from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.playlist_commands import SetSongVisual
from full_album_maker.visual_assignment import (
    RelinkMediaAsset,
    assignment_counts,
    assignment_status,
    deterministic_auto_match_commands,
    filtered_song_ids,
    validate_playback_eligibility,
)


def _document(tmp_path: Path) -> tuple[ProjectDocument, list[SongInstance], MediaAsset, MediaAsset, MediaAsset]:
    doc = ProjectDocument.new_empty("Visual STEP06")
    audio_assets = []
    songs = []
    for index in range(4):
        audio = MediaAsset(
            kind="audio",
            locator=str(tmp_path / f"lagu-{index}.mp3"),
            original_name=f"Lagu {index}.mp3",
            source_duration_tick=30 * TIMEBASE,
        )
        audio_assets.append(audio)
        songs.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index}",
                source_out_tick=30 * TIMEBASE,
            )
        )
    photo_path = tmp_path / "a-photo.png"
    photo_path.write_bytes(b"png-fixture")
    video_path = tmp_path / "b-video.mp4"
    video_path.write_bytes(b"video-fixture")
    missing_path = tmp_path / "missing-photo.png"
    photo = MediaAsset(kind="image", locator=str(photo_path), original_name=photo_path.name)
    video = MediaAsset(kind="video", locator=str(video_path), original_name=video_path.name, source_duration_tick=10 * TIMEBASE)
    missing = MediaAsset(kind="image", locator=str(missing_path), original_name=missing_path.name)
    doc.media.extend([*audio_assets, photo, video, missing])
    doc.playlist.entries.extend(songs)
    songs[0].visual_asset_id = photo.asset_id
    songs[1].visual_asset_id = video.asset_id
    songs[2].visual_asset_id = missing.asset_id
    doc.validate()
    return doc, songs, photo, video, missing


def test_assignment_status_counts_and_filter_are_model_driven(tmp_path: Path) -> None:
    doc, songs, photo, video, missing = _document(tmp_path)
    assert assignment_status(doc, songs[0].song_id).state == "image"
    assert assignment_status(doc, songs[1].song_id).state == "video"
    missing_status = assignment_status(doc, songs[2].song_id)
    assert missing_status.state == "missing"
    assert missing_status.source_kind == "image"
    assert assignment_status(doc, songs[3].song_id).state == "empty"
    assert assignment_counts(doc) == {"all": 4, "empty": 1, "image": 1, "video": 1, "missing": 1}
    assert filtered_song_ids(doc, "image") == (songs[0].song_id,)
    assert filtered_song_ids(doc, "missing") == (songs[2].song_id,)


def test_clear_visual_is_undoable_and_never_deletes_media(tmp_path: Path) -> None:
    doc, songs, photo, _video, _missing = _document(tmp_path)
    controller = EditorController(doc)
    before_assets = set(doc.asset_map())
    controller.dispatch(SetSongVisual(songs[0].song_id, None))
    active = controller.snapshot()
    assert active.song_map()[songs[0].song_id].visual_asset_id is None
    assert set(active.asset_map()) == before_assets
    assert photo.asset_id in active.asset_map()
    restored = controller.undo()
    assert restored.song_map()[songs[0].song_id].visual_asset_id == photo.asset_id


def test_relink_preserves_asset_identity_and_is_undoable(tmp_path: Path) -> None:
    doc, songs, _photo, _video, missing = _document(tmp_path)
    replacement = tmp_path / "replacement.png"
    replacement.write_bytes(b"replacement")
    old_locator = missing.locator
    controller = EditorController(doc)
    controller.dispatch(RelinkMediaAsset(missing.asset_id, str(replacement)))
    active = controller.snapshot()
    assert active.song_map()[songs[2].song_id].visual_asset_id == missing.asset_id
    assert active.asset_map()[missing.asset_id].locator == str(replacement)
    assert assignment_status(active, songs[2].song_id).state == "image"
    restored = controller.undo()
    assert restored.asset_map()[missing.asset_id].locator == old_locator
    assert assignment_status(restored, songs[2].song_id).state == "missing"


def test_auto_match_is_deterministic_and_preserves_existing(tmp_path: Path) -> None:
    doc, songs, photo, video, _missing = _document(tmp_path)
    commands = deterministic_auto_match_commands(doc, [song.song_id for song in songs])
    assert len(commands) == 1
    assert commands[0].song_id == songs[3].song_id
    assert commands[0].asset_id == photo.asset_id
    again = deterministic_auto_match_commands(doc, [song.song_id for song in songs])
    assert [(c.song_id, c.asset_id) for c in commands] == [(c.song_id, c.asset_id) for c in again]
    assert songs[0].visual_asset_id == photo.asset_id
    assert songs[1].visual_asset_id == video.asset_id


def test_loop_and_freeze_are_video_only(tmp_path: Path) -> None:
    doc, songs, _photo, _video, _missing = _document(tmp_path)
    validate_playback_eligibility(doc, songs[1].song_id, loop_video=True, freeze_end=False)
    with pytest.raises(Exception, match="hanya tersedia untuk sumber Video"):
        validate_playback_eligibility(doc, songs[0].song_id, loop_video=True, freeze_end=False)
    with pytest.raises(Exception, match="tidak boleh aktif bersamaan"):
        validate_playback_eligibility(doc, songs[1].song_id, loop_video=True, freeze_end=True)
