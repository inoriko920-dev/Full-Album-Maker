from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .foundation_components import FAMButton

_installed = False
_originals: dict[str, Any] = {}


_PRESET_SURFACE = (
    ("youtube_1080p", "▶  YouTube 1080p\n1920 × 1080 • H.264 • MP4"),
    ("youtube_1440p", "▶  YouTube 1440p\n2560 × 1440 • H.264 • MP4"),
    ("youtube_4k", "▶  YouTube 4K\n3840 × 2160 • H.265 • MP4"),
    ("custom", "⚙  Custom\nAtur pengaturan sendiri"),
)


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

    root = inspector.layout()
    close_after = QCheckBox("Tutup aplikasi setelah render selesai")
    close_after.setEnabled(False)
    close_after.setToolTip(
        "Kontrol visual referensi. Auto-close belum diaktifkan karena safe close semantics belum menjadi kontrak STEP10."
    )
    index = root.indexOf(inspector.overwrite)
    root.insertWidget(index + 1 if index >= 0 else max(0, root.count() - 1), close_after)
    inspector.ui09_close_after = close_after
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
            card.setMinimumHeight(82)
            grid.addWidget(card, 0, column)

    active_card = workspace.progress.parentWidget()
    if active_card is not None:
        active_card.hide()
    log_card = workspace.log_list.parentWidget()
    if log_card is not None:
        log_card.hide()
    workspace.queue_list.setMinimumHeight(190)

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

    # Performance belongs below the queue in the golden visual hierarchy.
    graph = getattr(window, "render_performance_s10", None)
    if graph is not None:
        center_layout.removeWidget(graph)
        center_layout.addWidget(graph)

    sidebar = QFrame(workspace)
    sidebar.setObjectName("ui09RenderSidebar")
    sidebar.setMinimumWidth(196)
    sidebar.setMaximumWidth(214)
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
        button.setMinimumHeight(48)
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
    workspace._ui09_prepared = True

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

    _originals["window_route"] = FoundationMainWindow._s10_route
    FoundationMainWindow._s10_route = _window_route
    _installed = True
