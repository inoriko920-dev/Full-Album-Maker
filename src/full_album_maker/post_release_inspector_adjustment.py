from __future__ import annotations

"""Post-release shell adjustment for canonical inspector geometry.

The shared STEP01 inspector shell keeps a tall empty collapsible dock header
above the Properti/AI tabs. UI-06 Template has no such strip, while UI-09 Render
retains only a shallow breathing area. Apply those presentation rules per route
and restore the normal dock everywhere else. No project, render, template,
provider, queue, or persistence state is changed here.
"""

_installed = False


def install_post_release_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    original_route = Window._s10_route

    def route_with_canonical_inspector_header(self, route: str) -> None:
        original_route(self, route)
        header = self.foundation_shell.inspector.header
        if route == "template":
            header.hide()
            return
        if route == "render":
            header.show()
            header.title.hide()
            header.collapse_button.hide()
            header.setMinimumHeight(28)
            header.setMaximumHeight(28)
            return

        header.setMinimumHeight(0)
        header.setMaximumHeight(16777215)
        header.collapse_button.show()
        header.show()

    Window._s10_route = route_with_canonical_inspector_header
    _installed = True
