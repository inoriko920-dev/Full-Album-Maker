from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QFrame, QHBoxLayout, QMessageBox

from .foundation_components import FAMButton
from .paths import output_dir
from .render_async_step10 import RenderAsyncBridge
from .render_center_model_step10 import RenderJob, RenderJobState
from .render_executor_step10 import sanitize_render_log
from .render_performance_step10 import RenderPerformanceGraph
from .render_queue_step10 import RenderQueue
from .render_workspace_step10 import RenderCenterWorkspace, RenderHistoryContext, RenderSettingsInspector


_installed = False
_original_init: Any = None

_TERMINAL = {
    RenderJobState.COMPLETED,
    RenderJobState.FAILED,
    RenderJobState.CANCELLED,
    RenderJobState.BLOCKED,
    RenderJobState.INTERRUPTED,
}
_ACTIVE = {
    RenderJobState.PREFLIGHTING,
    RenderJobState.STARTING,
    RenderJobState.RUNNING,
    RenderJobState.PAUSED,
    RenderJobState.FINALIZING,
}


def safe_job_log_text(job: RenderJob | None) -> str:
    if job is None:
        return ""
    values: list[str] = []
    for line in job.log_lines[-500:]:
        safe = sanitize_render_log(str(line))
        if safe:
            values.append(safe)
    if job.error_message:
        safe = sanitize_render_log(job.error_message)
        if safe and safe not in values:
            values.append(safe)
    return "\n".join(values)


def verified_output_path(job: RenderJob | None) -> Path | None:
    if job is None or job.state != RenderJobState.COMPLETED or not job.verified_output:
        return None
    path = Path(job.verified_output)
    return path if path.is_file() and path.stat().st_size > 0 else None


def _install_widgets(self) -> None:
    self._s10_queue = RenderQueue()
    self._s10_async = RenderAsyncBridge(parent=self)
    self._s10_preflight_token = 0
    self._s10_preflight_report = None
    self._s10_preflight_capability = None
    self._s10_preflight_settings_signature = ""
    self._s10_pending_retry: RenderJob | None = None
    self._s10_selected_key: tuple[str, str] | None = None
    self._s10_last_persisted_percent: dict[tuple[str, str], float] = {}

    self.render_workspace_s10 = RenderCenterWorkspace()
    index = self.foundation_shell.workspace_stack._index["render"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.render_workspace_s10)

    # Render route intentionally has context width 0 in the shared shell, but we
    # keep the history surface attached so route/compact changes retain one owner.
    context_layout = self.foundation_shell.context.layout()
    self.render_history_s10 = RenderHistoryContext()
    self.render_history_s10.hide()
    context_layout.addWidget(self.render_history_s10, 1)

    self.render_inspector_s10 = RenderSettingsInspector()
    self._inspector_router.addWidget(self.render_inspector_s10)
    if not self.render_inspector_s10.output_folder.text().strip():
        self.render_inspector_s10.set_output_folder(str(output_dir()))

    self.render_performance_s10 = RenderPerformanceGraph()
    center_layout = self.render_workspace_s10.layout()
    center_layout.insertWidget(max(0, center_layout.count() - 1), self.render_performance_s10)

    actions = QFrame()
    actions.setObjectName("renderCompletionActions")
    row = QHBoxLayout(actions)
    row.setContentsMargins(0, 2, 0, 0)
    row.setSpacing(6)
    self.render_add_queue_s10 = FAMButton("Tambah ke Antrian", kind="secondary")
    self.render_copy_log_s10 = FAMButton("Salin Log", kind="ghost")
    self.render_open_output_s10 = FAMButton("Buka Output", kind="ghost")
    row.addWidget(self.render_add_queue_s10)
    row.addWidget(self.render_copy_log_s10)
    row.addWidget(self.render_open_output_s10)
    inspector_layout = self.render_inspector_s10.layout()
    inspector_layout.insertWidget(max(0, inspector_layout.count() - 1), actions)


