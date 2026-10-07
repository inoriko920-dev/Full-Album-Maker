from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui08_ai_agent_remediation_route_contract() -> None:
    script = textwrap.dedent(
        r"""
        import os
        import tempfile
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")
        os.environ.setdefault("FAM_STEP09_GOLDEN", "1")

        import full_album_maker.main
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication
        from full_album_maker.ai_capture_step09 import GOLDEN_PROMPT, _fixture_document
        from full_album_maker.ai_provider_step09 import MockStep09Provider
        from full_album_maker.foundation_window import FoundationMainWindow

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui08-test-"))
        document, song_ids, _video_ids = _fixture_document(root)
        signature = document.content_signature()
        revision = document.revision

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        window._s06_selected_ids = set(song_ids)
        window._s06_primary_song_id = song_ids[0]
        window.foundation_shell.set_workspace("ai_agent")
        window.ai_workspace_s09.set_prompt(GOLDEN_PROMPT)

        context = window._s09_build_context(GOLDEN_PROMPT)
        session = window._s09_ensure_session()
        session.grant = window._s09_grant()
        session.begin_interpretation(GOLDEN_PROMPT, context)
        session.receive_interpretation(MockStep09Provider().interpret(GOLDEN_PROMPT, context))
        session.preview()
        window._s09_context_snapshot = context
        window._s09_refresh()
        window.show()

        loop = QEventLoop()
        QTimer.singleShot(80, loop.quit)
        loop.exec()
        app.processEvents()

        shell = window.foundation_shell
        assert shell.context.width() in range(290, 311), shell.context.width()
        assert shell.inspector.width() in range(290, 311), shell.inspector.width()
        assert shell.timeline.height() in range(168, 189), shell.timeline.height()

        assert window.ai_conversations_s09.new_button.text() == "＋  Percakapan Baru"
        assert hasattr(window.ai_workspace_s09, "ui08_plan_split")
        assert hasattr(window.ai_context_s09, "ui08_permission_toggle")
        assert all(check.isHidden() for check in window.ai_context_s09.permissions.values())
        assert window._ui08_timeline_panel.isHidden() is False
        assert window.ai_timeline_s09.isHidden() is False
        assert shell.timeline.body.isHidden() is True
        assert window._ui08_timeline_canvas.isHidden() is False
        assert window._inspector_router.currentWidget() is window.ai_context_s09
        for widget in getattr(window, "_s06_context_old", ()):
            assert widget.isHidden() is True

        live = window.editor_workspace.document()
        assert live.content_signature() == signature
        assert live.revision == revision
        assert session.snapshot().state.value == "PREVIEW_READY"

        # UI-07 must regain ownership when changing back to Spectrum.
        window.foundation_shell.set_workspace("spectrum")
        app.processEvents()
        assert window._ui08_timeline_panel.isHidden() is True
        assert getattr(window, "_ui07_timeline_panel").isHidden() is False
        assert live.content_signature() == signature
        assert live.revision == revision

        print("UI08_AI_AGENT_REMEDIATION_PASS", flush=True)
        if getattr(window, "_s09_async", None) is not None:
            window._s09_async.close()
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
    env["FAM_STEP09_GOLDEN"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "UI08_AI_AGENT_REMEDIATION_PASS" in result.stdout
