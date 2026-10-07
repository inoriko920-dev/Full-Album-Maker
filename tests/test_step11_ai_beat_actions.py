from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from full_album_maker.ai_action_registry_step09 import (
    Step09ActionError,
    Step09PermissionError,
    Step09TransactionEngine,
    registered_action_names,
    required_permissions_for_actions,
)
from full_album_maker.ai_agent_core_step09 import (
    AgentActionCall,
    AgentPermission,
    AgentPlan,
    PermissionGrant,
    build_agent_context_snapshot,
    deterministic_plan_id,
)
from full_album_maker.ai_workspace_step09 import AIContextDock, AITaskCanvas
from full_album_maker.album_visuals import make_song_cover_layer, make_vinyl_layer
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import (
    Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform,
)
from full_album_maker.music_style_presets import MusicStylePreset
from full_album_maker.spectrum_feature import make_spectrum_layer


def _app():
    return QApplication.instance() or QApplication([])


def _doc():
    doc=ProjectDocument.new_empty("STEP11 AI Beat")
    audio=MediaAsset(
        kind="audio",locator="C:/PRIVATE/song.wav",original_name="song.wav",
        source_duration_tick=4*TIMEBASE,
    )
    image=MediaAsset(
        kind="image",locator="C:/PRIVATE/cover.png",original_name="cover.png",
    )
    doc.media.extend([audio,image])
    song=SongInstance(
        asset_id=audio.asset_id,source_out_tick=4*TIMEBASE,
        display_title="Song",cover_asset_id=image.asset_id,visual_asset_id=image.asset_id,
    )
    doc.playlist.entries.append(song)
    track=doc.tracks[0].track_id
    cover=make_song_cover_layer(track,1,fallback_asset_id=image.asset_id)
    vinyl=make_vinyl_layer(track,2)
    spectrum=make_spectrum_layer(track,3)
    text=Layer(
        track_id=track,type="text",name="Title",order=4,
        transform=Transform(x=.1,y=.1,width=.8,height=.2),
        properties={"text":"Song","font_size":40,"color":"#ffffff"},
    )
    doc.layers.extend([cover,vinyl,spectrum,text])
    doc.validate()
    return doc,cover,vinyl,spectrum,text


def _context(doc, selected=()):
    return build_agent_context_snapshot(
        doc,
        selected_layer_ids=selected,
        enabled_contexts=("beat",),
        user_text="beat",
    )


def _plan(doc,ctx,actions,prompt="beat"):
    actions=tuple(actions)
    plan=AgentPlan(
        plan_id=deterministic_plan_id(
            project_id=doc.project_id,revision=doc.revision,
            context_fingerprint=ctx.fingerprint,prompt=prompt,actions=actions,
        ),
        project_id=doc.project_id,
        expected_revision=doc.revision,
        context_fingerprint=ctx.fingerprint,
        prompt_summary=prompt,
        scope_song_ids=(),
        actions=actions,
        required_permissions=required_permissions_for_actions(actions),
        provider="test",
    )
    plan.validate()
    return plan


def test_beat_permission_exists():
    assert AgentPermission.BEAT_WRITE.value=="beat.write"
    assert "beat.write" in PermissionGrant.all_editor_writes().permissions


def test_registry_contains_five_beat_actions():
    names=set(registered_action_names())
    assert {
        "set_beat_preset","adjust_beat_intensity","clear_beat_animation",
        "apply_music_style","set_vinyl_bpm_sync",
    }.issubset(names)


def test_context_contains_registry_and_is_path_free():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    beat=ctx.payload["beat_context"]
    assert len(beat["preset_catalog"])==18
    assert len(beat["music_styles"])==9
    assert beat["writable_layer_ids"]==[cover.layer_id]
    raw=str(ctx.payload).casefold()
    assert "c:/private" not in raw
    assert "locator" not in raw
    assert "api_key" not in raw


