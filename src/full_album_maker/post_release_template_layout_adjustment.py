from __future__ import annotations

"""Route-local post-release geometry alignment.

Template uses a compact filter rail, while Timeline uses wider track/context and
property docks in the immutable reference. Other workspaces keep the shared
post-release shell widths. Presentation only; route data and command state stay
untouched.
"""

from .foundation_shell import FoundationShellWidget
from .foundation_tokens import TOKENS

_installed = False
# UI-06 boundary measurement places the context/gallery divider near x=391.
_TEMPLATE_CONTEXT_WIDTH = 215
# UI-06 right dock begins near x=1296 at the 1672x941 QA viewport.
_TEMPLATE_RIGHT_DOCK_WIDTH = 339
# UI-04 golden boundary measurement places the track/preview divider near x=505
# and the inspector boundary near x=1303. These route-local widths reproduce
# those boundaries while leaving the shared shell untouched elsewhere.
_TIMELINE_CONTEXT_WIDTH = 329
_TIMELINE_RIGHT_DOCK_WIDTH = 355


def install_post_release_template_layout_adjustment() -> None:
    global _installed
    if _installed:
        return

    previous_sizes = FoundationShellWidget._apply_shell_sizes

    def post_release_route_sizes(self: FoundationShellWidget, route: str) -> None:
        previous_sizes(self, route)
        if self._responsive_compact:
            return

        if route == "template":
            context = _TEMPLATE_CONTEXT_WIDTH
            right = 38 if self.inspector.collapsed else _TEMPLATE_RIGHT_DOCK_WIDTH
        elif route == "timeline":
            context = _TIMELINE_CONTEXT_WIDTH
            right = 38 if self.inspector.collapsed else _TIMELINE_RIGHT_DOCK_WIDTH
        else:
            return

        total = max(1, self.width())
        nav = TOKENS.nav_width
        center = max(560, total - nav - context - right - TOKENS.splitter_handle * 3)

        self.context.setMinimumWidth(context)
        self.context.setMaximumWidth(context)
        self.inspector.set_expanded_width(right)
        self.horizontal_splitter.setSizes([nav, context, center, right])

    FoundationShellWidget._apply_shell_sizes = post_release_route_sizes
    _installed = True
