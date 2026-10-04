from __future__ import annotations

"""Presentation-only alignment for the UI-08 central AI canvas header.

The approved reference starts directly with the conversation surface; the
workspace name already exists in the left rail. Hide the duplicate central
heading/state chip while leaving AgentState and all session behavior intact.
"""

from PySide6.QtWidgets import QLabel

_installed = False


def install_post_release_ai_canvas_header_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AITaskCanvas

    original_init = AITaskCanvas.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        self.state_chip.hide()
        for label in self.findChildren(QLabel):
            if label.parent() is self and label.text().strip() == "AI Agent":
                label.hide()
        root = self.layout()
        if root is not None:
            root.setContentsMargins(11, 7, 11, 9)
            root.setSpacing(7)

    AITaskCanvas.__init__ = adjusted_init
    _installed = True
