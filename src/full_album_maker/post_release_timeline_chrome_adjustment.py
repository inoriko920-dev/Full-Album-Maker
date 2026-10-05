from __future__ import annotations

"""UI-04 Timeline chrome alignment.

STEP05 owns the functional precision toolbar. The shared STEP01 timeline host also
contains a legacy header row and a placeholder Packed/Free toolbar; displaying all
three rows at once makes UI-04 substantially taller than the immutable reference.
This post-release layer only changes route-local visibility/layout chrome. Timeline
commands, selection, document state, undo history, and precision controls remain
owned by STEP05.
"""

from PySide6.QtCore import QMargins
from PySide6.QtWidgets import QAbstractButton

_installed = False


def _layout_widgets(layout) -> tuple:
    if layout is None:
        return ()
    widgets = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            widgets.append(widget)
    return tuple(widgets)


def _step01_placeholder_widgets(timeline) -> tuple:
    """Return only the legacy STEP01 controls owned directly by timeline.body."""
    widgets = []
    mode = getattr(timeline, "mode", None)
    if mode is not None:
        widgets.append(mode)

    body = getattr(timeline, "body", None)
    if body is not None:
        for button in body.findChildren(QAbstractButton):
            if button.parentWidget() is body and button.text().strip() in {
                "Split",
                "Ripple",
                "Snap",
                "Marker",
            }:
                widgets.append(button)
    return tuple(dict.fromkeys(widgets))


def _prepare(timeline) -> None:
    if getattr(timeline, "_post_timeline_chrome_prepared", False):
        return

    outer = timeline.layout()
    head = outer.itemAt(0).layout() if outer is not None and outer.count() else None

    timeline._post_timeline_head_layout = head
    timeline._post_timeline_head_widgets = _layout_widgets(head)
    timeline._post_timeline_head_visibility = {
        widget: not widget.isHidden() for widget in timeline._post_timeline_head_widgets
    }
    timeline._post_timeline_message_visibility = not timeline.message.isHidden()
    if head is not None:
        margins = head.contentsMargins()
        timeline._post_timeline_head_margins = QMargins(
            margins.left(), margins.top(), margins.right(), margins.bottom()
        )
        timeline._post_timeline_head_spacing = head.spacing()

    timeline._post_timeline_step01_widgets = _step01_placeholder_widgets(timeline)
    timeline._post_timeline_chrome_prepared = True


def _apply(window, route: str) -> None:
    timeline = window.foundation_shell.timeline
    _prepare(timeline)
    active = str(route) == "timeline"

    head = getattr(timeline, "_post_timeline_head_layout", None)
    if active:
        # The project-context message is the last remaining shared header owner in
        # UI-04. Hide it explicitly so the STEP05 precision toolbar begins at the
        # timeline boundary, matching the golden structure.
        timeline.message.hide()
        for widget in getattr(timeline, "_post_timeline_head_widgets", ()):
            widget.hide()
        if head is not None:
            head.setContentsMargins(0, 0, 0, 0)
            head.setSpacing(0)

        # Hide the exact STEP01 owners. STEP05 precision buttons are children of
        # timeline_precision_s05, so they remain visible and functional.
        for widget in _step01_placeholder_widgets(timeline):
            widget.hide()
    else:
        for widget in getattr(timeline, "_post_timeline_head_widgets", ()):
            widget.setVisible(
                bool(getattr(timeline, "_post_timeline_head_visibility", {}).get(widget, True))
            )
        if timeline.message not in getattr(timeline, "_post_timeline_head_widgets", ()):
            timeline.message.setVisible(
                bool(getattr(timeline, "_post_timeline_message_visibility", True))
            )
        if head is not None:
            margins = getattr(timeline, "_post_timeline_head_margins", QMargins(8, 1, 8, 1))
            head.setContentsMargins(
                margins.left(), margins.top(), margins.right(), margins.bottom()
            )
            head.setSpacing(int(getattr(timeline, "_post_timeline_head_spacing", 4)))
        # Placeholder visibility is intentionally not forced here. Album, Template,
        # AI and the shared shell each own their non-Timeline presentation state.


def install_post_release_timeline_chrome_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        # Installed last: this connection runs after STEP04/05 and the Template
        # chrome listener, so UI-04 gets final ownership of its own route chrome.
        self.foundation_state.workspace_changed.connect(
            lambda route: _apply(self, str(route))
        )
        _apply(self, str(getattr(self.foundation_state, "workspace", "")))

    Window.__init__ = wrapped_init
    _installed = True
