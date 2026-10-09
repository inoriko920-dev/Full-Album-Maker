from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import time

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.render_center_model_step10 import (
    RenderJob,
    RenderJobState,
    RenderSettings,
    build_render_snapshot,
    settings_from_preset,
)
from full_album_maker.render_executor_step10 import (
    OutputVerification,
    RenderExecutor,
    Step10ProcessRunner,
    Step10RenderCancelled,
    Step10RenderError,
    apply_encoder_settings,
    apply_settings_to_snapshot,
    sanitize_render_log,
    verify_output,
)
from full_album_maker.render_preflight_step10 import FFmpegCapability


def _document(tmp_path: Path) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Executor")
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio-fixture")
    audio = MediaAsset(
        kind="audio",
        locator=str(source),
        original_name=source.name,
        source_duration_tick=6 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Before Enqueue",
            source_out_tick=6 * TIMEBASE,
        )
    )
    doc.validate()
    return doc


def _capability() -> FFmpegCapability:
    return FFmpegCapability(
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        version="ffmpeg fixture",
        encoders=frozenset({"libx264", "libx265"}),
        source="bundled",
    )


def _job(tmp_path: Path) -> RenderJob:
    doc = _document(tmp_path)
    settings = settings_from_preset(
        "youtube_1080p",
        filename="verified-final",
        output_folder=str(tmp_path),
    )
    return RenderJob(build_render_snapshot(doc), settings)


class FakeRunner:
    def __init__(self, *, cancel: bool = False) -> None:
        self.args: tuple[str, ...] | None = None
        self.cancel = cancel

    def run(self, args, *, duration_seconds, cancel_event=None, on_metrics=None, on_log=None):
        self.args = tuple(args)
        output = Path(args[-1])
        output.write_bytes(b"staged-mp4")
        if on_log:
            on_log("api_key=super-secret should-redact")
        if self.cancel:
            raise Step10RenderCancelled("cancel fixture")
        from full_album_maker.render_center_model_step10 import RenderMetrics
        value = RenderMetrics(percent=100.0, rendered_seconds=duration_seconds, fps=30.0, average_fps=30.0, speed=1.0, eta_seconds=0.0)
        if on_metrics:
            on_metrics(value)
        return value


def _verified(staged, *, settings, expected_duration_seconds, ffprobe):
    path = Path(staged)
    assert path.is_file()
    return OutputVerification(
        path=str(path),
        size_bytes=path.stat().st_size,
        duration_seconds=expected_duration_seconds,
        video_codec="h264",
        audio_codec="aac",
        width=settings.width,
        height=settings.height,
        fps=float(settings.fps),
        has_video=True,
        has_audio=True,
        verified=True,
        message="fixture verified",
    )


