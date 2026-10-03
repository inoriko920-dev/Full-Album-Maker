from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import wave

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


def _write_fixture_wav(path: Path, *, seconds: float = 8.0, sample_rate: int = 44100) -> None:
    """Write deterministic mono PCM: silence first, audible tone afterwards."""

    frames = int(round(seconds * sample_rate))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            t = index / sample_rate
            if t < 2.0:
                value = 0.0
            else:
                envelope = 0.55 + 0.35 * math.sin(math.tau * 0.7 * t) ** 2
                value = envelope * (
                    0.58 * math.sin(math.tau * 220.0 * t)
                    + 0.30 * math.sin(math.tau * 880.0 * t)
                )
            sample = max(-32767, min(32767, int(round(value * 32767.0))))
            payload.extend(struct.pack("<h", sample))
        handle.writeframes(bytes(payload))


def _write_fixture_image(path: Path, *, cover: bool = False) -> None:
    """Create deterministic scenic reference art without external assets."""

    from PIL import Image, ImageDraw, ImageFont

    width, height = (760, 760) if cover else (1920, 1080)
    image = Image.new("RGB", (width, height), "#14263E")
    pixels = image.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        if cover:
            top, bottom = (80, 92, 126), (22, 38, 55)
        else:
            top, bottom = (118, 121, 148), (17, 39, 55)
        r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
        for x in range(width):
            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(image, "RGBA")
    horizon = int(height * (0.57 if cover else 0.60))
    mountain = []
    for x in range(0, width + 1, max(4, width // 80)):
        wave = math.sin(x / width * math.tau * 1.7) * 0.055 + math.sin(x / width * math.tau * 4.6) * 0.022
        mountain.append((x, horizon - int(height * wave)))
    mountain += [(width, height), (0, height)]
    draw.polygon(mountain, fill=(13, 31, 43, 235))
    draw.ellipse((int(width * 0.72), int(height * 0.20), int(width * 0.78), int(height * 0.26)), fill=(255, 201, 155, 95))

    if cover:
        frame = int(width * 0.055)
        draw.rounded_rectangle((frame, frame, width - frame, height - frame), radius=24, outline=(255, 255, 255, 95), width=3)
        try:
            font = ImageFont.truetype("DejaVuSerif-Italic.ttf", 76)
            small = ImageFont.truetype("DejaVuSans.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
            small = ImageFont.load_default()
        draw.text((width * 0.18, height * 0.25), "Senja", font=font, fill=(255, 255, 255, 240))
        draw.text((width * 0.29, height * 0.39), "di Kota Ini", font=font, fill=(255, 255, 255, 240))
        draw.text((width * 0.38, height * 0.82), "ALBUM MUSIK", font=small, fill=(232, 239, 247, 210))
    image.save(path, "PNG")


def _fixture_document(root: Path):
    from .editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TimeBinding, Transform, TIMEBASE
    from .spectrum_feature import make_spectrum_layer, normalize_spectrum_properties
    from .spectrum_step08 import centered_transform, preset_properties

    document = ProjectDocument.new_empty("Senja di Kota Ini")
    document.album_title = "Senja di Kota Ini"
    document.canvas.width = 1920
    document.canvas.height = 1080

    wav = root / "Senja-di-Kota-Ini-Full-Album.wav"
    background_path = root / "Background.png"
    cover_path = root / "Cover.png"
    _write_fixture_wav(wav)
    _write_fixture_image(background_path)
    _write_fixture_image(cover_path, cover=True)

    audio = MediaAsset(
        kind="audio",
        locator=str(wav),
        original_name=wav.name,
        source_duration_tick=8 * TIMEBASE,
        metadata={"title": "Senja di Kota Ini", "artist": "FULL ALBUM"},
    )
    background_asset = MediaAsset(kind="image", locator=str(background_path), original_name=background_path.name)
    cover_asset = MediaAsset(kind="image", locator=str(cover_path), original_name=cover_path.name)
    document.media.extend([audio, background_asset, cover_asset])

    titles = (
        "Senja di Kota Ini",
        "Jalan Pulang",
        "Perjalanan Kita",
        "Cerita Baru",
        "Langit yang Sama",
        "Rumah di Hatiku",
        "Sekali Lagi",
        "Waktu dan Kita",
        "Sampai Nanti",
        "Di Ujung Jalan",
    )
    for title in titles:
        document.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                display_artist="FULL ALBUM",
                source_out_tick=8 * TIMEBASE,
                cover_asset_id=cover_asset.asset_id,
            )
        )

    track = next(item for item in document.tracks if item.kind == "visual")
    background = Layer(
        track_id=track.track_id,
        type="background",
        name="Overlay",
        order=0,
        time_binding=TimeBinding(kind="album"),
        asset_refs=[background_asset.asset_id],
        properties={"mode": "asset", "fit": "fill", "playback": "loop", "motion": "static"},
    )
    cover = Layer(
        track_id=track.track_id,
        type="song_cover",
        name="Logo",
        order=1,
        time_binding=TimeBinding(kind="album"),
        transform=Transform(x=0.29, y=0.29, width=0.25, height=0.44),
        properties={"fit": "fill", "fallback_asset_id": cover_asset.asset_id},
    )
    playlist = Layer(
        track_id=track.track_id,
        type="playlist_visual",
        name="Judul",
        order=2,
        time_binding=TimeBinding(kind="album"),
        transform=Transform(x=0.65, y=0.25, width=0.30, height=0.58),
        properties={
            "max_items": 10,
            "font_size": 28,
            "color": "#F0F4FA",
            "active_color": "#FFFFFF",
            "background_opacity": 0.03,
            "show_artist": False,
            "numbered": True,
        },
    )
    spectrum = make_spectrum_layer(track.track_id, 3, preset_id="minimal_bars")
    spectrum.properties = preset_properties("classic", spectrum.properties)
    spectrum.properties = normalize_spectrum_properties(
        {
            **spectrum.properties,
            "spectrum_type": "circular",
            "style": "circular_spectrum",
            "band_count": 128,
            "thickness": 12.0,
            "smoothing": 0.65,
            "reactive_scale": 1.20,
            "accent_color": "#1B8DFF",
            "preset": "classic",
        }
    )
    spectrum.opacity = 0.90
    spectrum.transform = Transform(x=0.20, y=0.15, width=0.47, height=0.70)
    document.layers.extend([background, cover, playlist, spectrum])
    document.validate()
    return document, spectrum.layer_id


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pixel_difference(a: Path, b: Path) -> dict[str, float | int]:
    from PIL import Image, ImageChops, ImageStat

    left = Image.open(a).convert("RGB")
    right = Image.open(b).convert("RGB")
    if left.size != right.size:
        raise RuntimeError(f"Probe size mismatch: {left.size} != {right.size}")
    diff = ImageChops.difference(left, right)
    bbox = diff.getbbox()
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / 3.0
    extrema = max(channel[1] for channel in stat.extrema)
    changed = 0
    if bbox is not None:
        gray = diff.convert("L")
        changed = sum(1 for value in gray.getdata() if value > 2)
    return {
        "different": bbox is not None,
        "mean_abs_difference": float(mean),
        "max_difference": int(extrema),
        "changed_pixels_gt_2": int(changed),
    }


def capture(output: Path, width: int, height: int, scale: float, evidence_dir: Path) -> dict[str, object]:
    os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    _prepare_qt(scale)
    import full_album_maker.main  # noqa: F401

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .preview_service import AccuratePreviewService
    from .spectrum_feature import normalize_spectrum_properties
    from .spectrum_step08 import spectrum_geometry

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    fixture_root = Path(tempfile.mkdtemp(prefix="fam-step08-spectrum-"))
    document, spectrum_id = _fixture_document(fixture_root)
    signature_before = document.content_signature()

    evidence_dir.mkdir(parents=True, exist_ok=True)
    silence = evidence_dir / "spectrum-probe-silence.png"
    loud = evidence_dir / "spectrum-probe-loud.png"
    service = AccuratePreviewService()
    service.render_frame(document, 1 * document.timebase, silence)
    service.render_frame(document, 4 * document.timebase, loud)
    activity = _pixel_difference(silence, loud)

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window.editor_workspace.session.select_one(spectrum_id)
    window.editor_workspace.set_playhead(4 * document.timebase)
    window.foundation_shell.set_workspace("spectrum")
    window._s08_selected_layer_id = spectrum_id
    window._s08_refresh(request_preview=False)
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    app.processEvents()

    window._s08_preview_worker.invalidate()
    window._s08_preview_token = window._s08_preview_worker.generation
    window.spectrum_workspace_s08.set_preview_result(str(loud), "DETERMINISTIC_LOUD")

    live_document = window.editor_workspace.document()
    signature_after = live_document.content_signature()
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot STEP08 Spectrum: {output}")

    shell = window.foundation_shell
    layer = live_document.layer_map()[spectrum_id]
    props = normalize_spectrum_properties(layer.properties)
    geometry = spectrum_geometry(live_document, layer)
    report = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "spectrum_active": shell.workspace_stack.currentWidget() is window.spectrum_workspace_s08,
        "context_visible": not window.spectrum_context_s08.isHidden(),
        "inspector_active": window._inspector_router.currentWidget() is window.spectrum_inspector_s08,
        "timeline_visible": not window.spectrum_timeline_s08.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "layer_count": len(live_document.layers),
        "spectrum_count": len([item for item in live_document.layers if item.type == "spectrum"]),
        "preset_card_count": window.spectrum_context_s08.preset_grid.count(),
        "selected_layer_id": spectrum_id,
        "spectrum_type": props["spectrum_type"],
        "band_count": props["band_count"],
        "thickness": props["thickness"],
        "opacity": layer.opacity,
        "smoothing": props["smoothing"],
        "reactive_scale": props["reactive_scale"],
        "accent_color": props["accent_color"],
        "center_x_px": geometry.center_x_px,
        "center_y_px": geometry.center_y_px,
        "size_ratio": geometry.size_ratio,
        "preview_status": window.spectrum_workspace_s08.preview_status.text(),
        "accurate_frame_installed": True,
        "accurate_frame_source": "deterministic_real_audio_loud_probe",
        "audio_probe": {
            "silence_sha256": _sha(silence),
            "loud_sha256": _sha(loud),
            **activity,
        },
        "content_unchanged_by_route_and_preview": signature_before == signature_after,
        "scale": scale,
        "font_family": font_family,
    }

    window.hide()
    window._s08_preview_worker.close()
    window.deleteLater()
    app.processEvents()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP08 Spectrum evidence")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    ns = parser.parse_args(argv)

    output = Path(ns.output)
    evidence_dir = Path(ns.evidence_dir) if ns.evidence_dir else output.parent
    geometry = capture(output, ns.width, ns.height, ns.scale, evidence_dir)
    result = {"current": str(output), "geometry": geometry}
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())