from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re

from .beat_render_control import MAX_COMMAND_ROWS
from .beat_visual_runtime import BeatVisualRuntime
from .editor_models import Layer, TIMEBASE
from .visual_binding_contract import VisualProperty


class BeatTextRenderControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class BeatTextRenderControl:
    command_file: Path
    sendcmd_filter: str
    drawtext_filter: str
    command_rows: int


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return token[:80] or "beat_text"


def _ffmpeg_path(value: Path) -> str:
    text = value.resolve().as_posix()
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _merge_intervals(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
    clean = sorted((max(0, int(a)), max(0, int(b))) for a, b in values if int(b) >= int(a))
    if not clean:
        return []
    merged = [list(clean[0])]
    for start, end in clean[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def _intersections(a_values: list[tuple[int, int]], b_values: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for a0, a1 in a_values:
        for b0, b1 in b_values:
            start = max(a0, b0)
            end = min(a1, b1)
            if end >= start:
                result.append((start, end))
    return _merge_intervals(result)


def build_beat_text_render_control(
    runtime: BeatVisualRuntime | None,
    layer: Layer,
    *,
    base_fontsize: int,
    canvas_width: int,
    canvas_height: int,
    fps: float,
    intervals: list[tuple[int, int]],
    work_dir: str | Path,
    stream_key: str,
) -> BeatTextRenderControl | None:
    if runtime is None or not runtime.has_layer(layer.layer_id):
        return None
    if layer.type not in {"text", "song_title"}:
        raise BeatTextRenderControlError("Beat text control hanya untuk text/song_title.")
    if base_fontsize < 4:
        raise BeatTextRenderControlError("Font size Beat text minimal 4px.")
    if canvas_width <= 0 or canvas_height <= 0:
        raise BeatTextRenderControlError("Ukuran canvas Beat text tidak valid.")
    if fps <= 0 or not math.isfinite(float(fps)):
        raise BeatTextRenderControlError("FPS Beat text tidak valid.")

    bindings = runtime.binding_set(layer.layer_id).bindings
    props = {binding.property for binding in bindings}
    if VisualProperty.ROTATION_OFFSET_DEG in props:
        raise BeatTextRenderControlError("Rotation Nudge belum didukung untuk Text/Title.")
    unsupported = props & {
        VisualProperty.X_OFFSET_NORMALIZED,
        VisualProperty.Y_OFFSET_NORMALIZED,
    }
    if unsupported:
        names = ", ".join(sorted(p.value for p in unsupported))
        raise BeatTextRenderControlError(f"Properti Beat text belum didukung: {names}")

    channels = {binding.channel for binding in bindings}
    trigger_windows = [
        (trigger.start_tick, trigger.end_tick)
        for trigger in runtime.signal_engine.program.triggers
        if trigger.channel in channels
    ]
    active = _intersections(_merge_intervals(trigger_windows), _merge_intervals(intervals))
    if not active:
        return None

    control_hz = min(30.0, float(fps))
    step = max(1, int(round(TIMEBASE / control_hz)))
    ticks: list[int] = []
    for start, end in active:
        tick = start
        while tick < end:
            ticks.append(tick)
            tick += step
        ticks.append(end)
    ticks = sorted(set(ticks))

    token = _safe_token(f"{layer.layer_id}_{stream_key}")
    target = f"drawtext@beat_text_{token}"
    rows: list[str] = []
    last: tuple[int, int, float, float, float] | None = None
    base_x = float(layer.transform.x) * float(canvas_width)
    base_y = float(layer.transform.y) * float(canvas_height)
    base_w = float(layer.transform.width) * float(canvas_width)
    base_h = float(layer.transform.height) * float(canvas_height)
    pivot_x = float(layer.transform.pivot_x)
    pivot_y = float(layer.transform.pivot_y)
    for tick in ticks:
        state = runtime.state_for_layer(layer.layer_id, tick)
        factor = max(0.50, min(2.00, float(state.scale_multiplier) * float(state.zoom_multiplier)))
        fontsize = max(4, int(round(base_fontsize * factor)))
        borderw = max(0, min(16, int(round(4.0 * float(state.glow_amount)))))
        alpha = max(0.0, min(1.0, float(state.opacity_multiplier)))
        x = base_x - pivot_x * base_w * (factor - 1.0) + float(state.x_offset_normalized) * float(canvas_width)
        y = base_y - pivot_y * base_h * (factor - 1.0) + float(state.y_offset_normalized) * float(canvas_height)
        current = (fontsize, borderw, round(alpha, 7), round(x, 6), round(y, 6))
        if current == last:
            continue
        ts = tick / TIMEBASE
        if last is None or current[0] != last[0]:
            rows.append(f"{ts:.6f} {target} fontsize {fontsize};")
        if last is None or current[1] != last[1]:
            rows.append(f"{ts:.6f} {target} borderw {borderw};")
        if last is None or current[3] != last[3]:
            rows.append(f"{ts:.6f} {target} x {x:.6f};")
        if last is None or current[4] != last[4]:
            rows.append(f"{ts:.6f} {target} y {y:.6f};")
        if VisualProperty.OPACITY_MULTIPLIER in props and (last is None or current[2] != last[2]):
            rows.append(f"{ts:.6f} {target} alpha {alpha:.7f};")
        if len(rows) > MAX_COMMAND_ROWS:
            raise BeatTextRenderControlError("Beat text command melebihi batas aman 250000 rows.")
        last = current

    if not rows:
        return None
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    command_file = work / f"beat-text-{token}.sendcmd"
    command_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return BeatTextRenderControl(
        command_file=command_file,
        sendcmd_filter=f"sendcmd=f='{_ffmpeg_path(command_file)}'",
        drawtext_filter=target,
        command_rows=len(rows),
    )
