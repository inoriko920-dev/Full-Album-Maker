from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from full_album_maker.advanced_motion_contract import AdvancedMotionPreset
from full_album_maker.ai_action_registry_step09 import (
    Step09ActionError, Step09PermissionError, Step09TransactionEngine,
    required_permissions_for_actions,
)
from full_album_maker.ai_agent_core_step09 import (
    AgentActionCall, AgentPermission, AgentPlan, PermissionGrant,
    build_agent_context_snapshot, deterministic_plan_id,
)
from full_album_maker.ai_beat_nlu_step11 import interpret_beat_prompt
from full_album_maker.album_visuals import make_song_cover_layer
from full_album_maker.beat_animation_assignment import assignment_for_layer
from full_album_maker.beat_combo_catalog import (
    BEAT_COMBO_CATALOG, combo_definition, combo_supported_for_layer,
    matching_combo_id, supported_combos_for_layer,
)
from full_album_maker.beat_render_preflight import estimate_command_load
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform
from full_album_maker.ffmpeg_command_batch import CommandBatchWriter, CommandLimitError
from full_album_maker.property_inspector import PropertyInspector


def _app():
    return QApplication.instance() or QApplication([])


def _doc():
    doc=ProjectDocument.new_empty("STEP13")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=4*TIMEBASE)
    image=MediaAsset(kind="image",locator="cover.png",original_name="cover.png")
    doc.media.extend([audio,image])
    doc.playlist.entries.append(SongInstance(
        asset_id=audio.asset_id,source_out_tick=4*TIMEBASE,display_title="Song",
        cover_asset_id=image.asset_id,
    ))
    cover=make_song_cover_layer(doc.tracks[0].track_id,1,fallback_asset_id=image.asset_id)
    cover.animation={"beat_v1":{
        "enabled":True,"presets":["strong_punch"],"intensity":1.0,
        "motion_preset":"camera_shake","motion_intensity":.8,
    }}
    text=Layer(
        track_id=doc.tracks[0].track_id,type="text",name="Text",order=2,
        transform=Transform(x=.1,y=.1,width=.8,height=.2),
        properties={"text":"Title","font_size":40,"color":"#ffffff"},
        animation={"beat_v1":{"enabled":True,"presets":["beat_zoom"],"intensity":.8}},
    )
    doc.layers.extend([cover,text]); doc.validate()
    return doc,cover,text


def _ctx(doc,selected):
    return build_agent_context_snapshot(
        doc,selected_layer_ids=selected,enabled_contexts=("beat",),user_text="motion"
    )


def _plan(doc,ctx,actions,prompt="motion"):
    actions=tuple(actions)
    plan=AgentPlan(
        plan_id=deterministic_plan_id(
            project_id=doc.project_id,revision=doc.revision,
            context_fingerprint=ctx.fingerprint,prompt=prompt,actions=actions,
        ),
        project_id=doc.project_id,expected_revision=doc.revision,
        context_fingerprint=ctx.fingerprint,prompt_summary=prompt,
        scope_song_ids=(),actions=actions,
        required_permissions=required_permissions_for_actions(actions),provider="test",
    )
    plan.validate(); return plan


def test_combo_catalog_has_eight_unique_valid_recipes():
    assert len(BEAT_COMBO_CATALOG)==8
    assert len(set(BEAT_COMBO_CATALOG))==8
    for key,value in BEAT_COMBO_CATALOG.items():
        assert key==value.combo_id
        assert 0<=value.visual_intensity<=2
        assert 0<=value.motion_intensity<=2
        assert value.payload()["presets"]==[value.visual_preset.value]
        assert value.payload()["motion_preset"]==value.motion_preset.value


def test_combo_capability_filters_text_and_allows_clean_bounce():
    doc,cover,text=_doc()
    values={c.combo_id for c in supported_combos_for_layer(text)}
    assert "clean_bounce" in values
    assert "club_impact" not in values
    assert "cinematic_spark" not in values
    assert combo_supported_for_layer(cover,"club_impact")


