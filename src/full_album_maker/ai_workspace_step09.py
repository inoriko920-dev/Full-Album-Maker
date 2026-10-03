from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .ai_action_registry_step09 import PlanPreview
from .ai_agent_core_step09 import (
    AgentPermission,
    AgentPlan,
    AgentState,
)
from .ai_history_step09 import AgentHistoryEntry, SavedAgentCommand
from .ai_session_step09 import AgentSessionSnapshot
from .foundation_components import FAMButton, FAMCard
from .foundation_tokens import TOKENS


def _chip(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("statusChip")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setContentsMargins(7, 2, 7, 2)
    return label


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeading")
    return label


class AIConversationPanel(QFrame):
    new_conversation_requested = Signal()
    saved_command_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aiConversationPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        header = QHBoxLayout()
        header.addWidget(_section("Percakapan"))
        header.addStretch(1)
        self.new_button = FAMButton("+ Baru", kind="primary")
        self.new_button.clicked.connect(self.new_conversation_requested)
        header.addWidget(self.new_button)
        root.addLayout(header)

        self.today_label = _section("Hari Ini")
        root.addWidget(self.today_label)
        self.today = QListWidget()
        self.today.setMaximumHeight(150)
        self.today.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self.today)

        self.yesterday_label = _section("Kemarin")
        root.addWidget(self.yesterday_label)
        self.yesterday = QListWidget()
        self.yesterday.setMaximumHeight(105)
        self.yesterday.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self.yesterday)

        root.addWidget(_section("Perintah Tersimpan"))
        self.saved = QListWidget()
        self.saved.itemDoubleClicked.connect(self._saved_clicked)
        root.addWidget(self.saved, 1)

        self.privacy = QLabel("Riwayat disanitasi • secret/path tidak disimpan")
        self.privacy.setObjectName("metadata")
        self.privacy.setWordWrap(True)
        root.addWidget(self.privacy)

    def apply_data(
        self,
        history: Iterable[AgentHistoryEntry],
        saved: Iterable[SavedAgentCommand],
    ) -> None:
        self.today.clear()
        self.yesterday.clear()
        self.saved.clear()
        now = datetime.now(timezone.utc).date()
        for entry in reversed(tuple(history)):
            try:
                day = datetime.fromisoformat(entry.timestamp).date()
            except Exception:
                day = now
            text = f"{entry.role.title()} • {entry.status}\n{entry.text[:88]}"
            item = QListWidgetItem(text)
            target = self.today if day == now else self.yesterday
            if target.count() < 8:
                target.addItem(item)
        if self.today.count() == 0:
            self.today.addItem(QListWidgetItem("Belum ada percakapan hari ini"))
        if self.yesterday.count() == 0:
            self.yesterday.addItem(QListWidgetItem("Tidak ada item lama"))
        for command in reversed(tuple(saved)):
            item = QListWidgetItem(command.name)
            item.setToolTip(command.prompt)
            item.setData(Qt.ItemDataRole.UserRole, command.prompt)
            self.saved.addItem(item)
        if self.saved.count() == 0:
            self.saved.addItem(QListWidgetItem("Belum ada perintah tersimpan"))

    def _saved_clicked(self, item: QListWidgetItem) -> None:
        prompt = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if prompt:
            self.saved_command_requested.emit(prompt)


