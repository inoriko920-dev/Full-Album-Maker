from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .editor_models import TIMEBASE
from .foundation_components import FAMButton, FAMSegmented
from .foundation_tokens import TOKENS
from .timeline_resolver import TimelineResolver
from .visual_assignment import assignment_counts, assignment_status, filtered_song_ids
from .visual_precision import visual_settings_for_song
from .visual_workspace_step06 import (
    MOTION_LABELS,
    TRANSITION_LABELS,
    VisualInspector,
    VisualPreviewCanvas,
    VisualPreviewWorkspace,
    VisualSongContext,
    _duration_text,
    _song_artist,
    _song_title,
)

_installed = False
_originals: dict[str, Any] = {}


def _placeholder_icon(kind: str) -> QIcon:
    pix = QPixmap(88, 54)
    palette = {
        "image": ("#DDEEF9", "#4F86A8"),
        "video": ("#E4E9FF", "#526DC4"),
        "empty": ("#EEF2F7", "#7A889C"),
        "missing": ("#FFF0D1", "#C08A27"),
    }
    bg, fg = palette.get(kind, palette["empty"])
    pix.fill(QColor(bg))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(QPen(QColor(fg), 2))
    if kind == "video":
        p.drawRoundedRect(QRectF(23, 13, 42, 28), 4, 4)
        p.setBrush(QColor(fg))
        p.drawPolygon([(39, 20), (39, 34), (52, 27)])
    elif kind == "image":
        p.drawRoundedRect(QRectF(16, 10, 56, 34), 4, 4)
        p.drawLine(20, 39, 36, 25)
        p.drawLine(36, 25, 48, 35)
        p.drawLine(48, 35, 63, 19)
        p.drawEllipse(QRectF(54, 14, 7, 7))
    elif kind == "missing":
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "!")
    else:
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "♫")
    p.end()
    return QIcon(pix)