def test_matching_combo_detects_exact_recipe_only():
    doc,cover,text=_doc()
    cover.animation["beat_v1"]=combo_definition("club_impact").payload()
    a=assignment_for_layer(cover)
    assert matching_combo_id(a)=="club_impact"
    cover.animation["beat_v1"]["motion_intensity"]=.76
    assert matching_combo_id(assignment_for_layer(cover)) is None


def test_inspector_combo_applies_canonical_payload():
    _app()
    doc,cover,text=_doc()
    inspector=PropertyInspector(); inspector.set_layer(cover)
    idx=inspector.beat_combo.findData("club_impact")
    assert idx>=0
    payloads=[]
    inspector.beatAnimationEdited.connect(lambda _layer,payload: payloads.append(payload))
    inspector.beat_combo.setCurrentIndex(idx)
    inspector._apply_beat_combo_from_ui()
    payload=payloads[-1]
    assert payload["presets"]==["club_punch"]
    assert payload["intensity"]==pytest.approx(1.10)
    assert payload["motion_preset"]=="camera_shake"
    assert payload["motion_intensity"]==pytest.approx(.75)


def test_ai_context_has_motion_and_combo_catalog_path_free():
    doc,cover,text=_doc(); ctx=_ctx(doc,(cover.layer_id,))
    beat=ctx.payload["beat_context"]
    assert len(beat["motion_catalog"])==6
    assert len(beat["combo_catalog"])==8
    layer=next(x for x in beat["layers"] if x["layer_id"]==cover.layer_id)
    assert layer["current_motion"]=="camera_shake"
    assert "club_impact" in layer["supported_combos"]
    raw=str(ctx.payload).casefold()
    assert "locator" not in raw and "api_key" not in raw


def test_ai_set_motion_preserves_visual_preset_and_intensity():
    doc,cover,text=_doc(); ctx=_ctx(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_motion",{
        "layer_ids":[cover.layer_id],"motion_preset":"bass_sway","motion_intensity":.9,
    })
    controller=EditorController(doc)
    Step09TransactionEngine(controller).execute(
        _plan(doc,ctx,(action,)),ctx,PermissionGrant.all_editor_writes()
    )
    a=assignment_for_layer(controller.snapshot().layer_map()[cover.layer_id])
    assert a.presets[0].value=="strong_punch"
    assert a.intensity==pytest.approx(1)
    assert a.motion_preset==AdvancedMotionPreset.BASS_SWAY
    assert a.motion_intensity==pytest.approx(.9)


def test_ai_adjust_and_clear_motion_preserve_visual():
    doc,cover,text=_doc(); ctx=_ctx(doc,(cover.layer_id,))
    actions=(
        AgentActionCall("adjust_motion_intensity",{"layer_ids":[cover.layer_id],"delta":.25}),
        AgentActionCall("clear_beat_motion",{"layer_ids":[cover.layer_id]}),
    )
    controller=EditorController(doc)
    Step09TransactionEngine(controller).execute(
        _plan(doc,ctx,actions),ctx,PermissionGrant.all_editor_writes()
    )
    a=assignment_for_layer(controller.snapshot().layer_map()[cover.layer_id])
    assert a.presets[0].value=="strong_punch"
    assert a.motion_preset is None


def test_ai_apply_combo_is_one_revision_and_undoable():
    doc,cover,text=_doc(); ctx=_ctx(doc,(cover.layer_id,))
    action=AgentActionCall("apply_beat_combo",{"layer_ids":[cover.layer_id],"combo_id":"cinematic_spark"})
    controller=EditorController(doc); engine=Step09TransactionEngine(controller)
    before=controller.snapshot().content_signature()
    record=engine.execute(_plan(doc,ctx,(action,),"pakai Cinematic Spark"),ctx,PermissionGrant.all_editor_writes())
    assert record.result_revision==doc.revision+1
    a=assignment_for_layer(controller.snapshot().layer_map()[cover.layer_id])
    assert a.presets[0].value=="cinematic_swell"
    assert a.motion_preset==AdvancedMotionPreset.SPARK_BURST
    assert engine.undo_ai().content_signature()==before


