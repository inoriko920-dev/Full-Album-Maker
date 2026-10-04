from __future__ import annotations

"""Tiny post-release shell adjustment for canonical Render inspector geometry.

The STEP01 inspector shell keeps an empty collapsible dock header above the
Properti/AI tabs. UI-09 has no equivalent blank strip. Hide it only while the
Render workspace is active and restore it immediately for every other route.
No project, render, queue, provider, or persistence state is changed here.
"""

_installed = False


def install_post_release_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_without_empty_render_header(self, route: str) -> None:
        original_route(self, route)
        header = self.foundation_shell.inspector.header
        header.setVisible(route != "render")

    Window._s10_route = route_without_empty_render_header
    _installed = True
