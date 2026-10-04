from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.song_visuals import make_song_visual_layer
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.timeline_resolver import TimelineResolver
from full_album_maker.visual_precision import (
    SetSongVideoSpeed,
    SetSongVisualSettings,
    ApplySongVisualSettings,
    visual_settings_for_song,
)


def _document(tmp_path: Path, *, second_kind: str = "video") -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP09 Slowmo Contract")
    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    doc.layers.append(make_song_visual_layer(visual_track.track_id, order=0))

    for index, kind in enumerate(("video", second_kind)):
        audio = MediaAsset(
            kind="audio",
            locator=str(tmp_path / f"song-{index}.wav"),
            original_name=f"song-{index}.wav",
            source_duration_tick=12 * TIMEBASE,
        )
        visual = MediaAsset(
            kind=kind,
            locator=str(tmp_path / (f"visual-{index}.mp4" if kind == "video" else f"visual-{index}.png")),
            original_name=(f"visual-{index}.mp4" if kind == "video" else f"visual-{index}.png"),
            source_duration_tick=6 * TIMEBASE if kind == "video" else 0,
        )
        doc.media.extend([audio, visual])
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index + 1}",
                source_out_tick=12 * TIMEBASE,
                visual_asset_id=visual.asset_id,
            )
        )
    doc.validate()
    return doc


def _graph(compiled) -> str:
    args = list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex") + 1]
    if "-/filter_complex" in args:
        return Path(args[args.index("-/filter_complex") + 1]).read_text(encoding="utf-8")
    raise AssertionError("filter graph missing")


def test_slowmo_is_visual_only_persisted_and_one_undo(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    ids = [song.song_id for song in doc.playlist.entries]
    controller = EditorController(doc)
    before = controller.snapshot()
    before_timeline = TimelineResolver().resolve(before)

    changed = controller.dispatch(SetSongVideoSpeed(ids, 0.5))
    assert changed.revision == doc.revision + 1
    assert visual_settings_for_song(changed, ids[0])["video_speed"] == pytest.approx(0.5)
    assert visual_settings_for_song(changed, ids[1])["video_speed"] == pytest.approx(0.5)

    after_timeline = TimelineResolver().resolve(changed)
    assert [(x.song_id, x.start_tick, x.end_tick) for x in after_timeline.songs] == [
        (x.song_id, x.start_tick, x.end_tick) for x in before_timeline.songs
    ]
    assert [(song.source_in_tick, song.source_out_tick) for song in changed.playlist.entries] == [
        (song.source_in_tick, song.source_out_tick) for song in before.playlist.entries
    ]

    restored = controller.undo()
    assert restored.content_signature() == before.content_signature()
    redone = controller.redo()
    assert visual_settings_for_song(redone, ids[0])["video_speed"] == pytest.approx(0.5)


def test_mixed_image_video_slowmo_fails_before_mutation(tmp_path: Path) -> None:
    doc = _document(tmp_path, second_kind="image")
    ids = [song.song_id for song in doc.playlist.entries]
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    with pytest.raises(Exception, match="sumber Video"):
        controller.dispatch(SetSongVideoSpeed(ids, 0.5))
    assert controller.snapshot().content_signature() == before
    assert controller.revision == doc.revision


def test_visual_edit_payload_without_speed_preserves_existing_slowmo(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    ids = [song.song_id for song in doc.playlist.entries]
    controller = EditorController(doc)
    controller.dispatch(SetSongVideoSpeed(ids, 0.5))
    current = controller.snapshot()

    controller.dispatch(
        SetSongVisualSettings(
            ids[0],
            {
                "fit": "fill",
                "transition": "fade",
                "transition_seconds": 1.0,
            },
        )
    )
    current = controller.snapshot()
    assert visual_settings_for_song(current, ids[0])["video_speed"] == pytest.approx(0.5)

    controller.dispatch(
        ApplySongVisualSettings(
            ids,
            {
                "fit": "fit",
                "transition": "cut",
            },
        )
    )
    current = controller.snapshot()
    assert all(
        visual_settings_for_song(current, song_id)["video_speed"] == pytest.approx(0.5)
        for song_id in ids
    )


def test_slowmo_roundtrip_uses_existing_project_extensions_schema(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    changed = controller.dispatch(SetSongVideoSpeed((song_id,), 0.5))
    reopened = ProjectDocument.from_dict(changed.to_dict())
    assert reopened.schema_version == changed.schema_version
    assert visual_settings_for_song(reopened, song_id)["video_speed"] == pytest.approx(0.5)


def test_renderer_applies_video_setpts_but_keeps_audio_plan_timing(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    song_id = doc.playlist.entries[0].song_id
    controller = EditorController(doc)
    before = controller.snapshot()
    normal = Step08FFmpegCompiler("ffmpeg").compile_video(
        before, tmp_path / "normal.mp4", tmp_path / "normal-work"
    )
    changed = controller.dispatch(SetSongVideoSpeed((song_id,), 0.5))
    slow = Step08FFmpegCompiler("ffmpeg").compile_video(
        changed, tmp_path / "slow.mp4", tmp_path / "slow-work"
    )

    graph = _graph(slow)
    assert "setpts=PTS/0.50000000" in graph
    assert "atempo=0.5" not in graph
    assert "atempo=0.50000000" not in graph
    assert slow.render_plan.duration_tick == normal.render_plan.duration_tick
    assert [
        (event.song_id, event.start_tick, event.end_tick)
        for event in slow.render_plan.audio_events
    ] == [
        (event.song_id, event.start_tick, event.end_tick)
        for event in normal.render_plan.audio_events
    ]


def test_video_speed_bounds_are_explicit(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    song_id = doc.playlist.entries[0].song_id
    for speed in (0.0, 0.1, 4.1, 8.0):
        controller = EditorController(doc)
        with pytest.raises(Exception, match="0.25x..4x"):
            controller.dispatch(SetSongVideoSpeed((song_id,), speed))
