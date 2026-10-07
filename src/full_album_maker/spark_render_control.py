from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re

from .advanced_motion_contract import AdvancedMotionPreset
from .animation_signal_contract import AnimationSignalChannel
from .beat_visual_runtime import BeatVisualRuntime
from .editor_models import Layer, TIMEBASE
from .spark_burst_engine import SPARK_LIFETIME_TICK, SPARK_PARTICLES_PER_BURST

SPARK_CONTROL_HZ=8.0
MAX_SPARK_COMMAND_ROWS=220_000


@dataclass(frozen=True)
class SparkRenderControl:
    command_file: Path
    filter_suffix: str
    command_rows: int


def _safe_token(value: str) -> str:
    token=re.sub(r"[^A-Za-z0-9_]","_",value)
    return token[:72] or "spark"


def _ffmpeg_path(value: Path) -> str:
    text=value.resolve().as_posix()
    return text.replace("\\","\\\\").replace(":","\\:").replace("'","\\'")


def _merge(values):
    clean=sorted((max(0,int(a)),max(0,int(b))) for a,b in values if int(b)>=int(a))
    if not clean: return []
    result=[list(clean[0])]
    for start,end in clean[1:]:
        if start <= result[-1][1]+1:
            result[-1][1]=max(result[-1][1],end)
        else:
            result.append([start,end])
    return [(a,b) for a,b in result]


def _intersections(a_values,b_values):
    out=[]
    for a0,a1 in a_values:
        for b0,b1 in b_values:
            s=max(a0,b0); e=min(a1,b1)
            if e>=s: out.append((s,e))
    return _merge(out)


def build_spark_render_control(
    runtime: BeatVisualRuntime | None,
    layer: Layer,
    *,
    base_width: int,
    base_height: int,
    intervals: list[tuple[int,int]],
    work_dir: str | Path,
    stream_key: str,
) -> SparkRenderControl | None:
    if runtime is None or runtime.motion_preset_for_layer(layer.layer_id) != AdvancedMotionPreset.SPARK_BURST:
        return None
    if base_width < 2 or base_height < 2:
        raise ValueError("Spark render membutuhkan ukuran layer minimal 2px.")
    bursts=[
        (t.event_tick,t.event_tick+SPARK_LIFETIME_TICK)
        for t in runtime.phase_engine.triggers(AnimationSignalChannel.STRONG_BEAT)
    ]
    active=_intersections(_merge(bursts),_merge(intervals))
    if not active:
        return None
    step=max(1,int(round(TIMEBASE/SPARK_CONTROL_HZ)))
    ticks=[]
    for start,end in active:
        tick=start
        while tick < end:
            ticks.append(tick); tick += step
        ticks.append(end)
    ticks=sorted(set(ticks))

    token=_safe_token(f"{layer.layer_id}_{stream_key}")
    names=[f"drawbox@beat_spark_{token}_{i}" for i in range(SPARK_PARTICLES_PER_BURST)]
    rows=[]
    last=[None]*SPARK_PARTICLES_PER_BURST
    min_dim=min(base_width,base_height)
    slot_sizes=[max(2,int(round(min_dim*v))) for v in (.006,.007,.008,.0065,.0075,.0085)]

    for tick in ticks:
        particles=runtime.particles_for_layer(layer.layer_id,tick)
        by_index={p.particle_index:p for p in particles}
        ts=tick/TIMEBASE
        for i,name in enumerate(names):
            particle=by_index.get(i)
            if particle is None:
                current=(0,0,0.0)
            else:
                size=slot_sizes[i]
                cx=base_width/2.0 + particle.x_offset_normalized*base_width
                cy=base_height/2.0 + particle.y_offset_normalized*base_height
                x=max(-size,min(base_width,cx-size/2.0))
                y=max(-size,min(base_height,cy-size/2.0))
                current=(int(round(x)),int(round(y)),round(float(particle.alpha),5))
            if current==last[i]:
                continue
            if last[i] is None or current[0]!=last[i][0]:
                rows.append(f"{ts:.6f} {name} x {current[0]};")
            if last[i] is None or current[1]!=last[i][1]:
                rows.append(f"{ts:.6f} {name} y {current[1]};")
            if last[i] is None or current[2]!=last[i][2]:
                rows.append(f"{ts:.6f} {name} color white@{current[2]:.5f};")
            last[i]=current
            if len(rows)>MAX_SPARK_COMMAND_ROWS:
                raise ValueError("Spark render command melebihi batas aman 220000 rows.")

    if not rows:
        return None
    work=Path(work_dir); work.mkdir(parents=True,exist_ok=True)
    command_file=work/f"spark-{token}.sendcmd"
    command_file.write_text("\n".join(rows)+"\n",encoding="utf-8")
    pieces=[f"sendcmd=f='{_ffmpeg_path(command_file)}'"]
    for i,name in enumerate(names):
        size=slot_sizes[i]
        pieces.append(f"{name}=x=0:y=0:w={size}:h={size}:color=white@0:t=fill")
    return SparkRenderControl(command_file,","+",".join(pieces),len(rows))
