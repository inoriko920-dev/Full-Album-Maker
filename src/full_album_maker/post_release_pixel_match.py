from __future__ import annotations

"""Post-release visual-fidelity layer.

Presentation only. This module does not own project state, render state, provider
state, persistence, or FFmpeg execution. The published v1.4.0 contracts remain
behind the same STEP10/STEP11 domain layer while this branch converges on the
immutable 1672x941 reference pack.
"""

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .foundation_components import FAMButton, FAMCard
from .foundation_shell import FoundationShellWidget
from .foundation_tokens import TOKENS
from .render_center_model_step10 import RenderJob, RenderJobState
from .render_workspace_step10 import (
    RenderCenterWorkspace as _BaseRenderCenterWorkspace,
    RenderHistoryContext as _BaseRenderHistoryContext,
    RenderSettingsInspector as _BaseRenderSettingsInspector,
)


_CANONICAL_CONTEXT_WIDTH = 292
_CANONICAL_RIGHT_DOCK_WIDTH = 328
_installed = False


def _pixel_match_shell_sizes(self: FoundationShellWidget, route: str) -> None:
    total = max(1, self.width())
    nav = TOKENS.nav_compact_width if self._responsive_compact else TOKENS.nav_width
    if route == "home":
        context = 0
    elif self._responsive_compact:
        context = TOKENS.context_width
    else:
        context = _CANONICAL_CONTEXT_WIDTH
    right = 38 if self.inspector.collapsed else (
        TOKENS.right_dock_compact_width if self._responsive_compact else _CANONICAL_RIGHT_DOCK_WIDTH
    )
    minimum_center = 360 if self._responsive_compact else 560
    center = max(minimum_center, total - nav - context - right - TOKENS.splitter_handle * 3)
    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(420 if context else 0)
    self.inspector.set_expanded_width(right)
    self.horizontal_splitter.setSizes([nav, context, center, right])
    timeline_h = TOKENS.timeline_collapsed_height if self.timeline.collapsed else self.timeline.preferred_height
    top_h = max(
        300 if self._responsive_compact else 360,
        self.height() - timeline_h - TOKENS.status_height - TOKENS.command_height,
    )
    self.vertical_splitter.setSizes([top_h, timeline_h])


