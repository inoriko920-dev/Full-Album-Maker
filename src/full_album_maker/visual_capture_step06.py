from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


def _fixture_document(root: Path):
    from PySide6.QtGui import QColor, QImage

    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
    from .visual_precision import SetSongVisualSettings

    document = ProjectDocument.new_empty("Perjalanan Kita")
    document.album_title = "Perjalanan Kita"

    image_assets: list[MediaAsset] = []
    for index, color in enumerate(("#E9986A", "#6FA9D8"), start=1):
        path = root / f"visual-foto-{index}.png"
        image = QImage(1280, 720, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(color))
        if not image.save(str(path), "PNG"):
            raise RuntimeError("Gagal membuat fixture gambar STEP06.")
        asset = MediaAsset(kind="image", locator=str(path), original_name=path.name)
        image_assets.append(asset)
        document.media.append(asset)

    video_assets: list[MediaAsset] = []
    for index in range(2):
        path = root / f"visual-video-{index + 1}.mp4"
        path.write_bytes(b"STEP06 deterministic video placeholder")
        asset = MediaAsset(
            kind="video",
            locator=str(path),
            original_name=path.name,
            source_duration_tick=(12 + index * 3) * TIMEBASE,
        )
        video_assets.append(asset)
        document.media.append(asset)

    missing_asset = MediaAsset(
        kind="image",
        locator=str(root / "visual-missing.png"),
        original_name="visual-missing.png",
    )
    document.media.append(missing_asset)

    titles = (
        "Senja di Kota Ini",
        "Langit Setelah Hujan",
        "Kembali Pulang",
        "Jalan yang Sama",
        "Malam Tanpa Batas",
        "Sampai Kita Bertemu",
    )
    assignments = (
        image_assets[0].asset_id,
        video_assets[0].asset_id,
        None,
        image_assets[1].asset_id,
        video_assets[1].asset_id,
        missing_asset.asset_id,
    )
    for index, title in enumerate(titles):
        audio_path = root / f"lagu-{index + 1}.mp3"
        audio_path.write_bytes(b"STEP06 deterministic audio placeholder")
        duration = 24 + index * 2
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=duration * TIMEBASE,
            metadata={"title": title, "artist": "Perjalanan Kita"},
        )
        document.media.append(audio)
        document.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                display_artist="Perjalanan Kita",
                source_out_tick=duration * TIMEBASE,
                visual_asset_id=assignments[index],
            )
        )

    first = document.playlist.entries[0].song_id
    SetSongVisualSettings(
        first,
        {
            "fit": "fill",
            "crop_x": 0.04,
            "crop_y": 0.03,
            "crop_width": 0.92,
            "crop_height": 0.90,
            "position_x": 0.08,
            "position_y": -0.04,
            "scale": 1.08,
            "pan_zoom": True,
            "image_motion": "ken_burns",
            "loop_video": False,
            "freeze_end": False,
            "transition": "fade",
            "transition_seconds": 1.2,
        },
    ).apply(document)
    SetSongVisualSettings(
        document.playlist.entries[1].song_id,
        {
            "fit": "fill",
            "pan_zoom": False,
            "image_motion": "static",
            "loop_video": True,
            "freeze_end": False,
            "transition": "slide_left",
            "transition_seconds": 0.8,
        },
    ).apply(document)
    SetSongVisualSettings(
        document.playlist.entries[4].song_id,
        {
            "fit": "fit",
            "pan_zoom": False,
            "image_motion": "static",
            "loop_video": False,
            "freeze_end": True,
            "transition": "fade",
            "transition_seconds": 1.0,
        },
    ).apply(document)
    document.validate()
    return document


def capture(output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    _prepare_qt(scale)

    # Install the real STEP01..06 presentation layers before creating the window.
    import full_album_maker.main  # noqa: F401

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .visual_assignment import assignment_counts, assignment_status
    from .visual_precision import visual_settings_for_song

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    fixture_root = Path(tempfile.mkdtemp(prefix="fam-step06-visual-"))
    document = _fixture_document(fixture_root)

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    signature_before_route = window.editor_workspace.document().content_signature()
    first = document.playlist.entries[0].song_id
    window._s06_primary_song_id = first
    window._s06_selected_ids = {first}
    window.editor_workspace.set_playhead(8 * document.timebase)
    window.foundation_shell.set_workspace("visual")
    window._s06_refresh()
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()
    app.processEvents()

    live_document = window.editor_workspace.document()
    signature_after_route = live_document.content_signature()
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot STEP06 Visual: {output}")

    shell = window.foundation_shell
    status = assignment_status(live_document, first)
    settings = visual_settings_for_song(live_document, first)
    counts = assignment_counts(live_document)
    geometry = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "visual_active": shell.workspace_stack.currentWidget() is window.visual_workspace_s06,
        "context_visible": not window.visual_context_s06.isHidden(),
        "inspector_active": window._inspector_router.currentWidget() is window.visual_inspector_s06,
        "timeline_visible": not window.visual_timeline_s06.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "song_rows": window.visual_context_s06.listing.count(),
        "song_count": len(live_document.playlist.entries),
        "selected_count": len(window.visual_context_s06.selected_song_ids),
        "primary_song": live_document.song_map()[first].display_title,
        "primary_state": status.state,
        "counts": counts,
        "fit": settings["fit"],
        "motion": settings["image_motion"],
        "transition": settings["transition"],
        "transition_seconds": settings["transition_seconds"],
        "apply_label": window.visual_inspector_s06.apply_selected.text(),
        "source_label": window.visual_inspector_s06.source_label.text(),
        "content_unchanged_by_route": signature_before_route == signature_after_route,
        "scale": scale,
        "font_family": font_family,
    }

    window.hide()
    window.deleteLater()
    app.processEvents()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP06 Visual evidence")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    ns = parser.parse_args(argv)

    output = Path(ns.output)
    geometry = capture(output, ns.width, ns.height, ns.scale)
    result = {"current": str(output), "geometry": geometry}
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
