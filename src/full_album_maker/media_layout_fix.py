from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSizePolicy

from .media_workspace import MediaWorkspace

_installed = False
_original_init: Any = None
_original_resize: Any = None


def install_step03_media_layout_fix() -> None:
    """Keep STEP03 grid breakpoints tied to the shell allocation, not a stale viewport.

    On the shared shell, Qt's offscreen backend can briefly report the scroll viewport
    at the previous splitter width even after the Media workspace already owns its
    final center width. That made a 994 px workspace render only three columns.
    The workspace allocation is the stable contract; the scroll area remains a
    resizable child and horizontal scrolling is intentionally disabled.
    """

    global _installed, _original_init, _original_resize
    if _installed:
        return

    _original_init = MediaWorkspace.__init__
    _original_resize = MediaWorkspace.resizeEvent

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

    MediaWorkspace.__init__ = layout_init
    MediaWorkspace._columns = workspace_columns
    MediaWorkspace.resizeEvent = layout_resize
    _installed = True
