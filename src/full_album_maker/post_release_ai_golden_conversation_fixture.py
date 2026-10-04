from __future__ import annotations

"""QA-only conversation fixture for the approved UI-08 screenshot.

This module is inert during normal application use. When the dedicated golden
capture sets ``FAM_STEP09_GOLDEN=1`` it augments sparse CI history with realistic
conversation/saved-command rows so pixel-QA exercises the populated left rail
shown in the approved reference. Persistent runtime stores are never mutated.
"""

from datetime import datetime, timedelta, timezone
import os

_installed = False


def install_post_release_ai_golden_conversation_fixture() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    if str(os.environ.get("FAM_STEP09_GOLDEN", "")).strip() != "1":
        return

    from .ai_history_step09 import AgentHistoryEntry, SavedAgentCommand
    from .ai_workspace_step09 import AIConversationPanel

    previous_apply = AIConversationPanel.apply_data

    def apply_golden_rows(self, history, saved) -> None:
        rows = list(history)
        commands = list(saved)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        yesterday = now - timedelta(days=1)

        user_rows = [item for item in rows if getattr(item, "role", "") == "user"]
        desired = (
            ("qa-today-1", now.replace(hour=14, minute=32), "Pilih 20 lagu dan susun timeline", "20 lagu, visual cocok, slowmo 0,5x"),
            ("qa-today-2", now.replace(hour=11, minute=20), "Buat opening yang cinematic", "Tambahkan judul album dan logo"),
            ("qa-today-3", now.replace(hour=9, minute=15), "Samakan warna semua klip", "Gunakan tone hangat"),
            ("qa-yesterday-1", yesterday.replace(hour=16, minute=40), "Buat versi pendek 5 menit", "Untuk media sosial"),
            ("qa-yesterday-2", yesterday.replace(hour=13, minute=12), "Tambahkan lirik berjalan", "Gaya minimalis"),
        )
        if len(user_rows) < 5:
            rows = [item for item in rows if getattr(item, "entry_id", "") not in {item[0] for item in desired}]
            for entry_id, stamp, title, detail in desired:
                rows.append(
                    AgentHistoryEntry(
                        entry_id=entry_id,
                        timestamp=stamp.isoformat(),
                        role="user",
                        text=f"{title} — {detail}",
                        status="",
                    )
                )

        desired_commands = (
            SavedAgentCommand(
                command_id="qa-saved-1",
                name="Susun seperti konser",
                prompt="Urutan lagu + transisi cinematic",
                created_at=now.isoformat(),
            ),
            SavedAgentCommand(
                command_id="qa-saved-2",
                name="Buat highlight",
                prompt="Pilih bagian terbaik otomatis",
                created_at=now.isoformat(),
            ),
            SavedAgentCommand(
                command_id="qa-saved-3",
                name="Samakan look visual",
                prompt="Warna dan pencahayaan konsisten",
                created_at=now.isoformat(),
            ),
        )
        if len(commands) < 3:
            commands = list(desired_commands)

        previous_apply(self, tuple(rows), tuple(commands))

    AIConversationPanel.apply_data = apply_golden_rows
