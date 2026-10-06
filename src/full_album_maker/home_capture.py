from __future__ import annotations

import argparse
import json
from pathlib import Path

from .foundation_capture import (
    _compose_native_title_preview,
    _difference,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


FIXTURE_STATES = (
    "recovery",
    "no-recovery",
    "first-run",
    "portable-warning",
    "output-invalid",
)


def _fixture_recents():
    from .home_state import RecentAvailability, RecentProject

    return [
        RecentProject(
            "fixture-1",
            "C:/Fixtures/Senja di Kota Ini.json",
            "Senja di Kota Ini",
            1736692320.0,
            10,
            42 * 60 + 18,
            availability=RecentAvailability.AVAILABLE,
        ),
        RecentProject(
            "fixture-2",
            "C:/Fixtures/Jalan Pulang.json",
            "Jalan Pulang",
            1736519520.0,
            12,
            38 * 60 + 5,
            availability=RecentAvailability.AVAILABLE,
        ),
        RecentProject(
            "fixture-3",
            "C:/Fixtures/Perjalanan Kita.json",
            "Perjalanan Kita",
            1736346720.0,
            11,
            45 * 60 + 27,
            availability=RecentAvailability.AVAILABLE,
        ),
        RecentProject(
            "fixture-4",
            "C:/Fixtures/Cerita Baru.json",
            "Cerita Baru",
            1736087520.0,
            9,
            36 * 60 + 14,
            availability=RecentAvailability.AVAILABLE,
        ),
    ]


def fixture_state(name: str = "recovery"):
    from .home_state import (
        CapabilityState,
        HomeViewState,
        PortableStatus,
        QuickDefaults,
        RecoveryCandidate,
        RecoveryValidation,
    )

    if name not in FIXTURE_STATES:
        raise ValueError(f"Fixture STEP02 tidak dikenal: {name}")

    caps = PortableStatus(
        ffmpeg=CapabilityState.READY,
        manual_offline=CapabilityState.READY,
        ai_config=CapabilityState.OPTIONAL,
        ffmpeg_detail="Siap untuk impor, proses, dan render tanpa instalasi tambahan.",
        manual_detail="Semua fitur editing tersedia offline.",
        ai_detail="Opsional. Konfigurasikan untuk fitur AI.",
    )
    defaults = QuickDefaults(
        ratio_id="16:9",
        resolution_id="1080p",
        width=1920,
        height=1080,
        output_folder="Video\\Full Album",
    )

    recents = [] if name == "first-run" else _fixture_recents()
    state = HomeViewState(quick_defaults=defaults, capabilities=caps).with_recent(recents)

    if name == "recovery":
        recovery = RecoveryCandidate(
            candidate_id="fixture-recovery",
            path="C:/Fixtures/recovery/home_autosave.json",
            timestamp=1736692320.0,
            project_identity="fixture-project",
            validation_state=RecoveryValidation.VALID,
        )
        return state.with_valid_recovery(recovery)

    if name in {"no-recovery", "first-run"}:
        return state.with_valid_recovery(None)

    if name == "portable-warning":
        warning = PortableStatus(
            ffmpeg=CapabilityState.WARNING,
            manual_offline=CapabilityState.READY,
            ai_config=CapabilityState.OPTIONAL,
            ffmpeg_detail="FFmpeg portable belum ditemukan. Editing manual tetap tersedia.",
            manual_detail="Semua fitur editing inti tetap tersedia offline.",
            ai_detail="Opsional. Tidak ada koneksi AI pada startup fixture.",
        )
        return state.with_capabilities(warning)

    invalid = QuickDefaults(
        ratio_id=defaults.ratio_id,
        resolution_id=defaults.resolution_id,
        width=defaults.width,
        height=defaults.height,
        output_folder="Z:/read-only-fixture",
    )
    return state.with_quick_defaults(invalid, output_valid=False)


def capture(
    output: Path,
    width: int = 1672,
    height: int = 941,
    scale: float = 1.0,
    fixture: str = "recovery",
) -> dict[str, object]:
    _prepare_qt(scale)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow

    from .foundation_font import install_foundation_font
    from .foundation_shell import FoundationCommandAdapter, FoundationShellWidget, FoundationUiState
    from .foundation_theme import FOUNDATION_STYLE
    from .home_inspector import HomeInspectorWidget
    from .home_workspace import HomeWorkspace

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    state = FoundationUiState()
    adapter = FoundationCommandAdapter(can_save=lambda: True, can_project_action=lambda: True)
    shell = FoundationShellWidget(state=state, adapter=adapter)
    home_state = fixture_state(fixture)
    home = HomeWorkspace(state=home_state)
    home_index = shell.workspace_stack._index["home"]
    old = shell.workspace_stack.widget(home_index)
    shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    shell.workspace_stack.insertWidget(home_index, home)
    inspector = HomeInspectorWidget(home_state)
    if fixture == "output-invalid":
        inspector.set_output_warning("Pilih lokasi output yang dapat ditulis.")
    shell.inspector.content.set_properties_widget(inspector)
    shell.set_workspace("home")
    shell.workspace_stack.setCurrentWidget(home)
    state.set_status(
        save=("Tersimpan", "success"),
        ffmpeg=(
            "FFmpeg Siap" if home_state.capabilities.ffmpeg.value == "ready" else "FFmpeg Perlu Perhatian",
            "success" if home_state.capabilities.ffmpeg.value == "ready" else "warning",
        ),
        ai=("AI Opsional", "neutral"),
        jobs=("Jobs: 0", "neutral"),
        project_context="Full Album Maker  v1.0.0 Portable  |  Siap digunakan",
    )
    shell.timeline.set_project_context("Belum ada proyek yang dibuka")

    client_height = max(320, height - TOKENS.title_height)
    window = QMainWindow()
    window.setWindowTitle("Full Album Maker")
    window.setStyleSheet(FOUNDATION_STYLE)
    window.setCentralWidget(shell)
    window.resize(width, client_height)
    shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(220, loop.quit)
    loop.exec()
    app.processEvents()
    shell.workspace_stack.setCurrentWidget(home)
    app.processEvents()

    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot: {output}")
    geometry = {
        "window": [width, height],
        "title_bottom": TOKENS.title_height - 1,
        "command_bottom": TOKENS.title_height + shell.command_bar.geometry().bottom(),
        "nav_right": shell.navigation.geometry().right(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "workspace": "home",
        "scale": scale,
        "font_family": font_family,
        "fixture": fixture,
        "home_mode": home_state.mode.value,
        "home_active": shell.workspace_stack.currentWidget() is home,
        "recovery_visible": not home.recovery_banner.isHidden(),
        "error_visible": not home.error_banner.isHidden(),
        "recent_cards": min(4, len(home_state.recent_projects)),
        "recent_empty": len(home_state.recent_projects) == 0,
        "output_invalid": home_state.mode.value == "HOME_OUTPUT_INVALID",
        "output_warning_visible": bool(inspector.output_warning.text()),
        "home_hero": [home.hero.x(), home.hero.y(), home.hero.width(), home.hero.height()],
        "home_recovery": [
            home.recovery_banner.x(), home.recovery_banner.y(),
            home.recovery_banner.width(), home.recovery_banner.height(),
        ],
        "home_recent_host": [
            home.recent_host.x(), home.recent_host.y(),
            home.recent_host.width(), home.recent_host.height(),
        ],
        "home_quick": [home.quick.x(), home.quick.y(), home.quick.width(), home.quick.height()],
        "home_new_button": [
            home.new_project_button.x(), home.new_project_button.y(),
            home.new_project_button.width(), home.new_project_button.height(),
        ],
        "inspector_status_card": [
            inspector.status_card.x(), inspector.status_card.y(),
            inspector.status_card.width(), inspector.status_card.height(),
        ],
        "inspector_settings_card": [
            inspector.settings_card.x(), inspector.settings_card.y(),
            inspector.settings_card.width(), inspector.settings_card.height(),
        ],
    }
    window.close()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP 02 Beranda fixture")
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--state", choices=FIXTURE_STATES, default="recovery")
    parser.add_argument("--golden")
    parser.add_argument("--report")
    ns = parser.parse_args(argv)
    output = Path(ns.output)
    geometry = capture(output, ns.width, ns.height, ns.scale, ns.state)
    result: dict[str, object] = {"current": str(output), "geometry": geometry}
    if ns.golden:
        result.update(_difference(output, Path(ns.golden), output.parent / "diff"))
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
