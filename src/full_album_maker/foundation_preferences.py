from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .foundation_tokens import TOKENS, WORKSPACE_LABELS
from .paths import data_dir


@dataclass
class FoundationPreferences:
    width: int = 1600
    height: int = 900
    maximized: bool = False
    workspace: str = "home"
    nav_compact: bool = False
    right_dock_collapsed: bool = False
    right_dock_width: int = TOKENS.right_dock_width
    timeline_collapsed: bool = True
    timeline_height: int = TOKENS.timeline_collapsed_height

    @classmethod
    def sanitize(cls, raw: object) -> "FoundationPreferences":
        if not isinstance(raw, dict):
            return cls()
        try:
            value = cls(
                width=int(raw.get("width", 1600)),
                height=int(raw.get("height", 900)),
                maximized=bool(raw.get("maximized", False)),
                workspace=str(raw.get("workspace", "home")),
                nav_compact=bool(raw.get("nav_compact", False)),
                right_dock_collapsed=bool(raw.get("right_dock_collapsed", False)),
                right_dock_width=int(raw.get("right_dock_width", TOKENS.right_dock_width)),
                timeline_collapsed=bool(raw.get("timeline_collapsed", True)),
                timeline_height=int(raw.get("timeline_height", TOKENS.timeline_collapsed_height)),
            )
        except (TypeError, ValueError):
            return cls()
        value.width = min(3840, max(900, value.width))
        value.height = min(2160, max(650, value.height))
        value.right_dock_width = min(520, max(280, value.right_dock_width))
        value.timeline_height = min(520, max(TOKENS.timeline_collapsed_height, value.timeline_height))
        if value.workspace not in WORKSPACE_LABELS:
            value.workspace = "home"
        return value


class FoundationPreferenceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "ui-foundation.json")

    def load(self) -> FoundationPreferences:
        try:
            return FoundationPreferences.sanitize(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return FoundationPreferences()

    def save(self, value: FoundationPreferences) -> None:
        safe = FoundationPreferences.sanitize(asdict(value))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(asdict(safe), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)
