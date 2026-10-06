from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.home_capture import fixture_state
from full_album_maker.home_inspector import HomeInspectorWidget
from full_album_maker.home_state import HomeMode, QuickDefaults
from full_album_maker.home_workspace import HomeWorkspace


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_home_workspace_renders_recovery_four_recent_and_quick_start():
    _app()
    state = fixture_state()
    home = HomeWorkspace(state=state)
    assert home.hero_title.text() == "Mulai Full Album"
    assert home.recovery_banner.isHidden() is False
    assert home.recent_row.count() == 4
    assert home.quick.layout().count() == 3
    assert home.see_all.isEnabled() is True


def test_home_workspace_create_and_open_signals_are_real_controls():
    _app()
    home = HomeWorkspace(state=fixture_state())
    called: list[str] = []
    home.create_project_requested.connect(lambda: called.append("create"))
    home.open_project_requested.connect(lambda: called.append("open"))
    home.new_project_button.click()
    home.open_project_button.click()
    assert called == ["create", "open"]


def test_home_loading_state_disables_double_open_controls():
    _app()
    state = fixture_state().begin("open_project")
    home = HomeWorkspace(state=state)
    assert home.new_project_button.isEnabled() is False
    assert home.open_project_button.isEnabled() is False


def test_home_error_state_is_visible_and_recovery_candidate_is_preserved():
    _app()
    state = fixture_state().fail("PROJECT_CORRUPT", "Proyek tidak dapat dibaca.")
    home = HomeWorkspace(state=state)
    assert home.error_banner.isHidden() is False
    assert "tidak dapat dibaca" in home.error_text.text()
    assert state.recovery is not None


def test_home_inspector_roundtrip_defaults_and_output_signal():
    _app()
    state = fixture_state()
    inspector = HomeInspectorWidget(state)
    assert inspector.current_defaults().ratio_id == "16:9"
    assert inspector.current_defaults().resolution_id == "1080p"

    emitted: list[QuickDefaults] = []
    inspector.defaults_changed.connect(lambda value: emitted.append(value))
    inspector.resolution.setCurrentIndex(0)
    assert emitted
    assert emitted[-1].resolution_id == "720p"
    assert (emitted[-1].width, emitted[-1].height) == (1280, 720)


def test_capability_warning_does_not_destroy_recovery_or_error_primary_state():
    state = fixture_state()
    assert state.mode == HomeMode.RECOVERY_AVAILABLE
    warning = state.capabilities.__class__(
        ffmpeg=state.capabilities.ffmpeg.__class__.WARNING,
        manual_offline=state.capabilities.manual_offline,
        ai_config=state.capabilities.ai_config,
    )
    updated = state.with_capabilities(warning)
    assert updated.mode == HomeMode.RECOVERY_AVAILABLE
    assert updated.recovery is not None

    errored = state.fail("PROJECT_CORRUPT", "Rusak")
    assert errored.with_capabilities(warning).mode == HomeMode.OPEN_ERROR


def test_replacing_selected_home_placeholder_keeps_beranda_active():
    app = _app()
    from full_album_maker.foundation_shell import FoundationCommandAdapter, FoundationShellWidget, FoundationUiState

    shell = FoundationShellWidget(
        state=FoundationUiState(),
        adapter=FoundationCommandAdapter(can_save=lambda: True, can_project_action=lambda: True),
    )
    assert shell.state.workspace == "home"
    home = HomeWorkspace(state=fixture_state())
    index = shell.workspace_stack._index["home"]
    old = shell.workspace_stack.widget(index)
    assert shell.workspace_stack.currentWidget() is old
    shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    shell.workspace_stack.insertWidget(index, home)
    app.processEvents()
    assert shell.workspace_stack.currentWidget() is home
    assert shell.state.workspace == "home"


def test_home_golden_density_and_status_presentation_contract():
    app = _app()
    state = fixture_state()
    home = HomeWorkspace(state=state)
    inspector = HomeInspectorWidget(state)
    home.resize(1068, 714)
    inspector.resize(324, 700)
    home.show()
    inspector.show()
    app.processEvents()

    assert home.hero.height() == 218
    assert home.recovery_banner.height() == 60
    assert home.recent_host.height() == 244
    assert home.quick.height() == 86
    assert home.new_project_button.minimumWidth() == 214
    assert home.open_project_button.minimumWidth() == 214
    assert home.new_project_button.maximumWidth() == 214
    assert home.open_project_button.maximumWidth() == 214
    assert len(home._recent_cards) == 4
    assert all(card.duration_badge.text() for card in home._recent_cards)

    assert inspector.ffmpeg.title.text() == "FFmpeg Siap"
    assert inspector.manual.title.text() == "Editing Manual Offline"
    assert inspector.ai.title.text() == "AI Belum Dikonfigurasi"
    assert inspector.ffmpeg.chip.isHidden()
    assert inspector.manual.chip.isHidden()
    assert inspector.ai.chip.isHidden()
    assert inspector.status_card.objectName() == "famCard"
    assert inspector.settings_card.objectName() == "famCard"

    home.close()
    inspector.close()
