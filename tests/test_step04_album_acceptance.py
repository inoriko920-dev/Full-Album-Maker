from __future__ import annotations

from full_album_maker.auto_arrange import AUTO_RECIPE_PROPERTY, AutoArrange, AutoArrangeRecipe
from full_album_maker.editor_commands import ReorderSongs
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


def _document(count: int = 8) -> ProjectDocument:
    document = ProjectDocument.new_empty("Perjalanan Kita")
    document.album_title = "Perjalanan Kita"
    visual = MediaAsset(
        kind="image",
        locator="/fixtures/album-cover.png",
        original_name="album-cover.png",
    )
    document.media.append(visual)
    for index in range(count):
        audio = MediaAsset(
            kind="audio",
            locator=f"/fixtures/Lagu {index + 1:03d}.mp3",
            original_name=f"Lagu {index + 1:03d}.mp3",
            source_duration_tick=(100 + index) * TIMEBASE,
        )
        document.media.append(audio)
        document.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index + 1:03d}",
                source_out_tick=audio.source_duration_tick,
                cover_asset_id=visual.asset_id,
                visual_asset_id=visual.asset_id,
            )
        )
    document.validate()
    return document


def test_reorder_is_one_undoable_transaction():
    document = _document()
    original_order = [song.song_id for song in document.playlist.entries]
    controller = EditorController(document)
    controller.dispatch(ReorderSongs(list(reversed(original_order))))
    assert [song.song_id for song in controller.snapshot().playlist.entries] == list(reversed(original_order))
    assert controller.can_undo
    controller.undo()
    assert [song.song_id for song in controller.snapshot().playlist.entries] == original_order
    assert controller.can_redo
    controller.redo()
    assert [song.song_id for song in controller.snapshot().playlist.entries] == list(reversed(original_order))


def test_auto_arrange_twice_reuses_owned_layers_without_duplicates():
    document = _document(12)
    controller = EditorController(document)
    visual_id = next(asset.asset_id for asset in document.media if asset.kind == "image")
    recipe = AutoArrangeRecipe(recipe_id="step04-album", fallback_visual_asset_id=visual_id)

    controller.dispatch(AutoArrange(recipe))
    first = controller.snapshot()
    first_owned = [
        layer for layer in first.layers
        if layer.origin == "auto" and layer.properties.get(AUTO_RECIPE_PROPERTY) == recipe.recipe_id
    ]
    first_ids = [layer.layer_id for layer in first_owned]
    first_signature = first.content_signature()
    assert len(first_owned) == 12
    assert len(set(first_ids)) == 12

    controller.dispatch(AutoArrange(recipe))
    second = controller.snapshot()
    second_owned = [
        layer for layer in second.layers
        if layer.origin == "auto" and layer.properties.get(AUTO_RECIPE_PROPERTY) == recipe.recipe_id
    ]
    second_ids = [layer.layer_id for layer in second_owned]

    assert len(second_owned) == 12
    assert second_ids == first_ids
    assert second.content_signature() == first_signature
