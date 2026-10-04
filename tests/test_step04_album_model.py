from __future__ import annotations

from full_album_maker.album_commands import SetAlbumDefaultTransition, SetSongTransition
from full_album_maker.album_model import (
    album_duration_text,
    move_selection_to_edge,
    page_rows,
    rows,
    safe_cover_matches,
    song_transition,
    summary,
)
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.playlist_commands import SetSongCover, SetSongVisual


def make_document(count: int = 100) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Perjalanan Kita")
    doc.album_title = "Perjalanan Kita"
    cover = MediaAsset(kind="image", locator="/tmp/Senja di Kota Ini.png", original_name="Senja di Kota Ini.png")
    visual = MediaAsset(kind="video", locator="/tmp/visual.mp4", original_name="visual.mp4", source_duration_tick=30 * TIMEBASE)
    doc.media.extend([cover, visual])
    for index in range(count):
        title = "Senja di Kota Ini" if index == 0 else f"Lagu {index + 1:03d}"
        audio = MediaAsset(
            kind="audio",
            locator=f"/tmp/{title}.mp3",
            original_name=f"{title}.mp3",
            source_duration_tick=(180 + index) * TIMEBASE,
            metadata={"title": title},
        )
        doc.media.append(audio)
        # Golden fixture contract: 12 without cover, 18 without visual, and
        # exactly six review rows (missing cover while a visual is already set).
        cover_id = cover.asset_id if index >= 12 else None
        visual_id = None if 6 <= index < 24 else visual.asset_id
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                source_out_tick=audio.source_duration_tick,
                cover_asset_id=cover_id,
                visual_asset_id=visual_id,
            )
        )
    doc.validate()
    return doc


def test_100_song_album_is_paged_and_counts_are_live():
    doc = make_document(100)
    info = summary(doc)
    assert info.song_count == 100
    assert info.missing_cover == 12
    assert info.missing_visual == 18
    assert info.needs_review == 6
    first, pages = page_rows(doc, "all", 1)
    last, last_pages = page_rows(doc, "all", 10)
    assert pages == last_pages == 10
    assert len(first) == len(last) == 10
    assert first[0].position == 1
    assert last[-1].position == 100
    assert album_duration_text(info.duration_seconds)


def test_statuses_come_from_actual_cover_and_visual_state():
    doc = make_document(30)
    values = rows(doc)
    assert values[0].status == "Perlu Ditinjau"
    assert values[5].status == "Perlu Ditinjau"
    assert values[6].status == "Belum Ada Visual"
    assert values[23].status == "Belum Ada Visual"
    assert values[24].status == "Siap"
    review = rows(doc, "review")
    assert len(review) == 6
    assert all(item.status == "Perlu Ditinjau" for item in review)


def test_safe_cover_match_never_guesses_ambiguous_candidates():
    doc = make_document(2)
    first = doc.playlist.entries[0]
    matches = safe_cover_matches(doc, {first.song_id})
    assert matches[first.song_id]
    duplicate = MediaAsset(kind="image", locator="/tmp/Senja-di-Kota-Ini.jpg", original_name="Senja-di-Kota-Ini.jpg")
    doc.media.append(duplicate)
    doc.validate()
    assert first.song_id not in safe_cover_matches(doc, {first.song_id})


def test_bulk_cover_visual_and_transition_are_one_undoable_transaction():
    doc = make_document(4)
    controller = EditorController(doc)
    snapshot = controller.snapshot()
    songs = snapshot.playlist.entries[:2]
    image_id = next(asset.asset_id for asset in snapshot.media if asset.kind == "image")
    video_id = next(asset.asset_id for asset in snapshot.media if asset.kind == "video")
    commands = [SetAlbumDefaultTransition("zoom", 1.5)]
    for song in songs:
        commands.extend(
            [
                SetSongCover(song.song_id, image_id),
                SetSongVisual(song.song_id, video_id),
                SetSongTransition(song.song_id, "zoom", 1.5),
            ]
        )
    controller.dispatch(commands)
    changed = controller.snapshot()
    assert controller.can_undo
    for song in changed.playlist.entries[:2]:
        assert song.cover_asset_id == image_id
        assert song.visual_asset_id == video_id
        assert song_transition(changed, song.song_id).kind == "zoom"
    controller.undo()
    restored = controller.snapshot()
    assert restored.content_signature() == doc.content_signature()
    controller.redo()
    redone = controller.snapshot()
    assert redone.content_signature() == changed.content_signature()


def test_move_selected_to_top_and_bottom_preserves_relative_order():
    doc = make_document(8)
    ids = [song.song_id for song in doc.playlist.entries]
    selected = {ids[2], ids[5]}
    assert move_selection_to_edge(doc, selected, top=True)[:2] == [ids[2], ids[5]]
    assert move_selection_to_edge(doc, selected, top=False)[-2:] == [ids[2], ids[5]]
