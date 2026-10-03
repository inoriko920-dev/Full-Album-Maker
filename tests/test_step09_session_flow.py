from __future__ import annotations

from pathlib import Path

from full_album_maker.ai_action_registry_step09 import required_permissions_for_actions
from full_album_maker.ai_agent_core_step09 import (
    AgentActionCall,
    AgentPlan,
    AgentState,
    ProviderInterpretation,
    build_agent_context_snapshot,
    deterministic_plan_id,
)
from full_album_maker.ai_history_step09 import AgentHistoryStore
from full_album_maker.ai_session_step09 import AgentSessionService
from full_album_maker.editor_commands import SetCanvasBackground
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


def _fixture():
    doc = ProjectDocument.new_empty("STEP09 session")
    audio = MediaAsset(
        kind="audio",
        locator="C:/private/song.wav",
        original_name="song.wav",
        source_duration_tick=10 * TIMEBASE,
    )
    video = MediaAsset(
        kind="video",
        locator="C:/private/song.mp4",
        original_name="song.mp4",
        source_duration_tick=6 * TIMEBASE,
    )
    doc.media.extend([audio, video])
    song = SongInstance(
        asset_id=audio.asset_id,
        display_title="Song",
        source_out_tick=10 * TIMEBASE,
    )
    doc.playlist.entries.append(song)
    doc.validate()
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=(song.song_id,),
        allowed_media_ids=(video.asset_id,),
        user_text="pasang visual",
    )
    action = AgentActionCall(
        "set_song_visual",
        {"song_ids": [song.song_id], "asset_id": video.asset_id},
    )
    plan = AgentPlan(
        plan_id=deterministic_plan_id(
            project_id=doc.project_id,
            revision=doc.revision,
            context_fingerprint=context.fingerprint,
            prompt="pasang visual",
            actions=(action,),
        ),
        project_id=doc.project_id,
        expected_revision=doc.revision,
        context_fingerprint=context.fingerprint,
        prompt_summary="pasang visual",
        scope_song_ids=(song.song_id,),
        actions=(action,),
        required_permissions=required_permissions_for_actions((action,)),
        provider="mock",
    )
    plan.validate()
    return doc, context, plan, song.song_id, video.asset_id


def test_complete_flow_preview_then_execute_is_one_revision_and_undo_ai(tmp_path: Path) -> None:
    doc, context, plan, song_id, video_id = _fixture()
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    history = AgentHistoryStore(tmp_path / "history.json")
    service = AgentSessionService(controller, history_store=history)

    assert service.begin_interpretation("pasang visual", context).state == AgentState.INTERPRETING
    assert service.receive_interpretation(
        ProviderInterpretation(message="Rencana siap", plan=plan)
    ).state == AgentState.PLAN_READY
    preview = service.preview()
    assert preview.state == AgentState.PREVIEW_READY
    assert preview.preview is not None and preview.preview.has_changes
    assert controller.snapshot().content_signature() == before

    completed = service.execute()
    assert completed.state == AgentState.COMPLETED
    assert controller.revision == doc.revision + 1
    assert controller.snapshot().song_map()[song_id].visual_asset_id == video_id
    assert service.can_undo_ai is True

    restored = service.undo_ai()
    assert restored.content_signature() == before
    assert service.can_undo_ai is False

    entries = history.load()
    assert [entry.role for entry in entries[:2]] == ["user", "assistant"]
    assert any(entry.status == "PREVIEW_READY" for entry in entries)
    assert any(entry.status == "COMPLETED" for entry in entries)
    assert any(entry.status == "UNDO_AI" for entry in entries)


def test_clarification_then_new_prompt_and_cancel_never_mutates_project() -> None:
    doc, context, _plan, _song_id, _video_id = _fixture()
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    service = AgentSessionService(controller)

    service.begin_interpretation("ubah yang itu", context)
    state = service.receive_interpretation(
        ProviderInterpretation(
            message="Target belum jelas",
            clarification="Lagu mana yang dimaksud?",
        )
    )
    assert state.state == AgentState.NEEDS_CLARIFICATION
    assert "Lagu mana" in state.clarification

    assert service.begin_interpretation("batal saja", context).state == AgentState.INTERPRETING
    assert service.cancel().state == AgentState.CANCELLED
    assert controller.snapshot().content_signature() == before
    assert controller.can_undo is False


def test_manual_edit_after_preview_makes_execute_fail_stale_without_ai_mutation() -> None:
    doc, context, plan, _song_id, _video_id = _fixture()
    controller = EditorController(doc)
    service = AgentSessionService(controller)
    service.begin_interpretation("pasang visual", context)
    service.receive_interpretation(ProviderInterpretation(message="siap", plan=plan))
    assert service.preview().state == AgentState.PREVIEW_READY

    controller.dispatch(SetCanvasBackground("#223344"))
    manual_signature = controller.snapshot().content_signature()
    result = service.execute()
    assert result.state == AgentState.FAILED
    assert "stale" in result.error.casefold() or "revision" in result.error.casefold()
    assert controller.snapshot().content_signature() == manual_signature
    assert controller.snapshot().canvas.background_color == "#223344"


def test_provider_plan_metadata_mismatch_fails_before_preview() -> None:
    doc, context, plan, _song_id, _video_id = _fixture()
    controller = EditorController(doc)
    service = AgentSessionService(controller)
    service.begin_interpretation("pasang visual", context)
    bad = AgentPlan(
        plan_id=plan.plan_id,
        project_id=plan.project_id,
        expected_revision=plan.expected_revision,
        context_fingerprint="0" * 64,
        prompt_summary=plan.prompt_summary,
        scope_song_ids=plan.scope_song_ids,
        actions=plan.actions,
        required_permissions=plan.required_permissions,
        provider=plan.provider,
    )
    result = service.receive_interpretation(ProviderInterpretation(message="siap", plan=bad))
    assert result.state == AgentState.FAILED
    assert controller.snapshot().content_signature() == doc.content_signature()
