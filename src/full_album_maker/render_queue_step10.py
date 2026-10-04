from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .atomic_io import atomic_write_text
from .paths import data_dir
from .render_center_model_step10 import (
    RenderJob,
    RenderJobState,
    RenderMetrics,
    RenderSettings,
    RenderSnapshot,
)
from .render_executor_step10 import sanitize_render_log


QUEUE_FORMAT = "full-album-maker-render-queue"
QUEUE_VERSION = 1
MAX_HISTORY = 200
_ACTIVE_ON_CRASH = {
    RenderJobState.PREFLIGHTING,
    RenderJobState.STARTING,
    RenderJobState.RUNNING,
    RenderJobState.PAUSED,
    RenderJobState.FINALIZING,
}


def _snapshot_to_dict(value: RenderSnapshot) -> dict:
    return {
        "project_id": value.project_id,
        "project_revision": value.project_revision,
        "content_signature": value.content_signature,
        "snapshot_hash": value.snapshot_hash,
        "project_json": value.project_json,
        "render_plan_json": value.render_plan_json,
        "duration_tick": value.duration_tick,
        "timebase": value.timebase,
    }


def _snapshot_from_dict(value: dict) -> RenderSnapshot:
    return RenderSnapshot(
        project_id=str(value["project_id"]),
        project_revision=int(value["project_revision"]),
        content_signature=str(value["content_signature"]),
        snapshot_hash=str(value["snapshot_hash"]),
        project_json=str(value["project_json"]),
        render_plan_json=str(value["render_plan_json"]),
        duration_tick=int(value["duration_tick"]),
        timebase=int(value["timebase"]),
    )


def _settings_from_dict(value: dict) -> RenderSettings:
    allowed = {
        "filename", "output_folder", "width", "height", "fps", "video_codec",
        "video_bitrate_bps", "audio_codec", "audio_bitrate_bps", "sample_rate",
        "hardware_mode", "container", "overwrite", "preset_id",
    }
    item = RenderSettings(**{key: value[key] for key in allowed if key in value})
    item.validate()
    return item


def job_to_dict(job: RenderJob) -> dict:
    job.metrics.validate()
    safe_logs: list[str] = []
    for line in job.log_lines[-500:]:
        safe = sanitize_render_log(line)
        if safe:
            safe_logs.append(safe)
    return {
        "job_id": job.job_id,
        "attempt_id": job.attempt_id,
        "state": job.state.value,
        "snapshot": _snapshot_to_dict(job.snapshot),
        "settings": job.settings.canonical_dict(),
        "metrics": asdict(job.metrics),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_code": sanitize_render_log(job.error_code, max_length=100),
        "error_message": sanitize_render_log(job.error_message),
        "verified_output": job.verified_output,
        "log_lines": safe_logs,
    }


def job_from_dict(value: dict) -> RenderJob:
    if not isinstance(value, dict):
        raise ValueError("Render job persistence tidak valid.")
    metrics_raw = value.get("metrics") or {}
    metrics = RenderMetrics(
        percent=float(metrics_raw.get("percent", 0.0)),
        rendered_seconds=float(metrics_raw.get("rendered_seconds", 0.0)),
        fps=None if metrics_raw.get("fps") is None else float(metrics_raw["fps"]),
        average_fps=None if metrics_raw.get("average_fps") is None else float(metrics_raw["average_fps"]),
        speed=None if metrics_raw.get("speed") is None else float(metrics_raw["speed"]),
        eta_seconds=None if metrics_raw.get("eta_seconds") is None else float(metrics_raw["eta_seconds"]),
    )
    metrics.validate()
    safe_logs: list[str] = []
    for line in (value.get("log_lines") or [])[-500:]:
        safe = sanitize_render_log(str(line))
        if safe:
            safe_logs.append(safe)
    return RenderJob(
        snapshot=_snapshot_from_dict(value["snapshot"]),
        settings=_settings_from_dict(value["settings"]),
        job_id=str(value["job_id"]),
        attempt_id=str(value["attempt_id"]),
        state=RenderJobState(str(value.get("state", RenderJobState.DRAFT.value))),
        metrics=metrics,
        created_at=str(value.get("created_at", "")),
        started_at=str(value.get("started_at", "")),
        finished_at=str(value.get("finished_at", "")),
        error_code=sanitize_render_log(str(value.get("error_code", "")), max_length=100),
        error_message=sanitize_render_log(str(value.get("error_message", ""))),
        verified_output=str(value.get("verified_output", "")),
        log_lines=safe_logs,
    )


class RenderQueueStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "render" / "queue_v1.json"

    def load(self) -> list[RenderJob]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Render queue store rusak/tidak dapat dibaca: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("format") != QUEUE_FORMAT or raw.get("version") != QUEUE_VERSION:
            raise ValueError("Versi render queue store tidak didukung.")
        values = raw.get("jobs", [])
        if not isinstance(values, list):
            raise ValueError("Daftar render job tidak valid.")
        return [job_from_dict(item) for item in values]

    def save(self, jobs: Iterable[RenderJob]) -> None:
        values = list(jobs)[-MAX_HISTORY:]
        payload = {
            "format": QUEUE_FORMAT,
            "version": QUEUE_VERSION,
            "jobs": [job_to_dict(job) for job in values],
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def recover(self) -> tuple[list[RenderJob], tuple[str, ...]]:
        jobs = self.load()
        changed: list[str] = []
        for job in jobs:
            if job.state not in _ACTIVE_ON_CRASH:
                continue
            # Recovery is intentionally not a normal state transition: the old
            # process no longer exists, so claiming resume semantics would be false.
            job.state = RenderJobState.INTERRUPTED
            job.error_code = "INTERRUPTED_ON_RESTART"
            job.error_message = (
                "Aplikasi berhenti sebelum attempt render selesai; resume otomatis "
                "tidak diklaim aman. Gunakan Retry untuk attempt baru."
            )
            if not job.finished_at:
                from .render_center_model_step10 import utc_now_iso
                job.finished_at = utc_now_iso()
            changed.append(job.attempt_id)
        removed = self.cleanup_orphan_stages(jobs)
        if changed or removed:
            self.save(jobs)
        return jobs, tuple(changed)

    @staticmethod
    def cleanup_orphan_stages(jobs: Iterable[RenderJob]) -> int:
        removed = 0
        seen: set[Path] = set()
        for job in jobs:
            final = job.settings.final_output
            folder = final.parent
            if not folder.is_dir():
                continue
            pattern = f".{final.stem}.*.rendering.mp4"
            for candidate in folder.glob(pattern):
                resolved = candidate.resolve(strict=False)
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    candidate.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass
        return removed


class RenderQueue:
    """Persistent single-active-slot queue; execution is owned by RenderExecutor."""

    def __init__(self, store: RenderQueueStore | None = None) -> None:
        self.store = store or RenderQueueStore()
        self.jobs, _ = self.store.recover()

    def enqueue(self, job: RenderJob) -> RenderJob:
        """Queue only a job that has already passed real preflight."""
        if job.state != RenderJobState.READY:
            raise ValueError("Job harus READY dari preflight nyata sebelum masuk queue.")
        if any(
            item.job_id == job.job_id and item.attempt_id == job.attempt_id
            for item in self.jobs
        ):
            raise ValueError("Attempt render sudah ada di queue/history.")
        job.transition(RenderJobState.QUEUED)
        self.jobs.append(job)
        self._trim_and_save()
        return job

    def next_queued(self) -> RenderJob | None:
        if any(job.state in _ACTIVE_ON_CRASH for job in self.jobs):
            return None
        return next(
            (job for job in self.jobs if job.state == RenderJobState.QUEUED),
            None,
        )

    def update(self, job: RenderJob) -> None:
        for index, current in enumerate(self.jobs):
            if current.job_id == job.job_id and current.attempt_id == job.attempt_id:
                self.jobs[index] = job
                self._trim_and_save()
                return
        self.jobs.append(job)
        self._trim_and_save()

    def retry(self, job_id: str, attempt_id: str) -> RenderJob:
        source = next(
            (
                job
                for job in self.jobs
                if job.job_id == job_id and job.attempt_id == attempt_id
            ),
            None,
        )
        if source is None:
            raise ValueError("Render job/attempt tidak ditemukan.")
        retry = source.retry()
        # Retry is deliberately DRAFT: it must pass preflight again before
        # enqueue, because source/disk/encoder/output may have changed.
        self.jobs.append(retry)
        self._trim_and_save()
        return retry

    def _trim_and_save(self) -> None:
        if len(self.jobs) > MAX_HISTORY:
            self.jobs = self.jobs[-MAX_HISTORY:]
        self.store.save(self.jobs)
