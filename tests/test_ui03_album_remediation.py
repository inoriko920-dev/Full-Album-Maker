from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui03_album_remediation_matches_route_contract(tmp_path) -> None:
    script = textwrap.dedent(
        r"""
        import os
        import tempfile
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")

        import full_album_maker.main  # installs the real production layer stack
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from full_album_maker.album_capture import _fixture_document
        from full_album_maker.foundation_window import FoundationMainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="ui03-remediation-") as folder:
            document = _fixture_document(Path(folder), populated=True)
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
            assert shell.inspector.width() in range(304, 315)
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
        os._exit(0)
        """
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FAM_STEP11_NO_RECOVERY_PROMPT"] = "1"
    env["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    env["FAM_STEP09_PROVIDER"] = "mock"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
