from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui07_spectrum_remediation_route_contract() -> None:
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
        from full_album_maker.spectrum_capture_step08 import _fixture_document
        from full_album_maker.spectrum_workspace_step08 import SpectrumLayerRow

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui07-test-"))
        document, spectrum_id = _fixture_document(root)
        signature = document.content_signature()

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        window.editor_workspace.session.select_one(spectrum_id)
        window.editor_workspace.set_playhead(4 * document.timebase)
        window._s08_selected_layer_id = spectrum_id
        # UI-only route contract must not depend on FFmpeg availability.
        window._s08_request_preview = lambda: None

        window.foundation_shell.set_workspace("spectrum")
        window._s08_refresh(request_preview=False)
        window.show()
        app.processEvents()

        shell = window.foundation_shell
        assert shell.context.width() in range(374, 395), shell.context.width()
        assert shell.inspector.width() in range(310, 331), shell.inspector.width()
        assert shell.timeline.height() in range(242, 263), shell.timeline.height()

        assert window._ui07_timeline_panel.isHidden() is False
        assert shell.timeline.body.isHidden() is True
        assert window.spectrum_timeline_s08.parentWidget() is window._ui07_timeline_panel
        assert window.spectrum_workspace_s08.preview_status.isHidden() is True
        assert window.spectrum_context_s08.isHidden() is False
        layer_rows = window.spectrum_context_s08.layer_host.findChildren(SpectrumLayerRow)
        assert len(layer_rows) == 4, len(layer_rows)
        assert all(row.isHidden() is False for row in layer_rows)
        assert window.spectrum_context_s08.layer_scroll.verticalScrollBar().maximum() == 0
        assert window._inspector_router.currentWidget() is window.spectrum_inspector_s08
        assert window.editor_workspace.document().content_signature() == signature

        # Foundation placeholder must not occupy the UI-07 left panel.
        for widget in getattr(window, "_s06_context_old", ()):
            assert widget.isHidden() is True

        # UI-06 remains owner of the Template route.
        window.foundation_shell.set_workspace("template")
        app.processEvents()
        assert window._ui07_timeline_panel.isHidden() is True
        assert getattr(window, "_ui06_timeline_panel").isHidden() is False
        assert window.editor_workspace.document().content_signature() == signature

        print("UI07_SPECTRUM_REMEDIATION_PASS", flush=True)
        window._s08_preview_worker.close()
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
    assert "UI07_SPECTRUM_REMEDIATION_PASS" in result.stdout
