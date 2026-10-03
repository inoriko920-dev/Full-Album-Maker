from __future__ import annotations

from pathlib import Path

from .editor_models import Layer, ProjectDocument, TIMEBASE
from .render_graph import (
    CompiledFFmpeg,
    _layer_size,
    _rotation_chain,
    ticks_to_seconds,
)
from .s11_render_graph import S11FFmpegCompiler, _externalize_large_filter_graph
from .timeline_resolver import TimelineResolver
from .visual_precision import visual_settings_for_song


def _filter_option(args: list[str]) -> tuple[int, str, Path | None]:
    if "-filter_complex" in args:
        index = args.index("-filter_complex")
        return index, args[index + 1], None
    if "-/filter_complex" in args:
        index = args.index("-/filter_complex")
        script = Path(args[index + 1])
        return index, script.read_text(encoding="utf-8").strip(), script
    raise ValueError("Filter graph FFmpeg tidak ditemukan.")


def _fit_chain(fit: str, width: int, height: int) -> str:
    if fit == "fill":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0"
    )


def _crop_chain(props: dict) -> str:
    x = float(props["crop_x"])
    y = float(props["crop_y"])
    width = float(props["crop_width"])
    height = float(props["crop_height"])
    if (
        abs(x) < 1e-9
        and abs(y) < 1e-9
        and abs(width - 1.0) < 1e-9
        and abs(height - 1.0) < 1e-9
    ):
        return ""
    return (
        f"crop=w=iw*{width:.8f}:h=ih*{height:.8f}:"
        f"x=iw*{x:.8f}:y=ih*{y:.8f},"
    )


def _image_motion_chain(
    motion: str,
    *,
    enabled: bool,
    width: int,
    height: int,
    fps: float,
    duration: float,
) -> str:
    if not enabled or motion == "static":
        return ""
    frames = max(1, round(max(duration, 0.001) * fps))
    if motion == "ken_burns":
        return (
            f",zoompan=z='min(1.10,1+0.10*on/{frames})':"
            f"x='(iw-iw/zoom)*on/{frames}':"
            f"y='(ih-ih/zoom)*(0.30+0.20*on/{frames})':"
            f"d=1:s={width}x{height}:fps={fps:g}"
        )
    if motion == "zoom_in":
        return (
            f",zoompan=z='min(1.08,1+0.08*on/{frames})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps:g}"
        )
    if motion == "zoom_out":
        return (
            f",zoompan=z='max(1,1.08-0.08*on/{frames})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps:g}"
        )
    if motion in {"pan_left", "pan_right"}:
        if motion == "pan_right":
            x_expr = f"(iw-iw/zoom)*on/{frames}"
        else:
            x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
        return (
            f",zoompan=z='1.08':x='{x_expr}':"
            f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps:g}"
        )
    raise ValueError(f"Motion foto belum didukung: {motion}")


def _slide_x_expression(
    transition: str,
    base_x: str,
    *,
    start: float,
    transition_seconds: float,
) -> str:
    if transition_seconds <= 0 or transition not in {"slide", "slide_left", "slide_right"}:
        return base_x
    end = start + transition_seconds
    progress = f"min(1,max(0,(t-{start:.6f})/{transition_seconds:.6f}))"
    if transition in {"slide", "slide_left"}:
        incoming = f"main_w+({base_x})"
    else:
        incoming = "-overlay_w"
    return f"if(lt(t,{end:.6f}),({incoming})+(({base_x})-({incoming}))*({progress}),({base_x}))"


def _song_visual_size(layer: Layer, document: ProjectDocument, scale: float) -> tuple[int, int]:
    base_width, base_height = _layer_size(layer, document)
    return (
        max(2, round(base_width * float(scale))),
        max(2, round(base_height * float(scale))),
    )


def _song_visual_position_expr(layer: Layer, props: dict, axis: str) -> str:
    if axis == "x":
        slot_start = float(layer.transform.x)
        slot_size = float(layer.transform.width)
        offset = float(props["position_x"])
        main = "main_w"
        overlay = "overlay_w"
    else:
        slot_start = float(layer.transform.y)
        slot_size = float(layer.transform.height)
        offset = float(props["position_y"])
        main = "main_h"
        overlay = "overlay_h"
    return (
        f"({slot_start:.8f}*{main})+"
        f"(({slot_size:.8f}*{main})-{overlay})/2+"
        f"({offset:.8f}*{main})"
    )


