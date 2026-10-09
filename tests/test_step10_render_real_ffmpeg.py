from __future__ import annotations

from array import array
import math
from pathlib import Path
import subprocess
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


def _write_tone_wav(
    path: Path, *, frequency_hz: int, seconds: float = 0.75, sample_rate: int = 48_000,
) -> None:
    frames = array("h", (
        int(11000 * math.sin(2 * math.pi * frequency_hz * index / sample_rate))
        for index in range(round(seconds * sample_rate))
    ))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames.tobytes())


def _decoded_mono_samples(mp4: Path, ffmpeg: str) -> array:
    proc = subprocess.run(
        [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-i", str(mp4),
            "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-",
        ],
        capture_output=True,
        timeout=45,
        check=True,
    )
    samples = array("h")
    samples.frombytes(proc.stdout)
    return samples


def _tone_frequency(samples: array, at_second: float, *, sample_rate: int = 48_000) -> float:
    # Estimate actual audible frequency from signed zero crossings. Unlike
    # stream-only checks this catches reordered, duplicated or silent songs.
    start = int((at_second - 0.1) * sample_rate)
    end = int((at_second + 0.1) * sample_rate)
    clip = samples[start:end]
    assert len(clip) == round(sample_rate * 0.2)
    assert max(abs(value) for value in clip) > 400
    crossings = sum(
        1 for earlier, later in zip(clip, clip[1:])
        if earlier < 0 <= later
    )
    return crossings / 0.2


@pytest.mark.parametrize(
    ("mode", "starts", "checkpoints", "expected_length"),
    [
        ("packed", (0, 0, 0), (0.375, 1.125, 1.875), 2.25),
        ("free", (0.0, 1.0, 2.0), (0.375, 1.375, 2.375), 2.75),
    ],
)
def test_real_ffmpeg_multisong_album_preserves_audio_order_and_duration(
    tmp_path: Path, mode: str, starts: tuple[float, ...],
    checkpoints: tuple[float, ...], expected_length: float,
) -> None:
    if not ffmpeg_path() or not ffprobe_path():
        pytest.skip("Real FFmpeg/ffprobe tersedia hanya pada targeted runtime job.")

    doc = ProjectDocument.new_empty("Three-song E2E Album")
    doc.playlist.mode = mode
    for index, frequency in enumerate((220, 440, 880)):
        source = tmp_path / f"track-{index + 1}.wav"
        _write_tone_wav(source, frequency_hz=frequency)
        stat = source.stat()
        asset = MediaAsset(
            kind="audio", locator=str(source), original_name=source.name,
            fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
            source_duration_tick=round(0.75 * TIMEBASE),
        )
        doc.media.append(asset)
        song = SongInstance(
            asset_id=asset.asset_id,
            display_title=f"Track {index + 1}",
            source_out_tick=round(0.75 * TIMEBASE),
        )
        if mode == "free":
            song.free_start_tick = round(starts[index] * TIMEBASE)
        doc.playlist.entries.append(song)
    doc.validate()

    settings = RenderSettings(
        filename=f"album-three-songs-{mode}",
        output_folder=str(tmp_path),
        width=320, height=240, fps=24, video_codec="h264",
        video_bitrate_bps=450_000, audio_codec="aac",
        audio_bitrate_bps=128_000, sample_rate=48_000,
        hardware_mode="software", container="mp4",
        overwrite=False, preset_id="custom",
    )
    capability = probe_ffmpeg()
    job = RenderJob(build_render_snapshot(doc), settings)
    assert abs(job.snapshot.duration_tick / TIMEBASE - expected_length) < 0.001
    result = RenderExecutor(capability).execute(job)
    assert result.verification.verified
    assert result.verification.has_video and result.verification.has_audio
    assert abs(result.verification.duration_seconds - expected_length) < 0.25
    assert settings.final_output.exists()

    samples = _decoded_mono_samples(settings.final_output, capability.ffmpeg)
    assert len(samples) >= int((expected_length - 0.08) * 48_000)
    for at_second, expected_hz in zip(checkpoints, (220, 440, 880)):
        measured = _tone_frequency(samples, at_second)
        assert abs(measured - expected_hz) < 25, (
            f"{mode} at {at_second}s: expected {expected_hz}Hz, got {measured:.1f}Hz"
        )
    if mode == "free":
        # The quarter-second gap should be nearly silent, not the next track.
        gap = samples[int(0.83 * 48_000) : int(0.92 * 48_000)]
        assert gap and max(abs(value) for value in gap) < 400
