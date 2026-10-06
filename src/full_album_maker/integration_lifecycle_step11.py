from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Callable

from .atomic_io import atomic_write_text
from .editor_models import ProjectDocument
from .integration_core_step11 import normalized_project_hash, project_token
from .paths import data_dir


RECOVERY_FORMAT = "full-album-maker-step11-recovery"
RECOVERY_VERSION = 1


@dataclass(frozen=True)
class AutosaveRequest:
    generation: int
    project_token: str
    revision: int
    signature: str
    source_project_path: str
    document_payload: dict

    def document(self) -> ProjectDocument:
        return ProjectDocument.from_dict(deepcopy(self.document_payload))


@dataclass(frozen=True)
class AutosaveStatus:
    latest_generation: int = 0
    latest_revision: int = 0
    latest_signature: str = ""
    last_success_generation: int = 0
    last_success_revision: int = 0
    last_success_signature: str = ""
    last_error: str = ""

    @property
    def pending(self) -> bool:
        return self.latest_generation > self.last_success_generation


@dataclass(frozen=True)
class RecoveryEnvelope:
    project_token: str
    revision: int
    signature: str
    source_project_path: str
    saved_at_utc: str
    document_payload: dict

    def document(self) -> ProjectDocument:
        document = ProjectDocument.from_dict(deepcopy(self.document_payload))
        if document.revision != self.revision:
            raise ValueError("Revision recovery tidak cocok dengan payload ProjectDocument.")
        if normalized_project_hash(document) != self.signature:
            raise ValueError("Signature recovery tidak cocok dengan ProjectDocument.")
        return document

    def to_dict(self) -> dict:
        return {
            "format": RECOVERY_FORMAT,
            "version": RECOVERY_VERSION,
            "project_token": self.project_token,
            "revision": self.revision,
            "signature": self.signature,
            "source_project_path": self.source_project_path,
            "saved_at_utc": self.saved_at_utc,
            "document": deepcopy(self.document_payload),
        }

    @classmethod
    def from_dict(cls, raw: object) -> "RecoveryEnvelope":
        if not isinstance(raw, dict):
            raise ValueError("Recovery envelope bukan object JSON.")
        if raw.get("format") != RECOVERY_FORMAT or int(raw.get("version", 0)) != RECOVERY_VERSION:
            raise ValueError("Format/versi recovery STEP11 tidak didukung.")
        document_payload = raw.get("document")
        if not isinstance(document_payload, dict):
            raise ValueError("Recovery tidak berisi ProjectDocument.")
        item = cls(
            project_token=str(raw.get("project_token", "")),
            revision=int(raw.get("revision", 0)),
            signature=str(raw.get("signature", "")),
            source_project_path=str(raw.get("source_project_path", "")),
            saved_at_utc=str(raw.get("saved_at_utc", "")),
            document_payload=deepcopy(document_payload),
        )
        if not item.project_token or not item.signature:
            raise ValueError("Recovery tidak memiliki identity/signature.")
        item.document()
        return item


