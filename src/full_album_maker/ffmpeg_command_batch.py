from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import math

MAX_COMMAND_ROWS = 250_000
MAX_COMMAND_OPS = 1_500_000
MAX_COMMAND_FILE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class CommandOp:
    target: str
    command: str
    argument: str

    def validate(self) -> None:
        if not self.target.strip() or not self.command.strip() or not str(self.argument).strip():
            raise ValueError("FFmpeg command op fields must be non-empty")


@dataclass(frozen=True)
class CommandBatch:
    timestamp: float
    ops: tuple[CommandOp, ...]

    def validate(self) -> None:
        if not math.isfinite(float(self.timestamp)) or self.timestamp < 0:
            raise ValueError("FFmpeg command timestamp must be non-negative finite")
        if not self.ops:
            raise ValueError("FFmpeg command batch requires at least one operation")
        for op in self.ops:
            op.validate()


@dataclass(frozen=True)
class CommandFileMetrics:
    rows: int
    ops: int
    bytes: int


class CommandLimitError(ValueError):
    pass


_COMMAND_RANK = {
    "width": 0,
    "height": 1,
    "angle": 2,
    "brightness": 3,
    "saturation": 4,
    "x": 5,
    "y": 6,
    "color": 7,
}


def _op_sort_key(op: CommandOp) -> tuple[int, str, str, str]:
    return (_COMMAND_RANK.get(op.command, 100), op.target, op.command, op.argument)


class CommandBatchWriter:
    def __init__(
        self,
        *,
        max_rows: int = MAX_COMMAND_ROWS,
        max_ops: int = MAX_COMMAND_OPS,
        max_bytes: int = MAX_COMMAND_FILE_BYTES,
    ) -> None:
        self.max_rows=int(max_rows); self.max_ops=int(max_ops); self.max_bytes=int(max_bytes)
        self._ops: dict[int, set[CommandOp]] = defaultdict(set)

    @staticmethod
    def _micros(timestamp: float) -> int:
        value=float(timestamp)
        if not math.isfinite(value) or value < 0:
            raise ValueError("FFmpeg command timestamp must be non-negative finite")
        return int(round(value * 1_000_000.0))

    def add(self, timestamp: float, target: str, command: str, argument: object) -> None:
        op=CommandOp(str(target),str(command),str(argument)); op.validate()
        self._ops[self._micros(timestamp)].add(op)

    def batches(self) -> tuple[CommandBatch, ...]:
        result=[]
        for micros in sorted(self._ops):
            ops=tuple(sorted(self._ops[micros], key=_op_sort_key))
            batch=CommandBatch(micros/1_000_000.0,ops); batch.validate(); result.append(batch)
        return tuple(result)

    def serialize(self) -> str:
        batches=self.batches()
        rows=[]
        op_count=0
        for batch in batches:
            op_count += len(batch.ops)
            row=f"{batch.timestamp:.6f} " + ", ".join(
                f"{op.target} {op.command} {op.argument}" for op in batch.ops
            ) + ";"
            rows.append(row)
        text="\n".join(rows) + ("\n" if rows else "")
        metrics=CommandFileMetrics(len(rows),op_count,len(text.encode("utf-8")))
        self.validate_metrics(metrics)
        return text

    def validate_metrics(self, metrics: CommandFileMetrics) -> None:
        if metrics.rows > self.max_rows:
            raise CommandLimitError(f"FFmpeg command rows exceed limit: {metrics.rows}>{self.max_rows}")
        if metrics.ops > self.max_ops:
            raise CommandLimitError(f"FFmpeg command ops exceed limit: {metrics.ops}>{self.max_ops}")
        if metrics.bytes > self.max_bytes:
            raise CommandLimitError(f"FFmpeg command file exceeds byte limit: {metrics.bytes}>{self.max_bytes}")

    def metrics(self) -> CommandFileMetrics:
        text=self.serialize()
        batches=self.batches()
        return CommandFileMetrics(
            rows=len(batches),
            ops=sum(len(batch.ops) for batch in batches),
            bytes=len(text.encode("utf-8")),
        )

    def write(self, path: str | Path) -> CommandFileMetrics:
        target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
        text=self.serialize()
        target.write_text(text,encoding="utf-8")
        return CommandFileMetrics(
            rows=len(self.batches()),
            ops=sum(len(batch.ops) for batch in self.batches()),
            bytes=len(text.encode("utf-8")),
        )
