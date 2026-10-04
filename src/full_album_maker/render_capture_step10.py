from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import wave

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


def _write_wav(path: Path, *, seconds: int = 1, sample_rate: int = 48_000) -> None:
    frames = b"\x00\x00" * sample_rate * seconds
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)


def _fixture_document(root: Path):
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("Render Center Golden Project")
    document.album_title = "Senja di Kota Ini — Full Album"
    document.canvas.width = 1920
    document.canvas.height = 1080
    document.canvas.fps_num = 30
    document.canvas.fps_den = 1
    titles = ("Senja di Kota Ini", "Jalan Pulang", "Perjalanan Kita")
    for index, title in enumerate(titles, start=1):
        source = root / f"song-{index:02d}.wav"
        _write_wav(source)
        stat = source.stat()
        asset = MediaAsset(
            kind="audio",
            locator=str(source),
            original_name=source.name,
            fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
            source_duration_tick=120 * TIMEBASE,
        )
        document.media.append(asset)
        document.playlist.entries.append(
            SongInstance(
                asset_id=asset.asset_id,
                display_title=title,
                display_artist="Perjalanan Kita",
                source_out_tick=120 * TIMEBASE,
            )
        )
    document.validate()
    return document


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settings(root: Path, filename: str):
    from .render_center_model_step10 import settings_from_preset

    output = root / "D" / "Video" / "Full Album"
    output.mkdir(parents=True, exist_ok=True)
    base = settings_from_preset(
        "youtube_1080p",
        filename=filename,
        output_folder=str(output),
    )
    return replace(
        base,
        fps=30,
        video_codec="h264",
        video_bitrate_bps=16_000_000,
        audio_codec="aac",
        audio_bitrate_bps=320_000,
        sample_rate=48_000,
        hardware_mode="h264_nvenc",
        overwrite=False,
    )


def _mock_preflight(document, settings):
    from .render_center_model_step10 import build_render_snapshot
    from .render_preflight_step10 import (
        EncoderResolution,
        FFmpegCapability,
        PreflightCheck,
        PreflightLevel,
        PreflightReport,
    )

    snapshot = build_render_snapshot(document)
    capability = FFmpegCapability(
        ffmpeg="tools/ffmpeg/ffmpeg.exe",
        ffprobe="tools/ffmpeg/ffprobe.exe",
        version="ffmpeg golden-fixture",
        encoders=frozenset({"libx264", "h264_nvenc"}),
        runtime_verified_encoders=frozenset({"h264_nvenc"}),
        source="bundled",
    )
    checks = (
        PreflightCheck("media", "Media Lengkap", PreflightLevel.PASS, "Semua source aktif tersedia."),
        PreflightCheck("timeline", "Timeline Valid", PreflightLevel.PASS, "RenderPlan snapshot valid."),
        PreflightCheck("ffmpeg", "FFmpeg Siap", PreflightLevel.PASS, "Bundled FFmpeg fixture siap."),
        PreflightCheck("output", "Output Folder", PreflightLevel.PASS, "Folder output dapat digunakan."),
        PreflightCheck("disk", "Disk Space", PreflightLevel.WARN, "Free 18.4 GB < recommended 20.0 GB."),
    )
    return PreflightReport(
        snapshot=snapshot,
        settings_signature=settings.signature(),
        checks=checks,
        capability=capability,
        encoder=EncoderResolution(
            "h264_nvenc",
            True,
            False,
            "Mock verified NVIDIA NVENC untuk golden screenshot.",
        ),
        estimated_output_bytes=750_000_000,
        required_free_bytes=2_000_000_000,
        recommended_free_bytes=20 * 1024**3,
    ), capability


