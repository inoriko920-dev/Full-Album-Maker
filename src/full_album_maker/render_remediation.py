from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .foundation_components import FAMButton
from .render_center_model_step10 import RenderJobState

_installed = False
_originals: dict[str, Any] = {}


_PRESET_SURFACE = (
    ("youtube_1080p", "▶  YouTube 1080p\n1920 × 1080 • H.264 • MP4"),
    ("youtube_1440p", "▶  YouTube 1440p\n2560 × 1440 • H.264 • MP4"),
    ("youtube_4k", "▶  YouTube 4K\n3840 × 2160 • H.265 • MP4"),
    ("custom", "⚙  Custom\nAtur pengaturan sendiri"),
)


# UI-09 queue cards read state exclusively from STEP10 RenderJob/RenderQueue.
# They do not have their own job model or rendering lifecycle.
_QUEUE_ACTIVE = frozenset({
    RenderJobState.QUEUED,
    RenderJobState.STARTING,
    RenderJobState.RUNNING,
    RenderJobState.FINALIZING,
})


def _visible_queue_jobs(jobs):
    active = [job for job in jobs if job.state in _QUEUE_ACTIVE]
    completed = [
        job for job in jobs
        if job.state == RenderJobState.COMPLETED and bool(job.verified_output)
    ]
    if completed:
        active.append(completed[-1])
    return active


