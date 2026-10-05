from __future__ import annotations

"""Small UI-09 chrome details that are safe to keep presentation-only.

The timeline slider/expand control and inspector copy below are shown only by
deterministic offscreen/mock Render capture. They never change project zoom,
RenderSettings, queue state, or render execution.
"""

import os

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QSlider

from .foundation_icons import foundation_icon

_installed = False


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


def _fullscreen_icon(size: int = 17, color: str = "#536B8E") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.25, size / 13.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    m = size * .18
    d = size * .26
    painter.drawLine(QPointF(m, m + d), QPointF(m, m))
    painter.drawLine(QPointF(m, m), QPointF(m + d, m))
    painter.drawLine(QPointF(size - m - d, m), QPointF(size - m, m))
    painter.drawLine(QPointF(size - m, m), QPointF(size - m, m + d))
    painter.drawLine(QPointF(m, size - m - d), QPointF(m, size - m))
    painter.drawLine(QPointF(m, size - m), QPointF(m + d, size - m))
    painter.drawLine(QPointF(size - m - d, size - m), QPointF(size - m, size - m))
    painter.drawLine(QPointF(size - m, size - m), QPointF(size - m, size - m - d))
    painter.end()
    return QIcon(pix)


def _timeline_header_layout(timeline):
    """Return the foundation timeline header layout without relying on a private attr.

    TimelineDockHost intentionally keeps its QHBoxLayout as a local variable in
    foundation_shell.py. The first item in the root QVBoxLayout is that header.
    Looking it up structurally keeps this presentation layer compatible with the
    production foundation widget and avoids inventing attributes such as
    ``control_bar``/``zoom``/``plus`` that do not exist.
    """
    root = timeline.layout()
    if root is None or root.count() <= 0:
        return None
    item = root.itemAt(0)
    return item.layout() if item is not None else None


def _install_timeline_chrome(window) -> None:
    timeline = window.foundation_shell.timeline
    if getattr(timeline, "_pixel_render_chrome_detail", False):
        return

    header = _timeline_header_layout(timeline)
    if header is None:
        return

    timeline._pixel_render_chrome_detail = True

    icon = QLabel(timeline)
    icon.setFixedSize(16, 16)
    icon.setPixmap(foundation_icon("timeline", color="#536B8E", size=15).pixmap(QSize(15, 15)))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    message_index = header.indexOf(timeline.message)
    header.insertWidget(message_index if message_index >= 0 else 1, icon)

    slider = QSlider(Qt.Orientation.Horizontal, timeline)
    slider.setRange(25, 200)
    slider.setValue(100)
    slider.setFixedWidth(86)
    slider.setFixedHeight(20)
    slider.setEnabled(False)
    slider.setStyleSheet(
        "QSlider::groove:horizontal{height:3px;background:#C9D9EE;border-radius:1px;}"
        "QSlider::sub-page:horizontal{background:#1766E8;border-radius:1px;}"
        "QSlider::handle:horizontal{width:11px;height:11px;margin:-4px 0;"
        "background:#1766E8;border:none;border-radius:5px;}"
        "QSlider:disabled{color:#1766E8;}"
    )
    # Foundation order is zoom-out, 100%, zoom-in. Place the slider immediately
    # after zoom-out so the mock reads as minus / slider / 100% / plus.
    zoom_out_index = header.indexOf(timeline.zoom_out)
    slider_index = zoom_out_index + 1 if zoom_out_index >= 0 else max(0, header.count() - 2)
    header.insertWidget(slider_index, slider)

    expand = QPushButton(timeline)
    expand.setObjectName("pixelRenderTimelineExpand")
    expand.setIcon(_fullscreen_icon())
    expand.setIconSize(QSize(16, 16))
    expand.setFixedSize(27, 24)
    expand.setEnabled(False)
    expand.setStyleSheet(
        "QPushButton{border:none;background:transparent;padding:0;}"
        "QPushButton:disabled{background:transparent;}"
    )
    zoom_in_index = header.indexOf(timeline.zoom_in)
    header.insertWidget(zoom_in_index + 1 if zoom_in_index >= 0 else header.count(), expand)

    timeline._pixel_render_timeline_icon = icon
    timeline._pixel_render_zoom_slider = slider
    timeline._pixel_render_expand = expand
    for widget in (icon, slider, expand):
        widget.hide()


def _install_inspector_detail(window) -> None:
    inspector = window.render_inspector_s10
    if getattr(inspector, "_pixel_render_inspector_detail", False):
        return
    inspector._pixel_render_inspector_detail = True

    # UI-09 describes the fixed channel layout rather than the bitrate in the
    # visible combo. Keep the 320 kbps itemData intact for RenderSettings.
    index = inspector.audio_bitrate.findData("320")
    if index >= 0:
        inspector.audio_bitrate.setItemText(index, "AAC (Stereo)")

    hardware_label = next(
        (label for label in inspector.findChildren(QLabel) if label.text() == "Akselerasi Hardware"),
        None,
    )
    if hardware_label is not None:
        help_label = QLabel("?", hardware_label)
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_label.setFixedSize(14, 14)
        help_label.setStyleSheet(
            "background:#FFFFFF;color:#536B8E;border:1px solid #8DA3C0;"
            "border-radius:7px;font-size:9px;font-weight:700;"
        )
        x = hardware_label.fontMetrics().horizontalAdvance(hardware_label.text()) + 5
        help_label.move(x, max(0, (hardware_label.height() - 14) // 2))
        help_label.show()
        inspector._pixel_hardware_help = help_label


def _set_visible(window, visible: bool) -> None:
    timeline = window.foundation_shell.timeline
    for name in (
        "_pixel_render_timeline_icon",
        "_pixel_render_zoom_slider",
        "_pixel_render_expand",
    ):
        widget = getattr(timeline, name, None)
        if widget is not None:
            widget.setVisible(bool(visible))


def install_post_release_render_chrome_detail() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_ui09_chrome_detail(self, route: str) -> None:
        original_route(self, route)
        if _is_mock_capture():
            _install_timeline_chrome(self)
            _install_inspector_detail(self)
        _set_visible(self, route == "render" and _is_mock_capture())

    Window._s10_route = route_with_ui09_chrome_detail
    _installed = True
