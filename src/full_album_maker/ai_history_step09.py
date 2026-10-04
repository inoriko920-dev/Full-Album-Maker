from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable

from .atomic_io import atomic_write_text
from .paths import data_dir


HISTORY_FORMAT = "full-album-maker-ai-history-v1"
COMMANDS_FORMAT = "full-album-maker-ai-saved-commands-v1"
STORE_VERSION = 1
MAX_HISTORY_ENTRIES = 250
MAX_SAVED_COMMANDS = 100
MAX_TEXT = 4000

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AIza[0-9A-Za-z_-]{16,}"), "<api-key-redacted>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+\-/=]{8,}"), "Bearer <redacted>"),
    (re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+"), r"\1<redacted>"),
    # Redact only the authorization credential itself. History text is
    # normalized to one line before sanitizing; consuming the rest of that line
    # would hide later filesystem paths instead of letting the path rules mark
    # them explicitly as <path-redacted>.
    (re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"), r"\1<redacted>"),
    (re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/])(?:[^\s<>\"']+)"), "<path-redacted>"),
    (re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|mnt|tmp|var|opt|private)/[^\s<>\"']+"), "<path-redacted>"),
)


def sanitize_history_text(value: object, *, limit: int = MAX_TEXT) -> str:
    text = " ".join(str(value or "").split())
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[: max(0, int(limit))]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class AgentHistoryEntry:
    entry_id: str
    timestamp: str
    role: str
    text: str
    status: str = ""
    plan_id: str = ""
    action_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        if self.role not in {"user", "assistant", "system"}:
            raise ValueError("Role history AI tidak valid.")
        return {
            "entry_id": sanitize_history_text(self.entry_id, limit=96),
            "timestamp": sanitize_history_text(self.timestamp, limit=64),
            "role": self.role,
            "text": sanitize_history_text(self.text),
            "status": sanitize_history_text(self.status, limit=80),
            "plan_id": sanitize_history_text(self.plan_id, limit=80),
            "action_names": [sanitize_history_text(value, limit=64) for value in self.action_names[:100]],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AgentHistoryEntry":
        if not isinstance(data, dict):
            raise ValueError("History AI harus object.")
        item = cls(
            entry_id=sanitize_history_text(data.get("entry_id", ""), limit=96),
            timestamp=sanitize_history_text(data.get("timestamp", ""), limit=64),
            role=str(data.get("role", "")),
            text=sanitize_history_text(data.get("text", "")),
            status=sanitize_history_text(data.get("status", ""), limit=80),
            plan_id=sanitize_history_text(data.get("plan_id", ""), limit=80),
            action_names=tuple(
                sanitize_history_text(value, limit=64)
                for value in (data.get("action_names", []) if isinstance(data.get("action_names", []), list) else [])
            ),
        )
        item.to_dict()
        return item


@dataclass(frozen=True)
class SavedAgentCommand:
    command_id: str
    name: str
    prompt: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        name = sanitize_history_text(self.name, limit=100)
        prompt = sanitize_history_text(self.prompt)
        if not self.command_id or not name or not prompt:
            raise ValueError("Perintah tersimpan membutuhkan ID, nama, dan prompt.")
        return {
            "command_id": sanitize_history_text(self.command_id, limit=96),
            "name": name,
            "prompt": prompt,
            "created_at": sanitize_history_text(self.created_at, limit=64),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SavedAgentCommand":
        if not isinstance(data, dict):
            raise ValueError("Perintah tersimpan harus object.")
        item = cls(
            command_id=sanitize_history_text(data.get("command_id", ""), limit=96),
            name=sanitize_history_text(data.get("name", ""), limit=100),
            prompt=sanitize_history_text(data.get("prompt", "")),
            created_at=sanitize_history_text(data.get("created_at", ""), limit=64),
        )
        item.to_dict()
        return item


class AgentHistoryStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "ai" / "history_step09_v1.json"

    def load(self) -> tuple[AgentHistoryEntry, ...]:
        if not self.path.is_file():
            return ()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("format") != HISTORY_FORMAT or raw.get("version") != STORE_VERSION:
                return ()
            entries = raw.get("entries", [])
            if not isinstance(entries, list):
                return ()
            result: list[AgentHistoryEntry] = []
            for item in entries[-MAX_HISTORY_ENTRIES:]:
                try:
                    result.append(AgentHistoryEntry.from_dict(item))
                except ValueError:
                    continue
            return tuple(result)
        except (OSError, json.JSONDecodeError):
            return ()

    def save(self, entries: Iterable[AgentHistoryEntry]) -> None:
        rows = tuple(entries)[-MAX_HISTORY_ENTRIES:]
        payload = {
            "format": HISTORY_FORMAT,
            "version": STORE_VERSION,
            "entries": [item.to_dict() for item in rows],
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def append(
        self,
        *,
        entry_id: str,
        role: str,
        text: str,
        status: str = "",
        plan_id: str = "",
        action_names: Iterable[str] = (),
    ) -> AgentHistoryEntry:
        item = AgentHistoryEntry(
            entry_id=sanitize_history_text(entry_id, limit=96),
            timestamp=_now_iso(),
            role=role,
            text=sanitize_history_text(text),
            status=sanitize_history_text(status, limit=80),
            plan_id=sanitize_history_text(plan_id, limit=80),
            action_names=tuple(sanitize_history_text(value, limit=64) for value in action_names),
        )
        rows = [*self.load(), item]
        self.save(rows)
        return item


class SavedAgentCommandStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "ai" / "saved_commands_step09_v1.json"

    def load(self) -> tuple[SavedAgentCommand, ...]:
        if not self.path.is_file():
            return ()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("format") != COMMANDS_FORMAT or raw.get("version") != STORE_VERSION:
                return ()
            commands = raw.get("commands", [])
            if not isinstance(commands, list):
                return ()
            result: list[SavedAgentCommand] = []
            seen: set[str] = set()
            for data in commands[-MAX_SAVED_COMMANDS:]:
                try:
                    item = SavedAgentCommand.from_dict(data)
                except ValueError:
                    continue
                if item.command_id in seen:
                    continue
                seen.add(item.command_id)
                result.append(item)
            return tuple(result)
        except (OSError, json.JSONDecodeError):
            return ()

    def save(self, commands: Iterable[SavedAgentCommand]) -> None:
        rows = tuple(commands)[-MAX_SAVED_COMMANDS:]
        payload = {
            "format": COMMANDS_FORMAT,
            "version": STORE_VERSION,
            "commands": [item.to_dict() for item in rows],
        }
        atomic_write_text(
            self.path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def upsert(self, command: SavedAgentCommand) -> SavedAgentCommand:
        command.to_dict()
        rows = [item for item in self.load() if item.command_id != command.command_id]
        rows.append(command)
        self.save(rows)
        return command

    def remove(self, command_id: str) -> None:
        rows = [item for item in self.load() if item.command_id != str(command_id)]
        self.save(rows)