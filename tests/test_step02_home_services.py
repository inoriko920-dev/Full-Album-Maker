from __future__ import annotations

from pathlib import Path

from full_album_maker.home_services import (
    HomeProjectService,
    QuickDefaultsStore,
    RecentProjectsService,
    RecoveryService,
)
from full_album_maker.home_state import QuickDefaults, RecentAvailability, RecoveryValidation
from full_album_maker.project import MediaItem, Project


def test_create_then_open_real_project_file(tmp_path: Path):
    target = tmp_path / "Album Uji.json"
    defaults = QuickDefaults(width=1280, height=720, resolution_id="720p", output_folder=str(tmp_path / "out"))

    created, project = HomeProjectService.create(target, defaults)
    assert created.success is True
    assert project is not None
    assert target.exists()
    assert project.settings.width == 1280
    assert project.settings.height == 720

    opened, loaded = HomeProjectService.open(target)
    assert opened.success is True
    assert loaded is not None
    assert loaded.settings.width == 1280
    assert opened.project_id == created.project_id


def test_open_missing_and_corrupt_project_fail_without_mutation(tmp_path: Path):
    missing, project = HomeProjectService.open(tmp_path / "missing.json")
    assert missing.success is False
    assert missing.error_code == "PROJECT_NOT_FOUND"
    assert project is None

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    result, project = HomeProjectService.open(broken)
    assert result.success is False
    assert result.error_code == "PROJECT_CORRUPT"
    assert project is None


def test_recent_index_is_persistent_sorted_and_missing_safe(tmp_path: Path):
    index = tmp_path / "recent.json"
    service = RecentProjectsService(index)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_path.write_text("{}", encoding="utf-8")
    second_path.write_text("{}", encoding="utf-8")

    p1 = Project(audios=[MediaItem(path="a.mp3", duration=10.0)])
    p2 = Project(audios=[MediaItem(path="b.mp3", duration=20.0), MediaItem(path="c.mp3", duration=30.0)])
    first = service.touch(first_path, p1, opened_at=10.0)
    second = service.touch(second_path, p2, opened_at=20.0)

    loaded = service.load()
    assert [item.project_id for item in loaded] == [second.project_id, first.project_id]
    assert loaded[0].song_count == 2
    assert loaded[0].duration_seconds == 50.0

    second_path.unlink()
    loaded = service.load()
    assert loaded[0].availability == RecentAvailability.MISSING
    service.remove(second.project_id)
    assert [item.project_id for item in service.load()] == [first.project_id]


def test_quick_defaults_store_roundtrip_and_writable_validation(tmp_path: Path):
    store = QuickDefaultsStore(tmp_path / "defaults.json")
    out = tmp_path / "Folder Dengan Spasi"
    out.mkdir()
    value = QuickDefaults(ratio_id="16:9", resolution_id="1080p", width=1920, height=1080, output_folder=str(out))
    store.save(value)
    assert store.load() == value
    assert store.output_is_writable(value) is True

    invalid = QuickDefaults(output_folder="")
    assert store.output_is_writable(invalid) is False


def test_recovery_snapshot_validates_restores_and_dismiss_does_not_delete(tmp_path: Path):
    snapshot = tmp_path / "recovery" / "home_autosave.json"
    service = RecoveryService(snapshot)
    project = Project(audios=[MediaItem(path="missing-but-allowed-at-load.mp3", duration=42.0)])

    candidate = service.write_snapshot(project)
    assert candidate.validation_state == RecoveryValidation.VALID
    assert snapshot.exists()

    discovered = service.discover()
    assert discovered is not None
    assert discovered.validation_state == RecoveryValidation.VALID

    result, restored = service.restore(discovered)
    assert result.success is True
    assert restored is not None
    assert restored.total_audio_duration == 42.0
    assert snapshot.exists()


def test_invalid_recovery_is_preserved_and_not_restored(tmp_path: Path):
    snapshot = tmp_path / "recovery" / "home_autosave.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("not-json", encoding="utf-8")
    service = RecoveryService(snapshot)

    candidate = service.discover()
    assert candidate is not None
    assert candidate.validation_state == RecoveryValidation.INVALID
    result, restored = service.restore(candidate)
    assert result.success is False
    assert result.error_code == "RECOVERY_INVALID"
    assert restored is None
    assert snapshot.exists()
