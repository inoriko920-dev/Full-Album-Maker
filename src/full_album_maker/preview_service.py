from __future__ import annotations

from pathlib import Path
import tempfile

from .editor_models import ProjectDocument
from .beat_visual_runtime import apply_beat_snapshot, build_beat_visual_runtime
from .vinyl_bpm_sync import document_needs_beat_runtime
from .paths import ffmpeg_path, temp_dir
from .render_service_v2 import FFmpegProcessRunner, RenderErrorV2
from .spectrum_render_step08 import Step08FFmpegCompiler


class AccuratePreviewService:
    def __init__(self, ffmpeg: str | None = None, runner: FFmpegProcessRunner | None = None) -> None:
        self.ffmpeg = ffmpeg or ffmpeg_path()
        if not self.ffmpeg:
            raise RenderErrorV2("FFmpeg tidak ditemukan.")
        self.runner = runner or FFmpegProcessRunner()
        self._beat_runtime_key = None
        self._beat_runtime = None
        self.runtime_memo_hits = 0
        self.runtime_memo_misses = 0

    @staticmethod
    def _runtime_key(document: ProjectDocument):
        assets = document.asset_map()
        sources = []
        seen = set()
        for song in document.playlist.entries:
            if not song.enabled or song.asset_id in seen:
                continue
            seen.add(song.asset_id)
            asset = assets.get(song.asset_id)
            if asset is None or asset.kind != "audio":
                continue
            path = Path(asset.locator)
            try:
                stat = path.stat()
                sources.append((asset.asset_id, str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns)))
            except OSError:
                sources.append((asset.asset_id, str(path), -1, -1))
        return document.content_signature(), tuple(sources)

    def clear_beat_runtime_cache(self) -> None:
        self._beat_runtime_key = None
        self._beat_runtime = None

    def _runtime_for(self, document: ProjectDocument):
        if not document_needs_beat_runtime(document):
            self.clear_beat_runtime_cache()
            return None
        key = self._runtime_key(document)
        if key == self._beat_runtime_key and self._beat_runtime is not None:
            self.runtime_memo_hits += 1
            return self._beat_runtime
        self.runtime_memo_misses += 1
        runtime = build_beat_visual_runtime(
            document,
            ffmpeg_executable=self.ffmpeg,
            ensure_analysis=True,
        )
        self._beat_runtime_key = key
        self._beat_runtime = runtime
        return runtime

    def render_frame(self, document: ProjectDocument, time_tick: int, destination: str | Path) -> str:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot = document.clone()
        runtime = self._runtime_for(document)
        if runtime is not None:
            snapshot = apply_beat_snapshot(snapshot, runtime, time_tick)
        with tempfile.TemporaryDirectory(prefix="fam_preview_", dir=temp_dir()) as folder:
            compiled = Step08FFmpegCompiler(self.ffmpeg).compile_frame(
                snapshot,
                time_tick,
                target,
                folder,
            )
            self.runner.run(compiled.args)
        if not target.exists() or target.stat().st_size == 0:
            raise RenderErrorV2("Preview frame tidak berhasil dibuat.")
        return str(target)
