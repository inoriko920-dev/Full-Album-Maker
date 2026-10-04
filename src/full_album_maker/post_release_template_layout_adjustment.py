from __future__ import annotations

"""Route-local UI-06 geometry alignment.

Template uses a compact filter rail in the approved reference. Other workspaces
keep the shared post-release shell widths. This patch changes presentation only;
Template data, filters, preview/apply commands, inspector state and project state
remain untouched.
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

        # UI-06 starts the expanded inspector directly at Properti / AI. Keep the
        # shared collapse header everywhere else, and also keep it when Template
        # is collapsed so the user can still expand the dock.
        hide_template_header = (
            route == "template"
            and not self._responsive_compact
            and not self.inspector.collapsed
        )
        self.inspector.header.setVisible(not hide_template_header)

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
