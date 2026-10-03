from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from .ai_agent_core_step09 import (
    AgentPermission,
    AgentState,
    PermissionGrant,
    build_agent_context_snapshot,
)
from .ai_async_step09 import AsyncAgentProvider
from .ai_history_step09 import (
    AgentHistoryStore,
    SavedAgentCommand,
    SavedAgentCommandStore,
)
from .ai_provider_step09 import GeminiStep09Provider, MockStep09Provider
from .ai_session_step09 import AgentSessionService
from .ai_workspace_step09 import AIContextDock, AIConversationPanel, AITaskCanvas
from .template_studio_step07 import builtin_descriptors
from .timeline_workspace_step05 import TimelinePrecisionPanel


_installed = False
_original_init: Any = None


def _key_ready(self) -> bool:
    pool = getattr(self, "pool", None)
    if pool is None:
        return False
    try:
        summary = pool.summary()
        return int(summary.get("ready", 0) or 0) > 0
    except Exception:
        return False


def _initial_provider(self) -> str:
    override = str(os.environ.get("FAM_STEP09_PROVIDER", "")).strip().casefold()
    if override in {"mock", "gemini"}:
        return override
    if str(os.environ.get("FAM_STEP09_GOLDEN", "")).strip() == "1":
        return "mock"
    return "gemini"


def _install_widgets(self) -> None:
    self._s09_history_store = AgentHistoryStore()
    self._s09_saved_store = SavedAgentCommandStore()
    self._s09_agent_session: AgentSessionService | None = None
    self._s09_controller_identity: int | None = None
    self._s09_async: AsyncAgentProvider | None = None
    self._s09_request_token = 0
    self._s09_provider_id = _initial_provider(self)
    self._s09_context_snapshot = None

    self.ai_workspace_s09 = AITaskCanvas()
    index = self.foundation_shell.workspace_stack._index["ai_agent"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.ai_workspace_s09)

    context_layout = self.foundation_shell.context.layout()
    self.ai_conversations_s09 = AIConversationPanel()
    self.ai_conversations_s09.hide()
    context_layout.addWidget(self.ai_conversations_s09, 1)

    self.ai_context_s09 = AIContextDock()
    self._inspector_router.addWidget(self.ai_context_s09)

    self.ai_timeline_s09 = TimelinePrecisionPanel()
    timeline_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    timeline_layout.addWidget(self.ai_timeline_s09, 1)
    self.ai_timeline_s09.hide()

    self.ai_context_s09.set_provider(self._s09_provider_id, key_ready=_key_ready(self))


def _connect_widgets(self) -> None:
    workspace = self.ai_workspace_s09
    workspace.send_requested.connect(self._s09_send)
    workspace.preview_requested.connect(self._s09_preview)
    workspace.execute_requested.connect(self._s09_execute)
    workspace.cancel_requested.connect(self._s09_cancel)
    workspace.undo_requested.connect(self._s09_undo_ai)
    workspace.save_command_requested.connect(self._s09_save_command)
    workspace.attachment_requested.connect(self._s09_attachment_info)

    self.ai_conversations_s09.new_conversation_requested.connect(self._s09_new_conversation)
    self.ai_conversations_s09.saved_command_requested.connect(self._s09_replay_saved)
    self.ai_context_s09.provider_changed.connect(self._s09_provider_changed)
    self.ai_context_s09.permissions_changed.connect(self._s09_permissions_changed)

    self.foundation_state.workspace_changed.connect(self._s09_route)
    self.editor_workspace.documentChanged.connect(self._s09_document_changed)
    self.editor_workspace.play_timer.timeout.connect(self._s09_playback_sync)


