from __future__ import annotations

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, seconds_to_tick
from full_album_maker.song_visuals import make_song_visual_layer, normalize_song_visual_properties
from full_album_maker.v13_render_graph import V13FFmpegCompiler
from full_album_maker.visual_precision import (
    ApplySongVisualSettings,
    SetSongVisualSettings,
    normalize_song_visual_settings,
    visual_settings_for_song,
)


def _document() -> tuple[ProjectDocument, SongInstance, SongInstance]:
    doc = ProjectDocument.new_empty("STEP06 Visual")
    duration = seconds_to_tick(12)
    audio_a = MediaAsset(
        kind="audio",
        locator="song-a.wav",
        original_name="Song A.wav",
        source_duration_tick=duration,
    )
    audio_b = MediaAsset(
        kind="audio",
        locator="song-b.wav",
        original_name="Song B.wav",
        source_duration_tick=duration,
    )
    image = MediaAsset(
        kind="image",
        locator="visual-a.png",
        original_name="Visual A.png",
    )
    video = MediaAsset(
        kind="video",
        locator="visual-b.mp4",
        original_name="Visual B.mp4",
        source_duration_tick=seconds_to_tick(4),
    )
    doc.media.extend([audio_a, audio_b, image, video])
    song_a = SongInstance(
        asset_id=audio_a.asset_id,
        display_title="Song A",
        source_out_tick=duration,
        visual_asset_id=image.asset_id,
    )
    song_b = SongInstance(
        asset_id=audio_b.asset_id,
        display_title="Song B",
        source_out_tick=duration,
        visual_asset_id=video.asset_id,
    )
    doc.playlist.entries.extend([song_a, song_b])
    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    layer = make_song_visual_layer(visual_track.track_id, 5)
    layer.properties = normalize_song_visual_properties(
        {
            "fit": "fill",
            "image_motion": "zoom_in",
            "video_playback": "loop",
            "transition": "fade",
            "transition_seconds": 0.8,
        }
    )
    doc.layers.append(layer)
    doc.validate()
    return doc, song_a, song_b


def _graph(compiled) -> str:
    args = list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex") + 1]
    from pathlib import Path

    return Path(args[args.index("-/filter_complex") + 1]).read_text(encoding="utf-8")


def test_visual_settings_validate_non_destructive_geometry_and_policies():
    props = normalize_song_visual_settings(
        {
            "fit": "fit",
            "crop_x": 0.10,
            "crop_y": 0.05,
            "crop_width": 0.80,
            "crop_height": 0.90,
            "position_x": 0.12,
            "position_y": -0.08,
            "scale": 1.25,
            "pan_zoom": True,
            "image_motion": "ken_burns",
            "loop_video": False,
            "freeze_end": True,
            "transition": "slide",
            "transition_seconds": 1.0,
        }
    )
    assert props["fit"] == "fit"
    assert props["crop_width"] == 0.8
    assert props["image_motion"] == "ken_burns"
    assert props["freeze_end"] is True
    assert props["video_playback"] == "freeze"
    assert props["transition"] == "slide"

    import pytest

    with pytest.raises(ValueError, match="melewati"):
        normalize_song_visual_settings({"crop_x": 0.5, "crop_width": 0.8})
    with pytest.raises(ValueError, match="tidak boleh aktif bersamaan"):
        normalize_song_visual_settings({"loop_video": True, "freeze_end": True})
    with pytest.raises(ValueError, match="Skala"):
        normalize_song_visual_settings({"scale": 9})


def test_apply_selected_is_one_revision_undoable_and_roundtrips():
    doc, song_a, song_b = _document()
    controller = EditorController(doc)
    settings = {
        "fit": "fill",
        "crop_x": 0.05,
        "crop_y": 0.05,
        "crop_width": 0.90,
        "crop_height": 0.90,
        "position_x": 0.1,
        "position_y": 0.0,
        "scale": 1.15,
        "pan_zoom": True,
        "image_motion": "pan_left",
        "loop_video": True,
        "freeze_end": False,
        "transition": "fade",
        "transition_seconds": 1.0,
    }
    start_revision = controller.revision
    controller.dispatch(ApplySongVisualSettings([song_a.song_id, song_b.song_id], settings))
    assert controller.revision == start_revision + 1
    changed = controller.snapshot()
    assert visual_settings_for_song(changed, song_a.song_id)["scale"] == 1.15
    assert visual_settings_for_song(changed, song_b.song_id)["crop_width"] == 0.9

    restored = ProjectDocument.from_dict(changed.to_dict())
    assert visual_settings_for_song(restored, song_a.song_id)["position_x"] == 0.1
    assert visual_settings_for_song(restored, song_b.song_id)["transition_seconds"] == 1.0

    controller.undo()
    reverted = controller.snapshot()
    assert "song_visual_settings_v1" not in reverted.extensions


def test_legacy_layer_properties_remain_fallback_without_rewrite():
    doc, song_a, _ = _document()
    layer = next(item for item in doc.layers if item.type == "song_visual")
    layer.properties = normalize_song_visual_properties(
        {
            "fit": "fit",
            "image_motion": "pan_right",
            "video_playback": "freeze",
            "transition": "slide_right",
            "transition_seconds": 0.7,
        }
    )
    before = doc.content_signature()
    props = visual_settings_for_song(doc, song_a.song_id)
    assert props["fit"] == "fit"
    assert props["image_motion"] == "pan_right"
    assert props["freeze_end"] is True
    assert props["loop_video"] is False
    assert props["transition"] == "slide_right"
    assert doc.content_signature() == before


def test_renderer_consumes_per_song_crop_scale_motion_freeze_and_transition(tmp_path):
    doc, song_a, song_b = _document()
    controller = EditorController(doc)
    controller.dispatch(
        SetSongVisualSettings(
            song_a.song_id,
            {
                "fit": "fill",
                "crop_x": 0.10,
                "crop_y": 0.10,
                "crop_width": 0.80,
                "crop_height": 0.80,
                "position_x": 0.10,
                "position_y": -0.05,
                "scale": 1.20,
                "pan_zoom": True,
                "image_motion": "ken_burns",
                "loop_video": True,
                "freeze_end": False,
                "transition": "slide",
                "transition_seconds": 1.0,
            },
        )
    )
    controller.dispatch(
        SetSongVisualSettings(
            song_b.song_id,
            {
                "fit": "fit",
                "crop_x": 0.0,
                "crop_y": 0.0,
                "crop_width": 1.0,
                "crop_height": 1.0,
                "position_x": 0.0,
                "position_y": 0.0,
                "scale": 1.0,
                "pan_zoom": False,
                "image_motion": "static",
                "loop_video": False,
                "freeze_end": True,
                "transition": "fade",
                "transition_seconds": 0.5,
            },
        )
    )
    compiled = V13FFmpegCompiler("ffmpeg").compile_video(
        controller.snapshot(), tmp_path / "visual.mp4", tmp_path / "work"
    )
    graph = _graph(compiled)
    assert "crop=w=iw*0.80000000:h=ih*0.80000000" in graph
    assert "zoompan=z='min(1.10" in graph
    assert "overlay=x='if(lt(t," in graph
    assert "tpad=stop_mode=clone" in graph
    assert "trim=end_frame=1" not in graph
    assert "fade=t=in" in graph
    assert "1.20000000" in graph or "2304" in graph