class IntegrationRecoveryStore:
    """Atomic STEP11 recovery file, intentionally separate from canonical project."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "recovery" / "integration_autosave_v2.json"

    def write(self, request: AutosaveRequest) -> RecoveryEnvelope:
        document = request.document()
        envelope = RecoveryEnvelope(
            project_token=request.project_token,
            revision=request.revision,
            signature=request.signature,
            source_project_path=request.source_project_path,
            saved_at_utc=datetime.now(timezone.utc).isoformat(),
            document_payload=document.to_dict(),
        )
        # Revalidate exact serialized envelope before publishing.
        RecoveryEnvelope.from_dict(envelope.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps(envelope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return envelope

    def discover(self) -> RecoveryEnvelope | None:
        if not self.path.is_file():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return RecoveryEnvelope.from_dict(raw)
        except Exception:
            return None

    def load_strict(self) -> RecoveryEnvelope:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return RecoveryEnvelope.from_dict(raw)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


class DebouncedAutosaveCoordinator:
    """Pure generation/coalescing state for UI timer + background writer.

    `request()` captures an immutable committed revision. A UI-level debounce timer
    later calls `take_pending()`. The returned request can be written on a worker.
    `complete()` ignores stale generations for user-facing latest-success state.
    Autosave never marks canonical dirty state saved.
    """

    def __init__(self) -> None:
        self._generation = 0
        self._latest: AutosaveRequest | None = None
        self._status = AutosaveStatus()

    @property
    def status(self) -> AutosaveStatus:
        return self._status

    def request(self, document: ProjectDocument, *, project_path: str = "", token: str = "") -> AutosaveRequest:
        snapshot = document.clone()
        snapshot.validate()
        self._generation += 1
        identity = token or project_token(snapshot, project_path)
        request = AutosaveRequest(
            generation=self._generation,
            project_token=identity,
            revision=snapshot.revision,
            signature=normalized_project_hash(snapshot),
            source_project_path=str(project_path or ""),
            document_payload=snapshot.to_dict(),
        )
        self._latest = request
        self._status = AutosaveStatus(
            latest_generation=request.generation,
            latest_revision=request.revision,
            latest_signature=request.signature,
            last_success_generation=self._status.last_success_generation,
            last_success_revision=self._status.last_success_revision,
            last_success_signature=self._status.last_success_signature,
            last_error=self._status.last_error,
        )
        return request

    def take_pending(self) -> AutosaveRequest | None:
        request = self._latest
        self._latest = None
        return request

    def complete(self, request: AutosaveRequest, *, success: bool, error: str = "") -> AutosaveStatus:
        current = self._status
        # A stale worker may finish after a newer edit. Keep its file on disk as a
        # valid snapshot, but never claim the latest revision autosaved.
        is_latest = request.generation == current.latest_generation
        if success and is_latest:
            self._status = AutosaveStatus(
                latest_generation=current.latest_generation,
                latest_revision=current.latest_revision,
                latest_signature=current.latest_signature,
                last_success_generation=request.generation,
                last_success_revision=request.revision,
                last_success_signature=request.signature,
                last_error="",
            )
        elif not success and is_latest:
            self._status = AutosaveStatus(
                latest_generation=current.latest_generation,
                latest_revision=current.latest_revision,
                latest_signature=current.latest_signature,
                last_success_generation=current.last_success_generation,
                last_success_revision=current.last_success_revision,
                last_success_signature=current.last_success_signature,
                last_error=str(error or "Autosave gagal."),
            )
        return self._status


def request_from_document(document: ProjectDocument, *, project_path: str = "", generation: int = 1) -> AutosaveRequest:
    """Deterministic helper for recovery tests/tools without coordinator state."""

    snapshot = document.clone()
    return AutosaveRequest(
        generation=int(generation),
        project_token=project_token(snapshot, project_path),
        revision=snapshot.revision,
        signature=normalized_project_hash(snapshot),
        source_project_path=str(project_path or ""),
        document_payload=snapshot.to_dict(),
    )


def extract_project_document_from_saved_json(path: str | Path) -> ProjectDocument:
    """Understand both native ProjectDocument v2 and the legacy compatibility envelope."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("File project bukan object JSON.")
    if raw.get("format") == "full-album-maker-project":
        return ProjectDocument.from_dict(raw)
    embedded = raw.get("album_document_v2")
    if isinstance(embedded, dict):
        return ProjectDocument.from_dict(embedded)
    raise ValueError("File project tidak membawa ProjectDocument authoritative.")


def verify_persisted_document(path: str | Path, expected: ProjectDocument) -> bool:
    restored = extract_project_document_from_saved_json(path)
    return normalized_project_hash(restored) == normalized_project_hash(expected)


def save_verified_legacy_project(
    path: str | Path,
    project,
    expected: ProjectDocument,
    *,
    verifier: Callable[[str | Path, ProjectDocument], bool] = verify_persisted_document,
) -> str:
    """Stage, semantically verify, then atomically publish a legacy project envelope.

    The canonical target is never touched until the staged JSON has been parsed
    back into the authoritative ProjectDocument and its normalized hash matches
    the expected document. Stage and target live in the same directory so
    os.replace is an atomic same-filesystem publish.
    """

    target = Path(path)
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, stage_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".stage.json",
        dir=str(target.parent),
    )
    os.close(fd)
    stage = Path(stage_name)
    try:
        payload = json.dumps(project.to_dict(), ensure_ascii=False, indent=2)
        atomic_write_text(stage, payload, encoding="utf-8")
        if not verifier(stage, expected):
            raise ValueError(
                "Project staged tidak sama dengan ProjectDocument authoritative."
            )
        os.replace(stage, target)
        return str(target)
    finally:
        stage.unlink(missing_ok=True)