def _asset_icon(document, song_id: str) -> QIcon:
    status = assignment_status(document, song_id)
    song = document.song_map().get(song_id)
    asset = document.asset_map().get(song.visual_asset_id or "") if song is not None else None
    if asset is not None:
        candidates = [
            str(asset.metadata.get("visual_preview_path", "") or ""),
            str(asset.metadata.get("thumbnail_path", "") or ""),
            str(asset.locator or "") if asset.kind == "image" else "",
        ]
        for value in candidates:
            if not value:
                continue
            pix = QPixmap(value)
            if not pix.isNull():
                thumb = pix.scaled(
                    88, 54,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                if thumb.width() != 88 or thumb.height() != 54:
                    x = max(0, (thumb.width() - 88) // 2)
                    y = max(0, (thumb.height() - 54) // 2)
                    thumb = thumb.copy(x, y, min(88, thumb.width()), min(54, thumb.height()))
                return QIcon(thumb)
    return _placeholder_icon(status.state)


def _context_init(self, *args, **kwargs) -> None:
    _originals["context_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(10, 10, 10, 8)
    root.setSpacing(7)

    # Keep the original semantic filters, but make the list read like the
    # reference: visual thumbnails, metadata and duration in one dense row.
    self.listing.setIconSize(QSize(88, 54))
    self.listing.setSpacing(4)
    self.listing.setStyleSheet(
        "QListWidget{border:0;background:#FFFFFF;}"
        "QListWidget::item{padding:5px;border-radius:8px;}"
        "QListWidget::item:selected{background:#DCEEFF;color:#10234A;}"
    )
    try:
        subtitle = root.itemAt(1).widget()
        if subtitle is not None:
            subtitle.hide()
    except Exception:
        pass
    self.counts.hide()
    self.missing.hide()


def _context_render(self) -> None:
    counts = assignment_counts(self._document)
    labels = {
        "all": f"Semua ({counts['all']})",
        "empty": f"Tanpa Visual ({counts['empty']})",
        "image": f"Foto ({counts['image']})",
        "video": f"Video ({counts['video']})",
    }
    for key, button in self.filters._buttons.items():
        if key in labels:
            button.setText(labels[key])

    self._updating = True
    try:
        self.listing.clear()
        resolved = TimelineResolver().resolve(self._document)
        duration_by_song = {item.song_id: item.end_tick - item.start_tick for item in resolved.songs}
        playlist_index = {song.song_id: index + 1 for index, song in enumerate(self._document.playlist.entries)}
        for song_id in filtered_song_ids(self._document, self._filter):
            status = assignment_status(self._document, song_id)
            title = _song_title(self._document, song_id)
            artist = _song_artist(self._document, song_id)
            duration = _duration_text(duration_by_song.get(song_id, 0))
            detail = status.label if not artist else f"{artist}   •   {status.label}"
            item = QListWidgetItem(
                _asset_icon(self._document, song_id),
                f"{playlist_index.get(song_id, 0):02d}   {title}\n     {detail}                                      {duration}",
            )
            item.setData(Qt.ItemDataRole.UserRole, song_id)
            item.setToolTip(status.locator or "Belum ada visual")
            item.setSizeHint(QSize(0, 66))
            self.listing.addItem(item)
        self._render_selection()
    finally:
        self._updating = False


def _preview_canvas_paint(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(self.rect(), QColor("#F4F8FD"))
    margin = 10
    available = self.rect().adjusted(margin, margin, -margin, -margin)
    aspect = 16 / 9
    width = available.width()
    height = int(width / aspect)
    if height > available.height():
        height = available.height()
        width = int(height * aspect)
    canvas = QRectF(
        available.center().x() - width / 2,
        available.center().y() - height / 2,
        width,
        height,
    )
    painter.fillRect(canvas, QColor("#101923"))
    painter.setPen(QPen(QColor("#CBD8E8"), 1))
    painter.drawRect(canvas)

    song = self._document.song_map().get(self._song_id)
    if song is None:
        painter.setPen(QColor("#D9E5F3"))
        painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "Pilih lagu untuk mengatur visual")
        painter.end()
        return

    status = assignment_status(self._document, self._song_id)
    settings = visual_settings_for_song(self._document, self._song_id)
    asset = self._document.asset_map().get(song.visual_asset_id or "")
    decoded = getattr(self, "_decoded_image", QImage())
    decoded_id = str(getattr(self, "_decoded_asset_id", "") or "")

    image = QImage()
    if asset is not None and asset.kind == "video" and decoded_id == asset.asset_id and not decoded.isNull():
        image = decoded
    elif asset is not None and asset.kind == "image":
        image = QImage(asset.locator)

    if status.state == "missing":
        painter.setPen(QColor("#F6C453"))
        painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, f"⚠ SOURCE MISSING\n{status.source_name}\nGunakan Relink")
    elif asset is None:
        painter.setPen(QColor("#D9E5F3"))
        painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "TANPA VISUAL\nPilih Foto atau Video")
    elif not image.isNull():
        self._paint_image(painter, canvas, image, settings)
    elif asset.kind == "video":
        painter.fillRect(canvas.adjusted(1, 1, -1, -1), QColor("#24384F"))
        painter.setPen(QColor("#E7F1FC"))
        playback = "LOOP" if settings["loop_video"] else "FREEZE END" if settings["freeze_end"] else "NORMAL"
        painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, f"▶ VIDEO\n{status.source_name}\n{playback}")
    else:
        painter.setPen(QColor("#F6C453"))
        painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "Visual tidak dapat dibaca")
    painter.end()


