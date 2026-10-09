from __future__ import annotations

import os
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from full_album_maker.async_import import install_async_import, uninstall_async_import
from full_album_maker.controller import ProjectController
from full_album_maker.engine_hardening import install_engine_hardening, uninstall_engine_hardening
from full_album_maker.playlist_feature import install_feature, uninstall_feature
from full_album_maker.playlist_hardening import install_playlist_hardening, uninstall_playlist_hardening
from full_album_maker.project import Project
from full_album_maker.project_dirty import install_project_dirty_state, uninstall_project_dirty_state
from full_album_maker.render_lifecycle import install_render_lifecycle, uninstall_render_lifecycle
from full_album_maker.source_integrity import install_source_integrity, uninstall_source_integrity
from full_album_maker.ui import MainWindow
from full_album_maker.ui_hardening import install_ui_hardening, uninstall_ui_hardening
from full_album_maker.visual_feature import install_visual_feature, uninstall_visual_feature


@pytest.fixture(autouse=True)
def feature_stack():
    install_feature()
    install_playlist_hardening()
    install_visual_feature()
    install_engine_hardening()
    install_source_integrity()
    install_ui_hardening()
    install_render_lifecycle()
    install_project_dirty_state()
    install_async_import()
    try:
        yield
    finally:
        uninstall_async_import()
        uninstall_project_dirty_state()
        uninstall_render_lifecycle()
        uninstall_ui_hardening()
        uninstall_source_integrity()
        uninstall_engine_hardening()
        uninstall_visual_feature()
        uninstall_playlist_hardening()
        uninstall_feature()


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wait_jobs(window, timeout: float = 5.0) -> None:
    app = _app()
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if window._import_job_count == 0:
            return
        time.sleep(0.01)
    raise AssertionError("Import worker tidak selesai dalam batas waktu tes.")


def _close_without_dirty_prompt(window) -> None:
    window._saved_project_state = None
    window.close()
    _app().processEvents()


def test_video_probe_runs_off_ui_thread_and_commits_after_completion(tmp_path, monkeypatch):
    app = _app()
    source = tmp_path / "slow-video.mp4"
    source.write_bytes(b"video")
    entered = threading.Event()
    release = threading.Event()

    def slow_probe(path, kind=None):
        assert kind == "video"
        entered.set()
        assert release.wait(timeout=5)
        return 12.5

    monkeypatch.setattr("full_album_maker.async_import.probe_duration", slow_probe)
    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], "Video"),
    )

    window = MainWindow()
    window.add_video()

    assert entered.wait(timeout=2)
    assert window._import_job_count == 1
    assert window.project.videos == []

    # If probing were still on the UI thread, execution could not reach here
    # until release was set. Mutating/refeshing another control proves the call
    # returned while the worker remains blocked.
    window.project.settings.fps = 60
    window.refresh()
    app.processEvents()
    assert window.project.settings.fps == 60

    release.set()
    _wait_jobs(window)

    assert len(window.project.videos) == 1
    assert Path(window.project.videos[0].path).name == "slow-video.mp4"
    assert window.project.videos[0].duration == pytest.approx(12.5)
    assert window.timeline_plan is None
    assert "background" in window.log.toPlainText().casefold()
    _close_without_dirty_prompt(window)


def test_audio_import_probes_metadata_in_worker(tmp_path, monkeypatch):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"audio")

    monkeypatch.setattr(
        "full_album_maker.async_import.probe_duration",
        lambda path, kind=None: 7.25,
    )
    monkeypatch.setattr(
        "full_album_maker.async_import.visual_feature_module.probe_audio_tags",
        lambda path: ("Judul Metadata", "Artis Metadata"),
    )
    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], "Audio"),
    )

    window = MainWindow()
    window.add_audio()
    _wait_jobs(window)

    assert len(window.project.audios) == 1
    item = window.project.audios[0]
    assert item.duration == pytest.approx(7.25)
    assert getattr(item, "display_title") == "Judul Metadata"
    assert getattr(item, "display_artist") == "Artis Metadata"
    assert getattr(item, "metadata_probed") is True
    _close_without_dirty_prompt(window)