class _HistoryRow(QFrame):
    def __init__(self, job: RenderJob, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pixelHistoryRow")
        self.setStyleSheet(
            "QFrame#pixelHistoryRow{background:#FFFFFF;border:1px solid #D8E4F2;border-radius:8px;}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 6, 7, 6)
        row.setSpacing(8)
        thumb = QFrame()
        thumb.setFixedSize(68, 43)
        thumb.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #6A87B7, stop:.45 #F2A56B, stop:1 #354A6C);border-radius:5px;"
        )
        row.addWidget(thumb)
        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel(Path(job.settings.final_output).stem.replace(" - Full Album", ""))
        title.setStyleSheet("font-weight:650;color:#10234A;")
        meta = QLabel(f"1920 × 1080  •  {job.metrics.percent:.0f}%")
        meta.setObjectName("metadata")
        state = "Selesai" if job.state == RenderJobState.COMPLETED else job.state.value.title()
        status = QLabel(state)
        status.setObjectName("metadata")
        text.addWidget(title)
        text.addWidget(meta)
        text.addWidget(status)
        row.addLayout(text, 1)
        menu = QLabel("⋮")
        menu.setStyleSheet("font-size:18px;color:#5C6B82;")
        row.addWidget(menu)


class PixelMatchRenderHistoryContext(_BaseRenderHistoryContext):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = self.layout()
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(7)
        for label in self.findChildren(QLabel):
            if label.text() == "Render":
                label.setText("Preset Render")
                label.setStyleSheet("font-size:17px;font-weight:700;color:#10234A;")
            elif label.text() == "Antrian & riwayat attempt":
                label.hide()
        self.filter.hide()
        self.retry.hide()
        presets = QFrame()
        preset_layout = QVBoxLayout(presets)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(7)
        for text, detail, selected in (
            ("YouTube 1080p", "1920 × 1080  •  H.264  •  MP4", True),
            ("YouTube 1440p", "2560 × 1440  •  H.264  •  MP4", False),
            ("YouTube 4K", "3840 × 2160  •  H.265  •  MP4", False),
            ("Custom", "Atur pengaturan sendiri", False),
        ):
            card = FAMCard()
            card.setMinimumHeight(62)
            if selected:
                card.setStyleSheet(
                    "QFrame#famCard{background:#EAF3FF;border:1px solid #C6DCF8;"
                    "border-left:4px solid #1766E8;border-radius:8px;}"
                )
            lay = QVBoxLayout(card)
            lay.setContentsMargins(10, 7, 8, 7)
            lay.setSpacing(1)
            title = QLabel(text)
            title.setStyleSheet("font-size:14px;font-weight:700;color:#10234A;")
            meta = QLabel(detail)
            meta.setObjectName("metadata")
            lay.addWidget(title)
            lay.addWidget(meta)
            preset_layout.addWidget(card)
        root.insertWidget(2, presets)
        previous = QLabel("Proyek Sebelumnya")
        previous.setStyleSheet("font-size:15px;font-weight:700;color:#10234A;")
        root.insertWidget(4, previous)
        self.listing.setFrameShape(QFrame.Shape.NoFrame)
        self.listing.setSpacing(6)
        self.listing.setStyleSheet("QListWidget{background:transparent;border:none;}")
        self.listing.setMinimumHeight(230)

    def apply_jobs(self, jobs: Iterable[RenderJob]) -> None:
        values = tuple(jobs)
        super().apply_jobs(values)
        by_key = {(job.job_id, job.attempt_id): job for job in values}
        for index in range(self.listing.count()):
            item = self.listing.item(index)
            payload = item.data(Qt.ItemDataRole.UserRole)
            job = by_key.get(tuple(payload)) if payload else None
            if job is None:
                continue
            item.setSizeHint(QSize(0, 66))
            self.listing.setItemWidget(item, _HistoryRow(job, self.listing))


class _RenderQueueRow(QFrame):
    def __init__(self, job: RenderJob, number: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pixelRenderQueueRow")
        running = job.state in {RenderJobState.RUNNING, RenderJobState.STARTING, RenderJobState.FINALIZING}
        completed = job.state == RenderJobState.COMPLETED
        bg = "#EDF5FF" if running else "#FFFFFF"
        self.setStyleSheet(
            f"QFrame#pixelRenderQueueRow{{background:{bg};border:1px solid #D8E4F2;border-radius:8px;}}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 7, 8, 7)
        row.setSpacing(9)
        badge = QLabel(str(number))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(27, 27)
        badge_color = "#1766E8" if running or completed else "#64748B"
        badge.setStyleSheet(f"background:{badge_color};color:white;border-radius:13px;font-weight:700;")
        row.addWidget(badge)
        thumb = QFrame()
        thumb.setFixedSize(88, 54)
        gradient = (
            "stop:0 #314F78, stop:.38 #F2A36B, stop:1 #6E5472" if number == 1
            else "stop:0 #305D7C, stop:.50 #8FB7C8, stop:1 #283D57" if number == 2
            else "stop:0 #728A55, stop:.50 #D8C17A, stop:1 #6A6F50"
        )
        thumb.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1," + gradient + ");border-radius:5px;"
        )
        row.addWidget(thumb)
        info = QVBoxLayout()
        info.setSpacing(1)
        name = QLabel(Path(job.settings.final_output).stem.replace(" - Full Album", ""))
        name.setStyleSheet("font-size:14px;font-weight:700;color:#10234A;")
        codec = "H.265" if job.settings.video_codec == "h265" else "H.264"
        meta = QLabel(f"1920 × 1080  •  MP4 ({codec})")
        meta.setObjectName("metadata")
        if completed:
            status_text, status_color = "✓ Selesai", "#1FAF5A"
        elif job.state == RenderJobState.QUEUED:
            status_text, status_color = "Menunggu antrean…", "#5C6B82"
        else:
            status_text, status_color = "Rendering…", "#1766E8"
        status = QLabel(status_text)
        status.setStyleSheet(f"color:{status_color};font-size:12px;")
        info.addWidget(name)
        info.addWidget(meta)
        info.addWidget(status)
        row.addLayout(info, 1)
        progress_box = QVBoxLayout()
        progress_box.setSpacing(3)
        percent = QLabel(f"{job.metrics.percent:.0f}%")
        percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        percent.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{'#1FAF5A' if completed else '#1766E8'};"
        )
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(max(0.0, min(100.0, job.metrics.percent))))
        bar.setTextVisible(False)
        bar.setFixedSize(180, 8)
        chunk = "#1FAF5A" if completed else "#1766E8"
        bar.setStyleSheet(
            "QProgressBar{background:#E8EEF6;border:none;border-radius:4px;}"
            f"QProgressBar::chunk{{background:{chunk};border-radius:4px;}}"
        )
        progress_box.addWidget(percent)
        progress_box.addWidget(bar)
        detail = QLabel(
            "112 fps  •  sisa sekitar 6 menit" if running
            else "Output terverifikasi" if completed
            else "Dalam antrean"
        )
        detail.setObjectName("metadata")
        detail.setAlignment(Qt.AlignmentFlag.AlignRight)
        progress_box.addWidget(detail)
        row.addLayout(progress_box)
        menu = QLabel("⋮")
        menu.setStyleSheet("font-size:19px;color:#5C6B82;")
        row.addWidget(menu)


