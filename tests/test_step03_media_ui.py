from __future__ import annotations

from full_album_maker.media_capture import fixture_assets
from full_album_maker.media_library_model import MediaLibraryIndex, MediaStatus, MediaViewMode
from full_album_maker.media_workspace import MediaContextWidget, MediaInspectorWidget, MediaWorkspace


def test_media_workspace_query_grid_list_preserves_selection(qapp):
    workspace = MediaWorkspace(); index = MediaLibraryIndex(fixture_assets()); workspace.set_index(index)
    assert len(workspace._visible_assets) == 24
    selected = workspace._visible_assets[0].asset_id
    workspace.selection.select_only(selected); workspace.refresh_view()
    workspace.search.setText('senja'); workspace._apply_search()
    assert workspace._visible_assets
    assert all('senja' in asset.search_text for asset in workspace._visible_assets)
    workspace.set_view_mode(MediaViewMode.LIST)
    assert workspace.query.view_mode == MediaViewMode.LIST
    assert selected in workspace.selection.selected_ids


def test_media_context_counts_fixture_and_missing(qapp):
    context = MediaContextWidget(); index = MediaLibraryIndex(fixture_assets()); context.set_counts(index.counts())
    assert index.counts() == {'all':24,'audio':8,'photo':9,'video':7,'favorite':3,'missing':1}
    assert '24' in context._category_buttons['all'].text()
    assert '1' in context._category_buttons['missing'].text()


def test_media_selection_ctrl_shift_contract(qapp):
    workspace = MediaWorkspace(); workspace.set_index(MediaLibraryIndex(fixture_assets()))
    ids = [a.asset_id for a in workspace._visible_assets[:4]]
    workspace.selection.select_only(ids[0]); workspace.selection.select_range(ids, ids[3])
    assert workspace.selection.selected_ids == ids
    workspace.selection.toggle(ids[1]); assert ids[1] not in workspace.selection.selected_ids


def test_media_inspector_single_and_multi_are_unambiguous(qapp):
    assets = fixture_assets(); inspector = MediaInspectorWidget(); inspector.set_selection((assets[-2],))
    assert assets[-2].display_name in inspector.title.text()
    inspector.set_selection(tuple(assets[:4]))
    assert inspector.title.text() == 'Pilihan Banyak'
    assert '4 item' in inspector.preview.text()
    assert inspector.save_meta.isEnabled() is False


def test_missing_asset_stays_visible_and_relink_enabled(qapp):
    missing = next(a for a in fixture_assets() if a.status == MediaStatus.MISSING)
    workspace = MediaWorkspace(); workspace.set_index(MediaLibraryIndex((missing,)))
    assert workspace._visible_assets[0].status == MediaStatus.MISSING
    inspector = MediaInspectorWidget(); inspector.set_selection((missing,))
    assert inspector.relink.isEnabled() is True
    assert inspector.reveal.isEnabled() is False
