from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .editor_models import ProjectDocument, TIMEBASE
from .foundation_components import FAMButton, FAMCard, FAMSegmented
from .foundation_tokens import TOKENS
from .preview_scene import PreviewCanvas
from .timeline_precision import song_mix, timeline_gaps, timeline_markers
from .timeline_resolver import TimelineResolver


def _timecode(tick: int, *, millis: bool = True) -> str:
    total = max(0, int(tick)) / TIMEBASE
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}" if millis else f"{hours:02d}:{minutes:02d}:{int(seconds):02d}"


def _song_title(document: ProjectDocument, song_id: str) -> str:
    song = document.song_map().get(song_id)
    if song is None:
        return "Lagu"
    asset = document.asset_map().get(song.asset_id)
    if song.display_title.strip():
        return song.display_title.strip()
    return Path(asset.locator).stem if asset is not None else "Lagu"


LANE_LABELS = (
    ("V3", "Teks & Elemen"),
    ("V2", "Overlay"),
    ("V1", "Video Utama"),
    ("A1", "Lagu Utama"),
    ("A2", "Background"),
    ("S1", "Spectrum"),
    ("S2", "Stiker/Overlay"),
)


def lane_for_layer(layer) -> str:
    if layer.type in {"text", "song_title", "playlist_visual", "progress", "song_time"}:
        return "V3"
    if layer.type in {"overlay", "vinyl", "song_cover"}:
        return "V2"
    if layer.type in {"background", "song_visual"}:
        return "V1"
    if layer.type == "spectrum":
        return "S1"
    return "S2"


