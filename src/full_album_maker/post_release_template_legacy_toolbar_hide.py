from __future__ import annotations

"""Hide the STEP01/STEP05 legacy toolbar only while UI-06 Template is active.

The post-release Template footer supplies its own UI-06 toolbar in the timeline
header. The foundation Packed/Free/Split/Ripple/Snap/Marker row must therefore
not consume a second row. This layer is deliberately presentation-only.
"""

from PySide6.QtWidgets import QAbstractButton

_installed = False


def _legacy_controls(window):
    timeline = window.foundation_shell.timeline
    controls = []

    mode = getattr(timeline, "mode", None)
    if mode is not None:
        controls.append(mode)

    # Foundation toolbar buttons are direct children of timeline.body. Nested
    # STEP05/other workspace controls have their own panel parent and are not
    # touched here.
    for button in timeline.body.findChildren(QAbstractButton):
        if button.parentWidget() is timeline.body and button.text().strip() in {
            "Split",
            "Ripple",
            "Snap",
            "Marker",
        }:
            controls.append(button)
    return tuple(controls)


def _apply(window, route: str) -> None:
    active = str(route) == "template"
    controls = _legacy_controls(window)
    if active:
        if not hasattr(window, "_post_template_legacy_visibility"):
            window._post_template_legacy_visibility = {
                id(widget): widget.isVisible() for widget in controls
            }
        for widget in controls:
            widget.hide()
        return

    # Restore only the visibility state that existed before entering Template;
    # do not force unrelated workspace controls visible.
    saved = getattr(window, "_post_template_legacy_visibility", None)
    if saved is None:
        return
    for widget in controls:
        widget.setVisible(bool(saved.get(id(widget), False)))
    delattr(window, "_post_template_legacy_visibility")


def install_post_release_template_legacy_toolbar_hide() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_refresh = Window._s07_refresh_timeline

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        self.foundation_state.workspace_changed.connect(lambda route: _apply(self, str(route)))
        _apply(self, getattr(self.foundation_state, "workspace", ""))

    def refresh_without_legacy_toolbar(self) -> None:
        previous_refresh(self)
        if getattr(self.foundation_state, "workspace", "") == "template":
            _apply(self, "template")

    Window.__init__ = wrapped_init
    Window._s07_refresh_timeline = refresh_without_legacy_toolbar
    _installed = True
