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
        from full_album_maker.render_capture_step10 import _fixture_document, _mock_jobs

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
        assert workspace.ui09_sidebar.width() in range(274, 283), workspace.ui09_sidebar.width()
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
        # Desktop-only proportion work: do not alter render settings, jobs,
        # workers or the 1366px compact layout.
        assert "Memeriksa kesiapan proyek untuk rendering." in headings
        assert workspace.ui09_preset_buttons["youtube_1080p"].minimumHeight() >= 74
        assert workspace.queue_list.maximumHeight() == 280

        assert inspector.start.text() == "Render Sekarang"
        assert inspector.preset.isHidden() is True
        assert inspector.preflight.isHidden() is True
        assert inspector.ui09_close_after.isEnabled() is False

        # Inspector settings scroll independently while render controls remain
        # pinned below; all widgets still belong to STEP10's settings owner.
        from PySide6.QtWidgets import QScrollArea, QWidget
        scroll = inspector.ui09_scroll
        assert isinstance(scroll, QScrollArea)
        assert scroll.widget() is inspector.ui09_scroll_host
        assert inspector.filename.parentWidget() is inspector.ui09_scroll_host
        assert inspector.start.parentWidget() is inspector
        assert scroll.horizontalScrollBar().maximum() == 0, {
            "horizontal_overflow": scroll.horizontalScrollBar().maximum(),
            "viewport_width": scroll.viewport().width(),
            "host_width": inspector.ui09_scroll_host.width(),
            "min_host_width": inspector.ui09_scroll_host.minimumSizeHint().width(),
            "resolution_widths": (inspector.width.width(), inspector.height.width()),
            "wide_children": [
                (type(w).__name__, w.objectName(), w.minimumSizeHint().width(),
                 str(w.text())[:55] if callable(getattr(w, "text", None)) else "")
                for w in inspector.ui09_scroll_host.findChildren(QWidget)
                if w.minimumSizeHint().width() > scroll.viewport().width() - 15
            ],
        }
        assert scroll.geometry().bottom() < inspector.start.geometry().top()
        assert inspector.start.isVisible() is True


        # Card widgets are pure views of STEP10 RenderJobs: no second queue,
        # no optimistic completion state, and no fake render lifecycle.
        from dataclasses import replace
        running, queued, completed = _mock_jobs(document, root)
        workspace.apply_queue((running, queued, completed))
        assert workspace.queue_list.count() == 3
        cards = [
            workspace.queue_list.itemWidget(workspace.queue_list.item(index))
            for index in range(3)
        ]
        assert all(card is not None for card in cards)
        # Without real image media, show an honest music placeholder.
        assert all(card.cover.source_path is None for card in cards)
        assert all(card.cover.text() == "♫" for card in cards)
        history = window.render_history_s10
        history.apply_jobs((running, queued, completed))
        assert history.listing.count() == 1
        history_card = history.listing.itemWidget(history.listing.item(0))
        assert history_card is not None
        assert history_card.cover.source_path is None
        assert "Terverifikasi" in history_card.status.text()
        assert [card.state.text() for card in cards] == [
            "RUNNING", "ANTREAN", "SELESAI"
        ]
        assert [card.bar.value() for card in cards] == [630, 0, 1000]
        assert "Output terverifikasi" in cards[2].note.text()
        assert workspace.queue_list.item(2).text().find("COMPLETED VERIFIED") >= 0

        # A real metrics update must reach the existing row, without queuing a
        # new RenderJob, executing FFmpeg or mutating the ProjectDocument.
        running.metrics = replace(running.metrics, percent=68.0, fps=101.0)
        workspace.apply_job(running)
        assert cards[0].bar.value() == 680
        assert cards[0].percent.text() == "68%"
        assert "101 fps" in cards[0].note.text()
        assert window.editor_workspace.document().content_signature() == signature

        # A real local cover must be used as-is rather than a fabricated
        # preview. This fixture never changes the active editor document.
        from PySide6.QtGui import QImage, QColor
        from PySide6.QtCore import QSize
        from full_album_maker.editor_models import MediaAsset
        from full_album_maker.render_remediation import _JobCoverThumb
        cover_path = root / "genuine-cover.png"
        cover_img = QImage(32, 32, QImage.Format.Format_RGB32)
        cover_img.fill(QColor("#3263B4"))
        assert cover_img.save(str(cover_path))
        copy_doc = document.clone()
        image_asset = MediaAsset(
            kind="image", locator=str(cover_path), original_name=cover_path.name,
        )
        copy_doc.media.append(image_asset)
        copy_doc.playlist.entries[0].cover_asset_id = image_asset.asset_id
        copy_doc.validate()
        with_cover = _mock_jobs(copy_doc, root)[0]
        thumb = _JobCoverThumb(with_cover, compact=True)
        assert thumb.source_path == str(cover_path)
        assert thumb.pixmap() is not None and not thumb.pixmap().isNull()
        assert window.editor_workspace.document().content_signature() == signature

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

        # This subprocess tests UI route ownership and zero project mutation,
        # not QObject/worker shutdown.  Windows Qt occasionally aborts with
        # 0xC0000409 while tearing down the offscreen widget graph after all
        # route assertions have passed.  Exit immediately and leave lifecycle
        # teardown to the dedicated close/async regression tests.
        print("UI09_RENDER_REMEDIATION_PASS", flush=True)
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
