from __future__ import annotations

from array import array
import math
from pathlib import Path
import subprocess
import wave

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.paths import ffmpeg_path, ffprobe_path
from full_album_maker.render_center_model_step10 import (
    RenderJob,
    RenderSettings,
    RenderJobState,
    build_render_snapshot,
)
from full_album_maker.render_executor_step10 import RenderExecutor
from full_album_maker.render_preflight_step10 import probe_ffmpeg
from full_album_maker.s11_render_graph import WINDOWS_COMMAND_SAFE_LIMIT, windows_command_line_length
from full_album_maker.spectrum_render_step08 import Step08FFmpegCompiler


TRACK_COUNT = 100
SONG_SECONDS = 0.30
SAMPLE_RATE = 48_000
TONES_HZ = (220, 330, 440, 550, 660, 770, 880)


def _source_tone(path: Path, frequency_hz: int) -> None:
    total_frames = round(SONG_SECONDS * SAMPLE_RATE)
    frames = array("h", (
        int(12_000 * math.sin(2 * math.pi * frequency_hz * i / SAMPLE_RATE))
        for i in range(total_frames)
    ))
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(frames.tobytes())


def _album_with_100_different_real_audio_files(tmp_path: Path) -> ProjectDocument:
    document = ProjectDocument.new_empty("STEP01 100-track Windows MP4 acceptance")
    for index in range(TRACK_COUNT):
        source = tmp_path / f"song-{index:03d}.wav"
        _source_tone(source, TONES_HZ[index % len(TONES_HZ)])
        stat = source.stat()
        media = MediaAsset(
            kind="audio", locator=str(source), original_name=source.name,
            source_duration_tick=round(SONG_SECONDS * TIMEBASE),
            fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        )
        document.media.append(media)
        document.playlist.entries.append(SongInstance(
            asset_id=media.asset_id,
            display_title=f"Song {index + 1:03d}",
            source_out_tick=round(SONG_SECONDS * TIMEBASE),
        ))
    document.validate()
    return document


def _decode_audio(path: Path, ffmpeg: str) -> array:
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        capture_output=True, timeout=120, check=True,
    )
    samples = array("h")
    samples.frombytes(completed.stdout)
    return samples


def _frequency_near(samples: array, center_second: float) -> float:
    half_window = 0.06
    start = round((center_second - half_window) * SAMPLE_RATE)
    end = round((center_second + half_window) * SAMPLE_RATE)
    window = samples[start:end]
    assert len(window) == round(2 * half_window * SAMPLE_RATE)
    assert max(map(abs, window)) > 300, "Exported song is silent"
    rising = sum(
        1 for left, right in zip(window, window[1:])
        if left < 0 <= right
    )
    return rising / (2 * half_window)


def test_100_real_songs_render_to_single_verified_h264_aac_mp4(tmp_path: Path) -> None:
    """STEP 01: 100 distinct WAV files, one actual completed MP4, audible order.

    This is a 30-second accelerated 100-song acceptance fixture. It validates
    the number of assets and song transitions, but it does NOT claim an actual
    two-hour export or genuine MP3 input performance.
    """
    if not ffmpeg_path() or not ffprobe_path():
        pytest.skip("Requires real FFmpeg/ffprobe installed in Windows CI")

    document = _album_with_100_different_real_audio_files(tmp_path)
    assert len(document.playlist.entries) == len(document.media) == TRACK_COUNT
    expected_seconds = TRACK_COUNT * SONG_SECONDS
    settings = RenderSettings(
        filename="STEP01_100_songs_real_export",
        output_folder=str(tmp_path),
        width=320, height=240, fps=24,
        video_codec="h264", video_bitrate_bps=300_000,
        audio_codec="aac", audio_bitrate_bps=128_000, sample_rate=SAMPLE_RATE,
        hardware_mode="software", container="mp4",
        overwrite=False, preset_id="custom",
    )
    capability = probe_ffmpeg()
    snapshot = build_render_snapshot(document)
    assert abs(snapshot.duration_tick / TIMEBASE - expected_seconds) < 0.01

    # With 100 independent inputs, Windows CreateProcess has a strict command
    # length limit. Compilation must externalize large filter graphs if needed.
    compile_dir = tmp_path / "compile"
    compiled = Step08FFmpegCompiler(capability.ffmpeg).compile_video(
        document, tmp_path / "dry-compile.mp4", compile_dir
    )
    assert windows_command_line_length(compiled.args) < WINDOWS_COMMAND_SAFE_LIMIT
    assert (
        "-/filter_complex" in compiled.args or "-filter_complex" in compiled.args
    )

    job = RenderJob(snapshot, settings)
    result = RenderExecutor(capability).execute(job)
    assert result.verification.verified
    assert job.state == RenderJobState.COMPLETED
    assert result.verification.video_codec == "h264"
    assert result.verification.audio_codec == "aac"
    assert result.verification.has_video and result.verification.has_audio
    assert (result.verification.width, result.verification.height) == (320, 240)
    assert abs(result.verification.duration_seconds - expected_seconds) < 0.35
    assert settings.final_output.is_file()
    assert settings.final_output.stat().st_size > 0

    decoded = _decode_audio(settings.final_output, capability.ffmpeg)
    assert len(decoded) >= (expected_seconds - 0.1) * SAMPLE_RATE
    # Check beginning, transitions, midpoint, and end for missing/reordered
    # songs. Distinct repeating tones make these checks audible, not metadata.
    for song_index in (0, 1, 24, 49, 50, 75, 98, 99):
        at = SONG_SECONDS * (song_index + 0.5)
        measured = _frequency_near(decoded, at)
        expected_hz = TONES_HZ[song_index % len(TONES_HZ)]
        assert abs(measured - expected_hz) < 35, (
            f"Track {song_index + 1}/100 at {at:.2f}s: "
            f"expected {expected_hz} Hz, heard {measured:.1f} Hz"
        )
