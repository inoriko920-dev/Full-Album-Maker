from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FoundationTokens:
    """Single source of truth for STEP 01 shell measurements and visual tokens."""

    primary_600: str = "#1766E8"
    accent_500: str = "#1B8DFF"
    selection_soft: str = "#EAF3FF"
    border: str = "#D8E4F2"
    app_bg: str = "#F6F9FD"
    surface: str = "#FFFFFF"
    text_primary: str = "#10234A"
    text_muted: str = "#5C6B82"
    success: str = "#1FAF5A"
    warning: str = "#E6A100"
    danger: str = "#D64545"

    # Native Windows title chrome is outside the Qt client area in production.
    # The offscreen screenshot harness reproduces it deterministically so the
    # 1672x941 golden references and client shell use the same coordinate space.
    title_height: int = 41
    command_height: int = 55
    nav_width: int = 172
    # The Beranda golden has no context panel and gives the labelled navigation
    # a wider rail. Other editor workspaces retain nav_width + context_width.
    home_nav_width: int = 211
    nav_compact_width: int = 72
    context_width: int = 264
    right_dock_width: int = 348
    right_dock_compact_width: int = 300
    status_height: int = 28
    timeline_collapsed_height: int = 34
    timeline_compact_height: int = 194
    timeline_medium_height: int = 238
    timeline_dominant_height: int = 352
    splitter_handle: int = 5

    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 22
    radius_control: int = 9
    radius_card: int = 11
    border_width: int = 1
    focus_ring: int = 2
    control_height: int = 38
    primary_control_height: int = 40
    icon_inline: int = 18
    icon_nav: int = 21

    golden_width: int = 1672
    golden_height: int = 941
    compact_breakpoint: int = 1450
    minimum_supported_width: int = 1366


TOKENS = FoundationTokens()

WORKSPACE_ORDER: tuple[tuple[str, str, str], ...] = (
    ("home", "Beranda", "home"),
    ("media", "Media", "media"),
    ("album", "Album", "album"),
    ("timeline", "Timeline", "timeline"),
    ("visual", "Visual", "visual"),
    ("template", "Template", "template"),
    ("spectrum", "Spectrum", "spectrum"),
    ("ai_agent", "AI Agent", "ai_agent"),
    ("render", "Render", "render"),
)

TIMELINE_HEIGHT_BY_WORKSPACE = {
    "home": TOKENS.timeline_collapsed_height,
    "media": TOKENS.timeline_compact_height,
    "album": TOKENS.timeline_compact_height,
    "timeline": TOKENS.timeline_dominant_height,
    "visual": TOKENS.timeline_medium_height,
    "template": 158,
    "spectrum": 252,
    "ai_agent": 178,
    "render": TOKENS.timeline_collapsed_height,
}

WORKSPACE_LABELS = {route: label for route, label, _ in WORKSPACE_ORDER}