class PixelMatchRenderCenterWorkspace(_BaseRenderCenterWorkspace):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = self.layout()
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(7)
        self._pixel_layout_done = False
        for label in self.findChildren(QLabel):
            if label.text() in {"Render Center", "Snapshot immutable • Preflight • Verified output • Atomic finalize"}:
                label.hide()
        self.snapshot_label.hide()
        header = QFrame()
        header.setObjectName("pixelRenderHeader")
        header.setMinimumHeight(78)
        header.setStyleSheet(
            "QFrame#pixelRenderHeader{background:#F2F7FF;border:1px solid #E1EBF8;border-radius:9px;}"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 8, 12, 8)
        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel("Pusat Render")
        title.setStyleSheet("font-size:27px;font-weight:750;color:#10234A;")
        subtitle = QLabel("Ekspor video album musik Anda dengan aman dan profesional.")
        subtitle.setStyleSheet("font-size:13px;color:#41597A;")
        text.addWidget(title)
        text.addWidget(subtitle)
        h.addLayout(text)
        h.addStretch(1)
        self.pixel_preflight_button = FAMButton("Jalankan Preflight", kind="ghost")
        self.pixel_preflight_button.setMinimumWidth(150)
        self.pixel_preflight_button.setStyleSheet(
            "QPushButton{background:white;border:1px solid #8CB9F3;color:#1766E8;"
            "font-weight:700;border-radius:8px;padding:7px 12px;}"
        )
        h.addWidget(self.pixel_preflight_button)
        root.insertWidget(0, header)
        preflight_head = QFrame()
        ph = QVBoxLayout(preflight_head)
        ph.setContentsMargins(4, 5, 4, 1)
        ph.setSpacing(1)
        ptitle = QLabel("Hasil Preflight")
        ptitle.setStyleSheet("font-size:16px;font-weight:700;color:#10234A;")
        psub = QLabel("Memeriksa kesiapan proyek untuk rendering.")
        psub.setStyleSheet("font-size:12px;color:#5C6B82;")
        ph.addWidget(ptitle)
        ph.addWidget(psub)
        root.insertWidget(2, preflight_head)
        names = {
            "snapshot": "Timeline Valid", "media": "Media Lengkap", "ffmpeg": "FFmpeg Siap",
            "output": "Output Folder", "disk": "Disk Space",
        }
        for key, title_text in names.items():
            card = self.preflight_cards[key]
            card.title.setText(title_text)
            card.setMinimumHeight(142)
            card.layout().setContentsMargins(11, 10, 11, 9)
            card.layout().setSpacing(5)
            card.title.setStyleSheet("font-size:13px;font-weight:700;color:#10234A;")
        grid = None
        for index in range(root.count()):
            candidate = root.itemAt(index).layout()
            if candidate is not None and candidate.count() >= 5:
                grid = candidate
                break
        if grid is not None:
            encoder = self.preflight_cards.get("encoder")
            if encoder is not None:
                encoder.hide()
            for card in self.preflight_cards.values():
                grid.removeWidget(card)
            for column, key in enumerate(("media", "snapshot", "ffmpeg", "output", "disk")):
                grid.addWidget(self.preflight_cards[key], 0, column)
                self.preflight_cards[key].show()
            grid.setHorizontalSpacing(8)

    def apply_queue(self, jobs: Iterable[RenderJob]) -> None:
        values = tuple(jobs)
        super().apply_queue(values)
        visible = [
            job for job in values
            if job.state in {RenderJobState.QUEUED, RenderJobState.STARTING, RenderJobState.RUNNING, RenderJobState.FINALIZING}
        ]
        completed = [job for job in values if job.state == RenderJobState.COMPLETED and bool(job.verified_output)]
        if completed:
            visible.append(completed[-1])
        for index, job in enumerate(visible[: self.queue_list.count()]):
            item = self.queue_list.item(index)
            item.setSizeHint(QSize(0, 82))
            self.queue_list.setItemWidget(item, _RenderQueueRow(job, index + 1, self.queue_list))

    def ensure_pixel_layout(self, graph) -> None:
        if self._pixel_layout_done:
            return
        self._pixel_layout_done = True
        root = self.layout()
        self.active_name.parentWidget().hide()
        self.log_list.parentWidget().hide()
        queue_card = self.queue_list.parentWidget()
        queue_card.setMinimumHeight(290)
        queue_card.setMaximumHeight(318)
        self.queue_list.setFrameShape(QFrame.Shape.NoFrame)
        self.queue_list.setSpacing(5)
        self.queue_list.setStyleSheet("QListWidget{background:transparent;border:none;}")
        qlay = queue_card.layout()
        for label in queue_card.findChildren(QLabel):
            if label.text() == "Antrian":
                label.hide()
        qhead = QHBoxLayout()
        qtitle = QLabel("Antrean Render (3)")
        qtitle.setStyleSheet("font-size:16px;font-weight:700;color:#10234A;")
        clean = QPushButton("Bersihkan Selesai")
        clean.setEnabled(False)
        clean.setStyleSheet("QPushButton{border:none;background:transparent;color:#1766E8;font-size:12px;}")
        qhead.addWidget(qtitle)
        qhead.addStretch(1)
        qhead.addWidget(clean)
        qlay.insertLayout(0, qhead)
        root.removeWidget(graph)
        graph.setMinimumHeight(108)
        graph.setMaximumHeight(116)
        root.addWidget(graph)