def _preview_init(self, *args, **kwargs) -> None:
    _originals["preview_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(8, 8, 8, 7)
    root.setSpacing(5)
    self.preview.setMinimumHeight(300)

    # Hide the recovered compact transport and replace it with the larger
    # reference-oriented transport while retaining the same STEP06 signals.
    old_row = root.itemAt(1).layout() if root.count() > 1 else None
    if old_row is not None:
        for index in range(old_row.count()):
            widget = old_row.itemAt(index).widget()
            if widget is not None:
                widget.hide()

    self.ui05_progress = QSlider(Qt.Orientation.Horizontal)
    self.ui05_progress.setRange(0, 1000)
    self.ui05_progress.setValue(0)
    root.insertWidget(1, self.ui05_progress)

    transport = QWidget()
    row = QHBoxLayout(transport)
    row.setContentsMargins(4, 0, 4, 0)
    row.setSpacing(7)
    self.ui05_play = FAMButton("▶", kind="primary")
    self.ui05_play.setFixedWidth(42)
    self.ui05_prev = FAMButton("◀|", kind="ghost")
    self.ui05_next = FAMButton("|▶", kind="ghost")
    self.ui05_play.clicked.connect(self.play_requested)
    self.ui05_prev.clicked.connect(self.previous_requested)
    self.ui05_next.clicked.connect(self.next_requested)
    row.addWidget(self.ui05_play)
    row.addWidget(self.ui05_prev)
    row.addWidget(self.ui05_next)
    row.addStretch(1)
    self.ui05_time = QLabel("00:00 / 00:00")
    self.ui05_time.setObjectName("metadata")
    row.addWidget(self.ui05_time)
    self.ui05_aspect = QComboBox()
    self.ui05_aspect.addItem("16:9")
    self.ui05_aspect.setFixedWidth(72)
    row.addWidget(self.ui05_aspect)
    self.ui05_snapshot = FAMButton("▣", kind="ghost")
    self.ui05_snapshot.setEnabled(False)
    self.ui05_snapshot.setToolTip("Snapshot preview belum memiliki aksi terpisah.")
    self.ui05_fullscreen = FAMButton("⛶", kind="ghost")
    self.ui05_fullscreen.setEnabled(False)
    self.ui05_fullscreen.setToolTip("Fullscreen preview belum memiliki aksi terpisah.")
    row.addWidget(self.ui05_snapshot)
    row.addWidget(self.ui05_fullscreen)
    root.addWidget(transport)
    self.source.hide()


def _format_mmss(tick: int) -> str:
    seconds = max(0, int(round(tick / TIMEBASE)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _preview_apply(self, document, song_id: str, playhead_tick: int) -> None:
    _originals["preview_apply"](self, document, song_id, playhead_tick)
    resolved = TimelineResolver().resolve(document)
    event = next((item for item in resolved.songs if item.song_id == song_id), None)
    if event is None:
        self.ui05_time.setText("00:00 / 00:00")
        self.ui05_progress.setValue(0)
        return
    duration = max(1, event.end_tick - event.start_tick)
    local = max(0, min(duration, playhead_tick - event.start_tick))
    self.ui05_time.setText(f"{_format_mmss(local)} / {_format_mmss(duration)}")
    self.ui05_progress.blockSignals(True)
    self.ui05_progress.setValue(int(round(local * 1000 / duration)))
    self.ui05_progress.blockSignals(False)


def _inspector_init(self, *args, **kwargs) -> None:
    _originals["inspector_init"](self, *args, **kwargs)
    outer = self.layout()
    old_scroll = outer.itemAt(0).widget()
    if old_scroll is not None:
        old_scroll.hide()

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    body = QWidget()
    root = QVBoxLayout(body)
    root.setContentsMargins(12, 8, 12, 10)
    root.setSpacing(8)

    # Source card.
    source_title = QLabel("Sumber Visual")
    source_title.setObjectName("sectionHeading")
    root.addWidget(source_title)
    source_row = QHBoxLayout()
    self.ui05_source_thumb = QLabel()
    self.ui05_source_thumb.setFixedSize(128, 72)
    self.ui05_source_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.ui05_source_thumb.setStyleSheet("border:1px solid #D8E3F0;border-radius:7px;background:#EEF4FA;")
    source_row.addWidget(self.ui05_source_thumb)
    self.ui05_source_meta = QLabel("Tanpa Visual")
    self.ui05_source_meta.setObjectName("metadata")
    self.ui05_source_meta.setWordWrap(True)
    source_row.addWidget(self.ui05_source_meta, 1)
    root.addLayout(source_row)

    choose = QHBoxLayout()
    self.image_button.setText("Pilih Foto")
    self.video_button.setText("Pilih Video")
    choose.addWidget(self.image_button)
    choose.addWidget(self.video_button)
    root.addLayout(choose)
    repair = QHBoxLayout()
    self.auto_button.setText("Auto Match Visual")
    repair.addWidget(self.auto_button, 1)
    repair.addWidget(self.relink_button)
    repair.addWidget(self.clear_button)
    root.addLayout(repair)

    visual_title = QLabel("Pengaturan Visual")
    visual_title.setObjectName("sectionHeading")
    root.addWidget(visual_title)

    fit_row = QHBoxLayout()
    fit_label = QLabel("Fit / Fill")
    fit_label.setMinimumWidth(78)
    fit_row.addWidget(fit_label)
    self.ui05_fit = FAMSegmented([("fit", "Fit"), ("fill", "Fill")])
    fit_row.addWidget(self.ui05_fit, 1)
    root.addLayout(fit_row)
    for key, button in self.ui05_fit._buttons.items():
        button.clicked.connect(
            lambda _checked=False, value=key:
            self.fit.setCurrentIndex(max(0, self.fit.findData(value)))
        )

    self.ui05_crop_button = FAMButton("⌗  Crop", kind="ghost")
    root.addWidget(self.ui05_crop_button)
    self.ui05_crop_panel = QWidget()
    crop = QGridLayout(self.ui05_crop_panel)
    crop.setContentsMargins(0, 0, 0, 0)
    crop.setHorizontalSpacing(6)
    crop.setVerticalSpacing(4)
    for row_index, (label, widget) in enumerate((
        ("X", self.crop_x), ("Y", self.crop_y), ("W", self.crop_w), ("H", self.crop_h)
    )):
        crop.addWidget(QLabel(label), row_index // 2, (row_index % 2) * 2)
        crop.addWidget(widget, row_index // 2, (row_index % 2) * 2 + 1)
    self.ui05_crop_panel.hide()
    self.ui05_crop_button.clicked.connect(
        lambda: self.ui05_crop_panel.setVisible(self.ui05_crop_panel.isHidden())
    )
    root.addWidget(self.ui05_crop_panel)

    pos = QHBoxLayout()
    pos.addWidget(QLabel("Posisi"))
    pos.addWidget(QLabel("X"))
    pos.addWidget(self.pos_x)
    pos.addWidget(QLabel("Y"))
    pos.addWidget(self.pos_y)
    root.addLayout(pos)

    scale_row = QHBoxLayout()
    scale_row.addWidget(QLabel("Skala"))
    self.ui05_scale_slider = QSlider(Qt.Orientation.Horizontal)
    self.ui05_scale_slider.setRange(25, 400)
    self.ui05_scale_slider.valueChanged.connect(lambda value: self.scale.setValue(float(value)))
    self.scale.valueChanged.connect(
        lambda value: self.ui05_scale_slider.setValue(int(round(float(value))))
    )
    scale_row.addWidget(self.ui05_scale_slider, 1)
    scale_row.addWidget(self.scale)
    root.addLayout(scale_row)

    motion_title = QLabel("Motion & Durasi")
    motion_title.setObjectName("sectionHeading")
    root.addWidget(motion_title)
    root.addWidget(QLabel("Preset Motion"))
    self.ui05_motion = FAMSegmented([
        ("static", "None"),
        ("ken_burns", "Ken Burns"),
        ("zoom_in", "Zoom In"),
        ("zoom_out", "Zoom Out"),
        ("pan_left", "Pan Left"),
        ("pan_right", "Pan Right"),
    ])
    self.ui05_motion.setStyleSheet("QPushButton{font-size:10px;padding:5px 3px;}")
    root.addWidget(self.ui05_motion)
    for key, button in self.ui05_motion._buttons.items():
        button.clicked.connect(
            lambda _checked=False, value=key:
            self.motion.setCurrentIndex(max(0, self.motion.findData(value)))
        )

    toggles = QHBoxLayout()
    toggles.addWidget(self.pan_zoom)
    toggles.addWidget(self.loop_video)
    toggles.addWidget(self.freeze_end)
    root.addLayout(toggles)

    trans_title = QLabel("Transisi")
    trans_title.setObjectName("sectionHeading")
    root.addWidget(trans_title)
    self.ui05_transition = FAMSegmented([("cut", "Cut"), ("fade", "Fade"), ("slide", "Slide")])
    root.addWidget(self.ui05_transition)
    for key, button in self.ui05_transition._buttons.items():
        button.clicked.connect(
            lambda _checked=False, value=key:
            self.transition.setCurrentIndex(max(0, self.transition.findData(value)))
        )

    duration_row = QHBoxLayout()
    duration_row.addWidget(QLabel("Durasi Transisi"))
    self.ui05_duration_slider = QSlider(Qt.Orientation.Horizontal)
    self.ui05_duration_slider.setRange(0, 50)
    self.ui05_duration_slider.valueChanged.connect(
        lambda value: self.transition_seconds.setValue(value / 10.0)
    )
    self.transition_seconds.valueChanged.connect(
        lambda value: self.ui05_duration_slider.setValue(int(round(float(value) * 10)))
    )
    duration_row.addWidget(self.ui05_duration_slider, 1)
    duration_row.addWidget(self.transition_seconds)
    root.addLayout(duration_row)

    self.apply_button.hide()
    root.addWidget(self.apply_selected)
    root.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)
    self.ui05_scroll = scroll


def _set_checked(segmented: FAMSegmented, value: str) -> None:
    for key, button in segmented._buttons.items():
        button.blockSignals(True)
        button.setChecked(key == value)
        button.blockSignals(False)


def _inspector_set_song(self, document, song_id: str, selected_count: int) -> None:
    _originals["inspector_set_song"](self, document, song_id, selected_count)
    enabled = bool(song_id and song_id in document.song_map())
    self.ui05_scroll.setEnabled(enabled)
    if not enabled:
        self.ui05_source_thumb.clear()
        self.ui05_source_meta.setText("Tanpa Visual")
        return

    status = assignment_status(document, song_id)
    song = document.song_map()[song_id]
    asset = document.asset_map().get(song.visual_asset_id or "")
    icon = _asset_icon(document, song_id)
    pix = icon.pixmap(QSize(128, 72))
    self.ui05_source_thumb.setPixmap(pix)

    if asset is None:
        meta = "Tanpa Visual"
    else:
        try:
            size_mb = Path(asset.locator).stat().st_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB"
        except OSError:
            size_text = "file tidak tersedia"
        width = asset.metadata.get("width")
        height = asset.metadata.get("height")
        dimensions = f"{width} × {height}" if width and height else asset.kind.title()
        meta = f"{asset.original_name or Path(asset.locator).name}\n{dimensions}  •  {size_text}"
    if status.state == "missing":
        meta += "\n⚠ File tidak ditemukan"
    self.ui05_source_meta.setText(meta)
    self.relink_button.setVisible(status.state == "missing")

    values = visual_settings_for_song(document, song_id)
    _set_checked(self.ui05_fit, str(values["fit"]))
    _set_checked(self.ui05_motion, str(values["image_motion"]))
    transition = str(values["transition"])
    if transition.startswith("slide"):
        transition = "slide"
    _set_checked(self.ui05_transition, transition)
    self.ui05_scale_slider.setValue(int(round(float(values["scale"]) * 100)))
    self.ui05_duration_slider.setValue(int(round(float(values["transition_seconds"]) * 10)))
    self.ui05_duration_slider.setEnabled(str(values["transition"]) != "cut")


def _timeline_paint(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(self.rect(), QColor("#FFFFFF"))
    resolved = TimelineResolver().resolve(self._document)
    left = 126
    ruler = 25
    row_h = max(44, int((self.height() - ruler) / 2))
    duration = max(TIMEBASE, resolved.duration_tick)
    pps = max(0.01, (max(160, self.width() - left - 10)) / (duration / TIMEBASE))

    painter.fillRect(QRectF(0, 0, left, self.height()), QColor("#F8FBFF"))
    painter.setPen(QPen(QColor(TOKENS.border), 1))
    painter.drawLine(left, 0, left, self.height())
    painter.drawLine(0, ruler, self.width(), ruler)
    painter.drawLine(0, ruler + row_h, self.width(), ruler + row_h)

    duration_seconds = max(1, int(duration / TIMEBASE))
    major = 30 if duration_seconds <= 600 else 60
    for second in range(0, duration_seconds + major, major):
        x = left + second * pps
        if x > self.width():
            break
        painter.setPen(QPen(QColor("#DCE6F3"), 1))
        painter.drawLine(QRectF(x, 0, 0, self.height()).topLeft(), QRectF(x, 0, 0, self.height()).bottomLeft())
        painter.setPen(QColor(TOKENS.text_muted))
        painter.drawText(QRectF(x + 3, 2, 60, 18), Qt.AlignmentFlag.AlignLeft, f"{second // 60:02d}:{second % 60:02d}")

    painter.setPen(QColor(TOKENS.text_primary))
    painter.drawText(QRectF(10, ruler, left - 18, row_h), Qt.AlignmentFlag.AlignVCenter, "◉  Video")
    painter.drawText(QRectF(10, ruler + row_h, left - 18, row_h), Qt.AlignmentFlag.AlignVCenter, "♫  Audio")

    songs = self._document.song_map()
    assets = self._document.asset_map()
    for event in resolved.songs:
        x = left + (event.start_tick / TIMEBASE) * pps
        width = max(5.0, ((event.end_tick - event.start_tick) / TIMEBASE) * pps)
        selected = event.song_id in self._selected_ids
        song = songs[event.song_id]
        status = assignment_status(self._document, event.song_id)

        visual_rect = QRectF(x + 1, ruler + 5, max(4, width - 2), row_h - 10)
        painter.setPen(QPen(QColor("#1766E8" if selected else "#7EA9D9"), 2 if selected else 1))
        painter.setBrush(QColor("#DDEEFF" if selected else "#EDF5FF"))
        painter.drawRoundedRect(visual_rect, 4, 4)
        if status.asset_id:
            asset = assets.get(status.asset_id)
            icon = _asset_icon(self._document, event.song_id)
            thumb_w = min(92.0, max(0.0, visual_rect.width() * 0.32))
            if thumb_w >= 24:
                pix = icon.pixmap(QSize(int(thumb_w), max(20, int(visual_rect.height()))))
                target = QRectF(visual_rect.left(), visual_rect.top(), thumb_w, visual_rect.height())
                painter.drawPixmap(target.toRect(), pix)
            painter.setPen(QColor("#164B8A"))
            name = status.source_name or status.label
            painter.drawText(
                visual_rect.adjusted(thumb_w + 5, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter,
                name,
            )
        else:
            painter.setPen(QColor("#76879A"))
            painter.drawText(visual_rect.adjusted(5, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, "Tanpa Visual")

        audio_rect = QRectF(x + 1, ruler + row_h + 5, max(4, width - 2), row_h - 10)
        painter.setPen(QPen(QColor("#72A9E6"), 1))
        painter.setBrush(QColor("#E9F4FF"))
        painter.drawRoundedRect(audio_rect, 4, 4)
        painter.setPen(QColor("#245A91"))
        painter.drawText(
            audio_rect.adjusted(5, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter,
            song.display_title or "Lagu",
        )

    play_x = left + (self._playhead_tick / TIMEBASE) * pps
    painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
    painter.drawLine(int(play_x), 0, int(play_x), self.height())
    painter.end()


def _ensure_timeline_panel(window) -> None:
    if hasattr(window, "_ui05_timeline_panel"):
        return
    host = window.foundation_shell.timeline
    panel = QFrame()
    panel.setObjectName("ui05TimelinePanel")
    root = QVBoxLayout(panel)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar = QHBoxLayout(toolbar_widget)
    toolbar.setContentsMargins(8, 3, 8, 3)
    toolbar.setSpacing(6)
    title = QLabel("Timeline")
    title.setObjectName("sectionHeading")
    toolbar.addWidget(title)

    add = FAMButton("⊕  Tambah Visual", kind="ghost")
    menu = QMenu(add)
    menu.addAction("Pilih Foto", lambda: window._s06_choose_visual("image"))
    menu.addAction("Pilih Video", lambda: window._s06_choose_visual("video"))
    add.setMenu(menu)
    toolbar.addWidget(add)

    split = FAMButton("Pisah", kind="ghost")
    split.setEnabled(False)
    split.setToolTip("Visual per lagu mengikuti durasi lagu; split clip belum menjadi kontrak STEP06.")
    toolbar.addWidget(split)

    delete = FAMButton("Hapus", kind="ghost")
    delete.clicked.connect(window._s06_clear_visual)
    toolbar.addWidget(delete)

    auto = FAMButton("Auto Match", kind="ghost")
    auto.clicked.connect(window._s06_auto_match)
    toolbar.addWidget(auto)
    toolbar.addStretch(1)
    toolbar.addWidget(QLabel("−"))
    toolbar.addWidget(QLabel("100%"))
    toolbar.addWidget(QLabel("+"))
    root.addWidget(toolbar_widget)

    canvas = window.visual_timeline_s06
    old_parent = canvas.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(canvas)
    root.addWidget(canvas, 1)
    host.layout().addWidget(panel, 1)
    panel.hide()
    window._ui05_timeline_panel = panel

    header = host.layout().itemAt(0).layout()
    window._ui05_timeline_header_widgets = []
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if widget is not None:
                window._ui05_timeline_header_widgets.append(widget)


def _seek_from_slider(window, value: int) -> None:
    document = window.editor_workspace.document()
    song_id = getattr(window, "_s06_primary_song_id", "")
    event = next((item for item in TimelineResolver().resolve(document).songs if item.song_id == song_id), None)
    if event is None:
        return
    target = event.start_tick + int(round((event.end_tick - event.start_tick) * max(0, min(1000, value)) / 1000))
    window.editor_workspace.set_playhead(target)


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    _ensure_timeline_panel(self)
    active = route == "visual"
    host = self.foundation_shell.timeline

    self._ui05_timeline_panel.setVisible(active)
    for widget in getattr(self, "_ui05_timeline_header_widgets", ()):
        widget.setVisible(not active)

    if active:
        host.body.hide()
        self.visual_timeline_s06.show()
        host._preferred_height = 220
        host.setMinimumHeight(220)
        host.setMaximumHeight(220)
        self.foundation_shell._apply_shell_sizes("visual")
        if not getattr(self, "_ui05_seek_connected", False):
            self.visual_workspace_s06.ui05_progress.sliderMoved.connect(lambda value: _seek_from_slider(self, value))
            self._ui05_seek_connected = True
    elif route != "timeline":
        self._ui05_timeline_panel.hide()
        host.body.setVisible(not host.collapsed)


def _shell_sizes(self, route: str) -> None:
    _originals["shell_sizes"](self, route)
    if route != "visual":
        return

    compact = bool(getattr(self, "_responsive_compact", False))
    total = max(1, self.width())
    nav = TOKENS.nav_compact_width if compact else TOKENS.nav_width
    context = 300 if compact else 384
    right = 38 if self.inspector.collapsed else (300 if compact else 368)
    center = max(430 if compact else 560, total - nav - context - right - TOKENS.splitter_handle * 3)

    self.navigation.setMinimumWidth(nav)
    self.navigation.setMaximumWidth(nav)
    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(context)
    if not self.inspector.collapsed:
        self.inspector.setMinimumWidth(right)
        self.inspector.setMaximumWidth(520)
    self.horizontal_splitter.setSizes([nav, context, center, right])

    timeline_h = 220
    self.timeline._preferred_height = timeline_h
    self.timeline.setMinimumHeight(timeline_h)
    self.timeline.setMaximumHeight(timeline_h)
    top_h = max(300 if compact else 360, self.height() - timeline_h - TOKENS.status_height - TOKENS.command_height)
    self.vertical_splitter.setSizes([top_h, timeline_h])


def install_ui05_visual_remediation() -> None:
    """Route-scoped UI-05 presentation parity; STEP06 model/render contracts stay authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget
    from .foundation_window import FoundationMainWindow
    from . import visual_preview_decode_step06 as preview_decode
    from . import visual_timeline_completion_step06 as timeline_completion

    _originals.update(
        context_init=VisualSongContext.__init__,
        context_render=VisualSongContext._render,
        preview_init=VisualPreviewWorkspace.__init__,
        preview_apply=VisualPreviewWorkspace.apply_state,
        inspector_init=VisualInspector.__init__,
        inspector_set_song=VisualInspector.set_song,
        window_route=FoundationMainWindow._s06_route,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    VisualSongContext.__init__ = _context_init
    VisualSongContext._render = _context_render
    VisualPreviewCanvas.paintEvent = _preview_canvas_paint
    preview_decode.DecodedVisualPreviewCanvas.paintEvent = _preview_canvas_paint
    VisualPreviewWorkspace.__init__ = _preview_init
    VisualPreviewWorkspace.apply_state = _preview_apply
    VisualInspector.__init__ = _inspector_init
    VisualInspector.set_song = _inspector_set_song
    timeline_completion.TransitionVisualAlignmentCanvas.paintEvent = _timeline_paint
    FoundationMainWindow._s06_route = _window_route
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
