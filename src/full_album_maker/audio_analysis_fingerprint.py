from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import threading
from typing import Callable

from .audio_analysis_contract import ANALYZER_VERSION, HOP_LENGTH, N_FFT, SAMPLE_RATE

HASH_CHUNK_BYTES = 4 * 1024 * 1024


class AnalysisCancelled(RuntimeError):
    pass


class SourceChangedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class AnalyzerSettings:
    analyzer_version: str = ANALYZER_VERSION
    sample_rate: int = SAMPLE_RATE
    hop_length: int = HOP_LENGTH
    n_fft: int = N_FFT
    bass_low_hz: float = 20.0
    bass_high_hz: float = 250.0
    mid_high_hz: float = 4_000.0
    high_high_hz: float = 12_000.0
    normalization_low_percentile: float = 5.0
    normalization_high_percentile: float = 99.0

    def signature(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def snapshot(path: str | Path) -> SourceSnapshot:
    stat = Path(path).stat()
    return SourceSnapshot(size=int(stat.st_size), mtime_ns=int(stat.st_mtime_ns))


def hash_source(
    path: str | Path,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> tuple[str, SourceSnapshot]:
    source = Path(path)
    before = snapshot(source)
    digest = hashlib.sha256()
    read_bytes = 0
    with source.open("rb") as handle:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise AnalysisCancelled("analysis cancelled")
            block = handle.read(HASH_CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
            read_bytes += len(block)
            if on_progress is not None:
                on_progress(min(1.0, read_bytes / max(1, before.size)))
    after = snapshot(source)
    if after != before:
        raise SourceChangedError("source changed while fingerprinting")
    return digest.hexdigest(), after


def cache_key(content_sha256: str, settings_signature: str) -> str:
    raw = f"{ANALYZER_VERSION}\0{content_sha256.lower()}\0{settings_signature.lower()}"
    return hashlib.sha256(raw.encode("ascii")).hexdigest()
