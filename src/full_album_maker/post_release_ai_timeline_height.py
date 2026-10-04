from __future__ import annotations

"""UI-08 geometry refinement for the AI Agent timeline.

The approved reference uses a more compact timeline than the shared STEP05
workspace. This patch changes only the dock height while the AI Agent route is
active; timeline data, controls, preview commands and project state are untouched.
"""

_installed = False
AI_TIMELINE_HEIGHT = 164


def install_post_release_ai_timeline_height() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_route = Window._s09_route

    def route_with_compact_height(self, route: str) -> None:
        previous_route(self, route)
        if str(route) != "ai_agent":
            return
        timeline = self.foundation_shell.timeline
        timeline._preferred_height = AI_TIMELINE_HEIGHT
        timeline._apply_height(AI_TIMELINE_HEIGHT)
        self.foundation_shell._apply_shell_sizes("ai_agent")

    Window._s09_route = route_with_compact_height
    _installed = True
