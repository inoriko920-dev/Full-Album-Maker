from __future__ import annotations

import json
from pathlib import Path

import pytest

from full_album_maker.foundation_preferences import FoundationPreferences
from full_album_maker.foundation_tokens import TOKENS, WORKSPACE_ORDER


def test_step01_color_and_geometry_contract():
    assert TOKENS.primary_600 == "#1766E8"
    assert TOKENS.accent_500 == "#1B8DFF"
    assert TOKENS.selection_soft == "#EAF3FF"
    assert TOKENS.border == "#D8E4F2"
    assert TOKENS.app_bg == "#F6F9FD"
    assert TOKENS.surface == "#FFFFFF"
    assert TOKENS.text_primary == "#10234A"
    assert TOKENS.text_muted == "#5C6B82"
    assert TOKENS.title_height in range(40, 43)
    assert TOKENS.command_height in range(52, 57)
    assert TOKENS.title_height + TOKENS.command_height in range(92, 101)
    assert TOKENS.nav_width in range(160, 181)
    assert TOKENS.right_dock_width in range(330, 361)
    assert TOKENS.status_height in range(26, 31)
    assert (TOKENS.golden_width, TOKENS.golden_height) == (1672, 941)


def test_workspace_route_contract_is_exact_and_stable():
    assert [(route, label) for route, label, _ in WORKSPACE_ORDER] == [
        ("home", "Beranda"),
        ("media", "Media"),
        ("album", "Album"),
        ("timeline", "Timeline"),
        ("visual", "Visual"),
        ("template", "Template"),
        ("spectrum", "Spectrum"),
        ("ai_agent", "AI Agent"),
        ("render", "Render"),
    ]


def test_preferences_fail_closed_to_safe_defaults():
    assert FoundationPreferences.sanitize("broken") == FoundationPreferences()
    value = FoundationPreferences.sanitize({
        "width": -1,
        "height": 99999,
        "workspace": "not-a-route",
        "right_dock_width": 5,
        "timeline_height": 9000,
    })
    assert value.width == 900
    assert value.height == 2160
    assert value.workspace == "home"
    assert value.right_dock_width == 280
    assert value.timeline_height == 520


def test_foundation_theme_does_not_restore_legacy_dark_theme():
    from full_album_maker.foundation_theme import FOUNDATION_STYLE

    assert "#1766E8" in FOUNDATION_STYLE
    assert "#F6F9FD" in FOUNDATION_STYLE
    assert "#FFFFFF" in FOUNDATION_STYLE
    assert "#07101c" not in FOUNDATION_STYLE.lower()
    assert "qlineargradient" not in FOUNDATION_STYLE.lower()
    # App name belongs to native title chrome; command bar keeps only a spacer.
    assert "QLabel#appName" in FOUNDATION_STYLE
    assert "color: transparent" in FOUNDATION_STYLE


def test_golden_reference_manifest_hashes_are_exact():
    root = Path(__file__).resolve().parents[1] / "docs" / "ui-reference"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = {
        "01-beranda.png": "039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0",
        "02-media.png": "117572570f900d7f25e2fd0dc822bd59c4496dcc6f23bfb9af8cb8b9d10aa3a5",
        "03-album.png": "42756121fc9a0b18b03d006710d1fb528388b3cf86eaf25c0e72afdac11062b9",
        "04-timeline.png": "d559b1d380f03bbb68ab832d3174b32e9d63d64fe7c1c4af98d11e5e7d3839c3",
        "05-visual.png": "8b661752b235de74843950945126ab80837dec01953b796fcdcd6ad2ac317ef8",
        "06-template.png": "cd2dcd55dcfcf16b947737e459129178a71f76b52b625e398c0fc2f1e87f5895",
        "07-spectrum.png": "ffd89d91c8679b819264ce012742e2387313fdfef90e2ea9a2f590685cb7d87f",
        "08-ai-agent.png": "276a602d2617762e87b2007e7191f9042217b41dd3bf75ce42da7a5fa5be29f3",
        "09-render.png": "8739b225d83089772b19f05b133b98b3ea8e448d1fb905ba613751f46d988618",
    }
    assert manifest["golden_viewport"] == [1672, 941]
    assert {item["file"]: item["sha256"] for item in manifest["references"]} == expected


@pytest.mark.usefixtures("qapp")
def test_shell_has_one_shared_navigation_and_switches_without_rebuild(qapp):
    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("home")
    window.resize(1672, 900)
    window.show()
    qapp.processEvents()
    shell = window.shell
    assert len(shell.navigation.buttons) == 9
    first_stack_count = shell.workspace_stack.count()
    shell.set_workspace("timeline")
    qapp.processEvents()
    assert shell.state.workspace == "timeline"
    assert shell.workspace_stack.count() == first_stack_count == 9
    assert shell.navigation.buttons["timeline"].isChecked()
    assert shell.timeline.height() >= 340
    shell.set_workspace("home")
    qapp.processEvents()
    assert shell.timeline.collapsed
    assert shell.timeline.height() <= 40
    window.close()


@pytest.mark.usefixtures("qapp")
def test_shell_compact_mode_at_1366_keeps_navigation_usable(qapp):
    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("media")
    window.resize(1366, 768 - TOKENS.title_height)
    # Fixture windows run through several Qt offscreen plugins in CI. Exercise
    # the same explicit compact-mode API used by production resizeEvent and the
    # deterministic screenshot harness rather than depending on a plugin's
    # pre-show child-resize delivery semantics.
    window.shell.set_compact_mode(True)
    window.show()
    qapp.processEvents()
    assert window.shell.navigation.width() == TOKENS.nav_compact_width
    assert all(button.toolTip() for button in window.shell.navigation.buttons.values())
    assert window.shell.inspector.width() >= 38
    window.close()
