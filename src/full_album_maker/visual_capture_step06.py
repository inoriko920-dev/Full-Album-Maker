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


def _make_visual_art(path: Path, seed: int, *, title: str = "") -> None:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPolygonF

    width, height = 1280, 720
    palettes = (
        ("#486B86", "#F0A36D", "#253B4B"),
        ("#6A8DB4", "#E7C49C", "#314E67"),
        ("#7BA58B", "#D6D8A8", "#3D6752"),
        ("#6F91B0", "#E6A574", "#46536C"),
        ("#7E8CA5", "#D8B88B", "#415A70"),
        ("#6E9A91", "#E1BD87", "#355D55"),
        ("#7A8DB5", "#E3A77A", "#3A4C69"),
        ("#7199A8", "#E8C48D", "#3D5E69"),
    )
    top, horizon, land = palettes[seed % len(palettes)]
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    sky = QLinearGradient(0, 0, 0, height)
    sky.setColorAt(0.0, QColor(top))
    sky.setColorAt(0.62, QColor(horizon))
    sky.setColorAt(1.0, QColor("#273A47"))
    painter.fillRect(image.rect(), sky)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 207, 108, 230))
    painter.drawEllipse(QRectF(width * 0.56, height * 0.44, 34, 34))

    painter.setBrush(QColor(land))
    painter.drawPolygon(QPolygonF([
        QPointF(0, height * 0.72),
        QPointF(width * 0.12, height * 0.61),
        QPointF(width * 0.24, height * 0.69),
        QPointF(width * 0.39, height * 0.56),
        QPointF(width * 0.52, height * 0.66),
        QPointF(width * 0.70, height * 0.54),
        QPointF(width, height * 0.69),
        QPointF(width, height),
        QPointF(0, height),
    ]))

    # Reference-like human silhouette; generated independently for deterministic QA.
    painter.setBrush(QColor("#1E222B"))
    painter.drawEllipse(QRectF(width * 0.73, height * 0.23, 84, 98))
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.72, height * 0.35),
        QPointF(width * 0.80, height * 0.32),
        QPointF(width * 0.87, height * 0.80),
        QPointF(width * 0.68, height * 0.81),
    ]))
    painter.setBrush(QColor("#E4E3DE"))
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.67, height * 0.44),
        QPointF(width * 0.74, height * 0.38),
        QPointF(width * 0.80, height * 0.81),
        QPointF(width * 0.62, height * 0.82),
    ]))

    if title:
        painter.setPen(QColor("#FFFFFF"))
        artist_font = QFont("Noto Sans", 16)
        painter.setFont(artist_font)
        painter.drawText(
            QRectF(width * 0.12, height * 0.22, width * 0.42, 30),
            Qt.AlignmentFlag.AlignCenter,
            "Raisa Herliani",
        )
        title_font = QFont("Noto Sans", 42)
        title_font.setItalic(True)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(width * 0.10, height * 0.28, width * 0.46, 70),
            Qt.AlignmentFlag.AlignCenter,
            "Senja",
        )
        subtitle_font = QFont("Noto Sans", 30)
        subtitle_font.setItalic(True)
        painter.setFont(subtitle_font)
        painter.drawText(
            QRectF(width * 0.13, height * 0.39, width * 0.40, 58),
            Qt.AlignmentFlag.AlignCenter,
            "di Kota Ini",
        )
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawLine(int(width * 0.29), int(height * 0.51), int(width * 0.37), int(height * 0.51))

    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Gagal membuat visual fixture: {path}")


def _fixture_document(root: Path):
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
    from .visual_precision import SetSongVisualSettings

    document = ProjectDocument.new_empty("Album Kenangan")
    document.album_title = "Album Kenangan"

    image_assets: list[MediaAsset] = []
    image_names = (
        "senja-kota-ini.png",
        "perjalanan-kita.png",
        "rumah-di-hati.png",
        "langkah-pagi.png",
        "cerita-lama.png",
        "kembali-pulang.png",
        "bunga-senja.png",
        "langit-biru.png",
    )
    for index, name in enumerate(image_names):
        path = root / name
        _make_visual_art(path, index, title=("Senja di Kota Ini" if index == 0 else ""))
        asset = MediaAsset(
            kind="image",
            locator=str(path),
            original_name=name,
            metadata={"width": 1280, "height": 720},
        )
        image_assets.append(asset)
        document.media.append(asset)

    video_assets: list[MediaAsset] = []
    for index, name in enumerate(("jalan-pulang.mp4", "cerita-baru.mp4", "malam-kota.mp4", "pagi-hari.mp4")):
        path = root / name
        path.write_bytes(b"UI05 deterministic video placeholder")
        preview = root / f"video-preview-{index + 1}.png"
        _make_visual_art(preview, index + 3)
        asset = MediaAsset(
            kind="video",
            locator=str(path),
            original_name=name,
            source_duration_tick=(14 + index * 3) * TIMEBASE,
            metadata={
                "width": 1920,
                "height": 1080,
                "visual_preview_path": str(preview),
            },
        )
        video_assets.append(asset)
        document.media.append(asset)

    titles = (
        "Senja di Kota Ini",
        "Jalan Pulang",
        "Perjalanan Kita",
        "Cerita Baru",
        "Langit yang Sama",
        "Rumah di Hati",
        "Langkah Pagi",
        "Cerita Lama",
        "Kembali Pulang",
        "Bunga Senja",
        "Langit Biru",
        "Malam Kota",
        "Pagi Hari",
        "Sampai Nanti",
    )
    durations = (258, 185, 267, 194, 242, 228, 214, 239, 201, 225, 219, 231, 208, 245)
    assignments = (
        image_assets[0].asset_id,
        video_assets[0].asset_id,
        image_assets[1].asset_id,
        video_assets[1].asset_id,
        None,
        image_assets[2].asset_id,
        image_assets[3].asset_id,
        image_assets[4].asset_id,
        image_assets[5].asset_id,
        image_assets[6].asset_id,
        image_assets[7].asset_id,
        video_assets[2].asset_id,
        video_assets[3].asset_id,
        None,
    )

    for index, (title, duration) in enumerate(zip(titles, durations)):
        audio_path = root / f"lagu-{index + 1:02d}.mp3"
        audio_path.write_bytes(b"UI05 deterministic audio placeholder")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=f"{title}.mp3",
            source_duration_tick=duration * TIMEBASE,
            metadata={"title": title, "artist": "Raisa Herliani"},
        )
        document.media.append(audio)
        document.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                display_artist="Raisa Herliani",
                source_out_tick=duration * TIMEBASE,
                visual_asset_id=assignments[index],
                enabled=index < 4,
            )
        )

    first = document.playlist.entries[0].song_id
    SetSongVisualSettings(
        first,
        {
            "fit": "fit",
            "crop_x": 0.0,
            "crop_y": 0.0,
            "crop_width": 1.0,
            "crop_height": 1.0,
            "position_x": 0.0,
            "position_y": 0.0,
            "scale": 1.0,
            "pan_zoom": True,
            "image_motion": "ken_burns",
            "loop_video": False,
            "freeze_end": False,
            "transition": "fade",
            "transition_seconds": 1.0,
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
            "transition": "slide",
            "transition_seconds": 0.8,
        },
    ).apply(document)
    SetSongVisualSettings(
        document.playlist.entries[3].song_id,
        {
            "fit": "fill",
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
    window.editor_workspace.set_playhead(52 * document.timebase)
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
