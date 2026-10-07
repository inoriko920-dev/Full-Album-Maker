from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from full_album_maker.beat_layer_capabilities import beat_capability_for_layer
from full_album_maker.beat_preset_catalog import (
    BEAT_PRESET_CATALOG,
    catalog_presets,
    preset_definition,
)
from full_album_maker.editor_models import Layer, ProjectDocument, Transform
from full_album_maker.property_inspector import PropertyInspector
from full_album_maker.visual_binding_contract import (
    CoreBeatPreset,
    VisualProperty,
)
from full_album_maker.visual_binding_engine import core_binding_set


def _app():
    return QApplication.instance() or QApplication([])


def _layer(layer_type="song_cover", *, rotation=0.0, pivot=(0.5, 0.5)):
    doc=ProjectDocument.new_empty("STEP10 catalog")
    layer=Layer(
        track_id=doc.tracks[0].track_id,
        type=layer_type,
        name=layer_type,
        transform=Transform(
            x=.2,y=.2,width=.4,height=.4,rotation=rotation,
            pivot_x=pivot[0],pivot_y=pivot[1],
        ),
    )
    return layer


def _binding_map(preset):
    return {
        (b.channel.value,b.property.value): (b.amount,b.response_gamma,b.min_signal)
        for b in core_binding_set(preset).bindings
    }


def test_catalog_has_exactly_eighteen_unique_presets():
    presets=catalog_presets()
    assert len(presets)==18
    assert len(set(p.value for p in presets))==18
    assert set(presets)==set(BEAT_PRESET_CATALOG)


def test_legacy_six_preset_ids_remain_stable():
    legacy={
        "subtle_beat_pulse","bass_pulse","strong_punch",
        "onset_flash","rotation_nudge","energy_breathe",
    }
    assert legacy.issubset({p.value for p in CoreBeatPreset})


def test_legacy_mapping_subtle_beat_pulse_unchanged():
    data=_binding_map(CoreBeatPreset.SUBTLE_BEAT_PULSE)
    assert data[("beat","scale_multiplier")][0] == pytest.approx(.025)


def test_legacy_mapping_bass_pulse_unchanged():
    data=_binding_map(CoreBeatPreset.BASS_PULSE)
    assert data[("bass","scale_multiplier")][0] == pytest.approx(.060)


def test_legacy_mapping_strong_punch_unchanged():
    data=_binding_map(CoreBeatPreset.STRONG_PUNCH)
    assert data[("strong_beat","scale_multiplier")][0] == pytest.approx(.080)
    assert data[("strong_beat","zoom_multiplier")][0] == pytest.approx(.060)
    assert data[("strong_beat","glow_amount")][0] == pytest.approx(.350)


@pytest.mark.parametrize("preset", list(CoreBeatPreset))
def test_every_preset_builds_valid_binding_set(preset):
    result=core_binding_set(preset)
    result.validate()
    assert result.binding_set_id==preset.value
    assert result.bindings


@pytest.mark.parametrize("preset", list(CoreBeatPreset))
def test_every_preset_has_complete_metadata(preset):
    definition=preset_definition(preset)
    assert definition.preset==preset
    assert definition.label.strip()
    assert definition.category.strip()
    assert definition.description.strip()
    assert definition.properties
    assert 0 <= definition.recommended_intensity <= 2
    assert all(alias.strip() for alias in definition.ai_aliases)


def test_rotation_presets_are_declared_not_text_safe():
    for preset in (CoreBeatPreset.ROTATION_NUDGE,CoreBeatPreset.BEAT_TILT,CoreBeatPreset.BASS_TILT):
        definition=preset_definition(preset)
        assert definition.rotation_required
        assert not definition.text_safe
        assert VisualProperty.ROTATION_OFFSET_DEG in definition.properties


def test_text_capability_filters_all_rotation_presets():
    cap=beat_capability_for_layer(_layer("text"))
    values=set(cap.supported_presets)
    assert CoreBeatPreset.ROTATION_NUDGE not in values
    assert CoreBeatPreset.BEAT_TILT not in values
    assert CoreBeatPreset.BASS_TILT not in values
    assert CoreBeatPreset.CLUB_PUNCH in values
    assert len(values)==15


def test_visual_rotation_unsafe_filters_rotation_presets_only():
    cap=beat_capability_for_layer(_layer("song_cover",rotation=5))
    values=set(cap.supported_presets)
    assert len(values)==15
    assert CoreBeatPreset.ROTATION_NUDGE not in values
    assert CoreBeatPreset.BEAT_TILT not in values
    assert CoreBeatPreset.BASS_TILT not in values
    assert CoreBeatPreset.BASS_PUNCH in values


def test_visual_rotation_safe_exposes_all_eighteen():
    cap=beat_capability_for_layer(_layer("song_cover"))
    assert len(cap.supported_presets)==18


def test_property_inspector_uses_registry_labels_for_advanced_presets():
    _app()
    layer=_layer("song_cover")
    inspector=PropertyInspector()
    inspector.set_layer(layer)
    values={
        inspector.beat_preset.itemData(i): inspector.beat_preset.itemText(i)
        for i in range(inspector.beat_preset.count())
    }
    assert values["club_punch"]=="Club Punch"
    assert values["bass_punch"]=="Bass Punch"
    assert values["cinematic_swell"]=="Cinematic Swell"


def test_vinyl_inspector_exposes_bpm_sync_controls():
    _app()
    layer=_layer("vinyl")
    layer.properties={
        "spin_seconds":8.0,"center_ratio":.18,
        "color":"#151515","groove_color":"#2d2d2d","center_color":"#d9d9d9",
        "bpm_sync":True,"beats_per_rotation":2.0,"bpm_sync_min_confidence":.55,
    }
    inspector=PropertyInspector()
    inspector.set_layer(layer)
    assert inspector.vinyl_bpm_sync.isChecked()
    assert inspector.vinyl_beats_per_rotation.currentData()==2.0
    assert not inspector.vinyl_bpm_sync.isHidden()
