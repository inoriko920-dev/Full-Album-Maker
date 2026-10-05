from __future__ import annotations

"""Post-release shell adjustment for canonical inspector geometry.

The shared STEP01 inspector shell keeps a tall empty collapsible dock header
above the Properti/AI tabs. UI-06 Template has no such strip, while UI-09 Render
retains only a shallow breathing area. Apply those presentation rules per route
and restore the normal dock everywhere else. No project, render, template,
provider, queue, or persistence state is changed here.

The canonical 9-reference pack also uses the same full-width segmented
Properti/AI control on every workspace. Keep the production tab buttons and
stack semantics, but align their presentation globally here instead of creating
route-specific copies.
"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy

from .foundation_icons import foundation_icon

_installed = False


def _stateful_foundation_icon(name: str, *, size: int = 18) -> QIcon:
    icon = QIcon()
    off = foundation_icon(name, color="#536B8E", size=size).pixmap(size, size)
    on = foundation_icon(name, color="#1766E8", size=size).pixmap(size, size)
    icon.addPixmap(off, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(off, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(on, QIcon.Mode.Disabled, QIcon.State.On)
    return icon


def _sparkle_pixmap(color: str, size: int = 18) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color), max(1.3, size / 12.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    c = size * 0.48
    long_r = size * 0.31
    short_r = size * 0.12
    painter.drawLine(QPointF(c, c - long_r), QPointF(c, c - short_r))
    painter.drawLine(QPointF(c, c + short_r), QPointF(c, c + long_r))
    painter.drawLine(QPointF(c - long_r, c), QPointF(c - short_r, c))
    painter.drawLine(QPointF(c + short_r, c), QPointF(c + long_r, c))
    painter.drawLine(QPointF(c - long_r * .68, c - long_r * .68), QPointF(c - short_r * .62, c - short_r * .62))
    painter.drawLine(QPointF(c + short_r * .62, c + short_r * .62), QPointF(c + long_r * .68, c + long_r * .68))
    painter.drawLine(QPointF(c + long_r * .68, c - long_r * .68), QPointF(c + short_r * .62, c - short_r * .62))
    painter.drawLine(QPointF(c - short_r * .62, c + short_r * .62), QPointF(c - long_r * .68, c + long_r * .68))
    # Small secondary sparkle in the canonical AI glyph.
    sx, sy = size * .79, size * .22
    r = size * .09
    painter.drawLine(QPointF(sx, sy - r), QPointF(sx, sy + r))
    painter.drawLine(QPointF(sx - r, sy), QPointF(sx + r, sy))
    painter.end()
    return pix


def _stateful_sparkle_icon(*, size: int = 18) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_sparkle_pixmap("#536B8E", size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_sparkle_pixmap("#1766E8", size), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def _align_shared_inspector_tabs(content) -> None:
    if getattr(content, "_post_release_segmented_tabs", False):
        return
    root = content.layout()
    if root is None or root.count() < 1:
        return
    tabs = root.itemAt(0).layout()
    if tabs is None:
        return

    # Remove the legacy trailing stretch. The golden control is one full-width
    # two-segment bar, not two short text tabs followed by empty space.
    while tabs.count() > 2:
        tabs.takeAt(2)
    tabs.setContentsMargins(10, 7, 10, 5)
    tabs.setSpacing(0)
    tabs.setStretch(0, 1)
    tabs.setStretch(1, 1)

    properties = content.properties
    ai = content.ai
    properties.setIcon(_stateful_foundation_icon("settings"))
    ai.setIcon(_stateful_sparkle_icon())
    properties.setIconSize(properties.iconSize().expandedTo(properties.icon().actualSize(properties.iconSize())))
    ai.setIconSize(ai.iconSize().expandedTo(ai.icon().actualSize(ai.iconSize())))
    for button in (properties, ai):
        button.setMinimumWidth(0)
        button.setMinimumHeight(42)
        button.setMaximumHeight(42)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    properties.setStyleSheet(
        "QPushButton{background:#F7FAFE;color:#536B8E;font-weight:600;"
        "border:1px solid #D8E4F2;border-right:0;"
        "border-top-left-radius:7px;border-bottom-left-radius:7px;"
        "border-top-right-radius:0;border-bottom-right-radius:0;padding:0 12px;}"
        "QPushButton:hover{background:#F0F6FE;color:#1766E8;}"
        "QPushButton:checked{background:#FFFFFF;color:#1766E8;font-weight:700;"
        "border-bottom:2px solid #1766E8;}"
    )
    ai.setStyleSheet(
        "QPushButton{background:#F7FAFE;color:#536B8E;font-weight:600;"
        "border:1px solid #D8E4F2;"
        "border-top-left-radius:0;border-bottom-left-radius:0;"
        "border-top-right-radius:7px;border-bottom-right-radius:7px;padding:0 12px;}"
        "QPushButton:hover{background:#F0F6FE;color:#1766E8;}"
        "QPushButton:checked{background:#FFFFFF;color:#1766E8;font-weight:700;"
        "border-bottom:2px solid #1766E8;}"
    )
    content._post_release_segmented_tabs = True


def install_post_release_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_canonical_inspector_header(self, route: str) -> None:
        original_route(self, route)
        inspector = self.foundation_shell.inspector
        _align_shared_inspector_tabs(inspector.content)
        header = inspector.header
        if route == "template":
            header.hide()
            return
        if route == "render":
            header.show()
            header.title.hide()
            header.collapse_button.hide()
            header.setMinimumHeight(28)
            header.setMaximumHeight(28)
            return

        header.setMinimumHeight(0)
        header.setMaximumHeight(16777215)
        header.collapse_button.show()
        header.show()

    Window._s10_route = route_with_canonical_inspector_header
    _installed = True
