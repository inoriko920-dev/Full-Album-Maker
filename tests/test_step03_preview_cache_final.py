from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage

from full_album_maker.media_library_model import MediaAsset, MediaMetadata, MediaStatus, MediaType, stable_asset_id
from full_album_maker.media_preview_cache import generate_preview, invalidate_source, preview_cache_path


def _photo(path: Path) -> MediaAsset:
    return MediaAsset(
        asset_id=stable_asset_id(str(path), MediaType.PHOTO),
        path=str(path),
        display_name=path.name,
        media_type=MediaType.PHOTO,
        metadata=MediaMetadata(width=64, height=48),
    )


def test_photo_preview_cache_hit_and_source_change_invalidate_identity(tmp_path):
    source = tmp_path / "foto.png"
    image = QImage(64, 48, QImage.Format.Format_RGB32)
    image.fill(0xFF4477AA)
    assert image.save(str(source), "PNG")
    asset = _photo(source)
    first_target = preview_cache_path(asset)
    first = generate_preview(asset)
    assert Path(first).is_file()
    first_mtime = Path(first).stat().st_mtime_ns
    second = generate_preview(asset)
    assert second == first
    assert Path(second).stat().st_mtime_ns == first_mtime

    time.sleep(0.01)
    source.write_bytes(source.read_bytes() + b"\n")
    assert preview_cache_path(asset) != first_target
    assert invalidate_source(source) >= 1
    assert not first_target.exists()


def test_missing_media_has_no_usable_preview(tmp_path):
    path = tmp_path / "missing.jpg"
    asset = MediaAsset(
        asset_id=stable_asset_id(str(path), MediaType.PHOTO),
        path=str(path),
        display_name=path.name,
        media_type=MediaType.PHOTO,
        status=MediaStatus.MISSING,
    )
    try:
        generate_preview(asset)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing media tidak boleh menghasilkan preview cache")
