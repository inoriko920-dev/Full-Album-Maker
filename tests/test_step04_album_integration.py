from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_step04_production_install_and_album_route_in_subprocess():
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    code = textwrap.dedent(
        r'''
        import full_album_maker.main  # installs production compatibility/presentation layers
        from PySide6.QtWidgets import QApplication
        from full_album_maker.editor_models import MediaAsset, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.project import Project

        app = QApplication.instance() or QApplication([])
        window = FoundationMainWindow()
        doc = window.editor_workspace.document()
        image = MediaAsset(kind='image', locator='/tmp/cover.png', original_name='cover.png')
        video = MediaAsset(kind='video', locator='/tmp/visual.mp4', original_name='visual.mp4', source_duration_tick=10*TIMEBASE)
        doc.media.extend([image, video])
        for index in range(100):
            audio = MediaAsset(
                kind='audio',
                locator=f'/tmp/Lagu {index+1:03d}.mp3',
                original_name=f'Lagu {index+1:03d}.mp3',
                source_duration_tick=(180+index)*TIMEBASE,
            )
            doc.media.append(audio)
            doc.playlist.entries.append(SongInstance(
                asset_id=audio.asset_id,
                display_title=f'Lagu {index+1:03d}',
                source_out_tick=audio.source_duration_tick,
                cover_asset_id=image.asset_id if index >= 12 else None,
                visual_asset_id=None if 6 <= index < 24 else video.asset_id,
            ))
        doc.album_title='Perjalanan Kita'
        doc.validate()
        window.editor_workspace.set_document(doc)
        window._foundation_project_open=True
        window.foundation_shell.set_workspace('album')
        app.processEvents()

        assert window.foundation_state.workspace == 'album'
        assert window.foundation_shell.workspace_stack.currentWidget() is window.album_workspace
        assert window.album_context.isHidden() is False
        assert window._inspector_router.currentWidget() is window.album_tools
        assert window.album_timeline_canvas.isHidden() is False
        assert window.album_workspace.table.rowCount() == 10
        assert window.album_workspace.page_label.text() == 'Halaman 1 dari 10'

        selected={song.song_id for song in doc.playlist.entries[:12]}
        window.album_workspace.set_selection(selected)
        app.processEvents()
        assert window.album_tools.heading.text() == 'Alat Massal (12 lagu dipilih)'

        window._s04_capture_document()
        saved = window.project.to_dict()
        assert 'album_document_v2' in saved
        restored = Project.from_dict(saved)
        payload = getattr(restored, '_album_document_v2')
        assert payload['album_title'] == 'Perjalanan Kita'
        assert len(payload['playlist']['entries']) == 100
        print('STEP04_ALBUM_PRODUCTION_SMOKE_PASS')
        '''
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "STEP04_ALBUM_PRODUCTION_SMOKE_PASS" in completed.stdout
