from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QSignalBlocker, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .editor_models import Layer, ProjectDocument
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
        self.setFixedHeight(42)
        self.setStyleSheet(
            "QFrame#famCard {"
            + (f"background:#EAF4FF;border:1px solid {TOKENS.primary_600};" if selected else "background:#FFFFFF;border:1px solid #E1EAF5;")
            + "border-radius:7px;}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(5, 3, 5, 3)
        row.setSpacing(3)

        arrow = QLabel("›")
        arrow.setFixedWidth(12)
        arrow.setStyleSheet("color:#6E86A8;font-weight:700;")
        row.addWidget(arrow)
        icon = QLabel("▥" if layer.type == "spectrum" else ("▣" if layer.type == "background" else "T" if layer.type in {"text", "song_title"} else "◇"))
        icon.setFixedWidth(19)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"color:{TOKENS.primary_600};font-weight:700;")
        row.addWidget(icon)

        self.select_button = QPushButton(layer.name or layer.type)
        self.select_button.setObjectName("tabButton")
        self.select_button.setCheckable(True)
        self.select_button.setChecked(bool(selected))
        self.select_button.setToolTip(f"{layer.type} • order {layer.order}")
        self.select_button.setStyleSheet("text-align:left;border:0;background:transparent;padding:3px;")
        self.select_button.clicked.connect(lambda: self.selected.emit(self.layer_id))
        row.addWidget(self.select_button, 1)

        self.eye = QPushButton("◉" if layer.enabled else "○")
        self.eye.setObjectName("tabButton")
        self.eye.setFixedWidth(27)
        self.eye.setToolTip("Tampil / sembunyikan")
        self.eye.clicked.connect(lambda: self.visibility_changed.emit(self.layer_id, not layer.enabled))
        row.addWidget(self.eye)

        self.lock = QPushButton("▣" if layer.locked else "♙")
        self.lock.setObjectName("tabButton")
        self.lock.setFixedWidth(27)
        self.lock.setToolTip("Kunci / buka kunci")
        self.lock.clicked.connect(lambda: self.lock_changed.emit(self.layer_id, not layer.locked))
        row.addWidget(self.lock)
        menu = QLabel("⋯")
        menu.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menu.setFixedWidth(18)
        menu.setStyleSheet("color:#48617D;font-size:17px;")
        row.addWidget(menu)


class SpectrumPresetPreview(QWidget):
    def __init__(self, preset_id: str, supported: bool, parent=None) -> None:
        super().__init__(parent)
        self.preset_id = preset_id
        self.supported = supported
        self.setMinimumHeight(54)
        self.setMaximumHeight(60)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor("#BFD4EC"), 1))
        p.setBrush(QColor("#071A32"))
        p.drawRoundedRect(rect, 5, 5)
        inner = rect.adjusted(6, 7, -6, -7)
        colors = {
            "classic": "#2B9BFF",
            "neon_glow": "#E653FF",
            "rainbow": "#52E78F",
            "minimal": "#AAB8CA",
            "wave": "#7C68FF",
            "particles": "#28A8FF",
            "retro": "#FF4A9B",
            "trance": "#776CFF",
            "ambient": "#5D8EEB",
        }
        color = QColor(colors.get(self.preset_id, "#2B9BFF"))
        if not self.supported:
            color.setAlpha(185)
        p.setPen(QPen(color, 2))

        if self.preset_id == "wave":
            path = QPainterPath()
            for i in range(40):
                ratio = i / 39
                x = inner.left() + ratio * inner.width()
                y = inner.center().y() - math.sin(ratio * math.tau * 2.2) * inner.height() * 0.28
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.drawPath(path)
        elif self.preset_id == "particles":
            for i in range(22):
                x = inner.left() + ((i * 37) % 97) / 96 * inner.width()
                y = inner.top() + ((i * 59) % 83) / 82 * inner.height()
                p.drawEllipse(QPointF(x, y), 1.6 + (i % 3), 1.6 + (i % 3))
        elif self.preset_id == "ambient":
            path = QPainterPath()
            for i in range(20):
                ratio = i / 19
                x = inner.left() + ratio * inner.width()
                y = inner.center().y() - (0.18 + 0.45 * abs(math.sin(i * 0.9))) * inner.height() * 0.45
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.drawPath(path)
        else:
            count = 15
            bar_w = max(2.0, inner.width() / count * 0.52)
            for i in range(count):
                amp = 0.18 + 0.78 * abs(math.sin(i * 0.61 + (0.8 if self.preset_id in {"trance", "retro"} else 0.0)))
                h = inner.height() * amp
                x = inner.left() + (i + 0.5) * inner.width() / count
                if self.preset_id == "rainbow":
                    rainbow = QColor.fromHsv(int(i / count * 300), 210, 245)
                    p.setPen(QPen(rainbow, bar_w))
                p.drawLine(QPointF(x, inner.bottom()), QPointF(x, inner.bottom() - h))
        p.end()


