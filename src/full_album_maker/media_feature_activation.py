from __future__ import annotations

from typing import Any

_installed = False
_original_init: Any = None


def install_step03_media_activation_guard() -> None:
    """Re-activate the current workspace after STEP 03 replaces its placeholder.

    Foundation preferences are restored during FoundationMainWindow.__init__.
    If `media` was already the persisted route, replacing the Media widget later
    does not emit another workspace_changed signal because the route ID has not
    changed. This small post-wrapper makes direct FoundationMainWindow creation
    deterministic without changing STEP 01 route semantics.
    """

    global _installed, _original_init
    if _installed:
        return

    from .foundation_window import FoundationMainWindow

    _original_init = FoundationMainWindow.__init__

    def guarded_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        shell = getattr(self, "foundation_shell", None)
        state = getattr(self, "foundation_state", None)
        if shell is not None and state is not None:
            shell.workspace_stack.set_route(state.workspace)
            # Keep all route-owned panels synchronized even when the route did
            # not change and therefore FoundationUiState emitted no signal.
            route_sync = getattr(self, "_s03_route", None)
            if callable(route_sync):
                route_sync(state.workspace)

    FoundationMainWindow.__init__ = guarded_init
    _installed = True
