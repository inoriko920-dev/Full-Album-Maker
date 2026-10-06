from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.usefixtures("qapp")
def test_inspector_tabs_and_collapse_contract(qapp):
    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("media")
    window.show()
    qapp.processEvents()
    dock = window.shell.inspector
    assert dock.content.stack.currentIndex() == 0
    dock.content.ai.click()
    qapp.processEvents()
    assert dock.content.stack.currentIndex() == 1
    assert dock.content.ai.isChecked()
    dock.set_collapsed(True)
    qapp.processEvents()
    assert dock.collapsed
    assert dock.width() == 38
    dock.set_collapsed(False)
    qapp.processEvents()
    assert not dock.collapsed
    assert dock.width() >= 280
    window.close()


@pytest.mark.usefixtures("qapp")
def test_timeline_collapse_and_workspace_height_contract(qapp):
    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("timeline")
    window.show()
    qapp.processEvents()
    timeline = window.shell.timeline
    assert not timeline.collapsed
    assert timeline.height() >= 340
    timeline.set_collapsed(True)
    qapp.processEvents()
    assert timeline.collapsed
    assert timeline.height() <= 40
    timeline.set_collapsed(False)
    qapp.processEvents()
    assert timeline.height() >= 340
    window.close()


def test_preference_store_roundtrip_and_corrupt_fallback(tmp_path: Path):
    from full_album_maker.foundation_preferences import FoundationPreferenceStore, FoundationPreferences

    path = tmp_path / "prefs.json"
    store = FoundationPreferenceStore(path)
    wanted = FoundationPreferences(
        width=1672,
        height=941,
        workspace="timeline",
        nav_compact=False,
        right_dock_collapsed=True,
        right_dock_width=344,
        timeline_collapsed=False,
        timeline_height=352,
    )
    store.save(wanted)
    assert store.load() == wanted
    path.write_text("{not valid json", encoding="utf-8")
    assert store.load() == FoundationPreferences()


@pytest.mark.usefixtures("qapp")
def test_status_bar_observes_state_events(qapp):
    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("home")
    window.show()
    qapp.processEvents()
    state = window.shell.state
    state.set_status(
        save=("Menyimpan…", "warning"),
        ffmpeg=("Tool hilang", "warning"),
        ai=("Gemini Terhubung", "success"),
        jobs=("Jobs: 2", "warning"),
        project_context="Fixture Project",
    )
    qapp.processEvents()
    bar = window.shell.status_bar
    assert bar.save.label.text() == "Menyimpan…"
    assert bar.ffmpeg.label.text() == "Tool hilang"
    assert bar.ai.label.text() == "Gemini Terhubung"
    assert bar.jobs.label.text() == "Jobs: 2"
    assert bar.context.text() == "Fixture Project"
    window.close()


@pytest.mark.usefixtures("qapp")
def test_keyboard_navigation_and_render_shortcut_are_non_destructive(qapp):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    from full_album_maker.foundation_shell import FoundationFixtureWindow

    window = FoundationFixtureWindow("home")
    window.show()
    qapp.processEvents()
    media = window.shell.navigation.buttons["media"]
    media.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.sendEvent(
        media,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier),
    )
    QApplication.sendEvent(
        media,
        QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier),
    )
    qapp.processEvents()
    assert window.shell.state.workspace == "media"
    # Render remains a navigation/preflight entry point. The fixture adapter has
    # no render process side effect and the button remains a safe enabled action.
    assert window.shell.command_bar.buttons["render"].isEnabled()
    window.close()


@pytest.mark.usefixtures("qapp")
def test_production_foundation_window_starts_route_switches_and_compacts(qapp, tmp_path, monkeypatch):
    from full_album_maker import __version__
    from full_album_maker.foundation_preferences import FoundationPreferenceStore
    from full_album_maker.foundation_tokens import TOKENS
    from full_album_maker.foundation_window import FoundationMainWindow

    monkeypatch.setattr(
        "full_album_maker.foundation_window.FoundationPreferenceStore",
        lambda: FoundationPreferenceStore(tmp_path / "ui-foundation.json"),
    )
    window = FoundationMainWindow()
    window.show()
    qapp.processEvents()
    assert window.windowTitle() == f"Full Album Maker v{__version__}"
    assert window.centralWidget() is window.foundation_shell
    before = id(window.project)
    window.foundation_shell.set_workspace("album")
    qapp.processEvents()
    assert id(window.project) == before
    assert window.foundation_state.workspace == "album"

    # The top-level window owns the responsive transition because Windows and
    # offscreen Qt plugins can delay child resize notifications differently.
    window.resize(1366, 768)
    qapp.processEvents()
    assert window.foundation_shell.navigation.width() == TOKENS.nav_compact_width
    assert all(button.toolTip() for button in window.foundation_shell.navigation.buttons.values())
    window.close()


@pytest.mark.usefixtures("qapp")
def test_production_command_adapters_call_recovered_save_open_without_fake_mutation(qapp, tmp_path, monkeypatch):
    from full_album_maker.foundation_preferences import FoundationPreferenceStore
    from full_album_maker.foundation_window import FoundationMainWindow

    monkeypatch.setattr(
        "full_album_maker.foundation_window.FoundationPreferenceStore",
        lambda: FoundationPreferenceStore(tmp_path / "ui-foundation.json"),
    )
    window = FoundationMainWindow()
    window.show()
    qapp.processEvents()
    calls = []
    window._foundation_project_open = True
    monkeypatch.setattr(window, "save_project_file", lambda: calls.append("save"))
    monkeypatch.setattr(window, "load_project_file", lambda: calls.append("open"))
    window._foundation_save_project()
    window._foundation_open_project()
    assert calls == ["save", "open"]
    window.close()


def test_portable_resource_paths_remain_app_relative():
    from full_album_maker.paths import app_root, asset_path, data_dir

    root = app_root().resolve()
    assert asset_path("logo.svg").resolve().is_relative_to(root)
    assert data_dir().resolve().is_relative_to(root)
