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


def _make_timeline_preview(path: Path, *, width: int = 1280, height: int = 720) -> None:
    """Generate independent deterministic artwork for the UI-04 capture fixture."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPolygonF

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    sky = QLinearGradient(0, 0, width, height)
    sky.setColorAt(0.0, QColor("#355A78"))
    sky.setColorAt(0.45, QColor("#D88A69"))
    sky.setColorAt(0.72, QColor("#F4B46D"))
    sky.setColorAt(1.0, QColor("#263D50"))
    painter.fillRect(image.rect(), sky)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 210, 115, 230))
    painter.drawEllipse(QRectF(width * 0.61, height * 0.39, 26, 26))

    # Distant skyline.
    painter.setBrush(QColor(37, 62, 78, 220))
    x = 0
    heights = (92, 55, 118, 72, 102, 63, 134, 84, 68, 115, 77, 126, 58, 95)
    for i, h in enumerate(heights):
        w = 62 + (i % 3) * 17
        painter.drawRect(QRectF(x, height * 0.60 - h, w, h + height * 0.22))
        x += w - 4
    painter.fillRect(QRectF(0, height * 0.66, width, height * 0.34), QColor(33, 59, 70, 230))

    # Balcony rails.
    painter.setPen(QPen(QColor("#121D27"), 10))
    painter.drawLine(0, int(height * 0.84), width, int(height * 0.84))
    painter.setPen(QPen(QColor("#5C372B"), 4))
    painter.drawLine(0, int(height * 0.87), width, int(height * 0.87))

    # Human silhouette on the right, intentionally generated and not copied from golden.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1A2029"))
    painter.drawEllipse(QRectF(width * 0.70, height * 0.28, 98, 112))
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.70, height * 0.40),
        QPointF(width * 0.78, height * 0.37),
        QPointF(width * 0.84, height * 0.72),
        QPointF(width * 0.68, height * 0.75),
    ]))
    painter.setBrush(QColor("#E2E4E7"))
    painter.drawPolygon(QPolygonF([
        QPointF(width * 0.66, height * 0.48),
        QPointF(width * 0.73, height * 0.43),
        QPointF(width * 0.79, height * 0.76),
        QPointF(width * 0.63, height * 0.78),
    ]))

    # Album title matching the fixture semantics.
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Noto Sans", 42)
    font.setItalic(True)
    painter.setFont(font)
    painter.drawText(QRectF(width * 0.12, height * 0.22, width * 0.42, 90), Qt.AlignmentFlag.AlignCenter, "Senja")
    font2 = QFont("Noto Sans", 34)
    painter.setFont(font2)
    painter.drawText(QRectF(width * 0.18, height * 0.35, width * 0.34, 80), Qt.AlignmentFlag.AlignCenter, "di Kota Ini")
    painter.end()

    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Gagal membuat preview fixture: {path}")


def _fixture_document(*, populated: bool):
    from .editor_models import (
        Layer,
        MediaAsset,
        ProjectDocument,
        SongInstance,
        TIMEBASE,
        TimeBinding,
        Transform,
    )
    from .timeline_precision import AddTimelineMarker, SetSongMix

    document = ProjectDocument.new_empty("Senja di Kota Ini")
    document.album_title = "Senja di Kota Ini"
    document.canvas.background_color = "#172536"
    if not populated:
        return document

    # Reference-like 4:28 state: one five-second crossfade and one five-second gap.
    durations = (155.2, 90.0, 22.8)
    titles = ("Senja di Kota Ini", "Jalan Pulang", "Cerita Baru")
    starts = (0.0, 150.2, 245.2)
    songs: list[SongInstance] = []
    for index, (title, seconds, start) in enumerate(zip(titles, durations, starts)):
        duration_tick = int(round(seconds * TIMEBASE))
        audio = MediaAsset(
            kind="audio",
            locator=f"fixture-{index + 1}.mp3",
            original_name=f"{title}.mp3",
            source_duration_tick=duration_tick,
            metadata={"title": title, "artist": "Full Album Maker"},
        )
        document.media.append(audio)
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=title,
            display_artist="Full Album Maker",
            source_out_tick=duration_tick,
            free_start_tick=int(round(start * TIMEBASE)),
            crossfade_in_tick=(5 * TIMEBASE if index == 1 else 0),
        )
        document.playlist.entries.append(song)
        songs.append(song)
    document.playlist.mode = "free"

    visual_track = document.tracks[0].track_id
    def add_layer(layer_type: str, name: str, order: int, start: float, duration: float, *, x=0.0, y=0.0, w=1.0, h=1.0):
        document.layers.append(
            Layer(
                track_id=visual_track,
                type=layer_type,
                name=name,
                order=order,
                opacity=0.0,
                time_binding=TimeBinding(
                    kind="absolute",
                    start_tick=int(round(start * TIMEBASE)),
                    duration_tick=int(round(duration * TIMEBASE)),
                ),
                transform=Transform(x=x, y=y, width=w, height=h),
                properties={"mode": "solid", "color": "#27445E"} if layer_type == "background" else {},
            )
        )

    add_layer("background", "Video 01 - Kota.mp4", 0, 0, 86)
    add_layer("background", "Video 02 - Perjalanan.mp4", 1, 86, 119)
    add_layer("background", "Video 03 - Senja.mp4", 2, 205, 63)
    add_layer("overlay", "Overlay Cahaya", 3, 9, 66, x=.60, y=.10, w=.28, h=.22)
    add_layer("overlay", "Overlay Film", 4, 91, 88, x=.60, y=.10, w=.28, h=.22)
    add_layer("overlay", "Bokeh", 5, 220, 38, x=.60, y=.10, w=.28, h=.22)
    add_layer("text", "Senja di Kota Ini", 6, 15, 75, x=.18, y=.22, w=.55, h=.22)
    add_layer("text", "Perjalanan Kita", 7, 105, 82, x=.18, y=.22, w=.55, h=.22)
    add_layer("text", "Cerita Baru", 8, 215, 40, x=.18, y=.22, w=.55, h=.22)
    add_layer("spectrum", "Spectrum", 9, 7, 228, x=.18, y=.76, w=.64, h=.16)
    add_layer("sticker", "Stiker - Daun", 10, 20, 48, x=.08, y=.72, w=.18, h=.16)
    add_layer("sticker", "Overlay - Cahaya", 11, 197, 31, x=.72, y=.72, w=.18, h=.16)

    for tick, label, color in (
        (15 * TIMEBASE, "Intro", "#E23A4B"),
        (84 * TIMEBASE, "Reff", "#1766E8"),
        (139 * TIMEBASE, "Bridge", "#D49B1B"),
        (210 * TIMEBASE, "Outro", "#35A765"),
    ):
        AddTimelineMarker(tick, label, color).apply(document)

    SetSongMix(songs[0].song_id, 1.0, 3 * TIMEBASE, 4 * TIMEBASE, False).apply(document)
    SetSongMix(songs[1].song_id, 1.0, 2 * TIMEBASE, 2 * TIMEBASE, False).apply(document)
    SetSongMix(songs[2].song_id, 1.0, 1 * TIMEBASE, 2 * TIMEBASE, False).apply(document)
    document.validate()
    return document


def capture(state: str, output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    _prepare_qt(scale)

    # Import main first so all production presentation/compatibility layers are active.
    import full_album_maker.main  # noqa: F401

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .timeline_precision import timeline_gaps, timeline_markers
    from .timeline_resolver import TimelineResolver

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    document = _fixture_document(populated=state != "empty")
    signature_before_route = document.content_signature()

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window.foundation_shell.set_workspace("timeline")
    if state != "empty":
        selected = document.playlist.entries[0]
        window._s05_select_song(selected.song_id)
        window._s05_set_playhead(84 * document.timebase)
        window.timeline_precision_s05.canvas.fit_project()

        fixture_root = Path(tempfile.mkdtemp(prefix="fam-ui04-timeline-"))
        preview_path = fixture_root / "timeline-preview.png"
        _make_timeline_preview(preview_path)
        window.timeline_workspace_s05.preview.set_accurate_frame(preview_path)
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()
    app.processEvents()

    live_document = window.editor_workspace.document()
    resolved = TimelineResolver().resolve(live_document)
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot Timeline: {output}")

    shell = window.foundation_shell
    precision = window.timeline_precision_s05
    geometry = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "timeline_active": shell.workspace_stack.currentWidget() is window.timeline_workspace_s05,
        "context_visible": not window.timeline_context_s05.isHidden(),
        "inspector_active": window._inspector_router.currentWidget() is window.timeline_inspector_s05,
        "precision_visible": not precision.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "precision_height": precision.height(),
        "status_height": shell.status_bar.height(),
        "playlist_mode": live_document.playlist.mode,
        "song_count": len(resolved.songs),
        "marker_count": len(timeline_markers(live_document)),
        "gap_count": len(timeline_gaps(live_document)) if live_document.playlist.mode == "free" else 0,
        "crossfade_count": sum(1 for song in live_document.playlist.entries if song.crossfade_in_tick > 0),
        "audio_errors": [item for item in resolved.errors if item.startswith("Audio: ")],
        "route_preserved_content": live_document.content_signature() == signature_before_route,
        "selected_inspector": window.timeline_inspector_s05.heading.text(),
        "selected_subtitle": window.timeline_inspector_s05.subtitle.text(),
        "monitor_audio_available": window.timeline_workspace_s05.monitor_volume.isEnabled(),
        "scale": scale,
        "font_family": font_family,
    }

    window.hide()
    window.deleteLater()
    app.processEvents()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP05 Timeline evidence")
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
