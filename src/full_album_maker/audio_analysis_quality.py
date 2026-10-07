from __future__ import annotations

from dataclasses import dataclass
import math

from .audio_analysis_contract import AnalysisQuality, TempoSummary, TIMEBASE


@dataclass(frozen=True)
class QualityDiagnostics:
    duration_tick: int
    tempo_bpm: float
    beat_count: int
    beat_interval_cv: float
    rms_mean: float
    rms_peak: float
    onset_mean: float
    onset_peak: float


def evaluate_quality(value: QualityDiagnostics) -> tuple[TempoSummary, tuple[str, ...]]:
    flags: list[str] = []
    duration_seconds = value.duration_tick / TIMEBASE if TIMEBASE else 0.0

    if value.rms_peak < 1e-4 or value.rms_mean < 1e-5:
        flags.append("SILENT_OR_NEAR_SILENT")
        return TempoSummary(0.0, 0.0, AnalysisQuality.SILENT, max(0.0, value.beat_interval_cv)), tuple(flags)

    if duration_seconds < 2.0:
        flags.append("AUDIO_TOO_SHORT")
    if value.beat_count < 3:
        flags.append("TOO_FEW_BEATS")
    if not 35.0 <= value.tempo_bpm <= 240.0:
        flags.append("TEMPO_OUT_OF_RANGE")
    if value.beat_interval_cv > 0.22:
        flags.append("UNSTABLE_BEAT_INTERVAL")

    onset_contrast = value.onset_peak / max(1e-9, value.onset_mean)
    if onset_contrast < 2.0:
        flags.append("LOW_ONSET_CONTRAST")

    stability = max(0.0, 1.0 - min(1.0, value.beat_interval_cv / 0.25))
    density = min(1.0, value.beat_count / max(4.0, duration_seconds / 2.0))
    contrast = min(1.0, max(0.0, (onset_contrast - 1.0) / 4.0))
    confidence = 0.50 * stability + 0.30 * density + 0.20 * contrast

    if any(flag in flags for flag in ("AUDIO_TOO_SHORT", "TOO_FEW_BEATS", "TEMPO_OUT_OF_RANGE")):
        confidence = min(confidence, 0.34)
    if "LOW_ONSET_CONTRAST" in flags:
        confidence = min(confidence, 0.44)
    if "UNSTABLE_BEAT_INTERVAL" in flags:
        confidence = min(confidence, 0.49)

    if confidence >= 0.75:
        quality = AnalysisQuality.HIGH
    elif confidence >= 0.50:
        quality = AnalysisQuality.MEDIUM
    else:
        quality = AnalysisQuality.LOW

    bpm = value.tempo_bpm if math.isfinite(value.tempo_bpm) and value.tempo_bpm > 0 else 0.0
    return TempoSummary(float(bpm), float(max(0.0, min(1.0, confidence))), quality, max(0.0, value.beat_interval_cv)), tuple(flags)
