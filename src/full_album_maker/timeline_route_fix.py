from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QPushButton

_installed = False
_original_panel_init: Any = None
_original_route: Any = None


def install_step05_timeline_route_fix() -> None:
    """Keep STEP01 placeholder controls and STEP05 controls from hiding each other."""

    global _installed, _original_panel_init, _original_route
    if _installed:
        return

    from .timeline_workspace_step05 import TimelinePrecisionPanel
    from .foundation_window import FoundationMainWindow as Window

    _original_panel_init = TimelinePrecisionPanel.__init__

    def panel_init(self, *args, **kwargs) -> None:
        _original_panel_init(self, *args, **kwargs)
        # timeline_feature_step05 hides only the exact legacy placeholder labels.
        self.ripple.setText("↔ Ripple")
        self.snap.setText("⌁ Snap")

    TimelinePrecisionPanel.__init__ = panel_init

    _original_route = Window._s05_route

    def route(self, route: str) -> None:
        if route != "timeline":
            mode = getattr(self.foundation_shell.timeline, "mode", None)
            if mode is not None:
                mode.setVisible(True)
            parent = self.foundation_shell.timeline.canvas.parentWidget()
            for button in parent.findChildren(QPushButton):
                if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
                    button.setVisible(True)
        _original_route(self, route)

    Window._s05_route = route
    _installed = True
