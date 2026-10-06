from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMessageBox

from .integration_core_step11 import (
    DomainEvent,
    DomainEventHub,
    DomainEventType,
    SelectionStore,
    classify_document_changes,
    normalized_project_hash,
    project_token,
)
from .integration_lifecycle_step11 import (
    DebouncedAutosaveCoordinator,
    IntegrationRecoveryStore,
    AutosaveRequest,
    save_verified_legacy_project,
)
from .paths import data_dir


_installed = False
_originals: dict[str, Any] = {}


class _IntegrationBridge(QObject):
    autosave_done = Signal(object, bool, str)


def _recovery_path(token: str) -> Path:
    safe = "".join(ch for ch in str(token) if ch.isalnum() or ch in "-_" )[:64] or "unknown"
    return data_dir() / "recovery" / "step11" / f"{safe}.json"


def _project_path(self) -> str:
    return str(
        getattr(self, "_foundation_project_path", "")
        or getattr(getattr(self, "editor_workspace", None), "current_project_path", "")
        or ""
    )


def _current_token(self) -> str:
    return project_token(self.editor_workspace.document(), self._s11_project_path())


def _emit(self, event_type: DomainEventType, document=None, payload=None, *, command_id: str = "") -> None:
    document = document or self.editor_workspace.document()
    self.event_hub.emit(
        DomainEvent(
            event_type,
            self._s11_project_token,
            document.revision,
            dict(payload or {}),
            command_id=command_id,
        )
    )


def _sync_foundation_status(self) -> None:
    if not hasattr(self, "foundation_state"):
        return
    session = self.editor_workspace.session
    if session.is_dirty:
        autosave = self._s11_autosave.status
        if autosave.last_error:
            state = ("Belum disimpan • Autosave gagal", "error")
        elif autosave.pending:
            state = ("Belum disimpan • Autosave…", "warning")
        elif autosave.last_success_revision:
            state = (f"Belum disimpan • Recovery r{autosave.last_success_revision}", "warning")
        else:
            state = ("Belum disimpan", "warning")
    else:
        state = ("Tersimpan", "success")
    self.foundation_state.set_status(save=state)
    self.foundation_shell.refresh_commands()


def _bind_project(self, document, *, clear_selection: bool = True) -> None:
    self._s11_project_token = self._s11_current_token()
    self.selection_store.bind_project(self._s11_project_token, clear=clear_selection)
    self._s11_previous_document = document.clone()
    self._s11_last_seen_revision = document.revision
    self._s11_last_seen_hash = normalized_project_hash(document)
    self._s11_autosave = DebouncedAutosaveCoordinator()
    self._s11_autosave_timer.stop()
    self._s11_emit(
        DomainEventType.PROJECT_OPENED,
        document,
        {"project_path": self._s11_project_path(), "project_id": document.project_id},
    )
    self._s11_sync_foundation_status()


def _document_changed(self, document) -> None:
    if not hasattr(self, "event_hub"):
        return
    current = document.clone()
    current_hash = normalized_project_hash(current)
    previous = self._s11_previous_document

    # Same document/revision is a refresh, not a mutation event.
    if (
        previous.project_id == current.project_id
        and self._s11_last_seen_revision == current.revision
        and self._s11_last_seen_hash == current_hash
    ):
        self.selection_store.prune(current, emit=False)
        self._s11_sync_layer_selection()
        return

    if previous.project_id != current.project_id:
        self._s11_bind_project(current, clear_selection=True)
        return

    changes = classify_document_changes(previous, current)
    self._s11_previous_document = current.clone()
    self._s11_last_seen_revision = current.revision
    self._s11_last_seen_hash = current_hash
    self.selection_store.prune(current, emit=True)
    self._s11_sync_layer_selection()

    self._s11_emit(
        DomainEventType.PROJECT_REVISION_CHANGED,
        current,
        {"revision": current.revision, "content_hash": current_hash},
    )
    for event_type in changes:
        self._s11_emit(event_type, current)
    self._s11_emit(
        DomainEventType.UNDO_STACK_CHANGED,
        current,
        {"can_undo": self.editor_workspace.session.can_undo, "can_redo": self.editor_workspace.session.can_redo},
    )
    self._s11_emit(
        DomainEventType.DIRTY_CHANGED,
        current,
        {"dirty": self.editor_workspace.session.is_dirty},
    )

    if self.editor_workspace.session.is_dirty:
        self._s11_autosave.request(
            current,
            project_path=self._s11_project_path(),
            token=self._s11_project_token,
        )
        self._s11_autosave_timer.start()
    else:
        self._s11_autosave_timer.stop()
    self._s11_sync_foundation_status()


