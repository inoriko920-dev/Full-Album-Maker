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
    MAX_HISTORY,
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
    # Another attempt for the same output stem must survive recovery.
    foreign_attempt = tmp_path / f".{job.settings.final_output.stem}.foreign.abc.rendering.mp4"
    foreign_attempt.write_bytes(b"do-not-delete")
    # The current mkstemp naming convention also includes a random suffix.
    bound_random = tmp_path / f".{job.settings.final_output.stem}.{job.attempt_id[:8]}.xyz.rendering.mp4"
    bound_random.write_bytes(b"old-attempt")
    store.save([job])

    jobs, changed = store.recover()
    assert changed == (job.attempt_id,)
    assert jobs[0].state == RenderJobState.INTERRUPTED
    assert jobs[0].error_code == "INTERRUPTED_ON_RESTART"
    assert not stage.exists()
    assert not bound_random.exists()
    assert unrelated.exists()
    assert foreign_attempt.read_bytes() == b"do-not-delete"
    assert store.load()[0].state == RenderJobState.INTERRUPTED


def test_restart_cleans_stage_for_filename_with_square_brackets(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "queue-with-brackets.json")
    job = _job(tmp_path, "My Album [Live]")
    _mark_ready(job)
    job.transition(RenderJobState.STARTING)
    job.transition(RenderJobState.RUNNING)
    stage = tmp_path / (
        f".{job.settings.final_output.stem}.{job.attempt_id[:8]}.abc.rendering.mp4"
    )
    stage.write_bytes(b"partial-render")
    unrelated = tmp_path / f".{job.settings.final_output.stem}.other.abc.rendering.mp4"
    unrelated.write_bytes(b"keep")
    store.save([job])

    jobs, changed = store.recover()
    assert changed == (job.attempt_id,)
    assert jobs[0].state == RenderJobState.INTERRUPTED
    assert not stage.exists()
    assert unrelated.read_bytes() == b"keep"


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


def test_many_queued_attempts_remain_persisted_past_history_limit(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "many-queued.json")
    queue = RenderQueue(store)
    prototype = _job(tmp_path, "many")
    from full_album_maker.render_center_model_step10 import RenderJob

    attempts = []
    for _ in range(MAX_HISTORY + 3):
        job = RenderJob(snapshot=prototype.snapshot, settings=prototype.settings)
        _mark_ready(job)
        queue.enqueue(job)
        attempts.append(job.attempt_id)

    assert [job.attempt_id for job in queue.jobs] == attempts
    assert [job.attempt_id for job in store.load()] == attempts
    assert queue.next_queued().attempt_id == attempts[0]
    assert RenderQueue(store).next_queued().attempt_id == attempts[0]


def test_old_terminal_history_is_trimmed_before_pending_jobs(tmp_path: Path) -> None:
    store = RenderQueueStore(tmp_path / "mixed-queue.json")
    prototype = _job(tmp_path, "mixed")
    from full_album_maker.render_center_model_step10 import RenderJob

    jobs = []
    for _ in range(MAX_HISTORY + 5):
        job = RenderJob(snapshot=prototype.snapshot, settings=prototype.settings)
        _mark_ready(job)
        job.transition(RenderJobState.STARTING)
        job.transition(RenderJobState.RUNNING)
        job.transition(RenderJobState.FINALIZING)
        job.transition(RenderJobState.COMPLETED)
        jobs.append(job)
    pending = RenderJob(snapshot=prototype.snapshot, settings=prototype.settings)
    _mark_ready(pending)
    pending.transition(RenderJobState.QUEUED)
    jobs.insert(0, pending)

    store.save(jobs)
    restored = store.load()
    assert len(restored) == MAX_HISTORY
    assert restored[0].attempt_id == pending.attempt_id
    assert [job.attempt_id for job in restored[1:]] == [job.attempt_id for job in jobs[-(MAX_HISTORY - 1):]]


def test_enqueue_failed_save_is_retryable_without_ghost_queue_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RenderQueueStore(tmp_path / "unwritable-queue.json")
    queue = RenderQueue(store)
    job = _job(tmp_path, "save-failure")
    _mark_ready(job)

    original_save = store.save

    def fail_save(_jobs) -> None:
        raise OSError("simulated disk full")

    monkeypatch.setattr(store, "save", fail_save)
    with pytest.raises(OSError, match="disk full"):
        queue.enqueue(job)

    assert job.state == RenderJobState.READY
    assert queue.jobs == []
    assert store.load() == []

    # A later successful write can enqueue the exact same attempt.
    monkeypatch.setattr(store, "save", original_save)
    assert queue.enqueue(job) is job
    assert job.state == RenderJobState.QUEUED
    assert queue.next_queued() is job
    assert store.load()[0].attempt_id == job.attempt_id


def test_retry_failed_save_does_not_create_unpersisted_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RenderQueueStore(tmp_path / "failed-retry-queue.json")
    failed = _job(tmp_path, "retry-save-failure")
    _mark_ready(failed)
    failed.transition(RenderJobState.STARTING)
    failed.transition(RenderJobState.FAILED)
    store.save([failed])
    queue = RenderQueue(store)
    original_save = store.save

    def fail_save(_jobs) -> None:
        raise PermissionError("queue directory read-only")

    monkeypatch.setattr(store, "save", fail_save)
    with pytest.raises(PermissionError, match="read-only"):
        queue.retry(failed.job_id, failed.attempt_id)

    assert len(queue.jobs) == 1
    assert queue.jobs[0].attempt_id == failed.attempt_id
    assert [j.attempt_id for j in store.load()] == [failed.attempt_id]

    monkeypatch.setattr(store, "save", original_save)
    retried = queue.retry(failed.job_id, failed.attempt_id)
    assert len(queue.jobs) == 2
    assert retried.state == RenderJobState.DRAFT
    assert retried.attempt_id != failed.attempt_id
    assert store.load()[1].attempt_id == retried.attempt_id


def test_update_failed_save_preserves_registered_queue_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RenderQueueStore(tmp_path / "failed-update-queue.json")
    existing = _job(tmp_path, "existing-update")
    _mark_ready(existing)
    store.save([existing])
    queue = RenderQueue(store)
    additional = _job(tmp_path, "new-update")
    _mark_ready(additional)

    def fail_save(_jobs) -> None:
        raise OSError("write interrupted")

    monkeypatch.setattr(store, "save", fail_save)
    with pytest.raises(OSError, match="interrupted"):
        queue.update(additional)
    assert [j.attempt_id for j in queue.jobs] == [existing.attempt_id]
    assert [j.attempt_id for j in store.load()] == [existing.attempt_id]
