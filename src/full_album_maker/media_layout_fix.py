from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSizePolicy

from .media_workspace import MediaWorkspace

_installed = False
_original_init: Any = None
_original_resize: Any = None
_original_window_init: Any = None
_original_window_sync: Any = None


def install_step03_media_layout_fix() -> None:
    """Stabilize STEP03 Media geometry and early bootstrap ordering.

    Qt's offscreen backend can briefly report the scroll viewport at an older
    splitter width even after Media already owns the final center allocation.
    Grid breakpoints therefore follow the Media workspace allocation, while the
    scroll area stays a resizable child with horizontal scrolling disabled.

    The shared Foundation window also performs an initial state sync while its
    constructor is still running. When the persisted route is ``media``, that
    sync can happen before STEP03 has created ``media_workspace`` and ``_s03_index``.
    Guard only that incomplete Media-specific sync and queue one final sync after
    the complete STEP03 window constructor returns.
    """

    global _installed, _original_init, _original_resize, _original_window_init, _original_window_sync
    if _installed:
        return

    from .foundation_window import FoundationMainWindow

    _original_init = MediaWorkspace.__init__
    _original_resize = MediaWorkspace.resizeEvent
    _original_window_init = FoundationMainWindow.__init__
    _original_window_sync = FoundationMainWindow._sync_foundation_state

    def layout_init(self: MediaWorkspace, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.card_host.setMinimumWidth(0)
        self.card_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._step03_layout_columns = self._columns()

    def workspace_columns(self: MediaWorkspace) -> int:
        usable_width = max(360, self.width() - 24)
        return max(2, min(5, usable_width // 180))

    def layout_resize(self: MediaWorkspace, event) -> None:
        _original_resize(self, event)
        current = self._columns()
        previous = getattr(self, "_step03_layout_columns", None)
        self._step03_layout_columns = current
        if previous != current and self.query.view_mode.value == "grid":
            QTimer.singleShot(0, self.refresh_view)

    def safe_window_sync(self: FoundationMainWindow) -> None:
        state = getattr(self, "foundation_state", None)
        if (
            getattr(state, "workspace", "") == "media"
            and (not hasattr(self, "media_workspace") or not hasattr(self, "_s03_index"))
        ):
            return
        _original_window_sync(self)

    def stable_window_init(self: FoundationMainWindow, *args, **kwargs) -> None:
        _original_window_init(self, *args, **kwargs)
        QTimer.singleShot(0, self._sync_foundation_state)

    MediaWorkspace.__init__ = layout_init
    MediaWorkspace._columns = workspace_columns
    MediaWorkspace.resizeEvent = layout_resize
    FoundationMainWindow._sync_foundation_state = safe_window_sync
    FoundationMainWindow.__init__ = stable_window_init
    _installed = True