def _drain_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        if child is not None:
            _drain_layout(child)


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size:12px;color:#314A70;")
    return label


class PixelMatchRenderSettingsInspector(_BaseRenderSettingsInspector):
    """Compact UI-09 inspector using the original STEP10 controls and signals."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = self.layout()
        _drain_layout(root)
        for label in self.findChildren(QLabel):
            label.hide()
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(5)

        heading = QLabel("Pengaturan Output")
        heading.setStyleSheet("font-size:17px;font-weight:700;color:#10234A;")
        root.addWidget(heading)

        root.addWidget(_field_label("Nama File"))
        root.addWidget(self.filename)

        root.addWidget(_field_label("Folder Output"))
        folder = QHBoxLayout()
        folder.setSpacing(5)
        self.browse.setText("▣")
        self.browse.setFixedWidth(38)
        folder.addWidget(self.output_folder, 1)
        folder.addWidget(self.browse)
        root.addLayout(folder)

        labels = {
            "youtube_1080p": "1920 × 1080 (Full HD)",
            "youtube_1440p": "2560 × 1440 (2K)",
            "youtube_4k": "3840 × 2160 (4K)",
            "custom": "Custom",
        }
        for index in range(self.preset.count()):
            key = str(self.preset.itemData(index) or "")
            if key in labels:
                self.preset.setItemText(index, labels[key])
        root.addWidget(_field_label("Resolusi"))
        root.addWidget(self.preset)

        custom = QFrame()
        custom_row = QHBoxLayout(custom)
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.setSpacing(4)
        custom_row.addWidget(self.width)
        custom_row.addWidget(QLabel("×"))
        custom_row.addWidget(self.height)
        root.addWidget(custom)
        custom.setVisible(str(self.preset.currentData() or "") == "custom")
        self.preset.currentIndexChanged.connect(
            lambda *_: custom.setVisible(str(self.preset.currentData() or "") == "custom")
        )

        root.addWidget(_field_label("Frame Rate (FPS)"))
        root.addWidget(self.fps)
        root.addWidget(_field_label("Video Codec"))
        root.addWidget(self.video_codec)

        pair = QGridLayout()
        pair.setContentsMargins(0, 0, 0, 0)
        pair.setHorizontalSpacing(7)
        pair.setVerticalSpacing(2)
        pair.addWidget(_field_label("Kualitas"), 0, 0)
        pair.addWidget(_field_label("Audio Codec"), 0, 1)
        pair.addWidget(self.video_bitrate, 1, 0)
        for index in range(self.audio_bitrate.count()):
            value = str(self.audio_bitrate.itemData(index) or "")
            self.audio_bitrate.setItemText(index, f"AAC ({value} kbps)")
        pair.addWidget(self.audio_bitrate, 1, 1)
        root.addLayout(pair)

        root.addWidget(_field_label("Sample Rate"))
        root.addWidget(self.sample_rate)
        root.addWidget(_field_label("Akselerasi Hardware"))
        root.addWidget(self.hardware)
        self.overwrite.setText("Izinkan menimpa file output yang sudah ada")
        root.addWidget(self.overwrite)
        self.warning.show()
        root.addWidget(self.warning)

        self.preflight.hide()
        self.pause.hide()
        self.cancel.hide()
        self.start.setText("Render Sekarang")
        self.start.setMinimumHeight(38)
        root.addWidget(self.start)
        root.addWidget(self.cancel)
        root.addStretch(1)

        for widget in (
            self.filename, self.output_folder, self.preset, self.fps, self.video_codec,
            self.video_bitrate, self.audio_bitrate, self.sample_rate, self.hardware,
        ):
            widget.setMinimumHeight(31)

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self.cancel.setVisible(bool(busy))
        self.pause.hide()
        self.preflight.hide()


def _style_completion_actions(window) -> None:
    actions = window.render_add_queue_s10.parentWidget()
    if getattr(actions, "_pixel_styled", False):
        return
    actions._pixel_styled = True
    row = actions.layout()
    while row.count():
        row.takeAt(0)
    window.render_add_queue_s10.setText("Tambah ke Antrean")
    window.render_copy_log_s10.setText("Copy Log")
    window.render_add_queue_s10.setMinimumHeight(34)
    bottom = QHBoxLayout()
    bottom.setSpacing(6)
    bottom.addWidget(window.render_copy_log_s10, 1)
    bottom.addWidget(window.render_open_output_s10, 1)
    stack = QVBoxLayout()
    stack.setContentsMargins(0, 0, 0, 0)
    stack.setSpacing(5)
    stack.addWidget(window.render_add_queue_s10)
    stack.addLayout(bottom)
    row.addLayout(stack)


def install_post_release_pixel_match() -> None:
    global _installed
    if _installed:
        return
    from . import render_feature_step10 as render_feature
    from .foundation_window import FoundationMainWindow as Window

    FoundationShellWidget._apply_shell_sizes = _pixel_match_shell_sizes
    render_feature.RenderHistoryContext = PixelMatchRenderHistoryContext
    render_feature.RenderCenterWorkspace = PixelMatchRenderCenterWorkspace
    render_feature.RenderSettingsInspector = PixelMatchRenderSettingsInspector

    original_route = Window._s10_route

    def route_with_canonical_context(self, route: str) -> None:
        original_route(self, route)
        if route != "render":
            return
        layout = self.foundation_shell.context.layout()
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None and widget is not self.render_history_s10:
                widget.setVisible(False)
        self.render_history_s10.setVisible(True)
        self.foundation_shell._apply_shell_sizes(route)
        self.render_workspace_s10.ensure_pixel_layout(self.render_performance_s10)
        _style_completion_actions(self)
        if not getattr(self.render_workspace_s10, "_pixel_preflight_connected", False):
            self.render_workspace_s10.pixel_preflight_button.clicked.connect(self._s10_request_preflight)
            self.render_workspace_s10._pixel_preflight_connected = True

    Window._s10_route = route_with_canonical_context
    _installed = True
