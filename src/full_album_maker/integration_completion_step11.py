from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .integration_core_step11 import DomainEventType


_installed = False
_originals: dict[str, Any] = {}


def _timeline_song_selected(self, song_id: str) -> None:
    document = self.editor_workspace.document()
    if song_id not in document.song_map():
        return
    self.selection_store.update(
        revision=document.revision,
        song_ids=(song_id,),
        layer_ids=(),
        primary_song_id=song_id,
        primary_layer_id="",
        time_tick=self.editor_workspace.session.playhead_tick,
        emit=True,
    )


def _timeline_layer_selected(self, layer_id: str) -> None:
    document = self.editor_workspace.document()
    if layer_id not in document.layer_map():
        return
    self.selection_store.update(
        revision=document.revision,
        song_ids=(),
        layer_ids=(layer_id,),
        primary_song_id="",
        primary_layer_id=layer_id,
        time_tick=self.editor_workspace.session.playhead_tick,
        emit=True,
    )


def _playhead_context(self, tick: int) -> None:
    document = self.editor_workspace.document()
    self.selection_store.update(
        revision=document.revision,
        time_tick=max(0, int(tick)),
        emit=True,
    )
    self._s11_emit(
        DomainEventType.PREVIEW_STATE,
        document,
        {
            "playhead_tick": self.editor_workspace.session.playhead_tick,
            "playing": bool(self.editor_workspace.play_timer.isActive()),
            "workspace": self.foundation_state.workspace,
        },
    )


def _spectrum_layer_selected(self, layer_id: str) -> None:
    self._s11_timeline_layer_selected(str(layer_id))


def _workspace_changed(self, route: str) -> None:
    # Navigation is view state only. This event lets observers update preview
    # ownership/status without touching ProjectDocument revision.
    document = self.editor_workspace.document()
    self._s11_emit(
        DomainEventType.PREVIEW_STATE,
        document,
        {
            "workspace": str(route),
            "playhead_tick": self.editor_workspace.session.playhead_tick,
            "playing": bool(self.editor_workspace.play_timer.isActive()),
        },
    )


def _quiesce_autosave(self, *, restart: bool) -> None:
    timer = getattr(self, "_s11_autosave_timer", None)
    if timer is not None:
        timer.stop()
    coordinator = getattr(self, "_s11_autosave", None)
    if coordinator is not None:
        coordinator.take_pending()
    executor = getattr(self, "_s11_executor", None)
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)
    self._s11_executor = (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="fam-step11-autosave")
        if restart
        else None
    )


def _foundation_save(self) -> bool:
    self._s11_quiesce_autosave(restart=True)
    return bool(_originals["foundation_save"](self))


def _close_event(self, event) -> None:
    _originals["close_event"](self, event)
    try:
        accepted = event.isAccepted()
    except Exception:
        accepted = True
    if accepted:
        self._s11_quiesce_autosave(restart=False)
        for name in ("_s08_preview_worker", "_s03_preview_cache"):
            worker = getattr(self, name, None)
            close = getattr(worker, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass


def _init(self, *args, **kwargs) -> None:
    _originals["window_init"](self, *args, **kwargs)

    if hasattr(self, "timeline_precision_s05"):
        canvas = self.timeline_precision_s05.canvas
        canvas.song_selected.connect(self._s11_timeline_song_selected)
        canvas.layer_selected.connect(self._s11_timeline_layer_selected)
        canvas.playhead_requested.connect(self._s11_playhead_context)
    if hasattr(self, "spectrum_context_s08"):
        self.spectrum_context_s08.layer_selected.connect(self._s11_spectrum_layer_selected)
    if hasattr(self, "spectrum_workspace_s08"):
        self.spectrum_workspace_s08.layer_selected.connect(self._s11_spectrum_layer_selected)
    if hasattr(self, "spectrum_timeline_s08"):
        self.spectrum_timeline_s08.playhead_requested.connect(self._s11_playhead_context)
    self.foundation_state.workspace_changed.connect(self._s11_workspace_changed)


def install_step11_integration_completion() -> None:
    global _installed
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _originals.update(
        window_init=Window.__init__,
        foundation_save=Window._foundation_save_project,
        close_event=Window.closeEvent,
    )

    Window.__init__ = _init
    Window._foundation_save_project = _foundation_save
    Window.closeEvent = _close_event
    Window._s11_timeline_song_selected = _timeline_song_selected
    Window._s11_timeline_layer_selected = _timeline_layer_selected
    Window._s11_playhead_context = _playhead_context
    Window._s11_spectrum_layer_selected = _spectrum_layer_selected
    Window._s11_workspace_changed = _workspace_changed
    Window._s11_quiesce_autosave = _quiesce_autosave
    _installed = True
