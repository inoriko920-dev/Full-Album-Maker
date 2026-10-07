from __future__ import annotations

from full_album_maker.ai_agent_core_step09 import build_agent_context_snapshot
from full_album_maker.ai_beat_nlu_step11 import interpret_beat_prompt
from full_album_maker.album_visuals import make_song_cover_layer, make_vinyl_layer
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


def _doc():
    doc=ProjectDocument.new_empty("STEP11 NLU")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=3*TIMEBASE)
    image=MediaAsset(kind="image",locator="cover.png",original_name="cover.png")
    doc.media.extend([audio,image])
    doc.playlist.entries.append(SongInstance(
        asset_id=audio.asset_id,source_out_tick=3*TIMEBASE,display_title="Song",
        cover_asset_id=image.asset_id,
    ))
    track=doc.tracks[0].track_id
    cover=make_song_cover_layer(track,1,fallback_asset_id=image.asset_id)
    vinyl=make_vinyl_layer(track,2)
    doc.layers.extend([cover,vinyl])
    doc.validate()
    return doc,cover,vinyl


def _ctx(doc,selected=()):
    return build_agent_context_snapshot(
        doc,selected_layer_ids=selected,enabled_contexts=("beat",),user_text="beat"
    )


def test_edm_phrase_maps_to_music_style():
    doc,cover,vinyl=_doc()
    d=interpret_beat_prompt("Buat animasinya cocok untuk EDM",_ctx(doc))
    assert d.actions[0].name=="apply_music_style"
    assert d.actions[0].args["style_id"]=="edm"


def test_dangdut_remix_phrase_maps_to_music_style():
    doc,cover,vinyl=_doc()
    d=interpret_beat_prompt("Pakai Dangdut Remix",_ctx(doc))
    assert d.actions[0].name=="apply_music_style"
    assert d.actions[0].args["style_id"]=="dangdut_remix"


def test_club_punch_120_prefers_specific_preset_over_club_style():
    doc,cover,vinyl=_doc()
    d=interpret_beat_prompt("Pakai Club Punch 120% di layer ini",_ctx(doc,(cover.layer_id,)))
    assert d.actions[0].name=="set_beat_preset"
    assert d.actions[0].args["preset_id"]=="club_punch"
    assert d.actions[0].args["intensity"]==1.2


def test_sync_vinyl_maps_to_bpm_action():
    doc,cover,vinyl=_doc()
    d=interpret_beat_prompt("Sinkronkan vinyl ke BPM",_ctx(doc,(vinyl.layer_id,)))
    assert d.actions[0].name=="set_vinyl_bpm_sync"
    assert d.actions[0].args["layer_ids"]==[vinyl.layer_id]
    assert d.actions[0].args["beats_per_rotation"]==4.0


def test_disable_beat_maps_to_clear_action():
    doc,cover,vinyl=_doc()
    cover.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    doc.validate()
    d=interpret_beat_prompt("Matikan beat di layer ini",_ctx(doc,(cover.layer_id,)))
    assert d.actions[0].name=="clear_beat_animation"


def test_more_powerful_maps_to_relative_intensity():
    doc,cover,vinyl=_doc()
    cover.animation={"beat_v1":{"enabled":True,"presets":["bass_punch"],"intensity":1}}
    doc.validate()
    d=interpret_beat_prompt("Bass-nya lebih kuat",_ctx(doc,(cover.layer_id,)))
    assert d.actions[0].name=="adjust_beat_intensity"
    assert d.actions[0].args["delta"]==.25


def test_ambiguous_layer_specific_phrase_clarifies_without_action():
    doc,cover,vinyl=_doc()
    cover.animation={"beat_v1":{"enabled":True,"presets":["strong_punch"],"intensity":1}}
    vinyl.animation={"beat_v1":{"enabled":True,"presets":["bass_pulse"],"intensity":1}}
    doc.validate()
    d=interpret_beat_prompt("Matikan beat",_ctx(doc))
    assert not d.actions
    assert d.clarification


def test_explicit_all_layers_can_target_all():
    doc,cover,vinyl=_doc()
    d=interpret_beat_prompt("Pakai Beat Pulse untuk semua layer Beat",_ctx(doc))
    assert d.actions[0].name=="set_beat_preset"
    assert set(d.actions[0].args["layer_ids"])=={cover.layer_id,vinyl.layer_id}


def test_unrelated_phrase_falls_through():
    doc,cover,vinyl=_doc()
    assert interpret_beat_prompt("buat judulnya lebih besar",_ctx(doc,(cover.layer_id,))) is None
