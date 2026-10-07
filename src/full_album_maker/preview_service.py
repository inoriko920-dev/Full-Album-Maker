from __future__ import annotations

from pathlib import Path
import tempfile

from .editor_models import ProjectDocument
from .beat_visual_runtime import apply_beat_snapshot, build_beat_visual_runtime
from .paths import ffmpeg_path, temp_dir
from .render_service_v2 import FFmpegProcessRunner, RenderErrorV2
from .spectrum_render_step08 import Step08FFmpegCompiler


class AccuratePreviewService:
    def __init__(self, ffmpeg: str | None = None, runner: FFmpegProcessRunner | None = None) -> None:
        self.ffmpeg = ffmpeg or ffmpeg_path()
        if not self.ffmpeg:
            raise RenderErrorV2("FFmpeg tidak ditemukan.")
        self.runner = runner or FFmpegProcessRunner()

    def render_frame(self, document: ProjectDocument, time_tick: int, destination: str | Path) -> str:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot = document.clone()
        runtime = build_beat_visual_runtime(
            snapshot,
            ffmpeg_executable=self.ffmpeg,
            ensure_analysis=True,
        )
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