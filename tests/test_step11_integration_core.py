from __future__ import annotations

from pathlib import Path

from full_album_maker.editor_commands import SetPlaylistEntries
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.integration_core_step11 import (
    DomainEvent,
    DomainEventHub,
    DomainEventType,
    OWNERSHIP_MAP,
    SelectionStore,
    classify_document_changes,
    normalized_project_hash,
    normalized_project_json,
)
from full_album_maker.playlist_commands import SetSongVisual


def _document(tmp_path: Path) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Integration STEP11")
    for index in range(3):
        path = tmp_path / f"song-{index}.mp3"
        path.write_bytes(b"audio")
        asset = MediaAsset(
            kind="audio",
            locator=str(path),
            original_name=path.name,
            source_duration_tick=20 * TIMEBASE,
        )
        doc.media.append(asset)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=asset.asset_id,
                display_title=f"Song {index}",
                source_out_tick=20 * TIMEBASE,
            )
        )
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"image")
    doc.media.append(MediaAsset(kind="image", locator=str(image_path), original_name=image_path.name))
    doc.validate()
    return doc


def test_editor_controller_revision_and_bulk_transaction_are_single_authority(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    controller = EditorController(doc)
    before_revision = controller.revision
    reordered = list(reversed(controller.snapshot().playlist.entries))
    controller.dispatch(SetPlaylistEntries(reordered))
    assert controller.revision == before_revision + 1
    assert controller.is_dirty is True
    assert controller.can_undo is True
    controller.undo()
    assert controller.revision == before_revision + 2
    assert [x.song_id for x in controller.snapshot().playlist.entries] == [x.song_id for x in doc.playlist.entries]


def test_event_hub_queues_nested_events_instead_of_reentrant_recursion() -> None:
    hub = DomainEventHub()
    observed: list[str] = []
    active_depth = 0
    max_depth = 0

    def first(event: DomainEvent) -> None:
        nonlocal active_depth, max_depth
        active_depth += 1
        max_depth = max(max_depth, active_depth)
        observed.append(event.type.value)
        hub.emit(DomainEvent(DomainEventType.DIRTY_CHANGED, "p", 2, {"dirty": True}))
        active_depth -= 1

    hub.subscribe(DomainEventType.PROJECT_REVISION_CHANGED, first)
    hub.subscribe(DomainEventType.DIRTY_CHANGED, lambda event: observed.append(event.type.value))
    hub.emit(DomainEvent(DomainEventType.PROJECT_REVISION_CHANGED, "p", 1))
    assert observed == ["PROJECT_REVISION_CHANGED", "DIRTY_CHANGED"]
    assert max_depth == 1


def test_selection_store_uses_stable_ids_and_prunes_deleted_domain_items(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    hub = DomainEventHub()
    events = []
    hub.subscribe(DomainEventType.SELECTION_CHANGED, events.append)
    store = SelectionStore(hub, "project-token")
    first = doc.playlist.entries[0].song_id
    image = next(asset for asset in doc.media if asset.kind == "image")
    store.update(
        revision=doc.revision,
        song_ids=[first, first],
        media_ids=[image.asset_id],
        primary_song_id=first,
        time_tick=999999999,
    )
    assert store.snapshot.song_ids == (first,)
    assert len(events) == 1

    changed = doc.clone()
    changed.playlist.entries = [song for song in changed.playlist.entries if song.song_id != first]
    changed.media = [asset for asset in changed.media if asset.asset_id != image.asset_id]
    changed.validate()
    store.prune(changed)
    assert store.snapshot.song_ids == ()
    assert store.snapshot.media_ids == ()
    assert store.snapshot.primary_song_id == ""
    assert store.snapshot.time_tick <= 60 * TIMEBASE
    assert events[-1].payload["pruned"] is True


def test_selection_range_can_be_preserved_or_explicitly_cleared(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    store = SelectionStore(DomainEventHub(), "p")
    store.update(revision=doc.revision, range_start_tick=100, range_end_tick=200)
    store.update(revision=doc.revision, time_tick=150)
    assert store.snapshot.range_start_tick == 100
    assert store.snapshot.range_end_tick == 200
    store.update(revision=doc.revision, range_start_tick=None, range_end_tick=None)
    assert store.snapshot.range_start_tick is None
    assert store.snapshot.range_end_tick is None


def test_normalized_state_is_deterministic_and_roundtrip_equal(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    encoded = normalized_project_json(doc)
    restored = ProjectDocument.from_dict(doc.to_dict())
    assert normalized_project_json(restored) == encoded
    assert normalized_project_hash(restored) == normalized_project_hash(doc)
    assert "preview" not in encoded.casefold()
    assert "render_progress" not in encoded.casefold()


def test_change_classifier_is_derived_from_project_document_not_widgets(tmp_path: Path) -> None:
    before = _document(tmp_path)
    after = before.clone()
    image = next(asset for asset in after.media if asset.kind == "image")
    song_id = after.playlist.entries[0].song_id
    controller = EditorController(after)
    controller.dispatch(SetSongVisual(song_id, image.asset_id))
    changed = controller.snapshot()
    events = classify_document_changes(before, changed)
    assert DomainEventType.ALBUM_CHANGED in events
    assert DomainEventType.VISUAL_CHANGED in events
    assert DomainEventType.MEDIA_CHANGED not in events


def test_ownership_map_marks_legacy_project_as_compatibility_envelope_only() -> None:
    owner, persistent = OWNERSHIP_MAP["legacy_project_envelope"]
    assert "compatibility bridge" in owner.casefold()
    assert persistent is True
    assert OWNERSHIP_MAP["project_document"][0].startswith("EditorSession/EditorController")