def _mock_jobs(document, root: Path):
    from .render_center_model_step10 import (
        RenderJob,
        RenderJobState,
        RenderMetrics,
        build_render_snapshot,
    )

    snapshot = build_render_snapshot(document)
    running = RenderJob(
        snapshot=snapshot,
        settings=_settings(root, "Senja di Kota Ini - Full Album"),
        state=RenderJobState.RUNNING,
        metrics=RenderMetrics(
            percent=63.0,
            rendered_seconds=226.8,
            fps=112.0,
            average_fps=108.4,
            speed=3.72,
            eta_seconds=36.0,
        ),
        log_lines=(
            ["frame=6804 fps=112.0 speed=3.72x", "snapshot immutable • staged output aktif"]
        ),
    )
    queued = RenderJob(
        snapshot=snapshot,
        settings=_settings(root, "Jalan Pulang - Full Album"),
        state=RenderJobState.QUEUED,
        metrics=RenderMetrics(percent=0.0),
    )
    completed = RenderJob(
        snapshot=snapshot,
        settings=_settings(root, "Perjalanan Kita - Full Album"),
        state=RenderJobState.COMPLETED,
        metrics=RenderMetrics(
            percent=100.0,
            rendered_seconds=360.0,
            fps=109.0,
            average_fps=107.2,
            speed=3.60,
            eta_seconds=0.0,
        ),
    )
    completed_output = completed.settings.final_output
    completed_output.parent.mkdir(parents=True, exist_ok=True)
    completed_output.write_bytes(b"verified-golden-fixture")
    completed.verified_output = str(completed_output)
    return running, queued, completed


def _set_inspector_golden(inspector, settings) -> None:
    inspector._updating = True
    try:
        inspector.filename.setText(settings.filename)
        inspector.output_folder.setText(settings.output_folder)
        index = inspector.preset.findData("youtube_1080p")
        if index >= 0:
            inspector.preset.setCurrentIndex(index)
        inspector.width.setValue(1920)
        inspector.height.setValue(1080)
        inspector._set_combo(inspector.fps, "30")
        inspector._set_combo(inspector.video_codec, "h264")
        inspector.video_bitrate.setValue(16)
        inspector._set_combo(inspector.audio_bitrate, "320")
        inspector._set_combo(inspector.sample_rate, "48000")
        inspector._set_combo(inspector.hardware, "h264_nvenc")
        inspector.overwrite.setChecked(False)
    finally:
        inspector._updating = False


