from __future__ import annotations

from pathlib import Path

from full_album_maker.editor_models import ProjectDocument
from full_album_maker.template_studio_step07 import TemplateStudioDraft, builtin_descriptors
from full_album_maker.template_thumbnail_cache_step07 import (
    TemplateThumbnailCache,
    thumbnail_cache_key,
)


def test_fast_renderer_does_not_deadlock_and_cache_hit_is_reused(tmp_path: Path) -> None:
    document = ProjectDocument.new_empty("Thumbnail Fixture")
    descriptor = builtin_descriptors()[0]
    draft = TemplateStudioDraft(template_id=descriptor.template_id)
    calls: list[str] = []

    def renderer(_document, item, _draft, _custom, destination: Path) -> str:
        calls.append(item.template_id)
        destination.write_bytes(b"png-fixture")
        return str(destination)

    cache = TemplateThumbnailCache(tmp_path / "cache", renderer=renderer, max_workers=1)
    try:
        assert cache.request(document, descriptor, draft) is None
        assert cache.wait_for_idle(timeout=3.0) is True
        expected = cache.path_for_key(thumbnail_cache_key(document, descriptor, draft))
        assert expected.is_file()
        assert expected.read_bytes() == b"png-fixture"
        assert cache.request(document, descriptor, draft) == str(expected)
        assert calls == [descriptor.template_id]
    finally:
        cache.close()


def test_failed_key_is_memoized_but_changed_draft_gets_new_attempt(tmp_path: Path) -> None:
    document = ProjectDocument.new_empty("Fallback Fixture")
    descriptor = builtin_descriptors()[0]
    calls = 0

    def renderer(_document, _item, _draft, _custom, _destination: Path) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("ffmpeg unavailable")

    cache = TemplateThumbnailCache(tmp_path / "cache", renderer=renderer, max_workers=1)
    try:
        first = TemplateStudioDraft(template_id=descriptor.template_id, overlay_opacity=0.60)
        second = TemplateStudioDraft(template_id=descriptor.template_id, overlay_opacity=0.45)
        first_key = thumbnail_cache_key(document, descriptor, first)
        second_key = thumbnail_cache_key(document, descriptor, second)
        assert first_key != second_key

        assert cache.request(document, descriptor, first) is None
        assert cache.wait_for_idle(timeout=3.0) is True
        assert calls == 1

        # Same failed payload must not keep spawning background jobs.
        assert cache.request(document, descriptor, first) is None
        assert cache.wait_for_idle(timeout=0.2) is True
        assert calls == 1

        # A meaningful draft change invalidates the key and may retry.
        assert cache.request(document, descriptor, second) is None
        assert cache.wait_for_idle(timeout=3.0) is True
        assert calls == 2
    finally:
        cache.close()
