from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .editor_models import Layer, ProjectDocument, TIMEBASE
from .foundation_components import FAMButton, FAMCard, FAMSegmented, FAMStatusChip
from .foundation_tokens import TOKENS
from .spectrum_feature import normalize_spectrum_properties
from .spectrum_preview_step08 import SpectrumPreviewCanvas
from .spectrum_step08 import STEP08_PRESETS, spectrum_geometry
from .timeline_resolver import TimelineResolver


@dataclass(frozen=True)
class SpectrumInspectorState:
    layer_id: str
    spectrum_type: str
    center_x_px: float
    center_y_px: float
    size_ratio: float
    band_count: int
    thickness: float
    opacity: float
    smoothing: float
    reactive_scale: float
    accent_color: str
    preset_id: str
    locked: bool


class SpectrumLayerRow(FAMCard):
    selected = Signal(str)
    visibility_changed = Signal(str, bool)
    lock_changed = Signal(str, bool)

    def __init__(self, layer: Layer, *, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.layer_id = layer.layer_id
        self.setProperty("selected", bool(selected))
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)

        self.select_button = QPushButton(layer.name or layer.type)
        self.select_button.setObjectName("tabButton")
        self.select_button.setCheckable(True)
        self.select_button.setChecked(bool(selected))
        self.select_button.setToolTip(f"{layer.type} • order {layer.order}")
        self.select_button.clicked.connect(lambda: self.selected.emit(self.layer_id))
        row.addWidget(self.select_button, 1)

        self.eye = QPushButton("●" if layer.enabled else "○")
        self.eye.setFixedWidth(34)
        self.eye.setToolTip("Tampil / sembunyikan")
        self.eye.setAccessibleName("Tampil layer")
        self.eye.clicked.connect(lambda: self.visibility_changed.emit(self.layer_id, not layer.enabled))
        row.addWidget(self.eye)

        self.lock = QPushButton("🔒" if layer.locked else "🔓")
        self.lock.setFixedWidth(38)
        self.lock.setToolTip("Kunci / buka kunci")
        self.lock.setAccessibleName("Kunci layer")
        self.lock.clicked.connect(lambda: self.lock_changed.emit(self.layer_id, not layer.locked))
        row.addWidget(self.lock)


class SpectrumPresetCard(FAMCard):
    requested = Signal(str)

    def __init__(self, preset_id: str, spec: dict[str, object], *, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.preset_id = preset_id
        supported = bool(spec.get("supported"))
        self.setMinimumWidth(92)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 7, 7, 7)
        lay.setSpacing(3)
        label = QLabel(str(spec.get("label", preset_id)))
        label.setObjectName("metadata")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(label)
        preview = QLabel("◉" if "circular" in str(spec.get("properties", {})) else "▥")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumHeight(30)
        preview.setStyleSheet(
            f"font-size: 22px; color: {TOKENS.primary_600 if supported else '#9AA7B7'};"
        )
        lay.addWidget(preview)
        button = FAMButton("Pakai" if supported else "Tidak didukung", kind="primary" if selected and supported else "secondary")
        button.setEnabled(supported)
        if not supported:
            button.setToolTip(str(spec.get("reason", "Belum didukung renderer final.")))
        button.clicked.connect(lambda: self.requested.emit(self.preset_id))
        lay.addWidget(button)