def capture(output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    os.environ["FAM_STEP09_PROVIDER"] = "mock"
    os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    _prepare_qt(scale)
    import full_album_maker.main  # noqa: F401 - installs production layers through STEP10

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .render_center_model_step10 import RenderJobState
    from .render_preflight_step10 import PreflightLevel

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    root = Path(tempfile.mkdtemp(prefix="fam-step10-render-"))
    document = _fixture_document(root)
    signature_before = document.content_signature()

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window.foundation_shell.set_workspace("render")

    golden_settings = _settings(root, "Senja di Kota Ini - Full Album")
    _set_inspector_golden(window.render_inspector_s10, golden_settings)
    report, capability = _mock_preflight(document, golden_settings)
    window._s10_preflight_report = report
    window._s10_preflight_capability = capability
    window._s10_preflight_settings_signature = golden_settings.signature()
    window.render_workspace_s10.apply_preflight(report)
    window.render_inspector_s10.set_preflight_ready(True, "Preflight siap • NVIDIA NVENC mock verified")

    running, queued, completed = _mock_jobs(document, root)
    window._s10_queue.jobs = [running, queued, completed]
    window._s10_selected_key = (running.job_id, running.attempt_id)
    window.render_workspace_s10.apply_queue(window._s10_queue.jobs)
    window.render_workspace_s10.apply_job(running)
    window.render_workspace_s10.log_list.clear()
    for line in running.log_lines:
        window.render_workspace_s10.append_log(line)
    window.render_performance_s10.clear()
    for percent, fps in ((8, 92), (21, 101), (37, 108), (51, 110), (63, 112)):
        from .render_center_model_step10 import RenderMetrics
        window.render_performance_s10.append_metrics(
            RenderMetrics(
                percent=float(percent),
                rendered_seconds=360.0 * percent / 100.0,
                fps=float(fps),
                average_fps=float(fps - 3),
                speed=3.72,
                eta_seconds=max(0.0, (100 - percent) * 0.97),
            )
        )
    window.foundation_state.set_status(
        ffmpeg=("FFmpeg Siap", "success"),
        jobs=("Jobs: 2", "warning"),
    )
    window._s10_update_action_state()
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(260, loop.quit)
    loop.exec()
    app.processEvents()

    live = window.editor_workspace.document()
    signature_after = live.content_signature()
    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot STEP10 Render Center: {output}")

    shell = window.foundation_shell
    visible_cards = {
        key: {
            "title": card.title.text(),
            "state": card.state.text(),
            "visible": not card.isHidden(),
        }
        for key, card in window.render_workspace_s10.preflight_cards.items()
    }
    pass_count = sum(
        1 for check in report.checks if check.level == PreflightLevel.PASS
    )
    warn_count = sum(
        1 for check in report.checks if check.level == PreflightLevel.WARN
    )
    queue_rows = [
        window.render_workspace_s10.queue_list.item(i).text()
        for i in range(window.render_workspace_s10.queue_list.count())
    ]
    settings = window.render_inspector_s10.settings()
    active_jobs = sum(
        1
        for job in window._s10_queue.jobs
        if job.state in {
            RenderJobState.PREFLIGHTING,
            RenderJobState.STARTING,
            RenderJobState.RUNNING,
            RenderJobState.PAUSED,
            RenderJobState.FINALIZING,
            RenderJobState.QUEUED,
        }
    )
    geometry = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "render_active": shell.workspace_stack.currentWidget() is window.render_workspace_s10,
        "inspector_active": window._inspector_router.currentWidget() is window.render_inspector_s10,
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "timeline_collapsed": bool(shell.timeline.collapsed),
        "project_signature_unchanged_by_route_and_fixture": signature_before == signature_after,
        "preflight_pass_count": pass_count,
        "preflight_warn_count": warn_count,
        "preflight_cards": visible_cards,
        "preset": settings.preset_id,
        "filename": settings.filename,
        "resolution": [settings.width, settings.height],
        "fps": settings.fps,
        "video_codec": settings.video_codec,
        "video_bitrate_bps": settings.video_bitrate_bps,
        "audio_codec": settings.audio_codec,
        "audio_bitrate_bps": settings.audio_bitrate_bps,
        "sample_rate": settings.sample_rate,
        "hardware_mode": settings.hardware_mode,
        "safe_output_folder": settings.output_folder,
        "running_name": Path(running.settings.final_output).name,
        "running_state": running.state.value,
        "running_percent": running.metrics.percent,
        "running_fps": running.metrics.fps,
        "queued_name": Path(queued.settings.final_output).name,
        "queued_state": queued.state.value,
        "completed_name": Path(completed.settings.final_output).name,
        "completed_state": completed.state.value,
        "completed_verified": bool(completed.verified_output),
        "queue_row_count": len(queue_rows),
        "queue_rows": queue_rows,
        "active_jobs_status_count": active_jobs,
        "performance_points": window.render_performance_s10.point_count,
        "pause_enabled": window.render_inspector_s10.pause.isEnabled(),
        "add_queue_text": window.render_add_queue_s10.text(),
        "copy_log_text": window.render_copy_log_s10.text(),
        "open_output_text": window.render_open_output_s10.text(),
        "screenshot_sha256": _sha(output),
        "scale": scale,
        "font_family": font_family,
    }

    if getattr(window, "_s10_async", None) is not None:
        window._s10_async.close()
    if getattr(window, "_s09_async", None) is not None:
        window._s09_async.close()
    window.hide()
    window.deleteLater()
    app.processEvents()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP10 Render Center evidence")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    ns = parser.parse_args(argv)

    output = Path(ns.output)
    geometry = capture(output, ns.width, ns.height, ns.scale)
    result = {"current": str(output), "geometry": geometry}
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())