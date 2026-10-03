from __future__ import annotations

import json
from pathlib import Path

import pytest

from full_album_maker.editor_commands import SetPlaylistEntries
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.integration_lifecycle_step11 import (
    DebouncedAutosaveCoordinator,
    IntegrationRecoveryStore,
    RecoveryEnvelope,
    extract_project_document_from_saved_json,
    request_from_document,
    verify_persisted_document,
)
from full_album_maker.project_repository import save_project_document


def _document(tmp_path: Path) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Lifecycle")
    for index in range(2):
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
            SongInstance(asset_id=asset.asset_id, display_title=f"Song {index}", source_out_tick=20 * TIMEBASE)
        )
    doc.validate()
    return doc


def _next_revision(doc: ProjectDocument) -> ProjectDocument:
    controller = EditorController(doc)
    controller.dispatch(SetPlaylistEntries(list(reversed(doc.playlist.entries))))
    return controller.snapshot()


def test_autosave_requests_coalesce_to_last_committed_revision(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    coordinator = DebouncedAutosaveCoordinator()
    first = coordinator.request(doc, project_path=str(tmp_path / "project.json"))
    second_doc = _next_revision(doc)
    second = coordinator.request(second_doc, project_path=str(tmp_path / "project.json"))
    pending = coordinator.take_pending()
    assert pending is not None
    assert pending.generation == second.generation
    assert pending.revision == second_doc.revision
    assert pending.signature == second.signature
    assert pending.signature != first.signature
    assert coordinator.take_pending() is None


def test_stale_autosave_completion_cannot_claim_newer_revision_saved(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    coordinator = DebouncedAutosaveCoordinator()
    older = coordinator.request(doc)
    newer_doc = _next_revision(doc)
    newer = coordinator.request(newer_doc)
    coordinator.complete(older, success=True)
    assert coordinator.status.last_success_generation == 0
    assert coordinator.status.pending is True
    coordinator.complete(newer, success=True)
    assert coordinator.status.last_success_generation == newer.generation
    assert coordinator.status.last_success_revision == newer.revision
    assert coordinator.status.pending is False


def test_failed_latest_autosave_records_error_without_marking_success(tmp_path: Path) -> None:
    coordinator = DebouncedAutosaveCoordinator()
    request = coordinator.request(_document(tmp_path))
    coordinator.complete(request, success=False, error="disk penuh")
    assert coordinator.status.pending is True
    assert coordinator.status.last_success_generation == 0
    assert coordinator.status.last_error == "disk penuh"


def test_recovery_store_roundtrip_is_atomic_domain_snapshot(tmp_path: Path) -> None:
    doc = _next_revision(_document(tmp_path))
    request = request_from_document(doc, project_path=str(tmp_path / "canonical.json"), generation=4)
    store = IntegrationRecoveryStore(tmp_path / "recovery.json")
    envelope = store.write(request)
    discovered = store.discover()
    assert discovered is not None
    assert discovered.project_token == envelope.project_token
    assert discovered.revision == doc.revision
    assert discovered.document().content_signature() == doc.content_signature()
    raw = json.loads((tmp_path / "recovery.json").read_text(encoding="utf-8"))
    assert raw["format"] == "full-album-maker-step11-recovery"
    assert raw["document"]["format"] == "full-album-maker-project"
    assert raw["source_project_path"].endswith("canonical.json")


def test_corrupt_or_tampered_recovery_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "recovery.json"
    path.write_text("{broken", encoding="utf-8")
    store = IntegrationRecoveryStore(path)
    assert store.discover() is None

    doc = _document(tmp_path)
    envelope = RecoveryEnvelope(
        project_token="p",
        revision=doc.revision,
        signature="0" * 64,
        source_project_path="",
        saved_at_utc="2026-01-01T00:00:00+00:00",
        document_payload=doc.to_dict(),
    )
    path.write_text(json.dumps(envelope.to_dict()), encoding="utf-8")
    assert store.discover() is None
    with pytest.raises(ValueError, match="Signature"):
        store.load_strict()


def test_native_project_save_verifies_normalized_authoritative_state(tmp_path: Path) -> None:
    doc = _next_revision(_document(tmp_path))
    path = tmp_path / "native.json"
    save_project_document(str(path), doc)
    restored = extract_project_document_from_saved_json(path)
    assert restored.content_signature() == doc.content_signature()
    assert verify_persisted_document(path, doc) is True


def test_legacy_envelope_verification_uses_embedded_project_document(tmp_path: Path) -> None:
    doc = _next_revision(_document(tmp_path))
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps({"legacy": True, "album_document_v2": doc.to_dict()}),
        encoding="utf-8",
    )
    restored = extract_project_document_from_saved_json(path)
    assert restored.project_id == doc.project_id
    assert verify_persisted_document(path, doc) is True

    changed = _next_revision(doc)
    assert verify_persisted_document(path, changed) is False
