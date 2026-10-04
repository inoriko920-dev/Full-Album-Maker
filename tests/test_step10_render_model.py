from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.render_center_model_step10 import (
    RenderJob,
    RenderJobState,
    RenderSettings,
    build_render_snapshot,
    normalized_output_path,
    sanitize_filename,
    settings_from_preset,
)


def _document(tmp_path: Path) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Album Kenangan")
    audio_path = tmp_path / "lagu utama.wav"
    audio_path.write_bytes(b"RIFF-fixture-audio")
    audio = MediaAsset(
        kind="audio",
        locator=str(audio_path),
        original_name=audio_path.name,
        source_duration_tick=30 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Senja di Kota Ini",
            display_artist="Perjalanan Kita",
            source_out_tick=30 * TIMEBASE,
        )
    )
    doc.validate()
    return doc


def test_render_settings_presets_are_normalized_and_not_ui_strings(tmp_path: Path) -> None:
    p1080 = settings_from_preset("youtube_1080p", filename="Senja di Kota Ini - Full Album", output_folder=str(tmp_path))
    p1440 = settings_from_preset("youtube_1440p", filename="Album 1440p", output_folder=str(tmp_path))
    p4k = settings_from_preset("youtube_4k", filename="Album 4K", output_folder=str(tmp_path))
    assert (p1080.width, p1080.height, p1080.video_codec, p1080.sample_rate) == (1920, 1080, "h264", 48_000)
    assert (p1440.width, p1440.height, p1440.video_codec) == (2560, 1440, "h264")
    assert (p4k.width, p4k.height, p4k.video_codec) == (3840, 2160, "h265")
    assert p1080.final_output == tmp_path.resolve() / "Senja di Kota Ini - Full Album.mp4"
    assert len({p1080.signature(), p1440.signature(), p4k.signature()}) == 3


def test_windows_safe_filename_and_output_path_policy(tmp_path: Path) -> None:
    assert sanitize_filename("Album Kenangan") == "Album Kenangan"
    assert normalized_output_path(tmp_path, "Album Kenangan") == tmp_path.resolve() / "Album Kenangan.mp4"
    for invalid in ("CON", "NUL.mp4", "bad:name", "bad?.mp4", "trailing. ", "../escape.mp4"):
        with pytest.raises(ValueError):
            normalized_output_path(tmp_path, invalid)


def test_codec_hardware_matrix_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tidak kompatibel"):
        RenderSettings(
            filename="x",
            output_folder=str(tmp_path),
            video_codec="h265",
            hardware_mode="h264_nvenc",
        ).validate()
    with pytest.raises(ValueError, match="tidak kompatibel"):
        RenderSettings(
            filename="x",
            output_folder=str(tmp_path),
            video_codec="h264",
            hardware_mode="hevc_nvenc",
        ).validate()


def test_render_snapshot_is_canonical_immutable_and_separate_from_live_edit(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    snapshot = build_render_snapshot(doc)
    first_hash = snapshot.snapshot_hash
    first_json = snapshot.project_json
    first_revision = snapshot.project_revision

    # Mutate the live project after enqueue/snapshot creation.
    doc.playlist.entries[0].display_title = "Judul Sesudah Enqueue"
    doc.revision += 1
    doc.validate()

    assert snapshot.snapshot_hash == first_hash
    assert snapshot.project_json == first_json
    assert snapshot.project_revision == first_revision
    snap_doc = snapshot.document()
    assert snap_doc.playlist.entries[0].display_title == "Senja di Kota Ini"
    assert snap_doc.revision == first_revision
    assert build_render_snapshot(snap_doc).snapshot_hash == first_hash
    assert build_render_snapshot(doc).snapshot_hash != first_hash


def test_snapshot_hash_changes_for_render_relevant_content(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    before = build_render_snapshot(doc)
    doc.canvas.width = 2560
    doc.canvas.height = 1440
    doc.revision += 1
    after = build_render_snapshot(doc)
    assert before.snapshot_hash != after.snapshot_hash
    assert before.content_signature != after.content_signature


def test_render_job_state_machine_prevents_invalid_transitions_and_pause_is_fail_closed(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    settings = settings_from_preset("youtube_1080p", filename="job", output_folder=str(tmp_path))
    job = RenderJob(build_render_snapshot(doc), settings)
    assert job.state == RenderJobState.DRAFT
    assert job.can_pause is False
    with pytest.raises(ValueError):
        job.transition(RenderJobState.RUNNING)
    job.transition(RenderJobState.PREFLIGHTING)
    job.transition(RenderJobState.READY)
    job.transition(RenderJobState.QUEUED)
    job.transition(RenderJobState.STARTING)
    job.transition(RenderJobState.RUNNING)
    assert job.started_at
    assert job.can_cancel is True
    job.transition(RenderJobState.FINALIZING)
    job.transition(RenderJobState.COMPLETED)
    assert job.finished_at
    assert job.can_cancel is False
    with pytest.raises(ValueError):
        job.transition(RenderJobState.RUNNING)


def test_retry_keeps_logical_job_id_but_creates_new_attempt(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    settings = settings_from_preset("youtube_1080p", filename="retry", output_folder=str(tmp_path))
    job = RenderJob(build_render_snapshot(doc), settings)
    job.transition(RenderJobState.PREFLIGHTING)
    job.transition(RenderJobState.BLOCKED)
    retry = job.retry()
    assert retry.job_id == job.job_id
    assert retry.attempt_id != job.attempt_id
    assert retry.state == RenderJobState.DRAFT
    assert retry.snapshot.snapshot_hash == job.snapshot.snapshot_hash
