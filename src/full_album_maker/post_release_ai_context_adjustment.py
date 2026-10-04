from __future__ import annotations

"""Presentation-only alignment for the UI-08 AI Agent context rail.

The foundation placeholder is useful before a workspace is implemented, but it
must not remain above the real conversation panel. This patch changes visibility
only; AI session, provider, permissions, history, project state, and execution
contracts remain untouched.
"""

_installed = False


def install_post_release_ai_context_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s09_route

    def route_without_foundation_placeholder(self, route: str) -> None:
        original_route(self, route)
        if route != "ai_agent":
            return
        layout = self.foundation_shell.context.layout()
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None and widget is not self.ai_conversations_s09:
                widget.setVisible(False)
        self.ai_conversations_s09.setVisible(True)

    Window._s09_route = route_without_foundation_placeholder
    _installed = True
