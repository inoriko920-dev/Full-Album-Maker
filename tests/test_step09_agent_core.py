from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.ai_action_registry_step09 import (
    ACTION_SPECS,
    Step09ActionError,
    Step09PermissionError,
    Step09StalePlan,
    Step09TransactionEngine,
    registered_action_names,
    required_permissions_for_actions,
)
from full_album_maker.ai_agent_core_step09 import (
    AgentActionCall,
    AgentPermission,
    AgentPlan,
    AgentState,
    AgentStateMachine,
    PermissionGrant,
    build_agent_context_snapshot,
    deterministic_plan_id,
)
from full_album_maker.editor_commands import SetCanvasBackground
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import (
    Layer,
    MediaAsset,
    ProjectDocument,
    SongInstance,
    TimeBinding,
    TIMEBASE,
)
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.visual_precision import visual_settings_for_song


def _document(tmp_path: Path, *, songs: int = 3) -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP09 Agent Core")
    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    for index in range(songs):
        audio = MediaAsset(
            kind="audio",
            locator=f"C:/RAHASIA/audio-{index:02d}.wav",
            original_name=f"song-{index:02d}.wav",
            source_duration_tick=15 * TIMEBASE,
        )
        video = MediaAsset(
            kind="video",
            locator=f"C:/RAHASIA/video-{index:02d}.mp4",
            original_name=f"song-{index:02d}.mp4",
            source_duration_tick=8 * TIMEBASE,
        )
        doc.media.extend([audio, video])
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index + 1:02d}",
                display_artist="Perjalanan Kita",
                source_out_tick=15 * TIMEBASE,
            )
        )
    doc.layers.append(
        Layer(
            track_id=visual_track.track_id,
            type="text",
            name="Judul Utama",
            order=0,
            time_binding=TimeBinding(kind="album"),
            properties={"text": "Album", "font_size": 48, "color": "#ffffff"},
        )
    )
    doc.layers.append(make_spectrum_layer(visual_track.track_id, 1, preset_id="minimal_bars"))
    doc.validate()
    return doc


def _video_ids(doc: ProjectDocument) -> tuple[str, ...]:
    return tuple(asset.asset_id for asset in doc.media if asset.kind == "video")


def _song_ids(doc: ProjectDocument) -> tuple[str, ...]:
    return tuple(song.song_id for song in doc.playlist.entries)


def _plan(
    doc: ProjectDocument,
    context,
    actions: tuple[AgentActionCall, ...],
    *,
    prompt: str = "kerjakan",
    scope: tuple[str, ...] | None = None,
    permissions: tuple[str, ...] | None = None,
) -> AgentPlan:
    scope_ids = scope if scope is not None else context.selected_song_ids
    required = permissions if permissions is not None else required_permissions_for_actions(actions)
    plan_id = deterministic_plan_id(
        project_id=doc.project_id,
        revision=doc.revision,
        context_fingerprint=context.fingerprint,
        prompt=prompt,
        actions=actions,
    )
    plan = AgentPlan(
        plan_id=plan_id,
        project_id=doc.project_id,
        expected_revision=doc.revision,
        context_fingerprint=context.fingerprint,
        prompt_summary=" ".join(prompt.split())[:500],
        scope_song_ids=tuple(scope_ids),
        actions=actions,
        required_permissions=tuple(required),
        provider="mock",
    )
    plan.validate()
    return plan


def test_state_machine_allows_only_explicit_transitions() -> None:
    machine = AgentStateMachine()
    assert machine.state == AgentState.IDLE
    machine.transition(AgentState.INTERPRETING)
    machine.transition(AgentState.PLAN_READY)
    machine.transition(AgentState.PREVIEW_READY)
    machine.transition(AgentState.EXECUTING)
    machine.transition(AgentState.COMPLETED)
    machine.transition(AgentState.IDLE)
    with pytest.raises(ValueError, match="Transisi state AI tidak valid"):
        machine.transition(AgentState.EXECUTING)


