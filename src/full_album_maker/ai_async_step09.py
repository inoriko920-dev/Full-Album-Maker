from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from copy import deepcopy
import threading

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .ai_agent_core_step09 import AgentContextSnapshot, ProviderInterpretation
from .ai_provider_step09 import AgentPlanProvider


class AsyncAgentProvider(QObject):
    """Run provider interpretation off the UI thread with stale-result guard.

    Cancelling/invalidation never attempts to stop a network socket forcibly; it
    advances the generation so an old completion cannot update UI state. Project
    mutation is impossible here because providers receive only a frozen context,
    never an EditorController.

    Future callbacks run on executor threads. They never emit the public UI
    signals directly. Completion is first queued back to this QObject's thread,
    then result/error/busy signals are emitted from that owner thread. This keeps
    production receivers such as FoundationMainWindow deterministic while
    preserving the existing stale-generation guard.
    """

    result_ready = Signal(int, object)
    request_failed = Signal(int, str)
    busy_changed = Signal(bool)
    _completion_ready = Signal(int, object, str)

    def __init__(
        self,
        provider: AgentPlanProvider,
        *,
        workers: int = 2,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(4, int(workers))),
            thread_name_prefix="fam-ai-provider",
        )
        self._lock = threading.Lock()
        self._generation = 0
        self._pending: dict[int, Future] = {}
        self._closed = False
        self._completion_ready.connect(
            self._deliver_completion,
            Qt.ConnectionType.QueuedConnection,
        )

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def request(self, prompt: str, context: AgentContextSnapshot) -> int:
        context.validate()
        with self._lock:
            if self._closed:
                raise RuntimeError("AsyncAgentProvider sudah ditutup.")
            self._generation += 1
            token = self._generation
            was_busy = bool(self._pending)
        # Rebuild a defensive copy so provider code cannot mutate the UI-owned
        # context payload even accidentally.
        snapshot = AgentContextSnapshot(
            project_id=context.project_id,
            revision=context.revision,
            selected_song_ids=tuple(context.selected_song_ids),
            selected_layer_ids=tuple(context.selected_layer_ids),
            allowed_media_ids=tuple(context.allowed_media_ids),
            enabled_contexts=tuple(context.enabled_contexts),
            payload=deepcopy(context.payload),
            fingerprint=context.fingerprint,
            format=context.format,
        )
        future = self._executor.submit(
            self._interpret,
            token,
            str(prompt),
            snapshot,
        )
        with self._lock:
            self._pending[token] = future
        if not was_busy:
            self.busy_changed.emit(True)
        future.add_done_callback(lambda done, value=token: self._finish(value, done))
        return token

    def invalidate(self) -> int:
        with self._lock:
            self._generation += 1
            token = self._generation
        return token

    def cancel_current(self) -> int:
        token = self.invalidate()
        with self._lock:
            futures = tuple(self._pending.values())
        for future in futures:
            future.cancel()
        return token

    def _interpret(
        self,
        token: int,
        prompt: str,
        context: AgentContextSnapshot,
    ) -> tuple[int, ProviderInterpretation | None, str]:
        try:
            result = self.provider.interpret(prompt, context)
            if not isinstance(result, ProviderInterpretation):
                raise TypeError("Provider STEP09 tidak mengembalikan ProviderInterpretation.")
            return token, result, ""
        except Exception as exc:
            return token, None, f"{type(exc).__name__}: {exc}"

    def _finish(self, token: int, future: Future) -> None:
        """Executor-thread callback: bookkeeping only, then queue to UI thread."""
        with self._lock:
            self._pending.pop(token, None)
        try:
            result_token, result, error = future.result()
        except Exception as exc:
            result_token, result, error = token, None, f"{type(exc).__name__}: {exc}"
        self._completion_ready.emit(result_token, result, error)

    @Slot(int, object, str)
    def _deliver_completion(
        self,
        result_token: int,
        result: ProviderInterpretation | None,
        error: str,
    ) -> None:
        """Owner-thread delivery for public Qt signals and stale-result checks."""
        with self._lock:
            current = self._generation
            still_busy = bool(self._pending)
            closed = self._closed
        if not still_busy:
            self.busy_changed.emit(False)
        if closed or result_token != current:
            return
        if error:
            self.request_failed.emit(result_token, error)
            return
        if result is None:
            self.request_failed.emit(
                result_token,
                "Provider STEP09 selesai tanpa ProviderInterpretation.",
            )
            return
        self.result_ready.emit(result_token, result)

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        with self._lock:
            pending = tuple(self._pending.values())
        if not pending:
            return True
        _done, not_done = wait(pending, timeout=max(0.0, float(timeout)))
        return not not_done

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            futures = tuple(self._pending.values())
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)