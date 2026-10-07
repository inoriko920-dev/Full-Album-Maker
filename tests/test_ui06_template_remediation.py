from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui06_template_remediation_route_contract() -> None:
    script = textwrap.dedent(
        r"""
        import os
        import tempfile
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")

        import full_album_maker.main
        from PySide6.QtWidgets import QApplication
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.template_capture_step07 import _fixture_document

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui06-test-"))
        document = _fixture_document(root)
        signature = document.content_signature()

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        first = document.playlist.entries[0].song_id
        second = document.playlist.entries[1].song_id
        window._s06_primary_song_id = first
        window._s06_selected_ids = {first, second}
        window.editor_workspace.set_playhead(7 * document.timebase)
        window.foundation_shell.set_workspace("template")
        window._s07_refresh()
        window._s07_select_template("spotify_clean")
        window._s07_preview()
        window.show()
        app.processEvents()

        shell = window.foundation_shell
        assert shell.context.width() in range(198, 219), shell.context.width()
        assert shell.inspector.width() in range(310, 331), shell.inspector.width()
        assert shell.timeline.height() in range(170, 191), shell.timeline.height()

        context = window.template_context_s07
        gallery = window.template_workspace_s07
        inspector = window.template_inspector_s07

        assert set(context.ui06_origin_buttons) == {"BUILT_IN", "CUSTOM", "FAVORITE"}
        assert "Semua" in context.ui06_category_buttons
        assert gallery.ui06_sort.currentText() == "Terbaru"
        assert inspector.ui06_preview is not None
        assert inspector.ui06_scope_buttons["current"].isChecked()
        assert inspector.use.text() == "▷  Gunakan Template"
        assert window._ui06_timeline_panel.isHidden() is False
        assert shell.timeline.body.isHidden() is True
        assert window.template_timeline_s07.parentWidget() is window._ui06_timeline_panel
        assert window._s07_current_descriptor().template_id == "spotify_clean"
        assert window.editor_workspace.document().content_signature() == signature

        # UI-05 remains the owner when changing back to Visual.
        window.foundation_shell.set_workspace("visual")
        app.processEvents()
        assert window._ui06_timeline_panel.isHidden() is True
        assert getattr(window, "_ui05_timeline_panel").isHidden() is False
        assert window.editor_workspace.document().content_signature() == signature

        print("UI06_TEMPLATE_REMEDIATION_PASS", flush=True)
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
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "UI06_TEMPLATE_REMEDIATION_PASS" in result.stdout
