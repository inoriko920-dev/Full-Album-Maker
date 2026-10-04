from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .foundation_components import FAMButton, FAMCard, FAMSegmented
from .foundation_tokens import TOKENS
from .render_center_model_step10 import RenderJob, RenderJobState, RenderMetrics, RenderSettings, settings_from_preset
from .render_preflight_step10 import PreflightLevel, PreflightReport


_PRESET_LABELS = {
    "youtube_1080p": "YouTube 1080p",
    "youtube_1440p": "YouTube 1440p",
    "youtube_4k": "YouTube 4K",
    "custom": "Custom",
}


class RenderHistoryContext(QFrame):
    retry_requested = Signal(str, str)
    job_selected = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("renderHistoryContext")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)
        title = QLabel("Render")
        title.setObjectName("sectionHeading")
        root.addWidget(title)
        sub = QLabel("Antrian & riwayat attempt")
        sub.setObjectName("muted")
        root.addWidget(sub)
        self.filter = FAMSegmented([
            ("all", "Semua"),
            ("queue", "Antrian"),
            ("history", "Riwayat"),
        ])
        root.addWidget(self.filter)
        self.listing = QListWidget()
        self.listing.currentItemChanged.connect(self._selected)
        root.addWidget(self.listing, 1)
        row = QHBoxLayout()
        self.retry = FAMButton("Coba Lagi", kind="ghost")
        self.retry.clicked.connect(self._retry)
        self.retry.setEnabled(False)
        row.addWidget(self.retry)
        row.addStretch(1)
        root.addLayout(row)
        for button in self.filter._buttons.values():
            button.clicked.connect(lambda: self._last_jobs and self.apply_jobs(self._last_jobs))
        self._last_jobs: tuple[RenderJob, ...] = ()

    def apply_jobs(self, jobs: Iterable[RenderJob]) -> None:
        self._last_jobs = tuple(jobs)
        selected = self.listing.currentItem()
        selected_key = selected.data(Qt.ItemDataRole.UserRole) if selected is not None else None
        key = self.filter.checked_value() or "all"
        values = list(self._last_jobs)
        if key == "queue":
            values = [job for job in values if job.state in {RenderJobState.READY, RenderJobState.QUEUED, RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.FINALIZING}]
        elif key == "history":
            values = [job for job in values if job.state in {RenderJobState.COMPLETED, RenderJobState.FAILED, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED, RenderJobState.BLOCKED}]
        self.listing.clear()
        restore = None
        for job in reversed(values):
            name = Path(job.settings.final_output).name
            item = QListWidgetItem(f"{name}\n{job.state.value} • {job.metrics.percent:.0f}%")
            payload = (job.job_id, job.attempt_id)
            item.setData(Qt.ItemDataRole.UserRole, payload)
            item.setToolTip(job.error_message or job.verified_output or job.snapshot.snapshot_hash[:12])
            self.listing.addItem(item)
            if payload == selected_key:
                restore = item
        if restore is not None:
            self.listing.setCurrentItem(restore)
        self._refresh_retry()

    def _selected(self, current, _previous) -> None:
        if current is not None:
            job_id, attempt_id = current.data(Qt.ItemDataRole.UserRole)
            self.job_selected.emit(str(job_id), str(attempt_id))
        self._refresh_retry()

    def _refresh_retry(self) -> None:
        current = self.listing.currentItem()
        retryable = False
        if current is not None:
            job_id, attempt_id = current.data(Qt.ItemDataRole.UserRole)
            job = next((item for item in self._last_jobs if item.job_id == job_id and item.attempt_id == attempt_id), None)
            retryable = bool(job and job.state in {RenderJobState.FAILED, RenderJobState.CANCELLED, RenderJobState.INTERRUPTED, RenderJobState.BLOCKED})
        self.retry.setEnabled(retryable)

    def _retry(self) -> None:
        current = self.listing.currentItem()
        if current is None:
            return
        job_id, attempt_id = current.data(Qt.ItemDataRole.UserRole)
        self.retry_requested.emit(str(job_id), str(attempt_id))


