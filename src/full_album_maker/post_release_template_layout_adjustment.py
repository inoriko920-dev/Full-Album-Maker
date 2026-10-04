from __future__ import annotations

"""Route-local UI-06 geometry alignment.

Template uses a compact filter rail and no empty inspector dock title strip in
the approved reference. Other workspaces keep the shared post-release shell
geometry. This patch changes presentation only; Template data, filters,
preview/apply commands, inspector state and project state remain untouched.
"""

from .foundation_shell import FoundationShellWidget
from .foundation_tokens import TOKENS

_installed = False
_TEMPLATE_CONTEXT_WIDTH = 205
_RIGHT_DOCK_WIDTH = 328


def install_post_release_template_layout_adjustment() -> None:
    global _installed
    if _installed:
        return

    previous_sizes = FoundationShellWidget._apply_shell_sizes

    def template_route_sizes(self: FoundationShellWidget, route: str) -> None:
        previous_sizes(self, route)

        # UI-06 starts the Properti / AI tab surface directly under the global
        # command bar. The shared STEP01 dock header has no title on this route
        # and only creates an empty strip, so hide that presentation chrome for
        # Template and restore it everywhere else. Collapse state/content remain
        # authoritative in InspectorDockHost.
        self.inspector.header.setVisible(route != "template")

        if route != "template" or self._responsive_compact:
            return

        total = max(1, self.width())
        nav = TOKENS.nav_width
        context = _TEMPLATE_CONTEXT_WIDTH
        right = 38 if self.inspector.collapsed else _RIGHT_DOCK_WIDTH
        center = max(560, total - nav - context - right - TOKENS.splitter_handle * 3)

        self.context.setMinimumWidth(context)
        self.context.setMaximumWidth(context)
        self.inspector.set_expanded_width(right)
        self.horizontal_splitter.setSizes([nav, context, center, right])

    FoundationShellWidget._apply_shell_sizes = template_route_sizes
    _installed = True