def _sync_layer_selection(self) -> None:
    if not hasattr(self, "selection_store"):
        return
    document = self.editor_workspace.document()
    valid = set(document.layer_map())
    values = tuple(
        layer_id for layer_id in self.editor_workspace.session.selected_layer_ids if layer_id in valid
    )
    primary = values[0] if len(values) == 1 else ""
    self.selection_store.update(
        revision=document.revision,
        layer_ids=values,
        primary_layer_id=primary,
        time_tick=self.editor_workspace.session.playhead_tick,
        emit=True,
    )


def _album_selection(self, values) -> None:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    ordered = tuple(song.song_id for song in document.playlist.entries if song.song_id in {str(x) for x in values})
    primary = ordered[0] if len(ordered) == 1 else (self.selection_store.snapshot.primary_song_id if self.selection_store.snapshot.primary_song_id in ordered else "")
    self.selection_store.update(
        revision=document.revision,
        song_ids=ordered,
        primary_song_id=primary,
        emit=True,
    )


def _visual_selection(self, values, primary: str) -> None:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    requested = {str(x) for x in (values or ())}
    ordered = tuple(song.song_id for song in document.playlist.entries if song.song_id in requested)
    self.selection_store.update(
        revision=document.revision,
        song_ids=ordered,
        primary_song_id=str(primary) if str(primary) in valid else "",
        time_tick=self.editor_workspace.session.playhead_tick,
        emit=True,
    )


def _schedule_autosave_flush(self) -> None:
    request = self._s11_autosave.take_pending()
    if request is None:
        return
    self._s11_emit(
        DomainEventType.AUTOSAVE_STATUS,
        payload={"state": "WRITING", "revision": request.revision},
    )
    path = _recovery_path(request.project_token)

    def work() -> tuple[AutosaveRequest, bool, str]:
        try:
            IntegrationRecoveryStore(path).write(request)
            return request, True, ""
        except Exception as exc:
            return request, False, str(exc)

    future = self._s11_executor.submit(work)

    def done(completed) -> None:
        try:
            req, success, error = completed.result()
        except Exception as exc:
            req, success, error = request, False, str(exc)
        self._s11_bridge.autosave_done.emit(req, success, error)

    future.add_done_callback(done)


def _autosave_done(self, request: AutosaveRequest, success: bool, error: str) -> None:
    # Project switch: completion remains valid for its own recovery file but must
    # not affect current project status.
    if request.project_token != self._s11_project_token:
        return
    status = self._s11_autosave.complete(request, success=bool(success), error=str(error))
    self._s11_emit(
        DomainEventType.AUTOSAVE_STATUS,
        payload={
            "state": "SAVED" if success else "FAILED",
            "revision": request.revision,
            "latest_revision": status.latest_revision,
            "error": str(error),
        },
    )
    self._s11_sync_foundation_status()


def _clear_recovery(self) -> None:
    IntegrationRecoveryStore(_recovery_path(self._s11_project_token)).clear()
    self._s11_autosave = DebouncedAutosaveCoordinator()
    self._s11_autosave_timer.stop()


def _mark_compatibility_persisted(self, path: str = "") -> None:
    """Synchronize legacy compatibility state without making it a second UX owner."""

    try:
        from .project_dirty import _project_state, _update_window_title

        if hasattr(self, "_saved_project_state"):
            self._saved_project_state = _project_state(self.project)
        if path and hasattr(self, "_current_project_path"):
            self._current_project_path = str(path)
        _update_window_title(self)
    except Exception:
        # Foundation STEP11 remains authoritative even if a legacy presentation
        # helper is unavailable during a reduced/headless test.
        pass


def _mark_saved_after_publish(self, path: str) -> bool:
    self.editor_workspace.session.mark_saved()
    self._s11_mark_compatibility_persisted(path)
    self._s11_clear_recovery()
    self._s11_previous_document = self.editor_workspace.document()
    self._s11_last_seen_revision = self._s11_previous_document.revision
    self._s11_last_seen_hash = normalized_project_hash(self._s11_previous_document)
    self._s11_emit(DomainEventType.DIRTY_CHANGED, payload={"dirty": False})
    self._s11_sync_foundation_status()
    return True


