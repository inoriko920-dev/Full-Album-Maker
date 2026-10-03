from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

from .editor_models import ProjectDocument
from .render_center_model_step10 import RenderJob, RenderSettings
from .render_executor_step10 import RenderExecutor, Step10RenderCancelled
from .render_preflight_step10 import (
    FFmpegCapability,
    hardware_encoder,
    probe_ffmpeg,
    run_preflight,
    verify_encoder_runtime,
)


class RenderAsyncBridge(QObject):
    preflight_ready = Signal(int, object, object)  # token, report, capability
    preflight_failed = Signal(int, str)
    render_started = Signal(str, str)
    metrics_ready = Signal(str, str, object)
    log_ready = Signal(str, str, str)
    render_finished = Signal(str, str, object)
    render_failed = Signal(str, str, str, str)  # job, attempt, code, message
    busy_changed = Signal(bool)

    def __init__(self, *, workers: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max(2, int(workers)), thread_name_prefix="fam-render-center")
        self._lock = threading.Lock()
        self._preflight_generation = 0
        self._active_attempt = ""
        self._cancel_event: threading.Event | None = None

    def _capability_for_settings(self, settings: RenderSettings) -> FFmpegCapability:
        capability = probe_ffmpeg()
        if settings.hardware_mode == "software":
            return capability
        try:
            candidate = hardware_encoder(settings.video_codec)
        except Exception:
            return capability
        if candidate in capability.encoders:
            capability = verify_encoder_runtime(capability, candidate)
        return capability

    def request_preflight(self, document: ProjectDocument, settings: RenderSettings) -> int:
        with self._lock:
            self._preflight_generation += 1
            token = self._preflight_generation
        snapshot = document.clone()
        self._executor.submit(self._run_preflight, token, snapshot, settings)
        return token

    def invalidate_preflight(self) -> int:
        with self._lock:
            self._preflight_generation += 1
            return self._preflight_generation

    def _run_preflight(self, token: int, document: ProjectDocument, settings: RenderSettings) -> None:
        try:
            capability = self._capability_for_settings(settings)
            report = run_preflight(document, settings, capability=capability)
        except Exception as exc:
            with self._lock:
                current = self._preflight_generation
            if token == current:
                self.preflight_failed.emit(token, str(exc))
            return
        with self._lock:
            current = self._preflight_generation
        if token == current:
            self.preflight_ready.emit(token, report, capability)

    def start(self, job: RenderJob) -> bool:
        with self._lock:
            if self._active_attempt:
                return False
            self._active_attempt = job.attempt_id
            self._cancel_event = threading.Event()
            cancel_event = self._cancel_event
        self.busy_changed.emit(True)
        self.render_started.emit(job.job_id, job.attempt_id)
        self._executor.submit(self._run_job, job, cancel_event)
        return True

    def _run_job(self, job: RenderJob, cancel_event: threading.Event) -> None:
        try:
            # Capability is re-probed here even when the UI preflight already
            # passed. RenderExecutor then performs the critical snapshot/media/
            # disk/output preflight again immediately before start.
            capability = self._capability_for_settings(job.settings)
            result = RenderExecutor(capability).execute(
                job,
                cancel_event=cancel_event,
                on_metrics=lambda value: self.metrics_ready.emit(job.job_id, job.attempt_id, value),
                on_log=lambda line: self.log_ready.emit(job.job_id, job.attempt_id, line),
            )
        except Step10RenderCancelled as exc:
            self.render_failed.emit(job.job_id, job.attempt_id, "CANCELLED", str(exc))
        except Exception as exc:
            self.render_failed.emit(
                job.job_id,
                job.attempt_id,
                job.error_code or "RENDER_FAILED",
                job.error_message or str(exc),
            )
        else:
            self.render_finished.emit(job.job_id, job.attempt_id, result)
        finally:
            with self._lock:
                if self._active_attempt == job.attempt_id:
                    self._active_attempt = ""
                    self._cancel_event = None
            self.busy_changed.emit(False)

    def cancel(self) -> bool:
        with self._lock:
            event = self._cancel_event
        if event is None:
            return False
        event.set()
        return True

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._active_attempt)

    def close(self) -> None:
        self.cancel()
        self.invalidate_preflight()
        self._executor.shutdown(wait=False, cancel_futures=True)