def test_image_import_keeps_dimensions_and_visual_order(tmp_path, monkeypatch):
    source = tmp_path / "cover.webp"
    source.write_bytes(b"image")

    monkeypatch.setattr(
        "full_album_maker.async_import.visual_feature_module.probe_image",
        lambda path: {"width": 1200, "height": 1600, "format": "webp"},
    )
    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], "Foto"),
    )

    window = MainWindow()
    window.add_image()
    _wait_jobs(window)

    assert len(getattr(window.project, "images")) == 1
    image = getattr(window.project, "images")[0]
    assert getattr(image, "width") == 1200
    assert getattr(image, "height") == 1600
    assert getattr(window.project, "_visual_order") == [str(source)]
    _close_without_dirty_prompt(window)


def test_pending_duplicate_is_not_started_twice(tmp_path, monkeypatch):
    source = tmp_path / "duplicate.mp4"
    source.write_bytes(b"video")
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def slow_probe(path, kind=None):
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(timeout=5)
        return 4.0

    monkeypatch.setattr("full_album_maker.async_import.probe_duration", slow_probe)
    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], "Video"),
    )

    window = MainWindow()
    window.add_video()
    assert entered.wait(timeout=2)
    window.add_video()

    assert window._import_job_count == 1
    release.set()
    _wait_jobs(window)

    assert calls == 1
    assert len(window.project.videos) == 1
    assert "pending dilewati" in window.log.toPlainText().casefold()
    _close_without_dirty_prompt(window)


def test_finished_import_is_discarded_if_project_changed(tmp_path, monkeypatch):
    source = tmp_path / "old-project-video.mp4"
    source.write_bytes(b"video")
    entered = threading.Event()
    release = threading.Event()

    def slow_probe(path, kind=None):
        entered.set()
        assert release.wait(timeout=5)
        return 9.0

    monkeypatch.setattr("full_album_maker.async_import.probe_duration", slow_probe)
    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], "Video"),
    )

    window = MainWindow()
    window.add_video()
    assert entered.wait(timeout=2)

    replacement = Project()
    window.project = replacement
    window.controller = ProjectController(replacement)
    release.set()
    _wait_jobs(window)

    assert replacement.videos == []
    assert "diabaikan karena proyek aktif sudah berganti" in window.log.toPlainText().casefold()
    _close_without_dirty_prompt(window)


