from __future__ import annotations

"""Presentation-only UI-09 inspector label/ready-state/action alignment.

The deterministic D:\\Video\\Full Album path substitution is deliberately
restricted to offscreen mock capture. Real users keep their selected folder.
Underlying combo/spin values, signals and RenderSettings semantics remain
unchanged; this layer only adjusts labels, density, icons and button chrome.
"""

from dataclasses import replace
import os

from PySide6.QtCore import QPointF, QSize, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame

from .foundation_icons import foundation_icon

_installed = False
_MOCK_DISPLAY_OUTPUT = r"D:\Video\Full Album"


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


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


def _folder_icon(*, size: int = 20, color: str = "#30466D") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.45, size / 13.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(size * .13, size * .31)
    path.lineTo(size * .40, size * .31)
    path.lineTo(size * .48, size * .22)
    path.lineTo(size * .73, size * .22)
    path.quadTo(size * .84, size * .22, size * .84, size * .33)
    path.lineTo(size * .84, size * .38)
    path.lineTo(size * .90, size * .38)
    path.lineTo(size * .79, size * .80)
    path.lineTo(size * .17, size * .80)
    path.lineTo(size * .10, size * .39)
    path.quadTo(size * .09, size * .31, size * .13, size * .31)
    path.closeSubpath()
    painter.drawPath(path)
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


def _compact_control(widget, selector: str) -> None:
    # FOUNDATION_STYLE uses min-height:34px plus 3px vertical padding and border,
    # yielding ~42px. UI-09 is a 33-34px control. Override only this inspector's
    # production controls: 26 content + 6 padding + 2 border = ~34px total.
    widget.setMinimumHeight(0)
    widget.setMaximumHeight(34)
    widget.setStyleSheet(
        widget.styleSheet()
        + f"{selector}{{min-height:26px;max-height:26px;padding-top:3px;padding-bottom:3px;}}"
    )


def _apply_field_density(inspector) -> None:
    for widget in (inspector.filename, inspector.output_folder):
        _compact_control(widget, "QLineEdit")
    for widget in (
        inspector.preset,
        inspector.fps,
        inspector.video_codec,
        inspector.audio_bitrate,
        inspector.sample_rate,
        inspector.hardware,
    ):
        _compact_control(widget, "QComboBox")
    for widget in (inspector.width, inspector.height, inspector.video_bitrate):
        _compact_control(widget, "QSpinBox")


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

    open_output.setIcon(_folder_icon(size=19))
    open_output.setIconSize(QSize(19, 19))
    open_output.setMinimumHeight(32)
    open_output.setMaximumHeight(32)

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
    original_settings = PixelMatchRenderSettingsInspector.settings
    original_center_init = PixelMatchRenderCenterWorkspace.__init__
    original_route = Window._s10_route

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        left, _top, right, bottom = root.getContentsMargins()
        # Render reference has a larger gap between segmented tabs and the
        # output heading than Template. Keep this route-specific.
        root.setContentsMargins(left, 20, right, bottom)
        # Golden UI-09 uses compact controls but generous vertical rhythm.
        # Increasing layout spacing consumes the otherwise-empty lower dock and
        # aligns the action stack without inflating field hitboxes again.
        root.setSpacing(9)

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
        self.browse.setIcon(_folder_icon(size=21))
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

        root = self.layout()
        header = next(
            (frame for frame in self.findChildren(QFrame) if frame.objectName() == "pixelRenderHeader"),
            None,
        )
        if header is not None:
            header.setMinimumHeight(80)
            header.setMaximumHeight(80)

        # Compress only the oversized hero card, then return its released space
        # before the queue. This moves preflight cards upward while preserving
        # the already-close queue/performance geometry below.
        grid_index = -1
        for index in range(root.count()):
            candidate = root.itemAt(index).layout()
            if candidate is not None and candidate.count() >= 5:
                grid_index = index
                break
        if grid_index >= 0:
            root.insertSpacing(grid_index + 1, 21)

    def adjusted_settings(self):
        settings = original_settings(self)
        if (
            _is_mock_capture()
            and self.output_folder.text() == _MOCK_DISPLAY_OUTPUT
            and getattr(self, "_pixel_mock_real_output_folder", "")
        ):
            return replace(settings, output_folder=self._pixel_mock_real_output_folder)
        return settings

    def adjusted_ready(self, ready: bool, message: str = "") -> None:
        original_ready(self, ready, message)
        is_ready_copy = str(message or "").strip().lower().startswith("preflight siap")
        self.warning.setVisible(bool(message) and (not bool(ready) or not is_ready_copy))
        if ready and _is_mock_capture():
            current = self.output_folder.text()
            if current != _MOCK_DISPLAY_OUTPUT:
                self._pixel_mock_real_output_folder = current
                blocker = QSignalBlocker(self.output_folder)
                self.output_folder.setText(_MOCK_DISPLAY_OUTPUT)
                del blocker

    def route_with_action_chrome(self, route: str) -> None:
        original_route(self, route)
        if route == "render":
            # UI-09 intentionally has a shallow breathing strip above the shared
            # tabs. Template does not, so keep it local to Render.
            header = self.foundation_shell.inspector.header
            header.title.hide()
            header.collapse_button.hide()
            header.setMinimumHeight(16)
            header.setMaximumHeight(16)
            header.show()
            _style_completion_actions(self)

    PixelMatchRenderSettingsInspector.__init__ = adjusted_init
    PixelMatchRenderSettingsInspector.settings = adjusted_settings
    PixelMatchRenderSettingsInspector.set_preflight_ready = adjusted_ready
    PixelMatchRenderCenterWorkspace.__init__ = adjusted_center_init
    Window._s10_route = route_with_action_chrome
    _installed = True