def _foundation_save_project(self) -> bool:
    if not getattr(self, "_foundation_project_open", False):
        return False
    expected = self.editor_workspace.document()
    if hasattr(self, "_s04_capture_document"):
        self._s04_capture_document()
    path = self._s11_project_path()
    if not path:
        from PySide6.QtWidgets import QFileDialog
        from .paths import output_dir
        default = str(output_dir() / "Full_Album_Project.json")
        path, _ = QFileDialog.getSaveFileName(self, "Simpan Proyek", default, "Full Album Project (*.json)")
        if not path:
            return False
    self.foundation_state.set_status(save=("Menyimpan…", "warning"))
    try:
        saved = save_verified_legacy_project(path, self.project, expected)
        self._foundation_project_path = str(saved)
        try:
            self._home_recent_service.touch(str(saved), self.project)
            self._home_state = self._home_state.with_recent(self._home_recent_service.load())
            self._apply_home_state()
        except Exception:
            pass
    except Exception as exc:
        self.foundation_state.set_status(save=("Gagal menyimpan", "error"))
        QMessageBox.critical(
            self,
            "Simpan Proyek",
            f"Gagal menyimpan/verifikasi proyek; file lama dipertahankan:\n{exc}",
        )
        return False
    return self._s11_mark_saved_after_publish(str(saved))


def _foundation_open_project(self) -> None:
    # HomeProjectService owns validated legacy-envelope open + recent-path state.
    self._home_choose_open_project()


def _adopt(self, project, result, *, route="media", add_recent=True):
    output = _originals["window_adopt"](self, project, result, route=route, add_recent=add_recent)
    if hasattr(self, "event_hub"):
        document = self.editor_workspace.document()
        self._s11_bind_project(document, clear_selection=True)
        self._s11_maybe_offer_recovery(document)
    return output


