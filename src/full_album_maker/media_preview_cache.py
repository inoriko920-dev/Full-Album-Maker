from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
from typing import Callable

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QImageReader

from .media_library_model import MediaAsset, MediaStatus, MediaType
from .media_library_services import canonical_path_key
from .paths import data_dir, ffmpeg_path


CACHE_VERSION = 1
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360


@dataclass(frozen=True)
class PreviewResult:
    asset_id: str
    path: str = ""
    error: str = ""
    generation: int = 0


def _source_fingerprint(asset: MediaAsset) -> str:
    source = Path(asset.path)
    try:
        stat = source.stat()
        size = stat.st_size
        mtime_ns = stat.st_mtime_ns
    except OSError:
        size = -1
        mtime_ns = -1
    raw = (
        f"v{CACHE_VERSION}\0{asset.media_type.value}\0"
        f"{canonical_path_key(asset.path)}\0{size}\0{mtime_ns}\0"
        f"{PREVIEW_WIDTH}x{PREVIEW_HEIGHT}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_root() -> Path:
    root = data_dir() / "cache" / "media-previews"
    root.mkdir(parents=True, exist_ok=True)
    return root


def preview_cache_path(asset: MediaAsset) -> Path:
    return _cache_root() / f"{_source_fingerprint(asset)}.png"


def _metadata_path(cache_path: Path) -> Path:
    return cache_path.with_suffix(".json")


def _write_metadata(cache_path: Path, asset: MediaAsset) -> None:
    payload = {
        "version": CACHE_VERSION,
        "asset_id": asset.asset_id,
        "source_key": canonical_path_key(asset.path),
        "media_type": asset.media_type.value,
        "preview": cache_path.name,
    }
    _metadata_path(cache_path).write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _atomic_replace_png(temp_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.replace(final_path)


def _generate_photo(source: Path, target: Path) -> None:
    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        scaled = size.scaled(
            QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        reader.setScaledSize(scaled)
    image = reader.read()
    if image.isNull():
        raise RuntimeError(reader.errorString() or "Foto tidak dapat didekode")
    if not image.save(str(target), "PNG"):
        raise RuntimeError("Preview foto tidak dapat disimpan")


def _run_ffmpeg(args: list[str], timeout: int = 45) -> None:
    tool = ffmpeg_path()
    if not tool:
        raise RuntimeError("FFmpeg belum tersedia untuk membuat preview")
    proc = subprocess.run(
        [tool, "-nostdin", "-y", "-v", "error", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        message = (proc.stderr or "").strip() or f"FFmpeg exit {proc.returncode}"
        raise RuntimeError(message[:600])


def _generate_video(source: Path, target: Path) -> None:
    _run_ffmpeg(
        [
            "-ss",
            "0.5",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease",
            str(target),
        ]
    )


def _generate_audio(source: Path, target: Path) -> None:
    _run_ffmpeg(
        [
            "-i",
            str(source),
            "-filter_complex",
            f"aformat=channel_layouts=mono,showwavespic=s={PREVIEW_WIDTH}x180:colors=0x6FA7FF",
            "-frames:v",
            "1",
            str(target),
        ]
    )


def generate_preview(asset: MediaAsset) -> str:
    """Build or reuse one disposable cached preview.

    Cache identity includes path, media type, file size, and mtime. A changed or
    relinked source therefore never reuses a stale preview even if explicit cache
    cleanup is skipped. Source media is opened read-only and never moved/edited.
    """
    if asset.status == MediaStatus.MISSING:
        raise FileNotFoundError(asset.path)
    source = Path(asset.path)
    if not source.is_file():
        raise FileNotFoundError(asset.path)
    target = preview_cache_path(asset)
    if target.is_file() and target.stat().st_size > 0:
        return str(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=target.stem + ".", suffix=".png", dir=str(target.parent))
    import os
    os.close(fd)
    # Generators need to create the image themselves; remove the empty mkstemp file.
    temp_path = Path(temp_name)
    temp_path.unlink(missing_ok=True)
    try:
        if asset.media_type == MediaType.PHOTO:
            _generate_photo(source, temp_path)
        elif asset.media_type == MediaType.VIDEO:
            _generate_video(source, temp_path)
        else:
            _generate_audio(source, temp_path)
        if not temp_path.is_file() or temp_path.stat().st_size <= 0:
            raise RuntimeError("Preview cache kosong")
        _atomic_replace_png(temp_path, target)
        _write_metadata(target, asset)
        return str(target)
    finally:
        temp_path.unlink(missing_ok=True)


def invalidate_source(path: str | Path) -> int:
    """Remove disposable cache entries that belong to one source path."""
    root = _cache_root()
    source_key = canonical_path_key(path)
    removed = 0
    for metadata in root.glob("*.json"):
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if payload.get("source_key") != source_key:
            continue
        preview = root / str(payload.get("preview") or metadata.with_suffix(".png").name)
        for candidate in (preview, metadata):
            try:
                candidate.unlink()
                removed += 1
            except FileNotFoundError:
                pass
            except OSError:
                pass
    return removed


class MediaPreviewCache(QObject):
    """Bounded daemon-worker preview queue with de-duplication and stale guards."""

    preview_ready = Signal(object)
    jobs_changed = Signal(int)

    def __init__(self, parent=None, *, workers: int = 2) -> None:
        super().__init__(parent)
        self._queue: queue.Queue[tuple[int, MediaAsset] | None] = queue.Queue()
        self._lock = threading.Lock()
        self._pending: set[tuple[int, str]] = set()
        self._generation = 0
        self._jobs = 0
        for index in range(max(1, min(4, int(workers)))):
            thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name=f"fam-media-preview-{index + 1}",
            )
            thread.start()

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def job_count(self) -> int:
        with self._lock:
            return self._jobs

    def reset(self) -> None:
        """Invalidate callbacks from older project state without blocking the UI."""
        with self._lock:
            self._generation += 1
            self._pending.clear()

    def request(self, asset: MediaAsset) -> bool:
        if asset.status == MediaStatus.MISSING:
            return False
        target = preview_cache_path(asset)
        if target.is_file() and target.stat().st_size > 0:
            self.preview_ready.emit(
                PreviewResult(asset_id=asset.asset_id, path=str(target), generation=self.generation)
            )
            return True
        with self._lock:
            generation = self._generation
            key = (generation, asset.asset_id)
            if key in self._pending:
                return False
            self._pending.add(key)
            self._jobs += 1
            jobs = self._jobs
        self.jobs_changed.emit(jobs)
        self._queue.put((generation, asset))
        return True

    def _worker(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            generation, asset = job
            try:
                path = generate_preview(asset)
                error = ""
            except Exception as exc:
                path = ""
                error = str(exc)
            with self._lock:
                self._pending.discard((generation, asset.asset_id))
                self._jobs = max(0, self._jobs - 1)
                jobs = self._jobs
                current = self._generation
            self.jobs_changed.emit(jobs)
            if generation == current:
                self.preview_ready.emit(
                    PreviewResult(
                        asset_id=asset.asset_id,
                        path=path,
                        error=error,
                        generation=generation,
                    )
                )
