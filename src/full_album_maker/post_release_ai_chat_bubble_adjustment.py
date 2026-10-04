from __future__ import annotations

"""Presentation-only chat-bubble refinement for UI-08.

The prompt/interpretation strings remain the same live AgentSession data. This
layer removes duplicate section captions inside the two conversation cards but
preserves their footprint so downstream plan/action geometry stays stable.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

_installed = False


def _hide_caption(card, text: str) -> None:
    for label in card.findChildren(QLabel):
        if label.text().strip() == text:
            label.hide()


def install_post_release_ai_chat_bubble_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AITaskCanvas

    original_init = AITaskCanvas.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)

        _hide_caption(self.user_card, "Perintah Anda")
        _hide_caption(self.ai_card, "Interpretasi AI")

        user_layout = self.user_card.layout()
        if user_layout is not None:
            user_layout.setContentsMargins(14, 9, 14, 9)
            user_layout.setSpacing(0)
        ai_layout = self.ai_card.layout()
        if ai_layout is not None:
            ai_layout.setContentsMargins(14, 9, 14, 9)
            ai_layout.setSpacing(0)

        self.user_card.setMinimumHeight(58)
        self.ai_card.setMinimumHeight(62)
        self.user_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.ai_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

    AITaskCanvas.__init__ = adjusted_init
    _installed = True
