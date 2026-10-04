from __future__ import annotations

"""Presentation-only geometry tuning for the UI-09 preflight surface."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

_installed = False


def _decorate_preflight(window) -> None:
    workspace = window.render_workspace_s10
    if getattr(workspace, "_pixel_preflight_adjusted", False):
        return
    workspace._pixel_preflight_adjusted = True

    heading = next(
        (label for label in workspace.findChildren(QLabel) if label.text() == "Hasil Preflight"),
        None,
    )
    if heading is not None:
        host = heading.parentWidget()
        if host is not None:
            host.setMinimumHeight(55)
            host.setMaximumHeight(55)
            layout = host.layout()
            if layout is not None:
                layout.setContentsMargins(4, 0, 4, 0)
                layout.setSpacing(0)

    icons = {
        "media": "▤",
        "snapshot": "☷",
        "ffmpeg": "▦",
        "output": "▱",
        "disk": "▰",
    }
    for key in ("media", "snapshot", "ffmpeg", "output", "disk"):
        card = workspace.preflight_cards[key]
        card.setMinimumHeight(166)
        card.setMaximumHeight(166)
        layout = card.layout()
        if layout is not None:
            layout.setContentsMargins(12, 12, 10, 10)
            layout.setSpacing(6)
        card.title.setContentsMargins(34, 0, 0, 0)
        card.state.setStyleSheet(card.state.styleSheet() + "font-size:15px;font-weight:700;")

        icon = QLabel(icons[key], card)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setGeometry(11, 14, 28, 28)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if key == "disk":
            icon.setStyleSheet("color:#475569;font-size:19px;font-weight:700;")
        else:
            icon.setStyleSheet("color:#1766E8;font-size:19px;font-weight:700;")
        icon.show()
        icon.raise_()


def install_post_release_render_preflight_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_preflight_alignment(self, route: str) -> None:
        original_route(self, route)
        if route == "render":
            _decorate_preflight(self)

    Window._s10_route = route_with_preflight_alignment
    _installed = True
