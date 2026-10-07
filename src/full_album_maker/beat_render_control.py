from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re

from .editor_models import Layer, TIMEBASE
from .visual_binding_contract import VisualProperty
from .beat_visual_runtime import BeatVisualRuntime
from .spark_render_control import build_spark_render_control

MAX_COMMAND_ROWS = 250_000
MAX_BEAT_RENDER_LAYERS = 4


class BeatRenderControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class BeatRenderControl:
    command_file: Path
    sendcmd_filter: str
    scale_filter: str | None
    rotate_filter: str | None
    glow_filter: str | None
    overlay_filter: str
    overlay_x_expr: str
    overlay_y_expr: str
    command_rows: int
    spark_filter_suffix: str


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return token[:80] or "beat"


def _ffmpeg_path(value: Path) -> str:
    text = value.resolve().as_posix()
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _merge_intervals(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
    clean = sorted((max(0, int(a)), max(0, int(b))) for a, b in values if int(b) >= int(a))
    if not clean:
        return []
    merged=[list(clean[0])]
    for start,end in clean[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start,end])
    return [(a,b) for a,b in merged]


def _intersections(a_values: list[tuple[int,int]], b_values: list[tuple[int,int]]) -> list[tuple[int,int]]:
    result=[]
    for a0,a1 in a_values:
        for b0,b1 in b_values:
            start=max(a0,b0); end=min(a1,b1)
            if end >= start:
                result.append((start,end))
    return _merge_intervals(result)


def _properties(runtime: BeatVisualRuntime, layer_id: str) -> set[VisualProperty]:
    return {binding.property for binding in runtime.binding_set(layer_id).bindings}


