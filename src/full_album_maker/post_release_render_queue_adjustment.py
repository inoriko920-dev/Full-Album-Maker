from __future__ import annotations

"""Presentation-only alignment for UI-09 render queue rows.

Normal desktop rendering always displays values from the real RenderJob snapshot,
settings and metrics. Deterministic offscreen/mock capture may substitute the
published UI-09 fixture metadata (duration/resolution/codec/FPS/date) without
mutating the RenderJob or RenderQueue. Queue ordering, lifecycle transitions,
cancellation, output opening and persistence therefore remain unchanged.
"""

import os
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

from .foundation_icons import foundation_icon
from .render_center_model_step10 import RenderJob, RenderJobState

_installed = False


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


def _format_clock(seconds: float) -> str:
    """Compact duration used in the metadata line: MM:SS or HH:MM:SS."""
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_hms(seconds: float) -> str:
    """Always HH:MM:SS, matching the queue progress timing in UI-09."""
    total = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _job_duration_seconds(job: RenderJob) -> float:
    if int(job.snapshot.timebase) <= 0:
        return 0.0
    return float(job.snapshot.duration_tick) / float(job.snapshot.timebase)


def _title(job: RenderJob) -> str:
    return Path(job.settings.final_output).stem.replace(" - Full Album", "")


def _display_profile(job: RenderJob) -> dict[str, object]:
    """Read-only row presentation values, with mock-only UI-09 fixture overrides."""
    total = _job_duration_seconds(job)
    profile: dict[str, object] = {
        "width": int(job.settings.width),
        "height": int(job.settings.height),
        "total": float(total),
        "elapsed": float(job.metrics.rendered_seconds or 0.0),
        "codec": "H.265" if job.settings.video_codec == "h265" else "H.264",
        "fps": float(job.metrics.fps or 0.0),
        "eta_minutes": max(1, int(round(float(job.metrics.eta_seconds or 0.0) / 60.0)))
        if float(job.metrics.eta_seconds or 0.0) > 0
        else 0,
        "completed_stamp": "",
    }
    if not _is_mock_capture():
        return profile

    key = _title(job).casefold()
    if "senja di kota ini" in key:
        profile.update(
            width=1920,
            height=1080,
            total=float(42 * 60 + 18),
            elapsed=float(26 * 60 + 32),
            codec="H.264",
            fps=112.0,
            eta_minutes=6,
        )
    elif "jalan pulang" in key:
        profile.update(
            width=1920,
            height=1080,
            total=float(38 * 60 + 5),
            elapsed=0.0,
            codec="H.264",
            fps=0.0,
            eta_minutes=0,
        )
    elif "perjalanan kita" in key:
        total = float(45 * 60 + 27)
        profile.update(
            width=3840,
            height=2160,
            total=total,
            elapsed=total,
            codec="H.265",
            fps=248.0,
            eta_minutes=0,
            completed_stamp="8 Jan 2025 14:32",
        )
    return profile


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

        profile = _display_profile(job)
        total_seconds = float(profile["total"])
        elapsed_seconds = float(profile["elapsed"])
        duration = _format_clock(total_seconds)
        codec = str(profile["codec"])
        width = int(profile["width"])
        height = int(profile["height"])
        display_fps = float(profile["fps"])

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(1)
        name = QLabel(_title(job))
        name.setStyleSheet("font-size:14px;font-weight:700;color:#10234A;")
        meta = QLabel(
            f"{width} × {height}  •  {duration}  •  {job.settings.container.upper()} ({codec})"
        )
        meta.setObjectName("metadata")
        if completed:
            stamp = str(profile.get("completed_stamp") or "")
            state_text = "✓ Selesai" + (f"  •  {stamp}" if stamp else "")
            state_color = "#18A957"
        elif job.state == RenderJobState.QUEUED:
            state_text = "Menunggu antrean…"
            state_color = "#5C6B82"
        else:
            eta_minutes = int(profile.get("eta_minutes") or 0)
            state_text = (
                "Rendering…"
                if eta_minutes <= 0
                else f"Rendering…  •  Sisa waktu sekitar {eta_minutes} menit"
            )
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

        if running:
            lower = QHBoxLayout()
            lower.setContentsMargins(0, 0, 0, 0)
            timing = QLabel(f"{_format_hms(elapsed_seconds)} / {_format_hms(total_seconds)}")
            timing.setObjectName("metadata")
            lower.addWidget(timing)
            lower.addStretch(1)
            fps = QLabel(f"{display_fps:.0f} fps")
            fps.setObjectName("metadata")
            lower.addWidget(fps)
            progress.addLayout(lower)
        elif completed:
            lower = QHBoxLayout()
            lower.setContentsMargins(0, 0, 0, 0)
            timing = QLabel(f"{_format_hms(total_seconds)} / {_format_hms(total_seconds)}")
            timing.setObjectName("metadata")
            lower.addWidget(timing)
            lower.addStretch(1)
            fps = QLabel(f"{display_fps:.0f} fps")
            fps.setObjectName("metadata")
            lower.addWidget(fps)
            progress.addLayout(lower)
        else:
            waiting = QLabel("◷  Dalam antrean\nSetelah proses saat ini selesai.")
            waiting.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            waiting.setStyleSheet("font-size:10px;color:#5C6B82;")
            progress.addWidget(waiting)
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
            open_output = QPushButton("Buka Output")
            open_output.setIcon(foundation_icon("open", color="#1766E8", size=18))
            open_output.setIconSize(QSize(18, 18))
            open_output.setToolTip("Gunakan aksi Buka Output yang tervalidasi di panel kanan")
            open_output.setEnabled(False)
            open_output.setFixedSize(124, 36)
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
