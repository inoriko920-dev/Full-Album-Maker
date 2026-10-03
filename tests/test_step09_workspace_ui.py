from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.ai_agent_core_step09 import AgentState, PermissionGrant
from full_album_maker.ai_session_step09 import AgentSessionSnapshot
from full_album_maker.ai_workspace_step09 import AIContextDock, AITaskCanvas


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _snapshot(state: AgentState) -> AgentSessionSnapshot:
    return AgentSessionSnapshot(
        state=state,
        prompt="Pilih 20 lagu",
        message="Rencana siap",
        clarification="",
        plan=None,
        preview=None,
        execution=None,
        error="",
    )


def test_task_canvas_button_enablement_is_driven_by_agent_state() -> None:
    _app()
    canvas = AITaskCanvas()
    canvas.set_prompt("perintah")

    canvas.apply_session(_snapshot(AgentState.IDLE), can_undo_ai=False)
    assert canvas.send_button.isEnabled() is True
    assert canvas.preview_button.isEnabled() is False
    assert canvas.execute_button.isEnabled() is False
    assert canvas.cancel_button.isEnabled() is False

    canvas.apply_session(_snapshot(AgentState.PLAN_READY), can_undo_ai=False)
    assert canvas.preview_button.isEnabled() is True
    assert canvas.execute_button.isEnabled() is False
    assert canvas.cancel_button.isEnabled() is True

    canvas.apply_session(_snapshot(AgentState.PREVIEW_READY), can_undo_ai=False)
    assert canvas.preview_button.isEnabled() is False
    assert canvas.execute_button.isEnabled() is True
    assert canvas.cancel_button.isEnabled() is True

    canvas.apply_session(_snapshot(AgentState.EXECUTING), can_undo_ai=False)
    assert canvas.send_button.isEnabled() is False
    assert canvas.execute_button.isEnabled() is False
    assert canvas.cancel_button.isEnabled() is False

    canvas.apply_session(_snapshot(AgentState.COMPLETED), can_undo_ai=True)
    assert canvas.undo_button.isEnabled() is True


def test_context_dock_exposes_explicit_permission_grant_and_masks_key_value() -> None:
    _app()
    dock = AIContextDock()
    dock.set_context(project_name="Album Kenangan", song_count=20, media_count=396)
    dock.set_provider("gemini", key_ready=True)
    grant = PermissionGrant(dock.permission_values())
    assert grant.allows(dock.permission_values())
    assert dock.project.text() == "Project Aktif: Album Kenangan"
    assert dock.songs.text() == "Lagu yang Dipilih: 20"
    assert dock.media.text() == "Media yang Boleh Dipakai: 396 dari project"
    assert dock.key_status.text() == "Status Key: Aktif"
    assert "AIza" not in dock.key_status.text()
    dock.permissions["visual.write"].setChecked(False)
    assert "visual.write" not in dock.permission_values()


def test_production_ai_route_and_mock_plan_preview_are_non_destructive(tmp_path: Path) -> None:
    script = textwrap.dedent(
        r'''
        import os
        from pathlib import Path
        import tempfile
        import time
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ["FAM_STEP09_PROVIDER"] = "mock"

        from PySide6.QtWidgets import QApplication
        import full_album_maker.main  # installs production layers through STEP09
        from full_album_maker.ai_agent_core_step09 import AgentState
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="s09-ui-") as root:
            root = Path(root)
            doc = ProjectDocument.new_empty("Album Kenangan")
            song_ids = []
            for index in range(20):
                title = f"Lagu Golden {index + 1:02d}"
                audio_path = root / f"audio-{index + 1:02d}.mp3"
                video_path = root / f"{title}.mp4"
                audio_path.write_bytes(b"audio")
                video_path.write_bytes(b"video")
                audio = MediaAsset(
                    kind="audio",
                    locator=str(audio_path),
                    original_name=audio_path.name,
                    source_duration_tick=30 * TIMEBASE,
                )
                video = MediaAsset(
                    kind="video",
                    locator=str(video_path),
                    original_name=video_path.name,
                    source_duration_tick=12 * TIMEBASE,
                )
                doc.media.extend([audio, video])
                song = SongInstance(
                    asset_id=audio.asset_id,
                    display_title=title,
                    display_artist="Fixture",
                    source_out_tick=30 * TIMEBASE,
                )
                doc.playlist.entries.append(song)
                song_ids.append(song.song_id)
            doc.validate()

            window = FoundationMainWindow()
            window._foundation_project_open = True
            window.editor_workspace.set_document(doc)
            window._s06_selected_ids = set(song_ids)
            before = window.editor_workspace.document().content_signature()
            before_dirty = window.editor_workspace.session.is_dirty
            before_undo = window.editor_workspace.session.can_undo

            window.foundation_shell.set_workspace("ai_agent")
            app.processEvents()
            assert window.foundation_state.workspace == "ai_agent"
            assert window.foundation_shell.workspace_stack.currentWidget() is window.ai_workspace_s09
            assert not window.ai_conversations_s09.isHidden()
            assert window._inspector_router.currentWidget() is window.ai_context_s09
            assert not window.ai_timeline_s09.isHidden()
            assert window.ai_context_s09.songs.text() == "Lagu yang Dipilih: 20"
            assert window._s09_provider_id == "mock"
            assert window.editor_workspace.document().content_signature() == before

            prompt = "Pilih 20 lagu, beri visual yang cocok, slowmo footage 0,5x, lalu susun timeline."
            window._s09_send(prompt)
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                app.processEvents()
                if window._s09_ensure_session().snapshot().state != AgentState.INTERPRETING:
                    break
                time.sleep(0.01)
            state = window._s09_ensure_session().snapshot()
            assert state.state == AgentState.PLAN_READY, state
            assert state.plan is not None
            assert len(state.plan.scope_song_ids) == 20
            assert window.editor_workspace.document().content_signature() == before
            assert window.editor_workspace.session.is_dirty == before_dirty
            assert window.editor_workspace.session.can_undo == before_undo

            window._s09_preview()
            app.processEvents()
            state = window._s09_ensure_session().snapshot()
            assert state.state == AgentState.PREVIEW_READY, state
            assert state.preview is not None
            assert len(state.preview.impact.changed_song_ids) == 20
            assert window.editor_workspace.document().content_signature() == before
            assert window.editor_workspace.session.is_dirty == before_dirty
            assert window.editor_workspace.session.can_undo == before_undo
            assert window.ai_workspace_s09.execute_button.isEnabled() is True

            if window._s09_async is not None:
                window._s09_async.close()
            window.hide()
            window.deleteLater()
            app.processEvents()
        '''
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FAM_STEP09_PROVIDER"] = "mock"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=40,
    )
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