class SpectrumLayerContext(QFrame):
    layer_selected = Signal(str)
    visibility_changed = Signal(str, bool)
    lock_changed = Signal(str, bool)
    add_spectrum_requested = Signal()
    preset_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("spectrumLayerContext")
        self._document = ProjectDocument.new_empty()
        self._selected_layer_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        heading = QLabel("Layers")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        subtitle = QLabel("Spectrum • Logo • Judul • Overlay")
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.add_button = FAMButton("+ Tambah Spectrum", kind="primary")
        self.add_button.clicked.connect(self.add_spectrum_requested.emit)
        root.addWidget(self.add_button)

        self.layer_scroll = QScrollArea()
        self.layer_scroll.setWidgetResizable(True)
        self.layer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.layer_host = QWidget()
        self.layer_layout = QVBoxLayout(self.layer_host)
        self.layer_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_layout.setSpacing(5)
        self.layer_scroll.setWidget(self.layer_host)
        root.addWidget(self.layer_scroll, 1)

        preset_heading = QLabel("Preset Spectrum")
        preset_heading.setObjectName("sectionHeading")
        root.addWidget(preset_heading)
        self.preset_host = QWidget()
        self.preset_grid = QGridLayout(self.preset_host)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setSpacing(5)
        root.addWidget(self.preset_host)
        self.unsupported_note = QLabel("Neon Glow, Rainbow, dan Particles tampil sebagai referensi golden tetapi dinonaktifkan karena renderer final recovered belum mendukung efek tersebut.")
        self.unsupported_note.setWordWrap(True)
        self.unsupported_note.setObjectName("metadata")
        root.addWidget(self.unsupported_note)

    def set_state(self, document: ProjectDocument, selected_layer_id: str = "") -> None:
        self._document = document.clone()
        self._selected_layer_id = selected_layer_id
        while self.layer_layout.count():
            item = self.layer_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        visual_layers = sorted(self._document.layers, key=lambda layer: layer.order, reverse=True)
        for layer in visual_layers:
            row = SpectrumLayerRow(layer, selected=layer.layer_id == selected_layer_id)
            row.selected.connect(self.layer_selected.emit)
            row.visibility_changed.connect(self.visibility_changed.emit)
            row.lock_changed.connect(self.lock_changed.emit)
            self.layer_layout.addWidget(row)
        if not visual_layers:
            empty = QLabel("Belum ada layer visual. Tambahkan Spectrum untuk mulai.")
            empty.setWordWrap(True)
            empty.setObjectName("muted")
            self.layer_layout.addWidget(empty)
        self.layer_layout.addStretch(1)

        while self.preset_grid.count():
            item = self.preset_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        selected_preset = ""
        layer = self._document.layer_map().get(selected_layer_id)
        if layer is not None and layer.type == "spectrum":
            selected_preset = str(normalize_spectrum_properties(layer.properties).get("preset", ""))
        for index, (preset_id, spec) in enumerate(STEP08_PRESETS.items()):
            card = SpectrumPresetCard(preset_id, spec, selected=preset_id == selected_preset)
            card.requested.connect(self.preset_requested.emit)
            self.preset_grid.addWidget(card, index // 3, index % 3)


class SpectrumWorkspace(QFrame):
    transform_committed = Signal(str, object)
    layer_selected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("spectrumWorkspaceStep08")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        heading = QLabel("Spectrum & Overlay")
        heading.setObjectName("workspaceHeading")
        title_box.addWidget(heading)
        subtitle = QLabel("Audio-reactive • Preview Akurat • Parameter final-render parity")
        subtitle.setObjectName("muted")
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.preview_status = FAMStatusChip("Preview resting", "neutral")
        header.addWidget(self.preview_status)
        root.addLayout(header)

        self.preview = SpectrumPreviewCanvas()
        self.preview.transformCommitted.connect(self.transform_committed.emit)
        self.preview.layerSelected.connect(self.layer_selected.emit)
        root.addWidget(self.preview, 1)

        self.detail = QLabel("Pilih Spectrum. Preview akurat memakai audio project; fallback tidak pernah membuat animasi acak.")
        self.detail.setObjectName("metadata")
        self.detail.setWordWrap(True)
        root.addWidget(self.detail)

    def set_document(self, document: ProjectDocument, selected_layer_id: str, playhead_tick: int) -> None:
        self.preview.set_document(document)
        self.preview.set_selected_layer(selected_layer_id or None)
        self.preview.set_playhead(playhead_tick)

    def set_preview_result(self, path: str, status: str) -> None:
        if path:
            self.preview.set_accurate_frame(path)
            self.preview_status.setText("Audio reaktif")
            self.preview_status.set_status("success")
            self.detail.setText(f"Preview akurat: {status}")
        else:
            self.preview.clear_accurate_frame()
            self.preview_status.setText("Preview resting")
            self.preview_status.set_status("warning")
            self.detail.setText(status or "Audio belum dapat dianalisis; editor tetap aktif dengan resting geometry.")

    def set_preview_pending(self) -> None:
        self.preview.clear_accurate_frame()
        self.preview_status.setText("Menganalisis…")
        self.preview_status.set_status("warning")


class SpectrumInspector(QFrame):
    type_changed = Signal(str)
    geometry_changed = Signal(float, float, float)
    property_changed = Signal(str, object)
    opacity_changed = Signal(float)
    center_requested = Signal()
    reset_requested = Signal()
    duplicate_requested = Signal()
    apply_all_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("spectrumInspectorStep08")
        self._layer_id = ""
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 8, 9, 10)
        root.setSpacing(6)
        heading = QLabel("Spectrum")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        self.identity = QLabel("Pilih layer Spectrum")
        self.identity.setObjectName("metadata")
        root.addWidget(self.identity)

        self.type_segment = FAMSegmented([("linear", "Linear"), ("circular", "Circular")])
        root.addWidget(QLabel("Tipe"))
        root.addWidget(self.type_segment)
        for value, button in self.type_segment._buttons.items():
            button.clicked.connect(lambda _checked=False, v=value: self._emit_type(v))

        form = QFormLayout()
        form.setSpacing(5)
        root.addLayout(form)
        self.size = self._double(10.0, 150.0, 1.0, 1)
        self.x = self._double(-10000.0, 10000.0, 1.0, 1)
        self.y = self._double(-10000.0, 10000.0, 1.0, 1)
        self.bands = QSpinBox()
        self.bands.setRange(16, 512)
        self.bands.setSingleStep(16)
        self.thickness = self._double(1.0, 64.0, 1.0, 1)
        self.opacity = self._double(0.0, 100.0, 5.0, 1)
        self.smoothing = self._double(0.0, 1.0, 0.05, 2)
        self.reactive = self._double(0.05, 8.0, 0.05, 2)
        self.color = QLineEdit()
        self.color.setPlaceholderText("#1B8DFF")
        form.addRow("Ukuran (%)", self.size)
        form.addRow("Posisi X", self.x)
        form.addRow("Posisi Y", self.y)
        form.addRow("Jumlah Band", self.bands)
        form.addRow("Ketebalan", self.thickness)
        form.addRow("Opasitas (%)", self.opacity)
        form.addRow("Smoothing", self.smoothing)
        form.addRow("Reaktif ke Audio", self.reactive)
        form.addRow("Warna Aksen", self.color)

        for widget in (self.size, self.x, self.y):
            widget.editingFinished.connect(self._emit_geometry)
        self.bands.editingFinished.connect(lambda: self._emit_property("band_count", self.bands.value()))
        self.thickness.editingFinished.connect(lambda: self._emit_property("thickness", self.thickness.value()))
        self.opacity.editingFinished.connect(lambda: self._emit_opacity(self.opacity.value() / 100.0))
        self.smoothing.editingFinished.connect(lambda: self._emit_property("smoothing", self.smoothing.value()))
        self.reactive.editingFinished.connect(lambda: self._emit_property("reactive_scale", self.reactive.value()))
        self.color.editingFinished.connect(lambda: self._emit_property("accent_color", self.color.text().strip()))

        row1 = QHBoxLayout()
        self.center_button = FAMButton("Center")
        self.reset_button = FAMButton("Reset Transform")
        row1.addWidget(self.center_button)
        row1.addWidget(self.reset_button)
        root.addLayout(row1)
        row2 = QHBoxLayout()
        self.duplicate_button = FAMButton("Duplicate")
        self.apply_all_button = FAMButton("Apply to All", kind="primary")
        row2.addWidget(self.duplicate_button)
        row2.addWidget(self.apply_all_button)
        root.addLayout(row2)
        self.center_button.clicked.connect(self.center_requested.emit)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.duplicate_button.clicked.connect(self.duplicate_requested.emit)
        self.apply_all_button.clicked.connect(self.apply_all_requested.emit)
        self.note = QLabel("Semua edit project melewati command/Undo. Reactive Scale tidak mengubah volume audio master.")
        self.note.setObjectName("metadata")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        root.addStretch(1)
        self.set_state(None)

    @staticmethod
    def _double(minimum: float, maximum: float, step: float, decimals: int) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setSingleStep(step)
        box.setDecimals(decimals)
        box.setKeyboardTracking(False)
        return box

    def set_state(self, state: SpectrumInspectorState | None) -> None:
        self._updating = True
        controls = [self.size, self.x, self.y, self.bands, self.thickness, self.opacity, self.smoothing, self.reactive, self.color]
        blockers = [QSignalBlocker(widget) for widget in controls]
        try:
            enabled = state is not None
            self._layer_id = state.layer_id if state else ""
            for widget in controls:
                widget.setEnabled(enabled and not bool(state.locked if state else False))
            for button in self.type_segment._buttons.values():
                button.setEnabled(enabled and not bool(state.locked if state else False))
            for button in (self.center_button, self.reset_button, self.duplicate_button, self.apply_all_button):
                button.setEnabled(enabled and not bool(state.locked if state else False))
            if state is None:
                self.identity.setText("Pilih layer Spectrum")
                return
            self.identity.setText(f"{state.layer_id[:8]} • {'TERKUNCI' if state.locked else 'editable'}")
            self.type_segment._buttons[state.spectrum_type].setChecked(True)
            self.size.setValue(state.size_ratio * 100.0)
            self.x.setValue(state.center_x_px)
            self.y.setValue(state.center_y_px)
            self.bands.setValue(state.band_count)
            self.thickness.setValue(state.thickness)
            self.opacity.setValue(state.opacity * 100.0)
            self.smoothing.setValue(state.smoothing)
            self.reactive.setValue(state.reactive_scale)
            self.color.setText(state.accent_color)
        finally:
            del blockers
            self._updating = False

    def _emit_type(self, value: str) -> None:
        if not self._updating and self._layer_id:
            self.type_changed.emit(value)

    def _emit_geometry(self) -> None:
        if not self._updating and self._layer_id:
            self.geometry_changed.emit(self.x.value(), self.y.value(), self.size.value() / 100.0)

    def _emit_property(self, key: str, value) -> None:
        if not self._updating and self._layer_id:
            self.property_changed.emit(key, value)

    def _emit_opacity(self, value: float) -> None:
        if not self._updating and self._layer_id:
            self.opacity_changed.emit(value)


