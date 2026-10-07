from __future__ import annotations

from pathlib import Path
import subprocess
import threading
import time

from .audio_analysis_contract import SAMPLE_RATE
from .audio_analysis_fingerprint import AnalysisCancelled
from .paths import ffmpeg_path


class DecodeError(RuntimeError):
    pass


class NoAudioStreamError(DecodeError):
    pass


def decode_to_f32(
    source: str | Path,
    destination: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    executable: str | None = None,
) -> Path:
    tool = executable or ffmpeg_path()
    if not tool:
        raise FileNotFoundError("bundled FFmpeg is unavailable")
    source_path = Path(source)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    args = [
        tool, "-nostdin", "-v", "error", "-y", "-i", str(source_path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-f", "f32le", "-acodec", "pcm_f32le", str(target),
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1.5)
                raise AnalysisCancelled("analysis cancelled during decode")
            time.sleep(0.05)
        stderr = (proc.stderr.read() if proc.stderr is not None else b"").decode("utf-8", errors="replace")
        if proc.returncode != 0:
            text = stderr.strip()
            lower = text.casefold()
            if "matches no streams" in lower or "does not contain any stream" in lower:
                raise NoAudioStreamError(text[:800] or "no usable audio stream")
            raise DecodeError(text[:800] or f"FFmpeg exited with {proc.returncode}")
        if not target.is_file() or target.stat().st_size < 4:
            raise DecodeError("FFmpeg produced empty analysis PCM")
        if target.stat().st_size % 4:
            raise DecodeError("decoded PCM size is not aligned to float32 samples")
        return target
    except Exception:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        target.unlink(missing_ok=True)
        raise
