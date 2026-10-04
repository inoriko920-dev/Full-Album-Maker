from __future__ import annotations

"""Presentation-only alignment for the UI-09 Render context rail.

This layer changes margins, spacing, and preset decoration only. It does not
change RenderJob ordering/state, project data, persistence, or retry behavior.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel

from .foundation_components import FAMCard

_installed = False


def _decorate_render_context(window) -> None:
    context = window.render_history_s10
    if getattr(context, "_pixel_context_adjusted", False):
        return
    context._pixel_context_adjusted = True

    root = context.layout()
    left, top, right, bottom = root.getContentsMargins()
    # UI-09 starts the first heading slightly lower than the recovered rail.
    root.setContentsMargins(left, top + 7, right, bottom)

    preset_titles = {"YouTube 1080p", "YouTube 1440p", "YouTube 4K", "Custom"}
    cards: list[tuple[FAMCard, str]] = []
    for card in context.findChildren(FAMCard):
        labels = card.findChildren(QLabel)
        title = next((label.text() for label in labels if label.text() in preset_titles), "")
        if title:
            cards.append((card, title))

    # Preserve construction order from the presentation class.
    for card, title in cards:
        card.setMinimumHeight(64)
        card.setMaximumHeight(64)
        layout = card.layout()
        if layout is not None:
            _l, t, r, b = layout.getContentsMargins()
            layout.setContentsMargins(54, t, r, b)

        icon = QLabel(card)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if title == "Custom":
            icon.setText("⚙")
            icon.setGeometry(12, 17, 30, 30)
            icon.setStyleSheet(
                "background:#F7FAFE;border:1px solid #C9D9EE;border-radius:7px;"
                "color:#1766E8;font-size:18px;font-weight:700;"
            )
        else:
            icon.setText("▶")
            icon.setGeometry(12, 20, 32, 24)
            icon.setStyleSheet(
                "background:#FF1234;border:none;border-radius:7px;"
                "color:white;font-size:12px;font-weight:700;padding-left:1px;"
            )
        icon.show()
        icon.raise_()

    # The immutable reference separates preset choices from previous projects
    # with a clearly visible divider and breathing room.
    previous = next(
        (label for label in context.findChildren(QLabel) if label.text() == "Proyek Sebelumnya"),
        None,
    )
    if previous is not None:
        index = root.indexOf(previous)
        if index >= 0:
            divider_box = QFrame(context)
            divider_box.setObjectName("pixelRenderContextDivider")
            divider_box.setFixedHeight(31)
            divider_box.setStyleSheet(
                "QFrame#pixelRenderContextDivider{border:none;border-bottom:1px solid #D8E4F2;}"
            )
            root.insertWidget(index, divider_box)


def install_post_release_render_context_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_context_alignment(self, route: str) -> None:
        original_route(self, route)
        outer = self.foundation_shell.context.layout()
        if not hasattr(self, "_pixel_context_host_margins"):
            self._pixel_context_host_margins = outer.getContentsMargins()
        left, top, right, bottom = self._pixel_context_host_margins
        if route == "render":
            # Remove only the duplicated horizontal host padding. Vertical host
            # spacing remains intact so other shared-shell geometry is stable.
            outer.setContentsMargins(0, top, 0, bottom)
            _decorate_render_context(self)
        else:
            outer.setContentsMargins(left, top, right, bottom)

    Window._s10_route = route_with_context_alignment
    _installed = True
