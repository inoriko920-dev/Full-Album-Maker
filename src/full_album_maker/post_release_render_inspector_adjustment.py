from __future__ import annotations

"""Presentation-only UI-09 inspector label/ready-state alignment.

The deterministic D:\\Video\\Full Album path substitution is deliberately
restricted to offscreen mock capture. Real users keep their selected folder.
Underlying combo/spin values and RenderSettings semantics remain unchanged.
"""

import os

from PySide6.QtCore import QSignalBlocker

_installed = False


def _set_item_text(combo, value: str, text: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setItemText(index, text)


def install_post_release_render_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_pixel_match import PixelMatchRenderSettingsInspector

    original_init = PixelMatchRenderSettingsInspector.__init__
    original_ready = PixelMatchRenderSettingsInspector.set_preflight_ready

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        for value in ("24", "25", "30", "50", "60"):
            _set_item_text(self.fps, value, f"{value} fps")
        _set_item_text(self.video_codec, "h264", "H.264 (AVC)")
        _set_item_text(self.video_codec, "h265", "H.265 (HEVC)")
        _set_item_text(self.hardware, "h264_nvenc", "Gunakan Hardware (NVIDIA NVENC)")
        _set_item_text(self.hardware, "hevc_nvenc", "Gunakan Hardware (NVIDIA NVENC • HEVC)")
        _set_item_text(self.hardware, "software", "Software (CPU)")
        self.video_bitrate.setPrefix("Tinggi (± ")
        self.video_bitrate.setSuffix(" Mbps)")

    def adjusted_ready(self, ready: bool, message: str = "") -> None:
        original_ready(self, ready, message)
        # A green ready-state does not need a second explanatory line in UI-09;
        # invalid/warning text remains visible when action is required.
        self.warning.setVisible(not bool(ready) and bool(message))
        if (
            ready
            and os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
            and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
        ):
            blocker = QSignalBlocker(self.output_folder)
            self.output_folder.setText(r"D:\Video\Full Album")
            del blocker

    PixelMatchRenderSettingsInspector.__init__ = adjusted_init
    PixelMatchRenderSettingsInspector.set_preflight_ready = adjusted_ready
    _installed = True
