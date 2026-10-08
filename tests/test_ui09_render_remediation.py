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
        from PySide6.QtCore import QEventLoop, QSize, Qt, QTimer
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
        # Emoji font fallback used to show tiny missing-glyph boxes on Windows.
        # Each preset now uses a deterministic Qt-painted icon.
        for preset_id, button in workspace.ui09_preset_buttons.items():
            glyph = getattr(button, "ui09_preset_glyph", None)
            assert glyph is not None and glyph.objectName() == "ui09PresetVectorGlyph"
            assert not glyph.pixmap().isNull(), preset_id
            assert glyph.pixmap().size() == QSize(36, 32), preset_id
            assert glyph.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            assert not button.text().startswith(("▶", "⚙")), preset_id
            assert button.accessibleName().startswith("Preset Render "), preset_id
        assert workspace.ui09_preflight.text() == "Jalankan Preflight"
        assert workspace.ui09_preflight.accessibleName() == "Jalankan Preflight"
        assert workspace.ui09_preflight.iconSize() == QSize(24, 24)
        assert not workspace.ui09_preflight.icon().pixmap(24, 24).isNull()
        assert workspace.ui09_preflight.minimumWidth() >= 172
        assert workspace.ui09_preflight.minimumHeight() >= 46
        assert "#BFDCFE" in workspace.ui09_preflight.styleSheet()
        assert "background:#FEFEFE" in workspace.ui09_preflight.styleSheet()
        assert "margin-top:6px" in workspace.ui09_preflight.styleSheet()
        assert window.render_history_s10.parentWidget() is workspace.ui09_sidebar

        headings = [label.text() for label in workspace.findChildren(QLabel)]
        assert "Pusat Render" in headings
        assert "Media Lengkap" in headings
        assert "Timeline Valid" in headings
        assert "FFmpeg Siap" in headings
        assert "Output Folder" in headings
        assert "Disk Space" in headings
        # Preflight status drawing is platform-independent, but the raw
        # source status text remains exactly STEP10's ✓/⚠/✕ semantic string.
        from full_album_maker.render_remediation import _UI09PreflightStatusLabel
        for key in ("media", "snapshot", "ffmpeg", "output", "disk"):
            card = workspace.preflight_cards[key]
            assert isinstance(card.state, _UI09PreflightStatusLabel), key
            assert card.state.objectName() == "sectionHeading"
        icon_check = _UI09PreflightStatusLabel("✓ PASS")
        icon_check.resize(110, 28)
        icon_check.show()
        app.processEvents()
        assert icon_check.text() == "✓ PASS"
        color_check = icon_check.grab().toImage().pixelColor(4, 12)
        assert color_check.green() > 110 and color_check.green() > color_check.red()
        icon_check.setText("⚠ WARN")
        app.processEvents()
        assert icon_check.text() == "⚠ WARN"
        color_warn = icon_check.grab().toImage().pixelColor(7, 17)
        assert color_warn.red() > 160 and color_warn.red() > color_warn.blue()
        icon_check.setText("✕ BLOCK")
        app.processEvents()
        assert icon_check.text() == "✕ BLOCK"
        assert not icon_check.grab().isNull()

        # Five card illustrations are Qt-painted vectors, not font glyphs.
        # Only the golden desktop preflight is modified; state text and real
        # PreflightReport ownership stay on the original STEP10 cards.
        for key in ("media", "snapshot", "ffmpeg", "output", "disk"):
            card = workspace.preflight_cards[key]
            assert card.ui09_icon.objectName() == "ui09PreflightVectorIcon"
            pixmap = card.ui09_icon.pixmap()
            assert pixmap is not None and not pixmap.isNull()
            assert pixmap.width() == pixmap.height() == 32
            assert card.minimumHeight() == card.maximumHeight() == 154
        assert getattr(workspace.preflight_cards["encoder"], "ui09_icon", None) is None
        # Desktop-only proportion work: do not alter render settings, jobs,
        # workers or the 1366px compact layout.
        assert "Memeriksa kesiapan proyek untuk rendering." in headings
        preset_card = workspace.ui09_preset_buttons["youtube_1080p"]
        assert preset_card.objectName() == "ui09PresetCard"
        assert preset_card.isVisible() and preset_card.height() >= 48
        assert preset_card.maximumHeight() >= preset_card.height()
        assert workspace.queue_list.maximumHeight() == 280
        # Windows Qt native viewport is 2px shorter in desktop and 5px in
        # compact capture; preserve card gaps and only trim the row hint.
        import sys
        assert workspace.queue_list.spacing() == 5

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
        expected_height = 76 if sys.platform == "win32" else 78
        assert [
            workspace.queue_list.item(i).sizeHint().height()
            for i in range(3)
        ] == [expected_height] * 3
        cards = [
            workspace.queue_list.itemWidget(workspace.queue_list.item(index))
            for index in range(3)
        ]
        assert all(card is not None for card in cards)
        # Only an actively running job gets the golden blue highlight.
        # Queued rows stay neutral and visually distinct from verified output.
        assert "#E8F2FF" in cards[0].styleSheet()
        assert "#FFFFFF" in cards[1].styleSheet()
        assert "#FFFFFF" in cards[2].styleSheet()
        assert "#687793" in cards[1].number.styleSheet()
        assert cards[0].progress_detail.text() == "Estimasi sisa 00:36"
        assert cards[1].progress_detail.text() == "◷ Dalam antrean"
        assert cards[1].note.text() == "Menunggu antrean..."
        assert cards[1].layout().itemAt(3).layout().spacing() == 1
        assert cards[1].layout().itemAt(3).layout().contentsMargins().bottom() == 7
        assert cards[0].layout().itemAt(3).layout().contentsMargins().bottom() == 0
        assert cards[0].layout().itemAt(3).layout().spacing() == 7
        assert cards[2].layout().itemAt(3).layout().spacing() == 7
        assert cards[2].progress_detail.text() == "✓ File terverifikasi"
        from full_album_maker.render_remediation import _UI09QueueProgressDetail
        assert all(isinstance(card.progress_detail, _UI09QueueProgressDetail)
                   for card in cards)
        assert cards[0].progress_detail.objectName() == "ui09QueueProgressDetail"
        # Raw status text and existing job ownership remain unchanged.
        assert cards[1].progress_detail.text() == "◷ Dalam antrean"
        assert cards[2].progress_detail.text() == "✓ File terverifikasi"
        assert not cards[1].progress_detail.grab().isNull()
        assert not cards[2].progress_detail.grab().isNull()
        # A completed job without verified_output must not draw a green
        # verified icon: the paint path only responds to genuine STEP10 text.
        # Without real image media, show an honest music placeholder.
        assert all(card.cover.source_path is None for card in cards)
        assert all(card.cover.text() == "♫" for card in cards)
        # Music notes are Qt painted, never Unicode font fallback squares.
        # Center stem stays dark blue against the light blue fallback field.
        for card in cards:
            cover_image = card.cover.grab().toImage()
            assert cover_image.pixelColor(10, 22).red() - cover_image.pixelColor(37, 22).red() > 110
            assert cover_image.pixelColor(37, 22).blue() > cover_image.pixelColor(37, 22).red()
        history = window.render_history_s10
        history.apply_jobs((running, queued, completed))
        assert history.listing.count() == 1
        history_card = history.listing.itemWidget(history.listing.item(0))
        assert history_card is not None
        assert history_card.cover.source_path is None
        assert history_card.cover.text() == "♫"
        history_cover = history_card.cover.grab().toImage()
        assert history_cover.pixelColor(10, 22).red() - history_cover.pixelColor(37, 22).red() > 110
        assert "Terverifikasi" in history_card.status.text()
        assert [card.state.text() for card in cards] == [
            "RUNNING", "ANTREAN", "SELESAI"
        ]
        assert [card.bar.value() for card in cards] == [630, 0, 1000]
        assert "Output terverifikasi" in cards[2].note.text()
        assert [card.heading.text() for card in cards] == [
            "Senja di Kota Ini", "Jalan Pulang", "Perjalanan Kita"
        ]
        assert "Full Album" in cards[0].heading.toolTip()
        assert "#148742" in cards[2].state.styleSheet()
        assert "#BAC8DC" in cards[1].bar.styleSheet()

        # An unverified COMPLETED state must not be presented as a verified
        # final file, even when the job reports 100 percent.
        verified = completed.verified_output
        completed.verified_output = ""
        cards[2].refresh(completed)
        assert cards[2].state.text() == "COMPLETED"
        assert cards[2].progress_detail.text() == "Belum terverifikasi"
        assert not cards[2].progress_detail.grab().isNull()
        assert "Output terverifikasi" not in cards[2].note.text()
        completed.verified_output = verified
        cards[2].refresh(completed)
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