def _connect_widgets(self) -> None:
    inspector = self.render_inspector_s10
    inspector.settings_changed.connect(self._s10_settings_changed)
    inspector.browse_requested.connect(self._s10_browse_output)
    inspector.preflight_requested.connect(self._s10_request_preflight)
    inspector.start_requested.connect(self._s10_render_now)
    inspector.cancel_requested.connect(self._s10_cancel)
    self.render_add_queue_s10.clicked.connect(self._s10_add_queue)
    self.render_copy_log_s10.clicked.connect(self._s10_copy_log)
    self.render_open_output_s10.clicked.connect(self._s10_open_output)
    self.render_history_s10.retry_requested.connect(self._s10_retry)
    self.render_history_s10.job_selected.connect(self._s10_select_job)

    bridge = self._s10_async
    bridge.preflight_ready.connect(self._s10_preflight_ready)
    bridge.preflight_failed.connect(self._s10_preflight_failed)
    bridge.render_started.connect(self._s10_render_started)
    bridge.metrics_ready.connect(self._s10_metrics_ready)
    bridge.log_ready.connect(self._s10_log_ready)
    bridge.render_finished.connect(self._s10_render_finished)
    bridge.render_failed.connect(self._s10_render_failed)
    bridge.busy_changed.connect(self._s10_busy_changed)

    self.foundation_state.workspace_changed.connect(self._s10_route)
    self.editor_workspace.documentChanged.connect(self._s10_document_changed)


