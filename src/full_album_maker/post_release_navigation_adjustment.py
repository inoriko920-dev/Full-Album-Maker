from __future__ import annotations

"""Presentation-only shared workspace navigation alignment."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS, WORKSPACE_ORDER

_installed = False


def _stateful_navigation_icon(icon_name: str, *, size: int) -> QIcon:
    """Build a full-resolution nav icon with a blue checked-state glyph."""
    icon = QIcon()
    normal = foundation_icon(icon_name, color=TOKENS.text_primary, size=size).pixmap(size, size)
    active = foundation_icon(icon_name, color=TOKENS.primary_600, size=size).pixmap(size, size)
    disabled = foundation_icon(icon_name, color="#97A2B2", size=size).pixmap(size, size)
    icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(active, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.On)
    return icon


def _apply_navigation_geometry(nav, *, compact: bool) -> None:
    layout = nav.layout()
    layout.setSpacing(3 if not compact else 2)
    source_size = 30 if compact else 34
    display_size = 30 if compact else 34
    icon_name_by_route = {route: icon_name for route, _label, icon_name in WORKSPACE_ORDER}
    for route, button in nav.buttons.items():
        button.setMinimumHeight(47)
        button.setMaximumHeight(47)
        icon_name = icon_name_by_route.get(route)
        if icon_name:
            button.setIcon(_stateful_navigation_icon(icon_name, size=source_size))
        button.setIconSize(QSize(display_size, display_size))
        # Golden uses a noticeably stronger navigation label than the initial
        # foundation shell. Keep the existing route text/state untouched.
        button.setStyleSheet("font-size:16px;" if not compact else "font-size:13px;")


def install_post_release_navigation_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_shell import WorkspaceNavigation

    original_init = WorkspaceNavigation.__init__
    original_set_compact = WorkspaceNavigation.set_compact

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        _apply_navigation_geometry(self, compact=False)

    def adjusted_set_compact(self, compact: bool) -> None:
        original_set_compact(self, compact)
        _apply_navigation_geometry(self, compact=bool(compact))

    WorkspaceNavigation.__init__ = adjusted_init
    WorkspaceNavigation.set_compact = adjusted_set_compact
    _installed = True
