from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.visual_workspace_step06 import VisualInspector, VisualSongContext


def _app():
    return QApplication.instance() or QApplication([])


def _fixture(tmp_path: Path) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Visual UI")
    photo = tmp_path / "senja.png"
    photo.write_bytes(b"fixture-photo")
    video = tmp_path / "malam.mp4"
    video.write_bytes(b"fixture-video")
    image_asset = MediaAsset(kind="image", locator=str(photo), original_name=photo.name)
    video_asset = MediaAsset(kind="video", locator=str(video), original_name=video.name, source_duration_tick=12 * TIMEBASE)
    doc.media.extend([image_asset, video_asset])
    for index in range(6):
        audio_path = tmp_path / f"song-{index}.mp3"
        audio_path.write_bytes(b"fixture-audio")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=20 * TIMEBASE,
        )
        doc.media.append(audio)
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=("Senja di Kota Ini" if index == 0 else f"Lagu {index + 1}"),
            display_artist="Perjalanan Kita",
            source_out_tick=20 * TIMEBASE,
        )
        if index == 0:
            song.visual_asset_id = image_asset.asset_id
        elif index == 1:
            song.visual_asset_id = video_asset.asset_id
        doc.playlist.entries.append(song)
    doc.validate()
    return doc


def test_visual_context_filter_keeps_song_id_selection_stable(tmp_path: Path) -> None:
    _app()
    doc = _fixture(tmp_path)
    context = VisualSongContext()
    first = doc.playlist.entries[0].song_id
    second = doc.playlist.entries[1].song_id
    context.apply_document(doc)
    context.set_selection({first, second}, first)
    context.set_filter("video")
    assert context.primary_song_id == first
    assert context.selected_song_ids == {first, second}
    assert context.listing.count() == 1
    assert context.counts.text() == "Semua 6 • Kosong 4 • Foto 1 • Video 1"
    context.set_filter("all")
    assert context.selected_song_ids == {first, second}
    assert context.listing.count() == 6


def test_visual_inspector_enforces_video_only_playback_controls(tmp_path: Path) -> None:
    _app()
    doc = _fixture(tmp_path)
    inspector = VisualInspector()
    image_song = doc.playlist.entries[0].song_id
    video_song = doc.playlist.entries[1].song_id

    inspector.set_song(doc, image_song, 1)
    assert inspector.loop_video.isEnabled() is False
    assert inspector.freeze_end.isEnabled() is False

    inspector.set_song(doc, video_song, 2)
    assert inspector.loop_video.isEnabled() is True
    assert inspector.freeze_end.isEnabled() is True
    inspector.loop_video.setChecked(True)
    inspector.freeze_end.setChecked(True)
    assert inspector.freeze_end.isChecked() is True
    assert inspector.loop_video.isChecked() is False
    settings = inspector.settings()
    assert settings["freeze_end"] is True
    assert settings["loop_video"] is False
    assert inspector.apply_selected.text() == "Apply to Selected (2)"


def test_production_visual_route_uses_step06_surfaces_without_route_mutation(tmp_path: Path) -> None:
    # Importing full_album_maker.main installs app-wide compatibility layers by
    # design. Keep that production activation test in a fresh interpreter so the
    # installers cannot contaminate legacy tests collected in this pytest process.
    script = r'''
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import full_album_maker.main  # noqa: F401
from PySide6.QtWidgets import QApplication
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.foundation_window import FoundationMainWindow
from full_album_maker.visual_timeline_completion_step06 import TransitionVisualAlignmentCanvas

root = Path(sys.argv[1])
app = QApplication.instance() or QApplication([])
doc = ProjectDocument.new_empty("Visual Production Route")
photo = root / "route-photo.png"
photo.write_bytes(b"fixture-photo")
audio_path = root / "route-song.mp3"
audio_path.write_bytes(b"fixture-audio")
image = MediaAsset(kind="image", locator=str(photo), original_name=photo.name)
audio = MediaAsset(kind="audio", locator=str(audio_path), original_name=audio_path.name, source_duration_tick=20 * TIMEBASE)
doc.media.extend([image, audio])
song = SongInstance(asset_id=audio.asset_id, display_title="Senja di Kota Ini", source_out_tick=20 * TIMEBASE, visual_asset_id=image.asset_id)
doc.playlist.entries.append(song)
doc.validate()

window = FoundationMainWindow()
window._foundation_project_open = True
window.editor_workspace.set_document(doc)
signature = window.editor_workspace.document().content_signature()
window.foundation_shell.set_workspace("visual")
app.processEvents()

assert window.foundation_state.workspace == "visual"
assert window.foundation_shell.workspace_stack.currentWidget() is window.visual_workspace_s06
assert not window.visual_context_s06.isHidden()
assert window._inspector_router.currentWidget() is window.visual_inspector_s06
assert not window.visual_timeline_s06.isHidden()
assert isinstance(window.visual_timeline_s06, TransitionVisualAlignmentCanvas)
assert window._s06_primary_song_id == song.song_id
assert window.editor_workspace.document().content_signature() == signature
window.hide()
window.deleteLater()
app.processEvents()
print("STEP06_PRODUCTION_ROUTE_PASS")
'''
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "STEP06_PRODUCTION_ROUTE_PASS" in result.stdout