def test_context_is_bounded_path_free_and_permission_scoped(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=4)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    selected_layer = doc.layers[1].layer_id
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs[:2],
        selected_layer_ids=(selected_layer,),
        allowed_media_ids=videos[:2],
        enabled_contexts=("media", "timeline", "spectrum"),
        user_text="pilih lagu dan video",
    )
    raw = str(context.payload).casefold()
    assert "rahasia" not in raw
    assert "locator" not in raw
    assert "api_key" not in raw
    assert context.selected_song_ids == songs[:2]
    assert context.selected_layer_ids == (selected_layer,)
    assert context.allowed_media_ids == videos[:2]
    assert {item["asset_id"] for item in context.payload["media_candidates"]} == set(videos[:2])

    changed = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs[1:3],
        selected_layer_ids=(selected_layer,),
        allowed_media_ids=videos[:2],
        enabled_contexts=("media", "timeline", "spectrum"),
        user_text="pilih lagu dan video",
    )
    assert changed.fingerprint != context.fingerprint


def test_registry_is_fail_closed_and_excludes_side_effect_actions() -> None:
    names = set(registered_action_names())
    assert "set_song_visual" in names
    assert "set_song_video_speed" in names
    assert "auto_arrange_timeline" in names
    assert "apply_template" in names
    assert "set_spectrum_preset" in names
    for forbidden in (
        "render_project",
        "save_template",
        "set_slowmo",
        "remove_video",
        "run_shell",
        "write_file",
    ):
        assert forbidden not in names
        assert forbidden not in ACTION_SPECS
    with pytest.raises(Step09ActionError, match="registry STEP09"):
        required_permissions_for_actions((AgentActionCall("render_project", {}),))


def test_dry_run_is_non_destructive_and_reports_real_impact(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs,
        allowed_media_ids=videos,
        user_text="pasang video lalu slowmo",
    )
    actions = (
        AgentActionCall("set_song_visual", {"song_ids": [songs[0]], "asset_id": videos[0]}),
        AgentActionCall("set_song_video_speed", {"song_ids": [songs[0]], "speed": 0.5}),
    )
    plan = _plan(doc, context, actions, prompt="pasang video lalu slowmo")
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    engine = Step09TransactionEngine(controller)

    preview = engine.dry_run(plan, context, PermissionGrant.all_editor_writes())

    assert preview.has_changes is True
    assert preview.command_count == 2
    assert songs[0] in preview.impact.changed_song_ids
    assert preview.impact.extensions_changed is True
    assert controller.snapshot().content_signature() == before
    assert controller.revision == doc.revision
    assert controller.can_undo is False


def test_permission_underdeclare_or_missing_grant_fails_before_mutation(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs,
        allowed_media_ids=videos,
    )
    actions = (
        AgentActionCall("set_song_visual", {"song_ids": [songs[0]], "asset_id": videos[0]}),
        AgentActionCall("auto_arrange_timeline", {}),
    )
    controller = EditorController(doc)
    engine = Step09TransactionEngine(controller)
    before = controller.snapshot().content_signature()

    underdeclared = _plan(
        doc,
        context,
        actions,
        permissions=(AgentPermission.VISUAL_WRITE.value,),
    )
    with pytest.raises(Step09PermissionError, match="mendeklarasikan"):
        engine.dry_run(underdeclared, context, PermissionGrant.all_editor_writes())
    assert controller.snapshot().content_signature() == before

    correct = _plan(doc, context, actions)
    visual_only = PermissionGrant(frozenset({AgentPermission.VISUAL_WRITE.value}))
    with pytest.raises(Step09PermissionError, match="Permission pengguna"):
        engine.dry_run(correct, context, visual_only)
    assert controller.snapshot().content_signature() == before


def test_scope_and_media_boundary_are_enforced(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=3)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=(songs[0],),
        allowed_media_ids=(videos[0],),
    )
    controller = EditorController(doc)
    engine = Step09TransactionEngine(controller)

    outside_song = (AgentActionCall(
        "set_song_visual",
        {"song_ids": [songs[1]], "asset_id": videos[0]},
    ),)
    plan = _plan(doc, context, outside_song, scope=(songs[0],))
    with pytest.raises(Step09PermissionError, match="scope/context"):
        engine.dry_run(plan, context, PermissionGrant.all_editor_writes())

    outside_media = (AgentActionCall(
        "set_song_visual",
        {"song_ids": [songs[0]], "asset_id": videos[1]},
    ),)
    plan = _plan(doc, context, outside_media, scope=(songs[0],))
    with pytest.raises(Step09PermissionError, match="media"):
        engine.dry_run(plan, context, PermissionGrant.all_editor_writes())


