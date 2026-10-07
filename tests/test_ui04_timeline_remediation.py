from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui04_timeline_remediation_matches_route_contract() -> None:
    script = textwrap.dedent(
        r"""
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")

        import full_album_maker.main
        from PySide6.QtWidgets import QApplication
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.timeline_capture import _fixture_document
        from full_album_maker.timeline_workspace_step05 import TimelinePrecisionCanvas

        app = QApplication.instance() or QApplication([])
        document = _fixture_document(populated=True)
        signature = document.content_signature()

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        window.foundation_shell.set_workspace("timeline")
        window._s05_select_song(document.playlist.entries[0].song_id)
        window._s05_set_playhead(84 * document.timebase)
        window.show()
        app.processEvents()

        shell = window.foundation_shell
        assert shell.context.width() in range(320, 339), shell.context.width()
        assert shell.inspector.width() in range(338, 359), shell.inspector.width()
        assert shell.timeline.height() in range(342, 349), shell.timeline.height()
        assert shell.timeline.body.isHidden() is True
        assert window.timeline_precision_s05.parentWidget() is shell.timeline
        assert window.timeline_precision_s05.isHidden() is False
        assert window.timeline_precision_s05.delete_gap.isHidden() is True
        assert window.timeline_context_s05.ui04_project_title.text() == "Proyek: Senja di Kota Ini"
        assert window.timeline_inspector_s05.heading.text() == "Lagu Utama"
        assert window.timeline_inspector_s05.subtitle.text() == "Senja di Kota Ini.mp3"
        assert window.timeline_inspector_s05.apply_button.isHidden() is True
        assert TimelinePrecisionCanvas.LEFT == 286
        assert TimelinePrecisionCanvas.RULER == 43
        assert TimelinePrecisionCanvas.ROW == 32
        assert window.editor_workspace.document().content_signature() == signature

        # UI-03 Album remains owned by the previous remediation layer.
        window.foundation_shell.set_workspace("album")
        app.processEvents()
        assert shell.context.width() in range(288, 306), shell.context.width()
        assert shell.timeline.body.isHidden() is False
        assert window.editor_workspace.document().content_signature() == signature

        print("UI04_TIMELINE_REMEDIATION_PASS")
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
    assert "UI04_TIMELINE_REMEDIATION_PASS" in result.stdout
