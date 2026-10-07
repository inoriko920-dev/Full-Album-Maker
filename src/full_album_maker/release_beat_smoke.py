from __future__ import annotations

from pathlib import Path
import tempfile

import librosa
import numba
import numpy as np
import scipy

from .audio_analysis_backend import analyze_pcm
from .audio_analysis_contract import SAMPLE_RATE
from .audio_analysis_fingerprint import AnalyzerSettings


def _clicks(bpm: float, seconds: float = 3.0) -> np.ndarray:
    count = int(SAMPLE_RATE * seconds)
    data = np.zeros(count, dtype=np.float32)
    step = 60.0 * SAMPLE_RATE / bpm
    for index in range(int(seconds * bpm / 60.0) + 1):
        start = int(round(index * step))
        if start >= count:
            break
        end = min(count, start + 180)
        data[start:end] += np.hanning((end - start) * 2)[: end - start].astype(np.float32)
    return data


def _octave_error(got: float, expected: float) -> float:
    return min(abs(got - expected), abs(got - expected / 2.0), abs(got - expected * 2.0))


def run_beat_runtime_smoke() -> int:
    expected = {
        "librosa": "1.0.0",
        "numpy": "2.5.3",
        "scipy": "1.18.1",
        "numba": "0.68.0",
    }
    actual = {
        "librosa": librosa.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "numba": numba.__version__,
    }
    if actual != expected:
        raise RuntimeError(f"Scientific runtime version mismatch: {actual!r}")
    with tempfile.TemporaryDirectory(prefix="fam-step14-runtime-") as folder:
        pcm = Path(folder) / "clicks.f32"
        _clicks(120.0).astype("<f4").tofile(pcm)
        output = analyze_pcm(pcm, AnalyzerSettings(), block_frames=128)
        if _octave_error(output.tempo_bpm, 120.0) >= 5.0:
            raise RuntimeError(f"Beat runtime tempo smoke failed: {output.tempo_bpm}")
    print("STEP14_MAIN_BEAT_RUNTIME_OK")
    return 0
