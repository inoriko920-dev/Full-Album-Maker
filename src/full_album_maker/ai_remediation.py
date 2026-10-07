from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .ai_history_step09 import AgentHistoryEntry, SavedAgentCommand
from .ai_workspace_step09 import AIContextDock, AIConversationPanel, AITaskCanvas, _PlanCard, _section
from .editor_models import TIMEBASE
from .foundation_components import FAMButton, FAMCard
from .foundation_tokens import TOKENS
from .timeline_resolver import TimelineResolver

_installed = False
_originals: dict[str, Any] = {}


def _conversation_init(self, *args, **kwargs) -> None:
    _originals["conversation_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(8, 7, 8, 7)
    root.setSpacing(6)

    header = root.itemAt(0).layout() if root.count() else None
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if isinstance(widget, QLabel) and widget.text() == "Percakapan":
                widget.setText("AI Agent")
        header.removeWidget(self.new_button)
        root.insertWidget(1, self.new_button)

    self.new_button.setText("＋  Percakapan Baru")
    self.new_button.setMinimumHeight(33)
    self.new_button.setMaximumHeight(36)
    self.today.setMaximumHeight(158)
    self.yesterday.setMaximumHeight(92)
    self.saved.setMinimumHeight(116)
    self.saved.setMaximumHeight(175)
    list_style = (
        "QListWidget{border:0;background:#FFFFFF;}"
        "QListWidget::item{padding:6px 5px;border-bottom:1px solid #E8EEF6;}"
        "QListWidget::item:selected{background:#E7F1FF;color:#163E73;border-radius:5px;}"
    )
    self.today.setStyleSheet(list_style)
    self.yesterday.setStyleSheet(list_style)
    self.saved.setStyleSheet(list_style)
    self.privacy.setText("Riwayat aman • secret/path disanitasi")


def _conversation_apply_data(
    self,
    history: Iterable[AgentHistoryEntry],
    saved: Iterable[SavedAgentCommand],
) -> None:
    self.today.clear()
    self.yesterday.clear()
    self.saved.clear()

    now = datetime.now(timezone.utc).date()
    # The golden shows conversation/session summaries, not every internal system
    # event. Keep user instructions as the readable history surface while the
    # complete sanitized audit history remains in the STEP09 store.
    user_rows = [entry for entry in history if entry.role == "user"]
    for entry in reversed(tuple(user_rows)):
        try:
            stamp = datetime.fromisoformat(entry.timestamp)
            day = stamp.date()
            time_text = stamp.strftime("%H:%M")
        except Exception:
            day = now
            time_text = ""
        title = " ".join(entry.text.split())
        short = title[:58] + ("…" if len(title) > 58 else "")
        status = entry.status.replace("_", " ").title() if entry.status else "Instruksi"
        item = QListWidgetItem(f"{short}    {time_text}\n{status}")
        item.setToolTip(entry.text)
        target = self.today if day == now else self.yesterday
        if target.count() < 6:
            target.addItem(item)

    if self.today.count() == 0:
        self.today.addItem(QListWidgetItem("Belum ada percakapan hari ini"))
    if self.yesterday.count() == 0:
        self.yesterday.addItem(QListWidgetItem("Tidak ada item lama"))

    for command in reversed(tuple(saved)):
        item = QListWidgetItem(f"◆  {command.name}\n    {command.prompt[:58]}")
        item.setToolTip(command.prompt)
        item.setData(Qt.ItemDataRole.UserRole, command.prompt)
        self.saved.addItem(item)
    if self.saved.count() == 0:
        self.saved.addItem(QListWidgetItem("Belum ada perintah tersimpan"))


def _plan_card_init(self, *args, **kwargs) -> None:
    _originals["plan_card_init"](self, *args, **kwargs)
    self.setMinimumHeight(56)
    self.setMaximumHeight(76)
    row = self.layout()
    row.setContentsMargins(8, 5, 8, 5)
    row.setSpacing(7)


def _task_init(self, *args, **kwargs) -> None:
    _originals["task_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(9, 7, 9, 7)
    root.setSpacing(6)

    # Golden does not repeat a large workspace title/state chip above the
    # conversation flow. The shell/navigation already owns workspace identity.
    top = root.itemAt(0).layout() if root.count() else None
    if top is not None:
        for index in range(top.count()):
            widget = top.itemAt(index).widget()
            if widget is not None:
                widget.hide()

    self.scroll.setStyleSheet("QScrollArea{border:0;background:#F7FAFE;}")
    self.body_layout.setSpacing(6)

    self.user_card.setStyleSheet(
        "QFrame#famCard{background:#FFFFFF;border:1px solid #D8E4F1;border-radius:8px;}"
    )
    self.ai_card.setStyleSheet(
        "QFrame#famCard{background:#F8FBFF;border:1px solid #D5E3F3;border-radius:8px;}"
    )

    # Recompose the plan section into the reference's two-column hierarchy:
    # Interpretasi Tugas on the left; Scope + Impact on the right.
    self.body_layout.removeWidget(self.plan_host)
    self.body_layout.removeWidget(self.scope_card)
    self.body_layout.removeWidget(self.impact_card)

    split = QWidget(self.body)
    split_layout = QHBoxLayout(split)
    split_layout.setContentsMargins(0, 0, 0, 0)
    split_layout.setSpacing(7)

    left_card = FAMCard()
    left_layout = QVBoxLayout(left_card)
    left_layout.setContentsMargins(8, 6, 8, 6)
    left_layout.setSpacing(5)
    left_layout.addWidget(_section("Interpretasi Tugas"))
    left_layout.addWidget(self.plan_host, 1)

    right_host = QWidget()
    right_layout = QVBoxLayout(right_host)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(6)
    right_layout.addWidget(self.scope_card)
    right_layout.addWidget(self.impact_card)
    right_layout.addStretch(1)

    self.scope_card.setStyleSheet(
        "QFrame#famCard{background:#F5F9FF;border:1px solid #D8E5F4;border-radius:8px;}"
    )
    self.impact_card.setStyleSheet(
        "QFrame#famCard{background:#F1FBF5;border:1px solid #CDEBD9;border-radius:8px;}"
    )

    split_layout.addWidget(left_card, 3)
    split_layout.addWidget(right_host, 2)
    self.body_layout.insertWidget(2, split)
    self.ui08_plan_split = split
    self.ui08_interpretation_card = left_card

    self.preview_button.setText("▷  Preview Perubahan")
    self.execute_button.setText("▶  Jalankan")
    self.cancel_button.setText("✕  Batalkan")
    self.undo_button.setText("↶  Undo AI")
    self.prompt.setMaximumHeight(58)
    self.attach_button.setText("＋")
    self.attach_button.setMaximumWidth(38)
    self.save_button.setText("Simpan")
    self.send_button.setText("➤  Kirim")

    composer = root.itemAt(root.count() - 1).widget()
    if composer is not None:
        composer.setMaximumHeight(118)
        self.ui08_composer = composer


def _context_init(self, *args, **kwargs) -> None:
    _originals["context_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(10, 7, 10, 8)
    root.setSpacing(6)

    # Permission switches stay functional but start collapsed like the approved
    # UI. Nothing about the PermissionGrant contract is changed.
    permission_heading = None
    safety_label = None
    for label in self.findChildren(QLabel):
        if label.text() == "Permission":
            permission_heading = label
        if label.text().startswith("• AI hanya membuat"):
            safety_label = label

    if permission_heading is not None:
        permission_heading.hide()
        self.ui08_permission_heading = permission_heading
    for check in self.permissions.values():
        check.hide()

    toggle = FAMButton("Kelola Izin", kind="ghost")
    toggle.setToolTip("Buka/tutup kontrol permission STEP09. Nilai permission tetap sama saat panel ditutup.")
    toggle.clicked.connect(lambda: _toggle_permissions(self))
    # Put the permission control immediately before the security heading where
    # possible; appending here is deterministic and keeps it accessible.
    root.insertWidget(max(0, root.count() - 3), toggle)
    self.ui08_permission_toggle = toggle
    self.ui08_permissions_open = False

    if safety_label is not None:
        safety_label.setStyleSheet(
            "QLabel{background:#FFF7DD;border:1px solid #F1D88C;border-radius:7px;padding:8px;color:#704F00;}"
        )
        safety_label.setText(
            "AI tidak menebak atau mengambil media di luar project. "
            "Preview Perubahan tidak memutasi project dan API key tidak pernah ditampilkan."
        )


def _toggle_permissions(dock: AIContextDock) -> None:
    opened = not bool(getattr(dock, "ui08_permissions_open", False))
    dock.ui08_permissions_open = opened
    heading = getattr(dock, "ui08_permission_heading", None)
    if heading is not None:
        heading.setVisible(opened)
    for check in dock.permissions.values():
        check.setVisible(opened)
    dock.ui08_permission_toggle.setText("Tutup Izin" if opened else "Kelola Izin")


def _context_set(self, *, project_name: str, song_count: int, media_count: int) -> None:
    _originals["context_set"](self, project_name=project_name, song_count=song_count, media_count=media_count)
    self.project.setText(f"◉  Project Aktif\n    {project_name or 'Untitled'}")
    self.songs.setText(f"♫  Lagu yang Dipilih\n    {int(song_count)} lagu")
    self.media.setText(f"▣  Media yang Boleh Dipakai\n    Semua media project • {int(media_count)} item")


def _context_provider(self, provider_id: str, *, key_ready: bool) -> None:
    _originals["context_provider"](self, provider_id, key_ready=key_ready)
    if provider_id == "mock":
        self.key_status.setText("●  Status Key: Test / offline")
    else:
        self.key_status.setText("●  Status Key: Aktif" if key_ready else "●  Status Key: Tidak Ada")
    self.key_status.setStyleSheet(
        "QLabel{color:#168A4A;font-weight:600;}" if (provider_id == "mock" or key_ready)
        else "QLabel{color:#A65B00;font-weight:600;}"
    )


class AIPlanTimelineCanvas(QWidget):
    """Read-only visualization of the current project + proposed AI plan.

    It never dispatches commands and never mutates ProjectDocument. At
    PREVIEW_READY, the blue video lane represents proposed set_song_visual
    actions while the green audio lane remains the live playlist.
    """

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self.setMinimumHeight(112)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        document = self.window.editor_workspace.document()
        resolved = TimelineResolver().resolve(document)
        left = 96
        ruler = 20
        row_h = max(28.0, (self.height() - ruler) / 3.0)
        duration = max(TIMEBASE, resolved.duration_tick)
        pps = max(0.01, max(160, self.width() - left - 8) / (duration / TIMEBASE))

        painter.fillRect(QRectF(0, 0, left, self.height()), QColor("#F8FBFF"))
        painter.setPen(QPen(QColor("#D8E3F0"), 1))
        painter.drawLine(left, 0, left, self.height())
        for row in range(4):
            y = ruler + row * row_h
            painter.drawLine(0, int(y), self.width(), int(y))

        labels = ("▣  Video", "♫  Audio", "T  Teks")
        for index, label in enumerate(labels):
            painter.setPen(QColor("#31465E"))
            painter.drawText(
                QRectF(9, ruler + index * row_h, left - 15, row_h),
                Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        duration_s = max(1, int(round(duration / TIMEBASE)))
        major = 60 if duration_s > 300 else 30
        for second in range(0, duration_s + major, major):
            x = left + second * pps
            if x > self.width():
                break
            painter.setPen(QColor("#8291A5"))
            painter.drawText(
                QRectF(x + 2, 1, 58, 16),
                Qt.AlignmentFlag.AlignLeft,
                f"{second // 60:02d}:{second % 60:02d}",
            )

        session = getattr(self.window, "_s09_agent_session", None)
        snapshot = session.snapshot() if session is not None else None
        plan = getattr(snapshot, "plan", None)
        proposed_visual: set[str] = set()
        if plan is not None:
            for action in plan.actions:
                if action.name == "set_song_visual":
                    proposed_visual.update(str(v) for v in action.args.get("song_ids", ()))

        song_map = document.song_map()
        for event in resolved.songs:
            x = left + (event.start_tick / TIMEBASE) * pps
            width = max(4.0, ((event.end_tick - event.start_tick) / TIMEBASE) * pps)
            title = song_map[event.song_id].display_title or "Lagu"
            short = title[:15]

            video_rect = QRectF(x + 1, ruler + 3, max(3, width - 2), row_h - 6)
            if event.song_id in proposed_visual:
                painter.setPen(QPen(QColor("#4585D0"), 1))
                painter.setBrush(QColor("#DCEBFF"))
                painter.drawRoundedRect(video_rect, 3, 3)
                painter.setPen(QColor("#245B99"))
                painter.drawText(video_rect.adjusted(4, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter, short)
            else:
                painter.setPen(QPen(QColor("#CAD5E1"), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QColor("#F7F9FC"))
                painter.drawRoundedRect(video_rect, 3, 3)

            audio_rect = QRectF(x + 1, ruler + row_h + 3, max(3, width - 2), row_h - 6)
            painter.setPen(QPen(QColor("#55AA8B"), 1))
            painter.setBrush(QColor("#D8F4E8"))
            painter.drawRoundedRect(audio_rect, 3, 3)
            painter.setPen(QColor("#2B715D"))
            painter.drawText(audio_rect.adjusted(4, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter, short)

        # Presentation-only text regions matching the approved three-lane layout.
        text_y = ruler + row_h * 2 + 3
        segments = (
            (0.00, 0.34, "Judul Album"),
            (0.34, 0.82, "Lirik Berjalan"),
            (0.82, 1.00, "Credit"),
        )
        usable = max(1.0, self.width() - left - 8)
        for start, end, label in segments:
            rect = QRectF(left + start * usable + 1, text_y, max(3, (end - start) * usable - 2), row_h - 6)
            painter.setPen(QPen(QColor("#9675D0"), 1))
            painter.setBrush(QColor("#E8DCF9"))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(QColor("#684A98"))
            painter.drawText(rect.adjusted(5, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, label)

        playhead = self.window.editor_workspace.session.playhead_tick
        play_x = left + (playhead / TIMEBASE) * pps
        painter.setPen(QPen(QColor("#1769E0"), 2))
        painter.drawLine(int(play_x), 0, int(play_x), self.height())
        painter.end()


def _ensure_timeline_panel(window) -> None:
    if hasattr(window, "_ui08_timeline_panel"):
        return
    host = window.foundation_shell.timeline
    panel = QFrame()
    panel.setObjectName("ui08AITimelinePanel")
    root = QVBoxLayout(panel)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar = QHBoxLayout(toolbar_widget)
    toolbar.setContentsMargins(8, 3, 8, 3)
    toolbar.setSpacing(7)
    title = QLabel("⌃  Timeline")
    title.setObjectName("sectionHeading")
    toolbar.addWidget(title)
    toolbar.addWidget(QLabel("▣  Daftar Scene"))
    split = FAMButton("✂  Split", kind="ghost")
    split.setEnabled(False)
    split.setToolTip("Split tetap dimiliki Timeline Editor; AI preview tidak memutasi clip.")
    toolbar.addWidget(split)
    toolbar.addStretch(1)
    toolbar.addWidget(QLabel("⌕"))
    toolbar.addWidget(QLabel("−"))
    toolbar.addWidget(QLabel("100%"))
    toolbar.addWidget(QLabel("+"))
    root.addWidget(toolbar_widget)

    canvas = AIPlanTimelineCanvas(window, panel)
    root.addWidget(canvas, 1)
    host.layout().addWidget(panel, 1)
    panel.hide()
    window._ui08_timeline_panel = panel
    window._ui08_timeline_canvas = canvas

    header = host.layout().itemAt(0).layout()
    window._ui08_timeline_header_widgets = []
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if widget is not None:
                window._ui08_timeline_header_widgets.append(widget)


def _hide_foundation_context(window) -> None:
    for widget in getattr(window, "_s06_context_old", ()):
        if widget is not None:
            widget.hide()


def _apply_ai_geometry(window) -> None:
    shell = window.foundation_shell
    compact = bool(getattr(shell, "_responsive_compact", False))
    total = max(1, shell.width())

    nav = TOKENS.nav_compact_width if compact else TOKENS.nav_width
    context = 245 if compact else 300
    right = 38 if shell.inspector.collapsed else (280 if compact else 300)
    center = max(500 if compact else 650, total - nav - context - right - TOKENS.splitter_handle * 3)

    shell.navigation.setMinimumWidth(nav)
    shell.navigation.setMaximumWidth(nav)
    shell.context.setMinimumWidth(context)
    shell.context.setMaximumWidth(context)
    if not shell.inspector.collapsed:
        shell.inspector._expanded_width = right
        shell.inspector.setMinimumWidth(right)
        shell.inspector.setMaximumWidth(420)
    shell.horizontal_splitter.setSizes([nav, context, center, right])

    host = shell.timeline
    host.body.hide()
    inherited_header = host.layout().itemAt(0).layout() if host.layout().count() else None
    if inherited_header is not None:
        for index in range(inherited_header.count()):
            widget = inherited_header.itemAt(index).widget()
            if widget is not None:
                widget.hide()

    panel = getattr(window, "_ui08_timeline_panel", None)
    if panel is not None:
        panel.show()

    timeline_h = 178
    host._preferred_height = timeline_h
    host.setMinimumHeight(timeline_h)
    host.setMaximumHeight(timeline_h)
    top_h = max(330 if compact else 430, shell.height() - timeline_h - TOKENS.status_height - TOKENS.command_height)
    shell.vertical_splitter.setSizes([top_h, timeline_h])


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    _ensure_timeline_panel(self)
    active = route == "ai_agent"

    self._ui08_timeline_panel.setVisible(active)
    for widget in getattr(self, "_ui08_timeline_header_widgets", ()):
        widget.setVisible(not active)

    if active:
        _hide_foundation_context(self)
        self.ai_timeline_s09.hide()
        self.foundation_shell.timeline.body.hide()
        self.foundation_shell._apply_shell_sizes("ai_agent")
        _apply_ai_geometry(self)
        self._ui08_timeline_canvas.update()
        QTimer.singleShot(
            0,
            lambda: _apply_ai_geometry(self)
            if getattr(self, "foundation_state", None) is not None
            and self.foundation_state.workspace == "ai_agent"
            else None,
        )
    else:
        self._ui08_timeline_panel.hide()
        self.foundation_shell._apply_shell_sizes(route)


def _window_refresh(self) -> None:
    _originals["window_refresh"](self)
    if hasattr(self, "_ui08_timeline_canvas"):
        self._ui08_timeline_canvas.update()


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    if route == "ai_agent":
        _apply_ai_geometry(self.window())


def _shell_resize(self, event) -> None:
    _originals["shell_resize"](self, event)
    if getattr(getattr(self, "state", None), "workspace", "") == "ai_agent":
        _apply_ai_geometry(self.window())


def _shell_sizes(self, route: str) -> None:
    _originals["shell_sizes"](self, route)
    if route == "ai_agent":
        _apply_ai_geometry(self.window())


def install_ui08_ai_agent_remediation() -> None:
    """UI-08 presentation only; STEP09 plan/preview/execute/permission contracts stay authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget
    from .foundation_window import FoundationMainWindow

    _originals.update(
        conversation_init=AIConversationPanel.__init__,
        conversation_apply=AIConversationPanel.apply_data,
        plan_card_init=_PlanCard.__init__,
        task_init=AITaskCanvas.__init__,
        context_init=AIContextDock.__init__,
        context_set=AIContextDock.set_context,
        context_provider=AIContextDock.set_provider,
        window_route=FoundationMainWindow._s09_route,
        window_refresh=FoundationMainWindow._s09_refresh,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_resize=FoundationShellWidget.resizeEvent,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    AIConversationPanel.__init__ = _conversation_init
    AIConversationPanel.apply_data = _conversation_apply_data
    _PlanCard.__init__ = _plan_card_init
    AITaskCanvas.__init__ = _task_init
    AIContextDock.__init__ = _context_init
    AIContextDock.set_context = _context_set
    AIContextDock.set_provider = _context_provider
    FoundationMainWindow._s09_route = _window_route
    FoundationMainWindow._s09_refresh = _window_refresh
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget.resizeEvent = _shell_resize
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
