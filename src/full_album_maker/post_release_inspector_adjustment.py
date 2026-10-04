from __future__ import annotations

"""Tiny post-release shell adjustment for canonical Render inspector geometry.

The STEP01 inspector shell keeps a tall empty collapsible dock header above the
Properti/AI tabs. UI-09 retains only a shallow top breathing area. Compress that
header only while Render is active and restore its normal behavior immediately
for every other route. No project, render, queue, provider, or persistence state
is changed here.
"""

_installed = False


def install_post_release_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_canonical_render_header(self, route: str) -> None:
        original_route(self, route)
        header = self.foundation_shell.inspector.header
        if route == "render":
            header.show()
            header.title.hide()
            header.collapse_button.hide()
            header.setMinimumHeight(28)
            header.setMaximumHeight(28)
        else:
            header.setMinimumHeight(0)
            header.setMaximumHeight(16777215)
            header.collapse_button.show()
            header.show()

    Window._s10_route = route_with_canonical_render_header
    _installed = True
