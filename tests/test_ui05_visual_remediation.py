from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_ui05_visual_remediation_route_contract() -> None:
    script = textwrap.dedent(
        r"""
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP11_NO_RECOVERY_PROMPT", "1")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")

        import tempfile
        from pathlib import Path

        import full_album_maker.main
        from PySide6.QtWidgets import QApplication
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.visual_capture_step06 import _fixture_document

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui05-test-"))
        document = _fixture_document(root)
        signature = document.content_signature()

        window = FoundationMainWindow()
        window.resize(1672, 900)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        first = document.playlist.entries[0].song_id
        window._s06_primary_song_id = first
        window._s06_selected_ids = {first}
        window.editor_workspace.set_playhead(52 * document.timebase)
        window.foundation_shell.set_workspace("visual")
        window._s06_refresh()
        window.show()
        app.processEvents()

        shell = window.foundation_shell
        print(
            "UI05_DIAG",
            {
                "route": window.foundation_state.workspace,
                "context_width": shell.context.width(),
                "context_min": shell.context.minimumWidth(),
                "context_max": shell.context.maximumWidth(),
                "inspector_width": shell.inspector.width(),
                "inspector_min": shell.inspector.minimumWidth(),
                "inspector_max": shell.inspector.maximumWidth(),
                "inspector_expanded": getattr(shell.inspector, "_expanded_width", None),
                "splitter": shell.horizontal_splitter.sizes(),
                "timeline_height": shell.timeline.height(),
                "compact": getattr(shell, "_responsive_compact", None),
            },
            flush=True,
        )
        assert shell.context.width() in range(374, 395), shell.context.width()
        assert shell.inspector.width() in range(358, 379), shell.inspector.width()
        assert shell.timeline.height() in range(215, 226), shell.timeline.height()
        assert window._ui05_timeline_panel.isHidden() is False
        assert shell.timeline.body.isHidden() is True
        assert window.visual_timeline_s06.parentWidget() is window._ui05_timeline_panel
        assert window.visual_context_s06.listing.iconSize().width() == 88
        assert window.visual_inspector_s06.ui05_source_meta.text().startswith("senja-kota-ini.png")
        assert window.visual_inspector_s06.ui05_fit.checked_value() == "fit"
        assert window.visual_inspector_s06.ui05_motion.checked_value() == "ken_burns"
        assert window.visual_inspector_s06.ui05_transition.checked_value() == "fade"
        assert window.visual_workspace_s06.ui05_time.text() == "00:52 / 04:18"
        assert window.editor_workspace.document().content_signature() == signature

        # Previous remediation ownership must remain intact.
        window.foundation_shell.set_workspace("timeline")
        app.processEvents()
        assert window._ui05_timeline_panel.isHidden() is True
        assert shell.context.width() in range(320, 339), shell.context.width()
        assert window.editor_workspace.document().content_signature() == signature

        print("UI05_VISUAL_REMEDIATION_PASS", flush=True)
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
    assert "UI05_VISUAL_REMEDIATION_PASS" in result.stdout
