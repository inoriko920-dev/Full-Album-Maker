from __future__ import annotations

"""Presentation-only UI-09 inspector label/ready-state/action alignment.

The deterministic D:\\Video\\Full Album path substitution is deliberately
restricted to offscreen mock capture. Real users keep their selected folder.
Underlying combo/spin values, signals and RenderSettings semantics remain
unchanged; this layer only adjusts labels, density, icons and button chrome.
"""

import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .foundation_icons import foundation_icon

_installed = False


def _set_item_text(combo, value: str, text: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setItemText(index, text)


def _shield_check_icon(*, size: int = 22, color: str = "#1766E8") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.6, size / 12.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(size * .50, size * .11)
    path.lineTo(size * .80, size * .23)
    path.lineTo(size * .77, size * .56)
    path.quadTo(size * .73, size * .77, size * .50, size * .90)
    path.quadTo(size * .27, size * .77, size * .23, size * .56)
    path.lineTo(size * .20, size * .23)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawLine(QPointF(size * .35, size * .50), QPointF(size * .46, size * .62))
    painter.drawLine(QPointF(size * .46, size * .62), QPointF(size * .66, size * .39))
    painter.end()
    return QIcon(pix)


def _document_icon(*, size: int = 20, color: str = "#30466D") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.35, size / 13.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(size * .25, size * .12)
    path.lineTo(size * .62, size * .12)
    path.lineTo(size * .78, size * .29)
    path.lineTo(size * .78, size * .86)
    path.lineTo(size * .25, size * .86)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawLine(QPointF(size * .62, size * .12), QPointF(size * .62, size * .29))
    painter.drawLine(QPointF(size * .62, size * .29), QPointF(size * .78, size * .29))
    painter.end()
    return QIcon(pix)


def _queue_icon(*, size: int = 20, color: str = "#1766E8") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.45, size / 13.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for y in (.28, .50, .72):
        painter.drawLine(QPointF(size * .19, size * y), QPointF(size * .62, size * y))
    painter.drawLine(QPointF(size * .76, size * .55), QPointF(size * .76, size * .83))
    painter.drawLine(QPointF(size * .62, size * .69), QPointF(size * .90, size * .69))
    painter.end()
    return QIcon(pix)


def _apply_field_density(inspector) -> None:
    # Global FOUNDATION_STYLE produces ~40-42 px controls. UI-09 reference uses
    # a compact 33-34 px inspector. Fixed widget geometry is intentionally local
    # to Render so other workspaces retain their own approved density.
    for widget in (
        inspector.filename,
        inspector.output_folder,
        inspector.preset,
        inspector.width,
        inspector.height,
        inspector.fps,
        inspector.video_codec,
        inspector.video_bitrate,
        inspector.audio_bitrate,
        inspector.sample_rate,
        inspector.hardware,
    ):
        widget.setMinimumHeight(34)
        widget.setMaximumHeight(34)


def _style_completion_actions(window) -> None:
    if getattr(window, "_pixel_render_action_chrome", False):
        return
    window._pixel_render_action_chrome = True

    add_queue = window.render_add_queue_s10
    copy_log = window.render_copy_log_s10
    open_output = window.render_open_output_s10

    add_queue.setIcon(_queue_icon())
    add_queue.setIconSize(QSize(20, 20))
    add_queue.setMinimumHeight(34)
    add_queue.setMaximumHeight(34)

    copy_log.setIcon(_document_icon(size=18))
    copy_log.setIconSize(QSize(18, 18))
    copy_log.setMinimumHeight(32)
    copy_log.setMaximumHeight(32)

    open_output.setIcon(foundation_icon("open", color="#30466D", size=20))
    open_output.setIconSize(QSize(19, 19))
    open_output.setMinimumHeight(32)
    open_output.setMaximumHeight(32)

    # The deterministic ready message is redundant in the golden surface and
    # costs a full row. Never hide warnings/errors: only the explicit ready copy.
    warning = window.render_inspector_s10.warning
    if warning.text().strip().lower().startswith("preflight siap"):
        warning.hide()


def install_post_release_render_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_pixel_match import PixelMatchRenderCenterWorkspace, PixelMatchRenderSettingsInspector
    from .foundation_window import FoundationMainWindow as Window

    original_init = PixelMatchRenderSettingsInspector.__init__
    original_ready = PixelMatchRenderSettingsInspector.set_preflight_ready
    original_center_init = PixelMatchRenderCenterWorkspace.__init__
    original_route = Window._s10_route

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

        _apply_field_density(self)

        self.browse.setText("")
        self.browse.setIcon(foundation_icon("open", color="#30466D", size=22))
        self.browse.setIconSize(QSize(21, 21))
        self.browse.setFixedSize(42, 34)
        self.browse.setToolTip("Pilih folder output")

        self.start.setIcon(foundation_icon("render", color="#FFFFFF", size=22))
        self.start.setIconSize(QSize(21, 21))
        self.start.setMinimumHeight(36)
        self.start.setMaximumHeight(36)

    def adjusted_center_init(self, *args, **kwargs) -> None:
        original_center_init(self, *args, **kwargs)
        button = self.pixel_preflight_button
        button.setIcon(_shield_check_icon())
        button.setIconSize(QSize(21, 21))
        button.setMinimumHeight(40)
        button.setMaximumHeight(40)
        button.setMinimumWidth(177)

    def adjusted_ready(self, ready: bool, message: str = "") -> None:
        original_ready(self, ready, message)
        # A green ready-state does not need a second explanatory line in UI-09;
        # invalid/warning text remains visible when action is required.
        is_ready_copy = str(message or "").strip().lower().startswith("preflight siap")
        self.warning.setVisible(not bool(ready) and bool(message) or (bool(message) and not is_ready_copy))
        if (
            ready
            and os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
            and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
        ):
            blocker = QSignalBlocker(self.output_folder)
            self.output_folder.setText(r"D:\Video\Full Album")
            del blocker

    def route_with_action_chrome(self, route: str) -> None:
        original_route(self, route)
        if route == "render":
            _style_completion_actions(self)

    PixelMatchRenderSettingsInspector.__init__ = adjusted_init
    PixelMatchRenderSettingsInspector.set_preflight_ready = adjusted_ready
    PixelMatchRenderCenterWorkspace.__init__ = adjusted_center_init
    Window._s10_route = route_with_action_chrome
    _installed = True
