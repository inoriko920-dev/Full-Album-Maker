from dataclasses import dataclass
from pathlib import Path
import threading

from full_album_maker.media_library_model import MediaStatus, MediaType, stable_asset_id
from full_album_maker.media_library_services import (
    MediaSidecarStore, SidecarRecord, asset_from_item, collect_folder_paths,
    media_type_for_path,
)


@dataclass
class Item:
    path: str
    duration: float = 0.0


def test_sidecar_roundtrip_does_not_modify_source_media(tmp_path: Path):
    project = tmp_path / 'Album.json'
    project.write_text('{}', encoding='utf-8')
    media = tmp_path / 'Lagu Ω.mp3'
    media.write_bytes(b'original')
    before = media.read_bytes()
    store = MediaSidecarStore(project)
    asset_id = stable_asset_id(str(media), MediaType.AUDIO)
    store.set(asset_id, SidecarRecord(True, ('senja',), 'deskripsi', ('Musik',), 123.0))
    assert media.read_bytes() == before
    loaded = MediaSidecarStore(project).get(asset_id)
    assert loaded.favorite is True
    assert loaded.tags == ('senja',)
    assert loaded.collections == ('Musik',)


def test_asset_adapter_marks_missing_without_dropping_record(tmp_path: Path):
    missing = tmp_path / 'hilang.mp4'
    asset = asset_from_item(Item(str(missing), 42), MediaType.VIDEO)
    assert asset.status == MediaStatus.MISSING
    assert asset.metadata.duration == 42
    assert asset.path.endswith('hilang.mp4')


def test_folder_scan_supported_unicode_hidden_and_cancel(tmp_path: Path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / '.cache').mkdir()
    (tmp_path / 'sub' / 'Video Ω.mp4').write_bytes(b'x')
    (tmp_path / 'foto.jpg').write_bytes(b'x')
    (tmp_path / 'ignore.txt').write_text('x')
    (tmp_path / '.cache' / 'hidden.mp3').write_bytes(b'x')
    result = collect_folder_paths(tmp_path)
    names = {Path(p).name for p in result.paths}
    assert names == {'Video Ω.mp4', 'foto.jpg'}
    assert result.canceled is False
    cancel = threading.Event(); cancel.set()
    assert collect_folder_paths(tmp_path, cancel).canceled is True


def test_media_type_resolver_supported_minimum():
    assert media_type_for_path('a.mp3') == MediaType.AUDIO
    assert media_type_for_path('a.jpg') == MediaType.PHOTO
    assert media_type_for_path('a.mp4') == MediaType.VIDEO
    assert media_type_for_path('a.exe') is None
