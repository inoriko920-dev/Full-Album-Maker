from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
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
    """Compact status row matching the Beranda reference while keeping the old chip API."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.base_title = title
        self.setMinimumHeight(82)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(TOKENS.space_2)

        self.indicator = QLabel("•")
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator.setFixedSize(26, 26)
        row.addWidget(self.indicator, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("sectionHeading")
        self.title.setStyleSheet("font-size: 13px;font-weight:700;")
        self.detail = QLabel("")
        self.detail.setObjectName("metadata")
        self.detail.setWordWrap(True)
        copy.addWidget(self.title)
        copy.addWidget(self.detail)
        row.addLayout(copy, 1)

        # Preserve this attribute for compatibility with older tests/integration,
        # but the golden Beranda uses a circular state indicator instead of a pill.
        self.chip = FAMStatusChip("", "neutral")
        self.chip.hide()

    def _display_title(self, state: CapabilityState) -> str:
        if self.base_title == "FFmpeg":
            if state == CapabilityState.READY:
                return "FFmpeg Siap"
            if state == CapabilityState.CHECKING:
                return "FFmpeg Memeriksa…"
            return "FFmpeg Perlu Perhatian"
        if self.base_title == "Editing Manual Offline":
            return "Editing Manual Offline"
        if self.base_title == "AI":
            if state == CapabilityState.READY:
                return "AI Siap"
            if state == CapabilityState.OPTIONAL:
                return "AI Belum Dikonfigurasi"
            if state == CapabilityState.CHECKING:
                return "AI Memeriksa…"
            return "AI Perlu Perhatian"
        return self.base_title

    def _indicator_style(self, state: CapabilityState) -> tuple[str, str]:
        if state == CapabilityState.READY:
            return "✓", "background:#1FAF5A;color:white;"
        if state == CapabilityState.WARNING:
            return "!", "background:#FFF2CC;color:#A56D00;"
        if state == CapabilityState.UNAVAILABLE:
            return "×", "background:#FFF0F0;color:#B73A3A;"
        if state == CapabilityState.CHECKING:
            return "•", "background:#EAF3FF;color:#1766E8;"
        return "•", "background:#DCE5F1;color:#62728A;"

    def set_value(self, state: CapabilityState, detail: str) -> None:
        text, style = _capability_style(state)
        self.chip.setText(text)
        self.chip.set_status(style)
        self.title.setText(self._display_title(state))
        glyph, colors = self._indicator_style(state)
        self.indicator.setText(glyph)
        self.indicator.setStyleSheet(
            colors + "border-radius:13px;font-size:15px;font-weight:800;"
        )
        self.detail.setText(detail)


class HomeInspectorWidget(QWidget):
    defaults_changed = Signal(object)
    browse_output_requested = Signal()

    def __init__(self, state: HomeViewState, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_3, 22, TOKENS.space_3, TOKENS.space_3)
        root.setSpacing(22)

        self.status_card = QFrame()
        self.status_card.setObjectName("famCard")
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(TOKENS.space_3, TOKENS.space_3, TOKENS.space_3, TOKENS.space_3)
        status_layout.setSpacing(TOKENS.space_1)

        title = QLabel("Status Portable")
        title.setObjectName("sectionHeading")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        status_layout.addWidget(title)

        self.ffmpeg = _StatusRow("FFmpeg")
        self.manual = _StatusRow("Editing Manual Offline")
        self.ai = _StatusRow("AI")
        status_layout.addWidget(self.ffmpeg)
        status_layout.addWidget(self.manual)
        status_layout.addWidget(self.ai)
        root.addWidget(self.status_card)

        self.settings_card = QFrame()
        self.settings_card.setObjectName("famCard")
        settings = QVBoxLayout(self.settings_card)
        settings.setContentsMargins(TOKENS.space_3, TOKENS.space_3, TOKENS.space_3, TOKENS.space_3)
        settings.setSpacing(7)

        quick = QLabel("Pengaturan Cepat")
        quick.setObjectName("sectionHeading")
        quick.setStyleSheet("font-size:16px;font-weight:700;")
        settings.addWidget(quick)

        ratio_label = QLabel("Rasio Video")
        ratio_label.setObjectName("metadata")
        settings.addWidget(ratio_label)
        self.ratio = QComboBox()
        for value, label in _RATIO_OPTIONS:
            self.ratio.addItem(label, value)
        settings.addWidget(self.ratio)

        resolution_label = QLabel("Resolusi Default")
        resolution_label.setObjectName("metadata")
        settings.addWidget(resolution_label)
        self.resolution = QComboBox()
        for value, label, width, height in _RESOLUTION_OPTIONS:
            self.resolution.addItem(label, (value, width, height))
        settings.addWidget(self.resolution)

        output_label = QLabel("Folder Output")
        output_label.setObjectName("metadata")
        settings.addWidget(output_label)
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
        settings.addLayout(output_row)

        self.output_warning = QLabel("")
        self.output_warning.setObjectName("metadata")
        self.output_warning.setWordWrap(True)
        settings.addWidget(self.output_warning)
        root.addWidget(self.settings_card)
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
