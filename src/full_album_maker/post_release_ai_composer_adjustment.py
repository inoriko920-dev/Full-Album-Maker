from __future__ import annotations

"""Presentation-only UI-08 refinement for the AI prompt composer.

Prompt text, send/save/lampiran signals and context-chip values remain unchanged.
Only the visual order and density of the existing controls are adjusted.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_installed = False


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def install_post_release_ai_composer_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AITaskCanvas

    original_init = AITaskCanvas.__init__
    original_set_chips = AITaskCanvas.set_context_chips

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        composer = self.prompt.parentWidget()
        layout = composer.layout()
        if layout is None or layout.count() < 2:
            return

        chip_item = layout.takeAt(0)
        input_item = layout.takeAt(0)
        chip_layout = chip_item.layout()
        input_layout = input_item.layout()
        if input_layout is not None:
            layout.addLayout(input_layout)
        if chip_layout is not None:
            layout.addLayout(chip_layout)

        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)
        self.prompt.setMaximumHeight(52)
        self.prompt.setMinimumHeight(44)

        # Keep Lampiran behavior; match the compact icon-only control in UI-08.
        self.attach_button.setText("📎")
        self.attach_button.setFixedWidth(38)
        self.attach_button.setMinimumHeight(30)
        self.save_button.setText("Simpan")
        self.save_button.setMaximumHeight(24)

        # Replace the one long context sentence with the same values rendered as
        # compact chips. The original QLabel remains hidden but still receives
        # updates from the production method.
        self.chip_label.hide()
        host = QWidget(composer)
        host_layout = QHBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(5)
        self._post_release_context_chip_host = host
        self._post_release_context_chip_layout = host_layout
        if chip_layout is not None:
            chip_layout.insertWidget(0, host, 1)

    def set_context_chips(self, labels) -> None:
        original_set_chips(self, labels)
        layout = getattr(self, "_post_release_context_chip_layout", None)
        if layout is None:
            return
        _clear_layout(layout)
        values = tuple(getattr(self, "_context_chips", ()))
        for value in values[:5]:
            chip = QLabel(str(value))
            chip.setObjectName("statusChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setContentsMargins(7, 2, 7, 2)
            layout.addWidget(chip)
        layout.addStretch(1)

    AITaskCanvas.__init__ = adjusted_init
    AITaskCanvas.set_context_chips = set_context_chips
    _installed = True
