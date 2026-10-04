from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .foundation_components import FAMButton, FAMStatusChip
from .foundation_tokens import TOKENS
from .home_state import CapabilityState, HomeViewState, QuickDefaults


_RATIO_OPTIONS = [
    ("16:9", "16:9 (YouTube)"),
    ("4:3", "4:3"),
    ("1:1", "1:1"),
    ("9:16", "9:16 (Vertikal)"),
]
_RESOLUTION_OPTIONS = [
    ("720p", "1280 × 720 (HD)", 1280, 720),
    ("1080p", "1920 × 1080 (Full HD)", 1920, 1080),
    ("1440p", "2560 × 1440 (2K)", 2560, 1440),
    ("2160p", "3840 × 2160 (4K)", 3840, 2160),
]


def _capability_style(state: CapabilityState) -> tuple[str, str]:
    if state == CapabilityState.READY:
        return "Siap", "success"
    if state == CapabilityState.CHECKING:
        return "Memeriksa…", "neutral"
    if state == CapabilityState.OPTIONAL:
        return "Opsional", "neutral"
    if state == CapabilityState.WARNING:
        return "Perlu perhatian", "warning"
    return "Tidak tersedia", "error"


class _StatusRow(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(TOKENS.space_2)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)
        self.title = QLabel(title)
        self.title.setObjectName("sectionHeading")
        self.title.setStyleSheet("font-size: 13px;")
        self.detail = QLabel("")
        self.detail.setObjectName("metadata")
        self.detail.setWordWrap(True)
        copy.addWidget(self.title)
        copy.addWidget(self.detail)
        row.addLayout(copy, 1)
        self.chip = FAMStatusChip("", "neutral")
        row.addWidget(self.chip)

    def set_value(self, state: CapabilityState, detail: str) -> None:
        text, style = _capability_style(state)
        self.chip.setText(text)
        self.chip.set_status(style)
        self.detail.setText(detail)


class HomeInspectorWidget(QWidget):
    defaults_changed = Signal(object)
    browse_output_requested = Signal()

    def __init__(self, state: HomeViewState, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_3, TOKENS.space_3, TOKENS.space_3, TOKENS.space_3)
        root.setSpacing(TOKENS.space_3)

        title = QLabel("Status Portable")
        title.setObjectName("sectionHeading")
        root.addWidget(title)

        self.ffmpeg = _StatusRow("FFmpeg")
        self.manual = _StatusRow("Editing Manual Offline")
        self.ai = _StatusRow("AI")
        root.addWidget(self.ffmpeg)
        root.addWidget(self.manual)
        root.addWidget(self.ai)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        quick = QLabel("Pengaturan Cepat")
        quick.setObjectName("sectionHeading")
        root.addWidget(quick)

        root.addWidget(QLabel("Rasio Video"))
        self.ratio = QComboBox()
        for value, label in _RATIO_OPTIONS:
            self.ratio.addItem(label, value)
        root.addWidget(self.ratio)

        root.addWidget(QLabel("Resolusi Default"))
        self.resolution = QComboBox()
        for value, label, width, height in _RESOLUTION_OPTIONS:
            self.resolution.addItem(label, (value, width, height))
        root.addWidget(self.resolution)

        root.addWidget(QLabel("Folder Output"))
        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(TOKENS.space_1)
        self.output = QLineEdit()
        self.output.setReadOnly(True)
        self.output.setAccessibleName("Folder Output")
        self.browse = FAMButton("…", kind="secondary")
        self.browse.setFixedWidth(40)
        self.browse.setToolTip("Pilih folder output")
        output_row.addWidget(self.output, 1)
        output_row.addWidget(self.browse)
        root.addLayout(output_row)

        self.output_warning = QLabel("")
        self.output_warning.setObjectName("metadata")
        self.output_warning.setWordWrap(True)
        root.addWidget(self.output_warning)
        root.addStretch(1)

        self.ratio.currentIndexChanged.connect(self._emit_defaults)
        self.resolution.currentIndexChanged.connect(self._emit_defaults)
        self.browse.clicked.connect(self.browse_output_requested.emit)
        self.apply_state(state)

    def _combo_index(self, combo: QComboBox, value: str, *, tuple_data: bool = False) -> int:
        for index in range(combo.count()):
            data = combo.itemData(index)
            candidate = data[0] if tuple_data and isinstance(data, tuple) else data
            if candidate == value:
                return index
        return 0

    def current_defaults(self) -> QuickDefaults:
        ratio_id = str(self.ratio.currentData())
        resolution_id, width, height = self.resolution.currentData()
        return QuickDefaults(
            ratio_id=ratio_id,
            resolution_id=str(resolution_id),
            width=int(width),
            height=int(height),
            output_folder=self.output.text(),
        )

    def set_output_folder(self, path: str) -> None:
        self.output.setText(path)
        self._emit_defaults()

    def set_output_warning(self, text: str) -> None:
        self.output_warning.setText(text)

    def _emit_defaults(self) -> None:
        if self._updating:
            return
        self.defaults_changed.emit(self.current_defaults())

    def apply_state(self, state: HomeViewState) -> None:
        self._updating = True
        try:
            caps = state.capabilities
            self.ffmpeg.set_value(caps.ffmpeg, caps.ffmpeg_detail)
            self.manual.set_value(caps.manual_offline, caps.manual_detail)
            self.ai.set_value(caps.ai_config, caps.ai_detail)
            defaults = state.quick_defaults
            self.ratio.setCurrentIndex(self._combo_index(self.ratio, defaults.ratio_id))
            self.resolution.setCurrentIndex(self._combo_index(self.resolution, defaults.resolution_id, tuple_data=True))
            self.output.setText(defaults.output_folder)
        finally:
            self._updating = False
