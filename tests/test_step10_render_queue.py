from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.render_center_model_step10 import (
    RenderJob,
    RenderJobState,
    build_render_snapshot,
    settings_from_preset,
)
from full_album_maker.render_queue_step10 import (
    RenderQueue,
    RenderQueueStore,
    job_from_dict,
    job_to_dict,
)


def _job(tmp_path: Path, name: str = "queue") -> RenderJob:
    doc = ProjectDocument.new_empty("Queue")
    source = tmp_path / f"{name}.wav"
    source.write_bytes(b"audio")
    audio = MediaAsset(
        kind="audio",
        locator=str(source),
        original_name=source.name,
        source_duration_tick=5 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(asset_id=audio.asset_id, display_title=name, source_out_tick=5 * TIMEBASE)
    )
    doc.validate()
    settings = settings_from_preset("youtube_1080p", filename=name, output_folder=str(tmp_path))
    return RenderJob(build_render_snapshot(doc), settings)


def _mark_ready(job: RenderJob) -> None:
    job.transition(RenderJobState.PREFLIGHTING)
    job.transition(RenderJobState.READY)


def test_job_roundtrip_preserves_snapshot_settings_state_and_sanitizes_logs(tmp_path: Path) -> None:
    job = _job(tmp_path)
    _mark_ready(job)
    job.log_lines = ["token=supersecret hello"]
    restored = job_from_dict(job_to_dict(job))
    assert restored.job_id == job.job_id
    assert restored.attempt_id == job.attempt_id
    assert restored.state == RenderJobState.READY
    assert restored.snapshot.snapshot_hash == job.snapshot.snapshot_hash
    assert restored.settings.signature() == job.settings.signature()
    assert "supersecret" not in "\n".join(restored.log_lines)


def test_queue_refuses_draft_and_only_accepts_real_ready_job(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue.json")
    queue = RenderQueue(store)
    job = _job(tmp_path)
    with pytest.raises(ValueError, match="READY"):
        queue.enqueue(job)
    _mark_ready(job)
    queued = queue.enqueue(job)
    assert queued.state == RenderJobState.QUEUED
    assert queue.next_queued() is queued
    assert store.load()[0].state == RenderJobState.QUEUED


def test_restart_marks_active_attempt_interrupted_and_cleans_bound_stage(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue.json")
    job = _job(tmp_path, "recover")
    _mark_ready(job)
    job.transition(RenderJobState.STARTING)
    job.transition(RenderJobState.RUNNING)
    stage = tmp_path / f".{job.settings.final_output.stem}.{job.attempt_id[:8]}.rendering.mp4"
    stage.write_bytes(b"partial")
    unrelated = tmp_path / ".unrelated.rendering.mp4"
    unrelated.write_bytes(b"leave-me")
    store.save([job])

    jobs, changed = store.recover()
    assert changed == (job.attempt_id,)
    assert jobs[0].state == RenderJobState.INTERRUPTED
    assert jobs[0].error_code == "INTERRUPTED_ON_RESTART"
    assert not stage.exists()
    assert unrelated.exists()
    assert store.load()[0].state == RenderJobState.INTERRUPTED


def test_queued_job_survives_restart_but_requires_executor_critical_preflight_later(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue.json")
    job = _job(tmp_path, "queued")
    _mark_ready(job)
    job.transition(RenderJobState.QUEUED)
    store.save([job])
    jobs, changed = store.recover()
    assert changed == ()
    assert jobs[0].state == RenderJobState.QUEUED


def test_retry_creates_new_attempt_in_draft_and_cannot_queue_without_new_preflight(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue.json")
    failed = _job(tmp_path, "failed")
    _mark_ready(failed)
    failed.transition(RenderJobState.STARTING)
    failed.transition(RenderJobState.FAILED)
    store.save([failed])
    queue = RenderQueue(store)
    retry = queue.retry(failed.job_id, failed.attempt_id)
    assert retry.job_id == failed.job_id
    assert retry.attempt_id != failed.attempt_id
    assert retry.state == RenderJobState.DRAFT
    with pytest.raises(ValueError, match="READY"):
        queue.enqueue(retry)


def test_single_active_slot_returns_no_next_job_while_an_attempt_is_running(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue.json")
    first = _job(tmp_path, "first")
    second = _job(tmp_path, "second")
    _mark_ready(first)
    first.transition(RenderJobState.STARTING)
    first.transition(RenderJobState.RUNNING)
    _mark_ready(second)
    second.transition(RenderJobState.QUEUED)
    store.save([first, second])
    queue = RenderQueue(store)
    # Constructor recovery converts the stale RUNNING state to INTERRUPTED,
    # so this process can safely offer the queued item after recovery.
    assert queue.jobs[0].state == RenderJobState.INTERRUPTED
    assert queue.next_queued() is not None

    # A live active state inside the current process blocks dequeue.
    live = _job(tmp_path, "live")
    _mark_ready(live)
    live.transition(RenderJobState.STARTING)
    live.transition(RenderJobState.RUNNING)
    queue.jobs.append(live)
    assert queue.next_queued() is None


def test_corrupt_queue_store_fails_closed_instead_of_silently_dropping_history(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    path.write_text("{broken", encoding="utf-8")
    store = RenderQueueStore(path)
    with pytest.raises(ValueError, match="rusak"):
        store.load()
