from __future__ import annotations

"""Presentation-only shared workspace navigation alignment."""

from PySide6.QtCore import QSize

_installed = False


def _apply_navigation_geometry(nav, *, compact: bool) -> None:
    layout = nav.layout()
    layout.setSpacing(3 if not compact else 2)
    for button in nav.buttons.values():
        button.setMinimumHeight(47)
        button.setMaximumHeight(47)
        button.setIconSize(QSize(24 if not compact else 22, 24 if not compact else 22))
        button.setStyleSheet("font-size:15px;" if not compact else "font-size:13px;")


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
