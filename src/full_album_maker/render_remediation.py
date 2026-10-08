from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QSize, QTimer
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .foundation_components import FAMButton
from .render_center_model_step10 import RenderJobState

_installed = False
_originals: dict[str, Any] = {}


_PRESET_SURFACE = (
    ("youtube_1080p", "YouTube 1080p\n1920 × 1080 • H.264 • MP4"),
    ("youtube_1440p", "YouTube 1440p\n2560 × 1440 • H.264 • MP4"),
    ("youtube_4k", "YouTube 4K\n3840 × 2160 • H.265 • MP4"),
    ("custom", "Custom\nAtur pengaturan sendiri"),
)


def _ui09_preset_icon(preset_id: str) -> QPixmap:
    """Deterministic YouTube/gear symbols; never rely on font emoji glyphs.

    The labels, preset ids and STEP10 settings owner remain unchanged.
    Dimensions match the original desktop 9th golden's prominent red
    YouTube branding without embedding that reference as an application asset.
    """
    pixmap = QPixmap(36, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if preset_id.startswith("youtube_"):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E91726"))
        painter.drawRoundedRect(2, 5, 32, 22, 6, 6)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPolygon(QPolygon([
            QPoint(16, 11), QPoint(16, 21), QPoint(25, 16),
        ]))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#173F9A"), 2.4))
        painter.drawEllipse(10, 8, 16, 16)
        painter.drawEllipse(15, 13, 6, 6)
        for x1, y1, x2, y2 in (
            (18, 2, 18, 8), (18, 24, 18, 30),
            (4, 16, 10, 16), (26, 16, 32, 16),
            (8, 6, 12, 10), (24, 22, 28, 26),
            (8, 26, 12, 22), (24, 10, 28, 6),
        ):
            painter.drawLine(x1, y1, x2, y2)
    painter.end()
    return pixmap


# UI-09 queue cards read state exclusively from STEP10 RenderJob/RenderQueue.
# They do not have their own job model or rendering lifecycle.
_QUEUE_ACTIVE = frozenset({
    RenderJobState.QUEUED,
    RenderJobState.STARTING,
    RenderJobState.RUNNING,
    RenderJobState.FINALIZING,
})



_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def _job_cover_path(job) -> Path | None:
    """Use a real, local cover from the frozen project; never invent artwork."""
    try:
        document = job.snapshot.document()
        assets = document.asset_map()
        songs = [song for song in document.playlist.entries if song.enabled]
        name = job.settings.filename.casefold()
        matching = [
            song for song in songs
            if song.display_title and song.display_title.casefold() in name
        ]
        for song in matching + [song for song in songs if song not in matching]:
            for asset_id in (song.cover_asset_id, song.visual_asset_id):
                asset = assets.get(asset_id) if asset_id else None
                if asset is None or asset.kind != "image":
                    continue
                path = Path(asset.locator)
                if (path.suffix.casefold() in _IMAGE_SUFFIXES
                    and path.is_file()
                    and 0 < path.stat().st_size <= 16 * 1024 * 1024):
                    return path
    except (OSError, ValueError, TypeError, KeyError):
        return None
    return None


class _JobCoverThumb(QLabel):
    """Small, safe image preview; an audio icon when no source cover exists."""

    def __init__(self, job, *, compact: bool = False, parent=None):
        super().__init__(parent)
        size = QSize(60, 44) if compact else QSize(78, 52)
        self.setObjectName("ui09JobCoverThumb")
        self.setFixedSize(size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel#ui09JobCoverThumb{background:#E7F1FF;color:#1665D8;"
            "border:1px solid #CEE2FB;border-radius:6px;"
            "font-size:23px;font-weight:700;}"
        )
        self.source_path = None
        path = _job_cover_path(job)
        if path is not None:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            reader.setScaledSize(QSize(size.width() * 2, size.height() * 2))
            image = reader.read()
            if not image.isNull():
                cover = QPixmap.fromImage(image).scaled(
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                left = max(0, (cover.width() - size.width()) // 2)
                top = max(0, (cover.height() - size.height()) // 2)
                self.setPixmap(cover.copy(left, top, size.width(), size.height()))
                self.source_path = str(path)
                self.setAccessibleName("Sampul proyek dari file media")
                return
        # Keep the semantic placeholder string for the existing STEP10
        # consumer/tests, but draw the icon ourselves. Missing-glyph squares
        # are otherwise visible on Windows hosts without musical-symbol fonts.
        self.setText("♫")
        self.setAccessibleName("Placeholder musik: tidak ada sampul proyek")

    def paintEvent(self, event) -> None:
        if self.source_path is not None:
            # A verified file-backed image is never modified or substituted.
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width() / 78.0, self.height() / 52.0)
        painter.setPen(QPen(QColor("#CEE2FB"), 1))
        painter.setBrush(QColor("#E7F1FF"))
        painter.drawRoundedRect(0, 0, 77, 51, 6, 6)

        # Two connected eighth notes, centered in the actual preview box.
        # All geometry is Qt-painted, independent of emoji/font availability.
        ink = QColor("#1665D8")
        painter.setBrush(ink)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(27, 31, 11, 8)
        painter.drawEllipse(42, 26, 11, 8)
        painter.setPen(QPen(ink, 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(37, 34, 37, 15)
        painter.drawLine(52, 29, 52, 11)
        painter.drawLine(37, 15, 52, 11)
        painter.end()


class _RenderHistoryCard(QFrame):
    """Read-only visual surface over the original clickable history item."""

    def __init__(self, job, *, compact=False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ui09HistoryCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "QFrame#ui09HistoryCard{background:#FFFFFF;border:1px solid #E1EBF7;"
            "border-radius:7px;}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)
        self.cover = _JobCoverThumb(job, compact=compact, parent=self)
        row.addWidget(self.cover)
        details = QVBoxLayout()
        details.setSpacing(2)
        self.title = QLabel(Path(job.settings.final_output).stem)
        self.title.setStyleSheet("font-size:11px;font-weight:700;color:#17294F;")
        self.title.setWordWrap(False)
        self.title.setToolTip(str(job.settings.final_output))
        self.format = QLabel(
            f"{job.settings.width} × {job.settings.height}  · "
            f"{job.settings.container.upper()}"
        )
        self.format.setStyleSheet("font-size:10px;color:#58739B;")
        done = job.state == RenderJobState.COMPLETED and bool(job.verified_output)
        self.status = QLabel(
            "Selesai · Terverifikasi" if done else job.state.value
        )
        self.status.setStyleSheet(
            "font-size:10px;color:#19985A;" if done
            else "font-size:10px;color:#6A7C96;"
        )
        details.addWidget(self.title)
        details.addWidget(self.format)
        details.addWidget(self.status)
        row.addLayout(details, 1)


def _present_history_cards(history) -> None:
    jobs = {
        (job.job_id, job.attempt_id): job
        for job in history._last_jobs
    }
    listing = history.listing
    for index in range(listing.count()):
        item = listing.item(index)
        job = jobs.get(item.data(Qt.ItemDataRole.UserRole))
        if job is None:
            continue
        item.setSizeHint(QSize(0, 64))
        card = _RenderHistoryCard(
            job, compact=listing.viewport().width() < 250, parent=listing
        )
        listing.setItemWidget(item, card)


def _apply_history_presentation(self, jobs) -> None:
    _originals["history_apply_jobs"](self, jobs)
    if getattr(self, "_ui09_history_prepared", False):
        _present_history_cards(self)


def _visible_queue_jobs(jobs):
    active = [job for job in jobs if job.state in _QUEUE_ACTIVE]
    completed = [
        job for job in jobs
        if job.state == RenderJobState.COMPLETED and bool(job.verified_output)
    ]
    if completed:
        active.append(completed[-1])
    return active


def _job_display_title(final_output: Path) -> str:
    """Short UI label only; retain the actual output filename and tooltip."""
    stem = final_output.stem
    suffix = " - Full Album"
    if stem.casefold().endswith(suffix.casefold()) and len(stem) > len(suffix):
        return stem[:-len(suffix)]
    return stem


class _UI09QueueProgressDetail(QLabel):
    """Draw queue status markers independent of Windows glyph coverage.

    The existing STEP10 job card remains sole owner of the raw semantic
    string. This class only changes how the two known, non-freeform status
    strings are displayed. Other text (including ETA and unverified state)
    is delegated to QLabel without modification.
    """

    def paintEvent(self, event) -> None:
        raw = self.text()
        if raw == "✓ File terverifikasi":
            caption, color, marker = "File terverifikasi", QColor("#148742"), "verified"
        elif raw == "◷ Dalam antrean":
            caption, color, marker = "Dalam antrean", QColor("#607EA8"), "queued"
        else:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        icon = 10
        gap = 4
        text_width = painter.fontMetrics().horizontalAdvance(caption)
        left = self.width() - text_width - icon - gap
        if left < 0:
            painter.end()
            super().paintEvent(event)
            return
        cy = self.height() // 2
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if marker == "verified":
            # Simple rounded check shield, never a font checkmark or a fake
            # output-verification claim. The actual text only comes from
            # RenderJob.COMPLETED with verified_output.
            painter.drawEllipse(left, cy - 5, 10, 10)
            painter.drawLine(left + 2, cy, left + 4, cy + 2)
            painter.drawLine(left + 4, cy + 2, left + 8, cy - 3)
        else:
            painter.drawEllipse(left, cy - 5, 10, 10)
            painter.drawLine(left + 5, cy - 3, left + 5, cy)
            painter.drawLine(left + 5, cy, left + 8, cy + 2)

        painter.setPen(color)
        painter.drawText(
            QRect(left + icon + gap, 0, self.width() - (left + icon + gap),
                  self.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            caption,
        )
        painter.end()


class _QueueJobCard(QFrame):
    """Render-only card; progress updates come from the engine job."""

    def __init__(self, job, position: int, *, compact=False, parent=None) -> None:
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
        self.number = number
        self.cover = _JobCoverThumb(job, compact=compact, parent=self)
        layout.addWidget(self.cover)

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
        self.progress_detail = _UI09QueueProgressDetail()
        self.progress_detail.setObjectName("ui09QueueProgressDetail")
        self.progress_detail.setStyleSheet("font-size:9px;color:#607EA8;")
        self.progress_detail.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        progress_column.addWidget(self.progress_detail)
        layout.addLayout(progress_column, 2)
        self.refresh(job)

    def refresh(self, job) -> None:
        final_output = Path(job.settings.final_output)
        name = _job_display_title(final_output)
        self.heading.setText(name)
        self.heading.setToolTip(final_output.name)
        self.setAccessibleName(f"Antrean render: {final_output.stem}")
        settings = job.settings
        self.details.setText(
            f"{settings.width} × {settings.height}  •  "
            f"{settings.container.upper()}  •  {settings.video_codec.upper()}"
        )
        percent = max(0.0, min(100.0, float(job.metrics.percent)))
        self.percent.setText(f"{percent:.0f}%")
        self.bar.setValue(round(percent * 10))
        running = job.state in {
            RenderJobState.RUNNING, RenderJobState.STARTING,
            RenderJobState.FINALIZING,
        }
        self.setStyleSheet(
            "QFrame#ui09QueueJobCard{"
            + ("background:#E8F2FF;border:1px solid #D5E8FF;"
               if running else "background:#FFFFFF;border:1px solid #DCE8F7;")
            + "border-radius:8px;} "
              "QProgressBar{background:#E8EEF7;border:0;border-radius:4px;}"
              "QProgressBar::chunk{background:#1672ED;border-radius:4px;}"
        )
        self.number.setStyleSheet(
            "background:#687793;color:white;border-radius:12px;font-weight:700;"
            if job.state == RenderJobState.QUEUED else
            "background:#0868EB;color:white;border-radius:12px;font-weight:700;"
        )
        self.progress_detail.setText("")
        self.state.setStyleSheet("font-size:10px;color:#52729A;")
        self.progress_detail.setStyleSheet("font-size:9px;color:#607EA8;")
        if job.state == RenderJobState.COMPLETED and bool(job.verified_output):
            self.state.setText("SELESAI")
            self.state.setStyleSheet("font-size:10px;color:#148742;font-weight:700;")
            self.note.setText("Output terverifikasi")
            self.progress_detail.setText("✓ File terverifikasi")
            self.progress_detail.setStyleSheet("font-size:9px;color:#148742;")
            self.bar.setStyleSheet("QProgressBar::chunk{background:#16A34A;}")
            self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#159447;")
        elif job.state == RenderJobState.QUEUED:
            self.state.setText("ANTREAN")
            self.note.setText("Menunggu giliran render")
            self.progress_detail.setText("◷ Dalam antrean")
            self.bar.setStyleSheet("QProgressBar::chunk{background:#BAC8DC;}")
            self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#0868EB;")
        else:
            self.state.setText(job.state.value)
            if job.state == RenderJobState.COMPLETED:
                # State alone never proves the final output was verified.
                self.note.setText("Verifikasi output belum tersedia")
                self.progress_detail.setText("Belum terverifikasi")
                self.bar.setStyleSheet("QProgressBar::chunk{background:#BAC8DC;}")
                self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#607EA8;")
                return
            self.bar.setStyleSheet("QProgressBar::chunk{background:#1672ED;}")
            self.percent.setStyleSheet("font-size:12px;font-weight:700;color:#0868EB;")
            fps = job.metrics.fps
            self.note.setText(
                "Sedang merender" if fps is None else f"Sedang merender  •  {fps:.0f} fps"
            )
            eta = job.metrics.eta_seconds
            if eta is not None and eta >= 0:
                remaining = round(eta)
                self.progress_detail.setText(
                    f"Estimasi sisa {remaining // 60:02d}:{remaining % 60:02d}"
                )


def _ui09_queue_row_height(*, compact: bool) -> int:
    # Windows Qt has a slightly smaller queue viewport than Linux Qt.
    # Keep the original 5px inter-row spacing to preserve golden alignment.
    # The cover/icon and progress widgets fit inside these heights.
    if sys.platform == "win32":
        return 65 if compact else 76
    return 68 if compact else 78


def _present_queue(workspace, jobs) -> None:
    widgets = {}
    for index, job in enumerate(_visible_queue_jobs(jobs)):
        item = workspace.queue_list.item(index)
        if item is None:
            break
        item.setSizeHint(QSize(
            0, _ui09_queue_row_height(
                compact=bool(getattr(workspace, "ui09_compact", False))
            ),
        ))
        card = _QueueJobCard(
            job, index + 1,
            compact=bool(getattr(workspace, "ui09_compact", False)),
            parent=workspace.queue_list,
        )
        workspace.queue_list.setItemWidget(item, card)
        widgets[(job.job_id, job.attempt_id)] = card
    workspace.ui09_queue_widgets = widgets


def _apply_queue_presentation(self, jobs) -> None:
    jobs = tuple(jobs)
    _originals["apply_queue"](self, jobs)
    # Last STEP10 job snapshots for repaint; never a second queue owner.
    self._ui09_last_jobs = jobs
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
    history._ui09_history_prepared = True
    _present_history_cards(history)
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


def _ui09_preflight_icon(kind: str) -> QPixmap:
    """Draw decorative vector icons, independent of platform emoji fonts."""
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#0967EB"), 2.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "media":
        painter.drawRoundedRect(9, 3, 17, 25, 2, 2)
        painter.drawLine(13, 11, 22, 11)
        painter.drawLine(13, 16, 22, 16)
        painter.drawLine(13, 21, 20, 21)
    elif kind == "snapshot":
        for y in (8, 16, 24):
            painter.drawEllipse(5, y - 2, 3, 3)
            painter.drawLine(12, y, 28, y)
    elif kind == "ffmpeg":
        painter.drawRoundedRect(9, 9, 15, 15, 2, 2)
        for pos in (12, 20):
            painter.drawLine(pos, 4, pos, 9)
            painter.drawLine(pos, 24, pos, 29)
            painter.drawLine(4, pos, 9, pos)
            painter.drawLine(24, pos, 29, pos)
    elif kind == "output":
        painter.drawLine(4, 10, 13, 10)
        painter.drawLine(13, 10, 16, 13)
        painter.drawRoundedRect(4, 12, 25, 15, 2, 2)
    elif kind == "disk":
        painter.drawRoundedRect(5, 8, 22, 17, 3, 3)
        painter.drawLine(9, 19, 23, 19)
        painter.drawEllipse(20, 12, 3, 3)
    painter.end()
    return image


class _UI09PreflightStatusLabel(QLabel):
    """Paint status badges while retaining exact STEP10 state .text().

    On Windows Unicode status prefix glyphs sometimes render as empty squares.
    STEP10 set_check still exclusively owns this widget's text/status updates.
    """

    def paintEvent(self, event) -> None:
        raw = self.text().strip()
        if raw == "✓ PASS":
            label, color = "PASS", QColor("#17A84E")
        elif raw == "⚠ WARN":
            label, color = "WARN", QColor("#F29C00")
        elif raw == "✕ BLOCK":
            label, color = "BLOCK", QColor("#D64545")
        else:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.height() // 2
        radius = min(12, max(6, cy - 1))
        cx = radius + 1 + (25 if self.width() >= 130 else 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        if label == "WARN":
            painter.drawPolygon(QPolygon([
                QPoint(cx, cy - radius),
                QPoint(cx - radius, cy + radius - 2),
                QPoint(cx + radius, cy + radius - 2),
            ]))
            painter.setPen(QPen(QColor("#FFFFFF"), 2.2))
            painter.drawLine(cx, cy - 4, cx, cy + 2)
            painter.drawPoint(cx, cy + 6)
        else:
            painter.drawEllipse(cx - radius, cy - radius,
                                2 * radius, 2 * radius)
            painter.setPen(QPen(QColor("#FFFFFF"), 2.4))
            if label == "PASS":
                painter.drawLine(cx - 5, cy, cx - 1, cy + 4)
                painter.drawLine(cx - 1, cy + 4, cx + 6, cy - 5)
            else:
                painter.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
                painter.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)

        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color)
        left = 2 * radius + 8 + (45 if self.width() >= 130 else 0)
        painter.drawText(
            QRect(left, 0, max(0, self.width() - left), self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
        painter.end()


def _ui09_prepare_preflight_status(card) -> None:
    """Replace presentation label only; preserve existing STEP10 set_check."""
    if isinstance(card.state, _UI09PreflightStatusLabel):
        return
    old = card.state
    replacement = _UI09PreflightStatusLabel(old.text(), card)
    replacement.setObjectName(old.objectName())
    replacement.setStyleSheet(old.styleSheet())
    replacement.setAccessibleName(old.accessibleName())
    replacement.setSizePolicy(old.sizePolicy())
    replacement.setMinimumHeight(26)
    content = card.layout()
    content.replaceWidget(old, replacement)
    card.state = replacement
    old.hide()
    old.deleteLater()


def _ui09_prepare_preflight_icon(card, kind: str) -> None:
    """Decorate the existing status card; keep its state/detail ownership."""
    if getattr(card, "ui09_icon", None) is not None:
        return
    content = card.layout()
    content.removeWidget(card.title)
    row = QHBoxLayout()
    row.setContentsMargins(5, 0, 0, 0)
    row.setSpacing(5)
    glyph = QLabel(card)
    glyph.setObjectName("ui09PreflightVectorIcon")
    glyph.setPixmap(_ui09_preflight_icon(kind))
    glyph.setFixedSize(32, 32)
    glyph.setAccessibleName(f"Ikon {card.title.text()}")
    card.title.setStyleSheet("font-weight:700;color:#203B67;font-size:11px;")
    row.addWidget(glyph)
    row.addWidget(card.title)
    row.addStretch(1)
    content.insertLayout(0, row)
    # The preflight illustration needs to stay near the top of each card;
    # Qt otherwise distributes unused card height among all three QLabel
    # rows, pushing PASS/WARN and detail captions too low versus the golden.
    # Keep the actual state/detail widgets as their sole source of truth.
    content.insertSpacing(1, 6)
    content.insertSpacing(3, 15)
    content.addStretch(1)
    card.ui09_icon = glyph
    # Preserve layout items for reversible desktop/compact spacing.
    card.ui09_icon_row = row
    card.ui09_icon_spacers = (
        content.itemAt(1).spacerItem(),
        content.itemAt(3).spacerItem(),
    )


def _ui09_preflight_action_icon() -> QIcon:
    """Draw the exact action affordance independent of Windows emoji fonts."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#0968EA"), 1.9))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolygon(QPolygon([
        QPoint(12, 2), QPoint(20, 5), QPoint(19, 13),
        QPoint(16, 18), QPoint(12, 21), QPoint(8, 18),
        QPoint(5, 13), QPoint(4, 5),
    ]))
    painter.drawLine(8, 11, 11, 14)
    painter.drawLine(11, 14, 16, 9)
    painter.end()
    return QIcon(pixmap)


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
        preflight = FAMButton("Jalankan Preflight", kind="ghost")
        preflight.setIcon(_ui09_preflight_action_icon())
        preflight.setIconSize(QSize(24, 24))
        preflight.setAccessibleName("Jalankan Preflight")
        preflight.setMinimumSize(QSize(172, 46))
        preflight.setStyleSheet(
            "QPushButton{background:#FEFEFE;color:#1656EC;"
            "border:1px solid #BFDCFE;border-radius:6px;"
            "font-size:12px;font-weight:700;padding:6px 10px;"
            "margin-top:6px;}"
            "QPushButton:hover{background:#F1F7FF;border-color:#0864DC;}"
            "QPushButton:pressed{background:#E1EFFF;}"
        )
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
            _ui09_prepare_preflight_status(card)
            if window.width() >= 1500:
                _ui09_prepare_preflight_icon(card, key)
            if window.width() >= 1500:
                # Keep desktop card height identical to the proven Wave07
                # screenshot; the new top-anchored vector layout otherwise
                # claims extra stretch and steals 30+ pixels from the queue.
                card.setFixedHeight(154)
            else:
                card.setMinimumHeight(88)
            grid.addWidget(card, 0, column)

    active_card = workspace.progress.parentWidget()
    if active_card is not None:
        active_card.hide()
    log_card = workspace.log_list.parentWidget()
    if log_card is not None:
        log_card.hide()
    workspace.queue_list.setMinimumHeight(225)
    # On golden-sized displays, reduce unused queue padding so the graph
    # remains visible while the preflight cards receive proper vertical space.
    if window.width() >= 1500:
        workspace.queue_list.setMaximumHeight(280)
    # Preserve the original gaps and reduce only per-row height on Windows
    # if its native Qt metrics would crop the final row by 2–5 pixels.
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
    center_layout.setContentsMargins(10, 17 if window.width() >= 1500 else 8, 10, 8)
    center_layout.setSpacing(7)
    for item in existing:
        _add_layout_item(center_layout, item)
    preflight_heading = QLabel("Hasil Preflight")
    preflight_heading.setObjectName("sectionHeading")
    center_layout.insertWidget(1, preflight_heading)
    desktop_golden = window.width() >= 1500
    center_layout.insertSpacing(1, 0 if not desktop_golden else 26)
    if desktop_golden:
        preflight_subtitle = QLabel("Memeriksa kesiapan proyek untuk rendering.")
        preflight_subtitle.setObjectName("ui09PreflightSubtitle")
        preflight_subtitle.setStyleSheet("font-size:11px;color:#6880A7;")
        center_layout.insertWidget(3, preflight_subtitle)
        center_layout.insertSpacing(4, 6)
        center_layout.insertSpacing(6, 12)

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
    # Freeze the breakpoint chosen for the entire route before Qt relayout.
    desktop = desktop_golden
    sidebar.setMinimumWidth(274 if desktop else 196)
    sidebar.setMaximumWidth(282 if desktop else 214)
    side = QVBoxLayout(sidebar)
    side.setContentsMargins(8, 24 if desktop else 8, 8, 8)
    side.setSpacing(10 if desktop else 6)

    title = QLabel("Preset Render")
    title.setObjectName("sectionHeading")
    side.addWidget(title)
    if desktop:
        side.addSpacing(9)

    workspace.ui09_preset_buttons = {}
    preset_gap_items = []
    for preset_id, label in _PRESET_SURFACE:
        button = QPushButton(label)
        button.setAccessibleName("Preset Render " + label.splitlines()[0])
        # Isolated from the global QSS tabButton min-height/padding rule.
        button.setObjectName("ui09PresetCard")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setMinimumHeight(81 if desktop else 55)
        button.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#24385A;border:1px solid #DDE8F5;"
            "border-radius:7px;text-align:left;padding:7px 10px 7px 51px;font-size:11px;}"
            "QPushButton:checked{background:#E8F2FF;color:#075CE3;"
            "border-left:3px solid #0870F6;font-weight:700;}"
            "QPushButton:hover{border-color:#86B8FC;}"
        )
        # A child drawing surface fixes icon coordinates independently of the
        # native Qt style's text/icon spacing. It never handles mouse events.
        glyph = QLabel(button)
        glyph.setObjectName("ui09PresetVectorGlyph")
        glyph.setPixmap(_ui09_preset_icon(preset_id))
        glyph.setFixedSize(36, 32)
        glyph.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        glyph.move(5, 11)
        glyph.show()
        button.ui09_preset_glyph = glyph
        # Qt styles may reset minimum heights when the widget is polished.
        # Keep these desktop cards proportionate; compact remains untouched.
        if desktop:
            button.setFixedHeight(81)
        button.clicked.connect(
            lambda _checked=False, value=preset_id: _select_preset(window, value)
        )
        side.addWidget(button)
        workspace.ui09_preset_buttons[preset_id] = button
        # The frozen golden has approximately 72px center-to-center preset
        # spacing, while default Qt card layout yields about 60px. An explicit
        # 12px spacer produces the target 72px on Windows-hosted Qt evidence,
        # without changing the compact layout or non-preset controls.
        # Keep an owned spacer for reversible compact/desktop transitions.
        if preset_id != "custom":
            spacer = QSpacerItem(0, 12, QSizePolicy.Policy.Minimum,
                                 QSizePolicy.Policy.Fixed)
            preset_gap_items.append((preset_id, spacer))
            if desktop:
                side.addItem(spacer)
    workspace.ui09_preset_gap_items = preset_gap_items

    if desktop:
        side.addSpacing(24)

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
    workspace.ui09_center_layout = center_layout
    workspace.ui09_center_top_spacer = center_layout.itemAt(1).spacerItem()
    workspace.ui09_center_subtitle = preflight_subtitle if desktop_golden else None
    workspace.ui09_center_extra_spacers = (
        (center_layout.itemAt(4).spacerItem(), center_layout.itemAt(6).spacerItem())
        if desktop_golden else (None, None)
    )
    workspace.ui09_sidebar_layout = side
    workspace.ui09_history_heading = history_title
    workspace.ui09_sidebar_extra_spacers = (
        (side.itemAt(1).spacerItem(),
         side.itemAt(side.indexOf(history_title) - 1).spacerItem())
        if desktop_golden else (None, None)
    )
    workspace._ui09_prepared = True
    # Initial STEP10 updates happen before the Render route is constructed.
    workspace._ui09_last_jobs = tuple(window._s10_queue.jobs)
    _present_queue(workspace, workspace._ui09_last_jobs)

    inspector = window.render_inspector_s10
    inspector.preset.currentIndexChanged.connect(lambda *_: _sync_preset_surface(window))
    _sync_preset_surface(window)


def _apply_ui09_breakpoint(window) -> None:
    """Reflow presentation when crossing the desktop/compact window threshold.

    Wave08 tuned the initial desktop capture but froze card and queue density
    after first Render entry. This path only runs after a breakpoint change;
    unchanged golden-sized captures retain exactly their prior structure.
    """
    workspace = window.render_workspace_s10
    if not getattr(workspace, "_ui09_prepared", False):
        return
    compact = window.width() < 1500
    if compact == workspace.ui09_compact:
        return

    desktop = not compact
    center = workspace.ui09_center_layout
    center.setContentsMargins(10, 17 if desktop else 8, 10, 8)
    workspace.ui09_center_top_spacer.changeSize(0, 26 if desktop else 0)
    subtitle = workspace.ui09_center_subtitle
    before, after = workspace.ui09_center_extra_spacers
    if desktop and subtitle is None:
        subtitle = QLabel("Memeriksa kesiapan proyek untuk rendering.")
        subtitle.setObjectName("ui09PreflightSubtitle")
        subtitle.setStyleSheet("font-size:11px;color:#6880A7;")
        center.insertWidget(3, subtitle)
        center.insertSpacing(4, 6)
        center.insertSpacing(6, 12)
        workspace.ui09_center_subtitle = subtitle
        before, after = center.itemAt(4).spacerItem(), center.itemAt(6).spacerItem()
        workspace.ui09_center_extra_spacers = (before, after)
    elif subtitle is not None:
        subtitle.setVisible(desktop)
        before.changeSize(0, 6 if desktop else 0)
        after.changeSize(0, 12 if desktop else 0)

    for key in ("media", "snapshot", "ffmpeg", "output", "disk"):
        card = workspace.preflight_cards[key]
        if desktop:
            _ui09_prepare_preflight_icon(card, key)
        glyph = getattr(card, "ui09_icon", None)
        if glyph is not None:
            glyph.setVisible(desktop)
            card.ui09_icon_row.setContentsMargins(5 if desktop else 0, 0, 0, 0)
            for item, height in zip(
                card.ui09_icon_spacers, (6, 15) if desktop else (0, 0)
            ):
                item.changeSize(0, height)
            card.layout().invalidate()
        if desktop:
            card.setFixedHeight(154)
        else:
            # setFixedHeight binds maximumHeight; both bounds must be reset.
            card.setMaximumHeight(16777215)
            card.setMinimumHeight(88)

    sidebar = workspace.ui09_sidebar
    sidebar.setMinimumWidth(274 if desktop else 196)
    sidebar.setMaximumWidth(282 if desktop else 214)
    side = workspace.ui09_sidebar_layout
    side.setContentsMargins(8, 24 if desktop else 8, 8, 8)
    side.setSpacing(10 if desktop else 6)
    top_space, history_space = workspace.ui09_sidebar_extra_spacers
    if desktop and top_space is None:
        side.insertSpacing(1, 9)
        side.insertSpacing(side.indexOf(workspace.ui09_history_heading), 24)
        top_space = side.itemAt(1).spacerItem()
        history_space = side.itemAt(
            side.indexOf(workspace.ui09_history_heading) - 1
        ).spacerItem()
        workspace.ui09_sidebar_extra_spacers = (top_space, history_space)
    elif top_space is not None:
        top_space.changeSize(0, 9 if desktop else 0)
        history_space.changeSize(0, 24 if desktop else 0)

    for button in workspace.ui09_preset_buttons.values():
        button.setMaximumHeight(16777215)
        button.setMinimumHeight(81 if desktop else 55)
        if desktop:
            button.setFixedHeight(81)
    # Remove the real QSpacerItem from the compact layout (hiding a 0px
    # spacer would leave another native Qt layout gap). Reinsert on desktop.
    for preset_id, spacer in workspace.ui09_preset_gap_items:
        if desktop:
            button = workspace.ui09_preset_buttons[preset_id]
            side.insertItem(side.indexOf(button) + 1, spacer)
        else:
            side.removeItem(spacer)

    graph = getattr(window, "render_performance_s10", None)
    if graph is not None:
        graph.setMinimumHeight(112 if desktop else 88)
        graph.setMaximumHeight(132 if desktop else 100)
    workspace.queue_list.setMaximumHeight(280 if desktop else 16777215)
    # Windows/Linux native Qt give the resized compact queue less height than
    # a compact-first route. Remove only the two 5px gaps after a breakpoint
    # transition, keeping three observed STEP10 jobs fully visible.
    workspace.queue_list.setSpacing(5 if desktop else 0)
    workspace.ui09_compact = compact
    _present_queue(workspace, getattr(workspace, "_ui09_last_jobs", ()))
    center.invalidate()
    side.invalidate()
    workspace.ui09_host.updateGeometry()


class _UI09ResizeWatcher(QObject):
    """Schedule at most one layout update after native Qt resize/layout."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._pending = False

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            workspace = getattr(watched, "render_workspace_s10", None)
            state = getattr(watched, "foundation_state", None)
            if (workspace is not None and getattr(workspace, "_ui09_prepared", False)
                    and state is not None and state.workspace == "render"
                    and (watched.width() < 1500) != workspace.ui09_compact
                    and not self._pending):
                self._pending = True
                QTimer.singleShot(0, self._refresh)
        return False

    def _refresh(self) -> None:
        self._pending = False
        window = self.parent()
        if window is not None:
            state = getattr(window, "foundation_state", None)
            if state is not None and state.workspace == "render":
                _apply_ui09_breakpoint(window)


def _ensure_ui09(window) -> None:
    _prepare_inspector(window)
    _prepare_center(window)
    if getattr(window, "_ui09_resize_watcher", None) is None:
        watcher = _UI09ResizeWatcher(window)
        window._ui09_resize_watcher = watcher
        window.installEventFilter(watcher)


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    if route != "render":
        return
    _ensure_ui09(self)
    _apply_ui09_breakpoint(self)
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
    from .render_workspace_step10 import RenderCenterWorkspace, RenderHistoryContext

    _originals["history_apply_jobs"] = RenderHistoryContext.apply_jobs
    RenderHistoryContext.apply_jobs = _apply_history_presentation
    _originals["apply_queue"] = RenderCenterWorkspace.apply_queue
    _originals["apply_job"] = RenderCenterWorkspace.apply_job
    RenderCenterWorkspace.apply_queue = _apply_queue_presentation
    RenderCenterWorkspace.apply_job = _apply_job_presentation
    _originals["window_route"] = FoundationMainWindow._s10_route
    FoundationMainWindow._s10_route = _window_route
    _installed = True
