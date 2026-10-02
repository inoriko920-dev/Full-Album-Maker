from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMenu

from full_album_maker.media_library_model import MediaAsset, MediaLibraryIndex, MediaMetadata, MediaType, stable_asset_id
from full_album_maker.media_workspace import MediaWorkspace


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _settle(ms: int = 120) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    _app().processEvents()


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
    import full_album_maker.main  # installs STEP03 completion in production order
    from full_album_maker.foundation_window import FoundationMainWindow

    app = _app()
    window = FoundationMainWindow()
    window.resize(1672, 900)
    window.show()
    window.foundation_shell.set_workspace("media")
    _settle()
    shell = window.foundation_shell
    assert shell.state.workspace == "media"
    assert shell.workspace_stack.currentWidget() is window.media_workspace
    assert shell.context.width() in range(196, 216)
    assert shell.inspector.width() in range(274, 301)
    assert shell.timeline.height() in range(180, 205)
    assert window.media_workspace._columns() == 5, (
        window.media_workspace.width(),
        window.media_workspace.scroll.viewport().width(),
        shell.workspace_stack.width(),
    )
    window._saved_project_state = None
    window.close()
    app.processEvents()