def test_real_mp3_files_import_through_ui_and_export_to_verified_mp4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-release acceptance: actual MP3 bytes, actual Qt import and FFmpeg.

    Existing UI import tests use fake file bytes and mocked durations. This
    test exercises the real MP3 decoder + metadata path, then constructs the
    canonical album using the actual imported sources, uses the production
    playlist service, and renders a real AAC/H.264 MP4. It does not claim
    that every visual UI interaction or a two-hour album is covered.
    """
    import math
    import subprocess
    from array import array

    from full_album_maker.editor_models import (
        MediaAsset as AlbumMediaAsset, ProjectDocument, TIMEBASE,
    )
    from full_album_maker.paths import ffmpeg_path, ffprobe_path
    from full_album_maker.playlist_service_v2 import PlaylistServiceV2
    from full_album_maker.render_center_model_step10 import (
        RenderJob, RenderSettings, build_render_snapshot,
    )
    from full_album_maker.render_executor_step10 import RenderExecutor
    from full_album_maker.render_preflight_step10 import probe_ffmpeg

    ffmpeg = ffmpeg_path()
    if not ffmpeg or not ffprobe_path():
        pytest.skip("Requires real bundled FFmpeg/FFprobe")

    frequencies = (220, 330, 440, 550, 660, 770, 880, 990)
    sources = []
    for index, hz in enumerate(frequencies):
        target = tmp_path / f"Track-{index + 1:02d}.mp3"
        subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi",
                "-i", f"sine=frequency={hz}:sample_rate=48000:duration=0.8",
                "-c:a", "libmp3lame", "-b:a", "128k",
                "-metadata", f"title=Track {index + 1:02d}",
                "-metadata", "artist=FAM Automated Acceptance",
                str(target),
            ],
            check=True, capture_output=True, timeout=45,
        )
        assert target.is_file() and target.stat().st_size > 1000
        sources.append(target)

    monkeypatch.setattr(
        "full_album_maker.async_import.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(s) for s in sources], "Audio"),
    )

    window = MainWindow()
    try:
        window.add_audio()
        _wait_jobs(window, timeout=45)
        imported = list(window.project.audios)
        assert len(imported) == len(frequencies)
        assert [Path(x.path) for x in imported] == sources
        assert all(0.70 < x.duration < 0.90 for x in imported)
        assert all(
            getattr(x, "display_artist", "") == "FAM Automated Acceptance"
            for x in imported
        )
        # This mirrors canonical album construction using media returned by
        # the production UI import, rather than creating placeholder files.
        doc = ProjectDocument.new_empty("Real MP3 post-release acceptance")
        for item in imported:
            path = Path(item.path)
            stat = path.stat()
            doc.media.append(AlbumMediaAsset(
                kind="audio",
                locator=str(path),
                original_name=path.name,
                source_duration_tick=round(item.duration * TIMEBASE),
                fingerprint={"size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
                metadata={"display_title": getattr(item, "display_title", "")},
            ))
        doc.playlist.entries = PlaylistServiceV2.use_all_audio(doc)
        doc.validate()
        assert len(doc.playlist.entries) == 8

        settings = RenderSettings(
            filename="real-MP3-import-to-export",
            output_folder=str(tmp_path),
            width=320, height=240, fps=24,
            video_codec="h264", video_bitrate_bps=350_000,
            audio_codec="aac", audio_bitrate_bps=128_000,
            sample_rate=48_000, hardware_mode="software",
            container="mp4", overwrite=False, preset_id="custom",
        )
        capability = probe_ffmpeg()
        snapshot = build_render_snapshot(doc)
        expected_duration = sum(item.duration for item in imported)
        assert abs(snapshot.duration_tick / TIMEBASE - expected_duration) < 0.01
        result = RenderExecutor(capability).execute(RenderJob(snapshot, settings))
        assert result.verification.verified
        assert result.verification.has_audio and result.verification.has_video
        assert abs(result.verification.duration_seconds - expected_duration) < 0.30
        assert settings.final_output.is_file()

        pcm = subprocess.run(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-i", str(settings.final_output), "-vn",
                "-ac", "1", "-ar", "48000", "-f", "s16le", "-",
            ],
            capture_output=True, check=True, timeout=60,
        )
        samples = array("h")
        samples.frombytes(pcm.stdout)
        assert len(samples) >= int((expected_duration - 0.15) * 48000)

        song_start = 0.0
        for index, (item, expected_hz) in enumerate(zip(imported, frequencies)):
            center = song_start + item.duration / 2
            start = round((center - 0.12) * 48000)
            end = round((center + 0.12) * 48000)
            clip = samples[start:end]
            assert len(clip) > 11000, f"Audio clip missing: song {index + 1}"
            assert max(abs(x) for x in clip) > 250, f"Silent: song {index + 1}"
            crossing = sum(1 for prev, cur in zip(clip, clip[1:]) if prev < 0 <= cur)
            observed_hz = crossing / (len(clip) / 48000)
            assert math.isclose(observed_hz, expected_hz, abs_tol=25), (
                f"Song {index + 1}: {observed_hz:.1f} Hz vs {expected_hz} Hz"
            )
            song_start += item.duration
    finally:
        _close_without_dirty_prompt(window)
