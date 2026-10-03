from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

from .custom_template_builder import CustomTemplate
from .editor_models import ProjectDocument
from .paths import data_dir, ffmpeg_path
from .template_studio_step07 import (
    TemplateStudioDescriptor,
    TemplateStudioDraft,
    preview_template_document,
    template_payload_hash,
)
from .template_thumbnail import TemplateThumbnailError, template_thumbnail_tick
from .v13_render_graph import V13FFmpegCompiler

CACHE_FORMAT = "step07-template-thumbnail-cache-v1"


def thumbnail_cache_key(
    document: ProjectDocument,
    descriptor: TemplateStudioDescriptor,
    draft: TemplateStudioDraft,
    custom_template: CustomTemplate | None = None,
) -> str:
    descriptor.validate()
    draft.validate()
    payload: dict[str, object] = {
        "format": CACHE_FORMAT,
        "template_id": descriptor.template_id,
        "origin": descriptor.origin,
        "template_payload": template_payload_hash(descriptor, draft),
        "ratio": draft.ratio,
        "document_signature": document.content_signature(),
    }
    if custom_template is not None:
        custom_template.validate()
        payload["custom_payload"] = custom_template.to_dict()
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def render_preview_thumbnail(
    document: ProjectDocument,
    descriptor: TemplateStudioDescriptor,
    draft: TemplateStudioDraft,
    custom_template: CustomTemplate | None,
    destination: Path,
) -> str:
    executable = ffmpeg_path()
    if not executable:
        raise TemplateThumbnailError("FFmpeg tidak tersedia; gunakan thumbnail fallback lokal.")
    if not document.playlist.entries:
        raise TemplateThumbnailError("Thumbnail template membutuhkan minimal satu lagu aktif.")

    target = (document.playlist.entries[0].song_id,)
    preview = preview_template_document(
        document,
        draft,
        target,
        custom_template=custom_template,
    )
    tick = template_thumbnail_tick(preview)
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, stage_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.",
        suffix=".template-preview.png",
        dir=destination.parent,
    )
    os.close(fd)
    stage = Path(stage_name)
    stage.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.stem}.work-",
            dir=destination.parent,
        ) as work:
            compiled = V13FFmpegCompiler(executable).compile_frame(preview, tick, stage, work)
            completed = subprocess.run(
                compiled.args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
            )
            if completed.returncode != 0:
                tail = "\n".join((completed.stderr or completed.stdout or "").splitlines()[-8:])
                raise TemplateThumbnailError(
                    "Render thumbnail template gagal." + (f"\n{tail}" if tail else "")
                )
            if not stage.exists() or stage.stat().st_size <= 0:
                raise TemplateThumbnailError("FFmpeg tidak menghasilkan thumbnail template.")
            os.replace(stage, destination)
    finally:
        stage.unlink(missing_ok=True)
    return str(destination)


Renderer = Callable[
    [ProjectDocument, TemplateStudioDescriptor, TemplateStudioDraft, CustomTemplate | None, Path],
    str,
]


class TemplateThumbnailCache(QObject):
    """Non-blocking thumbnail cache with deterministic invalidation.

    Gallery cards always have a local painted fallback. A request may replace
    it with a rendered PNG later. Render failure is memoized for the current
    cache key so an environment without FFmpeg does not retry on every refresh.
    A changed template/draft/document produces a new key and may try again.
    """

    thumbnail_ready = Signal(str, str, str)

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        renderer: Renderer | None = None,
        max_workers: int = 2,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.root = Path(root) if root is not None else data_dir() / "cache" / "template_thumbnails_v1"
        self.root.mkdir(parents=True, exist_ok=True)
        self._renderer = renderer or render_preview_thumbnail
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="fam-template-thumb",
        )
        self._lock = threading.Lock()
        self._pending: dict[str, Future] = {}
        self._failed_keys: set[str] = set()

    def path_for_key(self, key: str) -> Path:
        return self.root / f"{key}.png"

    def request(
        self,
        document: ProjectDocument,
        descriptor: TemplateStudioDescriptor,
        draft: TemplateStudioDraft,
        *,
        custom_template: CustomTemplate | None = None,
    ) -> str | None:
        key = thumbnail_cache_key(document, descriptor, draft, custom_template)
        destination = self.path_for_key(key)
        if destination.is_file() and destination.stat().st_size > 0:
            self.thumbnail_ready.emit(descriptor.template_id, str(destination), "CACHE_HIT")
            return str(destination)

        with self._lock:
            if key in self._failed_keys or key in self._pending:
                return None
            snapshot = document.clone()
            draft_copy = deepcopy(draft)
            descriptor_copy = deepcopy(descriptor)
            custom_copy = (
                CustomTemplate.from_dict(custom_template.to_dict())
                if custom_template is not None
                else None
            )
            future = self._executor.submit(
                self._run_job,
                snapshot,
                descriptor_copy,
                draft_copy,
                custom_copy,
                destination,
            )
            self._pending[key] = future

        # Register callback after releasing the lock. A test renderer can finish
        # immediately; adding a callback while holding the same lock can invoke
        # _finish synchronously and deadlock.
        future.add_done_callback(lambda done, cache_key=key: self._finish(cache_key, done))
        return None

    def _run_job(
        self,
        document: ProjectDocument,
        descriptor: TemplateStudioDescriptor,
        draft: TemplateStudioDraft,
        custom_template: CustomTemplate | None,
        destination: Path,
    ) -> tuple[str, str, str]:
        try:
            rendered = Path(
                self._renderer(document, descriptor, draft, custom_template, destination)
            )
            if not rendered.is_file() or rendered.stat().st_size <= 0:
                raise TemplateThumbnailError(
                    "Renderer thumbnail tidak menghasilkan file yang dapat dipakai."
                )
            return descriptor.template_id, str(rendered), "RENDERED"
        except Exception:
            destination.unlink(missing_ok=True)
            return descriptor.template_id, "", "FALLBACK"

    def _finish(self, key: str, future: Future) -> None:
        try:
            template_id, path, status = future.result()
        except Exception:
            template_id, path, status = "", "", "FALLBACK"
        with self._lock:
            self._pending.pop(key, None)
            if status == "FALLBACK":
                self._failed_keys.add(key)
            else:
                self._failed_keys.discard(key)
        self.thumbnail_ready.emit(template_id, path, status)

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        with self._lock:
            pending = tuple(self._pending.values())
        if not pending:
            return True
        _done, not_done = wait(pending, timeout=max(0.0, float(timeout)))
        return not not_done

    def clear_failed(self) -> None:
        with self._lock:
            self._failed_keys.clear()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
