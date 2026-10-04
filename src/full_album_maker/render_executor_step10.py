from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from typing import Callable

from .atomic_bundle import publish_bundle_transactional
from .render_center_model_step10 import (
    RenderJob,
    RenderJobState,
    RenderMetrics,
    RenderSettings,
)
from .render_preflight_step10 import FFmpegCapability, PreflightReport, run_preflight
from .spectrum_render_step08 import Step08FFmpegCompiler


class Step10RenderError(RuntimeError):
    pass


class Step10RenderCancelled(Step10RenderError):
    pass


@dataclass(frozen=True)
class OutputVerification:
    path: str
    size_bytes: int
    duration_seconds: float
    video_codec: str
    audio_codec: str
    width: int
    height: int
    fps: float
    has_video: bool
    has_audio: bool
    verified: bool
    message: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    job_id: str
    attempt_id: str
    final_output: str
    verification: OutputVerification
    preflight: PreflightReport


MetricCallback = Callable[[RenderMetrics], None]
LogCallback = Callable[[str], None]
Run = Callable[..., subprocess.CompletedProcess]

_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|token|secret|password)\s*[:=]\s*([^\s,;]+)"
)


def sanitize_render_log(line: str, *, max_length: int = 1500) -> str:
    text = str(line or "").replace("\x00", "").strip()
    # Bearer values sometimes appear as `Authorization: Bearer abc`; redact the
    # complete credential token rather than relying on the generic key=value form.
    text = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: Bearer [REDACTED]", text)
    text = _SECRETISH.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    if len(text) > max_length:
        text = text[: max_length - 14] + "…[TRUNCATED]"
    return text


