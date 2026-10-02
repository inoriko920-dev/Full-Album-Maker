from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .editor_models import ProjectDocument, TIMEBASE
from .foundation_components import FAMButton, FAMSegmented
from .foundation_tokens import TOKENS
from .timeline_resolver import TimelineResolver
from .visual_assignment import assignment_counts, assignment_status, filtered_song_ids
from .visual_precision import visual_settings_for_song


MOTION_LABELS = {
    "static": "None",
    "ken_burns": "Ken Burns",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "pan_left": "Pan Left",
    "pan_right": "Pan Right",
}
TRANSITION_LABELS = {
    "cut": "Cut",
    "fade": "Fade",
    "slide": "Slide",
    "slide_left": "Slide Left",
    "slide_right": "Slide Right",
}


def _song_title(document: ProjectDocument, song_id: str) -> str:
    song = document.song_map().get(song_id)
    if song is None:
        return "Lagu"
    if song.display_title.strip():
        return song.display_title.strip()
    asset = document.asset_map().get(song.asset_id)
    return Path(asset.locator).stem if asset is not None else "Lagu"


def _song_artist(document: ProjectDocument, song_id: str) -> str:
    song = document.song_map().get(song_id)
    return song.display_artist.strip() if song is not None else ""


def _duration_text(tick: int) -> str:
    total = max(0, int(tick)) / TIMEBASE
    minutes = int(total // 60)
    seconds = int(total % 60)
    return f"{minutes:02d}:{seconds:02d}"


class VisualSongContext(QFrame):
    selection_changed = Signal(object, str)
    filter_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("visualSongContext")
        self._document = ProjectDocument.new_empty()
        self._filter = "all"
        self._selected_ids: set[str] = set()
        self._primary = ""
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)
        heading = QLabel("Daftar Lagu")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        subtitle = QLabel("Visual per lagu")
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.filters = FAMSegmented([
            ("all", "Semua"),
            ("empty", "Kosong"),
            ("image", "Foto"),
            ("video", "Video"),
        ])
        root.addWidget(self.filters)
        for key, button in self.filters._buttons.items():
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))

        self.counts = QLabel("Semua 0 • Kosong 0 • Foto 0 • Video 0")
        self.counts.setObjectName("metadata")
        self.counts.setWordWrap(True)
        root.addWidget(self.counts)

        self.listing = QListWidget()
        self.listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.listing.setSpacing(2)
        self.listing.itemSelectionChanged.connect(self._selection_from_ui)
        self.listing.currentItemChanged.connect(self._current_from_ui)
        root.addWidget(self.listing, 1)

        self.missing = QLabel("")
        self.missing.setObjectName("metadata")
        self.missing.setWordWrap(True)
        root.addWidget(self.missing)

    @property
    def selected_song_ids(self) -> set[str]:
        return set(self._selected_ids)

    @property
    def primary_song_id(self) -> str:
        return self._primary

    @property
    def filter_key(self) -> str:
        return self._filter

    def set_filter(self, key: str) -> None:
        value = str(key or "all")
        if value not in {"all", "empty", "image", "video", "missing"}:
            value = "all"
        self._filter = value
        self._render()
        self.filter_changed.emit(value)

    def set_selection(self, song_ids: set[str] | tuple[str, ...] | list[str], primary: str = "") -> None:
        valid = set(self._document.song_map())
        self._selected_ids = {str(value) for value in song_ids if str(value) in valid}
        if primary in valid:
            self._primary = primary
        elif self._primary not in valid:
            self._primary = next(iter(self._selected_ids), "")
        self._render_selection()

    def apply_document(self, document: ProjectDocument) -> None:
        self._document = document.clone()
        valid = set(self._document.song_map())
        self._selected_ids.intersection_update(valid)
        if self._primary not in valid:
            self._primary = next(iter(self._selected_ids), "")
        if not self._primary and self._document.playlist.entries:
            self._primary = self._document.playlist.entries[0].song_id
            self._selected_ids.add(self._primary)
        self._render()

    def _render(self) -> None:
        counts = assignment_counts(self._document)
        self.counts.setText(
            f"Semua {counts['all']} • Kosong {counts['empty']} • Foto {counts['image']} • Video {counts['video']}"
        )
        self.missing.setText(f"⚠ Missing source: {counts['missing']}" if counts["missing"] else "")
        self._updating = True
        try:
            self.listing.clear()
            resolved = TimelineResolver().resolve(self._document)
            duration_by_song = {item.song_id: item.end_tick - item.start_tick for item in resolved.songs}
            for song_id in filtered_song_ids(self._document, self._filter):
                status = assignment_status(self._document, song_id)
                title = _song_title(self._document, song_id)
                artist = _song_artist(self._document, song_id)
                badge = "⚠ Missing" if status.state == "missing" else status.label
                detail = f"{artist} • {badge}" if artist else badge
                item = QListWidgetItem(f"{title}\n{detail}     {_duration_text(duration_by_song.get(song_id, 0))}")
                item.setData(Qt.ItemDataRole.UserRole, song_id)
                item.setToolTip(status.locator or "Belum ada visual")
                self.listing.addItem(item)
            self._render_selection()
        finally:
            self._updating = False

    def _render_selection(self) -> None:
        old = self._updating
        self._updating = True
        try:
            primary_item = None
            for index in range(self.listing.count()):
                item = self.listing.item(index)
                song_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
                item.setSelected(song_id in self._selected_ids)
                if song_id == self._primary:
                    primary_item = item
            if primary_item is not None:
                self.listing.setCurrentItem(primary_item)
        finally:
            self._updating = old

    def _selection_from_ui(self) -> None:
        if self._updating:
            return
        visible_ids = {
            str(self.listing.item(i).data(Qt.ItemDataRole.UserRole) or "")
            for i in range(self.listing.count())
        }
        selected_visible = {
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in self.listing.selectedItems()
        }
        # Hidden selections survive filtering; only visible selection is replaced.
        self._selected_ids.difference_update(visible_ids)
        self._selected_ids.update(selected_visible)
        current = self.listing.currentItem()
        if current is not None:
            self._primary = str(current.data(Qt.ItemDataRole.UserRole) or self._primary)
        if self._primary:
            self._selected_ids.add(self._primary)
        self.selection_changed.emit(set(self._selected_ids), self._primary)

    def _current_from_ui(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if self._updating or current is None:
            return
        song_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if not song_id:
            return
        self._primary = song_id
        self._selected_ids.add(song_id)
        self.selection_changed.emit(set(self._selected_ids), self._primary)


class VisualPreviewCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("visualPreviewCanvas")
        self.setMinimumHeight(300)
        self._document = ProjectDocument.new_empty()
        self._song_id = ""
        self._playhead_tick = 0

    def set_state(self, document: ProjectDocument, song_id: str, playhead_tick: int) -> None:
        self._document = document.clone()
        self._song_id = song_id
        self._playhead_tick = max(0, int(playhead_tick))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#F4F8FD"))
        margin = 14
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
        painter.fillRect(canvas, QColor("#17212F"))
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
        if status.state == "missing":
            painter.setPen(QColor("#F6C453"))
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, f"⚠ SOURCE MISSING\n{status.source_name}\nGunakan Relink")
        elif asset is None:
            painter.setPen(QColor("#D9E5F3"))
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "TANPA VISUAL\nPilih Foto atau Video")
        elif asset.kind == "image":
            image = QImage(asset.locator)
            if image.isNull():
                painter.setPen(QColor("#F6C453"))
                painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, f"Foto tidak dapat dibaca\n{status.source_name}")
            else:
                self._paint_image(painter, canvas, image, settings)
        else:
            painter.fillRect(canvas.adjusted(1, 1, -1, -1), QColor("#24384F"))
            painter.setPen(QColor("#E7F1FC"))
            playback = "LOOP" if settings["loop_video"] else "FREEZE END" if settings["freeze_end"] else "NORMAL"
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, f"▶ VIDEO\n{status.source_name}\n{playback}")
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(canvas.adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, _song_title(self._document, self._song_id))
        transition = TRANSITION_LABELS.get(settings["transition"], settings["transition"])
        painter.drawText(
            canvas.adjusted(12, 8, -12, -8),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            f"{settings['fit'].upper()} • {MOTION_LABELS.get(settings['image_motion'], settings['image_motion'])} • {transition} {settings['transition_seconds']:.1f}s",
        )
        painter.end()

    def _paint_image(self, painter: QPainter, canvas: QRectF, image: QImage, settings: dict) -> None:
        sx = settings["crop_x"] * image.width()
        sy = settings["crop_y"] * image.height()
        sw = settings["crop_width"] * image.width()
        sh = settings["crop_height"] * image.height()
        source = QRectF(sx, sy, sw, sh)
        fit = settings["fit"]
        source_ratio = sw / max(1.0, sh)
        target_ratio = canvas.width() / max(1.0, canvas.height())
        if fit == "fill":
            if source_ratio > target_ratio:
                desired = sh * target_ratio
                source.setX(source.x() + (sw - desired) / 2)
                source.setWidth(desired)
            else:
                desired = sw / target_ratio
                source.setY(source.y() + (sh - desired) / 2)
                source.setHeight(desired)
            target = QRectF(canvas)
        else:
            if source_ratio > target_ratio:
                tw = canvas.width()
                th = tw / source_ratio
            else:
                th = canvas.height()
                tw = th * source_ratio
            target = QRectF(canvas.center().x() - tw / 2, canvas.center().y() - th / 2, tw, th)

        resolved = TimelineResolver().resolve(self._document)
        event = next((item for item in resolved.songs if item.song_id == self._song_id), None)
        progress = 0.0
        if event is not None and event.end_tick > event.start_tick:
            progress = max(0.0, min(1.0, (self._playhead_tick - event.start_tick) / (event.end_tick - event.start_tick)))
        motion_scale = 1.0
        motion_x = 0.0
        if settings["pan_zoom"]:
            motion = settings["image_motion"]
            if motion in {"ken_burns", "zoom_in"}:
                motion_scale = 1.0 + 0.10 * progress
            elif motion == "zoom_out":
                motion_scale = 1.10 - 0.10 * progress
            elif motion == "pan_left":
                motion_x = -0.06 * progress
            elif motion == "pan_right":
                motion_x = 0.06 * progress
        scale = settings["scale"] * motion_scale
        target = QRectF(
            target.center().x() - target.width() * scale / 2,
            target.center().y() - target.height() * scale / 2,
            target.width() * scale,
            target.height() * scale,
        )
        target.translate(
            canvas.width() * (settings["position_x"] + motion_x) * 0.25,
            canvas.height() * settings["position_y"] * 0.25,
        )
        painter.save()
        painter.setClipRect(canvas)
        painter.drawImage(target, image, source)
        painter.restore()


