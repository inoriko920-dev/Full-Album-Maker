from __future__ import annotations

from pathlib import Path
import wave

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.paths import ffmpeg_path, ffprobe_path
from full_album_maker.render_center_model_step10 import RenderJob, RenderSettings, build_render_snapshot
from full_album_maker.render_executor_step10 import RenderExecutor
from full_album_maker.render_preflight_step10 import probe_ffmpeg


def _write_silence_wav(path: Path, seconds: int = 2, sample_rate: int = 48_000) -> None:
    frames = b"\x00\x00" * sample_rate * seconds
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)


def test_real_ffmpeg_renders_then_ffprobe_verifies_before_final_publish(tmp_path: Path) -> None:
    if not ffmpeg_path() or not ffprobe_path():
        pytest.skip("Real FFmpeg/ffprobe smoke hanya dijalankan pada targeted runtime job.")

    source = tmp_path / "source.wav"
    _write_silence_wav(source)
    stat = source.stat()

    doc = ProjectDocument.new_empty("STEP10 Real FFmpeg")
    audio = MediaAsset(
        kind="audio",
        locator=str(source),
        original_name=source.name,
        fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        source_duration_tick=2 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Tiny Real Render",
            source_out_tick=2 * TIMEBASE,
        )
    )
    doc.validate()

    settings = RenderSettings(
        filename="tiny-real",
        output_folder=str(tmp_path),
        width=320,
        height=240,
        fps=24,
        video_codec="h264",
        video_bitrate_bps=500_000,
        audio_codec="aac",
        audio_bitrate_bps=128_000,
        sample_rate=48_000,
        hardware_mode="software",
        container="mp4",
        overwrite=False,
        preset_id="custom",
    )
    capability = probe_ffmpeg()
    assert capability.has_encoder("libx264")

    job = RenderJob(build_render_snapshot(doc), settings)
    result = RenderExecutor(capability).execute(job)

    final = settings.final_output
    assert final.is_file() and final.stat().st_size > 0
    assert result.verification.verified is True
    assert result.verification.video_codec == "h264"
    assert result.verification.audio_codec == "aac"
    assert result.verification.width == 320
    assert result.verification.height == 240
    assert abs(result.verification.fps - 24.0) < 0.6
    assert job.verified_output == str(final)