def test_snapshot_settings_apply_only_to_frozen_clone(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    settings = RenderSettings(
        filename="clone",
        output_folder=str(tmp_path),
        width=2560,
        height=1440,
        fps=24,
        video_codec="h264",
        video_bitrate_bps=24_000_000,
        audio_codec="aac",
        audio_bitrate_bps=320_000,
        sample_rate=48_000,
        hardware_mode="software",
        container="mp4",
        overwrite=False,
        preset_id="custom",
    )
    job = RenderJob(build_render_snapshot(doc), settings)
    doc.playlist.entries[0].display_title = "Live Edit After Queue"
    doc.revision += 1
    render_doc = apply_settings_to_snapshot(job, "libx264")
    assert render_doc.playlist.entries[0].display_title == "Before Enqueue"
    assert (render_doc.canvas.width, render_doc.canvas.height) == (2560, 1440)
    assert (render_doc.canvas.fps_num, render_doc.canvas.fps_den) == (24, 1)
    assert render_doc.render_settings["resolved_encoder"] == "libx264"
    # The frozen snapshot remains unchanged; RenderSettings are applied only to
    # the per-attempt document reconstructed for the compiler.
    frozen = job.snapshot.document()
    assert (frozen.canvas.width, frozen.canvas.height) == (1920, 1080)
    assert (frozen.canvas.fps_num, frozen.canvas.fps_den) == (30, 1)
    assert doc.playlist.entries[0].display_title == "Live Edit After Queue"


def test_encoder_args_include_resolved_encoder_bitrates_and_sample_rate(tmp_path: Path) -> None:
    job = _job(tmp_path)
    args = (
        "ffmpeg", "-i", "x", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-t", "6", str(tmp_path / "x.mp4"),
    )
    updated = apply_encoder_settings(args, job.settings, "h264_nvenc")
    assert updated[updated.index("-c:v") + 1] == "h264_nvenc"
    assert updated[updated.index("-b:v") + 1] == "16M"
    assert updated[updated.index("-b:a") + 1] == "320k"
    assert updated[updated.index("-ar") + 1] == "48000"


def test_verified_executor_publishes_only_after_verifier(tmp_path: Path) -> None:
    job = _job(tmp_path)
    runner = FakeRunner()
    executor = RenderExecutor(_capability(), runner=runner, verifier=_verified)
    result = executor.execute(job)
    final = job.settings.final_output
    assert job.state == RenderJobState.COMPLETED
    assert final.read_bytes() == b"staged-mp4"
    assert result.final_output == str(final)
    assert result.verification.verified is True
    assert job.verified_output == str(final)
    assert any("[REDACTED]" in line for line in job.log_lines)
    assert runner.args is not None
    assert "-progress" in runner.args


def test_output_created_during_render_does_not_get_overwritten_without_permission(
    tmp_path: Path,
) -> None:
    job = _job(tmp_path)

    class RaceRunner(FakeRunner):
        def run(self, args, *, duration_seconds, cancel_event=None, on_metrics=None, on_log=None):
            value = super().run(
                args, duration_seconds=duration_seconds, cancel_event=cancel_event,
                on_metrics=on_metrics, on_log=on_log,
            )
            # Another program creates a real final while FFmpeg is working.
            job.settings.final_output.write_bytes(b"other-program-important-video")
            return value

    executor = RenderExecutor(_capability(), runner=RaceRunner(), verifier=_verified)
    with pytest.raises(Step10RenderError, match="overwrite tidak diizinkan"):
        executor.execute(job)

    assert job.state == RenderJobState.FAILED
    assert job.settings.final_output.read_bytes() == b"other-program-important-video"
    assert not list(tmp_path.glob(".*.rendering.mp4"))


def test_output_created_during_render_can_be_overwritten_if_explicitly_enabled(
    tmp_path: Path,
) -> None:
    original = _job(tmp_path)
    original.settings = RenderSettings(
        **{**original.settings.__dict__, "overwrite": True}
    )
    job = original

    class RaceRunner(FakeRunner):
        def run(self, args, *, duration_seconds, cancel_event=None, on_metrics=None, on_log=None):
            value = super().run(
                args, duration_seconds=duration_seconds, cancel_event=cancel_event,
                on_metrics=on_metrics, on_log=on_log,
            )
            job.settings.final_output.write_bytes(b"old-output-created-during-render")
            return value

    result = RenderExecutor(
        _capability(), runner=RaceRunner(), verifier=_verified
    ).execute(job)

    assert job.state == RenderJobState.COMPLETED
    assert result.verification.verified
    assert job.settings.final_output.read_bytes() == b"staged-mp4"


def test_verifier_failure_never_publishes_partial_final_and_cleans_stage(tmp_path: Path) -> None:
    job = _job(tmp_path)
    runner = FakeRunner()

    def reject(*args, **kwargs):
        raise Step10RenderError("corrupt fixture")

    executor = RenderExecutor(_capability(), runner=runner, verifier=reject)
    with pytest.raises(Step10RenderError, match="corrupt"):
        executor.execute(job)
    assert job.state == RenderJobState.FAILED
    assert not job.settings.final_output.exists()
    assert not list(tmp_path.glob("*.rendering.mp4"))
    assert not list(tmp_path.glob(".*.rendering.mp4"))


def test_cancel_never_publishes_final_and_sets_cancelled(tmp_path: Path) -> None:
    job = _job(tmp_path)
    executor = RenderExecutor(_capability(), runner=FakeRunner(cancel=True), verifier=_verified)
    with pytest.raises(Step10RenderCancelled):
        executor.execute(job, cancel_event=threading.Event())
    assert job.state == RenderJobState.CANCELLED
    assert not job.settings.final_output.exists()
    assert not list(tmp_path.glob(".*.rendering.mp4"))


def test_double_start_is_rejected_before_touching_output(tmp_path: Path) -> None:
    job = _job(tmp_path)
    executor = RenderExecutor(_capability(), runner=FakeRunner(), verifier=_verified)
    executor._active_attempt = "another-attempt"
    with pytest.raises(Step10RenderError, match="double-start"):
        executor.execute(job)
    assert job.state == RenderJobState.DRAFT
    assert not job.settings.final_output.exists()


def test_unexpected_preflight_error_does_not_leave_active_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _job(tmp_path)

    def preflight_crash(*_args, **_kwargs):
        raise OSError("source disappeared during preflight")

    monkeypatch.setattr(
        "full_album_maker.render_executor_step10.run_preflight", preflight_crash
    )
    executor = RenderExecutor(_capability(), runner=FakeRunner(), verifier=_verified)
    with pytest.raises(OSError, match="source disappeared"):
        executor.execute(job)
    assert job.state == RenderJobState.BLOCKED
    assert job.error_code == "PREFLIGHT_ERROR"
    assert "source disappeared" in job.error_message
    assert not job.settings.final_output.exists()
    assert not list(tmp_path.glob(".*.rendering.mp4"))


def test_ready_job_reenters_critical_preflight_before_start(tmp_path: Path) -> None:
    job = _job(tmp_path)
    job.transition(RenderJobState.PREFLIGHTING)
    job.transition(RenderJobState.READY)
    # Invalidate a required media source after initial READY.
    media_path = Path(job.snapshot.document().media[0].locator)
    media_path.unlink()
    executor = RenderExecutor(_capability(), runner=FakeRunner(), verifier=_verified)
    with pytest.raises(Step10RenderError, match="Critical preflight"):
        executor.execute(job)
    # Executor must not retain a misleading READY state after critical failure.
    assert job.state == RenderJobState.BLOCKED
    assert not job.settings.final_output.exists()


def test_log_sanitization_redacts_secretish_values() -> None:
    safe = sanitize_render_log("Authorization: Bearer abc123 token=xyz password=hunter2")
    assert "abc123" not in safe
    assert "xyz" not in safe
    assert "hunter2" not in safe
    assert "[REDACTED]" in safe


def test_ffprobe_verifier_rejects_corrupt_and_accepts_expected_streams(tmp_path: Path) -> None:
    path = tmp_path / "stage.mp4"
    path.write_bytes(b"fake-container")
    settings = settings_from_preset("youtube_1080p", filename="probe", output_folder=str(tmp_path))

    def good_run(args, **kwargs):
        payload = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "duration": "6.0"},
                {"codec_type": "audio", "codec_name": "aac", "duration": "6.0", "sample_rate": "48000"},
            ],
            "format": {"duration": "6.0", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        }
        import json
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    verified = verify_output(path, settings=settings, expected_duration_seconds=6.0, ffprobe="ffprobe", run=good_run)
    assert verified.verified is True
    assert verified.width == 1920 and verified.height == 1080

    def bad_run(args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="Invalid data found")

    with pytest.raises(Step10RenderError, match="menolak"):
        verify_output(path, settings=settings, expected_duration_seconds=6.0, ffprobe="ffprobe", run=bad_run)