def build_beat_render_control(
    runtime: BeatVisualRuntime | None,
    layer: Layer,
    *,
    base_width: int,
    base_height: int,
    fps: float,
    intervals: list[tuple[int,int]],
    work_dir: str | Path,
    stream_key: str,
) -> BeatRenderControl | None:
    if runtime is None or not runtime.has_layer(layer.layer_id):
        return None
    if base_width < 2 or base_height < 2:
        raise BeatRenderControlError("Beat render membutuhkan ukuran layer minimal 2px.")
    if fps <= 0 or not math.isfinite(float(fps)):
        raise BeatRenderControlError("FPS Beat render tidak valid.")

    props = _properties(runtime, layer.layer_id)
    unsupported = props & {
        VisualProperty.OPACITY_MULTIPLIER,
    }
    if unsupported:
        names=", ".join(sorted(p.value for p in unsupported))
        raise BeatRenderControlError(f"Properti Beat render V1 belum didukung: {names}")
    if VisualProperty.ROTATION_OFFSET_DEG in props:
        if abs(float(layer.transform.rotation)) > 1e-6:
            raise BeatRenderControlError("Rotation Nudge V1 membutuhkan base rotation 0°.")
        if abs(float(layer.transform.pivot_x)-0.5)>1e-6 or abs(float(layer.transform.pivot_y)-0.5)>1e-6:
            raise BeatRenderControlError("Rotation Nudge V1 membutuhkan center pivot.")

    channels={binding.channel for binding in runtime.binding_set(layer.layer_id).bindings}
    trigger_windows=[
        (trigger.start_tick, trigger.end_tick)
        for trigger in runtime.signal_engine.program.triggers
        if trigger.channel in channels
    ]
    if not trigger_windows:
        return None
    active=_intersections(_merge_intervals(trigger_windows), _merge_intervals(intervals))
    if not active:
        return None

    control_hz=min(30.0, float(fps))
    step=max(1, int(round(TIMEBASE/control_hz)))
    ticks=[]
    for start,end in active:
        tick=start
        while tick < end:
            ticks.append(tick); tick += step
        ticks.append(end)
    ticks=sorted(set(ticks))

    token=_safe_token(f"{layer.layer_id}_{stream_key}")
    scale_name=f"scale@beat_size_{token}" if props & {VisualProperty.SCALE_MULTIPLIER,VisualProperty.ZOOM_MULTIPLIER} else None
    rotate_name=f"rotate@beat_rotate_{token}" if VisualProperty.ROTATION_OFFSET_DEG in props else None
    glow_name=f"eq@beat_glow_{token}" if VisualProperty.GLOW_AMOUNT in props else None
    overlay_name=f"overlay@beat_overlay_{token}"

    pivot_project_x=float(layer.transform.x)+float(layer.transform.pivot_x)*float(layer.transform.width)
    pivot_project_y=float(layer.transform.y)+float(layer.transform.pivot_y)*float(layer.transform.height)
    x_expr=f"({pivot_project_x:.10f}*main_w)-({float(layer.transform.pivot_x):.10f}*overlay_w)"
    y_expr=f"({pivot_project_y:.10f}*main_h)-({float(layer.transform.pivot_y):.10f}*overlay_h)"

    rows=[]
    last=None
    for tick in ticks:
        state=runtime.state_for_layer(layer.layer_id,tick)
        factor=max(0.25,min(1.75,float(state.scale_multiplier)*float(state.zoom_multiplier)))
        width=max(2,int(round(base_width*factor)))
        height=max(2,int(round(base_height*factor)))
        rotation=float(state.rotation_offset_deg)
        glow=float(state.glow_amount)
        x_offset=float(state.x_offset_normalized)
        y_offset=float(state.y_offset_normalized)
        current=(width,height,round(rotation,7),round(glow,7),round(x_offset,9),round(y_offset,9))
        if current==last:
            continue
        ts=tick/TIMEBASE
        if scale_name is not None and (last is None or current[:2]!=last[:2]):
            rows.append(f"{ts:.6f} {scale_name} width {width};")
            rows.append(f"{ts:.6f} {scale_name} height {height};")
        if rotate_name is not None and (last is None or current[2]!=last[2]):
            rows.append(f"{ts:.6f} {rotate_name} angle {math.radians(rotation):.10f};")
        if glow_name is not None and (last is None or current[3]!=last[3]):
            brightness=max(-1.0,min(1.0,0.12*glow))
            saturation=max(0.0,min(3.0,1.0+0.15*glow))
            rows.append(f"{ts:.6f} {glow_name} brightness {brightness:.8f};")
            rows.append(f"{ts:.6f} {glow_name} saturation {saturation:.8f};")
        if VisualProperty.X_OFFSET_NORMALIZED in props and (last is None or current[4]!=last[4]):
            x_command=f"({pivot_project_x:.10f}*main_w)-({float(layer.transform.pivot_x):.10f}*overlay_w)+({x_offset:.10f}*main_w)"
            rows.append(f"{ts:.6f} {overlay_name} x {x_command};")
        if VisualProperty.Y_OFFSET_NORMALIZED in props and (last is None or current[5]!=last[5]):
            y_command=f"({pivot_project_y:.10f}*main_h)-({float(layer.transform.pivot_y):.10f}*overlay_h)+({y_offset:.10f}*main_h)"
            rows.append(f"{ts:.6f} {overlay_name} y {y_command};")
        if len(rows)>MAX_COMMAND_ROWS:
            raise BeatRenderControlError("Beat render command melebihi batas aman 250000 rows.")
        last=current

    spark_control = build_spark_render_control(
        runtime,
        layer,
        base_width=base_width,
        base_height=base_height,
        intervals=intervals,
        work_dir=work_dir,
        stream_key=stream_key,
    )
    if not rows and spark_control is None:
        return None
    work=Path(work_dir); work.mkdir(parents=True,exist_ok=True)
    command_file=work/f"beat-{token}.sendcmd"
    command_file.write_text("\n".join(rows)+"\n",encoding="utf-8")
    sendcmd=f"sendcmd=f='{_ffmpeg_path(command_file)}'" if rows else ""
    return BeatRenderControl(
        command_file=command_file,
        sendcmd_filter=sendcmd,
        scale_filter=scale_name,
        rotate_filter=rotate_name,
        glow_filter=glow_name,
        overlay_filter=overlay_name,
        overlay_x_expr=x_expr,
        overlay_y_expr=y_expr,
        command_rows=len(rows) + (spark_control.command_rows if spark_control is not None else 0),
        spark_filter_suffix=spark_control.filter_suffix if spark_control is not None else "",
    )


def render_filter_suffix(
    control: BeatRenderControl,
    *,
    base_width: int,
    base_height: int,
) -> str:
    pieces=[control.sendcmd_filter] if control.sendcmd_filter else []
    if control.scale_filter:
        pieces.append(f"{control.scale_filter}=w={base_width}:h={base_height}:eval=init")
    if control.glow_filter:
        pieces.append(f"{control.glow_filter}=brightness=0:saturation=1:eval=init")
    if control.rotate_filter:
        pieces.append(f"{control.rotate_filter}=angle=0:ow=iw:oh=ih:c=none")
    base = "," + ",".join(pieces) if pieces else ""
    return base + control.spark_filter_suffix