def _maybe_offer_recovery(self, canonical_document) -> bool:
    store = IntegrationRecoveryStore(_recovery_path(self._s11_project_token))
    candidate = store.discover()
    if candidate is None:
        return False
    try:
        recovered = candidate.document()
    except Exception:
        return False
    if normalized_project_hash(recovered) == normalized_project_hash(canonical_document):
        store.clear()
        return False
    if candidate.revision < canonical_document.revision:
        return False
    if str(os.environ.get("FAM_STEP11_NO_RECOVERY_PROMPT", "")).strip() == "1":
        self.foundation_state.set_status(save=("Recovery tersedia", "warning"))
        return True
    answer = QMessageBox.question(
        self,
        "Pulihkan Autosave",
        f"Recovery editor revision {candidate.revision} ditemukan. Pulihkan perubahan yang belum tersimpan?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return True
    from .editor_commands import ReplaceDocument
    self.editor_workspace.dispatch_external(
        ReplaceDocument(recovered),
        message="Recovery STEP11 dipulihkan ke ProjectDocument; simpan untuk menjadikannya canonical.",
    )
    return True


def _close_event(self, event) -> None:
    # Preserve render safety before any save/discard prompt.
    render_bridge = getattr(self, "_s10_async", None)
    if render_bridge is not None and bool(getattr(render_bridge, "busy", False)):
        QMessageBox.information(self, "Render masih berjalan", "Selesaikan/batalkan render sebelum menutup aplikasi.")
        event.ignore()
        return

    session = self.editor_workspace.session
    if session.is_dirty:
        answer = QMessageBox.question(
            self,
            "Perubahan belum disimpan",
            "Simpan perubahan project sebelum menutup aplikasi?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if answer == QMessageBox.StandardButton.Save:
            if not self._foundation_save_project():
                event.ignore()
                return
        else:
            # STEP11 owns dirty/close UX. Discard resets the authoritative session
            # and clears recovery so the same explicitly discarded edit is not
            # offered again on the next launch.
            session.mark_saved()
            self._s11_mark_compatibility_persisted(self._s11_project_path())
            self._s11_clear_recovery()
            self._s11_sync_foundation_status()
    else:
        # Keep the inherited compatibility close chain silent. It may still carry
        # a stale legacy envelope dirty marker, but it is not an independent UX
        # owner once Foundation/ProjectDocument STEP11 is active.
        self._s11_mark_compatibility_persisted(self._s11_project_path())

    return _originals["close_event"](self, event)


def _ai_selected_song_ids(self) -> tuple[str, ...]:
    store = getattr(self, "selection_store", None)
    if store is not None:
        document = self.editor_workspace.document()
        valid = set(document.song_map())
        requested = set(store.snapshot.song_ids)
        values = tuple(song.song_id for song in document.playlist.entries if song.song_id in requested and song.song_id in valid)
        if values:
            return values
    return _originals["ai_selected_song_ids"](self)


def _init(self, *args, **kwargs) -> None:
    _originals["window_init"](self, *args, **kwargs)
    self.event_hub = DomainEventHub()
    document = self.editor_workspace.document()
    self._s11_project_token = project_token(document, self._s11_project_path())
    self.selection_store = SelectionStore(self.event_hub, self._s11_project_token)
    self._s11_previous_document = document.clone()
    self._s11_last_seen_revision = document.revision
    self._s11_last_seen_hash = normalized_project_hash(document)
    self._s11_autosave = DebouncedAutosaveCoordinator()
    self._s11_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fam-step11-autosave")
    self._s11_bridge = _IntegrationBridge(self)
    self._s11_bridge.autosave_done.connect(self._s11_autosave_done)
    self._s11_autosave_timer = QTimer(self)
    self._s11_autosave_timer.setSingleShot(True)
    self._s11_autosave_timer.setInterval(1200)
    self._s11_autosave_timer.timeout.connect(self._s11_schedule_autosave_flush)

    self.editor_workspace.documentChanged.connect(self._s11_document_changed)
    self.editor_workspace.dirtyChanged.connect(lambda _dirty: self._s11_sync_foundation_status())
    if hasattr(self, "album_workspace"):
        self.album_workspace.selection_changed.connect(self._s11_album_selection)
    if hasattr(self, "visual_context_s06"):
        self.visual_context_s06.selection_changed.connect(self._s11_visual_selection)
    try:
        self.editor_workspace.timeline.layerSelected.connect(lambda _layer: self._s11_sync_layer_selection())
        self.editor_workspace.preview.layerSelected.connect(lambda _layer: self._s11_sync_layer_selection())
    except Exception:
        pass

    self._s11_emit(DomainEventType.PROJECT_OPENED, document, {"project_path": self._s11_project_path()})
    self._s11_sync_layer_selection()
    self._s11_sync_foundation_status()
    QTimer.singleShot(0, lambda: self._s11_maybe_offer_recovery(self.editor_workspace.document()))


def install_step11_integration() -> None:
    global _installed
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _originals.update(
        window_init=Window.__init__,
        foundation_save=Window._foundation_save_project,
        foundation_open=Window._foundation_open_project,
        window_adopt=Window._adopt_home_project,
        close_event=Window.closeEvent,
        ai_selected_song_ids=getattr(Window, "_s09_selected_song_ids"),
    )

    # Install command-bound methods before __init__; FoundationCommandAdapter will
    # bind the normalized Save/Open owners when the shell is constructed.
    Window._foundation_save_project = _foundation_save_project
    Window._foundation_open_project = _foundation_open_project
    Window._adopt_home_project = _adopt
    Window.closeEvent = _close_event
    Window._s09_selected_song_ids = _ai_selected_song_ids
    Window.__init__ = _init

    methods = {
        "_s11_project_path": _project_path,
        "_s11_current_token": _current_token,
        "_s11_emit": _emit,
        "_s11_sync_foundation_status": _sync_foundation_status,
        "_s11_bind_project": _bind_project,
        "_s11_document_changed": _document_changed,
        "_s11_sync_layer_selection": _sync_layer_selection,
        "_s11_album_selection": _album_selection,
        "_s11_visual_selection": _visual_selection,
        "_s11_schedule_autosave_flush": _schedule_autosave_flush,
        "_s11_autosave_done": _autosave_done,
        "_s11_clear_recovery": _clear_recovery,
        "_s11_mark_compatibility_persisted": _mark_compatibility_persisted,
        "_s11_mark_saved_after_publish": _mark_saved_after_publish,
        "_s11_maybe_offer_recovery": _maybe_offer_recovery,
    }
    for name, value in methods.items():
        setattr(Window, name, value)
    _installed = True
