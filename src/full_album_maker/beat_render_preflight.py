from __future__ import annotations

from dataclasses import dataclass
import math

from .editor_models import TIMEBASE
from .ffmpeg_command_batch import MAX_COMMAND_FILE_BYTES, MAX_COMMAND_OPS, MAX_COMMAND_ROWS


@dataclass(frozen=True)
class CommandLoadEstimate:
    sample_ticks: int
    command_rows_upper_bound: int
    command_ops_upper_bound: int
    estimated_bytes: int

    def validate(self) -> None:
        for name in ("sample_ticks","command_rows_upper_bound","command_ops_upper_bound","estimated_bytes"):
            if int(getattr(self,name)) < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def within_limits(self) -> bool:
        return (
            self.command_rows_upper_bound <= MAX_COMMAND_ROWS
            and self.command_ops_upper_bound <= MAX_COMMAND_OPS
            and self.estimated_bytes <= MAX_COMMAND_FILE_BYTES
        )


def estimate_command_load(
    active_duration_tick: int,
    control_hz: float,
    active_property_count: int,
    spark_bursts: int = 0,
    *,
    spark_hz: float = 8.0,
    spark_lifetime_ms: int = 220,
    spark_ops_per_tick: int = 18,
) -> CommandLoadEstimate:
    duration=max(0,int(active_duration_tick))
    hz=float(control_hz)
    if not math.isfinite(hz) or hz <= 0:
        raise ValueError("control_hz must be positive finite")
    props=max(0,int(active_property_count))
    burst_count=max(0,int(spark_bursts))
    seconds=duration/TIMEBASE
    ticks=0 if duration==0 else int(math.ceil(seconds*hz))+1
    base_rows=ticks if props else 0
    base_ops=ticks*props
    spark_ticks_per_burst=int(math.ceil((spark_lifetime_ms/1000.0)*spark_hz))+1
    spark_rows=burst_count*spark_ticks_per_burst
    spark_ops=spark_rows*max(0,int(spark_ops_per_tick))
    rows=base_rows+spark_rows
    ops=base_ops+spark_ops
    # Conservative ~72 bytes per operation + timestamp/separators.
    bytes_est=(ops*72)+(rows*16)
    result=CommandLoadEstimate(ticks,rows,ops,bytes_est); result.validate(); return result