def test_motion_actions_require_beat_permission():
    doc,cover,text=_doc(); ctx=_ctx(doc,(cover.layer_id,))
    action=AgentActionCall("set_beat_motion",{
        "layer_ids":[cover.layer_id],"motion_preset":"camera_shake","motion_intensity":.8,
    })
    grant=PermissionGrant(frozenset({AgentPermission.VISUAL_WRITE.value}))
    with pytest.raises(Step09PermissionError):
        Step09TransactionEngine(EditorController(doc)).dry_run(_plan(doc,ctx,(action,)),ctx,grant)


@pytest.mark.parametrize("prompt,name,argkey,argvalue",[
    ("tambahkan camera shake","set_beat_motion","motion_preset","camera_shake"),
    ("pakai spark saat beat kuat","set_beat_motion","motion_preset","spark_burst"),
    ("shake-nya lebih kuat","adjust_motion_intensity","delta",.25),
    ("hapus motion","clear_beat_motion",None,None),
    ("pakai Club Impact","apply_beat_combo","combo_id","club_impact"),
])
def test_motion_combo_nlu(prompt,name,argkey,argvalue):
    doc,cover,text=_doc(); d=interpret_beat_prompt(prompt,_ctx(doc,(cover.layer_id,)))
    assert d is not None and d.actions and d.actions[0].name==name
    if argkey is not None:
        assert d.actions[0].args[argkey]==argvalue


def test_ambiguous_motion_target_clarifies():
    doc,cover,text=_doc()
    text.animation["beat_v1"]["motion_preset"]="beat_bounce"
    text.animation["beat_v1"]["motion_intensity"]=.7
    doc.validate()
    d=interpret_beat_prompt("hapus motion",_ctx(doc,()))
    assert d is not None and not d.actions and d.clarification


def test_command_batch_groups_same_timestamp_and_dedupes():
    w=CommandBatchWriter()
    w.add(1.25,"scale@x","width",420)
    w.add(1.25,"scale@x","height",420)
    w.add(1.25,"scale@x","width",420)
    text=w.serialize()
    assert text.count("\n")==1
    assert text.startswith("1.250000 ")
    assert text.count("scale@x width 420")==1
    m=w.metrics()
    assert m.rows==1 and m.ops==2 and m.bytes==len(text.encode())


def test_command_batch_order_is_deterministic():
    a=CommandBatchWriter(); b=CommandBatchWriter()
    ops=[("z","b","2"),("a","x","1"),("z","a","3")]
    for op in ops: a.add(.5,*op)
    for op in reversed(ops): b.add(.5,*op)
    assert a.serialize()==b.serialize()


def test_command_batch_guards_ops_and_bytes():
    w=CommandBatchWriter(max_ops=1,max_bytes=1000)
    w.add(0,"a","x","1"); w.add(0,"a","y","2")
    with pytest.raises(CommandLimitError):
        w.serialize()
    b=CommandBatchWriter(max_bytes=10)
    b.add(0,"target","command","a very long argument")
    with pytest.raises(CommandLimitError):
        b.serialize()


def test_two_hour_estimator_keeps_strong_punch_row_architecture():
    est=estimate_command_load(7200*TIMEBASE,30,4)
    assert est.sample_ticks==216001
    assert est.command_rows_upper_bound<=250000
    assert est.command_ops_upper_bound<=1_500_000
    assert est.within_limits


def test_two_hour_estimator_does_not_silently_reduce_hz():
    est=estimate_command_load(7200*TIMEBASE,30,7)
    assert est.sample_ticks==216001
    assert est.command_ops_upper_bound>1_500_000
    assert not est.within_limits