def _hide_prior_surfaces(self) -> None:
    for name in (
        "media_context",
        "album_context",
        "timeline_context_s05",
        "visual_context_s06",
        "template_context_s07",
        "spectrum_context_s08",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    for name in (
        "media_timeline_canvas",
        "album_timeline_canvas",
        "timeline_precision_s05",
        "visual_timeline_s06",
        "template_timeline_s07",
        "spectrum_timeline_s08",
        "_s03_timeline_old",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    self.foundation_shell.timeline.canvas.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "ai_agent"
    self.ai_conversations_s09.setVisible(active)
    self.ai_timeline_s09.setVisible(active)
    if not active:
        if self._inspector_router.currentWidget() is self.ai_context_s09:
            self._inspector_router.setCurrentIndex(1)
        return
    _hide_prior_surfaces(self)
    self._inspector_router.setCurrentWidget(self.ai_context_s09)
    self.foundation_shell.timeline.set_collapsed(False)
    self._s09_ensure_session()
    self._s09_refresh()


def _selected_song_ids(self) -> tuple[str, ...]:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    values: set[str] = set()
    album = getattr(self, "album_workspace", None)
    if album is not None:
        values.update(str(value) for value in album.selected_song_ids if str(value) in valid)
    if not values:
        values.update(str(value) for value in getattr(self, "_s06_selected_ids", set()) if str(value) in valid)
    if not values:
        one = str(getattr(self, "_s05_selected_song_id", "") or "")
        if one in valid:
            values.add(one)
    return tuple(song.song_id for song in document.playlist.entries if song.song_id in values)


def _selected_layer_ids(self) -> tuple[str, ...]:
    document = self.editor_workspace.document()
    valid = set(document.layer_map())
    return tuple(
        str(value)
        for value in self.editor_workspace.session.selected_layer_ids
        if str(value) in valid
    )


def _allowed_media_ids(self) -> tuple[str, ...]:
    # "Semua media" means all media already inside this project document only;
    # it never grants arbitrary filesystem access.
    return tuple(asset.asset_id for asset in self.editor_workspace.document().media)


def _build_context(self, prompt: str = ""):
    document = self.editor_workspace.document()
    return build_agent_context_snapshot(
        document,
        selected_song_ids=self._s09_selected_song_ids(),
        selected_layer_ids=self._s09_selected_layer_ids(),
        allowed_media_ids=self._s09_allowed_media_ids(),
        enabled_contexts=("media", "timeline", "visual", "template", "spectrum"),
        user_text=prompt,
        template_ids=(item.template_id for item in builtin_descriptors()),
    )


def _grant(self) -> PermissionGrant:
    return PermissionGrant(self.ai_context_s09.permission_values())


def _ensure_session(self) -> AgentSessionService:
    controller = self.editor_workspace.session.controller
    identity = id(controller)
    if self._s09_agent_session is None or self._s09_controller_identity != identity:
        if self._s09_async is not None:
            self._s09_async.close()
            self._s09_async = None
        self._s09_agent_session = AgentSessionService(
            controller,
            grant=self._s09_grant(),
            history_store=self._s09_history_store,
        )
        self._s09_controller_identity = identity
        self._s09_context_snapshot = None
        self.ai_context_s09.set_stale_warning("")
    else:
        self._s09_agent_session.grant = self._s09_grant()
    return self._s09_agent_session


def _make_provider(self):
    if self._s09_provider_id == "mock":
        return MockStep09Provider()
    pool = getattr(self, "pool", None)
    if pool is None:
        raise RuntimeError("Gemini belum dikonfigurasi pada aplikasi.")
    return GeminiStep09Provider(pool)


def _replace_async_provider(self) -> AsyncAgentProvider:
    if self._s09_async is not None:
        self._s09_async.close()
    bridge = AsyncAgentProvider(self._s09_make_provider(), workers=2, parent=self)
    bridge.result_ready.connect(self._s09_provider_result)
    bridge.request_failed.connect(self._s09_provider_failed)
    bridge.busy_changed.connect(self._s09_busy_changed)
    self._s09_async = bridge
    return bridge


def _refresh(self) -> None:
    if not hasattr(self, "ai_workspace_s09"):
        return
    session = self._s09_ensure_session()
    document = self.editor_workspace.document()
    selected = self._s09_selected_song_ids()
    allowed = self._s09_allowed_media_ids()
    self.ai_context_s09.set_context(
        project_name=document.name or document.album_title,
        song_count=len(selected),
        media_count=len(allowed),
    )
    self.ai_context_s09.set_provider(self._s09_provider_id, key_ready=_key_ready(self))
    chips = [
        "Project Aktif",
        f"{len(selected)} lagu dipilih" if selected else "Scope lagu: album aktif",
        "Semua media project",
        "Template AI",
    ]
    prompt_lower = self.ai_workspace_s09.prompt.toPlainText().casefold()
    if "slowmo" in prompt_lower or "0,5" in prompt_lower or "0.5" in prompt_lower:
        chips.append("Slowmo 0,5x")
    self.ai_workspace_s09.set_context_chips(chips)
    self.ai_workspace_s09.apply_session(session.snapshot(), can_undo_ai=session.can_undo_ai)
    self.ai_conversations_s09.apply_data(
        self._s09_history_store.load(),
        self._s09_saved_store.load(),
    )
    self.ai_timeline_s09.apply_document(
        document,
        self.editor_workspace.session.playhead_tick,
        ripple=bool(getattr(self, "_s05_ripple", False)),
        snap=self.editor_workspace.session.snap_enabled,
    )
    self.ai_timeline_s09.canvas.set_selection(
        song_id=(selected[0] if len(selected) == 1 else ""),
        layer_id=(self._s09_selected_layer_ids()[0] if len(self._s09_selected_layer_ids()) == 1 else ""),
    )
    self.foundation_shell.refresh_commands()


def _document_changed(self, _document) -> None:
    if not hasattr(self, "ai_workspace_s09"):
        return
    session = self._s09_agent_session
    if session is not None and self._s09_controller_identity == id(self.editor_workspace.session.controller):
        snapshot = session.snapshot()
        if snapshot.state in {AgentState.PLAN_READY, AgentState.PREVIEW_READY}:
            # Same controller changed revision manually after plan creation.
            self.ai_context_s09.set_stale_warning("⚠ Project berubah setelah plan dibuat. Kirim/Preview ulang sebelum Jalankan.")
    self._s09_refresh()


def _playback_sync(self) -> None:
    if self.foundation_state.workspace != "ai_agent":
        return
    self.ai_timeline_s09.canvas.set_playhead(self.editor_workspace.session.playhead_tick)


def _send(self, prompt: str) -> None:
    session = self._s09_ensure_session()
    try:
        context = self._s09_build_context(prompt)
        session.grant = self._s09_grant()
        session.begin_interpretation(prompt, context)
        self._s09_context_snapshot = context
        bridge = self._s09_replace_async_provider()
        self._s09_request_token = bridge.request(prompt, context)
        self.ai_context_s09.set_stale_warning("")
        self._s09_refresh()
    except Exception as exc:
        try:
            session.fail(str(exc))
        except Exception:
            pass
        self._s09_refresh()


def _provider_result(self, token: int, result) -> None:
    if int(token) != int(self._s09_request_token):
        return
    session = self._s09_ensure_session()
    try:
        session.receive_interpretation(result)
    except Exception as exc:
        session.fail(str(exc))
    self._s09_refresh()


def _provider_failed(self, token: int, error: str) -> None:
    if int(token) != int(self._s09_request_token):
        return
    self._s09_ensure_session().fail(str(error))
    self._s09_refresh()


def _busy_changed(self, busy: bool) -> None:
    self.foundation_state.set_status(
        ai=("AI Agent menafsirkan…", "warning") if busy else ("AI Agent siap", "success")
    )


def _preview(self) -> None:
    session = self._s09_ensure_session()
    try:
        session.grant = self._s09_grant()
        session.preview()
    except Exception as exc:
        session.fail(str(exc))
    self._s09_refresh()


def _execute(self) -> None:
    session = self._s09_ensure_session()
    if session.snapshot().state != AgentState.PREVIEW_READY:
        return
    answer = QMessageBox.question(
        self,
        "Jalankan AI Agent",
        "Terapkan seluruh plan sebagai satu transaction Undo?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    before_revision = self.editor_workspace.session.revision
    try:
        result = session.execute()
        if result.execution is not None and not result.execution.duplicate and self.editor_workspace.session.revision != before_revision:
            self.editor_workspace._after_edit()
    except Exception as exc:
        try:
            session.fail(str(exc))
        except Exception:
            pass
    self._s09_refresh()


def _cancel(self) -> None:
    if self._s09_async is not None:
        self._s09_async.cancel_current()
    session = self._s09_ensure_session()
    try:
        session.cancel()
    except Exception as exc:
        QMessageBox.information(self, "Batalkan AI", str(exc))
    self._s09_refresh()


def _undo_ai(self) -> None:
    session = self._s09_ensure_session()
    try:
        session.undo_ai()
        self.editor_workspace._after_edit()
    except Exception as exc:
        QMessageBox.warning(self, "Undo AI", str(exc))
    self._s09_refresh()


def _provider_changed(self, provider_id: str) -> None:
    value = str(provider_id or "gemini")
    if value not in {"gemini", "mock"}:
        return
    if value == self._s09_provider_id:
        return
    self._s09_provider_id = value
    if self._s09_async is not None:
        self._s09_async.cancel_current()
        self._s09_async.close()
        self._s09_async = None
    session = self._s09_ensure_session()
    if session.snapshot().state in {AgentState.INTERPRETING, AgentState.NEEDS_CLARIFICATION, AgentState.PLAN_READY, AgentState.PREVIEW_READY}:
        try:
            session.cancel()
        except Exception:
            pass
    self.ai_context_s09.set_stale_warning("Provider berubah. Plan lama dibatalkan; interpretasi harus dibuat ulang.")
    self._s09_refresh()


def _permissions_changed(self) -> None:
    session = self._s09_ensure_session()
    session.grant = self._s09_grant()
    if session.snapshot().state in {AgentState.PLAN_READY, AgentState.PREVIEW_READY}:
        try:
            session.cancel()
        except Exception:
            pass
        self.ai_context_s09.set_stale_warning("Permission berubah. Preview lama tidak lagi valid.")
    self._s09_refresh()


def _save_command(self, prompt: str) -> None:
    normalized = " ".join(str(prompt).split())
    if not normalized:
        return
    command = SavedAgentCommand(
        command_id=str(uuid4()),
        name=(normalized[:52] + "…") if len(normalized) > 52 else normalized,
        prompt=normalized,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    try:
        self._s09_saved_store.upsert(command)
    except OSError as exc:
        QMessageBox.warning(self, "Simpan Perintah", f"Perintah tidak dapat disimpan:\n{exc}")
    self._s09_refresh()


def _replay_saved(self, prompt: str) -> None:
    # Replaying only fills the composer; Send rebuilds a new plan/context and
    # never reuses stale IDs from an old execution.
    self.ai_workspace_s09.set_prompt(prompt)
    self.ai_context_s09.set_stale_warning("Perintah tersimpan dimuat. Tekan Kirim untuk membuat plan baru pada context saat ini.")


def _new_conversation(self) -> None:
    if self._s09_async is not None:
        self._s09_async.cancel_current()
    self._s09_agent_session = AgentSessionService(
        self.editor_workspace.session.controller,
        grant=self._s09_grant(),
        history_store=self._s09_history_store,
    )
    self._s09_controller_identity = id(self.editor_workspace.session.controller)
    self._s09_context_snapshot = None
    self.ai_workspace_s09.set_prompt("")
    self.ai_context_s09.set_stale_warning("")
    self._s09_refresh()


def _attachment_info(self) -> None:
    QMessageBox.information(
        self,
        "Lampiran Context",
        "STEP09 hanya menerima object context yang sudah ada di project (lagu/media/layer/template). Path filesystem bebas tidak diteruskan ke provider.",
    )


def install_step09_ai_agent() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s09_ensure_session()
        self._s09_refresh()
        self._s09_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s09_route(route)

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s09_key_ready = _key_ready
    Window._s09_initial_provider = _initial_provider
    Window._s09_selected_song_ids = _selected_song_ids
    Window._s09_selected_layer_ids = _selected_layer_ids
    Window._s09_allowed_media_ids = _allowed_media_ids
    Window._s09_build_context = _build_context
    Window._s09_grant = _grant
    Window._s09_ensure_session = _ensure_session
    Window._s09_make_provider = _make_provider
    Window._s09_replace_async_provider = _replace_async_provider
    Window._s09_refresh = _refresh
    Window._s09_route = _route
    Window._s09_document_changed = _document_changed
    Window._s09_playback_sync = _playback_sync
    Window._s09_send = _send
    Window._s09_provider_result = _provider_result
    Window._s09_provider_failed = _provider_failed
    Window._s09_busy_changed = _busy_changed
    Window._s09_preview = _preview
    Window._s09_execute = _execute
    Window._s09_cancel = _cancel
    Window._s09_undo_ai = _undo_ai
    Window._s09_provider_changed = _provider_changed
    Window._s09_permissions_changed = _permissions_changed
    Window._s09_save_command = _save_command
    Window._s09_replay_saved = _replay_saved
    Window._s09_new_conversation = _new_conversation
    Window._s09_attachment_info = _attachment_info
    _installed = True
