from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


def _fixture_covers(root: Path):
    """Create four deterministic capture-only covers shaped like UI-06 moods."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPolygonF

    specs = (
        ("senja", "#172C43", "#D77B45", "sunset"),
        ("pulang", "#15374A", "#4F7E86", "mountain"),
        ("perjalanan", "#335B43", "#8EA166", "valley"),
        ("cerita", "#9E5A32", "#F0B868", "people"),
    )
    paths: list[Path] = []
    for name, top, bottom, motif in specs:
        path = root / f"cover-{name}.png"
        image = QImage(1280, 720, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(top))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        gradient = QLinearGradient(0, 0, 0, 720)
        gradient.setColorAt(0.0, QColor(top))
        gradient.setColorAt(1.0, QColor(bottom))
        painter.fillRect(image.rect(), gradient)
        painter.setPen(Qt.PenStyle.NoPen)

        if motif == "sunset":
            painter.setBrush(QColor("#EAA05B"))
            painter.drawEllipse(170, 220, 165, 165)
            painter.setBrush(QColor("#18222C"))
            painter.drawPolygon(QPolygonF([
                QPointF(0, 550), QPointF(260, 470), QPointF(510, 535),
                QPointF(760, 455), QPointF(1280, 565), QPointF(1280, 720),
                QPointF(0, 720),
            ]))
            painter.setBrush(QColor("#111820"))
            painter.drawEllipse(930, 180, 105, 105)
            painter.drawPolygon(QPolygonF([
                QPointF(980, 270), QPointF(870, 650), QPointF(1115, 650),
            ]))
        elif motif == "mountain":
            painter.setBrush(QColor("#244B5C"))
            painter.drawPolygon(QPolygonF([
                QPointF(0, 610), QPointF(300, 250), QPointF(600, 610),
            ]))
            painter.setBrush(QColor("#193A49"))
            painter.drawPolygon(QPolygonF([
                QPointF(360, 610), QPointF(760, 185), QPointF(1130, 610),
            ]))
            painter.setBrush(QColor("#607E79"))
            painter.drawPolygon(QPolygonF([
                QPointF(725, 225), QPointF(760, 185), QPointF(815, 248),
            ]))
            painter.setBrush(QColor("#142C36"))
            painter.drawRect(0, 600, 1280, 120)
        elif motif == "valley":
            painter.setBrush(QColor("#294D3A"))
            painter.drawPolygon(QPolygonF([
                QPointF(0, 490), QPointF(290, 305), QPointF(580, 520),
                QPointF(860, 260), QPointF(1280, 500), QPointF(1280, 720),
                QPointF(0, 720),
            ]))
            painter.setBrush(QColor("#B8B07A"))
            painter.drawPolygon(QPolygonF([
                QPointF(580, 720), QPointF(695, 520), QPointF(760, 720),
            ]))
            painter.setBrush(QColor(255, 255, 255, 55))
            painter.drawEllipse(425, 190, 420, 150)
        else:
            painter.setBrush(QColor("#E6A25D"))
            painter.drawEllipse(120, 165, 145, 145)
            painter.setBrush(QColor("#5A342B"))
            painter.drawRect(0, 535, 1280, 185)
            for cx in (735, 885):
                painter.setBrush(QColor("#302827"))
                painter.drawEllipse(cx, 250, 82, 82)
                painter.drawPolygon(QPolygonF([
                    QPointF(cx + 42, 320), QPointF(cx - 38, 560), QPointF(cx + 122, 560),
                ]))

        painter.end()
        if not image.save(str(path), "PNG"):
            raise RuntimeError(f"Gagal membuat cover fixture STEP07: {path.name}")
        paths.append(path)
    return tuple(paths)


def _fixture_document(root: Path):
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("Video Full Album")
    document.album_title = "Perjalanan Kita"

    cover_assets = []
    for cover_path in _fixture_covers(root):
        cover_asset = MediaAsset(
            kind="image",
            locator=str(cover_path),
            original_name=cover_path.name,
        )
        document.media.append(cover_asset)
        cover_assets.append(cover_asset)

    titles = (
        "Senja di Kota Ini",
        "Jalan Pulang",
        "Perjalanan Kita",
        "Cerita Baru",
    )
    # Capture-only timings are shaped to the immutable UI-06 reference. They do
    # not change runtime timeline semantics; they only make the QA fixture use the
    # same long-form spacing proportions as the approved screenshot.
    durations = (46, 39, 46, 54)
    for index, title in enumerate(titles):
        audio_path = root / f"lagu-{index + 1}.mp3"
        audio_path.write_bytes(b"STEP07 deterministic audio placeholder")
        duration = durations[index]
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
                cover_asset_id=cover_assets[index].asset_id,
            )
        )
    document.validate()
    return document


def _seed_reference_custom_templates(window, document, root: Path):
    """Create functional custom-template fixtures through the production API.

    UI-06 contains a mixed gallery: eight built-ins followed by four user custom
    templates. The clean CI account naturally has no user templates, so the
    fidelity capture creates four real portable customs in a temporary store.
    Nothing is written to the normal user data directory and built-in catalog
    semantics remain unchanged.
    """

    from .custom_template_builder import CustomTemplateStore
    from .template_portability_step07 import duplicate_portable_template
    from .template_studio_step07 import TemplateStudioDraft

    store = CustomTemplateStore(root / "custom-templates")
    window._s07_store = store
    targets = tuple(song.song_id for song in document.playlist.entries)
    fixtures = (
        ("spotify_clean", "Momen Bahagia", "Keluarga • Custom"),
        ("cafe_acoustic", "Jejak Perjalanan", "Travel • Custom"),
        ("neon_spectrum", "Harmoni", "Musik • Custom"),
        ("photo_album", "Warna Hidup", "Modern • Custom"),
    )
    for source_id, label, description in fixtures:
        duplicate_portable_template(
            document,
            TemplateStudioDraft(template_id=source_id, ratio="16:9"),
            targets,
            label=label,
            description=description,
            store=store,
        )
    return store


def capture(output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    # Thumbnail cards intentionally use their deterministic painted fallback in
    # golden capture. Runtime async thumbnail behavior has separate focused tests.
    os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    _prepare_qt(scale)

    # Install the real production STEP01..07 layers before creating the window.
    import full_album_maker.main  # noqa: F401

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QSlider

    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .template_studio_step07 import builtin_descriptors, custom_descriptors

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    fixture_root = Path(tempfile.mkdtemp(prefix="fam-step07-template-"))
    document = _fixture_document(fixture_root)

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    _seed_reference_custom_templates(window, document, fixture_root)
    signature_before = window.editor_workspace.document().content_signature()
    first = document.playlist.entries[0].song_id
    second = document.playlist.entries[1].song_id
    window._s06_primary_song_id = first
    window._s06_selected_ids = {first, second}
    window.editor_workspace.set_playhead(int(round(84.25 * document.timebase)))
    window.foundation_shell.set_workspace("template")
    window._s07_refresh()
    window._s07_select_template("spotify_clean")
    window._s07_preview()
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()
    app.processEvents()

    # Use the same long-form visual scale seen in UI-06. The production toolbar
    # remains fully functional; this deterministic value is capture-only.
    for slider in window.foundation_shell.timeline.findChildren(QSlider):
        if slider.minimum() == 50 and slider.maximum() == 180:
            slider.setValue(69)
    if hasattr(window.template_timeline_s07, "set_zoom_percent"):
        window.template_timeline_s07.set_zoom_percent(69)
    app.processEvents()

    # Showing the window can legitimately trigger a route refresh, which restores
    # the real Built-in filter. Apply the deterministic UI-06 overview only after
    # those events have settled so the screenshot actually contains 8 built-ins
    # plus 4 functional customs. No filter owner or project state is mutated.
    customs, custom_errors = window._s07_store.scan()
    if custom_errors:
        raise RuntimeError(f"Custom template fixture invalid: {custom_errors}")
    custom_cards = custom_descriptors(customs)
    custom_by_name = {descriptor.name: descriptor for descriptor in custom_cards}
    reference_order = (
        "Momen Bahagia",
        "Jejak Perjalanan",
        "Harmoni",
        "Warna Hidup",
    )
    ordered_customs = tuple(custom_by_name[name] for name in reference_order)
    overview = (*builtin_descriptors()[:8], *ordered_customs)
    window.template_workspace_s07.set_templates(
        overview,
        selected_id="spotify_clean",
        favorites=(),
    )
    app.processEvents()

    live_document = window.editor_workspace.document()
    signature_after = live_document.content_signature()
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot STEP07 Template: {output}")

    shell = window.foundation_shell
    descriptor = window._s07_current_descriptor()
    draft = window._s07_inspector_draft()
    card = window.template_workspace_s07._cards.get(descriptor.template_id)
    geometry = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "template_active": shell.workspace_stack.currentWidget() is window.template_workspace_s07,
        "context_visible": not window.template_context_s07.isHidden(),
        "inspector_active": window._inspector_router.currentWidget() is window.template_inspector_s07,
        "timeline_visible": not window.template_timeline_s07.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "card_count": len(window.template_workspace_s07._cards),
        "custom_card_count": len(customs),
        "custom_card_order": [descriptor.name for descriptor in ordered_customs],
        "song_count": len(live_document.playlist.entries),
        "selected_template_id": descriptor.template_id,
        "selected_template_name": descriptor.name,
        "origin_filter": window.template_context_s07.origin_key,
        "category_filter": window.template_context_s07.category_key,
        "ratio_filter": window.template_context_s07.ratio_key,
        "sort_filter": window.template_context_s07.sort_key,
        "search_placeholder": window.template_context_s07.search.placeholderText(),
        "draft_ratio": draft.ratio,
        "title_layout": draft.title_layout,
        "cover_position": draft.cover_position,
        "background_style": draft.background_style,
        "spacing": draft.spacing,
        "overlay_opacity": draft.overlay_opacity,
        "scope": window.template_inspector_s07.scope_key,
        "built_in_save_custom_enabled": window.template_inspector_s07.save_custom.isEnabled(),
        "preview_text": window.template_workspace_s07.preview_state.text(),
        "thumbnail_status": card.thumbnail.thumbnail_status if card is not None else "MISSING_CARD",
        "selected_song_count": len(window._s06_selected_ids),
        "content_unchanged_by_route_and_preview": signature_before == signature_after,
        "scale": scale,
        "font_family": font_family,
    }

    window.hide()
    window.deleteLater()
    app.processEvents()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP07 Template evidence")
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
        report.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
