from __future__ import annotations

import json
from pathlib import Path

from full_album_maker.ai_history_step09 import (
    AgentHistoryStore,
    SavedAgentCommand,
    SavedAgentCommandStore,
    sanitize_history_text,
)


def test_history_redacts_keys_authorization_and_absolute_paths(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    store = AgentHistoryStore(path)
    secret = (
        "api_key=AIza1234567890abcdefghijklmnop "
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz "
        r"C:\Users\Toni\rahasia\video.mp4 "
        "/home/toni/private/project.json"
    )
    store.append(
        entry_id="entry-1",
        role="user",
        text=secret,
        status="PLAN_READY",
        action_names=("set_song_visual",),
    )
    raw = path.read_text(encoding="utf-8").casefold()
    assert "aiza123" not in raw
    assert "abcdefghijklmnop" not in raw
    assert "c:\\users" not in raw
    assert "/home/toni" not in raw
    assert "<redacted>" in raw or "<api-key-redacted>" in raw
    assert "<path-redacted>" in raw

    loaded = AgentHistoryStore(path).load()
    assert len(loaded) == 1
    assert loaded[0].role == "user"
    assert loaded[0].action_names == ("set_song_visual",)


def test_saved_commands_restart_persistence_is_sanitized_and_upserted(tmp_path: Path) -> None:
    path = tmp_path / "saved.json"
    store = SavedAgentCommandStore(path)
    first = SavedAgentCommand(
        command_id="cmd-1",
        name="Golden 20 lagu",
        prompt=r"Pakai C:\private\clip.mp4 dan api_key=super-secret-value",
        created_at="2026-10-04T00:00:00+00:00",
    )
    store.upsert(first)
    store.upsert(
        SavedAgentCommand(
            command_id="cmd-1",
            name="Golden final",
            prompt="Pilih 20 lagu dan susun timeline",
            created_at="2026-10-04T00:01:00+00:00",
        )
    )
    reloaded = SavedAgentCommandStore(path).load()
    assert len(reloaded) == 1
    assert reloaded[0].name == "Golden final"
    assert reloaded[0].prompt == "Pilih 20 lagu dan susun timeline"

    store.remove("cmd-1")
    assert SavedAgentCommandStore(path).load() == ()


def test_corrupt_history_or_saved_command_file_fails_closed(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    commands = tmp_path / "commands.json"
    history.write_text("{broken", encoding="utf-8")
    commands.write_text("[]", encoding="utf-8")
    assert AgentHistoryStore(history).load() == ()
    assert SavedAgentCommandStore(commands).load() == ()


def test_sanitizer_bounds_text_and_keeps_normal_indonesian_content() -> None:
    normal = "Pilih 20 lagu, beri visual yang cocok, lalu susun timeline."
    assert sanitize_history_text(normal) == normal
    assert len(sanitize_history_text("x" * 5000, limit=120)) == 120