class PreflightSummaryCard(FAMCard):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 7, 9, 7)
        lay.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("metadata")
        self.state = QLabel("Belum diperiksa")
        self.state.setObjectName("sectionHeading")
        self.detail = QLabel("—")
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addWidget(self.state)
        lay.addWidget(self.detail)

    def set_check(self, level: PreflightLevel | None, detail: str) -> None:
        if level is None:
            self.state.setText("Belum diperiksa")
            self.state.setStyleSheet("")
        elif level == PreflightLevel.PASS:
            self.state.setText("✓ PASS")
            self.state.setStyleSheet(f"color:{TOKENS.success};")
        elif level == PreflightLevel.WARN:
            self.state.setText("⚠ WARN")
            self.state.setStyleSheet(f"color:{TOKENS.warning};")
        else:
            self.state.setText("✕ BLOCK")
            self.state.setStyleSheet(f"color:{TOKENS.danger};")
        self.detail.setText(detail or "—")


class RenderCenterWorkspace(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("renderCenterWorkspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(8)

        header = QHBoxLayout()
        box = QVBoxLayout()
        title = QLabel("Render Center")
        title.setObjectName("workspaceHeading")
        box.addWidget(title)
        subtitle = QLabel("Snapshot immutable • Preflight • Verified output • Atomic finalize")
        subtitle.setObjectName("muted")
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.snapshot_label = QLabel("Snapshot: —")
        self.snapshot_label.setObjectName("metadata")
        header.addWidget(self.snapshot_label)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        self.preflight_cards: dict[str, PreflightSummaryCard] = {}
        groups = [
            ("snapshot", "Project Snapshot"),
            ("media", "Media"),
            ("ffmpeg", "FFmpeg"),
            ("encoder", "Encoder"),
            ("output", "Output"),
            ("disk", "Disk Space"),
        ]
        for index, (key, label) in enumerate(groups):
            card = PreflightSummaryCard(label)
            self.preflight_cards[key] = card
            grid.addWidget(card, index // 3, index % 3)
        root.addLayout(grid)

        active = FAMCard()
        active_layout = QVBoxLayout(active)
        active_layout.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        self.active_name = QLabel("Belum ada render aktif")
        self.active_name.setObjectName("sectionHeading")
        self.active_state = QLabel("IDLE")
        self.active_state.setObjectName("statusChip")
        top.addWidget(self.active_name)
        top.addStretch(1)
        top.addWidget(self.active_state)
        active_layout.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        active_layout.addWidget(self.progress)
        metrics = QHBoxLayout()
        self.metric_labels: dict[str, QLabel] = {}
        for key, label in (("fps", "FPS"), ("avg", "Avg FPS"), ("speed", "Speed"), ("eta", "ETA")):
            panel = QFrame()
            p = QVBoxLayout(panel)
            p.setContentsMargins(6, 3, 6, 3)
            name = QLabel(label)
            name.setObjectName("metadata")
            value = QLabel("—")
            value.setObjectName("sectionHeading")
            p.addWidget(name)
            p.addWidget(value)
            metrics.addWidget(panel, 1)
            self.metric_labels[key] = value
        active_layout.addLayout(metrics)
        root.addWidget(active)

        lower = QHBoxLayout()
        queue_card = FAMCard()
        qlay = QVBoxLayout(queue_card)
        qtitle = QLabel("Antrian")
        qtitle.setObjectName("sectionHeading")
        qlay.addWidget(qtitle)
        self.queue_list = QListWidget()
        qlay.addWidget(self.queue_list, 1)
        lower.addWidget(queue_card, 1)

        log_card = FAMCard()
        llay = QVBoxLayout(log_card)
        ltitle = QLabel("Log Aman")
        ltitle.setObjectName("sectionHeading")
        llay.addWidget(ltitle)
        self.log_list = QListWidget()
        llay.addWidget(self.log_list, 1)
        lower.addWidget(log_card, 1)
        root.addLayout(lower, 1)

    def clear_preflight(self, message: str = "Pengaturan berubah — jalankan Preflight lagi") -> None:
        for card in self.preflight_cards.values():
            card.set_check(None, message)
        self.snapshot_label.setText("Snapshot: —")

    def apply_preflight(self, report: PreflightReport) -> None:
        by_key = {check.key: check for check in report.checks}
        for key, card in self.preflight_cards.items():
            if key == "output":
                values = [item for name, item in by_key.items() if name in {"output", "output_source"}]
                if values:
                    level = PreflightLevel.BLOCK if any(item.level == PreflightLevel.BLOCK for item in values) else PreflightLevel.WARN if any(item.level == PreflightLevel.WARN for item in values) else PreflightLevel.PASS
                    card.set_check(level, " • ".join(item.message for item in values))
                continue
            check = by_key.get(key)
            if check is not None:
                card.set_check(check.level, check.message)
        self.snapshot_label.setText(
            "Snapshot: " + (report.snapshot.snapshot_hash[:12] if report.snapshot else "BLOCKED")
        )

    def apply_job(self, job: RenderJob | None) -> None:
        if job is None:
            self.active_name.setText("Belum ada render aktif")
            self.active_state.setText("IDLE")
            self.apply_metrics(RenderMetrics())
            return
        self.active_name.setText(Path(job.settings.final_output).name)
        self.active_state.setText(job.state.value)
        self.apply_metrics(job.metrics)

    def apply_metrics(self, metrics: RenderMetrics) -> None:
        self.progress.setValue(int(max(0.0, min(100.0, metrics.percent)) * 10))
        self.progress.setFormat(f"{metrics.percent:.1f}%")
        self.metric_labels["fps"].setText("—" if metrics.fps is None else f"{metrics.fps:.1f}")
        self.metric_labels["avg"].setText("—" if metrics.average_fps is None else f"{metrics.average_fps:.1f}")
        self.metric_labels["speed"].setText("—" if metrics.speed is None else f"{metrics.speed:.2f}x")
        if metrics.eta_seconds is None:
            eta = "—"
        else:
            seconds = max(0, int(round(metrics.eta_seconds)))
            eta = f"{seconds // 60:02d}:{seconds % 60:02d}"
        self.metric_labels["eta"].setText(eta)

    def apply_queue(self, jobs: Iterable[RenderJob]) -> None:
        self.queue_list.clear()
        for job in jobs:
            if job.state not in {RenderJobState.QUEUED, RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.FINALIZING}:
                continue
            self.queue_list.addItem(
                f"{Path(job.settings.final_output).name}  •  {job.state.value}  •  {job.metrics.percent:.0f}%"
            )

    def append_log(self, line: str) -> None:
        if not line:
            return
        self.log_list.addItem(str(line))
        while self.log_list.count() > 150:
            self.log_list.takeItem(0)
        self.log_list.scrollToBottom()


class RenderSettingsInspector(QFrame):
    settings_changed = Signal()
    browse_requested = Signal()
    preflight_requested = Signal()
    start_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("renderSettingsInspector")
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)
        heading = QLabel("Pengaturan Render")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)

        self.filename = self._line(root, "Nama File", "Full Album Final")
        root.addWidget(self._label("Folder Output"))
        folder_row = QHBoxLayout()
        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText("Pilih folder output...")
        self.browse = FAMButton("Pilih", kind="ghost")
        self.browse.clicked.connect(self.browse_requested)
        folder_row.addWidget(self.output_folder, 1)
        folder_row.addWidget(self.browse)
        root.addLayout(folder_row)

        self.preset = self._combo(root, "Preset", [(key, label) for key, label in _PRESET_LABELS.items()])
        row = QHBoxLayout()
        self.width = self._spin(320, 7680, 1920)
        self.height = self._spin(240, 4320, 1080)
        row.addWidget(self.width)
        row.addWidget(QLabel("×"))
        row.addWidget(self.height)
        root.addWidget(self._label("Resolusi"))
        root.addLayout(row)
        self.fps = self._combo(root, "FPS", [(str(v), str(v)) for v in (24, 25, 30, 50, 60)])
        self.video_codec = self._combo(root, "Video Codec", [("h264", "H.264"), ("h265", "H.265 / HEVC")])
        self.video_bitrate = self._spin(1, 200, 16, suffix=" Mbps")
        root.addWidget(self._label("Video Bitrate"))
        root.addWidget(self.video_bitrate)
        self.audio_bitrate = self._combo(root, "Audio Bitrate", [(str(v), f"{v} kbps") for v in (128, 192, 256, 320)])
        self.sample_rate = self._combo(root, "Sample Rate", [("44100", "44.1 kHz"), ("48000", "48 kHz")])
        self.hardware = self._combo(root, "Encoder", [
            ("auto", "Auto (verified HW → SW fallback)"),
            ("software", "Software"),
            ("h264_nvenc", "NVIDIA H.264 NVENC"),
            ("hevc_nvenc", "NVIDIA HEVC NVENC"),
        ])
        self.overwrite = QCheckBox("Izinkan ganti file final yang sudah ada")
        root.addWidget(self.overwrite)

        self.warning = QLabel("")
        self.warning.setObjectName("metadata")
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)

        self.preflight = FAMButton("Jalankan Preflight", kind="ghost")
        self.start = FAMButton("Mulai Render", kind="primary")
        self.pause = FAMButton("Pause", kind="ghost")
        self.pause.setEnabled(False)
        self.pause.setToolTip("Pause/resume belum diaktifkan karena safe semantics belum terbukti pada engine recovered.")
        self.cancel = FAMButton("Batalkan", kind="ghost")
        self.cancel.setEnabled(False)
        root.addWidget(self.preflight)
        root.addWidget(self.start)
        buttons = QHBoxLayout()
        buttons.addWidget(self.pause)
        buttons.addWidget(self.cancel)
        root.addLayout(buttons)
        root.addStretch(1)

        self.preflight.clicked.connect(self.preflight_requested)
        self.start.clicked.connect(self.start_requested)
        self.cancel.clicked.connect(self.cancel_requested)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        for widget in (
            self.filename, self.output_folder, self.width, self.height, self.fps,
            self.video_codec, self.video_bitrate, self.audio_bitrate,
            self.sample_rate, self.hardware, self.overwrite,
        ):
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(lambda *_: self._changed())
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(lambda *_: self._changed())
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(lambda *_: self._changed())
            if hasattr(widget, "toggled"):
                widget.toggled.connect(lambda *_: self._changed())
        self.set_preflight_ready(False)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("metadata")
        return label

    def _line(self, root: QVBoxLayout, label: str, value: str) -> QLineEdit:
        root.addWidget(self._label(label))
        field = QLineEdit(value)
        root.addWidget(field)
        return field

    def _combo(self, root: QVBoxLayout, label: str, values: list[tuple[str, str]]) -> QComboBox:
        root.addWidget(self._label(label))
        combo = QComboBox()
        for value, text in values:
            combo.addItem(text, value)
        root.addWidget(combo)
        return combo

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int, suffix: str = "") -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        if suffix:
            box.setSuffix(suffix)
        return box

    def _set_combo(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _preset_changed(self) -> None:
        if self._updating:
            return
        preset_id = str(self.preset.currentData() or "custom")
        if preset_id == "custom":
            self._changed()
            return
        try:
            settings = settings_from_preset(
                preset_id,
                filename=self.filename.text() or "Full Album Final",
                output_folder=self.output_folder.text() or str(Path.cwd()),
            )
        except Exception:
            self._changed()
            return
        self._updating = True
        try:
            self.width.setValue(settings.width)
            self.height.setValue(settings.height)
            self._set_combo(self.fps, str(settings.fps))
            self._set_combo(self.video_codec, settings.video_codec)
            self.video_bitrate.setValue(settings.video_bitrate_bps // 1_000_000)
            self._set_combo(self.audio_bitrate, str(settings.audio_bitrate_bps // 1000))
            self._set_combo(self.sample_rate, str(settings.sample_rate))
            self._set_combo(self.hardware, settings.hardware_mode)
        finally:
            self._updating = False
        self._changed()

    def _changed(self) -> None:
        if not self._updating:
            self.settings_changed.emit()

    def settings(self) -> RenderSettings:
        settings = RenderSettings(
            filename=self.filename.text().strip(),
            output_folder=self.output_folder.text().strip(),
            width=self.width.value(),
            height=self.height.value(),
            fps=int(self.fps.currentData() or 30),
            video_codec=str(self.video_codec.currentData() or "h264"),
            video_bitrate_bps=self.video_bitrate.value() * 1_000_000,
            audio_codec="aac",
            audio_bitrate_bps=int(self.audio_bitrate.currentData() or 320) * 1000,
            sample_rate=int(self.sample_rate.currentData() or 48000),
            hardware_mode=str(self.hardware.currentData() or "auto"),
            container="mp4",
            overwrite=self.overwrite.isChecked(),
            preset_id=str(self.preset.currentData() or "custom"),
        )
        settings.validate()
        return settings

    def set_output_folder(self, path: str) -> None:
        self.output_folder.setText(str(path))

    def set_preflight_ready(self, ready: bool, message: str = "") -> None:
        self.start.setEnabled(bool(ready))
        self.warning.setText(message)

    def set_busy(self, busy: bool) -> None:
        self.preflight.setEnabled(not busy)
        self.start.setEnabled(self.start.isEnabled() and not busy)
        self.cancel.setEnabled(bool(busy))
        self.browse.setEnabled(not busy)