def test_set_beat_preset_dry_run_is_non_destructive():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_preset",{
        "layer_ids":[cover.layer_id],"preset_id":"club_punch","intensity":1.2,
    })
    plan=_plan(doc,ctx,(action,),"pakai Club Punch 120%")
    controller=EditorController(doc)
    before=controller.snapshot().content_signature()
    preview=Step09TransactionEngine(controller).dry_run(
        plan,ctx,PermissionGrant.all_editor_writes()
    )
    assert preview.has_changes
    assert preview.command_count==1
    assert cover.layer_id in preview.impact.changed_layer_ids
    assert controller.snapshot().content_signature()==before


def test_set_beat_preset_incompatible_rotation_text_rejected():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(text.layer_id,))
    action=AgentActionCall("set_beat_preset",{
        "layer_ids":[text.layer_id],"preset_id":"rotation_nudge","intensity":1,
    })
    plan=_plan(doc,ctx,(action,))
    with pytest.raises(Step09ActionError,match="tidak kompatibel"):
        Step09TransactionEngine(EditorController(doc)).dry_run(
            plan,ctx,PermissionGrant.all_editor_writes()
        )


def test_locked_layer_rejected():
    doc,cover,vinyl,spectrum,text=_doc()
    cover.locked=True; doc.validate()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_preset",{
        "layer_ids":[cover.layer_id],"preset_id":"club_punch","intensity":1,
    })
    plan=_plan(doc,ctx,(action,))
    with pytest.raises(Step09ActionError,match="terkunci"):
        Step09TransactionEngine(EditorController(doc)).dry_run(
            plan,ctx,PermissionGrant.all_editor_writes()
        )


def test_adjust_intensity_preserves_multi_preset_and_clamps():
    doc,cover,vinyl,spectrum,text=_doc()
    cover.animation={"beat_v1":{
        "enabled":True,"presets":["strong_punch","bass_pulse"],"intensity":1.9,
    }}
    doc.validate()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("adjust_beat_intensity",{
        "layer_ids":[cover.layer_id],"delta":.25,
    })
    plan=_plan(doc,ctx,(action,))
    controller=EditorController(doc)
    engine=Step09TransactionEngine(controller)
    engine.execute(plan,ctx,PermissionGrant.all_editor_writes())
    payload=controller.snapshot().layer_map()[cover.layer_id].animation["beat_v1"]
    assert payload["presets"]==["strong_punch","bass_pulse"]
    assert payload["intensity"]==2.0


def test_adjust_without_assignment_rejected():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("adjust_beat_intensity",{
        "layer_ids":[cover.layer_id],"delta":.25,
    })
    plan=_plan(doc,ctx,(action,))
    with pytest.raises(Step09ActionError,match="sudah aktif"):
        Step09TransactionEngine(EditorController(doc)).dry_run(
            plan,ctx,PermissionGrant.all_editor_writes()
        )


def test_clear_beat_leaves_vinyl_bpm_sync_unchanged():
    doc,cover,vinyl,spectrum,text=_doc()
    vinyl.animation={"beat_v1":{"enabled":True,"presets":["bass_pulse"],"intensity":1}}
    vinyl.properties["bpm_sync"]=True
    doc.validate()
    ctx=_context(doc,(vinyl.layer_id,))
    action=AgentActionCall("clear_beat_animation",{"layer_ids":[vinyl.layer_id]})
    plan=_plan(doc,ctx,(action,))
    controller=EditorController(doc)
    Step09TransactionEngine(controller).execute(plan,ctx,PermissionGrant.all_editor_writes())
    changed=controller.snapshot().layer_map()[vinyl.layer_id]
    assert "beat_v1" not in changed.animation
    assert changed.properties["bpm_sync"] is True


def test_apply_music_style_is_one_domain_command_and_one_undo():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc)
    action=AgentActionCall("apply_music_style",{"style_id":MusicStylePreset.EDM.value})
    plan=_plan(doc,ctx,(action,),"buat gaya EDM")
    controller=EditorController(doc)
    before=controller.snapshot().content_signature()
    engine=Step09TransactionEngine(controller)
    preview=engine.dry_run(plan,ctx,PermissionGrant.all_editor_writes())
    assert preview.command_count==1
    record=engine.execute(plan,ctx,PermissionGrant.all_editor_writes())
    assert record.result_revision==doc.revision+1
    changed=controller.snapshot()
    assert changed.layer_map()[cover.layer_id].animation["beat_v1"]["presets"]==["club_punch"]
    restored=engine.undo_ai()
    assert restored.content_signature()==before