def test_ui09_resize_reflow_preserves_queue_and_golden_desktop() -> None:
    """Window resize must not freeze Wave08 desktop card heights in compact."""
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
        from PySide6.QtCore import QEventLoop, QSize, Qt, QTimer
        from PySide6.QtWidgets import QApplication
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.render_capture_step10 import _fixture_document, _mock_jobs

        app = QApplication.instance() or QApplication([])
        root = Path(tempfile.mkdtemp(prefix="fam-ui09-resize-"))
        document = _fixture_document(root)
        signature = document.content_signature()
        window = FoundationMainWindow()
        window.resize(1672, 941)
        window._foundation_project_open = True
        window.editor_workspace.set_document(document)
        window.foundation_shell.set_workspace("render")
        window.show()

        def settle():
            app.processEvents()
            loop = QEventLoop()
            QTimer.singleShot(90, loop.quit)
            loop.exec()
            app.processEvents()

        settle()
        workspace = window.render_workspace_s10
        running, queued, completed = _mock_jobs(document, root)
        workspace.apply_queue((running, queued, completed))
        settle()
        assert workspace.ui09_compact is False
        assert workspace.queue_list.count() == 3
        assert all(workspace.preflight_cards[k].height() == 154 for k in
                   ("media", "snapshot", "ffmpeg", "output", "disk"))

        window.resize(1366, 768)
        settle()
        assert window.width() == 1366, window.width()
        assert workspace.ui09_compact is True
        assert workspace.ui09_sidebar.width() in range(196, 215)
        assert workspace.ui09_preset_buttons["youtube_1080p"].height() >= 40
        assert workspace.queue_list.count() == 3
        assert all(workspace.preflight_cards[k].minimumHeight() == 88
                   and workspace.preflight_cards[k].maximumHeight() > 154
                   and workspace.preflight_cards[k].ui09_icon.isHidden()
                   for k in ("media", "snapshot", "ffmpeg", "output", "disk"))
        import sys
        expected = 65 if sys.platform == "win32" else 68
        assert [workspace.queue_list.item(i).sizeHint().height()
                for i in range(3)] == [expected] * 3
        assert all(workspace.queue_list.visualItemRect(
                    workspace.queue_list.item(i)).bottom()
                    < workspace.queue_list.viewport().height() for i in range(3)), (
                    workspace.queue_list.viewport().height(),
                    [workspace.queue_list.visualItemRect(
                        workspace.queue_list.item(i)).getRect() for i in range(3)]
                )

        window.resize(1672, 941)
        settle()
        assert workspace.ui09_compact is False
        assert workspace.ui09_sidebar.width() in range(274, 283)
        assert workspace.ui09_preset_buttons["youtube_1080p"].height() >= 48
        assert all(workspace.preflight_cards[k].minimumHeight() == 154
                   and workspace.preflight_cards[k].maximumHeight() == 154
                   and not workspace.preflight_cards[k].ui09_icon.isHidden()
                   for k in ("media", "snapshot", "ffmpeg", "output", "disk"))
        assert [workspace.queue_list.item(i).sizeHint().height()
                for i in range(3)] == [76 if sys.platform == "win32" else 78] * 3
        assert workspace.queue_list.count() == 3
        assert window.editor_workspace.document().content_signature() == signature
        assert workspace.ui09_queue_widgets[(completed.job_id, completed.attempt_id)].progress_detail.text() == "✓ File terverifikasi"
        print("UI09_RESIZE_REFLOW_PASS", flush=True)
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
    assert "UI09_RESIZE_REFLOW_PASS" in result.stdout
