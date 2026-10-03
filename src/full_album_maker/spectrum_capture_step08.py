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
                # Two fixed tones plus a slow deterministic envelope create a
                # real, repeatable frequency image without random input.
                envelope = 0.55 + 0.35 * math.sin(math.tau * 0.7 * t) ** 2
                value = envelope * (
                    0.58 * math.sin(math.tau * 220.0 * t)
                    + 0.30 * math.sin(math.tau * 880.0 * t)
                )
            sample = max(-32767, min(32767, int(round(value * 32767.0))))
            payload.extend(struct.pack("<h", sample))
        handle.writeframes(bytes(payload))


def _fixture_document(root: Path):
    from .editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TimeBinding, Transform, TIMEBASE
    from .spectrum_feature import make_spectrum_layer, normalize_spectrum_properties
    from .spectrum_step08 import centered_transform, preset_properties

    document = ProjectDocument.new_empty("Senja di Kota Ini")
    document.album_title = "Senja di Kota Ini"
    document.canvas.width = 1920
    document.canvas.height = 1080

    wav = root / "Senja-di-Kota-Ini-Full-Album.wav"
    _write_fixture_wav(wav)
    audio = MediaAsset(
        kind="audio",
        locator=str(wav),
        original_name=wav.name,
        source_duration_tick=8 * TIMEBASE,
        metadata={"title": "Senja di Kota Ini", "artist": "FULL ALBUM"},
    )
    document.media.append(audio)
    document.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Senja di Kota Ini",
            display_artist="FULL ALBUM",
            source_out_tick=8 * TIMEBASE,
        )
    )

    track = next(item for item in document.tracks if item.kind == "visual")
    background = Layer(
        track_id=track.track_id,
        type="background",
        name="Overlay",
        order=0,
        time_binding=TimeBinding(kind="album"),
        properties={"mode": "solid", "color": "#14283D"},
    )
    logo = Layer(
        track_id=track.track_id,
        type="text",
        name="Logo",
        order=1,
        time_binding=TimeBinding(kind="album"),
        transform=Transform(x=0.38, y=0.31, width=0.24, height=0.18),
        properties={
            "text": "Senja\ndi Kota Ini",
            "font_size": 50,
            "color": "#FFFFFF",
            "align": "center",
        },
    )
    title = Layer(
        track_id=track.track_id,
        type="song_title",
        name="Judul",
        order=2,
        time_binding=TimeBinding(kind="album"),
        transform=Transform(x=0.68, y=0.18, width=0.27, height=0.28),
        properties={
            "template": "{title}\n{artist}",
            "font_size": 38,
            "color": "#FFFFFF",
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
    spectrum.transform = centered_transform(document, "circular", size_ratio=0.78)
    document.layers.extend([background, logo, title, spectrum])
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
        # Bounded deterministic metric; exact FFmpeg rasterization can vary by
        # platform, so acceptance checks presence of real activity, not one hash.
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

    # Production installers must be active before FoundationMainWindow is built.
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

    # Let initial route/layout signals settle first. A route activation may have
    # already queued an accurate-preview request, so the deterministic evidence
    # frame must be installed *after* this event loop, not before it.
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    app.processEvents()

    # Invalidate every older async result, then pin the synchronously rendered
    # real-audio loud frame immediately before capture. No later event processing
    # occurs before grab(), so a stale worker cannot overwrite this evidence.
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