class _PlanCard(FAMCard):
    def __init__(self, number: int, title: str, detail: str, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(9, 7, 9, 7)
        index = QLabel(str(number))
        index.setObjectName("statusChip")
        index.setFixedWidth(28)
        index.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(index)
        box = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        box.addWidget(heading)
        meta = QLabel(detail)
        meta.setObjectName("metadata")
        meta.setWordWrap(True)
        box.addWidget(meta)
        row.addLayout(box, 1)


class AITaskCanvas(QFrame):
    send_requested = Signal(str)
    preview_requested = Signal()
    execute_requested = Signal()
    cancel_requested = Signal()
    undo_requested = Signal()
    save_command_requested = Signal(str)
    attachment_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aiTaskCanvas")
        self._state = AgentState.IDLE
        self._context_chips: tuple[str, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(11, 9, 11, 9)
        root.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("AI Agent")
        title.setObjectName("workspaceHeading")
        top.addWidget(title)
        top.addStretch(1)
        self.state_chip = _chip("IDLE")
        top.addWidget(self.state_chip)
        root.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(2, 2, 2, 2)
        self.body_layout.setSpacing(8)

        self.user_card = FAMCard()
        user_box = QVBoxLayout(self.user_card)
        user_box.addWidget(_section("Perintah Anda"))
        self.user_text = QLabel("Belum ada instruksi aktif.")
        self.user_text.setWordWrap(True)
        user_box.addWidget(self.user_text)
        self.body_layout.addWidget(self.user_card)

        self.ai_card = FAMCard()
        ai_box = QVBoxLayout(self.ai_card)
        ai_box.addWidget(_section("Interpretasi AI"))
        self.ai_text = QLabel("Kirim instruksi untuk membuat rencana terstruktur.")
        self.ai_text.setWordWrap(True)
        self.ai_text.setObjectName("muted")
        ai_box.addWidget(self.ai_text)
        self.body_layout.addWidget(self.ai_card)

        self.plan_host = QWidget()
        self.plan_layout = QVBoxLayout(self.plan_host)
        self.plan_layout.setContentsMargins(0, 0, 0, 0)
        self.plan_layout.setSpacing(6)
        self.body_layout.addWidget(self.plan_host)

        self.scope_card = FAMCard()
        scope_box = QVBoxLayout(self.scope_card)
        scope_box.addWidget(_section("Ruang Lingkup"))
        self.scope_text = QLabel("Belum ada scope tervalidasi.")
        self.scope_text.setWordWrap(True)
        self.scope_text.setObjectName("metadata")
        scope_box.addWidget(self.scope_text)
        self.body_layout.addWidget(self.scope_card)

        self.impact_card = FAMCard()
        impact_box = QVBoxLayout(self.impact_card)
        impact_box.addWidget(_section("Impact Summary"))
        self.impact_text = QLabel("Preview Perubahan belum dijalankan.")
        self.impact_text.setWordWrap(True)
        impact_box.addWidget(self.impact_text)
        self.body_layout.addWidget(self.impact_card)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

        actions = QHBoxLayout()
        self.preview_button = FAMButton("Preview Perubahan", kind="secondary")
        self.execute_button = FAMButton("Jalankan", kind="primary")
        self.cancel_button = FAMButton("Batalkan", kind="ghost")
        self.undo_button = FAMButton("Undo AI", kind="ghost")
        self.preview_button.clicked.connect(self.preview_requested)
        self.execute_button.clicked.connect(self.execute_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.undo_button.clicked.connect(self.undo_requested)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.execute_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        actions.addWidget(self.undo_button)
        root.addLayout(actions)

        composer = QFrame()
        composer.setObjectName("famCard")
        compose_layout = QVBoxLayout(composer)
        compose_layout.setContentsMargins(9, 7, 9, 7)
        chip_row = QHBoxLayout()
        self.chip_label = QLabel("Project Aktif • 0 lagu dipilih • Semua media")
        self.chip_label.setObjectName("metadata")
        self.chip_label.setWordWrap(True)
        chip_row.addWidget(self.chip_label, 1)
        self.attach_button = FAMButton("+ Lampiran", kind="ghost")
        self.attach_button.setToolTip("Hanya context/project/media object yang sudah divalidasi; bukan path filesystem bebas.")
        self.attach_button.clicked.connect(self.attachment_requested)
        chip_row.addWidget(self.attach_button)
        compose_layout.addLayout(chip_row)

        input_row = QHBoxLayout()
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Instruksikan AI Agent…")
        self.prompt.setMaximumHeight(82)
        self.prompt.textChanged.connect(self._update_send_enabled)
        input_row.addWidget(self.prompt, 1)
        send_col = QVBoxLayout()
        self.send_button = FAMButton("Kirim", kind="primary")
        self.save_button = FAMButton("Simpan Perintah", kind="ghost")
        self.send_button.clicked.connect(self._send)
        self.save_button.clicked.connect(self._save)
        send_col.addWidget(self.send_button)
        send_col.addWidget(self.save_button)
        input_row.addLayout(send_col)
        compose_layout.addLayout(input_row)
        root.addWidget(composer)
        self._update_buttons(False)

    def set_prompt(self, text: str) -> None:
        self.prompt.setPlainText(str(text))
        self.prompt.setFocus()

    def set_context_chips(self, labels: Iterable[str]) -> None:
        self._context_chips = tuple(str(value) for value in labels if str(value))
        self.chip_label.setText(" • ".join(self._context_chips) if self._context_chips else "Context belum tersedia")

    def apply_session(self, snapshot: AgentSessionSnapshot, *, can_undo_ai: bool) -> None:
        self._state = snapshot.state
        self.state_chip.setText(snapshot.state.value)
        self.user_text.setText(snapshot.prompt or "Belum ada instruksi aktif.")
        if snapshot.state == AgentState.NEEDS_CLARIFICATION:
            self.ai_text.setText(snapshot.clarification or snapshot.message or "AI membutuhkan klarifikasi.")
        elif snapshot.error:
            self.ai_text.setText(snapshot.error)
        else:
            self.ai_text.setText(snapshot.message or "Kirim instruksi untuk membuat rencana terstruktur.")
        self._render_plan(snapshot.plan)
        self._render_impact(snapshot.preview)
        self._update_buttons(can_undo_ai)

    def _render_plan(self, plan: AgentPlan | None) -> None:
        while self.plan_layout.count():
            item = self.plan_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if plan is None:
            self.scope_text.setText("Belum ada scope tervalidasi.")
            return
        groups: list[tuple[str, str]] = []
        visual_count = sum(1 for action in plan.actions if action.name == "set_song_visual")
        speed = next((action for action in plan.actions if action.name == "set_song_video_speed"), None)
        if plan.scope_song_ids:
            groups.append(("Target lagu", f"{len(plan.scope_song_ids)} stable song_id tervalidasi"))
        if visual_count:
            groups.append(("Pasangkan visual", f"{visual_count} assignment media dari allowlist context"))
        if speed is not None:
            groups.append(("Atur kecepatan visual", f"speed {speed.args.get('speed')}x melalui action contract Visual"))
        if any(action.name == "auto_arrange_timeline" for action in plan.actions):
            groups.append(("Susun timeline", "Auto Susun lokal melalui action whitelist"))
        known = {"set_song_visual", "set_song_video_speed", "auto_arrange_timeline"}
        other = [action.name for action in plan.actions if action.name not in known]
        if other:
            groups.append(("Action tambahan", ", ".join(other[:8])))
        for index, (title, detail) in enumerate(groups[:6], start=1):
            self.plan_layout.addWidget(_PlanCard(index, title, detail))
        permissions = ", ".join(plan.required_permissions) or "read-only"
        self.scope_text.setText(
            f"{len(plan.scope_song_ids)} lagu • {len(plan.actions)} action • permission: {permissions}\nplan_id {plan.plan_id[:12]}…"
        )

    def _render_impact(self, preview: PlanPreview | None) -> None:
        if preview is None:
            self.impact_text.setText("Preview Perubahan belum dijalankan. Project belum dimutasi.")
            return
        impact = preview.impact
        self.impact_text.setText(
            f"{len(impact.changed_song_ids)} lagu • {len(impact.changed_layer_ids)} layer • "
            f"playlist {'berubah' if impact.playlist_order_changed else 'tetap'} • "
            f"{preview.command_count} domain command • "
            f"{'Siap Dijalankan' if preview.has_changes else 'Tidak ada perubahan'}"
        )

    def _update_buttons(self, can_undo_ai: bool) -> None:
        state = self._state
        self.preview_button.setEnabled(state == AgentState.PLAN_READY)
        self.execute_button.setEnabled(state == AgentState.PREVIEW_READY)
        self.cancel_button.setEnabled(state in {AgentState.INTERPRETING, AgentState.NEEDS_CLARIFICATION, AgentState.PLAN_READY, AgentState.PREVIEW_READY})
        self.undo_button.setEnabled(bool(can_undo_ai))
        self.send_button.setEnabled(bool(self.prompt.toPlainText().strip()) and state != AgentState.EXECUTING)
        self.save_button.setEnabled(bool(self.prompt.toPlainText().strip()))

    def _update_send_enabled(self) -> None:
        self._update_buttons(self.undo_button.isEnabled())

    def _send(self) -> None:
        text = " ".join(self.prompt.toPlainText().split())
        if text:
            self.send_requested.emit(text)

    def _save(self) -> None:
        text = " ".join(self.prompt.toPlainText().split())
        if text:
            self.save_command_requested.emit(text)


class AIContextDock(QFrame):
    provider_changed = Signal(str)
    permissions_changed = Signal()
    context_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aiContextDock")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        root.addWidget(_section("Context & Izin"))
        self.project = QLabel("Project Aktif: —")
        self.project.setWordWrap(True)
        root.addWidget(self.project)
        self.songs = QLabel("Lagu yang Dipilih: 0")
        self.songs.setObjectName("metadata")
        root.addWidget(self.songs)
        self.media = QLabel("Media yang Boleh Dipakai: 0")
        self.media.setObjectName("metadata")
        root.addWidget(self.media)

        root.addWidget(_section("Provider AI"))
        self.provider = QComboBox()
        self.provider.addItem("Gemini", "gemini")
        self.provider.addItem("Mock / Test", "mock")
        self.provider.currentIndexChanged.connect(
            lambda _index: self.provider_changed.emit(str(self.provider.currentData() or "gemini"))
        )
        root.addWidget(self.provider)
        self.key_status = QLabel("Status Key: memeriksa…")
        self.key_status.setObjectName("metadata")
        root.addWidget(self.key_status)

        root.addWidget(_section("Permission"))
        self.permissions: dict[str, QCheckBox] = {}
        labels = {
            AgentPermission.VISUAL_WRITE.value: "Visual",
            AgentPermission.TIMELINE_WRITE.value: "Timeline",
            AgentPermission.PLAYLIST_WRITE.value: "Album / Playlist",
            AgentPermission.TEMPLATE_WRITE.value: "Template",
            AgentPermission.SPECTRUM_WRITE.value: "Spectrum",
        }
        for permission, label in labels.items():
            check = QCheckBox(label)
            check.setChecked(True)
            check.toggled.connect(self.permissions_changed)
            self.permissions[permission] = check
            root.addWidget(check)

        root.addWidget(_section("Catatan Keamanan"))
        safety = QLabel(
            "• AI hanya membuat rencana terstruktur.\n"
            "• ID/media harus berasal dari context.\n"
            "• Preview Perubahan tidak memutasi project.\n"
            "• API key tidak pernah ditampilkan/disimpan di project/history."
        )
        safety.setObjectName("metadata")
        safety.setWordWrap(True)
        root.addWidget(safety)
        self.stale = QLabel("")
        self.stale.setObjectName("metadata")
        self.stale.setWordWrap(True)
        root.addWidget(self.stale)
        root.addStretch(1)

    def set_context(self, *, project_name: str, song_count: int, media_count: int) -> None:
        self.project.setText(f"Project Aktif: {project_name or 'Untitled'}")
        self.songs.setText(f"Lagu yang Dipilih: {int(song_count)}")
        self.media.setText(f"Media yang Boleh Dipakai: {int(media_count)} dari project")

    def set_provider(self, provider_id: str, *, key_ready: bool) -> None:
        index = self.provider.findData(provider_id)
        if index >= 0:
            self.provider.blockSignals(True)
            self.provider.setCurrentIndex(index)
            self.provider.blockSignals(False)
        if provider_id == "mock":
            self.key_status.setText("Status Key: Test / tidak memakai live API")
        else:
            self.key_status.setText("Status Key: Aktif" if key_ready else "Status Key: Tidak Ada")

    def permission_values(self) -> frozenset[str]:
        return frozenset(key for key, check in self.permissions.items() if check.isChecked())

    def set_stale_warning(self, text: str) -> None:
        self.stale.setText(str(text))
