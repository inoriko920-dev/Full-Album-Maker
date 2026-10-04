from full_album_maker.media_library_model import (
    MediaAsset, MediaLibraryIndex, MediaMetadata, MediaQuery, MediaSelection,
    MediaSort, MediaStatus, MediaType, normalize_tags, stable_asset_id,
)


def _asset(name, kind, imported, *, fav=False, status=MediaStatus.READY, tags=()):
    return MediaAsset(
        asset_id=stable_asset_id('/fixture/' + name, kind),
        path='/fixture/' + name,
        display_name=name,
        media_type=kind,
        status=status,
        favorite=fav,
        tags=tuple(tags),
        metadata=MediaMetadata(),
        imported_at=imported,
    )


def test_query_search_filter_sort_are_in_memory_and_stable():
    assets = [
        _asset('Senja.mp4', MediaType.VIDEO, 30, fav=True, tags=('vlog',)),
        _asset('Jalan.mp3', MediaType.AUDIO, 20, tags=('senja',)),
        _asset('Pantai.jpg', MediaType.PHOTO, 10),
        _asset('Hilang.mp4', MediaType.VIDEO, 5, status=MediaStatus.MISSING),
    ]
    index = MediaLibraryIndex(assets)
    assert index.counts() == {'all': 4, 'audio': 1, 'photo': 1, 'video': 2, 'favorite': 1, 'missing': 1}
    assert [x.display_name for x in index.project(MediaQuery(search='SENJA'))] == ['Senja.mp4', 'Jalan.mp3']
    assert [x.display_name for x in index.project(MediaQuery(category='video', sort=MediaSort.OLDEST))] == ['Hilang.mp4', 'Senja.mp4']
    assert [x.display_name for x in index.project(MediaQuery(category='favorite'))] == ['Senja.mp4']


def test_selection_single_toggle_range_and_all():
    ids = ['a', 'b', 'c', 'd']
    selection = MediaSelection()
    selection.select_only('b')
    selection.select_range(ids, 'd')
    assert selection.selected_ids == ['b', 'c', 'd']
    selection.toggle('c')
    assert selection.selected_ids == ['b', 'd']
    selection.select_all(['d', 'a'])
    assert selection.selected_ids == ['d', 'a']


def test_tag_normalization_trims_and_deduplicates_case_insensitive():
    assert normalize_tags([' senja ', 'Vlog', 'SENJA', '', 'vlog ']) == ('senja', 'Vlog')
