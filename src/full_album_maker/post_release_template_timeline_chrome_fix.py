from __future__ import annotations

"""Route-only chrome fix for the UI-06 Template timeline.

The production-backed Template surface installs its controls in the timeline
header. The foundation Packed/Free toolbar must therefore stop consuming a
second row while Template is active. This layer only changes widget visibility
and layout margins; project data, commands and history remain untouched.
"""

from PySide6.QtWidgets import QAbstractButton

from .foundation_tokens import TOKENS

_installed = False


def _apply_template_timeline_chrome(window, route: str) -> None:
    timeline = window.foundation_shell.timeline
    active = str(route) == "template"

    # The foundation mode is a composite widget. Enforce the hidden state on the
    # owner and its child buttons because other workspace refresh layers may show
    # the body again after the first initialization pass.
    timeline.mode.setVisible(not active)
    for button in timeline.mode.findChildren(QAbstractButton):
        button.setVisible(not active)
    for button in timeline.body.findChildren(QAbstractButton):
        if button.text().strip() in {"Split", "Ripple", "Snap", "Marker"}:
            button.setVisible(not active)

    body_layout = timeline.body.layout()
    if body_layout is not None:
        if active:
            body_layout.setContentsMargins(0, 0, 0, 2)
            body_layout.setSpacing(0)
        else:
            body_layout.setContentsMargins(
                TOKENS.space_2,
                0,
                TOKENS.space_2,
                TOKENS.space_2,
            )
            body_layout.setSpacing(2)


def install_post_release_template_timeline_chrome_fix() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_route = Window._s07_route
    previous_refresh = Window._s07_refresh_timeline

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        self.foundation_state.workspace_changed.connect(
            lambda route: _apply_template_timeline_chrome(self, str(route))
        )
        _apply_template_timeline_chrome(
            self,
            str(getattr(self.foundation_state, "workspace", "")),
        )

    def wrapped_route(self, route: str) -> None:
        previous_route(self, route)
        _apply_template_timeline_chrome(self, str(route))

    def wrapped_refresh(self) -> None:
        previous_refresh(self)
        _apply_template_timeline_chrome(
            self,
            str(getattr(self.foundation_state, "workspace", "")),
        )

    Window.__init__ = wrapped_init
    Window._s07_route = wrapped_route
    Window._s07_refresh_timeline = wrapped_refresh
    _installed = True
