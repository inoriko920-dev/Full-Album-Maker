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


def _fixture_art(path: Path, index: int, *, size: tuple[int, int] = (160, 96)) -> None:
    """Create deterministic synthetic artwork so real thumbnail UI is exercised.

    These images are fixture media, not copies of the immutable UI golden.
    """
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen

    width, height = size
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    palettes = (
        ("#314B72", "#F29A63", "#FFD78D"),
        ("#163A57", "#5D9FBC", "#BBD4D9"),
        ("#294D42", "#7FAF73", "#D5C27B"),
        ("#5C405E", "#E18B68", "#FFD398"),
        ("#3A4B68", "#C88258", "#F7C183"),
        ("#214C64", "#72A8C0", "#C8E2E9"),
        ("#3F5570", "#E3A45D", "#F7D88F"),
        ("#173950", "#4D829D", "#A2C7D3"),
        ("#405C42", "#87A864", "#D3C77B"),
        ("#3B4B5F", "#DB9966", "#F5D29C"),
    )
    sky, horizon, sun = palettes[index % len(palettes)]
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0.0, QColor(sky))
    gradient.setColorAt(0.68, QColor(horizon))
    gradient.setColorAt(1.0, QColor("#24384B"))
    painter.fillRect(image.rect(), gradient)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(sun))
    radius = max(7, int(height * 0.09))
    painter.drawEllipse(QPointF(width * (0.68 - (index % 3) * 0.11), height * 0.34), radius, radius)

    painter.setBrush(QColor("#203244"))
    mountains = [
        QPointF(0, height * 0.72),
        QPointF(width * 0.22, height * 0.48),
        QPointF(width * 0.40, height * 0.70),
        QPointF(width * 0.60, height * 0.44),
        QPointF(width * 0.82, height * 0.69),
        QPointF(width, height * 0.55),
        QPointF(width, height),
        QPointF(0, height),
    ]
    from PySide6.QtGui import QPolygonF
    painter.drawPolygon(QPolygonF(mountains))
    painter.setPen(QPen(QColor("#FFFFFF"), 1))
    painter.setOpacity(0.18)
    painter.drawLine(QPointF(0, height * 0.80), QPointF(width, height * 0.80))
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Gagal membuat fixture artwork Album: {path}")


def _fixture_document(root: Path, *, populated: bool):
    from .album_model import ALBUM_COVER_KEY, DEFAULT_TRANSITION_KEY, TRANSITIONS_KEY
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("Perjalanan Kita")
    document.album_title = "Perjalanan Kita"
    if not populated:
        return document

    cover_assets: list[MediaAsset] = []
    visual_assets: list[MediaAsset] = []
    for index in range(10):
        cover_path = root / "covers" / f"cover-{index + 1:02d}.png"
        visual_thumb = root / "visuals" / f"visual-{index + 1:02d}.png"
        _fixture_art(cover_path, index, size=(120, 120))
        _fixture_art(visual_thumb, index + 3, size=(160, 90))
        video_path = root / "visuals" / f"visual-{index + 1:02d}.mp4"
        video_path.write_bytes(b"fixture-video-placeholder")
        cover = MediaAsset(
            kind="image",
            locator=str(cover_path),
            original_name=f"Cover {index + 1:02d}.png",
            metadata={"title": f"Cover {index + 1:02d}"},
        )
        visual = MediaAsset(
            kind="video",
            locator=str(video_path),
            original_name=video_path.name,
            source_duration_tick=360 * TIMEBASE,
            metadata={"thumbnail_path": str(visual_thumb)},
        )
        document.media.extend([cover, visual])
        cover_assets.append(cover)
        visual_assets.append(visual)

    document.extensions[ALBUM_COVER_KEY] = cover_assets[0].asset_id
    document.extensions[DEFAULT_TRANSITION_KEY] = {"kind": "fade", "duration_seconds": 2.0}

    visible_titles = (
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
    visible_durations = (258, 185, 327, 194, 276, 232, 251, 225, 248, 312)
    visible_transitions = (
        "fade", "cross_fade", "fade", "zoom", "fade",
        "cross_fade", "fade", "zoom", "fade", "cross_fade",
    )
    transitions: dict[str, dict[str, object]] = {}

    # Keep the established STEP04 contract while making the first page realistic:
    # 100 songs, exactly 10,020 seconds (2j47m), 12 missing covers,
    # 18 missing visuals, and exactly 6 review rows.
    missing_cover = {4, *range(20, 31)}
    missing_visual = {5, 6, *range(20, 26), *range(40, 50)}

    for index in range(100):
        if index < 10:
            duration_seconds = visible_durations[index]
            title = visible_titles[index]
        else:
            # Remaining 90 tracks sum to 7,512 seconds: 42×84 + 48×83.
            duration_seconds = 84 if index < 52 else 83
            title = f"Perjalanan {index + 1:02d}"
        audio_path = root / "audio" / f"{index + 1:03d}-{title}.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"fixture-audio")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=duration_seconds * TIMEBASE,
            metadata={"title": title, "artist": "Perjalanan Kita"},
        )
        document.media.append(audio)
        cover_id = None if index in missing_cover else cover_assets[index % len(cover_assets)].asset_id
        visual_id = None if index in missing_visual else visual_assets[index % len(visual_assets)].asset_id
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=title,
            display_artist="Perjalanan Kita",
            source_out_tick=audio.source_duration_tick,
            cover_asset_id=cover_id,
            visual_asset_id=visual_id,
        )
        document.playlist.entries.append(song)
        if index < 10:
            transitions[song.song_id] = {
                "kind": visible_transitions[index],
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
        # Match the visible selection pattern while preserving the 12-song
        # selection contract: rows 1..7 plus five selections outside page 1.
        chosen = [*document.playlist.entries[:7], *document.playlist.entries[20:25]]
        selected = {song.song_id for song in chosen}
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