def _hide_prior_surfaces(self) -> None:
    for name in (
        "media_context",
        "album_context",
        "timeline_context_s05",
        "visual_context_s06",
        "template_context_s07",
        "spectrum_context_s08",
        "ai_conversations_s09",
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
        "ai_timeline_s09",
        "_s03_timeline_old",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    self.foundation_shell.timeline.canvas.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "render"
    self.render_history_s10.setVisible(active)
    if not active:
        if self._inspector_router.currentWidget() is self.render_inspector_s10:
            self._inspector_router.setCurrentIndex(1)
        return
    _hide_prior_surfaces(self)
    self._inspector_router.setCurrentWidget(self.render_inspector_s10)
    # Foundation route contract collapses the timeline for Render Center.
    self.foundation_shell.timeline.set_collapsed(True)
    self._s10_refresh()
    self._s10_pump_queue()


def _document_changed(self, _document) -> None:
    self._s10_invalidate_preflight("Project berubah — jalankan Preflight lagi.")
    if self.foundation_state.workspace == "render":
        self._s10_refresh()


def _settings_changed(self) -> None:
    self._s10_invalidate_preflight("Pengaturan berubah — jalankan Preflight lagi.")


def _invalidate_preflight(self, message: str) -> None:
    if not hasattr(self, "_s10_async"):
        return
    self._s10_async.invalidate_preflight()
    self._s10_preflight_report = None
    self._s10_preflight_capability = None
    self._s10_preflight_settings_signature = ""
    self._s10_pending_retry = None
    self.render_workspace_s10.clear_preflight(message)
    self.render_inspector_s10.set_preflight_ready(False, message)
    self._s10_update_action_state()


def _browse_output(self) -> None:
    start = self.render_inspector_s10.output_folder.text().strip() or str(output_dir())
    selected = QFileDialog.getExistingDirectory(self, "Pilih Folder Output Render", start)
    if selected:
        self.render_inspector_s10.set_output_folder(selected)


def _request_preflight(self) -> None:
    try:
        settings = self.render_inspector_s10.settings()
    except Exception as exc:
        self.render_inspector_s10.set_preflight_ready(False, str(exc))
        return
    self._s10_pending_retry = None
    self.render_inspector_s10.set_preflight_ready(False, "Menjalankan preflight…")
    self._s10_preflight_token = self._s10_async.request_preflight(
        self.editor_workspace.document(), settings
    )


def _preflight_still_valid(self) -> bool:
    report = self._s10_preflight_report
    if report is None or report.blocked or report.snapshot is None:
        return False
    try:
        settings = self.render_inspector_s10.settings()
    except Exception:
        return False
    if settings.signature() != self._s10_preflight_settings_signature:
        return False
    current = self.editor_workspace.document()
    return current.content_signature() == report.snapshot.content_signature


def _preflight_ready(self, token: int, report, capability) -> None:
    if int(token) != int(self._s10_preflight_token):
        return
    retry = self._s10_pending_retry
    if retry is not None:
        self._s10_pending_retry = None
        try:
            retry.transition(RenderJobState.PREFLIGHTING)
            if report.blocked or report.snapshot is None:
                retry.error_code = "PREFLIGHT_BLOCKED"
                retry.error_message = "; ".join(
                    check.message for check in report.checks if check.level.value == "BLOCK"
                )
                retry.transition(RenderJobState.BLOCKED)
                self._s10_queue.update(retry)
            else:
                retry.transition(RenderJobState.READY)
                self._s10_queue.enqueue(retry)
        except Exception as exc:
            QMessageBox.warning(self, "Retry Render", str(exc))
        self.render_workspace_s10.apply_preflight(report)
        self._s10_refresh()
        self._s10_pump_queue()
        return

    self._s10_preflight_report = report
    self._s10_preflight_capability = capability
    self._s10_preflight_settings_signature = report.settings_signature
    self.render_workspace_s10.apply_preflight(report)
    ready = bool(report.ready and not report.blocked)
    warning_text = " • ".join(check.message for check in report.warnings)
    self.render_inspector_s10.set_preflight_ready(
        ready and not self._s10_async.busy,
        warning_text if warning_text else ("Preflight siap." if ready else "Preflight BLOCK."),
    )
    if capability is not None:
        self.foundation_state.set_status(
            ffmpeg=("FFmpeg Siap", "success")
        )
    self._s10_update_action_state()


def _preflight_failed(self, token: int, error: str) -> None:
    if int(token) != int(self._s10_preflight_token):
        return
    retry = self._s10_pending_retry
    self._s10_pending_retry = None
    if retry is not None:
        try:
            retry.transition(RenderJobState.PREFLIGHTING)
            retry.error_code = "PREFLIGHT_FAILED"
            retry.error_message = sanitize_render_log(error)
            retry.transition(RenderJobState.BLOCKED)
            self._s10_queue.update(retry)
        except Exception:
            pass
    self.render_inspector_s10.set_preflight_ready(False, f"Preflight gagal: {error}")
    self._s10_refresh()


def _job_from_current_preflight(self) -> RenderJob:
    if not self._s10_preflight_still_valid():
        raise ValueError("Preflight sudah stale; jalankan ulang sebelum membuat RenderJob.")
    report = self._s10_preflight_report
    assert report is not None and report.snapshot is not None
    settings = self.render_inspector_s10.settings()
    final = settings.final_output.resolve(strict=False)
    for item in self._s10_queue.jobs:
        if item.state in _TERMINAL:
            continue
        if item.settings.final_output.resolve(strict=False) == final:
            raise ValueError("Sudah ada job aktif/antrian dengan output final yang sama.")
    return RenderJob(report.snapshot, settings)


def _render_now(self) -> None:
    try:
        job = self._s10_job_from_current_preflight()
    except Exception as exc:
        QMessageBox.warning(self, "Render Now", str(exc))
        return
    self._s10_queue.update(job)
    self._s10_selected_key = (job.job_id, job.attempt_id)
    if not self._s10_async.start(job):
        QMessageBox.information(self, "Render", "Renderer sedang sibuk. Gunakan Tambah ke Antrian.")
        return
    self.render_performance_s10.clear()
    self._s10_refresh()


def _add_queue(self) -> None:
    try:
        job = self._s10_job_from_current_preflight()
        job.transition(RenderJobState.PREFLIGHTING)
        job.transition(RenderJobState.READY)
        self._s10_queue.enqueue(job)
    except Exception as exc:
        QMessageBox.warning(self, "Tambah ke Antrian", str(exc))
        return
    self._s10_selected_key = (job.job_id, job.attempt_id)
    self._s10_refresh()
    self._s10_pump_queue()


def _pump_queue(self) -> None:
    if self._s10_async.busy:
        return
    job = self._s10_queue.next_queued()
    if job is None:
        return
    self._s10_selected_key = (job.job_id, job.attempt_id)
    if self._s10_async.start(job):
        self.render_performance_s10.clear()
        self._s10_refresh()


def _find_job(self, job_id: str, attempt_id: str) -> RenderJob | None:
    return next(
        (
            job for job in self._s10_queue.jobs
            if job.job_id == str(job_id) and job.attempt_id == str(attempt_id)
        ),
        None,
    )


def _selected_job(self) -> RenderJob | None:
    if self._s10_selected_key is not None:
        job = self._s10_find_job(*self._s10_selected_key)
        if job is not None:
            return job
    active = next((job for job in reversed(self._s10_queue.jobs) if job.state in _ACTIVE), None)
    return active or (self._s10_queue.jobs[-1] if self._s10_queue.jobs else None)


def _select_job(self, job_id: str, attempt_id: str) -> None:
    if self._s10_find_job(job_id, attempt_id) is not None:
        self._s10_selected_key = (str(job_id), str(attempt_id))
        self._s10_refresh()


def _retry(self, job_id: str, attempt_id: str) -> None:
    try:
        retry = self._s10_queue.retry(job_id, attempt_id)
    except Exception as exc:
        QMessageBox.warning(self, "Coba Lagi", str(exc))
        return
    self._s10_selected_key = (retry.job_id, retry.attempt_id)
    self._s10_pending_retry = retry
    self._s10_preflight_token = self._s10_async.request_preflight(
        retry.snapshot.document(), retry.settings
    )
    self.render_workspace_s10.clear_preflight("Retry: critical preflight dijalankan ulang…")
    self._s10_refresh()


def _render_started(self, job_id: str, attempt_id: str) -> None:
    job = self._s10_find_job(job_id, attempt_id)
    if job is None:
        return
    self._s10_selected_key = (job.job_id, job.attempt_id)
    self.render_workspace_s10.apply_job(job)
    self.foundation_state.set_status(jobs=("Jobs: render aktif", "warning"))

    # Executor mutates the shared RenderJob on its worker. Persist shortly after
    # start so crash recovery sees PREFLIGHTING/RUNNING instead of stale DRAFT.
    QTimer.singleShot(150, lambda: self._s10_persist_active(job.job_id, job.attempt_id))


def _persist_active(self, job_id: str, attempt_id: str) -> None:
    job = self._s10_find_job(job_id, attempt_id)
    if job is not None and job.state in _ACTIVE:
        self._s10_queue.update(job)
        self._s10_refresh()


def _metrics_ready(self, job_id: str, attempt_id: str, metrics) -> None:
    job = self._s10_find_job(job_id, attempt_id)
    if job is None:
        return
    job.metrics = metrics
    self.render_workspace_s10.apply_job(job)
    self.render_performance_s10.append_metrics(metrics)
    key = (job.job_id, job.attempt_id)
    previous = self._s10_last_persisted_percent.get(key, -10.0)
    if metrics.percent >= 100.0 or metrics.percent - previous >= 5.0:
        self._s10_last_persisted_percent[key] = metrics.percent
        self._s10_queue.update(job)
    self._s10_update_status()


def _log_ready(self, job_id: str, attempt_id: str, line: str) -> None:
    if self._s10_find_job(job_id, attempt_id) is not None:
        self.render_workspace_s10.append_log(sanitize_render_log(line))


def _render_finished(self, job_id: str, attempt_id: str, _result) -> None:
    job = self._s10_find_job(job_id, attempt_id)
    if job is None:
        return
    self._s10_queue.update(job)
    self._s10_selected_key = (job.job_id, job.attempt_id)
    self._s10_refresh()
    QTimer.singleShot(0, self._s10_pump_queue)


def _render_failed(self, job_id: str, attempt_id: str, code: str, message: str) -> None:
    job = self._s10_find_job(job_id, attempt_id)
    if job is not None:
        if not job.error_code:
            job.error_code = sanitize_render_log(code, max_length=100)
        if not job.error_message:
            job.error_message = sanitize_render_log(message)
        self._s10_queue.update(job)
        self._s10_selected_key = (job.job_id, job.attempt_id)
    self._s10_refresh()
    QTimer.singleShot(0, self._s10_pump_queue)


def _busy_changed(self, busy: bool) -> None:
    self.render_inspector_s10.set_busy(bool(busy))
    self._s10_update_action_state()
    self._s10_update_status()


def _cancel(self) -> None:
    if not self._s10_async.cancel():
        QMessageBox.information(self, "Batalkan Render", "Tidak ada render aktif yang dapat dibatalkan.")


def _copy_log(self) -> None:
    text = safe_job_log_text(self._s10_selected_job())
    if not text:
        return
    clipboard = QApplication.clipboard()
    clipboard.setText(text)


def _open_output(self) -> None:
    path = verified_output_path(self._s10_selected_job())
    if path is None:
        QMessageBox.information(self, "Buka Output", "Output VERIFIED belum tersedia.")
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _update_action_state(self) -> None:
    valid = self._s10_preflight_still_valid()
    busy = self._s10_async.busy
    self.render_add_queue_s10.setEnabled(valid)
    # RenderSettingsInspector.set_busy() is intentionally conservative; restore
    # the correct start state whenever busy/preflight changes.
    message = self.render_inspector_s10.warning.text()
    self.render_inspector_s10.set_preflight_ready(valid and not busy, message)
    selected = self._s10_selected_job()
    self.render_copy_log_s10.setEnabled(bool(safe_job_log_text(selected)))
    self.render_open_output_s10.setEnabled(verified_output_path(selected) is not None)


def _update_status(self) -> None:
    queued = sum(1 for job in self._s10_queue.jobs if job.state == RenderJobState.QUEUED)
    active = sum(1 for job in self._s10_queue.jobs if job.state in _ACTIVE)
    count = queued + active
    state = "warning" if active else ("neutral" if count == 0 else "warning")
    self.foundation_state.set_status(jobs=(f"Jobs: {count}", state))


def _refresh(self) -> None:
    if not hasattr(self, "render_workspace_s10"):
        return
    jobs = tuple(self._s10_queue.jobs)
    self.render_history_s10.apply_jobs(jobs)
    self.render_workspace_s10.apply_queue(jobs)
    selected = self._s10_selected_job()
    self.render_workspace_s10.apply_job(selected)
    if selected is not None:
        self.render_workspace_s10.log_list.clear()
        for line in selected.log_lines[-150:]:
            self.render_workspace_s10.append_log(sanitize_render_log(line))
    self._s10_update_action_state()
    self._s10_update_status()
    self.foundation_shell.refresh_commands()


def install_step10_render() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s10_refresh()
        self._s10_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s10_route(route)

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s10_route = _route
    Window._s10_document_changed = _document_changed
    Window._s10_settings_changed = _settings_changed
    Window._s10_invalidate_preflight = _invalidate_preflight
    Window._s10_browse_output = _browse_output
    Window._s10_request_preflight = _request_preflight
    Window._s10_preflight_still_valid = _preflight_still_valid
    Window._s10_preflight_ready = _preflight_ready
    Window._s10_preflight_failed = _preflight_failed
    Window._s10_job_from_current_preflight = _job_from_current_preflight
    Window._s10_render_now = _render_now
    Window._s10_add_queue = _add_queue
    Window._s10_pump_queue = _pump_queue
    Window._s10_find_job = _find_job
    Window._s10_selected_job = _selected_job
    Window._s10_select_job = _select_job
    Window._s10_retry = _retry
    Window._s10_render_started = _render_started
    Window._s10_persist_active = _persist_active
    Window._s10_metrics_ready = _metrics_ready
    Window._s10_log_ready = _log_ready
    Window._s10_render_finished = _render_finished
    Window._s10_render_failed = _render_failed
    Window._s10_busy_changed = _busy_changed
    Window._s10_cancel = _cancel
    Window._s10_copy_log = _copy_log
    Window._s10_open_output = _open_output
    Window._s10_update_action_state = _update_action_state
    Window._s10_update_status = _update_status
    Window._s10_refresh = _refresh
    _installed = True
