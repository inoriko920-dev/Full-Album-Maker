from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu

from full_album_maker.media_library_model import MediaAsset, MediaLibraryIndex, MediaMetadata, MediaType, stable_asset_id
from full_album_maker.media_workspace import MediaWorkspace


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _asset(tmp_path: Path, name: str = "clip.mp4") -> MediaAsset:
    path = tmp_path / name
    path.write_bytes(b"fixture")
    return MediaAsset(
        asset_id=stable_asset_id(str(path), MediaType.VIDEO),
        path=str(path),
        display_name=name,
        media_type=MediaType.VIDEO,
        metadata=MediaMetadata(duration=42.0, width=1920, height=1080, fps=24.0),
    )


def test_completion_workspace_targets_five_columns_and_collection_action(tmp_path):
    from full_album_maker.media_feature import install_step03_media
    from full_album_maker.media_completion import install_step03_media_completion

    install_step03_media()
    install_step03_media_completion()
    app = _app()
    asset = _asset(tmp_path)
    workspace = MediaWorkspace()
    workspace.resize(990, 600)
    workspace.show()
    workspace.set_index(MediaLibraryIndex([asset]))
    app.processEvents()

    assert workspace._columns() == 5
    calls: list[tuple[str, str, bool]] = []
    workspace._step03_collection_handler = lambda asset_id, name, enabled: calls.append((asset_id, name, enabled))
    card = workspace._cards[0]
    menus = card.findChildren(QMenu)
    assert menus
    collection_menu = next(action.menu() for action in menus[0].actions() if action.text() == "Koleksi")
    target = next(action for action in collection_menu.actions() if action.text() == "Aset Utama")
    target.trigger()
    assert calls == [(asset.asset_id, "Aset Utama", True)]
    workspace.close()


def test_completion_shared_shell_media_geometry_is_route_specific():
    # Importing full_album_maker.main installs the complete recovered compatibility
    # stack globally. Keep that production-order smoke in a child interpreter so
    # it cannot mutate TimelineEngine/project-signature behavior for later tests in
    # the same pytest process.
    script = r'''
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import full_album_maker.main
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from full_album_maker.foundation_window import FoundationMainWindow

app = QApplication.instance() or QApplication([])
window = FoundationMainWindow()
window.resize(1672, 900)
window.show()
window.foundation_shell.set_workspace("media")
loop = QEventLoop()
QTimer.singleShot(140, loop.quit)
loop.exec()
app.processEvents()
shell = window.foundation_shell
assert shell.state.workspace == "media"
assert shell.workspace_stack.currentWidget() is window.media_workspace
assert shell.navigation.width() in range(154, 162)
assert shell.context.width() in range(196, 216)
assert shell.inspector.width() in range(274, 301)
assert shell.timeline.height() in range(180, 205)
assert max(button.height() for button in window.media_context._category_buttons.values()) <= 36
assert max(button.height() for button in window.media_context._collection_buttons.values()) <= 35
assert window.media_workspace._columns() == 5, (
    window.media_workspace.width(),
    window.media_workspace.scroll.viewport().width(),
    shell.workspace_stack.width(),
)
window._saved_project_state = None
window.close()
app.processEvents()
'''
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_final_media_fixture_order_matches_canonical_visual_rhythm():
    from full_album_maker.media_capture_final import _golden_fixture_assets
    from full_album_maker.media_library_model import MediaLibraryIndex, MediaQuery

    # The helper preserves source storage order. The Media workspace applies the
    # default "Terbaru" projection using the deterministic imported_at fixture.
    names = [
        asset.display_name
        for asset in MediaLibraryIndex(_golden_fixture_assets()).project(MediaQuery())
    ]
    assert names[:15] == [
        "Senja di Kota Ini.mp3",
        "Jalan Pulang.mp3",
        "Pantai Bali.jpg",
        "Gunung Bromo.jpg",
        "Perjalanan.jpg",
        "Senja di Kota Ini.mp4",
        "Jalan Pulang.mp4",
        "Perjalanan Kita.mp4",
        "Cerita Baru.mp4",
        "Danau.jpg",
        "Inspirasi.mp3",
        "Hutan.jpg",
        "Pelangi.mp3",
        "Timelapse.mp4",
        "Kota Malam.jpg",
    ]
