from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable

import numpy as np

from .audio_analysis_contract import HOP_LENGTH, N_FFT, SAMPLE_RATE, TICKS_PER_FRAME, TICKS_PER_SAMPLE
from .audio_analysis_fingerprint import AnalysisCancelled, AnalyzerSettings


@dataclass(frozen=True)
class BackendOutput:
    duration_tick: int
    tempo_bpm: float
    beat_frames: tuple[int, ...]
    onset_frames: tuple[int, ...]
    beat_interval_cv: float
    curves: dict[str, np.ndarray]
    rms_mean: float
    rms_peak: float
    onset_mean: float
    onset_peak: float


def _check_cancel(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise AnalysisCancelled("analysis cancelled")


def _normalize(values: np.ndarray, low_percentile: float, high_percentile: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0:
        return values
    hi = float(np.percentile(values, high_percentile))
    lo = float(np.percentile(values, low_percentile))
    if not np.isfinite(hi) or hi <= max(1e-12, lo):
        return np.zeros(values.shape, dtype=np.float32)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def analyze_pcm(
    pcm_path: str | Path,
    settings: AnalyzerSettings,
    *,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[float], None] | None = None,
    block_frames: int = 1024,
) -> BackendOutput:
    _check_cancel(cancel_event)
    pcm = np.memmap(str(pcm_path), dtype="<f4", mode="r")
    sample_count = int(pcm.size)
    duration_tick = sample_count * TICKS_PER_SAMPLE
    if sample_count == 0:
        raise ValueError("decoded PCM is empty")

    if sample_count < settings.n_fft:
        padded = np.zeros(settings.n_fft, dtype=np.float32)
        padded[:sample_count] = np.asarray(pcm, dtype=np.float32)
        working = padded
        total_frames = 1
    else:
        working = pcm
        total_frames = 1 + (sample_count - settings.n_fft) // settings.hop_length

    energy = np.empty(total_frames, dtype=np.float32)
    bass = np.empty(total_frames, dtype=np.float32)
    mid = np.empty(total_frames, dtype=np.float32)
    high = np.empty(total_frames, dtype=np.float32)
    onset = np.empty(total_frames, dtype=np.float32)

    window = np.hanning(settings.n_fft).astype(np.float32)
    freqs = np.fft.rfftfreq(settings.n_fft, 1.0 / settings.sample_rate)
    bass_mask = (freqs >= settings.bass_low_hz) & (freqs < settings.bass_high_hz)
    mid_mask = (freqs >= settings.bass_high_hz) & (freqs < settings.mid_high_hz)
    high_mask = (freqs >= settings.mid_high_hz) & (freqs <= settings.high_high_hz)
    previous_mag: np.ndarray | None = None

    for first_frame in range(0, total_frames, max(1, int(block_frames))):
        _check_cancel(cancel_event)
        last_frame = min(total_frames, first_frame + max(1, int(block_frames)))
        frame_count = last_frame - first_frame
        sample_start = first_frame * settings.hop_length
        sample_end = sample_start + (frame_count - 1) * settings.hop_length + settings.n_fft
        segment = np.asarray(working[sample_start:sample_end], dtype=np.float32)
        needed = (frame_count - 1) * settings.hop_length + settings.n_fft
        if segment.size < needed:
            segment = np.pad(segment, (0, needed - segment.size))
        windows = np.lib.stride_tricks.sliding_window_view(segment, settings.n_fft)[:: settings.hop_length][:frame_count]
        rms = np.sqrt(np.mean(np.square(windows, dtype=np.float32), axis=1, dtype=np.float64)).astype(np.float32)
        magnitude = np.abs(np.fft.rfft(windows * window, axis=1)).astype(np.float32)
        power = np.square(magnitude, dtype=np.float32)
        energy[first_frame:last_frame] = rms
        bass[first_frame:last_frame] = np.mean(power[:, bass_mask], axis=1, dtype=np.float64).astype(np.float32) if bass_mask.any() else 0
        mid[first_frame:last_frame] = np.mean(power[:, mid_mask], axis=1, dtype=np.float64).astype(np.float32) if mid_mask.any() else 0
        high[first_frame:last_frame] = np.mean(power[:, high_mask], axis=1, dtype=np.float64).astype(np.float32) if high_mask.any() else 0

        for local in range(frame_count):
            mag = magnitude[local]
            if previous_mag is None:
                onset[first_frame + local] = 0.0
            else:
                onset[first_frame + local] = float(np.maximum(mag - previous_mag, 0.0).mean())
            previous_mag = mag
        if on_progress is not None:
            on_progress(last_frame / total_frames)

    _check_cancel(cancel_event)
    normalized_onset = _normalize(onset, settings.normalization_low_percentile, settings.normalization_high_percentile)

    import librosa

    beat_value = librosa.beat.beat_track(
        onset_envelope=normalized_onset,
        sr=settings.sample_rate,
        hop_length=settings.hop_length,
        units="frames",
        sparse=True,
    )
    _check_cancel(cancel_event)
    tempo_raw, beat_frames_raw = beat_value
    tempo_array = np.asarray(tempo_raw).reshape(-1)
    tempo_bpm = float(tempo_array[0]) if tempo_array.size else 0.0
    beat_frames = tuple(int(x) for x in np.asarray(beat_frames_raw, dtype=np.int64).reshape(-1) if 0 <= int(x) < total_frames)

    onset_frames_raw = librosa.onset.onset_detect(
        onset_envelope=normalized_onset,
        sr=settings.sample_rate,
        hop_length=settings.hop_length,
        units="frames",
        backtrack=False,
        sparse=True,
    )
    _check_cancel(cancel_event)
    onset_frames = tuple(int(x) for x in np.asarray(onset_frames_raw, dtype=np.int64).reshape(-1) if 0 <= int(x) < total_frames)

    if len(beat_frames) >= 3:
        intervals = np.diff(np.asarray(beat_frames, dtype=np.float64))
        mean_interval = float(np.mean(intervals))
        beat_interval_cv = float(np.std(intervals) / mean_interval) if mean_interval > 0 else 1.0
    else:
        beat_interval_cv = 1.0

    curves = {
        "energy": _normalize(energy, settings.normalization_low_percentile, settings.normalization_high_percentile),
        "bass": _normalize(bass, settings.normalization_low_percentile, settings.normalization_high_percentile),
        "mid": _normalize(mid, settings.normalization_low_percentile, settings.normalization_high_percentile),
        "high": _normalize(high, settings.normalization_low_percentile, settings.normalization_high_percentile),
        "onset": normalized_onset,
    }
    result = BackendOutput(
        duration_tick=duration_tick,
        tempo_bpm=tempo_bpm,
        beat_frames=beat_frames,
        onset_frames=onset_frames,
        beat_interval_cv=beat_interval_cv,
        curves=curves,
        rms_mean=float(np.mean(energy, dtype=np.float64)),
        rms_peak=float(np.max(energy)),
        onset_mean=float(np.mean(onset, dtype=np.float64)),
        onset_peak=float(np.max(onset)),
    )

    # Windows keeps an mmap-backed PCM file locked until the memmap handle is
    # closed explicitly. Drop the last sliding-window views before closing so
    # analysis temp directories can be removed immediately after a successful
    # result (and frozen executables behave the same as source runs).
    try:
        del windows
    except UnboundLocalError:
        pass
    try:
        del segment
    except UnboundLocalError:
        pass
    if working is pcm:
        del working
    mmap_handle = getattr(pcm, "_mmap", None)
    if mmap_handle is not None:
        mmap_handle.close()
    return result
