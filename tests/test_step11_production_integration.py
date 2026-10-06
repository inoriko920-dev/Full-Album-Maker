from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_step11_production_shell_uses_one_state_and_canonical_save(tmp_path) -> None:
    script = textwrap.dedent(
        r'''
        import os
        import tempfile
        import time
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ["FAM_STEP11_NO_RECOVERY_PROMPT"] = "1"
        os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
        os.environ["FAM_STEP09_PROVIDER"] = "mock"

        from PySide6.QtWidgets import QApplication
        import full_album_maker.main  # installs all production layers through STEP11
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.v14_window import create_main_window
        from full_album_maker.integration_core_step11 import DomainEventType, normalized_project_hash
        from full_album_maker.integration_lifecycle_step11 import verify_persisted_document
        from full_album_maker.project import MediaItem

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="s11-production-") as folder:
            root = Path(folder)
            audio_path = root / "song.mp3"
            audio_path.write_bytes(b"fixture-audio")
            image_path = root / "visual.png"
            image_path.write_bytes(b"fixture-image")

            doc = ProjectDocument.new_empty("STEP11 Integrated")
            audio = MediaAsset(
                kind="audio",
                locator=str(audio_path),
                original_name=audio_path.name,
                source_duration_tick=20 * TIMEBASE,
            )
            image = MediaAsset(kind="image", locator=str(image_path), original_name=image_path.name)
            doc.media.extend([audio, image])
            song = SongInstance(
                asset_id=audio.asset_id,
                display_title="Senja di Kota Ini",
                source_out_tick=20 * TIMEBASE,
                visual_asset_id=image.asset_id,
            )
            doc.playlist.entries.append(song)
            doc.validate()

            window = create_main_window()
            assert isinstance(window, FoundationMainWindow)
            window._foundation_project_open = True
            window.project.audios = [MediaItem(path=str(audio_path), duration=20.0)]
            window.editor_workspace.set_document(doc)
            app.processEvents()

            assert hasattr(window, "event_hub")
            assert hasattr(window, "selection_store")
            assert window._s11_project_token
            assert window.editor_workspace.session.is_dirty is False

            # Shared stable-ID selection feeds STEP09 before legacy workspace fallbacks.
            window._s11_visual_selection({song.song_id}, song.song_id)
            assert window.selection_store.snapshot.song_ids == (song.song_id,)
            assert window._s09_selected_song_ids() == (song.song_id,)

            events = []
            window.event_hub.subscribe(DomainEventType.PROJECT_REVISION_CHANGED, events.append)
            window.event_hub.subscribe(DomainEventType.DIRTY_CHANGED, events.append)
            before_revision = window.editor_workspace.session.revision
            before_hash = normalized_project_hash(window.editor_workspace.document())

            # One real editor transaction: revision increases once and integration
            # observes it from ProjectDocument, not from widget state.
            window.editor_workspace.session.add_text_layer()
            window.editor_workspace._after_edit()
            app.processEvents()
            changed = window.editor_workspace.document()
            assert changed.revision == before_revision + 1
            assert normalized_project_hash(changed) != before_hash
            assert window.editor_workspace.session.is_dirty is True
            assert any(event.type == DomainEventType.PROJECT_REVISION_CHANGED for event in events)
            assert window._s11_autosave.status.latest_revision == changed.revision
            assert window.foundation_state.save_state == "warning"

            # Flush autosave explicitly; it must not mark canonical save state clean.
            window._s11_autosave_timer.stop()
            window._s11_schedule_autosave_flush()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and window._s11_autosave.status.last_success_revision != changed.revision:
                app.processEvents()
                time.sleep(0.01)
            assert window._s11_autosave.status.last_success_revision == changed.revision
            assert window.editor_workspace.session.is_dirty is True

            # Workspace navigation is view state only and cannot mutate the project.
            navigation_hash = normalized_project_hash(window.editor_workspace.document())
            for route in ("home", "media", "album", "timeline", "visual", "template", "spectrum", "ai_agent", "render"):
                window.foundation_shell.set_workspace(route)
                app.processEvents()
                assert normalized_project_hash(window.editor_workspace.document()) == navigation_hash, route

            # Canonical Foundation save captures the same ProjectDocument in the
            # compatibility envelope, read-back verifies it, then marks clean.
            canonical = root / "canonical-project.json"
            window._foundation_project_path = str(canonical)
            expected = window.editor_workspace.document()
            assert window._foundation_save_project() is True
            assert canonical.is_file()
            assert verify_persisted_document(canonical, expected) is True
            assert window.editor_workspace.session.is_dirty is False
            assert window.foundation_state.save_state == "success"

            # Cleanup without invoking close-confirmation UI.
            window._s11_clear_recovery()
            window._s11_executor.shutdown(wait=True, cancel_futures=True)
            window.hide()
            window.deleteLater()
            app.processEvents()
        '''
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
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
