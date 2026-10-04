from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.spectrum_feature import make_spectrum_layer, normalize_spectrum_properties
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler
from full_album_maker.spectrum_step08 import centered_transform, preset_properties


def _doc(tmp_path: Path, *, circular: bool) -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP08 render")
    doc.canvas.width = 1920
    doc.canvas.height = 1080
    audio = MediaAsset(
        kind="audio",
        locator=str(tmp_path / "deterministic.wav"),
        original_name="deterministic.wav",
        source_duration_tick=4 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Senja di Kota Ini",
            source_out_tick=4 * TIMEBASE,
        )
    )
    track = next(item for item in doc.tracks if item.kind == "visual")
    layer = make_spectrum_layer(track.track_id, 0, preset_id="minimal_bars")
    props = preset_properties("classic", layer.properties)
    if circular:
        props = normalize_spectrum_properties(
            {**props, "spectrum_type": "circular", "style": "circular_spectrum"}
        )
    layer.properties = props
    layer.transform = centered_transform(doc, "circular" if circular else "linear", size_ratio=0.78)
    layer.opacity = 0.90
    doc.layers.append(layer)
    doc.validate()
    return doc


def _graph(compiled) -> str:
    args = list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex") + 1]
    if "-/filter_complex" in args:
        return Path(args[args.index("-/filter_complex") + 1]).read_text(encoding="utf-8")
    raise AssertionError("filter graph missing")


def test_circular_renderer_consumes_band_count_smoothing_thickness_reactive_and_color(tmp_path: Path) -> None:
    doc = _doc(tmp_path, circular=True)
    graph = _graph(
        Step08FFmpegCompiler("ffmpeg").compile_video(
            doc, tmp_path / "out.mp4", tmp_path / "work"
        )
    )
    assert "[specaudio0]volume=1.200000,showfreqs=s=128x512" in graph
    assert "averaging=11" in graph
    assert "scale=512:512:flags=neighbor" in graph
    assert "atan2(" in graph and "hypot(" in graph
    assert "colorchannelmixer=rr=" in graph
    assert "aa=0.900000" in graph
    assert "[aout]volume=1.200000" not in graph


def test_band_count_and_thickness_change_real_filter_geometry(tmp_path: Path) -> None:
    doc = _doc(tmp_path, circular=True)
    layer = doc.layers[0]
    graph_a = _graph(
        Step08FFmpegCompiler("ffmpeg").compile_video(
            doc, tmp_path / "a.mp4", tmp_path / "work-a"
        )
    )
    layer.properties = normalize_spectrum_properties(
        {**layer.properties, "band_count": 64, "thickness": 4.0}
    )
    graph_b = _graph(
        Step08FFmpegCompiler("ffmpeg").compile_video(
            doc, tmp_path / "b.mp4", tmp_path / "work-b"
        )
    )
    assert "showfreqs=s=128x512" in graph_a
    assert "showfreqs=s=64x512" in graph_b
    assert graph_a != graph_b
    # Radial source expressions change because thickness is converted from final
    # project pixels into the polar geometry band.
    assert "min(W,H)*0.465" in graph_a or "min(W,H)*0.46" in graph_a


def test_linear_renderer_uses_band_resolution_time_averaging_and_render_space_thickness(tmp_path: Path) -> None:
    doc = _doc(tmp_path, circular=False)
    layer = doc.layers[0]
    layer.properties = normalize_spectrum_properties(
        {
            **layer.properties,
            "band_count": 96,
            "thickness": 7.0,
            "smoothing": 0.40,
            "reactive_scale": 1.30,
            "accent_color": "#1B8DFF",
        }
    )
    graph = _graph(
        Step08FFmpegCompiler("ffmpeg").compile_video(
            doc, tmp_path / "linear.mp4", tmp_path / "work-linear"
        )
    )
    assert "[specaudio0]volume=1.300000,showfreqs=s=96x" in graph
    assert "averaging=7" in graph
    assert "flags=neighbor" in graph
    assert graph.count(",dilation") >= 2
    assert "colors=0x1B8DFF" in graph


def test_smoothing_zero_preserves_single_frame_averaging(tmp_path: Path) -> None:
    doc = _doc(tmp_path, circular=False)
    layer = doc.layers[0]
    layer.properties = normalize_spectrum_properties({**layer.properties, "smoothing": 0.0})
    graph = _graph(
        Step08FFmpegCompiler("ffmpeg").compile_video(
            doc, tmp_path / "zero.mp4", tmp_path / "work-zero"
        )
    )
    assert "averaging=1" in graph
