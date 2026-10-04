from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any


class HomeMode(str, Enum):
    """Stable STEP 02 Home state IDs; labels are presentation-only."""

    IDLE = "HOME_IDLE"
    RECOVERY_AVAILABLE = "HOME_RECOVERY_AVAILABLE"
    NO_RECOVERY = "HOME_NO_RECOVERY"
    PROJECT_LOADING = "HOME_PROJECT_LOADING"
    PROJECT_OPEN = "HOME_PROJECT_OPEN"
    OPEN_ERROR = "HOME_OPEN_ERROR"
    FIRST_RUN = "HOME_FIRST_RUN"
    PORTABLE_WARNING = "HOME_PORTABLE_WARNING"
    OUTPUT_INVALID = "HOME_OUTPUT_INVALID"


class RecentAvailability(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    CORRUPT = "corrupt"
    UNKNOWN = "unknown"


class RecoveryValidation(str, Enum):
    CANDIDATE = "candidate"
    VALID = "valid"
    INVALID = "invalid"


class CapabilityState(str, Enum):
    READY = "ready"
    OPTIONAL = "optional"
    WARNING = "warning"
    CHECKING = "checking"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RecoveryCandidate:
    candidate_id: str
    path: str
    timestamp: float
    project_identity: str = ""
    validation_state: RecoveryValidation = RecoveryValidation.CANDIDATE
    detail: str = ""

    def validate(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("Recovery candidate harus memiliki ID stabil.")
        if not self.path.strip():
            raise ValueError("Recovery candidate harus memiliki path.")
        if self.timestamp < 0:
            raise ValueError("Timestamp recovery tidak valid.")


@dataclass(frozen=True)
class RecentProject:
    project_id: str
    path: str
    display_name: str
    last_opened: float
    song_count: int | None = None
    duration_seconds: float | None = None
    thumbnail_ref: str | None = None
    availability: RecentAvailability = RecentAvailability.UNKNOWN
    error_detail: str = ""

    def validate(self) -> None:
        if not self.project_id.strip():
            raise ValueError("Recent project harus memiliki project_id.")
        if not self.path.strip():
            raise ValueError("Recent project harus memiliki path.")
        if not self.display_name.strip():
            raise ValueError("Recent project harus memiliki nama tampilan.")
        if self.last_opened < 0:
            raise ValueError("last_opened tidak valid.")
        if self.song_count is not None and self.song_count < 0:
            raise ValueError("song_count tidak valid.")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds tidak valid.")

    @property
    def filename(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class PortableStatus:
    ffmpeg: CapabilityState = CapabilityState.CHECKING
    manual_offline: CapabilityState = CapabilityState.READY
    ai_config: CapabilityState = CapabilityState.OPTIONAL
    ffmpeg_detail: str = "Memeriksa FFmpeg portable…"
    manual_detail: str = "Editing manual tersedia tanpa AI."
    ai_detail: str = "AI opsional dan belum dikonfigurasi."

    @property
    def has_warning(self) -> bool:
        return any(
            state in {CapabilityState.WARNING, CapabilityState.UNAVAILABLE}
            for state in (self.ffmpeg, self.manual_offline, self.ai_config)
        )


@dataclass(frozen=True)
class QuickDefaults:
    """Home defaults; stable IDs are separated from UI labels."""

    ratio_id: str = "16:9"
    resolution_id: str = "1080p"
    width: int = 1920
    height: int = 1080
    output_folder: str = ""

    def validate(self) -> None:
        if self.ratio_id not in {"16:9", "4:3", "1:1", "9:16"}:
            raise ValueError("Rasio video tidak didukung.")
        if self.resolution_id not in {"720p", "1080p", "1440p", "2160p"}:
            raise ValueError("Preset resolusi tidak didukung.")
        if not 320 <= self.width <= 7680 or not 240 <= self.height <= 4320:
            raise ValueError("Resolusi video tidak valid.")
        if self.width % 2 or self.height % 2:
            raise ValueError("Resolusi video harus genap.")


@dataclass(frozen=True)
class ProjectOpenResult:
    success: bool
    error_code: str = ""
    message: str = ""
    project_context: str = ""
    project_path: str = ""
    project_id: str = ""

    @classmethod
    def ok(cls, *, project_context: str, project_path: str, project_id: str = "") -> "ProjectOpenResult":
        return cls(True, project_context=project_context, project_path=project_path, project_id=project_id)

    @classmethod
    def failed(cls, error_code: str, message: str, *, project_path: str = "") -> "ProjectOpenResult":
        return cls(False, error_code=str(error_code), message=str(message), project_path=str(project_path))


@dataclass(frozen=True)
class HomeViewState:
    mode: HomeMode = HomeMode.IDLE
    loading_action: str = ""
    error_code: str = ""
    error_message: str = ""
    recovery: RecoveryCandidate | None = None
    recent_projects: tuple[RecentProject, ...] = field(default_factory=tuple)
    quick_defaults: QuickDefaults = field(default_factory=QuickDefaults)
    capabilities: PortableStatus = field(default_factory=PortableStatus)
    recovery_dismissed_for_session: bool = False
    current_project_path: str = ""
    current_project_name: str = ""

    def validate(self) -> None:
        self.quick_defaults.validate()
        if self.recovery is not None:
            self.recovery.validate()
        for recent in self.recent_projects:
            recent.validate()
        if self.mode == HomeMode.PROJECT_LOADING and not self.loading_action:
            raise ValueError("HOME_PROJECT_LOADING membutuhkan loading_action.")
        if self.mode == HomeMode.OPEN_ERROR and not self.error_message:
            raise ValueError("HOME_OPEN_ERROR membutuhkan error_message.")
        if self.mode == HomeMode.RECOVERY_AVAILABLE:
            if self.recovery is None or self.recovery.validation_state != RecoveryValidation.VALID:
                raise ValueError("HOME_RECOVERY_AVAILABLE membutuhkan candidate recovery yang valid.")

    def begin(self, action_id: str) -> "HomeViewState":
        action_id = str(action_id).strip()
        if not action_id:
            raise ValueError("action_id tidak boleh kosong.")
        return replace(
            self,
            mode=HomeMode.PROJECT_LOADING,
            loading_action=action_id,
            error_code="",
            error_message="",
        )

    def fail(self, error_code: str, message: str) -> "HomeViewState":
        message = str(message).strip()
        if not message:
            raise ValueError("Pesan error tidak boleh kosong.")
        return replace(
            self,
            mode=HomeMode.OPEN_ERROR,
            loading_action="",
            error_code=str(error_code).strip() or "HOME_ERROR",
            error_message=message,
        )

    def with_recent(self, recent_projects: list[RecentProject] | tuple[RecentProject, ...]) -> "HomeViewState":
        ordered = tuple(sorted(recent_projects, key=lambda item: item.last_opened, reverse=True))
        mode = self.mode
        if not ordered and mode in {HomeMode.IDLE, HomeMode.NO_RECOVERY}:
            mode = HomeMode.FIRST_RUN
        return replace(self, recent_projects=ordered, mode=mode)

    def with_valid_recovery(self, candidate: RecoveryCandidate | None) -> "HomeViewState":
        if candidate is None or self.recovery_dismissed_for_session:
            mode = HomeMode.FIRST_RUN if not self.recent_projects else HomeMode.NO_RECOVERY
            return replace(self, recovery=None, mode=mode)
        candidate.validate()
        if candidate.validation_state != RecoveryValidation.VALID:
            raise ValueError("Recovery banner hanya boleh memakai candidate yang valid.")
        return replace(self, recovery=candidate, mode=HomeMode.RECOVERY_AVAILABLE)

    def dismiss_recovery(self) -> "HomeViewState":
        mode = HomeMode.FIRST_RUN if not self.recent_projects else HomeMode.NO_RECOVERY
        return replace(
            self,
            recovery=None,
            recovery_dismissed_for_session=True,
            mode=mode,
        )

    def project_opened(self, result: ProjectOpenResult) -> "HomeViewState":
        if not result.success:
            return self.fail(result.error_code or "PROJECT_OPEN_FAILED", result.message or "Proyek tidak dapat dibuka.")
        return replace(
            self,
            mode=HomeMode.PROJECT_OPEN,
            loading_action="",
            error_code="",
            error_message="",
            current_project_path=result.project_path,
            current_project_name=result.project_context,
        )

    def with_capabilities(self, value: PortableStatus) -> "HomeViewState":
        mode = self.mode
        if mode in {HomeMode.IDLE, HomeMode.NO_RECOVERY, HomeMode.FIRST_RUN, HomeMode.PORTABLE_WARNING}:
            if value.has_warning:
                mode = HomeMode.PORTABLE_WARNING
            elif mode == HomeMode.PORTABLE_WARNING:
                mode = HomeMode.FIRST_RUN if not self.recent_projects else HomeMode.NO_RECOVERY
        return replace(self, capabilities=value, mode=mode)

    def with_quick_defaults(self, value: QuickDefaults, *, output_valid: bool = True) -> "HomeViewState":
        value.validate()
        mode = self.mode
        if mode not in {HomeMode.PROJECT_LOADING, HomeMode.OPEN_ERROR}:
            if not output_valid:
                mode = HomeMode.OUTPUT_INVALID
            elif mode == HomeMode.OUTPUT_INVALID:
                mode = HomeMode.FIRST_RUN if not self.recent_projects else HomeMode.NO_RECOVERY
        return replace(self, quick_defaults=value, mode=mode)

    def as_debug_dict(self) -> dict[str, Any]:
        """Small non-secret diagnostic snapshot; never serializes credentials."""

        return {
            "mode": self.mode.value,
            "loading_action": self.loading_action,
            "error_code": self.error_code,
            "recovery": None if self.recovery is None else self.recovery.validation_state.value,
            "recent_count": len(self.recent_projects),
            "ratio_id": self.quick_defaults.ratio_id,
            "resolution_id": self.quick_defaults.resolution_id,
            "ffmpeg": self.capabilities.ffmpeg.value,
            "manual_offline": self.capabilities.manual_offline.value,
            "ai_config": self.capabilities.ai_config.value,
        }
