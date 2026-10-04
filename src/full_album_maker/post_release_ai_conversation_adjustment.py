from __future__ import annotations

"""Presentation-only UI-08 conversation-rail refinement.

The persisted AI history is unchanged. The conversation list now presents user
instructions rather than internal system/assistant audit rows. Saved commands keep
their existing prompt payload and double-click behavior.
"""

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

_installed = False


def _time_text(timestamp: str) -> str:
    try:
        value = datetime.fromisoformat(str(timestamp))
        return value.strftime("%H:%M")
    except Exception:
        return ""


def _display_prompt(text: str, *, limit: int = 54) -> str:
    value = " ".join(str(text or "").split())
    if len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value


def install_post_release_ai_conversation_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AIConversationPanel
    from .foundation_window import FoundationMainWindow as Window

    original_apply = AIConversationPanel.apply_data

    def apply_user_facing_history(self, history, saved) -> None:
        # Keep history stores authoritative; only select which rows become
        # conversation-navigation items.
        rows = tuple(history)
        commands = tuple(saved)
        self.today.clear()
        self.yesterday.clear()
        self.saved.clear()

        now = datetime.now(timezone.utc).date()
        user_rows = [entry for entry in rows if getattr(entry, "role", "") == "user"]
        for entry in reversed(user_rows):
            try:
                day = datetime.fromisoformat(str(entry.timestamp)).date()
            except Exception:
                day = now
            title = _display_prompt(entry.text)
            time = _time_text(entry.timestamp)
            subtitle = "Instruksi AI" if not entry.status else str(entry.status).replace("_", " ").title()
            item = QListWidgetItem(f"{title}\n{subtitle}{'   ' + time if time else ''}")
            item.setToolTip(str(entry.text))
            target = self.today if day == now else self.yesterday
            if target.count() < (3 if target is self.today else 2):
                target.addItem(item)

        for command in reversed(commands):
            item = QListWidgetItem(f"✦  {command.name}\n{_display_prompt(command.prompt, limit=46)}")
            item.setToolTip(command.prompt)
            item.setData(Qt.ItemDataRole.UserRole, command.prompt)
            self.saved.addItem(item)

        # Empty groups stay visually quiet rather than exposing implementation
        # placeholders as though they were user conversations.
        self.today_label.setVisible(self.today.count() > 0)
        self.today.setVisible(self.today.count() > 0)
        self.yesterday_label.setVisible(self.yesterday.count() > 0)
        self.yesterday.setVisible(self.yesterday.count() > 0)
        self.saved.setVisible(self.saved.count() > 0)

    AIConversationPanel.apply_data = apply_user_facing_history

    original_route = Window._s09_route

    def route_with_conversation_fidelity(self, route: str) -> None:
        original_route(self, route)
        if route != "ai_agent":
            return
        panel = self.ai_conversations_s09
        if getattr(panel, "_post_release_conversation_styled", False):
            return
        panel._post_release_conversation_styled = True
        root = panel.layout()
        root.setContentsMargins(12, 10, 10, 10)
        root.setSpacing(8)

        # Foundation implementation places +Baru beside the heading. UI-08 uses
        # a full-width conversation action below the AI Agent heading.
        header = root.itemAt(0).layout() if root.count() else None
        if header is not None:
            header.removeWidget(panel.new_button)
        for label in panel.findChildren(type(panel.today_label)):
            if label.text() == "Percakapan":
                label.setText("AI Agent")
                label.setStyleSheet("font-size:17px;font-weight:700;color:#10234A;")
                break
        panel.new_button.setText("＋  Percakapan Baru")
        panel.new_button.setMinimumHeight(36)
        root.insertWidget(1, panel.new_button)

        list_style = (
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{border:none;border-bottom:1px solid #E7EEF7;"
            "padding:7px 5px;color:#17345F;}"
            "QListWidget::item:selected{background:#EAF3FF;color:#10234A;border-radius:6px;}"
        )
        for widget in (panel.today, panel.yesterday, panel.saved):
            widget.setStyleSheet(list_style)
            widget.setSpacing(1)
        panel.today.setMaximumHeight(150)
        panel.yesterday.setMaximumHeight(108)
        panel.privacy.hide()

        # Re-apply current data through the new presentation immediately.
        self._s09_refresh()

    Window._s09_route = route_with_conversation_fidelity
    _installed = True
