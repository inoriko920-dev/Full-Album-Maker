from __future__ import annotations

import pytest

from full_album_maker.home_state import (
    CapabilityState,
    HomeMode,
    HomeViewState,
    PortableStatus,
    ProjectOpenResult,
    QuickDefaults,
    RecentAvailability,
    RecentProject,
    RecoveryCandidate,
    RecoveryValidation,
)


def _recent(name: str, opened: float) -> RecentProject:
    return RecentProject(
        project_id=f"id-{name}",
        path=f"C:/Projects/{name}.json",
        display_name=name,
        last_opened=opened,
        song_count=3,
        duration_seconds=180.0,
        availability=RecentAvailability.AVAILABLE,
    )


def test_step02_home_state_ids_are_stable():
    assert [mode.value for mode in HomeMode] == [
        "HOME_IDLE",
        "HOME_RECOVERY_AVAILABLE",
        "HOME_NO_RECOVERY",
        "HOME_PROJECT_LOADING",
        "HOME_PROJECT_OPEN",
        "HOME_OPEN_ERROR",
        "HOME_FIRST_RUN",
        "HOME_PORTABLE_WARNING",
        "HOME_OUTPUT_INVALID",
    ]


def test_recent_projects_are_sorted_last_opened_descending():
    state = HomeViewState().with_recent([_recent("lama", 10), _recent("baru", 30), _recent("tengah", 20)])
    assert [item.display_name for item in state.recent_projects] == ["baru", "tengah", "lama"]


def test_empty_recent_enters_first_run_without_fake_data():
    state = HomeViewState().with_recent([])
    assert state.mode == HomeMode.FIRST_RUN
    assert state.recent_projects == ()


def test_recovery_banner_requires_valid_candidate_and_dismiss_is_session_only():
    candidate = RecoveryCandidate(
        candidate_id="recovery-1",
        path="C:/Portable/data/autosave.json",
        timestamp=123.0,
        project_identity="project-1",
        validation_state=RecoveryValidation.VALID,
    )
    state = HomeViewState(recent_projects=(_recent("album", 20),)).with_valid_recovery(candidate)
    assert state.mode == HomeMode.RECOVERY_AVAILABLE
    assert state.recovery == candidate

    dismissed = state.dismiss_recovery()
    assert dismissed.mode == HomeMode.NO_RECOVERY
    assert dismissed.recovery is None
    assert dismissed.recovery_dismissed_for_session is True
    # Dismiss only mutates the in-memory view state; candidate/path remain external.
    assert candidate.path.endswith("autosave.json")


def test_invalid_recovery_never_enters_available_state():
    candidate = RecoveryCandidate(
        candidate_id="bad",
        path="C:/Portable/data/autosave.json",
        timestamp=1.0,
        validation_state=RecoveryValidation.INVALID,
    )
    with pytest.raises(ValueError):
        HomeViewState().with_valid_recovery(candidate)


def test_loading_and_open_error_are_explicit_and_safe():
    state = HomeViewState().begin("open_project")
    assert state.mode == HomeMode.PROJECT_LOADING
    assert state.loading_action == "open_project"

    failed = state.project_opened(ProjectOpenResult.failed("PROJECT_CORRUPT", "Proyek tidak dapat dibaca."))
    assert failed.mode == HomeMode.OPEN_ERROR
    assert failed.error_code == "PROJECT_CORRUPT"
    assert failed.loading_action == ""


def test_successful_open_records_context_without_ui_reference():
    result = ProjectOpenResult.ok(
        project_context="Album Uji",
        project_path="C:/Projects/Album Uji.json",
        project_id="project-123",
    )
    state = HomeViewState().begin("open_project").project_opened(result)
    assert state.mode == HomeMode.PROJECT_OPEN
    assert state.current_project_name == "Album Uji"
    assert state.current_project_path.endswith("Album Uji.json")


def test_quick_defaults_are_stable_ids_and_validate_resolution():
    defaults = QuickDefaults(output_folder="C:/Video/Full Album")
    defaults.validate()
    assert defaults.ratio_id == "16:9"
    assert defaults.resolution_id == "1080p"
    assert (defaults.width, defaults.height) == (1920, 1080)

    with pytest.raises(ValueError):
        QuickDefaults(width=1919, height=1080).validate()


def test_output_invalid_has_dedicated_home_mode():
    state = HomeViewState().with_quick_defaults(
        QuickDefaults(output_folder="Z:/read-only"),
        output_valid=False,
    )
    assert state.mode == HomeMode.OUTPUT_INVALID


def test_portable_warning_only_when_capability_really_warns():
    neutral = PortableStatus(
        ffmpeg=CapabilityState.READY,
        manual_offline=CapabilityState.READY,
        ai_config=CapabilityState.OPTIONAL,
    )
    assert neutral.has_warning is False

    warning = PortableStatus(
        ffmpeg=CapabilityState.WARNING,
        manual_offline=CapabilityState.READY,
        ai_config=CapabilityState.OPTIONAL,
    )
    state = HomeViewState().with_capabilities(warning)
    assert warning.has_warning is True
    assert state.mode == HomeMode.PORTABLE_WARNING


def test_debug_snapshot_contains_no_api_key_field():
    snapshot = HomeViewState().as_debug_dict()
    assert "api_key" not in snapshot
    assert "key" not in snapshot
    assert snapshot["ai_config"] == "optional"
