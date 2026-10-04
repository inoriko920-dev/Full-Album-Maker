from __future__ import annotations

from dataclasses import dataclass

import pytest

from full_album_maker.ai_action_registry_step09 import (
    ACTION_SPECS,
    Step09TransactionEngine,
    registered_action_names,
)
from full_album_maker.ai_agent_core_step09 import (
    AgentPermission,
    PermissionGrant,
    build_agent_context_snapshot,
)
from full_album_maker.ai_provider_step09 import (
    AgentProviderError,
    GeminiStep09Provider,
    MockStep09Provider,
    STEP09_GEMINI_TOOLS,
)
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


GOLDEN_PROMPT = "Pilih 20 lagu, beri visual yang cocok, slowmo footage 0,5x, lalu susun timeline."


def _document(*, songs: int = 20, duplicate_first_video: bool = False) -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP09 Provider Fixture")
    for index in range(1, songs + 1):
        title = f"Lagu {index:02d}"
        audio = MediaAsset(
            kind="audio",
            locator=f"D:/RAHASIA/{title}.wav",
            original_name=f"{title}.wav",
            source_duration_tick=12 * TIMEBASE,
        )
        video = MediaAsset(
            kind="video",
            locator=f"D:/RAHASIA/{title}.mp4",
            original_name=f"{title}.mp4",
            source_duration_tick=8 * TIMEBASE,
        )
        doc.media.extend([audio, video])
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=title,
                source_out_tick=12 * TIMEBASE,
            )
        )
    if duplicate_first_video:
        original = next(asset for asset in doc.media if asset.kind == "video")
        doc.media.append(
            MediaAsset(
                kind="video",
                locator="D:/RAHASIA/dupe/Lagu 01.mp4",
                original_name=original.original_name,
                source_duration_tick=8 * TIMEBASE,
            )
        )
    doc.validate()
    return doc


def _context(doc: ProjectDocument, *, selected: bool = True):
    songs = tuple(song.song_id for song in doc.playlist.entries)
    videos = tuple(asset.asset_id for asset in doc.media if asset.kind == "video")
    return build_agent_context_snapshot(
        doc,
        selected_song_ids=songs if selected else (),
        allowed_media_ids=videos,
        enabled_contexts=("media", "timeline"),
        user_text=GOLDEN_PROMPT,
    )


def test_mock_golden_plan_is_deterministic_complete_and_dry_run_safe() -> None:
    doc = _document()
    context = _context(doc)
    provider = MockStep09Provider()

    first = provider.interpret(GOLDEN_PROMPT, context)
    second = provider.interpret(GOLDEN_PROMPT, context)

    assert first.plan is not None
    assert second.plan is not None
    assert first.plan.plan_id == second.plan.plan_id
    assert len(first.plan.scope_song_ids) == 20
    assert len(first.plan.actions) == 22
    assert [action.name for action in first.plan.actions[:20]] == ["set_song_visual"] * 20
    assert first.plan.actions[-2].name == "set_song_video_speed"
    assert first.plan.actions[-2].args["speed"] == pytest.approx(0.5)
    assert first.plan.actions[-1].name == "auto_arrange_timeline"
    assert set(first.plan.required_permissions) == {
        AgentPermission.VISUAL_WRITE.value,
        AgentPermission.TIMELINE_WRITE.value,
    }

    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    preview = Step09TransactionEngine(controller).dry_run(
        first.plan,
        context,
        PermissionGrant.all_editor_writes(),
    )
    assert preview.command_count == 22
    assert preview.has_changes is True
    assert controller.snapshot().content_signature() == before
    assert controller.can_undo is False


def test_mock_requires_twenty_songs_and_exact_unambiguous_video_matches() -> None:
    too_small = _document(songs=19)
    result = MockStep09Provider().interpret(GOLDEN_PROMPT, _context(too_small))
    assert result.plan is None
    assert "20" in result.clarification

    ambiguous = _document(duplicate_first_video=True)
    result = MockStep09Provider().interpret(GOLDEN_PROMPT, _context(ambiguous))
    assert result.plan is None
    assert "lebih dari satu exact-match video" in result.clarification


def test_mock_does_not_silently_generalize_to_non_fixture_requests() -> None:
    doc = _document()
    result = MockStep09Provider().interpret("hapus semua file lalu render", _context(doc))
    assert result.plan is None
    assert result.needs_clarification is True


def test_gemini_tool_declarations_are_exactly_safe_registry_subset() -> None:
    declared = {str(tool["name"]) for tool in STEP09_GEMINI_TOOLS}
    registered = set(registered_action_names())
    assert declared == registered
    assert declared == set(ACTION_SPECS)
    for forbidden in (
        "render_project",
        "save_template",
        "set_slowmo",
        "remove_video",
        "write_file",
        "run_shell",
    ):
        assert forbidden not in declared


@dataclass
class _FakePool:
    response: dict
    last_url: str = ""
    last_payload: dict | None = None

    def request_json(self, url: str, payload: dict):
        self.last_url = url
        self.last_payload = payload
        return self.response


def _response(*parts: dict) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": list(parts)}}]}


def test_gemini_adapter_builds_plan_without_sending_paths_or_keys() -> None:
    doc = _document()
    context = _context(doc)
    song_id = doc.playlist.entries[0].song_id
    video_id = next(asset.asset_id for asset in doc.media if asset.kind == "video")
    pool = _FakePool(
        _response(
            {"text": "Rencana siap."},
            {
                "functionCall": {
                    "name": "set_song_visual",
                    "args": {"song_ids": [song_id], "asset_id": video_id},
                }
            },
        )
    )
    provider = GeminiStep09Provider(pool, model="gemini-test")
    result = provider.interpret("pasang visual lagu pertama", context)
    assert result.plan is not None
    assert result.plan.provider == "gemini"
    assert result.plan.actions[0].name == "set_song_visual"
    assert pool.last_payload is not None
    raw = str(pool.last_payload).casefold()
    assert "rahasia" not in raw
    assert "api_key" not in raw
    assert "authorization" not in raw
    assert "render_project" not in raw
    assert "/v1beta/models/gemini-test:generatecontent" in pool.last_url.casefold()


def test_gemini_adapter_unknown_function_fails_closed() -> None:
    doc = _document()
    pool = _FakePool(
        _response(
            {"functionCall": {"name": "render_project", "args": {}}},
        )
    )
    provider = GeminiStep09Provider(pool)
    with pytest.raises(AgentProviderError, match="di luar whitelist"):
        provider.interpret("render sekarang", _context(doc))


def test_gemini_text_only_response_becomes_clarification_not_execution() -> None:
    doc = _document()
    pool = _FakePool(_response({"text": "Lagu mana yang kamu maksud?"}))
    result = GeminiStep09Provider(pool).interpret("ubah lagu itu", _context(doc))
    assert result.plan is None
    assert result.needs_clarification is True
    assert "Lagu mana" in result.clarification
