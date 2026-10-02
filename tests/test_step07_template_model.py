from __future__ import annotations

import json
from pathlib import Path

import pytest

from full_album_maker.custom_template_builder import CustomTemplateStore
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.template_studio_step07 import (
    ORIGIN_BUILT_IN,
    TemplateFavoriteStore,
    TemplateStudioDraft,
    build_template_apply_commands,
    builtin_descriptors,
    duplicate_to_custom,
    filter_templates,
    preview_template_document,
    stable_scope_song_ids,
)
from full_album_maker.template_system import current_template_id, template_choices
from full_album_maker.visual_precision import visual_settings_map


def _document(tmp_path: Path, songs: int = 3) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Video Full Album")
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"image-fixture")
    image = MediaAsset(kind="image", locator=str(image_path), original_name=image_path.name)
    doc.media.append(image)
    for index in range(songs):
        audio_path = tmp_path / f"song-{index + 1}.mp3"
        audio_path.write_bytes(b"audio-fixture")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=20 * TIMEBASE,
        )
        doc.media.append(audio)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=("Senja di Kota Ini" if index == 0 else f"Lagu {index + 1}"),
                display_artist="Perjalanan Kita",
                source_out_tick=20 * TIMEBASE,
                cover_asset_id=image.asset_id,
            )
        )
    doc.validate()
    return doc


def test_builtin_presentation_wraps_without_renaming_recovered_engine_ids() -> None:
    engine_ids = [item.template_id for item in template_choices()]
    descriptors = builtin_descriptors()
    assert [item.template_id for item in descriptors] == engine_ids
    assert len(descriptors) == 10
    assert descriptors[0].name == "Senja di Kota Ini"
    assert descriptors[0].origin == ORIGIN_BUILT_IN
    assert "16:9" in descriptors[0].ratios
    assert "9:16" in descriptors[0].ratios


def test_favorite_store_is_separate_persistent_and_corruption_safe(tmp_path: Path) -> None:
    path = tmp_path / "favorites.json"
    store = TemplateFavoriteStore(path)
    assert store.load() == set()
    store.set_favorite("spotify_clean", True)
    store.set_favorite("dark_cinematic", True)
    assert store.load() == {"spotify_clean", "dark_cinematic"}
    store.set_favorite("spotify_clean", False)
    assert store.load() == {"dark_cinematic"}
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["template_ids"] == ["dark_cinematic"]
    path.write_text("{broken", encoding="utf-8")
    assert store.load() == set()


def test_filter_search_category_and_favorite_are_metadata_only() -> None:
    items = builtin_descriptors()
    romantic = filter_templates(items, category="Romantis")
    assert {item.template_id for item in romantic} >= {"cafe_acoustic", "romantic_bokeh"}
    searched = filter_templates(items, search="langit")
    assert [item.template_id for item in searched] == ["dark_cinematic"]
    favorite = filter_templates(items, origin="FAVORITE", favorites={"photo_album"})
    assert [item.template_id for item in favorite] == ["photo_album"]


def test_preview_is_disposable_and_does_not_mutate_source_or_history(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    before = doc.content_signature()
    before_revision = doc.revision
    first = doc.playlist.entries[0].song_id
    draft = TemplateStudioDraft(template_id="spotify_clean")

    preview = preview_template_document(doc, draft, (first,))

    assert doc.content_signature() == before
    assert doc.revision == before_revision
    assert current_template_id(doc) == ""
    assert visual_settings_map(doc) == {}
    assert current_template_id(preview) == "spotify_clean"
    assert first in visual_settings_map(preview)
    assert any(layer.name == "Template Dark Overlay" for layer in preview.layers)


def test_selected_scope_preserves_playlist_order_and_is_one_undo_transaction(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=4)
    controller = EditorController(doc)
    ids = [song.song_id for song in doc.playlist.entries]
    selected = {ids[2], ids[0]}
    targets = stable_scope_song_ids(doc, "selected", selected_song_ids=selected)
    assert targets == (ids[0], ids[2])
    draft = TemplateStudioDraft(template_id="dark_cinematic", overlay_opacity=0.45)
    before = controller.snapshot().content_signature()

    commands = build_template_apply_commands(controller.snapshot(), draft, targets)
    after = controller.dispatch(commands)

    assert after.revision == doc.revision + 1
    assert [song.song_id for song in after.playlist.entries] == ids
    assert set(visual_settings_map(after)) == set(targets)
    assert current_template_id(after) == "dark_cinematic"
    assert controller.can_undo is True

    restored = controller.undo()
    assert restored.content_signature() == before
    assert current_template_id(restored) == ""
    assert visual_settings_map(restored) == {}


def test_scope_prevalidation_rejects_stale_selected_id_without_mutation(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    before = doc.content_signature()
    with pytest.raises(ValueError, match="tidak valid"):
        stable_scope_song_ids(
            doc,
            "selected",
            selected_song_ids={doc.playlist.entries[0].song_id, "stale-id"},
        )
    assert doc.content_signature() == before


def test_duplicate_builtin_to_custom_uses_new_portable_custom_id(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    first = doc.playlist.entries[0].song_id
    store = CustomTemplateStore(tmp_path / "custom")
    custom = duplicate_to_custom(
        doc,
        TemplateStudioDraft(template_id="spotify_clean"),
        (first,),
        label="Salinan Senja di Kota Ini",
        description="Fixture STEP07",
        store=store,
    )
    assert custom.template_id.startswith("custom:")
    assert custom.label == "Salinan Senja di Kota Ini"
    loaded = store.load(custom.template_id)
    assert loaded.to_dict() == custom.to_dict()
    assert all("font_path" not in layer.get("properties", {}) for layer in custom.layers)


def test_custom_store_scan_isolates_one_corrupt_file(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    store = CustomTemplateStore(tmp_path / "custom")
    custom = duplicate_to_custom(
        doc,
        TemplateStudioDraft(template_id="photo_album"),
        (doc.playlist.entries[0].song_id,),
        label="Momen Bahagia",
        store=store,
    )
    (store.root / "broken.famtpl.json").write_text("{broken", encoding="utf-8")
    templates, errors = store.scan()
    assert [item.template_id for item in templates] == [custom.template_id]
    assert len(errors) == 1
    assert "broken.famtpl.json" in errors[0]