class VisualPreviewWorkspace(QFrame):
    previous_requested = Signal()
    play_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("visualWorkspaceStep06")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(5)
        self.preview = VisualPreviewCanvas()
        root.addWidget(self.preview, 1)
        row = QHBoxLayout()
        self.time = QLabel("00:00:00.000 / 00:00:00.000")
        self.time.setObjectName("metadata")
        row.addWidget(self.time)
        row.addStretch(1)
        prev = FAMButton("◀|", kind="ghost")
        play = FAMButton("▶", kind="primary")
        nxt = FAMButton("|▶", kind="ghost")
        prev.clicked.connect(self.previous_requested)
        play.clicked.connect(self.play_requested)
        nxt.clicked.connect(self.next_requested)
        row.addWidget(prev)
        row.addWidget(play)
        row.addWidget(nxt)
        row.addStretch(1)
        self.source = QLabel("Tanpa Visual")
        self.source.setObjectName("metadata")
        row.addWidget(self.source)
        root.addLayout(row)

    def apply_state(self, document: ProjectDocument, song_id: str, playhead_tick: int) -> None:
        self.preview.set_state(document, song_id, playhead_tick)
        resolved = TimelineResolver().resolve(document)
        event = next((item for item in resolved.songs if item.song_id == song_id), None)
        if event is None:
            self.time.setText("00:00:00.000 / 00:00:00.000")
        else:
            local = max(0, min(event.end_tick - event.start_tick, playhead_tick - event.start_tick))
            duration = event.end_tick - event.start_tick
            self.time.setText(f"{local / TIMEBASE:06.3f}s / {duration / TIMEBASE:06.3f}s")
        if song_id in document.song_map():
            status = assignment_status(document, song_id)
            self.source.setText(status.label + (f" • {status.source_name}" if status.source_name else ""))
        else:
            self.source.setText("Tanpa Visual")