def test_set_vinyl_bpm_sync_validates_type_and_bpr():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(vinyl.layer_id,))
    action=AgentActionCall("set_vinyl_bpm_sync",{
        "layer_ids":[vinyl.layer_id],"enabled":True,"beats_per_rotation":2,
    })
    plan=_plan(doc,ctx,(action,))
    controller=EditorController(doc)
    Step09TransactionEngine(controller).execute(plan,ctx,PermissionGrant.all_editor_writes())
    props=controller.snapshot().layer_map()[vinyl.layer_id].properties
    assert props["bpm_sync"] is True
    assert props["beats_per_rotation"]==2.0

    ctx2=_context(doc,(cover.layer_id,))
    bad=AgentActionCall("set_vinyl_bpm_sync",{
        "layer_ids":[cover.layer_id],"enabled":True,"beats_per_rotation":4,
    })
    with pytest.raises(Step09ActionError,match="Vinyl"):
        Step09TransactionEngine(EditorController(doc)).dry_run(
            _plan(doc,ctx2,(bad,)),ctx2,PermissionGrant.all_editor_writes()
        )

    invalid=AgentActionCall("set_vinyl_bpm_sync",{
        "layer_ids":[vinyl.layer_id],"enabled":True,"beats_per_rotation":3,
    })
    with pytest.raises(Step09ActionError,match="1, 2, 4, atau 8"):
        Step09TransactionEngine(EditorController(doc)).dry_run(
            _plan(doc,ctx,(invalid,)),ctx,PermissionGrant.all_editor_writes()
        )


def test_beat_plan_denied_without_beat_permission():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_preset",{
        "layer_ids":[cover.layer_id],"preset_id":"strong_punch","intensity":1,
    })
    plan=_plan(doc,ctx,(action,))
    grant=PermissionGrant(frozenset({AgentPermission.VISUAL_WRITE.value}))
    with pytest.raises(Step09PermissionError,match="Permission pengguna"):
        Step09TransactionEngine(EditorController(doc)).dry_run(plan,ctx,grant)


def test_execute_multi_beat_actions_is_one_revision_and_duplicate_safe():
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    actions=(
        AgentActionCall("set_beat_preset",{
            "layer_ids":[cover.layer_id],"preset_id":"club_punch","intensity":1,
        }),
        AgentActionCall("adjust_beat_intensity",{
            "layer_ids":[cover.layer_id],"delta":.25,
        }),
    )
    plan=_plan(doc,ctx,actions,"club punch lalu lebih kuat")
    controller=EditorController(doc)
    engine=Step09TransactionEngine(controller)
    record=engine.execute(plan,ctx,PermissionGrant.all_editor_writes())
    assert record.result_revision==doc.revision+1
    assert controller.snapshot().layer_map()[cover.layer_id].animation["beat_v1"]["intensity"]==1.25
    duplicate=engine.execute(plan,ctx,PermissionGrant.all_editor_writes())
    assert duplicate.duplicate
    assert controller.revision==doc.revision+1


def test_context_dock_has_beat_permission_checkbox():
    _app()
    dock=AIContextDock()
    assert AgentPermission.BEAT_WRITE.value in dock.permissions
    assert dock.permissions[AgentPermission.BEAT_WRITE.value].isChecked()


def test_task_canvas_renders_human_readable_beat_plan_card():
    _app()
    doc,cover,vinyl,spectrum,text=_doc()
    ctx=_context(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_preset",{
        "layer_ids":[cover.layer_id],"preset_id":"club_punch","intensity":1.2,
    })
    plan=_plan(doc,ctx,(action,),"Club Punch 120%")
    canvas=AITaskCanvas()
    canvas._render_plan(plan)
    labels=[w.text() for w in canvas.plan_host.findChildren(QLabel)]
    assert "Beat Preset" in labels
    assert any("Club Punch" in value and "120%" in value for value in labels)
    assert "beat.write" in canvas.scope_text.text()