def _fps_value(value: object) -> float:
    text = str(value or "0").strip()
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            denominator = float(right)
            return float(left) / denominator if denominator else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def verify_output(
    path: str | Path,
    *,
    settings: RenderSettings,
    expected_duration_seconds: float,
    ffprobe: str,
    run: Run = subprocess.run,
    timeout: float = 20.0,
) -> OutputVerification:
    target = Path(path)
    if not target.is_file():
        raise Step10RenderError("Output staged tidak ditemukan setelah FFmpeg selesai.")
    size = target.stat().st_size
    if size <= 0:
        raise Step10RenderError("Output staged kosong/0 byte.")

    args = [
        str(ffprobe), "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(target),
    ]
    try:
        completed = run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        raise Step10RenderError(f"ffprobe output gagal dijalankan: {exc}") from exc
    if int(getattr(completed, "returncode", 1)) != 0:
        detail = sanitize_render_log(
            getattr(completed, "stderr", "") or getattr(completed, "stdout", "")
        )
        raise Step10RenderError(
            "ffprobe menolak output staged." + (f" {detail}" if detail else "")
        )
    try:
        payload = json.loads(getattr(completed, "stdout", "") or "{}")
    except json.JSONDecodeError as exc:
        raise Step10RenderError("ffprobe menghasilkan JSON yang tidak valid.") from exc

    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        raise Step10RenderError("ffprobe tidak mengembalikan daftar stream.")
    video = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"),
        None,
    )
    audio = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"),
        None,
    )
    if video is None:
        raise Step10RenderError("Output staged tidak memiliki video stream.")
    if audio is None:
        raise Step10RenderError("Output staged tidak memiliki audio stream.")

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if (width, height) != (int(settings.width), int(settings.height)):
        raise Step10RenderError(
            f"Resolusi output {width}x{height} tidak sama dengan target "
            f"{settings.width}x{settings.height}."
        )

    video_codec = str(video.get("codec_name") or "").casefold()
    expected_video = "h264" if settings.video_codec == "h264" else "hevc"
    if video_codec != expected_video:
        raise Step10RenderError(
            f"Codec video output {video_codec or '-'} tidak sama dengan target {expected_video}."
        )
    audio_codec = str(audio.get("codec_name") or "").casefold()
    if audio_codec != "aac":
        raise Step10RenderError(f"Codec audio output {audio_codec or '-'} bukan AAC.")
    try:
        sample_rate = int(audio.get("sample_rate") or 0)
    except (TypeError, ValueError):
        sample_rate = 0
    if sample_rate != int(settings.sample_rate):
        raise Step10RenderError(
            f"Sample rate output {sample_rate or '-'} tidak sama dengan target {settings.sample_rate}."
        )

    format_data = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    format_name = str(format_data.get("format_name") or "").casefold()
    if settings.container == "mp4" and "mp4" not in format_name:
        raise Step10RenderError(f"Container output bukan MP4 ({format_name or 'unknown'}).")

    duration = 0.0
    for candidate in (format_data.get("duration"), video.get("duration"), audio.get("duration")):
        try:
            parsed = float(candidate)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed) and parsed > duration:
            duration = parsed
    if duration <= 0:
        raise Step10RenderError("Durasi output tidak valid.")
    expected = max(0.001, float(expected_duration_seconds))
    tolerance = max(0.75, expected * 0.015)
    if abs(duration - expected) > tolerance:
        raise Step10RenderError(
            f"Durasi output {duration:.3f}s berbeda dari snapshot {expected:.3f}s "
            f"lebih dari toleransi {tolerance:.3f}s."
        )

    fps = _fps_value(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    if fps <= 0 or abs(fps - float(settings.fps)) > 0.6:
        raise Step10RenderError(
            f"FPS output {fps:.3f} tidak sama dengan target {settings.fps}."
        )

    return OutputVerification(
        path=str(target),
        size_bytes=size,
        duration_seconds=duration,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        fps=fps,
        has_video=True,
        has_audio=True,
        verified=True,
        message="Output staged lolos ffprobe dan kontrak snapshot/settings.",
    )


def _bitrate_string(bits_per_second: int) -> str:
    value = int(bits_per_second)
    if value % 1_000_000 == 0:
        return f"{value // 1_000_000}M"
    if value % 1_000 == 0:
        return f"{value // 1_000}k"
    return str(value)


def apply_settings_to_snapshot(job: RenderJob, encoder: str):
    document = job.snapshot.document()
    settings = job.settings
    settings.validate()
    document.canvas.width = int(settings.width)
    document.canvas.height = int(settings.height)
    # CanvasSettings persists FPS as an explicit rational. Writing a dynamic
    # `fps` attribute would be ignored by the recovered compiler, which reads
    # fps_num/fps_den and would silently keep the project default (typically 30).
    document.canvas.fps_num = int(settings.fps)
    document.canvas.fps_den = 1
    document.render_settings = dict(document.render_settings)
    document.render_settings["codec"] = settings.video_codec
    document.render_settings["audio_bitrate"] = _bitrate_string(settings.audio_bitrate_bps)
    document.render_settings["sample_rate"] = int(settings.sample_rate)
    document.render_settings["video_bitrate"] = _bitrate_string(settings.video_bitrate_bps)
    document.render_settings["resolved_encoder"] = str(encoder)
    document.validate()
    return document


def apply_encoder_settings(
    args: tuple[str, ...], settings: RenderSettings, encoder: str
) -> tuple[str, ...]:
    values = list(args)
    if "-c:v" not in values:
        raise Step10RenderError("Compiler recovered tidak menghasilkan opsi video encoder.")
    video_index = values.index("-c:v")
    values[video_index + 1] = str(encoder)
    while "-b:v" in values:
        index = values.index("-b:v")
        del values[index : index + 2]
    video_index = values.index("-c:v")
    values[video_index + 2:video_index + 2] = [
        "-b:v", _bitrate_string(settings.video_bitrate_bps)
    ]

    if "-c:a" in values:
        while "-b:a" in values:
            index = values.index("-b:a")
            del values[index : index + 2]
        while "-ar" in values:
            index = values.index("-ar")
            del values[index : index + 2]
        audio_index = values.index("-c:a")
        values[audio_index + 2:audio_index + 2] = [
            "-b:a", _bitrate_string(settings.audio_bitrate_bps),
            "-ar", str(settings.sample_rate),
        ]
    return tuple(values)


def add_progress_protocol(args: tuple[str, ...]) -> tuple[str, ...]:
    values = list(args)
    if not values:
        raise Step10RenderError("Argumen FFmpeg kosong.")
    values[1:1] = ["-nostats", "-progress", "pipe:1"]
    return tuple(values)


class Step10ProcessRunner:
    def run(
        self,
        args: tuple[str, ...],
        *,
        duration_seconds: float,
        cancel_event: threading.Event | None = None,
        on_metrics: MetricCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> RenderMetrics:
        process = subprocess.Popen(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            raise Step10RenderError("FFmpeg process pipe tidak tersedia.")

        stderr_lines: list[str] = []
        stderr_lock = threading.Lock()

        def drain_stderr() -> None:
            for raw in process.stderr:
                line = sanitize_render_log(raw)
                if not line:
                    continue
                with stderr_lock:
                    stderr_lines.append(line)
                    del stderr_lines[:-50]
                if on_log:
                    on_log(line)

        thread = threading.Thread(
            target=drain_stderr, name="fam-render-stderr", daemon=True
        )
        thread.start()
        values: dict[str, str] = {}
        last = RenderMetrics()
        try:
            for raw in process.stdout:
                if cancel_event is not None and cancel_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                    raise Step10RenderCancelled("Render dibatalkan oleh pengguna.")
                line = sanitize_render_log(raw)
                if "=" not in line:
                    if line and on_log:
                        on_log(line)
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
                if key.strip() != "progress":
                    continue
                rendered = 0.0
                for time_key in ("out_time_us", "out_time_ms"):
                    if values.get(time_key):
                        try:
                            # FFmpeg progress reports these fields in microseconds
                            # despite the historical out_time_ms label.
                            rendered = float(values[time_key]) / 1_000_000.0
                        except ValueError:
                            rendered = 0.0
                        break
                percent = max(
                    0.0,
                    min(100.0, rendered / max(0.001, duration_seconds) * 100.0),
                )
                try:
                    fps = max(0.0, float(values.get("fps", "0") or 0))
                except ValueError:
                    fps = 0.0
                try:
                    speed = max(
                        0.0,
                        float((values.get("speed", "0x") or "0x").rstrip("x") or 0),
                    )
                except ValueError:
                    speed = 0.0
                eta = (
                    max(0.0, (duration_seconds - rendered) / speed)
                    if speed > 0
                    else None
                )
                last = RenderMetrics(
                    percent=100.0 if values.get("progress") == "end" else percent,
                    rendered_seconds=max(0.0, rendered),
                    fps=fps,
                    average_fps=fps,
                    speed=speed,
                    eta_seconds=eta,
                )
                last.validate()
                if on_metrics:
                    on_metrics(last)
                values.clear()

            return_code = process.wait()
            thread.join(timeout=1.0)
            if cancel_event is not None and cancel_event.is_set():
                raise Step10RenderCancelled("Render dibatalkan oleh pengguna.")
            if return_code != 0:
                with stderr_lock:
                    detail = "\n".join(stderr_lines[-8:])
                raise Step10RenderError(
                    f"FFmpeg keluar dengan kode {return_code}."
                    + (f"\n{detail}" if detail else "")
                )
            return last
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            thread.join(timeout=1.0)


class RenderExecutor:
    def __init__(
        self,
        capability: FFmpegCapability,
        *,
        runner: Step10ProcessRunner | None = None,
        verifier: Callable[..., OutputVerification] = verify_output,
    ) -> None:
        self.capability = capability
        self.runner = runner or Step10ProcessRunner()
        self.verifier = verifier
        self._active_attempt: str | None = None
        self._lock = threading.Lock()

    def _claim(self, attempt_id: str) -> None:
        with self._lock:
            if self._active_attempt is not None:
                raise Step10RenderError(
                    "Renderer sedang menjalankan attempt lain; double-start ditolak."
                )
            self._active_attempt = attempt_id

    def _release(self, attempt_id: str) -> None:
        with self._lock:
            if self._active_attempt == attempt_id:
                self._active_attempt = None

    def execute(
        self,
        job: RenderJob,
        *,
        cancel_event: threading.Event | None = None,
        on_metrics: MetricCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> ExecutionResult:
        self._claim(job.attempt_id)
        staged: Path | None = None
        try:
            if job.state not in {
                RenderJobState.DRAFT,
                RenderJobState.BLOCKED,
                RenderJobState.READY,
                RenderJobState.QUEUED,
            }:
                raise Step10RenderError(
                    f"Job state {job.state.value} tidak dapat dimulai."
                )

            # Every launch path explicitly returns to PREFLIGHTING. A previously
            # READY/QUEUED job is never trusted without this critical recheck.
            job.transition(RenderJobState.PREFLIGHTING)
            preflight = run_preflight(
                job.snapshot.document(),
                job.settings,
                capability=self.capability,
            )
            if preflight.blocked or preflight.snapshot is None or preflight.encoder is None:
                job.error_code = "PREFLIGHT_BLOCKED"
                job.error_message = "; ".join(
                    check.message
                    for check in preflight.checks
                    if check.level.value == "BLOCK"
                )
                job.transition(RenderJobState.BLOCKED)
                raise Step10RenderError(
                    "Critical preflight BLOCK; render tidak dimulai."
                )
            job.error_code = ""
            job.error_message = ""
            job.transition(RenderJobState.READY)
            job.transition(RenderJobState.STARTING)

            final = job.settings.final_output
            final.parent.mkdir(parents=True, exist_ok=True)
            fd, stage_name = tempfile.mkstemp(
                prefix=f".{final.stem}.{job.attempt_id[:8]}.",
                suffix=".rendering.mp4",
                dir=final.parent,
            )
            os.close(fd)
            staged = Path(stage_name)
            staged.unlink(missing_ok=True)

            document = apply_settings_to_snapshot(job, preflight.encoder.encoder)
            with tempfile.TemporaryDirectory(
                prefix=f".{final.stem}.{job.attempt_id[:8]}.work-",
                dir=final.parent,
            ) as work:
                compiled = Step08FFmpegCompiler(self.capability.ffmpeg).compile_video(
                    document, staged, work
                )
                args = apply_encoder_settings(
                    compiled.args,
                    job.settings,
                    preflight.encoder.encoder,
                )
                args = add_progress_protocol(args)
                job.transition(RenderJobState.RUNNING)

                def metrics(value: RenderMetrics) -> None:
                    job.metrics = value
                    if on_metrics:
                        on_metrics(value)

                self.runner.run(
                    args,
                    duration_seconds=(
                        job.snapshot.duration_tick / max(1, job.snapshot.timebase)
                    ),
                    cancel_event=cancel_event,
                    on_metrics=metrics,
                    on_log=lambda line: self._record_log(job, line, on_log),
                )

            if cancel_event is not None and cancel_event.is_set():
                raise Step10RenderCancelled(
                    "Render dibatalkan sebelum verifikasi output."
                )
            job.transition(RenderJobState.FINALIZING)
            verification = self.verifier(
                staged,
                settings=job.settings,
                expected_duration_seconds=(
                    job.snapshot.duration_tick / max(1, job.snapshot.timebase)
                ),
                ffprobe=self.capability.ffprobe,
            )
            if not verification.verified:
                raise Step10RenderError(
                    "Output verifier tidak memberi status VERIFIED."
                )

            publish_bundle_transactional([(staged, final)])
            staged = None
            job.verified_output = str(final)
            job.metrics = RenderMetrics(
                percent=100.0,
                rendered_seconds=verification.duration_seconds,
                fps=verification.fps,
                average_fps=verification.fps,
                speed=job.metrics.speed,
                eta_seconds=0.0,
            )
            job.transition(RenderJobState.COMPLETED)
            return ExecutionResult(
                job_id=job.job_id,
                attempt_id=job.attempt_id,
                final_output=str(final),
                verification=verification,
                preflight=preflight,
            )
        except Step10RenderCancelled as exc:
            job.error_code = "CANCELLED"
            job.error_message = sanitize_render_log(str(exc))
            if job.state in {
                RenderJobState.PREFLIGHTING,
                RenderJobState.READY,
                RenderJobState.STARTING,
                RenderJobState.RUNNING,
                RenderJobState.PAUSED,
            }:
                job.transition(RenderJobState.CANCELLED)
            raise
        except Exception as exc:
            if not job.error_code:
                job.error_code = "RENDER_FAILED"
            if not job.error_message:
                job.error_message = sanitize_render_log(str(exc))
            if job.state in {
                RenderJobState.STARTING,
                RenderJobState.RUNNING,
                RenderJobState.FINALIZING,
            }:
                job.transition(RenderJobState.FAILED)
            raise
        finally:
            if staged is not None:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    pass
            self._release(job.attempt_id)

    @staticmethod
    def _record_log(
        job: RenderJob, line: str, callback: LogCallback | None
    ) -> None:
        safe = sanitize_render_log(line)
        if not safe:
            return
        job.log_lines.append(safe)
        del job.log_lines[:-500]
        if callback:
            callback(safe)