class VisualInspector(QFrame):
    choose_image_requested = Signal()
    choose_video_requested = Signal()
    clear_requested = Signal()
    relink_requested = Signal()
    auto_match_requested = Signal()
    apply_requested = Signal(object)
    apply_selected_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("visualInspectorStep06")
        self._document = ProjectDocument.new_empty()
        self._song_id = ""
        self._updating = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(7)

        heading = QLabel("Properti Visual")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        self.song_label = QLabel("Pilih lagu")
        self.song_label.setObjectName("muted")
        root.addWidget(self.song_label)

        root.addWidget(self._section("Sumber Visual"))
        self.source_label = QLabel("Tanpa Visual")
        self.source_label.setWordWrap(True)
        self.source_label.setObjectName("metadata")
        root.addWidget(self.source_label)
        source_row = QHBoxLayout()
        self.image_button = FAMButton("Pilih Foto", kind="ghost")
        self.video_button = FAMButton("Pilih Video", kind="ghost")
        self.clear_button = FAMButton("Clear", kind="ghost")
        source_row.addWidget(self.image_button)
        source_row.addWidget(self.video_button)
        source_row.addWidget(self.clear_button)
        root.addLayout(source_row)
        repair_row = QHBoxLayout()
        self.relink_button = FAMButton("Relink", kind="ghost")
        self.auto_button = FAMButton("Auto Match", kind="ghost")
        repair_row.addWidget(self.relink_button)
        repair_row.addWidget(self.auto_button)
        root.addLayout(repair_row)

        root.addWidget(self._section("Transform"))
        self.fit = QComboBox()
        self.fit.addItem("Fit", "fit")
        self.fit.addItem("Fill", "fill")
        root.addLayout(self._row("Fit / Fill", self.fit))
        self.crop_x = self._spin(0, 95, 1, "%")
        self.crop_y = self._spin(0, 95, 1, "%")
        self.crop_w = self._spin(5, 100, 1, "%")
        self.crop_h = self._spin(5, 100, 1, "%")
        root.addLayout(self._row("Crop X", self.crop_x))
        root.addLayout(self._row("Crop Y", self.crop_y))
        root.addLayout(self._row("Crop W", self.crop_w))
        root.addLayout(self._row("Crop H", self.crop_h))
        self.pos_x = self._spin(-100, 100, 1, "%")
        self.pos_y = self._spin(-100, 100, 1, "%")
        self.scale = self._spin(25, 400, 5, "%")
        root.addLayout(self._row("Posisi X", self.pos_x))
        root.addLayout(self._row("Posisi Y", self.pos_y))
        root.addLayout(self._row("Scale", self.scale))

        root.addWidget(self._section("Motion & Durasi"))
        self.motion = QComboBox()
        for key, label in MOTION_LABELS.items():
            self.motion.addItem(label, key)
        root.addLayout(self._row("Motion", self.motion))
        self.pan_zoom = QCheckBox("Pan & Zoom")
        self.loop_video = QCheckBox("Loop Video")
        self.freeze_end = QCheckBox("Freeze di Akhir")
        root.addWidget(self.pan_zoom)
        root.addWidget(self.loop_video)
        root.addWidget(self.freeze_end)

        root.addWidget(self._section("Transisi"))
        self.transition = QComboBox()
        for key, label in TRANSITION_LABELS.items():
            self.transition.addItem(label, key)
        self.transition_seconds = self._spin(0, 5, 0.1, " dtk")
        root.addLayout(self._row("Jenis", self.transition))
        root.addLayout(self._row("Durasi", self.transition_seconds))

        self.apply_button = FAMButton("Terapkan", kind="ghost")
        self.apply_selected = FAMButton("Apply to Selected", kind="primary")
        root.addWidget(self.apply_button)
        root.addWidget(self.apply_selected)
        root.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self.image_button.clicked.connect(self.choose_image_requested)
        self.video_button.clicked.connect(self.choose_video_requested)
        self.clear_button.clicked.connect(self.clear_requested)
        self.relink_button.clicked.connect(self.relink_requested)
        self.auto_button.clicked.connect(self.auto_match_requested)
        self.apply_button.clicked.connect(lambda: self.apply_requested.emit(self.settings()))
        self.apply_selected.clicked.connect(lambda: self.apply_selected_requested.emit(self.settings()))
        self.loop_video.toggled.connect(self._loop_toggled)
        self.freeze_end.toggled.connect(self._freeze_toggled)
        self.transition.currentIndexChanged.connect(self._transition_changed)
        self._set_enabled(False)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionHeading")
        return label

    @staticmethod
    def _row(label: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        text = QLabel(label)
        text.setMinimumWidth(76)
        row.addWidget(text)
        row.addWidget(widget, 1)
        return row

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float, suffix: str) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setSingleStep(step)
        box.setDecimals(1)
        box.setSuffix(suffix)
        box.setKeyboardTracking(False)
        return box

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (
            self.image_button, self.video_button, self.clear_button, self.relink_button, self.auto_button,
            self.fit, self.crop_x, self.crop_y, self.crop_w, self.crop_h, self.pos_x, self.pos_y, self.scale,
            self.motion, self.pan_zoom, self.loop_video, self.freeze_end, self.transition, self.transition_seconds,
            self.apply_button, self.apply_selected,
        ):
            widget.setEnabled(bool(enabled))

    def set_song(self, document: ProjectDocument, song_id: str, selected_count: int) -> None:
        self._document = document.clone()
        self._song_id = song_id if song_id in document.song_map() else ""
        if not self._song_id:
            self.song_label.setText("Pilih lagu")
            self.source_label.setText("Tanpa Visual")
            self._set_enabled(False)
            return
        self._set_enabled(True)
        self.song_label.setText(_song_title(document, self._song_id))
        status = assignment_status(document, self._song_id)
        self.source_label.setText(
            f"{status.label}\n{status.source_name or 'Belum ada source'}" + ("\n⚠ File tidak ditemukan" if status.state == "missing" else "")
        )
        self.relink_button.setEnabled(status.state == "missing" and bool(status.asset_id))
        self.clear_button.setEnabled(bool(status.asset_id))
        video_eligible = status.source_kind == "video" and bool(status.asset_id)
        self.loop_video.setEnabled(video_eligible)
        self.freeze_end.setEnabled(video_eligible)
        self.apply_selected.setText(f"Apply to Selected ({max(1, int(selected_count))})")
        values = visual_settings_for_song(document, self._song_id)
        self._updating = True
        try:
            self.fit.setCurrentIndex(max(0, self.fit.findData(values["fit"])))
            self.crop_x.setValue(values["crop_x"] * 100)
            self.crop_y.setValue(values["crop_y"] * 100)
            self.crop_w.setValue(values["crop_width"] * 100)
            self.crop_h.setValue(values["crop_height"] * 100)
            self.pos_x.setValue(values["position_x"] * 100)
            self.pos_y.setValue(values["position_y"] * 100)
            self.scale.setValue(values["scale"] * 100)
            self.motion.setCurrentIndex(max(0, self.motion.findData(values["image_motion"])))
            self.pan_zoom.setChecked(bool(values["pan_zoom"]))
            self.loop_video.setChecked(bool(values["loop_video"]) if video_eligible else False)
            self.freeze_end.setChecked(bool(values["freeze_end"]) if video_eligible else False)
            self.transition.setCurrentIndex(max(0, self.transition.findData(values["transition"])))
            self.transition_seconds.setValue(values["transition_seconds"])
            self._transition_changed()
        finally:
            self._updating = False

    def settings(self) -> dict:
        crop_x = self.crop_x.value() / 100.0
        crop_y = self.crop_y.value() / 100.0
        crop_w = min(self.crop_w.value() / 100.0, 1.0 - crop_x)
        crop_h = min(self.crop_h.value() / 100.0, 1.0 - crop_y)
        return {
            "fit": str(self.fit.currentData() or "fit"),
            "crop_x": crop_x,
            "crop_y": crop_y,
            "crop_width": max(0.05, crop_w),
            "crop_height": max(0.05, crop_h),
            "position_x": self.pos_x.value() / 100.0,
            "position_y": self.pos_y.value() / 100.0,
            "scale": self.scale.value() / 100.0,
            "image_motion": str(self.motion.currentData() or "static"),
            "pan_zoom": bool(self.pan_zoom.isChecked()),
            "loop_video": bool(self.loop_video.isChecked()) if self.loop_video.isEnabled() else False,
            "freeze_end": bool(self.freeze_end.isChecked()) if self.freeze_end.isEnabled() else False,
            "transition": str(self.transition.currentData() or "cut"),
            "transition_seconds": self.transition_seconds.value(),
        }

    def _loop_toggled(self, checked: bool) -> None:
        if self._updating or not checked:
            return
        self.freeze_end.blockSignals(True)
        self.freeze_end.setChecked(False)
        self.freeze_end.blockSignals(False)

    def _freeze_toggled(self, checked: bool) -> None:
        if self._updating or not checked:
            return
        self.loop_video.blockSignals(True)
        self.loop_video.setChecked(False)
        self.loop_video.blockSignals(False)

    def _transition_changed(self, *_args) -> None:
        is_cut = str(self.transition.currentData() or "cut") == "cut"
        self.transition_seconds.setEnabled(not is_cut and bool(self._song_id))
        if is_cut and not self._updating:
            self.transition_seconds.setValue(0.0)


class VisualAlignmentCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("visualAlignmentCanvas")
        self.setMinimumHeight(150)
        self._document = ProjectDocument.new_empty()
        self._selected_ids: set[str] = set()
        self._playhead_tick = 0

    def set_state(self, document: ProjectDocument, selected_ids: set[str], playhead_tick: int) -> None:
        self._document = document.clone()
        self._selected_ids = set(selected_ids)
        self._playhead_tick = max(0, int(playhead_tick))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        resolved = TimelineResolver().resolve(self._document)
        left = 102
        duration = max(TIMEBASE, resolved.duration_tick)
        pps = max(0.01, (max(120, self.width() - left - 12)) / (duration / TIMEBASE))
        painter.fillRect(QRectF(0, 0, left, self.height()), QColor("#F8FBFF"))
        painter.setPen(QColor(TOKENS.text_primary))
        painter.drawText(QRectF(10, 18, 86, 42), Qt.AlignmentFlag.AlignVCenter, "V1  Visual")
        painter.drawText(QRectF(10, 82, 86, 42), Qt.AlignmentFlag.AlignVCenter, "A1  Audio")
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawLine(left, 0, left, self.height())
        painter.drawLine(0, 72, self.width(), 72)
        songs = self._document.song_map()
        for event in resolved.songs:
            x = left + (event.start_tick / TIMEBASE) * pps
            width = max(4.0, ((event.end_tick - event.start_tick) / TIMEBASE) * pps)
            selected = event.song_id in self._selected_ids
            audio_rect = QRectF(x, 88, width, 30)
            painter.setPen(QPen(QColor("#1766E8" if selected else "#6DA9EA"), 2 if selected else 1))
            painter.setBrush(QColor("#E7F2FF"))
            painter.drawRoundedRect(audio_rect, 3, 3)
            title = songs[event.song_id].display_title or "Lagu"
            painter.setPen(QColor("#164B8A"))
            painter.drawText(audio_rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, title)
            status = assignment_status(self._document, event.song_id)
            if status.asset_id:
                visual_rect = QRectF(x, 24, width, 30)
                fill = "#FFE8C2" if status.state == "missing" else "#DDEEDB" if status.source_kind == "image" else "#E1E8FF"
                border = "#D39A33" if status.state == "missing" else "#4E9B68" if status.source_kind == "image" else "#6279C8"
                painter.setPen(QPen(QColor("#1766E8" if selected else border), 2 if selected else 1))
                painter.setBrush(QColor(fill))
                painter.drawRoundedRect(visual_rect, 3, 3)
                painter.setPen(QColor(TOKENS.text_primary))
                painter.drawText(visual_rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, status.label)
        play_x = left + (self._playhead_tick / TIMEBASE) * pps
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        painter.drawLine(play_x, 2, play_x, self.height() - 2)
        painter.end()
