from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")

import full_album_maker.main  # noqa: F401  # installs production presentation layers
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from full_album_maker.album_capture import _fixture_document
from full_album_maker.foundation_window import FoundationMainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_ui03_album_remediation_matches_route_contract(tmp_path) -> None:
    app = _app()
    document = _fixture_document(tmp_path, populated=True)
    window = FoundationMainWindow()
    window.resize(1672, 900)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window.foundation_shell.set_workspace("album")
    selected = {song.song_id for song in document.playlist.entries[:7]} | {
        song.song_id for song in document.playlist.entries[20:25]
    }
    window.album_workspace.set_selection(selected)
    window.show()
    app.processEvents()

    shell = window.foundation_shell
    assert shell.context.width() in range(288, 306)
    assert shell.inspector.width() in range(315, 334)
    assert window.album_workspace.table.columnCount() == 9
    assert window.album_workspace.table.rowCount() == 10
    assert window.album_workspace.table.item(0, 3).text() == "Senja di Kota Ini"
    assert window.album_workspace.table.item(4, 7).text() == "Perlu Ditinjau"
    assert window.album_workspace.table.item(5, 7).text() == "Belum Ada Visual"
    assert window.album_workspace.table.item(0, 1).checkState() == Qt.CheckState.Checked
    assert window.album_workspace.table.item(7, 1).checkState() == Qt.CheckState.Unchecked
    assert window.album_tools.heading.text() == "Alat Massal (12 lagu dipilih)"
    assert window.album_context.modified.text() == "Dibuat 8 Jan 2025 14:32"
    assert len(getattr(shell.timeline, "_album_header_tools", ())) == 6

    window.hide()
    window.deleteLater()
    app.processEvents()
