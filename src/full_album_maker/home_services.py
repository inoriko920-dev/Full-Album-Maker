from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable

from .atomic_io import atomic_write_text
from .home_state import (
    ProjectOpenResult,
    QuickDefaults,
    RecentAvailability,
    RecentProject,
    RecoveryCandidate,
    RecoveryValidation,
)
from .paths import data_dir, output_dir
from .project import Project
from .project_io import load_project, save_project


def stable_project_id(path: str | Path) -> str:
    """Path-derived stable ID for legacy v1 project files that have no project_id."""

    value = str(Path(path).expanduser().resolve(strict=False)).casefold()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


class HomeProjectService:
    """Create/open legacy project files using the recovered project contract.

    STEP 02 deliberately reuses project_io instead of inventing another schema.
    Mutating the live application object remains the window/controller's job and
    happens only after these methods return success.
    """

    @staticmethod
    def create(path: str | Path, defaults: QuickDefaults) -> tuple[ProjectOpenResult, Project | None]:
        defaults.validate()
        target = Path(path).expanduser()
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".json")
        if not target.name:
            return ProjectOpenResult.failed("PROJECT_PATH_INVALID", "Lokasi proyek tidak valid."), None

        project = Project()
        project.settings.width = defaults.width
        project.settings.height = defaults.height
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = Path(save_project(str(target), project))
        except (OSError, ValueError, TypeError) as exc:
            return ProjectOpenResult.failed(
                "PROJECT_CREATE_FAILED",
                f"Proyek tidak dapat dibuat: {exc}",
                project_path=str(target),
            ), None

        return (
            ProjectOpenResult.ok(
                project_context=saved.stem,
                project_path=str(saved),
                project_id=stable_project_id(saved),
            ),
            project,
        )

    @staticmethod
    def open(path: str | Path) -> tuple[ProjectOpenResult, Project | None]:
        source = Path(path).expanduser()
        if not source.exists():
            return ProjectOpenResult.failed(
                "PROJECT_NOT_FOUND", "Proyek tidak ditemukan.", project_path=str(source)
            ), None
        if not source.is_file():
            return ProjectOpenResult.failed(
                "PROJECT_PATH_INVALID", "Lokasi proyek bukan file proyek.", project_path=str(source)
            ), None
        try:
            project = load_project(str(source))
        except PermissionError:
            return ProjectOpenResult.failed(
                "PROJECT_PERMISSION", "Proyek tidak dapat dibaca karena izin akses.", project_path=str(source)
            ), None
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            return ProjectOpenResult.failed(
                "PROJECT_CORRUPT", f"Proyek tidak dapat dibaca: {exc}", project_path=str(source)
            ), None

        return (
            ProjectOpenResult.ok(
                project_context=source.stem,
                project_path=str(source.resolve(strict=False)),
                project_id=stable_project_id(source),
            ),
            project,
        )


