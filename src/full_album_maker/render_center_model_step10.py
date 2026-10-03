from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .editor_models import ProjectDocument
from .render_plan import RenderPlan, compile_render_plan


class RenderJobState(str, Enum):
    DRAFT = "DRAFT"
    PREFLIGHTING = "PREFLIGHTING"
    READY = "READY"
    QUEUED = "QUEUED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    INTERRUPTED = "INTERRUPTED"


_ALLOWED_TRANSITIONS: dict[RenderJobState, frozenset[RenderJobState]] = {
    RenderJobState.DRAFT: frozenset({RenderJobState.PREFLIGHTING, RenderJobState.CANCELLED}),
    RenderJobState.PREFLIGHTING: frozenset({RenderJobState.READY, RenderJobState.BLOCKED, RenderJobState.CANCELLED}),
    # READY/QUEUED may return to PREFLIGHTING for the mandatory critical
    # recheck immediately before start. This prevents stale media/disk/encoder
    # state from being treated as still ready.
    RenderJobState.READY: frozenset({RenderJobState.PREFLIGHTING, RenderJobState.QUEUED, RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.CANCELLED}),
    RenderJobState.QUEUED: frozenset({RenderJobState.PREFLIGHTING, RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.CANCELLED}),
    RenderJobState.STARTING: frozenset({RenderJobState.RUNNING, RenderJobState.FAILED, RenderJobState.CANCELLED}),
    RenderJobState.RUNNING: frozenset({RenderJobState.PAUSED, RenderJobState.FINALIZING, RenderJobState.FAILED, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED}),
    RenderJobState.PAUSED: frozenset({RenderJobState.RUNNING, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED}),
    RenderJobState.FINALIZING: frozenset({RenderJobState.COMPLETED, RenderJobState.FAILED, RenderJobState.INTERRUPTED}),
    RenderJobState.COMPLETED: frozenset(),
    RenderJobState.FAILED: frozenset(),
    RenderJobState.CANCELLED: frozenset(),
    RenderJobState.BLOCKED: frozenset({RenderJobState.PREFLIGHTING, RenderJobState.CANCELLED}),
    RenderJobState.INTERRUPTED: frozenset(),
}


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
WINDOWS_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SUPPORTED_VIDEO_CODECS = {"h264", "h265"}
SUPPORTED_AUDIO_CODECS = {"aac"}
SUPPORTED_SAMPLE_RATES = {44_100, 48_000}
SUPPORTED_FPS = {24, 25, 30, 50, 60}
SUPPORTED_HARDWARE_MODES = {"auto", "software", "h264_nvenc", "hevc_nvenc"}
SUPPORTED_CONTAINERS = {"mp4"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize_filename(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Nama file output kosong.")
    if raw.endswith((".", " ")):
        raise ValueError("Nama file Windows tidak boleh berakhir dengan titik/spasi.")
    if WINDOWS_INVALID_FILENAME.search(raw):
        raise ValueError("Nama file output mengandung karakter Windows yang tidak valid.")
    stem = Path(raw).stem if Path(raw).suffix else raw
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError("Nama file output memakai nama perangkat Windows yang dilarang.")
    if raw in {".", ".."} or ".." in Path(raw).parts:
        raise ValueError("Nama file output tidak boleh traversal.")
    return raw


def normalized_output_path(folder: str | Path, filename: str, container: str = "mp4") -> Path:
    container = str(container).casefold()
    if container not in SUPPORTED_CONTAINERS:
        raise ValueError("Container output belum didukung.")
    clean = sanitize_filename(filename)
    suffix = f".{container}"
    if Path(clean).suffix:
        if Path(clean).suffix.casefold() != suffix:
            raise ValueError(f"Ekstensi output harus {suffix}.")
    else:
        clean += suffix
    base = Path(folder).expanduser().resolve(strict=False)
    target = (base / clean).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Output path keluar dari folder yang dipilih.") from exc
    return target


@dataclass(frozen=True)
class RenderSettings:
    filename: str
    output_folder: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_codec: str = "h264"
    video_bitrate_bps: int = 16_000_000
    audio_codec: str = "aac"
    audio_bitrate_bps: int = 320_000
    sample_rate: int = 48_000
    hardware_mode: str = "auto"
    container: str = "mp4"
    overwrite: bool = False
    preset_id: str = "youtube_1080p"

    def validate(self) -> None:
        sanitize_filename(self.filename)
        if not isinstance(self.output_folder, str) or not self.output_folder.strip():
            raise ValueError("Folder output kosong.")
        if not 320 <= int(self.width) <= 7680 or not 240 <= int(self.height) <= 4320:
            raise ValueError("Resolusi output di luar batas.")
        if int(self.width) % 2 or int(self.height) % 2:
            raise ValueError("Resolusi output harus genap.")
        if int(self.fps) not in SUPPORTED_FPS:
            raise ValueError("FPS output belum didukung.")
        if self.video_codec not in SUPPORTED_VIDEO_CODECS:
            raise ValueError("Video codec belum didukung.")
        if self.audio_codec not in SUPPORTED_AUDIO_CODECS:
            raise ValueError("Audio codec belum didukung.")
        if int(self.sample_rate) not in SUPPORTED_SAMPLE_RATES:
            raise ValueError("Sample rate belum didukung.")
        if self.hardware_mode not in SUPPORTED_HARDWARE_MODES:
            raise ValueError("Hardware mode belum didukung.")
        if self.container not in SUPPORTED_CONTAINERS:
            raise ValueError("Container belum didukung.")
        if not 250_000 <= int(self.video_bitrate_bps) <= 200_000_000:
            raise ValueError("Video bitrate di luar batas.")
        if not 64_000 <= int(self.audio_bitrate_bps) <= 1_536_000:
            raise ValueError("Audio bitrate di luar batas.")
        if self.video_codec == "h265" and self.hardware_mode == "h264_nvenc":
            raise ValueError("H.265 tidak kompatibel dengan h264_nvenc.")
        if self.video_codec == "h264" and self.hardware_mode == "hevc_nvenc":
            raise ValueError("H.264 tidak kompatibel dengan hevc_nvenc.")
        normalized_output_path(self.output_folder, self.filename, self.container)

    @property
    def final_output(self) -> Path:
        self.validate()
        return normalized_output_path(self.output_folder, self.filename, self.container)

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "filename": self.filename,
            "output_folder": str(Path(self.output_folder).expanduser().resolve(strict=False)),
            "width": int(self.width),
            "height": int(self.height),
            "fps": int(self.fps),
            "video_codec": self.video_codec,
            "video_bitrate_bps": int(self.video_bitrate_bps),
            "audio_codec": self.audio_codec,
            "audio_bitrate_bps": int(self.audio_bitrate_bps),
            "sample_rate": int(self.sample_rate),
            "hardware_mode": self.hardware_mode,
            "container": self.container,
            "overwrite": bool(self.overwrite),
            "preset_id": self.preset_id,
        }

    def signature(self) -> str:
        raw = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


PRESETS: dict[str, dict[str, Any]] = {
    "youtube_1080p": {
        "width": 1920, "height": 1080, "fps": 30,
        "video_codec": "h264", "video_bitrate_bps": 16_000_000,
        "audio_codec": "aac", "audio_bitrate_bps": 320_000, "sample_rate": 48_000,
        "hardware_mode": "auto", "container": "mp4",
    },
    "youtube_1440p": {
        "width": 2560, "height": 1440, "fps": 30,
        "video_codec": "h264", "video_bitrate_bps": 24_000_000,
        "audio_codec": "aac", "audio_bitrate_bps": 320_000, "sample_rate": 48_000,
        "hardware_mode": "auto", "container": "mp4",
    },
    "youtube_4k": {
        "width": 3840, "height": 2160, "fps": 30,
        "video_codec": "h265", "video_bitrate_bps": 45_000_000,
        "audio_codec": "aac", "audio_bitrate_bps": 320_000, "sample_rate": 48_000,
        "hardware_mode": "auto", "container": "mp4",
    },
}


def settings_from_preset(preset_id: str, *, filename: str, output_folder: str) -> RenderSettings:
    if preset_id == "custom":
        raise ValueError("Preset Custom membutuhkan RenderSettings eksplisit.")
    try:
        values = PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError("Preset Render tidak ditemukan.") from exc
    settings = RenderSettings(filename=filename, output_folder=output_folder, preset_id=preset_id, **values)
    settings.validate()
    return settings


@dataclass(frozen=True)
class RenderSnapshot:
    project_id: str
    project_revision: int
    content_signature: str
    snapshot_hash: str
    project_json: str
    render_plan_json: str
    duration_tick: int
    timebase: int

    def document(self) -> ProjectDocument:
        return ProjectDocument.from_dict(json.loads(self.project_json))

    def render_plan(self) -> RenderPlan:
        # Regenerate the typed plan from the frozen document. render_plan_json
        # remains immutable audit evidence and can be compared independently.
        return compile_render_plan(self.document())


def build_render_snapshot(document: ProjectDocument) -> RenderSnapshot:
    clone = document.clone()
    clone.validate()
    plan = compile_render_plan(clone)
    project_payload = clone.to_dict()
    project_json = json.dumps(project_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    plan_json = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256()
    digest.update(b"full-album-maker-render-snapshot-v1\0")
    digest.update(project_json.encode("utf-8"))
    digest.update(b"\0")
    digest.update(plan_json.encode("utf-8"))
    return RenderSnapshot(
        project_id=clone.project_id,
        project_revision=clone.revision,
        content_signature=clone.content_signature(),
        snapshot_hash=digest.hexdigest(),
        project_json=project_json,
        render_plan_json=plan_json,
        duration_tick=plan.duration_tick,
        timebase=plan.timebase,
    )


@dataclass(frozen=True)
class RenderMetrics:
    percent: float = 0.0
    rendered_seconds: float = 0.0
    fps: float | None = None
    average_fps: float | None = None
    speed: float | None = None
    eta_seconds: float | None = None

    def validate(self) -> None:
        if not 0.0 <= float(self.percent) <= 100.0:
            raise ValueError("Render percent harus 0..100.")
        for value in (self.rendered_seconds, self.fps, self.average_fps, self.speed, self.eta_seconds):
            if value is not None and (not math.isfinite(float(value)) or float(value) < 0):
                raise ValueError("Metric render tidak valid.")


@dataclass
class RenderJob:
    snapshot: RenderSnapshot
    settings: RenderSettings
    job_id: str = field(default_factory=lambda: str(uuid4()))
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    state: RenderJobState = RenderJobState.DRAFT
    metrics: RenderMetrics = field(default_factory=RenderMetrics)
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    finished_at: str = ""
    error_code: str = ""
    error_message: str = ""
    verified_output: str = ""
    log_lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.settings.validate()
        if self.snapshot.project_id == "" or self.snapshot.snapshot_hash == "":
            raise ValueError("Snapshot render tidak valid.")

    def transition(self, next_state: RenderJobState) -> None:
        next_state = RenderJobState(next_state)
        if next_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"Transisi RenderJob {self.state.value} -> {next_state.value} tidak valid.")
        self.state = next_state
        if next_state == RenderJobState.RUNNING and not self.started_at:
            self.started_at = utc_now_iso()
        if next_state in {RenderJobState.COMPLETED, RenderJobState.FAILED, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED}:
            self.finished_at = utc_now_iso()

    @property
    def can_pause(self) -> bool:
        # Recovered FFmpeg lifecycle has cancellation but no proven safe
        # pause/resume contract. Keep this fail-closed until capability exists.
        return False

    @property
    def can_cancel(self) -> bool:
        return self.state in {
            RenderJobState.PREFLIGHTING, RenderJobState.READY, RenderJobState.QUEUED,
            RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.PAUSED,
        }

    def retry(self) -> "RenderJob":
        if self.state not in {RenderJobState.FAILED, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED, RenderJobState.BLOCKED}:
            raise ValueError("Hanya job gagal/cancel/interrupted/blocked yang dapat dicoba ulang.")
        return RenderJob(snapshot=self.snapshot, settings=self.settings, job_id=self.job_id)
