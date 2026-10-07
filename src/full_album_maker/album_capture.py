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


def _make_artwork(path: Path, seed: int, *, width: int = 160, height: int = 92) -> None:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen, QPolygonF

    palettes = (
        ("#F3A45F", "#F8D79A", "#556C63"),
        ("#86B9E7", "#D6ECF8", "#586E8B"),
        ("#79A787", "#D0E1B4", "#3F6550"),
        ("#E99A5C", "#F5C57E", "#6C5A4D"),
        ("#6E8CAF", "#C3D6E9", "#344D67"),
        ("#87C1D8", "#DCEEF6", "#49717C"),
    )
    top, bottom, land = palettes[seed % len(palettes)]
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0.0, QColor(top))
    gradient.setColorAt(0.62, QColor(bottom))
    gradient.setColorAt(1.0, QColor("#EDF4F8"))
    painter.fillRect(image.rect(), gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(land))
    painter.drawPolygon(QPolygonF([
        QPointF(0, height),
        QPointF(width * .18, height * .62),
        QPointF(width * .34, height * .45),
        QPointF(width * .51, height * .68),
        QPointF(width * .72, height * .38),
        QPointF(width, height),
    ]))
    painter.setBrush(QColor(255, 215, 120, 210))
    painter.drawEllipse(QRectF(width * .72, height * .16, 14, 14))
    painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
    painter.drawLine(0, int(height * .72), width, int(height * .72))
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Gagal membuat artwork fixture: {path}")


def _fixture_document(root: Path, *, populated: bool):
    from .album_model import ALBUM_COVER_KEY, TRANSITIONS_KEY
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("Perjalanan Kita")
    document.album_title = "Perjalanan Kita"
    if not populated:
        return document

    artwork_paths: list[Path] = []
    visual_paths: list[Path] = []
    for index in range(10):
        artwork = root / f"artwork-{index + 1:02d}.png"
        visual_preview = root / f"visual-{index + 1:02d}.png"
        _make_artwork(artwork, index)
        _make_artwork(visual_preview, index + 3)
        artwork_paths.append(artwork)
        visual_paths.append(visual_preview)

    album_cover_path = root / "album-cover.png"
    _make_artwork(album_cover_path, 0, width=112, height=112)

    cover = MediaAsset(
        kind="image",
        locator=str(album_cover_path),
        original_name="Perjalanan Kita.png",
        metadata={"title": "Perjalanan Kita"},
    )
    visual = MediaAsset(
        kind="video",
        locator=str(root / "album-visual.mp4"),
        original_name="album-visual.mp4",
        source_duration_tick=100 * TIMEBASE,
    )
    document.media.extend([cover, visual])
    document.extensions[ALBUM_COVER_KEY] = cover.asset_id
    document.extensions["album_created_label"] = "Dibuat 8 Jan 2025 14:32"

    first_titles = (
        "Senja di Kota Ini",
        "Jalan Pulang",
        "Perjalanan Kita",
        "Cerita Baru",
        "Di Ujung Waktu",
        "Langit Yang Sama",
        "Rumah Untuk Kembali",
        "Terdekat Namun Jauh",
        "Bersama Lagi",
        "Sampai Nanti",
    )
    first_durations = (258, 185, 327, 194, 276, 232, 251, 225, 248, 312)
    transition_kinds = ("fade", "cross_fade", "fade", "zoom", "fade", "cross_fade", "fade", "zoom", "fade", "cross_fade")

    # Keep the exact acceptance totals while making the first viewport mirror the
    # canonical Album state: row 5 review, rows 6-7 missing visual, others ready.
    missing_cover = {4, 10, 11, 12, 13, 14, 15, 30, 31, 32, 33, 34}
    missing_visual = {5, 6, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}
    transitions: dict[str, dict[str, object]] = {}

    # First ten durations follow the reference. Remaining ninety sum to 7,512s,
    # preserving the exact 10,020s / 2j 47m acceptance duration.
    for index in range(100):
        if index < 10:
            title = first_titles[index]
            duration_seconds = first_durations[index]
        else:
            title = f"Lagu {index + 1:03d}"
            duration_seconds = 84 if index < 52 else 83

        artwork_path = artwork_paths[index % 10]
        visual_preview = visual_paths[index % 10]
        audio = MediaAsset(
            kind="audio",
            locator=str(root / f"{title}.mp3"),
            original_name=f"{title}.mp3",
            source_duration_tick=duration_seconds * TIMEBASE,
            metadata={
                "title": title,
                "artist": "Perjalanan Kita",
                "artwork_path": str(artwork_path),
                "visual_preview_path": str(visual_preview),
            },
        )
        document.media.append(audio)
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=title,
            display_artist="Perjalanan Kita",
            source_out_tick=audio.source_duration_tick,
            cover_asset_id=None if index in missing_cover else cover.asset_id,
            visual_asset_id=None if index in missing_visual else visual.asset_id,
        )
        document.playlist.entries.append(song)
        transitions[song.song_id] = {
            "kind": transition_kinds[index] if index < 10 else "fade",
            "duration_seconds": 2.0,
        }

    document.extensions[TRANSITIONS_KEY] = transitions
    document.validate()
    return document

def capture(state: str, output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    _prepare_qt(scale)

    # Importing main installs the production compatibility/presentation layers.
    import full_album_maker.main  # noqa: F401

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .album_model import album_duration_text, summary
    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    fixture_root = Path(tempfile.mkdtemp(prefix="fam-step04-album-"))
    document = _fixture_document(fixture_root, populated=state != "empty")

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window.foundation_shell.set_workspace("album")
    if state != "empty":
        selected = {song.song_id for song in document.playlist.entries[:7]} | {song.song_id for song in document.playlist.entries[20:25]}
        window.album_workspace.set_selection(selected)
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(240, loop.quit)
    loop.exec()
    app.processEvents()

    live_document = window.editor_workspace.document()
    info = summary(live_document)
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot Album: {output}")

    shell = window.foundation_shell
    geometry = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "album_active": shell.workspace_stack.currentWidget() is window.album_workspace,
        "context_visible": not window.album_context.isHidden(),
        "inspector_active": window._inspector_router.currentWidget() is window.album_tools,
        "timeline_visible": not window.album_timeline_canvas.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "table_rows": window.album_workspace.table.rowCount(),
        "song_count": info.song_count,
        "missing_cover": info.missing_cover,
        "missing_visual": info.missing_visual,
        "needs_review": info.needs_review,
        "album_duration": album_duration_text(info.duration_seconds),
        "selected_count": len(window.album_workspace.selected_song_ids),
        "bulk_heading": window.album_tools.heading.text(),
        "page_label": window.album_workspace.page_label.text(),
        "scale": scale,
        "font_family": font_family,
    }

    # Do not call close() in deterministic/offscreen capture. The production
    # closeEvent correctly asks the user to save a dirty Editor V2 document,
    # which would create an unanswerable modal dialog on a headless CI runner.
    # Hiding/deleting the fixture window bypasses only that interactive shutdown
    # prompt; application close semantics remain untouched.
    window.hide()
    window.deleteLater()
    app.processEvents()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP04 Album evidence")
    parser.add_argument("--state", choices=("golden", "empty"), default="golden")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    ns = parser.parse_args(argv)

    output = Path(ns.output)
    geometry = capture(ns.state, output, ns.width, ns.height, ns.scale)
    result = {"current": str(output), "geometry": geometry}
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
