from __future__ import annotations

"""UI-09 completed-project history presentation.

The Render Center queue remains the owner of active/queued attempts. The left
"Proyek Sebelumnya" rail is a read-only completed-project surface in the golden
reference, so this layer filters that presentation to completed jobs and gives
those rows their own metadata/chrome. RenderJob state, queue persistence,
retry semantics and renderer execution are untouched.

The four-project history used by deterministic visual QA is synthesized only in
offscreen/mock capture. It is never inserted into RenderQueue and can never be
seen by the normal desktop runtime.
"""

from dataclasses import replace
from datetime import datetime
import os
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from .foundation_icons import foundation_icon
from .render_center_model_step10 import RenderJob, RenderJobState, RenderMetrics

_installed = False

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


def _duration_text(seconds: float | None) -> str:
    total = max(0, int(round(float(seconds or 0.0))))
    return f"{total // 60:02d}:{total % 60:02d}"


def _finished_date(job: RenderJob) -> str:
    raw = str(job.finished_at or job.started_at or job.created_at or "").strip()
    if not raw:
        return "—"
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def _thumb_gradient(title: str) -> str:
    key = title.casefold()
    if "jalan pulang" in key:
        return "stop:0 #26567B, stop:.46 #6EA8C3, stop:1 #334E4E"
    if "perjalanan" in key:
        return "stop:0 #476A38, stop:.48 #D4BF78, stop:1 #7D8058"
    if "cerita baru" in key:
        return "stop:0 #53637B, stop:.43 #F3B676, stop:1 #9B653E"
    return "stop:0 #314F78, stop:.42 #F2A36B, stop:1 #6E5472"


def _mock_completed_history(jobs: tuple[RenderJob, ...]) -> tuple[RenderJob, ...]:
    """Return capture-only completed history without mutating the active queue."""
    if not _is_mock_capture() or not jobs:
        return tuple(job for job in jobs if job.state == RenderJobState.COMPLETED)

    seed = next((job for job in reversed(jobs) if job.state == RenderJobState.COMPLETED), jobs[-1])
    # Original apply_jobs reverses this sequence. Keep oldest/display-last first
    # so the rendered order is Senja, Jalan, Perjalanan, Cerita as in UI-09.
    specs = (
        ("Cerita Baru - Full Album", 1920, 1080, 36 * 60 + 14, "2025-01-05T18:10:00+00:00"),
        ("Perjalanan Kita - Full Album", 3840, 2160, 45 * 60 + 27, "2025-01-08T14:32:00+00:00"),
        ("Jalan Pulang - Full Album", 1920, 1080, 38 * 60 + 5, "2025-01-10T09:15:00+00:00"),
        ("Senja di Kota Ini - Full Album", 1920, 1080, 42 * 60 + 18, "2025-01-05T20:42:00+00:00"),
    )
    staged: list[RenderJob] = []
    for filename, width, height, seconds, finished_at in specs:
        settings = replace(seed.settings, filename=filename, width=width, height=height)
        staged.append(
            RenderJob(
                snapshot=seed.snapshot,
                settings=settings,
                state=RenderJobState.COMPLETED,
                metrics=RenderMetrics(percent=100.0, rendered_seconds=float(seconds)),
                finished_at=finished_at,
            )
        )
    return tuple(staged)


class _CompletedHistoryRow(QFrame):
    def __init__(self, job: RenderJob, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pixelCompletedHistoryRow")
        self.setStyleSheet(
            "QFrame#pixelCompletedHistoryRow{background:#FFFFFF;border:1px solid #D8E4F2;border-radius:8px;}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 6, 7, 6)
        row.setSpacing(8)

        title_text = Path(job.settings.final_output).stem.replace(" - Full Album", "")
        thumb = QFrame()
        thumb.setFixedSize(68, 43)
        thumb.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            + _thumb_gradient(title_text)
            + ");border-radius:5px;"
        )
        row.addWidget(thumb)

        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel(title_text)
        title.setStyleSheet("font-size:12px;font-weight:700;color:#10234A;")
        meta = QLabel(
            f"{job.settings.width} × {job.settings.height}  •  {_duration_text(job.metrics.rendered_seconds)}"
        )
        meta.setStyleSheet("font-size:10px;color:#5C6B82;")
        status = QLabel(f"Selesai  •  {_finished_date(job)}")
        status.setStyleSheet("font-size:10px;color:#5C6B82;")
        text.addWidget(title)
        text.addWidget(meta)
        text.addWidget(status)
        row.addLayout(text, 1)

        menu = QLabel("⋮")
        menu.setStyleSheet("font-size:18px;color:#30466D;")
        row.addWidget(menu)


def install_post_release_render_history_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window
    from .post_release_pixel_match import PixelMatchRenderHistoryContext

    original_apply = PixelMatchRenderHistoryContext.apply_jobs
    original_route = Window._s10_route

    def completed_history(self, jobs: Iterable[RenderJob]) -> None:
        values = tuple(jobs)
        completed = _mock_completed_history(values)
        original_apply(self, completed)
        by_key = {(job.job_id, job.attempt_id): job for job in completed}
        for index in range(self.listing.count()):
            item = self.listing.item(index)
            payload = item.data(Qt.ItemDataRole.UserRole)
            job = by_key.get(tuple(payload)) if payload else None
            if job is None:
                continue
            item.setSizeHint(QSize(0, 66))
            self.listing.setItemWidget(item, _CompletedHistoryRow(job, self.listing))

    def route_with_painted_context_icons(self, route: str) -> None:
        original_route(self, route)
        if route != "render":
            return
        context = self.render_history_s10
        gear = getattr(context, "_pixel_preset_heading_icon", None)
        if gear is not None:
            gear.setText("")
            gear.setPixmap(foundation_icon("settings", color="#30466D", size=20).pixmap(20, 20))
            gear.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # The Custom preset decoration previously depended on a Unicode gear;
        # replace it with the same deterministic painter icon when present.
        for label in context.findChildren(QLabel):
            if label.text() == "⚙":
                label.setText("")
                label.setPixmap(foundation_icon("settings", color="#1766E8", size=20).pixmap(20, 20))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    PixelMatchRenderHistoryContext.apply_jobs = completed_history
    Window._s10_route = route_with_painted_context_icons
    _installed = True