class RecentProjectsService:
    VERSION = 1

    def __init__(self, index_path: str | Path | None = None) -> None:
        self.index_path = Path(index_path) if index_path is not None else data_dir() / "recent_projects.json"

    def load(self) -> list[RecentProject]:
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(raw, dict) or raw.get("version") != self.VERSION or not isinstance(raw.get("items"), list):
            return []

        values: list[RecentProject] = []
        for item in raw["items"]:
            if not isinstance(item, dict):
                continue
            try:
                path = str(item["path"])
                recent = RecentProject(
                    project_id=str(item.get("project_id") or stable_project_id(path)),
                    path=path,
                    display_name=str(item.get("display_name") or Path(path).stem),
                    last_opened=float(item.get("last_opened", 0.0)),
                    song_count=None if item.get("song_count") is None else int(item.get("song_count")),
                    duration_seconds=None if item.get("duration_seconds") is None else float(item.get("duration_seconds")),
                    thumbnail_ref=item.get("thumbnail_ref") or None,
                    availability=(
                        RecentAvailability.AVAILABLE
                        if Path(path).exists()
                        else RecentAvailability.MISSING
                    ),
                    error_detail=str(item.get("error_detail", "") or ""),
                )
                recent.validate()
            except (KeyError, TypeError, ValueError):
                continue
            values.append(recent)
        values.sort(key=lambda value: value.last_opened, reverse=True)
        return values

    def save(self, items: Iterable[RecentProject]) -> None:
        clean = sorted(items, key=lambda value: value.last_opened, reverse=True)
        for item in clean:
            item.validate()
        payload = {
            "version": self.VERSION,
            "items": [
                {
                    **asdict(item),
                    "availability": item.availability.value,
                }
                for item in clean[:100]
            ],
        }
        atomic_write_text(
            self.index_path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def touch(self, path: str | Path, project: Project, *, opened_at: float | None = None) -> RecentProject:
        source = Path(path).resolve(strict=False)
        project_id = stable_project_id(source)
        item = RecentProject(
            project_id=project_id,
            path=str(source),
            display_name=source.stem or "Proyek Full Album",
            last_opened=float(time.time() if opened_at is None else opened_at),
            song_count=len(project.audios),
            duration_seconds=project.total_audio_duration,
            availability=RecentAvailability.AVAILABLE,
        )
        values = [value for value in self.load() if value.project_id != project_id]
        values.insert(0, item)
        self.save(values)
        return item

    def remove(self, project_id: str) -> None:
        self.save(value for value in self.load() if value.project_id != project_id)


class QuickDefaultsStore:
    VERSION = 1

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "home_defaults.json"

    @staticmethod
    def default_value() -> QuickDefaults:
        return QuickDefaults(output_folder=str(output_dir()))

    def load(self) -> QuickDefaults:
        fallback = self.default_value()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return fallback
        if not isinstance(raw, dict) or raw.get("version") != self.VERSION:
            return fallback
        try:
            value = QuickDefaults(
                ratio_id=str(raw.get("ratio_id", fallback.ratio_id)),
                resolution_id=str(raw.get("resolution_id", fallback.resolution_id)),
                width=int(raw.get("width", fallback.width)),
                height=int(raw.get("height", fallback.height)),
                output_folder=str(raw.get("output_folder", fallback.output_folder)),
            )
            value.validate()
            return value
        except (TypeError, ValueError):
            return fallback

    def save(self, value: QuickDefaults) -> None:
        value.validate()
        payload = {"version": self.VERSION, **asdict(value)}
        atomic_write_text(self.path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def output_is_writable(value: QuickDefaults) -> bool:
        folder = Path(value.output_folder).expanduser()
        if not value.output_folder.strip():
            return False
        if folder.exists():
            return folder.is_dir() and os.access(folder, os.W_OK)
        parent = folder.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        return parent.is_dir() and os.access(parent, os.W_OK)


class RecoveryService:
    """Single safe legacy-project recovery snapshot for STEP 02.

    Dismissal is handled only in HomeViewState and never deletes this snapshot.
    Restore validates by parsing into a new Project before the live window swaps
    its current project reference.
    """

    def __init__(self, snapshot_path: str | Path | None = None) -> None:
        self.snapshot_path = Path(snapshot_path) if snapshot_path is not None else data_dir() / "recovery" / "home_autosave.json"

    def write_snapshot(self, project: Project) -> RecoveryCandidate:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        saved = Path(save_project(str(self.snapshot_path), project))
        timestamp = saved.stat().st_mtime
        return RecoveryCandidate(
            candidate_id=hashlib.sha256(str(saved.resolve(strict=False)).encode("utf-8")).hexdigest()[:24],
            path=str(saved),
            timestamp=timestamp,
            project_identity="legacy-project-v1",
            validation_state=RecoveryValidation.VALID,
        )

    def discover(self) -> RecoveryCandidate | None:
        source = self.snapshot_path
        if not source.exists() or not source.is_file():
            return None
        candidate_id = hashlib.sha256(str(source.resolve(strict=False)).encode("utf-8")).hexdigest()[:24]
        try:
            load_project(str(source))
            state = RecoveryValidation.VALID
            detail = ""
        except Exception as exc:
            state = RecoveryValidation.INVALID
            detail = str(exc)
        return RecoveryCandidate(
            candidate_id=candidate_id,
            path=str(source),
            timestamp=source.stat().st_mtime,
            project_identity="legacy-project-v1",
            validation_state=state,
            detail=detail,
        )

    def restore(self, candidate: RecoveryCandidate) -> tuple[ProjectOpenResult, Project | None]:
        candidate.validate()
        source = Path(candidate.path)
        if source.resolve(strict=False) != self.snapshot_path.resolve(strict=False):
            return ProjectOpenResult.failed("RECOVERY_INVALID", "Snapshot recovery tidak dikenali."), None
        if candidate.validation_state != RecoveryValidation.VALID:
            return ProjectOpenResult.failed("RECOVERY_INVALID", "Autosave tidak dapat dipulihkan."), None
        try:
            project = load_project(str(source))
        except Exception as exc:
            return ProjectOpenResult.failed("RECOVERY_INVALID", f"Autosave tidak dapat dipulihkan: {exc}"), None
        return ProjectOpenResult.ok(
            project_context="Proyek Dipulihkan",
            project_path=str(source),
            project_id="recovery-" + candidate.candidate_id,
        ), project
