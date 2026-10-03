from __future__ import annotations

import re
from pathlib import Path

from .circular_spectrum import circular_spectrum_filter
from .editor_models import Layer, ProjectDocument
from .render_graph import (
    CompiledFFmpeg,
    _color,
    _ffmpeg_scale,
    _layer_size,
    _rotation_chain,
)
from .s11_render_graph import _externalize_large_filter_graph
from .spectrum_feature import normalize_spectrum_properties, smoothing_to_averaging
from .v13_render_graph import V13FFmpegCompiler, _filter_option


_SPECTRUM_SOURCE = re.compile(r"^\[specaudio(?P<index>\d+)\].*(?P<output>\[spec\d+\])$")


def _active_spectrum_layers(document: ProjectDocument) -> tuple[Layer, ...]:
    tracks = {track.track_id: track for track in document.tracks}
    return tuple(
        layer
        for layer in sorted(document.layers, key=lambda item: item.order)
        if layer.enabled
        and layer.type == "spectrum"
        and layer.track_id in tracks
        and tracks[layer.track_id].enabled
    )


def _thickness_chain(thickness: float) -> str:
    """Approximate positive project-pixel line width via bounded morphology.

    Dilation is applied only after the analyzer image has been scaled into the
    layer's project/render dimensions, so each iteration is a render-space pixel
    operation rather than a preview-widget pixel operation. The chain is bounded
    to avoid pathological cost for large user-entered values.
    """

    iterations = max(0, min(8, int(round((float(thickness) - 1.0) / 2.0))))
    return ",dilation" * iterations


def _spectrum_source_chain(document: ProjectDocument, layer: Layer, audio_index: int, output_label: str) -> str:
    props = normalize_spectrum_properties(layer.properties)
    width, height = _layer_size(layer, document)
    style = props["style"]
    color = _color(props["accent_color"])
    gain = float(props["reactive_scale"])
    ascale = _ffmpeg_scale(props["amplitude_scale"])
    fscale = _ffmpeg_scale(props["frequency_scale"])
    alpha = max(0.0, min(1.0, float(layer.opacity)))
    rotate = _rotation_chain(layer)
    mirror = ",vflip" if props["mirror"] else ""

    if style == "circular_spectrum":
        visual = circular_spectrum_filter(
            width=width,
            height=height,
            color=color,
            frequency_scale=fscale,
            amplitude_scale=ascale,
            inner_ratio=props["inner_ratio"],
            band_count=props["band_count"],
            thickness=props["thickness"],
            smoothing=props["smoothing"],
        )
    elif style in {"bars", "spectrum_line"}:
        mode = "bar" if style == "bars" else "line"
        averaging = smoothing_to_averaging(props["smoothing"])
        # Frequency analysis really runs at band_count horizontal samples. It is
        # then mapped to the persisted layer geometry, so changing band_count is
        # not decorative and does not rebuild the source audio.
        visual = (
            f"showfreqs=s={props['band_count']}x{height}:mode={mode}:"
            f"fscale={fscale}:ascale={ascale}:averaging={averaging}:colors={color},"
            f"scale={width}:{height}:flags=neighbor,format=rgba,"
            "colorkey=0x000000:0.08:0.0"
            + _thickness_chain(props["thickness"])
        )
    else:
        split = ":split_channels=1" if style == "stereo_waveform" else ""
        visual = (
            f"showwaves=s={width}x{height}:mode=line:scale={ascale}:colors={color}{split},"
            "format=rgba,colorkey=0x000000:0.08:0.0"
            + _thickness_chain(props["thickness"])
        )

    return (
        f"[specaudio{audio_index}]volume={gain:.6f},{visual},"
        f"colorchannelmixer=aa={alpha:.6f}{mirror}{rotate}{output_label}"
    )


def apply_step08_spectrum_graph(
    compiled: CompiledFFmpeg,
    document: ProjectDocument,
    work_dir: str | Path,
) -> CompiledFFmpeg:
    layers = _active_spectrum_layers(document)
    if not layers:
        return compiled

    args = list(compiled.args)
    try:
        filter_index, graph, graph_script = _filter_option(args)
    except ValueError:
        return compiled
    parts = graph.split(";")
    replaced: set[int] = set()
    rebuilt: list[str] = []
    for part in parts:
        match = _SPECTRUM_SOURCE.match(part)
        if match is None:
            rebuilt.append(part)
            continue
        index = int(match.group("index"))
        if not 0 <= index < len(layers):
            rebuilt.append(part)
            continue
        rebuilt.append(
            _spectrum_source_chain(
                document,
                layers[index],
                index,
                match.group("output"),
            )
        )
        replaced.add(index)

    expected = set(range(len(layers)))
    if replaced != expected:
        missing = sorted(expected - replaced)
        raise ValueError(f"STEP08 tidak dapat memetakan source Spectrum ke render graph: {missing}")

    new_graph = ";".join(rebuilt)
    if graph_script is None:
        args[filter_index + 1] = new_graph
    else:
        graph_script.write_text(new_graph + "\n", encoding="utf-8")
    result = CompiledFFmpeg(tuple(args), compiled.render_plan, compiled.text_files)
    return _externalize_large_filter_graph(result, work_dir)


class Step08FFmpegCompiler(V13FFmpegCompiler):
    """V13 compiler with additive STEP08 Spectrum parameter mapping only."""

    def compile_video(
        self,
        document: ProjectDocument,
        destination: str | Path,
        work_dir: str | Path,
        *,
        include_audio: bool = True,
    ) -> CompiledFFmpeg:
        compiled = super().compile_video(
            document,
            destination,
            work_dir,
            include_audio=include_audio,
        )
        return apply_step08_spectrum_graph(compiled, document, work_dir)