def test_silent_ffmpeg_process_can_be_cancelled_without_stdout() -> None:
    # A subprocess that never emits a progress line must still be cancellable.
    cancel = threading.Event()
    trigger = threading.Timer(0.2, cancel.set)
    trigger.start()
    start = time.monotonic()
    try:
        with pytest.raises(Step10RenderCancelled, match="dibatalkan"):
            Step10ProcessRunner().run(
                (sys.executable, "-u", "-c", "import time; time.sleep(4)"),
                duration_seconds=4.0,
                cancel_event=cancel,
            )
    finally:
        trigger.cancel()
        trigger.join(timeout=1)
    assert time.monotonic() - start < 3.0


def test_cancel_after_child_closes_stdout_before_exit() -> None:
    # The child closes its progress pipe but remains running. The parent must
    # continue polling the cancellation token instead of blocking in wait().
    cancel = threading.Event()
    trigger = threading.Timer(0.2, cancel.set)
    trigger.start()
    started = time.monotonic()
    try:
        with pytest.raises(Step10RenderCancelled, match="dibatalkan"):
            Step10ProcessRunner().run(
                (
                    sys.executable, "-u", "-c",
                    "import sys, time; sys.stdout.close(); time.sleep(4)",
                ),
                duration_seconds=4.0,
                cancel_event=cancel,
            )
    finally:
        trigger.cancel()
        trigger.join(timeout=1)
    assert time.monotonic() - started < 3.0


def test_cancelled_before_launch_never_starts_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    cancel = threading.Event()
    cancel.set()

    def never_start(*_args, **_kwargs):
        raise AssertionError("Should not launch FFmpeg for a cancelled job")

    monkeypatch.setattr("full_album_maker.render_executor_step10.subprocess.Popen", never_start)
    with pytest.raises(Step10RenderCancelled, match="sebelum FFmpeg"):
        Step10ProcessRunner().run(("ffmpeg", "-version"), duration_seconds=2, cancel_event=cancel)


def test_progress_lines_remain_parsed_with_background_stdout() -> None:
    script = (
        "print('out_time_us=500000'); print('fps=30'); "
        "print('speed=1x'); print('progress=continue'); "
        "print('out_time_us=1000000'); print('fps=30'); "
        "print('speed=1x'); print('progress=end')"
    )
    updates = []
    latest = Step10ProcessRunner().run(
        (sys.executable, "-u", "-c", script),
        duration_seconds=1.0,
        on_metrics=updates.append,
    )
    assert len(updates) == 2
    assert updates[0].percent == pytest.approx(50)
    assert latest.percent == pytest.approx(100)
