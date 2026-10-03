from __future__ import annotations

import threading

from PySide6.QtCore import QCoreApplication

from full_album_maker.ai_agent_core_step09 import ProviderInterpretation, build_agent_context_snapshot
from full_album_maker.ai_async_step09 import AsyncAgentProvider
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _context():
    doc = ProjectDocument.new_empty("Async AI")
    audio = MediaAsset(
        kind="audio",
        locator="C:/private/song.wav",
        original_name="song.wav",
        source_duration_tick=5 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(
            asset_id=audio.asset_id,
            display_title="Song",
            source_out_tick=5 * TIMEBASE,
        )
    )
    doc.validate()
    return build_agent_context_snapshot(doc, selected_song_ids=(doc.playlist.entries[0].song_id,))


class _OutOfOrderProvider:
    provider_id = "test"

    def __init__(self) -> None:
        self.first_release = threading.Event()
        self.second_done = threading.Event()
        self._lock = threading.Lock()
        self._calls = 0

    def interpret(self, prompt, context):
        with self._lock:
            self._calls += 1
            call = self._calls
        if call == 1:
            self.first_release.wait(timeout=3)
            return ProviderInterpretation(message=f"first:{prompt}", clarification="first")
        self.second_done.set()
        return ProviderInterpretation(message=f"second:{prompt}", clarification="second")


class _BlockingProvider:
    provider_id = "test"

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()

    def interpret(self, prompt, context):
        self.started.set()
        self.release.wait(timeout=3)
        return ProviderInterpretation(message="late", clarification="late")


class _MutatingProvider:
    provider_id = "test"

    def interpret(self, prompt, context):
        context.payload["mutated_by_provider"] = True
        return ProviderInterpretation(message="ok", clarification="ok")


def _drain(app: QCoreApplication, rounds: int = 6) -> None:
    for _ in range(rounds):
        app.processEvents()


def test_newer_provider_result_wins_and_stale_completion_is_discarded() -> None:
    app = _app()
    provider = _OutOfOrderProvider()
    worker = AsyncAgentProvider(provider, workers=2)
    results: list[tuple[int, str]] = []
    worker.result_ready.connect(lambda token, result: results.append((token, result.message)))

    first = worker.request("pertama", _context())
    second = worker.request("kedua", _context())
    assert second > first
    assert provider.second_done.wait(timeout=2)
    _drain(app)
    assert results == [(second, "second:kedua")]

    provider.first_release.set()
    assert worker.wait_for_idle(timeout=2)
    _drain(app)
    assert results == [(second, "second:kedua")]
    worker.close()


def test_cancel_invalidates_inflight_result_without_emitting_failure() -> None:
    app = _app()
    provider = _BlockingProvider()
    worker = AsyncAgentProvider(provider, workers=1)
    results: list[object] = []
    errors: list[str] = []
    worker.result_ready.connect(lambda _token, result: results.append(result))
    worker.request_failed.connect(lambda _token, error: errors.append(error))

    token = worker.request("jalan", _context())
    assert provider.started.wait(timeout=2)
    cancelled_generation = worker.cancel_current()
    assert cancelled_generation > token
    provider.release.set()
    assert worker.wait_for_idle(timeout=2)
    _drain(app)
    assert results == []
    assert errors == []
    worker.close()


def test_provider_receives_defensive_context_copy() -> None:
    app = _app()
    context = _context()
    assert "mutated_by_provider" not in context.payload
    worker = AsyncAgentProvider(_MutatingProvider(), workers=1)
    worker.request("test", context)
    assert worker.wait_for_idle(timeout=2)
    _drain(app)
    assert "mutated_by_provider" not in context.payload
    worker.close()
