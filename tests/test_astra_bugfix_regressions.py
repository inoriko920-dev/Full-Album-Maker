from __future__ import annotations

import inspect
from pathlib import Path
import tomllib

import pytest

import full_album_maker
from full_album_maker.editor_models import ProjectDocument
from full_album_maker.integration_lifecycle_step11 import (
    extract_project_document_from_saved_json,
    save_verified_legacy_project,
)
from full_album_maker import release_smoke, v14_window


class _LegacyEnvelope:
    def __init__(self, document: ProjectDocument) -> None:
        self.document = document

    def to_dict(self) -> dict:
        return {
            "name": "compatibility-envelope",
            "album_document_v2": self.document.to_dict(),
        }


def _document() -> ProjectDocument:
    document = ProjectDocument.new_empty("ASTRA regression")
    document.validate()
    return document


def test_failed_semantic_verification_preserves_previous_project_bytes(tmp_path: Path) -> None:
    target = tmp_path / "project.json"
    previous = b'{"known":"good"}\n'
    target.write_bytes(previous)
    document = _document()

    with pytest.raises(ValueError, match="authoritative"):
        save_verified_legacy_project(
            target,
            _LegacyEnvelope(document),
            document,
            verifier=lambda _path, _expected: False,
        )

    assert target.read_bytes() == previous
    assert list(tmp_path.glob(".*.stage.json")) == []


def test_verified_staged_save_replaces_target_atomically(tmp_path: Path) -> None:
    target = tmp_path / "project.json"
    target.write_bytes(b"OLD")
    document = _document()

    saved = save_verified_legacy_project(target, _LegacyEnvelope(document), document)

    assert Path(saved) == target
    assert target.read_bytes() != b"OLD"
    restored = extract_project_document_from_saved_json(target)
    assert restored.content_signature() == document.content_signature()


def test_save_to_new_path_leaves_no_orphan_stage_file(tmp_path: Path) -> None:
    document = _document()
    target = tmp_path / "new-project"

    saved = Path(save_verified_legacy_project(target, _LegacyEnvelope(document), document))

    assert saved == tmp_path / "new-project.json"
    assert saved.is_file()
    assert list(tmp_path.glob(".*.stage.json")) == []


def test_release_smoke_uses_production_window_factory() -> None:
    normal_source = inspect.getsource(v14_window.run)
    smoke_source = inspect.getsource(release_smoke.run_portable_smoke)
    assert "create_main_window()" in normal_source
    assert "create_main_window()" in smoke_source
    assert "V14EditorMainWindow()" not in smoke_source


def test_version_metadata_is_single_source_or_equal() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == full_album_maker.__version__


def test_release_version_is_newer_than_preserved_v1_4_1_lineage() -> None:
    actual = tuple(int(part) for part in full_album_maker.__version__.split("."))
    assert actual > (1, 4, 1)