class V13FFmpegCompiler(S11FFmpegCompiler):
    """S11 compiler plus dynamic per-song image/video compositing.

    STEP06 keeps the recovered v1.3 composition path and adds per-song
    non-destructive visual overrides. Projects without STEP06 metadata retain the
    original shared-layer behavior through the fallback contract.

    STEP09 prerequisite adds one normal Visual-domain field, ``video_speed``.
    It changes only video timestamps in the visual filter chain. Audio events,
    song timing, render-plan duration, and audible gain remain untouched.
    """

    def compile_video(
        self,
        document: ProjectDocument,
        destination: str | Path,
        work_dir: str | Path,
        *,
        include_audio: bool = True,
    ) -> CompiledFFmpeg:
        visual_layers = [
            layer
            for layer in sorted(document.layers, key=lambda item: item.order)
            if layer.enabled and layer.type == "song_visual"
        ]
        if not visual_layers:
            return super().compile_video(
                document,
                destination,
                work_dir,
                include_audio=include_audio,
            )

        track_map = {track.track_id: track for track in document.tracks}
        visual_layers = [
            layer
            for layer in visual_layers
            if track_map.get(layer.track_id) and track_map[layer.track_id].enabled
        ]
        if not visual_layers:
            return super().compile_video(
                document,
                destination,
                work_dir,
                include_audio=include_audio,
            )

        clean = document.clone()
        visual_ids = {layer.layer_id for layer in visual_layers}
        clean.layers = [layer for layer in clean.layers if layer.layer_id not in visual_ids]
        compiled = super().compile_video(
            clean,
            destination,
            work_dir,
            include_audio=include_audio,
        )

        args = list(compiled.args)
        filter_index, graph, graph_script = _filter_option(args)
        parts = graph.split(";")
        base_index = next(
            (
                index
                for index, part in enumerate(parts)
                if part.startswith("[0:v]") and part.endswith("[v0]")
            ),
            None,
        )
        if base_index is None:
            raise ValueError("Base video [v0] tidak ditemukan untuk Song Visual.")

        assets = document.asset_map()
        songs = document.song_map()
        plan_events = list(compiled.render_plan.audio_events)
        resolved = TimelineResolver().resolve(document)
        resolved_by_layer = {item.layer_id: item for item in resolved.layers}
        fps = document.canvas.fps_num / document.canvas.fps_den
        duration_tick = compiled.render_plan.duration_tick

        next_input = sum(1 for value in args if value == "-i")
        extra_inputs: list[str] = []
        visual_filters: list[str] = []
        current = "svbase"
        parts[base_index] = parts[base_index][:-4] + f"[{current}]"
        sequence = 0

        for layer in visual_layers:
            fallback_properties = dict(layer.properties)
            rotate = _rotation_chain(layer)
            opacity = max(0.0, min(1.0, float(layer.opacity)))
            layer_resolved = resolved_by_layer.get(layer.layer_id)
            layer_intervals = (
                []
                if layer_resolved is None
                else [
                    (item.start_tick, item.end_tick)
                    for item in layer_resolved.intervals
                ]
            )

            for event_index, event in enumerate(plan_events):
                song = songs[event.song_id]
                asset_id = song.visual_asset_id
                if not asset_id:
                    continue
                asset = assets.get(asset_id)
                if asset is None or asset.kind not in {"image", "video"}:
                    raise ValueError(
                        "visual_asset_id lagu harus merujuk image/video yang valid."
                    )

                props = visual_settings_for_song(
                    document,
                    song.song_id,
                    fallback_layer_properties=fallback_properties,
                )
                width, height = _song_visual_size(layer, document, props["scale"])
                base_x = _song_visual_position_expr(layer, props, "x")
                base_y = _song_visual_position_expr(layer, props, "y")

                intersection_start = event.start_tick
                intersection_end = event.end_tick
                if layer_intervals:
                    candidates = [
                        (max(event.start_tick, start), min(event.end_tick, end))
                        for start, end in layer_intervals
                        if min(event.end_tick, end) > max(event.start_tick, start)
                    ]
                    if not candidates:
                        continue
                    intersection_start = min(start for start, _ in candidates)
                    intersection_end = max(end for _, end in candidates)

                event_duration = max(1, intersection_end - intersection_start)
                transition = min(
                    float(props["transition_seconds"]),
                    ticks_to_seconds(event_duration) / 2.0,
                )
                transition_tick = int(round(transition * TIMEBASE))
                visual_end_tick = intersection_end
                if props["transition"] != "cut" and event_index + 1 < len(plan_events):
                    visual_end_tick = min(
                        duration_tick,
                        visual_end_tick + transition_tick,
                    )
                visual_duration = ticks_to_seconds(
                    max(1, visual_end_tick - intersection_start)
                )
                start_seconds = ticks_to_seconds(intersection_start)
                end_seconds = ticks_to_seconds(visual_end_tick)

                if asset.kind == "image":
                    extra_inputs += ["-loop", "1", "-i", asset.locator]
                else:
                    if props["loop_video"]:
                        extra_inputs += [
                            "-stream_loop",
                            "-1",
                            "-an",
                            "-i",
                            asset.locator,
                        ]
                    else:
                        extra_inputs += ["-an", "-i", asset.locator]
                input_index = next_input
                next_input += 1

                source = f"svsrc{sequence}"
                output = f"sv{sequence}"
                sequence += 1
                crop = _crop_chain(props)
                geometry = _fit_chain(props["fit"], width, height)
                chain = f"[{input_index}:v]{crop}{geometry}"
                if asset.kind == "image":
                    chain += _image_motion_chain(
                        props["image_motion"],
                        enabled=bool(props["pan_zoom"]),
                        width=width,
                        height=height,
                        fps=fps,
                        duration=visual_duration,
                    )
                else:
                    speed = float(props["video_speed"])
                    if abs(speed - 1.0) > 1e-9:
                        # FFmpeg video slow/fast motion is local to this visual
                        # stream. 0.5x => timestamps doubled; master audio is not
                        # routed through this chain.
                        chain += f",setpts=PTS/{speed:.8f}"
                chain += f",fps={fps:g}"
                if asset.kind == "video" and props["freeze_end"]:
                    # Extend the decoded source by cloning its last frame. The
                    # final trim below bounds it to the song visual interval.
                    chain += f",tpad=stop_mode=clone:stop_duration={visual_duration:.6f}"
                chain += (
                    f",trim=duration={visual_duration:.6f},"
                    "setpts=PTS-STARTPTS,format=rgba"
                )
                if props["transition"] == "fade" and transition > 0:
                    chain += f",fade=t=in:st=0:d={transition:.6f}:alpha=1"
                chain += f",colorchannelmixer=aa={opacity:.6f}{rotate}"
                if start_seconds > 0:
                    chain += f",setpts=PTS+{start_seconds:.6f}/TB"
                chain += f"[{source}]"
                visual_filters.append(chain)

                x_expr = _slide_x_expression(
                    props["transition"],
                    base_x,
                    start=start_seconds,
                    transition_seconds=transition,
                )
                visual_filters.append(
                    f"[{current}][{source}]overlay=x='{x_expr}':y='{base_y}':"
                    f"shortest=0:eof_action=pass:enable='between(t,{start_seconds:.6f},{end_seconds:.6f})'"
                    f"[{output}]"
                )
                current = output

        visual_filters.append(f"[{current}]null[v0]")

        parts[base_index + 1 : base_index + 1] = visual_filters
        new_graph = ";".join(parts)

        args[filter_index:filter_index] = extra_inputs
        if graph_script is None:
            # filter_index moved to the right by inserted inputs.
            new_filter_index = filter_index + len(extra_inputs)
            args[new_filter_index + 1] = new_graph
        else:
            graph_script.write_text(new_graph + "\n", encoding="utf-8")

        result = CompiledFFmpeg(
            tuple(args),
            compiled.render_plan,
            compiled.text_files,
        )
        return _externalize_large_filter_graph(result, work_dir)
