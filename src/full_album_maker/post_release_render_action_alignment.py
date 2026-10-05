from __future__ import annotations

"""Final UI-09 alignment for Render heading chrome and action stack.

This layer only changes layout/chrome of existing production widgets. Signals,
enabled states, RenderSettings, queue state and render execution stay owned by
the STEP10 implementation.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel

from .foundation_icons import foundation_icon

_installed = False


def _compact_button(button, *, content_height: int) -> None:
    if getattr(button, "_pixel_compact_action", False):
        return
    button._pixel_compact_action = True
    # Global button QSS contributes vertical padding/border on top of min-height.
    # Override only the box model while leaving kind/hover/disabled colors intact.
    button.setMinimumHeight(0)
    button.setMaximumHeight(content_height + 8)
    button.setStyleSheet(
        button.styleSheet()
        + f"QPushButton{{min-height:{content_height}px;max-height:{content_height}px;"
          "padding-top:3px;padding-bottom:3px;}"
    )


def _align_action_stack(window) -> None:
    inspector = window.render_inspector_s10
    _compact_button(inspector.start, content_height=28)       # ~36 px total
    _compact_button(window.render_add_queue_s10, content_height=26)   # ~34 px
    _compact_button(window.render_copy_log_s10, content_height=24)    # ~32 px
    _compact_button(window.render_open_output_s10, content_height=24)

    actions = window.render_add_queue_s10.parentWidget()
    if actions is None:
        return
    layout = actions.layout()
    if layout is not None:
        layout.setContentsMargins(0, 0, 0, 0)
        # post_release_pixel_match nests one vertical stack in this host.
        for index in range(layout.count()):
            child = layout.itemAt(index).layout()
            if child is not None:
                child.setSpacing(3)


def _install_preset_heading_row(window) -> None:
    context = window.render_history_s10
    if getattr(context, "_pixel_preset_heading_row_done", False):
        return
    heading = next(
        (label for label in context.findChildren(QLabel) if label.text() == "Preset Render"),
        None,
    )
    if heading is None:
        return
    root = context.layout()
    index = root.indexOf(heading)
    if index < 0:
        return

    floating = getattr(context, "_pixel_preset_heading_icon", None)
    if floating is not None:
        floating.hide()

    root.removeWidget(heading)
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    row.addWidget(heading)
    row.addStretch(1)
    icon = QLabel()
    icon.setFixedSize(24, 24)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setPixmap(foundation_icon("settings", color="#30466D", size=20).pixmap(QSize(20, 20)))
    icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    row.addWidget(icon)
    root.insertLayout(index, row)

    context._pixel_preset_heading_row_icon = icon
    context._pixel_preset_heading_row_done = True


def install_post_release_render_action_alignment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_final_render_alignment(self, route: str) -> None:
        original_route(self, route)
        if route != "render":
            return
        _install_preset_heading_row(self)
        _align_action_stack(self)

    Window._s10_route = route_with_final_render_alignment
    _installed = True
