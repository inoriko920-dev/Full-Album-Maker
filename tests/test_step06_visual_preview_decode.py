from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.media_preview_cache import PreviewResult
from full_album_maker.visual_preview_decode_step06 import (
    DecodedVisualPreviewCanvas,
    DecodedVisualPreviewWorkspace,
    install_step06_visual_preview_decode,
)


def _app():
    return QApplication.instance() or QApplication([])


def _document(tmp_path: Path) -> tuple[ProjectDocument, str, str, str, str]:
    doc = ProjectDocument.new_empty("Preview Guard")
    song_ids = []
    video_ids = []
    for index in range(2):
        audio_path = tmp_path / f"audio-{index}.mp3"
        video_path = tmp_path / f"video-{index}.mp4"
        audio_path.write_bytes(b"audio")
        video_path.write_bytes(b"video")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=10 * TIMEBASE,
        )
        video = MediaAsset(
            kind="video",
            locator=str(video_path),
            original_name=video_path.name,
            source_duration_tick=5 * TIMEBASE,
        )
        doc.media.extend([audio, video])
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=f"Song {index + 1}",
            source_out_tick=10 * TIMEBASE,
            visual_asset_id=video.asset_id,
        )
        doc.playlist.entries.append(song)
        song_ids.append(song.song_id)
        video_ids.append(video.asset_id)
    doc.validate()
    return doc, song_ids[0], song_ids[1], video_ids[0], video_ids[1]


def test_selection_change_invalidates_older_video_preview_result(tmp_path: Path) -> None:
    _app()
    install_step06_visual_preview_decode()
    doc, song_a, song_b, video_a, video_b = _document(tmp_path)
    workspace = DecodedVisualPreviewWorkspace()
    # This test validates request identity/generation only. Actual decoder execution
    # is covered by recovered MediaPreviewCache tests and portable FFmpeg gates.
    workspace.preview_cache.request = lambda _asset: True

    workspace.apply_state(doc, song_a, 0)
    generation_a = workspace.preview_cache.generation
    assert workspace._requested_asset_id == video_a
    assert isinstance(workspace.preview, DecodedVisualPreviewCanvas)

    workspace.apply_state(doc, song_b, 10 * TIMEBASE)
    generation_b = workspace.preview_cache.generation
    assert generation_b > generation_a
    assert workspace._requested_asset_id == video_b

    stale = PreviewResult(asset_id=video_a, path="old-frame.png", generation=generation_a)
    assert workspace.accepts_preview_result(stale) is False


def test_current_generation_result_is_applied_to_matching_video(tmp_path: Path) -> None:
    _app()
    install_step06_visual_preview_decode()
    doc, _song_a, song_b, _video_a, video_b = _document(tmp_path)
    workspace = DecodedVisualPreviewWorkspace()
    workspace.preview_cache.request = lambda _asset: True
    workspace.apply_state(doc, song_b, 10 * TIMEBASE)

    frame_path = tmp_path / "decoded.png"
    frame = QImage(640, 360, QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(QColor("#4477AA"))
    assert frame.save(str(frame_path), "PNG")

    result = PreviewResult(
        asset_id=video_b,
        path=str(frame_path),
        generation=workspace.preview_cache.generation,
    )
    assert workspace.accepts_preview_result(result) is True
    workspace._preview_ready(result)
    assert workspace.preview.decoded_asset_id == video_b
