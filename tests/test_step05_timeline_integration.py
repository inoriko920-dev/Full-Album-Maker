from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_step05_production_route_and_deferred_ownership_in_subprocess():
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    code = textwrap.dedent(
        r'''
        import full_album_maker.main
        from PySide6.QtWidgets import QApplication
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.timeline_precision import AddTimelineMarker

        app = QApplication.instance() or QApplication([])
        window = FoundationMainWindow()
        doc = ProjectDocument.new_empty('Timeline Production')
        doc.playlist.mode = 'free'
        starts=(0, 10*TIMEBASE, 24*TIMEBASE)
        for index, start in enumerate(starts):
            asset=MediaAsset(
                kind='audio',
                locator=f'/tmp/timeline-{index+1}.mp3',
                original_name=f'timeline-{index+1}.mp3',
                source_duration_tick=12*TIMEBASE,
            )
            doc.media.append(asset)
            doc.playlist.entries.append(SongInstance(
                asset_id=asset.asset_id,
                display_title=f'Lagu {index+1}',
                source_out_tick=12*TIMEBASE,
                free_start_tick=start,
                crossfade_in_tick=2*TIMEBASE if index == 1 else 0,
            ))
        AddTimelineMarker(10*TIMEBASE, 'Reff').apply(doc)
        doc.validate()
        window.editor_workspace.set_document(doc)
        window._foundation_project_open=True
        before=window.editor_workspace.document().content_signature()
        window.foundation_shell.set_workspace('timeline')
        app.processEvents()

        assert window.foundation_state.workspace == 'timeline'
        assert window.foundation_shell.workspace_stack.currentWidget() is window.timeline_workspace_s05
        assert window.timeline_context_s05.isHidden() is False
        assert window._inspector_router.currentWidget() is window.timeline_inspector_s05
        assert window.timeline_precision_s05.isHidden() is False
        assert window.timeline_precision_s05.mode.checked_value() == 'free'
        assert window.foundation_shell.timeline.height() >= 340
        assert window.editor_workspace.document().content_signature() == before

        # Marker participates in STEP05 snap candidates.
        song_id=doc.playlist.entries[2].song_id
        snapped=window._s05_snap_song_tick(song_id, 10*TIMEBASE + 1000, 80.0)
        assert snapped == 10*TIMEBASE

        # Leaving the workspace must also be non-mutating and must restore older shell controls.
        window.foundation_shell.set_workspace('album')
        app.processEvents()
        assert window.editor_workspace.document().content_signature() == before
        assert window.foundation_shell.timeline.mode.isHidden() is False
        print('STEP05_TIMELINE_PRODUCTION_SMOKE_PASS')
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
    assert "STEP05_TIMELINE_PRODUCTION_SMOKE_PASS" in completed.stdout
