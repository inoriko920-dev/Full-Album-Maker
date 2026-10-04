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


def _fixture_document(root: Path, *, populated: bool):
    from PySide6.QtGui import QColor, QImage

    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("Perjalanan Kita")
    document.album_title = "Perjalanan Kita"
    if not populated:
        return document

    cover_path = root / "album-cover.png"
    cover_image = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
    cover_image.fill(QColor("#76A9FA"))
    if not cover_image.save(str(cover_path), "PNG"):
        raise RuntimeError("Gagal membuat fixture cover Album.")

    cover = MediaAsset(
        kind="image",
        locator=str(cover_path),
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

    # 20 × 101 detik + 80 × 100 detik = 10.020 detik = 2j 47m.
    for index in range(100):
        duration_seconds = 101 if index < 20 else 100
        title = f"Lagu {index + 1:03d}"
        audio = MediaAsset(
            kind="audio",
            locator=str(root / f"{title}.mp3"),
            original_name=f"{title}.mp3",
            source_duration_tick=duration_seconds * TIMEBASE,
            metadata={"title": title, "artist": "Perjalanan Kita"},
        )
        document.media.append(audio)
        # Contract fixture:
        # - first 12 have no cover
        # - rows 7..24 have no visual = 18
        # - first 6 have a visual but no cover = exactly 6 review rows
        cover_id = cover.asset_id if index >= 12 else None
        visual_id = None if 6 <= index < 24 else visual.asset_id
        document.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                display_artist="Perjalanan Kita",
                source_out_tick=audio.source_duration_tick,
                cover_asset_id=cover_id,
                visual_asset_id=visual_id,
            )
        )
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
        selected = {song.song_id for song in document.playlist.entries[:12]}
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
