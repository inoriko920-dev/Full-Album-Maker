from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

_installed = False
_original_init: Any = None


def install_step03_media_activation_guard() -> None:
    """Re-activate the current workspace after STEP 03 replaces its placeholder.

    STEP 02 Home schedules a zero-delay activation after it is inserted into the
    shared stack. On startup with a persisted non-Home route, that older timer can
    otherwise run after STEP 03 replaces Media and leave the visible widget out of
    sync with FoundationUiState. Re-applying the persisted route on the next event
    turn preserves the STEP 01 route contract without redesigning the shell.
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
        if shell is None or state is None:
            return

        def reactivate_current_route() -> None:
            route = state.workspace
            # Reuse the shared STEP 01 application path so navigation, context,
            # timeline geometry and stack index stay coherent.
            shell._apply_workspace(route)
            route_sync = getattr(self, "_s03_route", None)
            if callable(route_sync):
                route_sync(route)

        # STEP 02 Home queued its activation before this guard is installed on
        # the instance, so our queued callback runs after it and restores the
        # actual persisted route deterministically.
        QTimer.singleShot(0, reactivate_current_route)

    FoundationMainWindow.__init__ = guarded_init
    _installed = True
