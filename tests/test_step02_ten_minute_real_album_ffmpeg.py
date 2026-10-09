from __future__ import annotations

from array import array
import math
from pathlib import Path
import subprocess
import threading
import wave

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.paths import ffmpeg_path, ffprobe_path
from full_album_maker.project_repository import load_project_document, save_project_document
from full_album_maker.render_center_model_step10 import (
    RenderJob, RenderJobState, RenderSettings, build_render_snapshot,
)
from full_album_maker.render_executor_step10 import (
    RenderExecutor, Step10RenderCancelled,
)
from full_album_maker.render_preflight_step10 import probe_ffmpeg


TRACK_COUNT = 100
SONG_SECONDS = 6
DURATION_SECONDS = TRACK_COUNT * SONG_SECONDS  # 10 minutes
RATE = 48_000
TONES = (220, 330, 440, 550, 660, 770, 880)


def _write_wav(path: Path, frequency: int) -> None:
    # PCM files intentionally differ; they are not placeholders or fake media.
    frame_count = RATE * SONG_SECONDS
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        # Stream bounded chunks to avoid allocating all 100 songs in RAM.
        chunk_size = RATE // 2
        for offset in range(0, frame_count, chunk_size):
            count = min(chunk_size, frame_count - offset)
            frames = array("h", (
                int(11_000 * math.sin(
                    2 * math.pi * frequency * (offset + index) / RATE
                )) for index in range(count)
            ))
            out.writeframesraw(frames.tobytes())


def _document(tmp_path: Path) -> ProjectDocument:
    document = ProjectDocument.new_empty("STEP02 actual ten-minute 100-song album")
    for index in range(TRACK_COUNT):
        path = tmp_path / f"music-{index + 1:03d}.wav"
        _write_wav(path, TONES[index % len(TONES)])
        stat = path.stat()
        asset = MediaAsset(
            kind="audio", locator=str(path), original_name=path.name,
            source_duration_tick=SONG_SECONDS * TIMEBASE,
            fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
        )
        document.media.append(asset)
        document.playlist.entries.append(SongInstance(
            asset_id=asset.asset_id,
            display_title=f"STEP02 Song {index + 1:03d}",
            source_out_tick=SONG_SECONDS * TIMEBASE,
        ))
    document.validate()
    return document


def _tone_at(ffmpeg: str, mp4: Path, time_seconds: float) -> float:
    # Seek to a small region of the *actual exported MP4* without holding the
    # whole 10-minute AAC stream in memory. Use enough samples for frequency.
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-ss", f"{time_seconds - 0.15:.3f}", "-i", str(mp4),
            "-vn", "-t", "0.300", "-ac", "1", "-ar", str(RATE),
            "-f", "s16le", "-",
        ],
        capture_output=True, check=True, timeout=60,
    )
    samples = array("h")
    samples.frombytes(result.stdout)
    assert len(samples) >= 12000, f"Audio clip missing around {time_seconds}s"
    assert max(abs(v) for v in samples) > 300, f"Silent clip at {time_seconds}s"
    # Inspect only the central 0.20 s to avoid AAC seek edges.
    start = (len(samples) - 9600) // 2
    clip = samples[start:start + 9600]
    crossings = sum(
        1 for left, right in zip(clip, clip[1:])
        if left < 0 <= right
    )
    return crossings / 0.2


def test_real_ten_minute_album_and_cancelled_retry_never_publish_partial_mp4(
    tmp_path: Path,
) -> None:
    """Actual 100-song, ten-minute H264/AAC MP4 render on Windows.

    Duration and a selection of audible track IDs are independently verified.
    This does not claim full two-hour testing or MP3 import, which need separate
    gates. A second render deliberately cancels after progress on the same
    large source set and must leave no final/partial public output.
    """
    if not ffmpeg_path() or not ffprobe_path():
        pytest.skip("Requires real FFmpeg and FFprobe in Windows CI")

    document = _document(tmp_path)
    project_path = tmp_path / "ten-minute-100-songs.json"
    save_project_document(str(project_path), document)
    reopened = load_project_document(str(project_path))
    assert len(reopened.media) == TRACK_COUNT
    assert len(reopened.playlist.entries) == TRACK_COUNT
    assert reopened.content_signature() == document.content_signature()

    settings = RenderSettings(
        filename="STEP02-ten-minute-final",
        output_folder=str(tmp_path),
        width=320, height=240, fps=24,
        video_codec="h264", video_bitrate_bps=300_000,
        audio_codec="aac", audio_bitrate_bps=128_000, sample_rate=RATE,
        hardware_mode="software", container="mp4", overwrite=False,
        preset_id="custom",
    )
    capability = probe_ffmpeg()
    snapshot = build_render_snapshot(reopened)
    assert abs(snapshot.duration_tick / TIMEBASE - DURATION_SECONDS) < 0.001

    job = RenderJob(snapshot, settings)
    result = RenderExecutor(capability).execute(job)
    output = settings.final_output
    assert job.state == RenderJobState.COMPLETED
    assert result.verification.verified
    assert result.verification.video_codec == "h264"
    assert result.verification.audio_codec == "aac"
    assert result.verification.has_audio and result.verification.has_video
    assert abs(result.verification.duration_seconds - DURATION_SECONDS) < 0.5
    assert output.is_file() and output.stat().st_size > 50_000

    # Verify physical *audio* at widely separated song positions, including
    # last track, rather than trusting only successful process exit.
    for index in (0, 1, 24, 49, 50, 74, 98, 99):
        freq = _tone_at(capability.ffmpeg, output, SONG_SECONDS * (index + 0.5))
        expected = TONES[index % len(TONES)]
        assert abs(freq - expected) < 25, (
            f"Song {index + 1} expected {expected}Hz, exported {freq:.1f}Hz"
        )

    # Perform cancellation with a *real* second 10-minute export. No fake
    # runner is used. The verified first MP4 must not be modified.
    original_size = output.stat().st_size
    cancel_settings = RenderSettings(
        **{**settings.__dict__, "filename": "STEP02-cancelled-long-album"},
    )
    cancelled = RenderJob(snapshot, cancel_settings)
    stop = threading.Event()
    observed: list[float] = []

    def cancel_after_progress(metrics) -> None:
        observed.append(metrics.rendered_seconds)
        if metrics.rendered_seconds > 0.05:
            stop.set()

    with pytest.raises(Step10RenderCancelled):
        RenderExecutor(capability).execute(
            cancelled, cancel_event=stop, on_metrics=cancel_after_progress
        )
    assert observed and any(value > 0.05 for value in observed)
    assert cancelled.state == RenderJobState.CANCELLED
    assert not cancel_settings.final_output.exists()
    assert not list(tmp_path.glob(".*.rendering.mp4"))
    assert output.stat().st_size == original_size
