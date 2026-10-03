from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
import pytest

import full_album_maker.custom_template_builder as custom_builder
from full_album_maker.custom_template_builder import CustomTemplateStore
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.template_portability_step07 import duplicate_portable_template
from full_album_maker.template_studio_step07 import (
    TemplateStudioDraft,
    build_template_apply_commands,
    builtin_descriptors,
    preview_template_document,
)
from full_album_maker.template_system import current_template_id
from full_album_maker.template_workspace_step07 import TemplateCard


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _document(tmp_path: Path, songs: int = 3) -> tuple[ProjectDocument, Path]:
    doc = ProjectDocument.new_empty("Video Full Album")
    cover_path = tmp_path / "machine-project-cover.png"
    cover_path.write_bytes(b"fixture-image")
    cover = MediaAsset(kind="image", locator=str(cover_path), original_name=cover_path.name)
    doc.media.append(cover)
    for index in range(songs):
        audio_path = tmp_path / f"song-{index + 1}.mp3"
        audio_path.write_bytes(b"fixture-audio")
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
                display_title=f"Lagu {index + 1}",
                display_artist="Perjalanan Kita",
                source_out_tick=20 * TIMEBASE,
                cover_asset_id=cover.asset_id,
            )
        )
    doc.validate()
    return doc, cover_path


def test_reusable_custom_payload_excludes_project_identity_and_machine_paths(tmp_path: Path) -> None:
    doc, cover_path = _document(tmp_path)
    store = CustomTemplateStore(tmp_path / "templates")
    custom = duplicate_portable_template(
        doc,
        TemplateStudioDraft(template_id="photo_album"),
        (doc.playlist.entries[0].song_id,),
        label="Portable Custom",
        description="No project identity",
        store=store,
    )
    encoded = json.dumps(custom.to_dict(), ensure_ascii=False, sort_keys=True)
    assert str(tmp_path) not in encoded
    assert str(cover_path) not in encoded
    assert "song_id" not in encoded
    assert "api_key" not in encoded.casefold()
    assert "output_path" not in encoded.casefold()


def test_custom_template_stays_usable_when_original_project_resource_disappears(tmp_path: Path) -> None:
    doc, cover_path = _document(tmp_path)
    store = CustomTemplateStore(tmp_path / "templates")
    custom = duplicate_portable_template(
        doc,
        TemplateStudioDraft(template_id="photo_album"),
        (doc.playlist.entries[0].song_id,),
        label="Missing Resource Safe",
        store=store,
    )
    cover_path.unlink()

    controller = EditorController(doc)
    targets = (doc.playlist.entries[0].song_id,)
    applied = controller.dispatch(
        build_template_apply_commands(
            controller.snapshot(),
            TemplateStudioDraft(template_id=custom.template_id),
            targets,
            custom_template=CustomTemplateStore(tmp_path / "templates").load(custom.template_id),
        )
    )
    assert applied.revision == doc.revision + 1
    assert any(layer.origin == "template" for layer in applied.layers)


def test_custom_save_failure_keeps_previous_file_and_retry_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, _cover_path = _document(tmp_path)
    store = CustomTemplateStore(tmp_path / "templates")
    original = duplicate_portable_template(
        doc,
        TemplateStudioDraft(template_id="spotify_clean"),
        (doc.playlist.entries[0].song_id,),
        label="Atomic Original",
        store=store,
    )
    path = store._path_for_id(original.template_id)
    previous_bytes = path.read_bytes()
    updated = replace(original, label="Atomic Updated")
    real_replace = custom_builder.os.replace

    def fail_replace(_source, _destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(custom_builder.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        store.save(updated)
    assert path.read_bytes() == previous_bytes
    assert not list(path.parent.glob(path.name + ".*.tmp"))

    monkeypatch.setattr(custom_builder.os, "replace", real_replace)
    store.save(updated)
    assert CustomTemplateStore(tmp_path / "templates").load(updated.template_id).label == "Atomic Updated"


def test_preview_does_not_touch_source_controller_undo_history(tmp_path: Path) -> None:
    doc, _cover_path = _document(tmp_path)
    controller = EditorController(doc)
    assert controller.can_undo is False
    before = controller.snapshot().content_signature()

    preview = preview_template_document(
        controller.snapshot(),
        TemplateStudioDraft(template_id="spotify_clean"),
        (doc.playlist.entries[0].song_id,),
    )

    assert controller.snapshot().content_signature() == before
    assert controller.can_undo is False
    assert current_template_id(controller.snapshot()) == ""
    assert current_template_id(preview) == "spotify_clean"


def test_heart_toggle_emits_favorite_only_never_use_apply() -> None:
    _app()
    card = TemplateCard(builtin_descriptors()[0])
    favorites: list[tuple[str, bool]] = []
    uses: list[str] = []
    card.favorite_requested.connect(lambda template_id, value: favorites.append((template_id, value)))
    card.use_requested.connect(uses.append)

    card.heart.click()

    assert favorites == [(card.descriptor.template_id, True)]
    assert uses == []
