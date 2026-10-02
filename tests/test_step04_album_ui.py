from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from full_album_maker.album_workspace import AlbumContextWidget, AlbumMassToolsWidget, AlbumWorkspace
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


def app():
    return QApplication.instance() or QApplication([])


def make_document(count: int = 100) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Perjalanan Kita")
    doc.album_title = "Perjalanan Kita"
    image = MediaAsset(kind="image", locator="/tmp/cover.png", original_name="cover.png")
    video = MediaAsset(kind="video", locator="/tmp/visual.mp4", original_name="visual.mp4", source_duration_tick=10 * TIMEBASE)
    doc.media.extend([image, video])
    for index in range(count):
        audio = MediaAsset(
            kind="audio",
            locator=f"/tmp/Lagu {index + 1:03d}.mp3",
            original_name=f"Lagu {index + 1:03d}.mp3",
            source_duration_tick=(180 + index) * TIMEBASE,
        )
        doc.media.append(audio)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index + 1:03d}",
                source_out_tick=audio.source_duration_tick,
                cover_asset_id=image.asset_id if index >= 12 else None,
                visual_asset_id=None if 6 <= index < 24 else video.asset_id,
            )
        )
    doc.validate()
    return doc


def test_album_workspace_virtualizes_100_song_fixture_to_ten_rows():
    app()
    widget = AlbumWorkspace()
    widget.apply_document(make_document())
    assert widget.table.rowCount() == 10
    assert widget.page_label.text() == "Halaman 1 dari 10"
    widget.set_page(10)
    assert widget.table.rowCount() == 10
    assert widget.table.item(9, 1).text() == "100"


def test_checkbox_selection_is_real_song_id_state():
    qt = app()
    widget = AlbumWorkspace()
    document = make_document(20)
    widget.apply_document(document)
    first_id = document.playlist.entries[0].song_id
    item = widget.table.item(0, 0)
    item.setCheckState(Qt.CheckState.Checked)
    qt.processEvents()
    assert widget.selected_song_ids == {first_id}
    assert widget.bulk_count.text() == "1 lagu dipilih"
    assert all(button.isEnabled() for button in widget.bulk_buttons)


def test_filters_and_context_counts_follow_document_not_fixture_text():
    app()
    document = make_document(100)
    workspace = AlbumWorkspace()
    context = AlbumContextWidget()
    workspace.apply_document(document)
    workspace.set_filter("missing_cover")
    context.apply_document(document, workspace.filter_key)
    assert workspace.table.rowCount() == 10
    assert context.filter_buttons["all"].text().endswith("100")
    assert context.filter_buttons["missing_cover"].text().endswith("12")
    assert context.filter_buttons["missing_visual"].text().endswith("18")
    assert context.filter_buttons["review"].text().endswith("6")


def test_mass_tools_enable_only_when_album_selection_exists():
    app()
    tools = AlbumMassToolsWidget()
    tools.set_selection_count(0)
    assert all(not button.isEnabled() for button in tools._action_widgets)
    tools.set_selection_count(12)
    assert tools.heading.text() == "Alat Massal (12 lagu dipilih)"
    assert tools.selection_chip.text() == "Dipilih: 12 lagu"
    assert all(button.isEnabled() for button in tools._action_widgets)
