from __future__ import annotations

from full_album_maker.album_visuals import make_song_cover_layer, make_vinyl_layer
from full_album_maker.editor_models import (
    Layer, MediaAsset, ProjectDocument, SongInstance, TIMEBASE, Transform,
)
from full_album_maker.editor_session import EditorSession
from full_album_maker.music_style_presets import (
    MUSIC_STYLE_CATALOG,
    MusicStylePreset,
    apply_music_style,
)
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.visual_binding_contract import CoreBeatPreset


def _doc():
    doc=ProjectDocument.new_empty("STEP10 styles")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=4*TIMEBASE)
    image=MediaAsset(kind="image",locator="visual.png",original_name="visual.png")
    doc.media.extend([audio,image])
    song=SongInstance(
        asset_id=audio.asset_id,source_out_tick=4*TIMEBASE,
        display_title="Song",cover_asset_id=image.asset_id,visual_asset_id=image.asset_id,
    )
    doc.playlist.entries.append(song)
    cover=make_song_cover_layer(doc.tracks[0].track_id,1,fallback_asset_id=image.asset_id)
    vinyl=make_vinyl_layer(doc.tracks[0].track_id,2)
    spectrum=make_spectrum_layer(doc.tracks[0].track_id,3)
    text=Layer(
        track_id=doc.tracks[0].track_id,type="text",name="Title",
        transform=Transform(x=.1,y=.1,width=.8,height=.2),
        properties={"text":"Song","font_size":40,"color":"#ffffff"},
    )
    doc.layers.extend([cover,vinyl,spectrum,text])
    doc.validate()
    return doc,cover,vinyl,spectrum,text


def test_music_style_catalog_has_nine_unique_styles():
    assert len(MUSIC_STYLE_CATALOG)==len(MusicStylePreset)==9
    assert len(set(s.value for s in MusicStylePreset))==9


def test_every_style_references_valid_presets_and_intensity():
    for style,definition in MUSIC_STYLE_CATALOG.items():
        assert definition.style==style
        assert definition.label.strip()
        assert definition.recipes
        for recipe in definition.recipes.values():
            assert isinstance(recipe.preset,CoreBeatPreset)
            assert 0 <= recipe.intensity <= 2


def test_edm_applies_advanced_presets_and_enables_vinyl_bpm_sync():
    doc,cover,vinyl,spectrum,text=_doc()
    changed,report=apply_music_style(doc,MusicStylePreset.EDM)
    cmap=changed.layer_map()
    assert report.applied_layers>=4
    assert cmap[cover.layer_id].animation["beat_v1"]["presets"]==["club_punch"]
    assert cmap[spectrum.layer_id].animation["beat_v1"]["presets"]==["bass_punch"]
    assert cmap[vinyl.layer_id].properties["bpm_sync"] is True
    assert cmap[vinyl.layer_id].properties["beats_per_rotation"]==4.0
    assert "beat_v1" not in doc.layer_map()[cover.layer_id].animation


def test_acoustic_does_not_force_vinyl_bpm_sync():
    doc,cover,vinyl,spectrum,text=_doc()
    changed,_=apply_music_style(doc,MusicStylePreset.ACOUSTIC)
    assert changed.layer_map()[vinyl.layer_id].properties["bpm_sync"] is False


def test_locked_layer_is_skipped_and_preserved():
    doc,cover,vinyl,spectrum,text=_doc()
    cover.locked=True
    cover.animation={"beat_v1":{"enabled":True,"presets":["bass_pulse"],"intensity":.33}}
    changed,report=apply_music_style(doc,MusicStylePreset.EDM)
    assert report.skipped_locked==1
    assert changed.layer_map()[cover.layer_id].animation==cover.animation


def test_apply_style_does_not_change_media_playlist_or_timing():
    doc,*_= _doc()
    before=[(s.song_id,s.asset_id,s.source_in_tick,s.source_out_tick,s.free_start_tick) for s in doc.playlist.entries]
    media=[(m.asset_id,m.locator,m.kind) for m in doc.media]
    changed,_=apply_music_style(doc,MusicStylePreset.POP)
    after=[(s.song_id,s.asset_id,s.source_in_tick,s.source_out_tick,s.free_start_tick) for s in changed.playlist.entries]
    assert before==after
    assert media==[(m.asset_id,m.locator,m.kind) for m in changed.media]


def test_editor_session_apply_style_is_one_undoable_transaction():
    doc,cover,vinyl,spectrum,text=_doc()
    session=EditorSession(doc)
    start_revision=session.revision
    report=session.apply_music_style(MusicStylePreset.EDM)
    assert report.applied_layers>=4
    assert session.revision==start_revision+1
    assert session.snapshot().layer_map()[vinyl.layer_id].properties["bpm_sync"] is True
    session.undo()
    restored=session.snapshot()
    assert "beat_v1" not in restored.layer_map()[cover.layer_id].animation
    assert restored.layer_map()[vinyl.layer_id].properties.get("bpm_sync",False) is False
    session.redo()
    assert session.snapshot().layer_map()[cover.layer_id].animation["beat_v1"]["presets"]==["club_punch"]


def test_dangdut_remix_enables_bpm_sync():
    doc,cover,vinyl,spectrum,text=_doc()
    changed,_=apply_music_style(doc,MusicStylePreset.DANGDUT_REMIX)
    assert changed.layer_map()[vinyl.layer_id].properties["bpm_sync"] is True
    assert changed.layer_map()[cover.layer_id].animation["beat_v1"]["presets"]==["club_punch"]