class SpectrumPresetCard(FAMCard):
    requested = Signal(str)

    def __init__(self, preset_id: str, spec: dict[str, object], *, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.preset_id = preset_id
        self.supported = bool(spec.get("supported"))
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.supported else Qt.CursorShape.ForbiddenCursor)
        self.setMinimumWidth(82)
        self.setMaximumWidth(110)
        self.setFixedHeight(87)
        border = TOKENS.primary_600 if selected else "#D7E3F1"
        self.setStyleSheet(
            f"QFrame#famCard{{background:#FFFFFF;border:{2 if selected else 1}px solid {border};border-radius:6px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 3)
        lay.setSpacing(2)
        lay.addWidget(SpectrumPresetPreview(preset_id, self.supported), 1)
        label = QLabel(str(spec.get("label", preset_id)))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:10px;color:#17355E;")
        lay.addWidget(label)
        if not self.supported:
            self.setToolTip(str(spec.get("reason", "Belum didukung renderer final.")))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.supported:
            self.requested.emit(self.preset_id)
            event.accept()
            return
        super().mousePressEvent(event)


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
        root.setContentsMargins(4, 3, 4, 4)
        root.setSpacing(5)

        header = QHBoxLayout()
        heading = QLabel("Lapisan (Layer)")
        heading.setObjectName("sectionHeading")
        header.addWidget(heading)
        header.addStretch(1)
        self.add_button = FAMButton("＋  Tambah Spectrum", kind="primary")
        self.add_button.setFixedHeight(34)
        self.add_button.clicked.connect(self.add_spectrum_requested.emit)
        header.addWidget(self.add_button)
        root.addLayout(header)

        self.layer_scroll = QScrollArea()
        self.layer_scroll.setWidgetResizable(True)
        self.layer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.layer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layer_scroll.setMinimumHeight(165)
        self.layer_scroll.setMaximumHeight(190)
        self.layer_host = QWidget()
        self.layer_layout = QVBoxLayout(self.layer_host)
        self.layer_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_layout.setSpacing(4)
        self.layer_scroll.setWidget(self.layer_host)
        root.addWidget(self.layer_scroll)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:#DDE7F2;")
        root.addWidget(divider)
        preset_head = QHBoxLayout()
        preset_heading = QLabel("Preset Spectrum")
        preset_heading.setObjectName("sectionHeading")
        preset_head.addWidget(preset_heading)
        preset_head.addStretch(1)
        see_all = QLabel("Lihat Semua  →")
        see_all.setStyleSheet(f"color:{TOKENS.primary_600};font-size:10px;")
        preset_head.addWidget(see_all)
        root.addLayout(preset_head)

        self.preset_host = QWidget()
        self.preset_grid = QGridLayout(self.preset_host)
        self.preset_grid.setContentsMargins(0, 0, 0, 0)
        self.preset_grid.setHorizontalSpacing(5)
        self.preset_grid.setVerticalSpacing(5)
        root.addWidget(self.preset_host)
        self.unsupported_note = QLabel("")
        self.unsupported_note.hide()
        root.addStretch(1)

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
            empty = QLabel("Belum ada layer visual.")
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
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(6)

        header = QHBoxLayout()
        heading = QLabel("Pratinjau Video")
        heading.setObjectName("workspaceHeading")
        header.addWidget(heading)
        header.addStretch(1)
        ratio = FAMButton("▣  16:9 (YouTube)", kind="secondary")
        quality = FAMButton("⚙  1080p (Full HD)", kind="secondary")
        fullscreen = FAMButton("⛶", kind="ghost")
        ratio.setMinimumWidth(154)
        quality.setMinimumWidth(166)
        fullscreen.setFixedWidth(38)
        header.addWidget(ratio)
        header.addWidget(quality)
        header.addWidget(fullscreen)
        root.addLayout(header)

        self.preview = SpectrumPreviewCanvas()
        self.preview.setMinimumHeight(310)
        self.preview.transformCommitted.connect(self.transform_committed.emit)
        self.preview.layerSelected.connect(self.layer_selected.emit)
        root.addWidget(self.preview, 1)

        transport = QFrame()
        transport.setStyleSheet("background:#F3F8FE;border:1px solid #DFEAF6;border-radius:7px;")
        transport_row = QHBoxLayout(transport)
        transport_row.setContentsMargins(9, 5, 9, 5)
        transport_row.setSpacing(8)
        play = FAMButton("▶", kind="ghost")
        play.setFixedWidth(34)
        transport_row.addWidget(play)
        self.time_label = QLabel("01:24 / 42:18")
        self.time_label.setStyleSheet("color:#173A70;font-weight:600;")
        transport_row.addWidget(self.time_label)
        seek = QSlider(Qt.Orientation.Horizontal)
        seek.setRange(0, 100)
        seek.setValue(18)
        seek.setEnabled(False)
        transport_row.addWidget(seek, 1)
        transport_row.addWidget(QLabel("🔊"))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(72)
        volume.setEnabled(False)
        volume.setFixedWidth(92)
        transport_row.addWidget(volume)
        transport_row.addWidget(QLabel("│  ◫  ⛶"))
        self.preview_status = FAMStatusChip("Preview resting", "neutral")
        self.preview_status.setMaximumWidth(108)
        transport_row.addWidget(self.preview_status)
        root.addWidget(transport)

        self.detail = QLabel("")
        self.detail.setObjectName("metadata")
        self.detail.setMaximumHeight(1)
        self.detail.hide()
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
            self.detail.setText(status or "Audio belum dapat dianalisis.")

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
        root.setContentsMargins(10, 7, 10, 9)
        root.setSpacing(6)

        heading = QLabel("Pengaturan Spectrum")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        self.identity = QLabel("Pilih layer Spectrum")
        self.identity.setObjectName("metadata")
        self.identity.hide()
        root.addWidget(self.identity)

        root.addWidget(self._caption("Tipe Spectrum"))
        self.type_segment = FAMSegmented([("linear", "▥  Linear"), ("circular", "◯  Circular")])
        self.type_segment.setFixedHeight(40)
        root.addWidget(self.type_segment)
        for value, button in self.type_segment._buttons.items():
            button.clicked.connect(lambda _checked=False, v=value: self._emit_type(v))

        self.size = self._double(10.0, 150.0, 1.0, 1, "%")
        self.size_slider = self._slider(10, 150, 78)
        self._control_row(root, "Ukuran", self.size_slider, self.size)

        pos = QHBoxLayout()
        pos.addWidget(self._caption("Posisi"))
        pos.addStretch(1)
        pos.addWidget(QLabel("X"))
        self.x = self._double(-10000.0, 10000.0, 1.0, 0)
        self.x.setFixedWidth(82)
        pos.addWidget(self.x)
        pos.addWidget(QLabel("Y"))
        self.y = self._double(-10000.0, 10000.0, 1.0, 0)
        self.y.setFixedWidth(82)
        pos.addWidget(self.y)
        root.addLayout(pos)

        self.bands = QSpinBox()
        self.bands.setRange(16, 512)
        self.bands.setSingleStep(16)
        self.bands.setFixedWidth(68)
        self.bands_slider = self._slider(16, 512, 128)
        self._control_row(root, "Jumlah Band", self.bands_slider, self.bands)

        self.thickness = self._double(1.0, 64.0, 1.0, 1, " px")
        self.thickness_slider = self._slider(1, 64, 12)
        self._control_row(root, "Ketebalan", self.thickness_slider, self.thickness)

        self.opacity = self._double(0.0, 100.0, 5.0, 1, "%")
        self.opacity_slider = self._slider(0, 100, 90)
        self._control_row(root, "Opasitas", self.opacity_slider, self.opacity)

        self.smoothing = self._double(0.0, 1.0, 0.05, 2)
        self.smoothing_slider = self._slider(0, 100, 65)
        self._control_row(root, "Smoothing", self.smoothing_slider, self.smoothing)

        self.reactive = self._double(0.05, 8.0, 0.05, 2)
        self.reactive_slider = self._slider(5, 800, 120)
        self._control_row(root, "Reaktif ke Audio", self.reactive_slider, self.reactive)

        color_row = QHBoxLayout()
        color_row.addWidget(self._caption("Warna Aksen"))
        color_row.addStretch(1)
        self.color_swatch = QFrame()
        self.color_swatch.setFixedSize(30, 27)
        color_row.addWidget(self.color_swatch)
        self.color = QLineEdit()
        self.color.setPlaceholderText("#1B8DFF")
        self.color.setFixedWidth(118)
        color_row.addWidget(self.color)
        root.addLayout(color_row)

        self.mode_note = QFrame()
        self.mode_note.setStyleSheet("background:#EEFBF5;border:1px solid #C6F0D9;border-radius:6px;")
        note_row = QHBoxLayout(self.mode_note)
        note_row.setContentsMargins(8, 5, 8, 5)
        check = QLabel("●")
        check.setStyleSheet("color:#18A65B;font-size:18px;")
        note_row.addWidget(check)
        note = QLabel("Mode Circular dioptimalkan\nPerforma stabil untuk render video.")
        note.setStyleSheet("color:#315A4A;font-size:10px;")
        note_row.addWidget(note, 1)
        root.addWidget(self.mode_note)

        row1 = QHBoxLayout()
        self.center_button = FAMButton("⌾  Center")
        self.reset_button = FAMButton("↶  Reset Transform")
        row1.addWidget(self.center_button)
        row1.addWidget(self.reset_button)
        root.addLayout(row1)
        row2 = QHBoxLayout()
        self.duplicate_button = FAMButton("▣  Duplicate")
        self.apply_all_button = FAMButton("▱  Apply to All", kind="primary")
        row2.addWidget(self.duplicate_button)
        row2.addWidget(self.apply_all_button)
        root.addLayout(row2)

        self.center_button.clicked.connect(self.center_requested.emit)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.duplicate_button.clicked.connect(self.duplicate_requested.emit)
        self.apply_all_button.clicked.connect(self.apply_all_requested.emit)

        self.size.editingFinished.connect(self._emit_geometry)
        self.x.editingFinished.connect(self._emit_geometry)
        self.y.editingFinished.connect(self._emit_geometry)
        self.bands.editingFinished.connect(lambda: self._emit_property("band_count", self.bands.value()))
        self.thickness.editingFinished.connect(lambda: self._emit_property("thickness", self.thickness.value()))
        self.opacity.editingFinished.connect(lambda: self._emit_opacity(self.opacity.value() / 100.0))
        self.smoothing.editingFinished.connect(lambda: self._emit_property("smoothing", self.smoothing.value()))
        self.reactive.editingFinished.connect(lambda: self._emit_property("reactive_scale", self.reactive.value()))
        self.color.editingFinished.connect(lambda: self._emit_property("accent_color", self.color.text().strip()))

        self.size_slider.sliderReleased.connect(self._size_slider_commit)
        self.bands_slider.sliderReleased.connect(self._bands_slider_commit)
        self.thickness_slider.sliderReleased.connect(self._thickness_slider_commit)
        self.opacity_slider.sliderReleased.connect(self._opacity_slider_commit)
        self.smoothing_slider.sliderReleased.connect(self._smoothing_slider_commit)
        self.reactive_slider.sliderReleased.connect(self._reactive_slider_commit)

        self.note = QLabel("Semua perubahan melewati command + Undo. Reactive Scale tidak mengubah volume audio master.")
        self.note.setObjectName("metadata")
        self.note.setWordWrap(True)
        self.note.hide()
        root.addWidget(self.note)
        root.addStretch(1)
        self.set_state(None)

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size:11px;color:#17355E;")
        return label

    @staticmethod
    def _slider(minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setMinimumWidth(78)
        return slider

    @staticmethod
    def _double(minimum: float, maximum: float, step: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setSingleStep(step)
        box.setDecimals(decimals)
        box.setKeyboardTracking(False)
        box.setFixedWidth(68)
        if suffix:
            box.setSuffix(suffix)
        return box

    def _control_row(self, root: QVBoxLayout, label_text: str, slider: QSlider, value_widget: QWidget) -> None:
        row = QHBoxLayout()
        label = self._caption(label_text)
        label.setMinimumWidth(92)
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value_widget)
        root.addLayout(row)

    def set_state(self, state: SpectrumInspectorState | None) -> None:
        self._updating = True
        controls = [self.size, self.x, self.y, self.bands, self.thickness, self.opacity, self.smoothing, self.reactive, self.color]
        sliders = [self.size_slider, self.bands_slider, self.thickness_slider, self.opacity_slider, self.smoothing_slider, self.reactive_slider]
        blockers = [QSignalBlocker(widget) for widget in (*controls, *sliders)]
        try:
            enabled = state is not None
            locked = bool(state.locked if state else False)
            self._layer_id = state.layer_id if state else ""
            for widget in (*controls, *sliders):
                widget.setEnabled(enabled and not locked)
            for button in self.type_segment._buttons.values():
                button.setEnabled(enabled and not locked)
            for button in (self.center_button, self.reset_button, self.duplicate_button, self.apply_all_button):
                button.setEnabled(enabled and not locked)
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
            self.size_slider.setValue(round(state.size_ratio * 100.0))
            self.bands_slider.setValue(state.band_count)
            self.thickness_slider.setValue(round(state.thickness))
            self.opacity_slider.setValue(round(state.opacity * 100.0))
            self.smoothing_slider.setValue(round(state.smoothing * 100.0))
            self.reactive_slider.setValue(round(state.reactive_scale * 100.0))
            self.color_swatch.setStyleSheet(f"background:{state.accent_color};border:1px solid #AED0F5;border-radius:4px;")
        finally:
            del blockers
            self._updating = False

    def _size_slider_commit(self) -> None:
        self.size.setValue(float(self.size_slider.value()))
        self._emit_geometry()

    def _bands_slider_commit(self) -> None:
        value = max(16, round(self.bands_slider.value() / 16) * 16)
        self.bands.setValue(value)
        self._emit_property("band_count", value)

    def _thickness_slider_commit(self) -> None:
        self.thickness.setValue(float(self.thickness_slider.value()))
        self._emit_property("thickness", self.thickness.value())

    def _opacity_slider_commit(self) -> None:
        self.opacity.setValue(float(self.opacity_slider.value()))
        self._emit_opacity(self.opacity.value() / 100.0)

    def _smoothing_slider_commit(self) -> None:
        self.smoothing.setValue(self.smoothing_slider.value() / 100.0)
        self._emit_property("smoothing", self.smoothing.value())

    def _reactive_slider_commit(self) -> None:
        self.reactive.setValue(self.reactive_slider.value() / 100.0)
        self._emit_property("reactive_scale", self.reactive.value())

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
        self.setMinimumHeight(155)
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
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        left = 118
        ruler_h = 25
        top = ruler_h + 3
        row_h = max(33, (self.height() - ruler_h - 8) // 3)
        width = max(1, self.width() - left - 10)
        duration = self._duration()
        resolved = TimelineResolver().resolve(self._document)
        layer_resolved = {item.layer_id: item for item in resolved.layers}
        song_resolved = {item.song_id: item for item in resolved.songs}

        painter.setPen(QColor("#55708F"))
        for index in range(9):
            x = left + width * index / 8
            seconds = (duration / max(1, self._document.timebase)) * index / 8
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            painter.drawText(QRectF(x - 18, 2, 60, 18), Qt.AlignmentFlag.AlignLeft, f"{minutes:02d}:{secs:02d}")
            painter.setPen(QPen(QColor("#E1EAF4"), 1))
            painter.drawLine(int(x), ruler_h, int(x), self.height())
            painter.setPen(QColor("#55708F"))

        spectrum_layers = [layer for layer in self._document.layers if layer.type == "spectrum" and layer.enabled]
        overlays = [layer for layer in self._document.layers if layer.type != "spectrum" and layer.enabled]
        songs = [song for song in self._document.playlist.entries if song.enabled]
        rows = (
            ("▥  Spectrum", spectrum_layers, "#D9ECFF", "#1787FF"),
            ("▣  Overlay", overlays, "#DDD5FF", "#775BE7"),
            ("♫  Audio", songs, "#D9F7E8", "#36C98A"),
        )

        for index, (label, items, fill, accent) in enumerate(rows):
            y = top + index * row_h
            painter.fillRect(QRectF(0, y, left, row_h), QColor("#FAFCFF"))
            painter.setPen(QColor("#17355E"))
            painter.drawText(QRectF(12, y, left - 18, row_h), Qt.AlignmentFlag.AlignVCenter, label)
            painter.setPen(QPen(QColor("#D9E4F1"), 1))
            painter.drawLine(0, y + row_h, self.width(), y + row_h)

            for item_index, item in enumerate(items):
                if index == 2:
                    timing = song_resolved.get(item.song_id)
                    spans = [(timing.start_tick, timing.end_tick)] if timing else []
                    clip_label = item.display_title or "Senja di Kota Ini - Full Album.mp3"
                else:
                    timing = layer_resolved.get(item.layer_id)
                    spans = [(span.start_tick, span.end_tick) for span in timing.intervals] if timing else []
                    clip_label = "Spectrum - Circular" if item.type == "spectrum" else (item.name or "Background.jpg")
                for start, end in spans:
                    x = left + width * start / duration
                    w = max(3.0, width * max(1, end - start) / duration)
                    clip = QRectF(x + 1, y + 5, max(2.0, w - 2), row_h - 10)
                    painter.setBrush(QColor(fill))
                    painter.setPen(QPen(QColor(accent), 1))
                    painter.drawRoundedRect(clip, 4, 4)
                    painter.setPen(QColor("#234A75"))
                    painter.drawText(clip.adjusted(8, 1, -4, -1), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, clip_label[:38])
                    painter.setPen(QPen(QColor(accent), 1))
                    baseline = clip.bottom() - 6
                    points = 70
                    for j in range(points):
                        xx = clip.left() + j * clip.width() / max(1, points - 1)
                        amp = 2 + abs(math.sin(j * 0.47 + item_index)) * max(2.0, clip.height() * 0.22)
                        painter.drawLine(QPointF(xx, baseline), QPointF(xx, baseline - amp))

        play_x = left + width * min(self._playhead, duration) / duration
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        painter.drawLine(int(play_x), 0, int(play_x), self.height() - 2)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        left = 118
        width = max(1, self.width() - left - 10)
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