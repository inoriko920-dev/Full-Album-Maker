from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui09_render_remediation_route_contract() -> None:
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
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication, QLabel
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.render_capture_step10 import _fixture_document

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui09-test-"))
        document = _fixture_document(root)
        signature = document.content_signature()

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        window.foundation_shell.set_workspace("render")
        window.show()
        loop = QEventLoop()
        QTimer.singleShot(80, loop.quit)
        loop.exec()
        app.processEvents()

        shell = window.foundation_shell
        workspace = window.render_workspace_s10
        inspector = window.render_inspector_s10

        # Preserve the proven STEP10 shell contract while adding the golden
        # preset/history surface inside the Render workspace itself.
        assert shell.context.maximumWidth() == 0
        assert shell.timeline.collapsed is True
        assert workspace.ui09_sidebar.isHidden() is False
        assert workspace.ui09_sidebar.width() in range(196, 215), workspace.ui09_sidebar.width()
        assert set(workspace.ui09_preset_buttons) == {
            "youtube_1080p", "youtube_1440p", "youtube_4k", "custom"
        }
        assert workspace.ui09_preflight.text().endswith("Jalankan Preflight")
        assert window.render_history_s10.parentWidget() is workspace.ui09_sidebar

        headings = [label.text() for label in workspace.findChildren(QLabel)]
        assert "Pusat Render" in headings
        assert "Media Lengkap" in headings
        assert "Timeline Valid" in headings
        assert "FFmpeg Siap" in headings
        assert "Output Folder" in headings
        assert "Disk Space" in headings

        assert inspector.start.text() == "Render Sekarang"
        assert inspector.preset.isHidden() is True
        assert inspector.preflight.isHidden() is True
        assert inspector.ui09_close_after.isEnabled() is False

        # Presentation preset cards drive the same STEP10 RenderSettings owner.
        workspace.ui09_preset_buttons["youtube_1440p"].click()
        assert inspector.preset.currentData() == "youtube_1440p"
        assert (inspector.width.value(), inspector.height.value()) == (2560, 1440)
        assert window.editor_workspace.document().content_signature() == signature

        # UI-08 remains the owner when leaving Render.
        window.foundation_shell.set_workspace("ai_agent")
        app.processEvents()
        assert window.foundation_state.workspace == "ai_agent"
        assert getattr(window, "_ui08_timeline_panel").isHidden() is False
        assert window.editor_workspace.document().content_signature() == signature

        print("UI09_RENDER_REMEDIATION_PASS", flush=True)
        if getattr(window, "_s10_async", None) is not None:
            window._s10_async.close()
        if getattr(window, "_s09_async", None) is not None:
            window._s09_async.close()
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
    assert "UI09_RENDER_REMEDIATION_PASS" in result.stdout
