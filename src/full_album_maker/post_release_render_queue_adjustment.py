from __future__ import annotations

"""Presentation-only alignment for UI-09 render queue rows.

All status/progress/duration values come from the existing RenderJob snapshot and
metrics. No queue ordering, lifecycle transition, cancellation, output opening,
or persistence behavior is changed here.
"""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .render_center_model_step10 import RenderJob, RenderJobState

_installed = False


def _format_clock(seconds: float) -> str:
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _job_duration_seconds(job: RenderJob) -> float:
    if int(job.snapshot.timebase) <= 0:
        return 0.0
    return float(job.snapshot.duration_tick) / float(job.snapshot.timebase)


class GoldenRenderQueueRow(QFrame):
    def __init__(self, job: RenderJob, number: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("goldenRenderQueueRow")
        running = job.state in {
            RenderJobState.RUNNING,
            RenderJobState.STARTING,
            RenderJobState.FINALIZING,
        }
        completed = job.state == RenderJobState.COMPLETED
        bg = "#EAF3FF" if running else "#FFFFFF"
        self.setStyleSheet(
            f"QFrame#goldenRenderQueueRow{{background:{bg};border:1px solid #D8E4F2;border-radius:8px;}}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(8)

        badge = QLabel(str(number))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(27, 27)
        badge_color = "#1766E8" if running or completed else "#526284"
        badge.setStyleSheet(
            f"background:{badge_color};color:white;border-radius:13px;font-weight:700;font-size:13px;"
        )
        row.addWidget(badge)

        thumb = QFrame()
        thumb.setFixedSize(92, 58)
        gradient = (
            "stop:0 #314F78, stop:.38 #F2A36B, stop:1 #6E5472" if number == 1
            else "stop:0 #305D7C, stop:.50 #8FB7C8, stop:1 #283D57" if number == 2
            else "stop:0 #728A55, stop:.50 #D8C17A, stop:1 #6A6F50"
        )
        thumb.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1," + gradient + ");border-radius:5px;"
        )
        row.addWidget(thumb)

        total_seconds = _job_duration_seconds(job)
        duration = _format_clock(total_seconds)
        codec = "H.265" if job.settings.video_codec == "h265" else "H.264"

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(1)
        name = QLabel(Path(job.settings.final_output).stem.replace(" - Full Album", ""))
        name.setStyleSheet("font-size:14px;font-weight:700;color:#10234A;")
        meta = QLabel(
            f"{job.settings.width} × {job.settings.height}  •  {duration}  •  {job.settings.container.upper()} ({codec})"
        )
        meta.setObjectName("metadata")
        if completed:
            state_text = "✓ Selesai"
            state_color = "#18A957"
        elif job.state == RenderJobState.QUEUED:
            state_text = "Menunggu antrean…"
            state_color = "#5C6B82"
        else:
            eta = float(job.metrics.eta_seconds or 0.0)
            state_text = "Rendering…" if eta <= 0 else f"Rendering…  •  Sisa sekitar {max(1, int(round(eta / 60.0)))} menit"
            state_color = "#1766E8"
        state = QLabel(state_text)
        state.setStyleSheet(f"font-size:12px;color:{state_color};")
        info.addWidget(name)
        info.addWidget(meta)
        info.addWidget(state)
        row.addLayout(info, 1)

        progress = QVBoxLayout()
        progress.setContentsMargins(0, 0, 0, 0)
        progress.setSpacing(3)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        percent = QLabel(f"{job.metrics.percent:.0f}%")
        percent.setStyleSheet(
            f"font-size:15px;font-weight:700;color:{'#18A957' if completed else '#1766E8'};"
        )
        top.addStretch(1)
        top.addWidget(percent)
        progress.addLayout(top)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(max(0.0, min(100.0, float(job.metrics.percent)))))
        bar.setTextVisible(False)
        bar.setFixedSize(190, 8)
        chunk = "#18A957" if completed else "#1766E8"
        bar.setStyleSheet(
            "QProgressBar{background:#E6EDF6;border:none;border-radius:4px;}"
            f"QProgressBar::chunk{{background:{chunk};border-radius:4px;}}"
        )
        progress.addWidget(bar)

        lower = QHBoxLayout()
        lower.setContentsMargins(0, 0, 0, 0)
        if running:
            elapsed = _format_clock(float(job.metrics.rendered_seconds or 0.0))
            total = _format_clock(total_seconds)
            timing = QLabel(f"{elapsed} / {total}")
            timing.setObjectName("metadata")
            lower.addWidget(timing)
            lower.addStretch(1)
            fps = QLabel(f"{float(job.metrics.fps or 0.0):.0f} fps")
            fps.setObjectName("metadata")
            lower.addWidget(fps)
        elif completed:
            lower.addStretch(1)
            fps = QLabel(f"{float(job.metrics.fps or 0.0):.0f} fps")
            fps.setObjectName("metadata")
            lower.addWidget(fps)
        else:
            lower.addStretch(1)
            waiting = QLabel("◷  Dalam antrean")
            waiting.setObjectName("metadata")
            lower.addWidget(waiting)
        progress.addLayout(lower)
        row.addLayout(progress)

        if running:
            pause = QPushButton("Ⅱ")
            pause.setToolTip("Pause belum tersedia pada render engine yang tervalidasi")
            pause.setEnabled(False)
            pause.setFixedSize(40, 36)
            pause.setStyleSheet(
                "QPushButton{background:#FFFFFF;border:1px solid #BFD3EC;border-radius:6px;color:#264B7D;font-weight:700;}"
            )
            stop = QPushButton("■")
            stop.setToolTip("Gunakan kontrol batal Render yang sudah tervalidasi")
            stop.setEnabled(False)
            stop.setFixedSize(40, 36)
            stop.setStyleSheet(
                "QPushButton{background:#FFFFFF;border:1px solid #BFD3EC;border-radius:6px;color:#526284;font-weight:700;}"
            )
            row.addWidget(pause)
            row.addWidget(stop)
        elif completed:
            open_output = QPushButton("▱  Buka Output")
            open_output.setToolTip("Gunakan aksi Buka Output yang tervalidasi di panel kanan")
            open_output.setEnabled(False)
            open_output.setFixedSize(118, 36)
            open_output.setStyleSheet(
                "QPushButton{background:#FFFFFF;border:1px solid #8CB9F3;border-radius:6px;color:#1766E8;font-weight:600;}"
            )
            row.addWidget(open_output)

        menu = QLabel("⋮")
        menu.setStyleSheet("font-size:19px;color:#5C6B82;")
        row.addWidget(menu)


def install_post_release_render_queue_adjustment() -> None:
    global _installed
    if _installed:
        return

    from . import post_release_pixel_match as pixel

    pixel._RenderQueueRow = GoldenRenderQueueRow
    original_apply = pixel.PixelMatchRenderCenterWorkspace.apply_queue

    def apply_queue_with_golden_geometry(self, jobs) -> None:
        original_apply(self, jobs)
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            item.setSizeHint(QSize(0, 76))
        card = self.queue_list.parentWidget()
        if card is not None:
            card.setMinimumHeight(300)
            card.setMaximumHeight(312)

    pixel.PixelMatchRenderCenterWorkspace.apply_queue = apply_queue_with_golden_geometry
    _installed = True
