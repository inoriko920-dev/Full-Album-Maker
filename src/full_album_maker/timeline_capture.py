from __future__ import annotations

import argparse
import json
from pathlib import Path

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


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

    durations = (30, 30, 30)
    titles = ("Senja di Kota Ini", "Jalan Pulang", "Cerita Baru")
    starts = (0, 25, 60)
    songs: list[SongInstance] = []
    for index, (title, seconds, start) in enumerate(zip(titles, durations, starts)):
        audio = MediaAsset(
            kind="audio",
            locator=f"fixture-{index + 1}.mp3",
            original_name=f"{title}.mp3",
            source_duration_tick=seconds * TIMEBASE,
            metadata={"title": title, "artist": "Full Album Maker"},
        )
        document.media.append(audio)
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=title,
            display_artist="Full Album Maker",
            source_out_tick=audio.source_duration_tick,
            free_start_tick=start * TIMEBASE,
            crossfade_in_tick=(5 * TIMEBASE if index == 1 else 0),
        )
        document.playlist.entries.append(song)
        songs.append(song)
    document.playlist.mode = "free"

    visual_track = document.tracks[0].track_id
    document.layers.extend(
        [
            Layer(
                track_id=visual_track,
                type="background",
                name="Video 01 - Kota.mp4",
                order=0,
                time_binding=TimeBinding(kind="album"),
                transform=Transform(x=0.0, y=0.0, width=1.0, height=1.0),
                properties={"mode": "solid", "color": "#27445E"},
            ),
            Layer(
                track_id=visual_track,
                type="overlay",
                name="Overlay Cahaya",
                order=1,
                time_binding=TimeBinding(kind="absolute", start_tick=8 * TIMEBASE, duration_tick=24 * TIMEBASE),
                transform=Transform(x=0.62, y=0.12, width=0.25, height=0.20),
            ),
            Layer(
                track_id=visual_track,
                type="text",
                name="Senja di Kota Ini",
                order=2,
                time_binding=TimeBinding(kind="absolute", start_tick=0, duration_tick=45 * TIMEBASE),
                transform=Transform(x=0.20, y=0.25, width=0.60, height=0.22),
                properties={"text": "Senja\ndi Kota Ini", "color": "#FFFFFF"},
            ),
            Layer(
                track_id=visual_track,
                type="spectrum",
                name="Spectrum",
                order=3,
                time_binding=TimeBinding(kind="album"),
                transform=Transform(x=0.18, y=0.76, width=0.64, height=0.16),
                properties={"style": "bars", "color": "#8A5CF5", "gain": 1.0},
            ),
            Layer(
                track_id=visual_track,
                type="sticker",
                name="Stiker - Daun",
                order=4,
                time_binding=TimeBinding(kind="absolute", start_tick=64 * TIMEBASE, duration_tick=15 * TIMEBASE),
                transform=Transform(x=0.08, y=0.72, width=0.18, height=0.16),
            ),
        ]
    )

    for tick, label, color in (
        (0, "Intro", "#E23A4B"),
        (25 * TIMEBASE, "Reff", "#1766E8"),
        (55 * TIMEBASE, "Bridge", "#D49B1B"),
        (82 * TIMEBASE, "Outro", "#35A765"),
    ):
        AddTimelineMarker(tick, label, color).apply(document)

    SetSongMix(songs[0].song_id, 1.0, 1 * TIMEBASE, 2 * TIMEBASE, False).apply(document)
    SetSongMix(songs[1].song_id, 0.92, 2 * TIMEBASE, 2 * TIMEBASE, False).apply(document)
    SetSongMix(songs[2].song_id, 0.96, 1 * TIMEBASE, 3 * TIMEBASE, False).apply(document)
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
        selected = document.playlist.entries[1]
        window._s05_select_song(selected.song_id)
        window._s05_set_playhead(27 * document.timebase)
        window.timeline_precision_s05.canvas.fit_project()
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(260, loop.quit)
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