class _QueueJobCard(QFrame):
    """Render-only card; progress updates come from the engine job."""

    def __init__(self, job, position: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ui09QueueJobCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "QFrame#ui09QueueJobCard{background:#FFFFFF;border:1px solid #DCE8F7;"
            "border-radius:8px;} "
            "QProgressBar{background:#E8EEF7;border:0;border-radius:4px;}"
            "QProgressBar::chunk{background:#1672ED;border-radius:4px;}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 7, 11, 7)
        layout.setSpacing(9)

        number = QLabel(str(position))
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFixedSize(24, 24)
        number.setStyleSheet(
            "background:#0868EB;color:white;border-radius:12px;font-weight:700;"
        )
        layout.addWidget(number)

        content = QVBoxLayout()
        content.setSpacing(3)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-size:12px;font-weight:700;color:#15254B;")
        self.details = QLabel()
        self.details.setStyleSheet("font-size:10px;color:#677EA4;")
        self.details.setToolTip(str(Path(job.settings.final_output)))
        self.note = QLabel()
        self.note.setStyleSheet("font-size:10px;color:#5077B3;")
        content.addWidget(self.heading)
        content.addWidget(self.details)
        content.addWidget(self.note)
        layout.addLayout(content, 3)

        progress_column = QVBoxLayout()
        progress_column.setSpacing(7)
        value_line = QHBoxLayout()
        self.percent = QLabel()
        self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#0868EB;")
        self.state = QLabel()
        self.state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.state.setStyleSheet("font-size:10px;color:#52729A;")
        value_line.addWidget(self.percent)
        value_line.addWidget(self.state, 1)
        progress_column.addLayout(value_line)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        progress_column.addWidget(self.bar)
        layout.addLayout(progress_column, 2)
        self.refresh(job)

    def refresh(self, job) -> None:
        name = Path(job.settings.final_output).stem
        self.heading.setText(name)
        self.setAccessibleName(f"Antrean render: {name}")
        settings = job.settings
        self.details.setText(
            f"{settings.width} × {settings.height}  •  "
            f"{settings.container.upper()}  •  {settings.video_codec.upper()}"
        )
        percent = max(0.0, min(100.0, float(job.metrics.percent)))
        self.percent.setText(f"{percent:.0f}%")
        self.bar.setValue(round(percent * 10))
        if job.state == RenderJobState.COMPLETED:
            self.state.setText("SELESAI")
            self.note.setText("Output terverifikasi")
            self.bar.setStyleSheet("QProgressBar::chunk{background:#16A34A;}")
            self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#159447;")
        elif job.state == RenderJobState.QUEUED:
            self.state.setText("ANTREAN")
            self.note.setText("Menunggu giliran render")
        else:
            self.state.setText(job.state.value)
            fps = job.metrics.fps
            self.note.setText(
                "Sedang merender" if fps is None else f"Sedang merender  •  {fps:.0f} fps"
            )


def _present_queue(workspace, jobs) -> None:
    widgets = {}
    for index, job in enumerate(_visible_queue_jobs(jobs)):
        item = workspace.queue_list.item(index)
        if item is None:
            break
        item.setSizeHint(QSize(0, 68 if getattr(workspace, 'ui09_compact', False) else 78))
        card = _QueueJobCard(job, index + 1, workspace.queue_list)
        workspace.queue_list.setItemWidget(item, card)
        widgets[(job.job_id, job.attempt_id)] = card
    workspace.ui09_queue_widgets = widgets


def _apply_queue_presentation(self, jobs) -> None:
    jobs = tuple(jobs)
    _originals["apply_queue"](self, jobs)
    if getattr(self, "_ui09_prepared", False):
        _present_queue(self, jobs)


def _apply_job_presentation(self, job) -> None:
    _originals["apply_job"](self, job)
    if job is not None and getattr(self, "_ui09_prepared", False):
        card = getattr(self, "ui09_queue_widgets", {}).get(
            (job.job_id, job.attempt_id)
        )
        if card is not None:
            card.refresh(job)


def _add_layout_item(destination: QVBoxLayout, item) -> None:
    widget = item.widget()
    if widget is not None:
        destination.addWidget(widget)
        return
    layout = item.layout()
    if layout is not None:
        destination.addLayout(layout)
        return
    spacer = item.spacerItem()
    if spacer is not None:
        destination.addItem(spacer)


def _sync_preset_surface(window) -> None:
    inspector = window.render_inspector_s10
    value = str(inspector.preset.currentData() or "custom")
    for key, button in getattr(window.render_workspace_s10, "ui09_preset_buttons", {}).items():
        button.blockSignals(True)
        button.setChecked(key == value)
        button.blockSignals(False)


def _select_preset(window, preset_id: str) -> None:
    inspector = window.render_inspector_s10
    index = inspector.preset.findData(str(preset_id))
    if index >= 0:
        inspector.preset.setCurrentIndex(index)
    _sync_preset_surface(window)


def _prepare_history(window, sidebar_layout: QVBoxLayout) -> None:
    history = window.render_history_s10
    shell_layout = window.foundation_shell.context.layout()
    if shell_layout is not None:
        shell_layout.removeWidget(history)
    history.setParent(window.render_workspace_s10.ui09_sidebar)

    for label in history.findChildren(QLabel):
        if label.text() in {"Render", "Antrian & riwayat attempt"}:
            label.hide()
    history.filter.hide()
    history_button = history.filter._buttons.get("history")
    if history_button is not None:
        history_button.setChecked(True)
    history.setStyleSheet("QListWidget{border:0;background:#FFFFFF;}")
    history.apply_jobs(window._s10_queue.jobs)
    sidebar_layout.addWidget(history, 1)



def _prepare_inspector_scroll(inspector) -> None:
    """Keep action controls visible while making dense settings scrollable.

    Moves only existing Qt layout items; all STEP10 widgets, signals, settings,
    disabled safety controls and render action owners remain unchanged.
    """
    root = inspector.layout()
    # Long hardware choices and native checkbox labels can impose a width
    # above the 1366px inspector dock. Shrink controls without removing or
    # replacing the underlying settings widgets.
    for field in (
        inspector.filename, inspector.output_folder, inspector.width,
        inspector.height, inspector.fps, inspector.video_codec,
        inspector.video_bitrate, inspector.audio_bitrate,
        inspector.sample_rate, inspector.hardware,
    ):
        field.setMinimumWidth(0)
        field.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
    for combo in (
        inspector.preset, inspector.fps, inspector.video_codec,
        inspector.audio_bitrate, inspector.sample_rate, inspector.hardware,
    ):
        combo.setMinimumContentsLength(8)
        combo.setSizeAdjustPolicy(
            combo.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
    # Native Windows QSpinBox minimumSizeHint can otherwise force the
    # two-column resolution row wider than the inspector's visible viewport.
    inspector.width.setMaximumWidth(118)
    inspector.height.setMaximumWidth(118)
    items = [root.takeAt(0) for _ in range(root.count())]
    start_index = next(
        (index for index, item in enumerate(items)
         if item.widget() is inspector.start),
        None,
    )
    if start_index is None or start_index < 2 or items[0].widget() is None:
        raise RuntimeError("UI-09 inspector structure did not match STEP10")

    settings_host = QWidget(inspector)
    settings_host.setObjectName("ui09InspectorSettings")
    settings_host.setStyleSheet("QWidget#ui09InspectorSettings{background:#FFFFFF;}")
    settings_layout = QVBoxLayout(settings_host)
    settings_layout.setContentsMargins(0, 7, 6, 7)
    settings_layout.setSpacing(8)
    for item in items[1:start_index]:
        _add_layout_item(settings_layout, item)
    settings_layout.addStretch(1)

    scroll = QScrollArea(inspector)
    scroll.setObjectName("ui09InspectorScroll")
    scroll.setStyleSheet("QScrollArea#ui09InspectorScroll{background:#FFFFFF;border:0;}")
    scroll.viewport().setStyleSheet("background:#FFFFFF;")
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(settings_host)

    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)
    _add_layout_item(root, items[0])
    root.addWidget(scroll, 1)
    # STEP10 render/cancel/pause widgets remain pinned to the bottom.
    # The trailing old spacer is intentionally omitted.
    for item in items[start_index:]:
        if item.spacerItem() is not None:
            continue
        _add_layout_item(root, item)

    inspector.ui09_scroll = scroll
    inspector.ui09_scroll_host = settings_host


def _prepare_inspector(window) -> None:
    inspector = window.render_inspector_s10
    if getattr(inspector, "_ui09_prepared", False):
        return

    for label in inspector.findChildren(QLabel):
        text = label.text()
        if text == "Pengaturan Render":
            label.setText("Pengaturan Output")
        elif text == "Preset":
            label.hide()
        elif text == "FPS":
            label.setText("Frame Rate (FPS)")
        elif text == "Encoder":
            label.setText("Accelerasi Hardware")
        elif text == "Video Bitrate":
            label.setText("Kualitas / Bitrate")
        elif text == "Audio Bitrate":
            label.setText("Audio Bitrate (AAC)")

    inspector.preset.hide()
    inspector.preflight.hide()
    inspector.start.setText("Render Sekarang")
    # Preserve 'auto' data/verified HW -> SW fallback behavior. Qt/Windows
    # otherwise derives an oversized minimum width from the longest text.
    auto_encoder = inspector.hardware.findData("auto")
    if auto_encoder >= 0:
        inspector.hardware.setItemText(auto_encoder, "Auto (HW → Software)")
        inspector.hardware.setItemData(
            auto_encoder,
            "Auto: gunakan hardware hanya jika terverifikasi, fallback ke software.",
            Qt.ItemDataRole.ToolTipRole,
        )

    root = inspector.layout()
    close_after = QCheckBox("Tutup aplikasi setelah render selesai")
    close_after.setEnabled(False)
    close_after.setToolTip(
        "Kontrol visual referensi. Auto-close belum diaktifkan karena safe close semantics belum menjadi kontrak STEP10."
    )
    index = root.indexOf(inspector.overwrite)
    root.insertWidget(index + 1 if index >= 0 else max(0, root.count() - 1), close_after)
    inspector.ui09_close_after = close_after
    inspector.overwrite.setToolTip(
        "Izinkan penggantian file output final yang sudah ada."
    )
    inspector.overwrite.setText("Timpa file final")
    # Native Windows QCheckBox.minimumSizeHint is sensitive to font metrics.
    # Keep the full semantics in an accessible tooltip and use a short label.
    close_after.setText("Tutup otomatis")
    close_after.setAccessibleName("Tutup aplikasi setelah render selesai")
    _prepare_inspector_scroll(inspector)
    inspector._ui09_prepared = True


def _prepare_center(window) -> None:
    workspace = window.render_workspace_s10
    if getattr(workspace, "_ui09_prepared", False):
        return

    root = workspace.layout()
    header = root.itemAt(0).layout() if root.count() else None
    grid = root.itemAt(1).layout() if root.count() > 1 else None

    for label in workspace.findChildren(QLabel):
        if label.text() == "Render Center":
            label.setText("Pusat Render")
        elif label.text() == "Snapshot immutable • Preflight • Verified output • Atomic finalize":
            label.setText("Ekspor video album musik Anda dengan aman dan profesional.")
        elif label.text() == "Antrian":
            label.setText("Antrean Render")

    workspace.snapshot_label.hide()

    if header is not None:
        preflight = FAMButton("🛡  Jalankan Preflight", kind="ghost")
        preflight.clicked.connect(window.render_inspector_s10.preflight.click)
        header.addWidget(preflight)
        workspace.ui09_preflight = preflight

    titles = {
        "media": "Media Lengkap",
        "snapshot": "Timeline Valid",
        "ffmpeg": "FFmpeg Siap",
        "output": "Output Folder",
        "disk": "Disk Space",
    }
    if grid is not None:
        encoder = workspace.preflight_cards.get("encoder")
        if encoder is not None:
            grid.removeWidget(encoder)
            encoder.hide()
        for column, key in enumerate(("media", "snapshot", "ffmpeg", "output", "disk")):
            card = workspace.preflight_cards.get(key)
            if card is None:
                continue
            grid.removeWidget(card)
            card.title.setText(titles[key])
            card.setMinimumHeight(88 if window.width() < 1500 else 154)
            grid.addWidget(card, 0, column)

    active_card = workspace.progress.parentWidget()
    if active_card is not None:
        active_card.hide()
    log_card = workspace.log_list.parentWidget()
    if log_card is not None:
        log_card.hide()
    workspace.queue_list.setMinimumHeight(225)
    workspace.queue_list.setSpacing(5)
    workspace.queue_list.setStyleSheet(
        "QListWidget{border:0;background:#F7FAFF;padding:3px;}"
        "QListWidget::item{border:0;margin:0;padding:0;}"
        "QListWidget::item:selected{background:transparent;}"
    )

    # Move the already-complete STEP10 workspace into a presentation row and
    # add the golden-style preset/history surface without changing shell context
    # ownership (the proven STEP10 context width remains zero).
    existing = []
    while root.count():
        existing.append(root.takeAt(0))

    center = QWidget(workspace)
    center_layout = QVBoxLayout(center)
    center_layout.setContentsMargins(10, 8, 10, 8)
    center_layout.setSpacing(7)
    for item in existing:
        _add_layout_item(center_layout, item)
    preflight_heading = QLabel("Hasil Preflight")
    preflight_heading.setObjectName("sectionHeading")
    center_layout.insertWidget(1, preflight_heading)
    center_layout.insertSpacing(1, 0 if window.width() < 1500 else 14)

    # Performance belongs below the queue in the golden visual hierarchy.
    graph = getattr(window, "render_performance_s10", None)
    if graph is not None:
        graph.setMinimumHeight(88 if window.width() < 1500 else 112)
        graph.setMaximumHeight(100 if window.width() < 1500 else 132)
        center_layout.removeWidget(graph)
        center_layout.addWidget(graph)

    sidebar = QFrame(workspace)
    sidebar.setObjectName("ui09RenderSidebar")
    # Golden viewport reserves a substantial preset/history rail; compact
    # layouts keep the smaller rail to avoid squeezing preflight/queue cards.
    desktop = window.width() >= 1500
    sidebar.setMinimumWidth(274 if desktop else 196)
    sidebar.setMaximumWidth(282 if desktop else 214)
    side = QVBoxLayout(sidebar)
    side.setContentsMargins(8, 8, 8, 8)
    side.setSpacing(6)

    title = QLabel("Preset Render")
    title.setObjectName("sectionHeading")
    side.addWidget(title)

    workspace.ui09_preset_buttons = {}
    for preset_id, label in _PRESET_SURFACE:
        button = QPushButton(label)
        button.setObjectName("tabButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setMinimumHeight(55)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#24385A;border:1px solid #DDE8F5;"
            "border-radius:7px;text-align:left;padding:7px 10px;font-size:11px;}"
            "QPushButton:checked{background:#E8F2FF;color:#075CE3;"
            "border-left:3px solid #0870F6;font-weight:700;}"
            "QPushButton:hover{border-color:#86B8FC;}"
        )
        button.clicked.connect(
            lambda _checked=False, value=preset_id: _select_preset(window, value)
        )
        side.addWidget(button)
        workspace.ui09_preset_buttons[preset_id] = button

    history_title = QLabel("Proyek Sebelumnya")
    history_title.setObjectName("sectionHeading")
    side.addWidget(history_title)
    workspace.ui09_sidebar = sidebar
    _prepare_history(window, side)

    host = QWidget(workspace)
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(sidebar)
    row.addWidget(center, 1)

    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(host, 1)
    workspace.ui09_center = center
    workspace.ui09_host = host
    workspace.ui09_compact = window.width() < 1500
    workspace._ui09_prepared = True
    # Initial STEP10 updates happen before the Render route is constructed.
    _present_queue(workspace, tuple(window._s10_queue.jobs))

    inspector = window.render_inspector_s10
    inspector.preset.currentIndexChanged.connect(lambda *_: _sync_preset_surface(window))
    _sync_preset_surface(window)


def _ensure_ui09(window) -> None:
    _prepare_inspector(window)
    _prepare_center(window)


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    if route != "render":
        return
    _ensure_ui09(self)
    self.render_history_s10.show()
    _sync_preset_surface(self)
    # Prior integration/remediation layers may finish a route resize one event
    # later. Reassert presentation only; no render state or settings are changed.
    QTimer.singleShot(
        0,
        lambda: (
            self.render_history_s10.show(),
            _sync_preset_surface(self),
        )
        if getattr(self, "foundation_state", None) is not None
        and self.foundation_state.workspace == "render"
        else None,
    )


def install_ui09_render_remediation() -> None:
    """UI-09 presentation parity without changing STEP10 render semantics."""
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow
    from .render_workspace_step10 import RenderCenterWorkspace

    _originals["apply_queue"] = RenderCenterWorkspace.apply_queue
    _originals["apply_job"] = RenderCenterWorkspace.apply_job
    RenderCenterWorkspace.apply_queue = _apply_queue_presentation
    RenderCenterWorkspace.apply_job = _apply_job_presentation
    _originals["window_route"] = FoundationMainWindow._s10_route
    FoundationMainWindow._s10_route = _window_route
    _installed = True
