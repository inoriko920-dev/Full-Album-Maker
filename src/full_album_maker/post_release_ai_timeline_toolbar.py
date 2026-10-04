from __future__ import annotations

"""Compact functional toolbar for the AI Agent preview timeline.

The controls are the existing STEP05 buttons/signals; this module only reparents
and relabels them into the outer timeline header while the AI route is active.
No timeline mutation semantics are duplicated or faked here.
"""

from PySide6.QtWidgets import QLabel

_installed = False


def _install_toolbar(window) -> None:
    panel = getattr(window, "ai_timeline_s09", None)
    timeline = window.foundation_shell.timeline
    if panel is None or getattr(timeline, "_post_release_ai_toolbar", False):
        return

    head = timeline.layout().itemAt(0).layout()
    if head is None:
        return

    # The outer header already owns Timeline, project message, stretch and zoom.
    # Reuse its message slot as the secondary UI-08 label.
    timeline._post_release_ai_original_message = timeline.message.text()
    timeline._post_release_ai_toolbar = True

    controls = (
        (panel.split, "✂", "Split clip"),
        (panel.delete_gap, "⌫", "Delete Gap"),
        (panel.ripple, "R", "Ripple"),
        (panel.snap, "S", "Snap"),
        (panel.marker, "●", "Tambah Marker"),
    )
    timeline._post_release_ai_controls = tuple(widget for widget, _text, _tip in controls)

    # Insert before the existing stretch (currently after Timeline + message).
    insert_at = 3
    for widget, text, tooltip in controls:
        old_layout = widget.parentWidget().layout() if widget.parentWidget() is not None else None
        if old_layout is not None:
            old_layout.removeWidget(widget)
        widget.setText(text)
        widget.setToolTip(tooltip)
        widget.setFixedWidth(32)
        widget.setMinimumHeight(28)
        head.insertWidget(insert_at, widget)
        insert_at += 1

    timeline.message.setText("Daftar Scene")
    timeline.message.setStyleSheet("font-weight:600;color:#536B88;")


def _set_active(window, active: bool) -> None:
    timeline = window.foundation_shell.timeline
    if not getattr(timeline, "_post_release_ai_toolbar", False):
        return
    for widget in timeline._post_release_ai_controls:
        widget.setVisible(bool(active))
    if active:
        timeline.message.setText("Daftar Scene")
        timeline.message.setStyleSheet("font-weight:600;color:#536B88;")
    else:
        timeline.message.setStyleSheet("")
        # Normal workspace refresh will update the project message as needed.
        original = getattr(timeline, "_post_release_ai_original_message", "")
        if original and timeline.message.text() == "Daftar Scene":
            timeline.message.setText(original)


def install_post_release_ai_timeline_toolbar() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_route = Window._s09_route

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_toolbar(self)
        _set_active(self, getattr(self.foundation_state, "workspace", "") == "ai_agent")

    def route_with_toolbar(self, route: str) -> None:
        previous_route(self, route)
        _install_toolbar(self)
        _set_active(self, str(route) == "ai_agent")

    Window.__init__ = wrapped_init
    Window._s09_route = route_with_toolbar
    _installed = True