class _TrackRow(QWidget):
    action_requested = Signal(str, str, bool)

    def __init__(self, key: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(4)
        key_label = QLabel(key)
        key_label.setObjectName("metadata")
        key_label.setFixedWidth(23)
        row.addWidget(key_label)
        self.name = QLabel(label)
        self.name.setObjectName("metadata")
        row.addWidget(self.name, 1)
        self.lock = QPushButton("🔒")
        self.lock.setCheckable(True)
        self.lock.setToolTip(f"Kunci {key}")
        self.lock.setFixedSize(25, 25)
        self.eye = QPushButton("◉")
        self.eye.setCheckable(True)
        self.eye.setChecked(True)
        self.eye.setToolTip(f"Tampil/sembunyi {key}")
        self.eye.setFixedSize(25, 25)
        self.lock.toggled.connect(lambda value: self.action_requested.emit(self.key, "lock", bool(value)))
        self.eye.toggled.connect(lambda value: self.action_requested.emit(self.key, "visible", bool(value)))
        row.addWidget(self.lock)
        row.addWidget(self.eye)

    def set_state(self, *, locked: bool, visible: bool, enabled: bool = True) -> None:
        for button, value in ((self.lock, locked), (self.eye, visible)):
            button.blockSignals(True)
            button.setChecked(bool(value))
            button.blockSignals(False)
            button.setEnabled(enabled)


class TimelineContextWidget(QFrame):
    lane_action_requested = Signal(str, str, bool)
    marker_selected = Signal(str)
    clip_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelineContext")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self.tabs = FAMSegmented([("track", "Track"), ("marker", "Marker"), ("clip", "Daftar Klip")])
        root.addWidget(self.tabs)
        for value, button in self.tabs._buttons.items():
            button.clicked.connect(lambda _checked=False, key=value: self._select_tab(key))

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        track_page = QWidget()
        track_layout = QVBoxLayout(track_page)
        track_layout.setContentsMargins(0, 4, 0, 0)
        track_layout.setSpacing(1)
        self.track_rows: dict[str, _TrackRow] = {}
        group = None
        for key, label in LANE_LABELS:
            target_group = "Video (3)" if key.startswith("V") else ("Audio (2)" if key.startswith("A") else "Elemen (2)")
            if target_group != group:
                heading = QLabel(target_group)
                heading.setObjectName("sectionHeading")
                track_layout.addWidget(heading)
                group = target_group
            row = _TrackRow(key, label)
            row.action_requested.connect(self.lane_action_requested)
            self.track_rows[key] = row
            track_layout.addWidget(row)
        track_layout.addStretch(1)
        self.stack.addWidget(track_page)

        self.marker_list = QListWidget()
        self.marker_list.itemClicked.connect(
            lambda item: self.marker_selected.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        )
        self.stack.addWidget(self.marker_list)

        self.clip_list = QListWidget()
        self.clip_list.itemClicked.connect(
            lambda item: self.clip_selected.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        )
        self.stack.addWidget(self.clip_list)

    def _select_tab(self, key: str) -> None:
        self.stack.setCurrentIndex({"track": 0, "marker": 1, "clip": 2}.get(key, 0))

    def apply_document(self, document: ProjectDocument) -> None:
        lane_layers = {key: [] for key, _ in LANE_LABELS}
        for layer in document.layers:
            lane_layers.setdefault(lane_for_layer(layer), []).append(layer)
        for key, row in self.track_rows.items():
            if key == "A1":
                enabled = bool(document.playlist.entries)
                visible = all(song.enabled for song in document.playlist.entries) if enabled else True
                locked = bool(document.playlist.entries) and all(song_mix(document, song.song_id)["locked"] for song in document.playlist.entries)
                row.set_state(locked=locked, visible=visible, enabled=enabled)
            elif key == "A2":
                row.set_state(locked=False, visible=True, enabled=False)
            else:
                layers = lane_layers.get(key, [])
                row.set_state(
                    locked=bool(layers) and all(layer.locked for layer in layers),
                    visible=all(layer.enabled for layer in layers) if layers else True,
                    enabled=bool(layers),
                )

        self.marker_list.clear()
        for marker in timeline_markers(document):
            item = QListWidgetItem(f"{_timecode(marker.tick, millis=False)}   {marker.label}")
            item.setData(Qt.ItemDataRole.UserRole, marker.marker_id)
            self.marker_list.addItem(item)
        if self.marker_list.count() == 0:
            self.marker_list.addItem(QListWidgetItem("Belum ada marker"))

        self.clip_list.clear()
        resolved = TimelineResolver().resolve(document)
        for event in resolved.songs:
            item = QListWidgetItem(f"A1  {_timecode(event.start_tick, millis=False)}  {_song_title(document, event.song_id)}")
            item.setData(Qt.ItemDataRole.UserRole, event.song_id)
            self.clip_list.addItem(item)
        for layer in document.layers:
            item = QListWidgetItem(f"{lane_for_layer(layer)}  {layer.name}")
            item.setData(Qt.ItemDataRole.UserRole, f"layer:{layer.layer_id}")
            self.clip_list.addItem(item)


class TimelinePreviewWorkspace(QFrame):
    previous_requested = Signal()
    next_requested = Signal()
    play_requested = Signal()
    fullscreen_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelineWorkspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(5)
        self.preview = PreviewCanvas(self)
        self.preview.setMinimumHeight(250)
        root.addWidget(self.preview, 1)

        controls = QHBoxLayout()
        controls.setContentsMargins(4, 0, 4, 0)
        self.time = QLabel("00:00:00.000 / 00:00:00.000")
        self.time.setObjectName("metadata")
        controls.addWidget(self.time)
        controls.addStretch(1)
        previous = FAMButton("◀|", kind="ghost")
        play = FAMButton("▶", kind="primary")
        next_button = FAMButton("|▶", kind="ghost")
        previous.clicked.connect(self.previous_requested)
        play.clicked.connect(self.play_requested)
        next_button.clicked.connect(self.next_requested)
        controls.addWidget(previous)
        controls.addWidget(play)
        controls.addWidget(next_button)
        controls.addSpacing(14)
        controls.addWidget(QLabel("🔊"))
        self.monitor_volume = QSlider(Qt.Orientation.Horizontal)
        self.monitor_volume.setRange(0, 100)
        self.monitor_volume.setValue(72)
        self.monitor_volume.setMaximumWidth(100)
        controls.addWidget(self.monitor_volume)
        self.aspect = QComboBox()
        self.aspect.addItems(["16:9", "1:1", "9:16"])
        self.aspect.setCurrentText("16:9")
        self.aspect.setMaximumWidth(72)
        controls.addWidget(self.aspect)
        fullscreen = FAMButton("⛶", kind="ghost")
        fullscreen.clicked.connect(self.fullscreen_requested)
        controls.addWidget(fullscreen)
        root.addLayout(controls)

    def apply_document(self, document: ProjectDocument) -> None:
        self.preview.set_document(document)
        self._update_time(document, self.preview._playhead_tick)

    def set_playhead(self, document: ProjectDocument, tick: int) -> None:
        self.preview.set_playhead(tick)
        self._update_time(document, tick)

    def _update_time(self, document: ProjectDocument, tick: int) -> None:
        end = TimelineResolver().resolve(document).duration_tick
        self.time.setText(f"{_timecode(tick)} / {_timecode(end)}")


class TimelineClipInspector(QFrame):
    song_changed = Signal(str, int, int, int, int, int, float, bool)
    layer_changed = Signal(str, int, int, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelineClipInspector")
        self._document = ProjectDocument.new_empty()
        self._song_id = ""
        self._layer_id = ""
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        self.heading = QLabel("Tidak ada clip dipilih")
        self.heading.setObjectName("sectionHeading")
        root.addWidget(self.heading)
        self.subtitle = QLabel("Pilih clip pada timeline")
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)

        self.start = self._spin(0, 86_400, 0.1)
        self.duration = self._spin(0.001, 86_400, 0.1)
        self.fade_in = self._spin(0, 60, 0.1)
        self.fade_out = self._spin(0, 60, 0.1)
        self.crossfade = self._spin(0, 60, 0.1)
        self.volume = self._spin(0, 4, 0.05)
        self.locked = QCheckBox("Lock")
        for label, widget in (
            ("Start", self.start),
            ("Durasi", self.duration),
            ("Fade In", self.fade_in),
            ("Fade Out", self.fade_out),
            ("Crossfade", self.crossfade),
            ("Volume", self.volume),
        ):
            row = QHBoxLayout()
            text = QLabel(label)
            text.setMinimumWidth(72)
            row.addWidget(text)
            row.addWidget(widget, 1)
            root.addLayout(row)
        root.addWidget(self.locked)
        self.apply_button = FAMButton("Terapkan", kind="primary")
        self.apply_button.clicked.connect(self._emit_apply)
        root.addWidget(self.apply_button)
        root.addStretch(1)
        self.set_none()

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setSingleStep(step)
        box.setDecimals(3)
        box.setSuffix(" dtk" if maximum > 4 else "")
        box.setKeyboardTracking(False)
        return box

    def set_none(self) -> None:
        self._song_id = ""
        self._layer_id = ""
        self.heading.setText("Tidak ada clip dipilih")
        self.subtitle.setText("Pilih clip pada timeline")
        self.apply_button.setEnabled(False)
        for widget in (self.start, self.duration, self.fade_in, self.fade_out, self.crossfade, self.volume, self.locked):
            widget.setEnabled(False)

    def set_song(self, document: ProjectDocument, song_id: str) -> None:
        song = document.song_map().get(song_id)
        event = next((item for item in TimelineResolver().resolve(document).songs if item.song_id == song_id), None)
        if song is None or event is None:
            self.set_none()
            return
        self._document = document.clone()
        self._song_id = song_id
        self._layer_id = ""
        self.heading.setText("Lagu Utama")
        self.subtitle.setText(_song_title(document, song_id))
        mix = song_mix(document, song_id)
        duration = event.end_tick - event.start_tick
        values = (
            (self.start, event.start_tick / TIMEBASE),
            (self.duration, duration / TIMEBASE),
            (self.fade_in, mix["fade_in_tick"] / TIMEBASE),
            (self.fade_out, mix["fade_out_tick"] / TIMEBASE),
            (self.crossfade, song.crossfade_in_tick / TIMEBASE),
            (self.volume, float(song.gain)),
        )
        for widget, value in values:
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
            widget.setEnabled(True)
        self.crossfade.setEnabled(document.playlist.mode == "free")
        self.start.setEnabled(document.playlist.mode == "free")
        self.locked.blockSignals(True)
        self.locked.setChecked(bool(mix["locked"]))
        self.locked.blockSignals(False)
        self.locked.setEnabled(True)
        self.apply_button.setEnabled(True)

    def set_layer(self, document: ProjectDocument, layer_id: str) -> None:
        layer = document.layer_map().get(layer_id)
        resolved = TimelineResolver().resolve(document)
        item = next((entry for entry in resolved.layers if entry.layer_id == layer_id), None)
        if layer is None or item is None or not item.intervals:
            self.set_none()
            return
        interval = min(item.intervals, key=lambda value: value.start_tick)
        self._document = document.clone()
        self._song_id = ""
        self._layer_id = layer_id
        self.heading.setText(layer.name)
        self.subtitle.setText(f"{lane_for_layer(layer)} • {layer.type}")
        self.start.setValue(interval.start_tick / TIMEBASE)
        self.duration.setValue((interval.end_tick - interval.start_tick) / TIMEBASE)
        for widget in (self.start, self.duration, self.locked):
            widget.setEnabled(True)
        for widget in (self.fade_in, self.fade_out, self.crossfade, self.volume):
            widget.setEnabled(False)
        self.locked.blockSignals(True)
        self.locked.setChecked(layer.locked)
        self.locked.blockSignals(False)
        self.apply_button.setEnabled(True)

    def _emit_apply(self) -> None:
        if self._song_id:
            self.song_changed.emit(
                self._song_id,
                int(round(self.start.value() * TIMEBASE)),
                int(round(self.duration.value() * TIMEBASE)),
                int(round(self.fade_in.value() * TIMEBASE)),
                int(round(self.fade_out.value() * TIMEBASE)),
                int(round(self.crossfade.value() * TIMEBASE)),
                float(self.volume.value()),
                bool(self.locked.isChecked()),
            )
        elif self._layer_id:
            self.layer_changed.emit(
                self._layer_id,
                int(round(self.start.value() * TIMEBASE)),
                int(round(self.duration.value() * TIMEBASE)),
                bool(self.locked.isChecked()),
            )


@dataclass
class _SongHit:
    song_id: str
    rect: QRectF
    start_tick: int


@dataclass
class _LayerHit:
    layer_id: str
    rect: QRectF


class TimelinePrecisionCanvas(QWidget):
    playhead_requested = Signal(int)
    song_selected = Signal(str)
    layer_selected = Signal(str)
    song_move_requested = Signal(str, int, float)

    LEFT = 145
    RULER = 25
    ROW = 31

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelinePrecisionCanvas")
        self.setMinimumHeight(self.RULER + self.ROW * len(LANE_LABELS) + 4)
        self._document = ProjectDocument.new_empty()
        self._playhead_tick = 0
        self._selected_song_id = ""
        self._selected_layer_id = ""
        self._pixels_per_second = 46.0
        self._fit = True
        self._song_hits: list[_SongHit] = []
        self._layer_hits: list[_LayerHit] = []
        self._drag_song: tuple[str, QPointF, int] | None = None
        self.setMouseTracking(True)

    def set_document(self, document: ProjectDocument) -> None:
        self._document = document.clone()
        if self._selected_song_id not in self._document.song_map():
            self._selected_song_id = ""
        if self._selected_layer_id not in self._document.layer_map():
            self._selected_layer_id = ""
        self.update()

    def set_playhead(self, tick: int) -> None:
        self._playhead_tick = max(0, int(tick))
        self.update()

    def set_selection(self, *, song_id: str = "", layer_id: str = "") -> None:
        self._selected_song_id = song_id
        self._selected_layer_id = layer_id
        self.update()

    def set_pixels_per_second(self, value: float) -> None:
        self._pixels_per_second = max(4.0, min(400.0, float(value)))
        self._fit = False
        self.update()

    def fit_project(self) -> None:
        self._fit = True
        self.update()

    def _pps(self, resolved) -> float:
        duration_seconds = max(1.0, resolved.duration_tick / TIMEBASE)
        if self._fit:
            return max(4.0, (max(160, self.width() - self.LEFT - 12)) / duration_seconds)
        return self._pixels_per_second

    def _x(self, tick: int, pps: float) -> float:
        return self.LEFT + (tick / TIMEBASE) * pps

    def _tick(self, x: float, pps: float) -> int:
        return max(0, int(round(((x - self.LEFT) / max(0.001, pps)) * TIMEBASE)))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        resolved = TimelineResolver().resolve(self._document)
        pps = self._pps(resolved)
        self._song_hits = []
        self._layer_hits = []

        painter.fillRect(QRectF(0, 0, self.LEFT, self.height()), QColor("#F8FBFF"))
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawLine(self.LEFT, 0, self.LEFT, self.height())
        painter.drawLine(0, self.RULER, self.width(), self.RULER)

        duration_seconds = max(1, int(resolved.duration_tick / TIMEBASE) + 1)
        major = 5 if duration_seconds <= 90 else (15 if duration_seconds <= 600 else 30)
        for second in range(0, duration_seconds + major, major):
            x = self.LEFT + second * pps
            if x > self.width():
                break
            painter.setPen(QPen(QColor("#DCE6F3"), 1))
            painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(QRectF(x + 3, 2, 65, 18), Qt.AlignmentFlag.AlignLeft, f"00:{second//60:02d}:{second%60:02d}")

        lane_y: dict[str, float] = {}
        for index, (key, label) in enumerate(LANE_LABELS):
            y = self.RULER + index * self.ROW
            lane_y[key] = y
            painter.setPen(QPen(QColor(TOKENS.border), 1))
            painter.drawLine(0, y, self.width(), y)
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(QRectF(8, y, 28, self.ROW), Qt.AlignmentFlag.AlignVCenter, key)
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(QRectF(38, y, self.LEFT - 42, self.ROW), Qt.AlignmentFlag.AlignVCenter, label)

        # Gaps are explicit Free Timeline silence regions.
        try:
            gaps = timeline_gaps(self._document)
        except Exception:
            gaps = ()
        for gap in gaps:
            left = self._x(gap.start_tick, pps)
            right = self._x(gap.end_tick, pps)
            rect = QRectF(left, lane_y["A1"] + 3, max(1, right - left), self.ROW - 6)
            painter.fillRect(rect, QColor("#FFF5DA"))
            painter.setPen(QPen(QColor("#D7A32C"), 1))
            step = 8
            x = rect.left() - rect.height()
            while x < rect.right():
                painter.drawLine(QPointF(x, rect.bottom()), QPointF(x + rect.height(), rect.top()))
                x += step

        assets = self._document.asset_map()
        songs = self._document.song_map()
        for event in resolved.songs:
            left = self._x(event.start_tick, pps)
            right = self._x(event.end_tick, pps)
            rect = QRectF(left, lane_y["A1"] + 3, max(4, right - left), self.ROW - 6)
            selected = event.song_id == self._selected_song_id
            painter.setPen(QPen(QColor("#1766E8" if selected else "#5A9CF4"), 2 if selected else 1))
            painter.setBrush(QColor("#D8ECFF" if selected else "#EAF4FF"))
            painter.drawRoundedRect(rect, 3, 3)
            title = songs[event.song_id].display_title.strip() or Path(assets[event.asset_id].locator).stem
            painter.setPen(QColor("#164B8A"))
            text = QFontMetrics(painter.font()).elidedText(title, Qt.TextElideMode.ElideRight, max(10, int(rect.width()) - 10))
            painter.drawText(rect.adjusted(5, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, text)
            # lightweight waveform cue
            painter.setPen(QPen(QColor("#63AFE8"), 1))
            mid = rect.center().y()
            for bar in range(int(rect.left()) + 5, int(rect.right()) - 3, 7):
                height = 2 + ((bar * 13) % 7)
                painter.drawLine(bar, mid - height, bar, mid + height)
            fade = songs[event.song_id].crossfade_in_tick
            if fade > 0:
                fade_width = (fade / TIMEBASE) * pps
                painter.fillRect(QRectF(rect.left(), rect.top(), fade_width, rect.height()), QColor(55, 120, 230, 70))
            self._song_hits.append(_SongHit(event.song_id, rect, event.start_tick))

        for layer in sorted(self._document.layers, key=lambda item: item.order):
            item = next((entry for entry in resolved.layers if entry.layer_id == layer.layer_id), None)
            if item is None:
                continue
            lane = lane_for_layer(layer)
            for interval in item.intervals:
                left = self._x(interval.start_tick, pps)
                right = self._x(interval.end_tick, pps)
                rect = QRectF(left, lane_y[lane] + 4, max(4, right - left), self.ROW - 8)
                selected = layer.layer_id == self._selected_layer_id
                palette = {
                    "V1": ("#DFF0F7", "#3A8CA8"),
                    "V2": ("#EDE6FF", "#805CC6"),
                    "V3": ("#E5D7FF", "#7B4DC4"),
                    "S1": ("#F1E4FF", "#8C5BB5"),
                    "S2": ("#FFE7E7", "#C45D69"),
                }
                fill, border = palette.get(lane, ("#EEF3FA", "#6D8098"))
                painter.setPen(QPen(QColor("#1766E8" if selected else border), 2 if selected else 1))
                painter.setBrush(QColor(fill))
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(QColor(TOKENS.text_primary))
                label = QFontMetrics(painter.font()).elidedText(layer.name, Qt.TextElideMode.ElideRight, max(8, int(rect.width()) - 8))
                painter.drawText(rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, label)
                self._layer_hits.append(_LayerHit(layer.layer_id, rect))

        for marker in timeline_markers(self._document):
            x = self._x(marker.tick, pps)
            color = QColor(marker.color)
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            painter.drawPolygon([QPointF(x - 4, 1), QPointF(x + 4, 1), QPointF(x, 8)])
            painter.drawLine(QPointF(x, 8), QPointF(x, self.height()))
            painter.drawText(QRectF(x + 4, 6, 80, 16), Qt.AlignmentFlag.AlignLeft, marker.label)

        play_x = self._x(self._playhead_tick, pps)
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        painter.drawLine(QPointF(play_x, 0), QPointF(play_x, self.height()))
        painter.setBrush(QColor(TOKENS.primary_600))
        painter.drawRoundedRect(QRectF(play_x - 27, 0, 54, 18), 7, 7)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(play_x - 25, 0, 50, 18), Qt.AlignmentFlag.AlignCenter, _timecode(self._playhead_tick, millis=False)[3:])
        painter.end()

    def mousePressEvent(self, event) -> None:
        resolved = TimelineResolver().resolve(self._document)
        pps = self._pps(resolved)
        pos = event.position()
        if pos.y() <= self.RULER and pos.x() >= self.LEFT:
            tick = self._tick(pos.x(), pps)
            self.playhead_requested.emit(tick)
            return
        for hit in reversed(self._song_hits):
            if hit.rect.contains(pos):
                self._selected_song_id = hit.song_id
                self._selected_layer_id = ""
                self.song_selected.emit(hit.song_id)
                if self._document.playlist.mode == "free" and event.button() == Qt.MouseButton.LeftButton:
                    self._drag_song = (hit.song_id, pos, hit.start_tick)
                self.update()
                return
        for hit in reversed(self._layer_hits):
            if hit.rect.contains(pos):
                self._selected_layer_id = hit.layer_id
                self._selected_song_id = ""
                self.layer_selected.emit(hit.layer_id)
                self.update()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_song is not None:
            song_id, start_pos, start_tick = self._drag_song
            delta_px = event.position().x() - start_pos.x()
            target = max(0, start_tick + int(round((delta_px / max(0.001, self._pps(TimelineResolver().resolve(self._document)))) * TIMEBASE)))
            if abs(delta_px) >= 2:
                self.song_move_requested.emit(song_id, target, self._pps(TimelineResolver().resolve(self._document)))
            self._drag_song = None
        super().mouseReleaseEvent(event)


class TimelinePrecisionPanel(QFrame):
    mode_requested = Signal(str)
    split_requested = Signal()
    delete_gap_requested = Signal()
    ripple_changed = Signal(bool)
    snap_changed = Signal(bool)
    marker_requested = Signal()
    zoom_requested = Signal(int)
    fit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelinePrecisionPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 2, 8, 2)
        toolbar.setSpacing(5)
        self.mode = FAMSegmented([("packed", "Packed"), ("free", "Free")])
        for value, button in self.mode._buttons.items():
            button.clicked.connect(lambda _checked=False, key=value: self.mode_requested.emit(key))
        toolbar.addWidget(self.mode)
        self.split = FAMButton("✂  Split", kind="ghost")
        self.delete_gap = FAMButton("Delete Gap", kind="ghost")
        self.ripple = FAMButton("Ripple", kind="ghost")
        self.ripple.setCheckable(True)
        self.snap = FAMButton("Snap", kind="ghost")
        self.snap.setCheckable(True)
        self.snap.setChecked(True)
        self.marker = FAMButton("●  Marker", kind="ghost")
        for widget in (self.split, self.delete_gap, self.ripple, self.snap, self.marker):
            toolbar.addWidget(widget)
        self.split.clicked.connect(self.split_requested)
        self.delete_gap.clicked.connect(self.delete_gap_requested)
        self.ripple.toggled.connect(self.ripple_changed)
        self.snap.toggled.connect(self.snap_changed)
        self.marker.clicked.connect(self.marker_requested)
        toolbar.addStretch(1)
        minus = FAMButton("−", kind="ghost")
        plus = FAMButton("+", kind="ghost")
        fit = FAMButton("Fit", kind="ghost")
        minus.clicked.connect(lambda: self.zoom_requested.emit(-1))
        plus.clicked.connect(lambda: self.zoom_requested.emit(1))
        fit.clicked.connect(self.fit_requested)
        toolbar.addWidget(minus)
        self.playhead_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.playhead_label.setObjectName("metadata")
        toolbar.addWidget(self.playhead_label)
        toolbar.addWidget(plus)
        toolbar.addWidget(fit)
        root.addLayout(toolbar)
        self.canvas = TimelinePrecisionCanvas()
        root.addWidget(self.canvas, 1)

    def apply_document(self, document: ProjectDocument, playhead_tick: int, *, ripple: bool, snap: bool) -> None:
        self.canvas.set_document(document)
        self.canvas.set_playhead(playhead_tick)
        for key, button in self.mode._buttons.items():
            button.blockSignals(True)
            button.setChecked(key == document.playlist.mode)
            button.blockSignals(False)
        self.ripple.blockSignals(True)
        self.ripple.setChecked(bool(ripple))
        self.ripple.blockSignals(False)
        self.snap.blockSignals(True)
        self.snap.setChecked(bool(snap))
        self.snap.blockSignals(False)
        end = TimelineResolver().resolve(document).duration_tick
        self.playhead_label.setText(f"{_timecode(playhead_tick)} / {_timecode(end)}")
