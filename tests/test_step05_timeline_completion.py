from __future__ import annotations


def _install_completion() -> None:
    from full_album_maker.timeline_completion_step05 import install_step05_timeline_completion

    install_step05_timeline_completion()


def test_completion_layer_exposes_marker_actions(qapp):
    _install_completion()

    from full_album_maker.timeline_workspace_step05 import TimelineContextWidget

    context = TimelineContextWidget()
    assert context.marker_edit_s05.text() == "Edit Marker"
    assert context.marker_delete_s05.text() == "Hapus Marker"
    assert context.stack.indexOf(context.marker_page_s05) == 1


def test_timeline_keyboard_navigation_emits_real_playhead_targets(qapp):
    _install_completion()

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
    from full_album_maker.timeline_workspace_step05 import TimelinePrecisionCanvas

    document = ProjectDocument.new_empty("Keyboard")
    audio = MediaAsset(
        kind="audio",
        locator="keyboard.mp3",
        original_name="keyboard.mp3",
        source_duration_tick=12 * TIMEBASE,
    )
    document.media.append(audio)
    document.playlist.entries.append(
        SongInstance(asset_id=audio.asset_id, source_out_tick=audio.source_duration_tick)
    )
    document.validate()

    canvas = TimelinePrecisionCanvas()
    canvas.set_document(document)
    canvas.set_playhead(4 * TIMEBASE)
    canvas.show()
    canvas.setFocus()
    qapp.processEvents()

    targets: list[int] = []
    canvas.playhead_requested.connect(targets.append)

    QTest.keyClick(canvas, Qt.Key.Key_Right)
    assert targets[-1] == 5 * TIMEBASE
    QTest.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert targets[-1] == 0
    QTest.keyClick(canvas, Qt.Key.Key_End)
    assert targets[-1] == 12 * TIMEBASE
    QTest.keyClick(canvas, Qt.Key.Key_Home)
    assert targets[-1] == 0


def test_preview_aspect_control_changes_display_frame_without_project_mutation(qapp):
    _install_completion()

    from full_album_maker.timeline_workspace_step05 import TimelinePreviewWorkspace

    workspace = TimelinePreviewWorkspace()
    workspace.resize(900, 520)
    workspace.show()
    qapp.processEvents()

    signature_before = workspace.preview._document.content_signature()

    workspace.aspect.setCurrentText("1:1")
    qapp.processEvents()
    square = workspace.preview._canvas_rect()
    assert abs(square.width() / square.height() - 1.0) < 0.01

    workspace.aspect.setCurrentText("9:16")
    qapp.processEvents()
    portrait = workspace.preview._canvas_rect()
    assert abs(portrait.width() / portrait.height() - (9 / 16)) < 0.01

    workspace.aspect.setCurrentText("16:9")
    qapp.processEvents()
    landscape = workspace.preview._canvas_rect()
    assert abs(landscape.width() / landscape.height() - (16 / 9)) < 0.01
    assert workspace.preview._document.content_signature() == signature_before

    assert workspace.monitor_volume.isEnabled() is False
    assert "Audio monitor belum tersedia" in workspace.monitor_volume.toolTip()