class SpectrumTimelineCanvas(QWidget):
    playhead_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setObjectName("spectrumTimelineStep08")
        self._document = ProjectDocument.new_empty()
        self._playhead = 0

    def set_state(self, document: ProjectDocument, playhead_tick: int) -> None:
        self._document = document.clone()
        self._playhead = max(0, int(playhead_tick))
        self.update()

    def _duration(self) -> int:
        return max(1, TimelineResolver().resolve(self._document).duration_tick)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#F8FBFF"))
        left = 92
        top = 10
        row_h = max(34, (self.height() - 24) // 3)
        width = max(1, self.width() - left - 12)
        duration = self._duration()
        rows = (
            ("Spectrum", [layer for layer in self._document.layers if layer.type == "spectrum" and layer.enabled], "#CFE5FF"),
            ("Overlay", [layer for layer in self._document.layers if layer.type != "spectrum" and layer.enabled], "#E8EEF6"),
            ("Audio", [song for song in self._document.playlist.entries if song.enabled], "#DDF6E7"),
        )
        resolved = TimelineResolver().resolve(self._document)
        layer_resolved = {item.layer_id: item for item in resolved.layers}
        song_resolved = {item.song_id: item for item in resolved.songs}
        painter.setPen(QPen(QColor("#D8E4F2"), 1))
        for index, (label, items, fill) in enumerate(rows):
            y = top + index * row_h
            painter.setPen(QColor("#5C6B82"))
            painter.drawText(QRectF(8, y, left - 16, row_h - 4), Qt.AlignmentFlag.AlignVCenter, label)
            painter.setPen(QPen(QColor("#D8E4F2"), 1))
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(QRectF(left, y + 3, width, row_h - 10), 6, 6)
            for item in items:
                if label == "Audio":
                    timing = song_resolved.get(item.song_id)
                    spans = [(timing.start_tick, timing.end_tick)] if timing else []
                else:
                    timing = layer_resolved.get(item.layer_id)
                    spans = [(span.start_tick, span.end_tick) for span in timing.intervals] if timing else []
                for start, end in spans:
                    x = left + width * start / duration
                    w = max(2.0, width * max(1, end - start) / duration)
                    painter.setBrush(QColor(fill))
                    painter.setPen(QPen(QColor("#9FBAD8"), 1))
                    painter.drawRoundedRect(QRectF(x, y + 7, w, row_h - 18), 4, 4)
        play_x = left + width * min(self._playhead, duration) / duration
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        painter.drawLine(int(play_x), top, int(play_x), self.height() - 8)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        left = 92
        width = max(1, self.width() - left - 12)
        if event.position().x() < left:
            return
        ratio = max(0.0, min(1.0, (event.position().x() - left) / width))
        self.playhead_requested.emit(int(round(self._duration() * ratio)))
        event.accept()


def inspector_state(document: ProjectDocument, layer: Layer | None) -> SpectrumInspectorState | None:
    if layer is None or layer.type != "spectrum":
        return None
    props = normalize_spectrum_properties(layer.properties)
    geometry = spectrum_geometry(document, layer)
    return SpectrumInspectorState(
        layer_id=layer.layer_id,
        spectrum_type=props["spectrum_type"],
        center_x_px=geometry.center_x_px,
        center_y_px=geometry.center_y_px,
        size_ratio=geometry.size_ratio,
        band_count=int(props["band_count"]),
        thickness=float(props["thickness"]),
        opacity=float(layer.opacity),
        smoothing=float(props["smoothing"]),
        reactive_scale=float(props["reactive_scale"]),
        accent_color=str(props["accent_color"]),
        preset_id=str(props.get("preset", "")),
        locked=bool(layer.locked),
    )