def test_execute_multi_action_is_one_revision_one_undo_and_idempotent(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=4)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs,
        allowed_media_ids=videos,
    )
    actions = tuple(
        AgentActionCall("set_song_visual", {"song_ids": [song_id], "asset_id": asset_id})
        for song_id, asset_id in zip(songs, videos)
    ) + (
        AgentActionCall("set_song_video_speed", {"song_ids": list(songs), "speed": 0.5}),
        AgentActionCall("auto_arrange_timeline", {}),
    )
    plan = _plan(doc, context, actions, prompt="visual slowmo lalu susun")
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    engine = Step09TransactionEngine(controller)

    record = engine.execute(plan, context, PermissionGrant.all_editor_writes())
    changed = controller.snapshot()
    assert record.duplicate is False
    assert changed.revision == doc.revision + 1
    assert controller.can_undo is True
    assert all(song.visual_asset_id for song in changed.playlist.entries)
    assert all(
        visual_settings_for_song(changed, song_id)["video_speed"] == pytest.approx(0.5)
        for song_id in songs
    )
    assert any(layer.origin == "auto" for layer in changed.layers)

    duplicate = engine.execute(plan, context, PermissionGrant.all_editor_writes())
    assert duplicate.duplicate is True
    assert controller.revision == changed.revision

    restored = engine.undo_ai()
    assert restored.content_signature() == before
    assert engine.can_undo_ai() is False


def test_undo_ai_refuses_to_jump_over_manual_edit(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=(songs[0],),
        allowed_media_ids=(videos[0],),
    )
    actions = (
        AgentActionCall("set_song_visual", {"song_ids": [songs[0]], "asset_id": videos[0]}),
    )
    plan = _plan(doc, context, actions)
    controller = EditorController(doc)
    engine = Step09TransactionEngine(controller)
    engine.execute(plan, context, PermissionGrant.all_editor_writes())
    assert engine.can_undo_ai() is True

    controller.dispatch(SetCanvasBackground("#112233"))
    assert engine.can_undo_ai() is False
    with pytest.raises(Step09ActionError, match="bukan lagi edit terakhir"):
        engine.undo_ai()
    assert controller.snapshot().canvas.background_color == "#112233"


def test_stale_revision_and_context_fingerprint_fail_closed(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=2)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=(songs[0],),
        allowed_media_ids=(videos[0],),
    )
    actions = (
        AgentActionCall("set_song_visual", {"song_ids": [songs[0]], "asset_id": videos[0]}),
    )
    plan = _plan(doc, context, actions)
    controller = EditorController(doc)
    engine = Step09TransactionEngine(controller)
    before = controller.snapshot().content_signature()

    controller.dispatch(SetCanvasBackground("#223344"))
    with pytest.raises(Step09StalePlan, match="revision"):
        engine.dry_run(plan, context, PermissionGrant.all_editor_writes())
    assert controller.snapshot().canvas.background_color == "#223344"

    controller = EditorController(doc)
    engine = Step09TransactionEngine(controller)
    altered = build_agent_context_snapshot(
        doc,
        selected_song_ids=(songs[1],),
        allowed_media_ids=(videos[0],),
    )
    with pytest.raises(Step09StalePlan, match="fingerprint"):
        engine.dry_run(plan, altered, PermissionGrant.all_editor_writes())
    assert controller.snapshot().content_signature() == before


def test_golden_shape_twenty_songs_can_dry_run_without_mutation(tmp_path: Path) -> None:
    doc = _document(tmp_path, songs=20)
    songs = _song_ids(doc)
    videos = _video_ids(doc)
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=songs,
        allowed_media_ids=videos,
        enabled_contexts=("media", "timeline"),
        user_text="Pilih 20 lagu, beri visual yang cocok, slowmo footage 0,5x, lalu susun timeline.",
    )
    actions = tuple(
        AgentActionCall("set_song_visual", {"song_ids": [song_id], "asset_id": asset_id})
        for song_id, asset_id in zip(songs, videos)
    ) + (
        AgentActionCall("set_song_video_speed", {"song_ids": list(songs), "speed": 0.5}),
        AgentActionCall("auto_arrange_timeline", {}),
    )
    plan = _plan(
        doc,
        context,
        actions,
        prompt="Pilih 20 lagu, beri visual yang cocok, slowmo footage 0,5x, lalu susun timeline.",
        scope=songs,
    )
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    preview = Step09TransactionEngine(controller).dry_run(
        plan,
        context,
        PermissionGrant.all_editor_writes(),
    )
    assert preview.has_changes is True
    assert preview.command_count == 22
    assert controller.snapshot().content_signature() == before
    assert controller.can_undo is False
