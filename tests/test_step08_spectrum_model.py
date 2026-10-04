from __future__ import annotations

from copy import deepcopy

import pytest

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import ProjectDocument, Transform
from full_album_maker.spectrum_feature import (
    normalize_spectrum_properties,
    smoothing_to_averaging,
)
from full_album_maker.spectrum_step08 import (
    STEP08_PRESETS,
    SetSpectrumLayerState,
    build_apply_to_all_commands,
    build_preset_command,
    build_type_command,
    centered_transform,
    default_transform,
    preset_properties,
    spectrum_geometry,
)
from full_album_maker.spectrum_feature import make_spectrum_layer


def _document() -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP08")
    doc.canvas.width = 1920
    doc.canvas.height = 1080
    track = next(item for item in doc.tracks if item.kind == "visual")
    first = make_spectrum_layer(track.track_id, 0, preset_id="minimal_bars")
    second = make_spectrum_layer(track.track_id, 1, preset_id="circular_neon")
    doc.layers.extend([first, second])
    doc.validate()
    return doc


def test_normalizer_keeps_recovered_aliases_and_validates_step08_fields() -> None:
    props = normalize_spectrum_properties(
        {
            "style": "bars",
            "gain": 1.2,
            "color": "#1b8dff",
            "band_count": 128,
            "thickness": 12,
            "smoothing": 0.65,
        }
    )
    assert props["spectrum_type"] == "linear"
    assert props["gain"] == props["reactive_scale"] == pytest.approx(1.2)
    assert props["color"] == props["accent_color"] == "#1B8DFF"
    assert props["band_count"] == 128
    assert props["thickness"] == pytest.approx(12)
    assert props["smoothing"] == pytest.approx(0.65)
    assert props["audio_binding"] == "project_mix"
    assert smoothing_to_averaging(0.0) == 1
    assert smoothing_to_averaging(0.65) == 11
    with pytest.raises(ValueError, match="16..512"):
        normalize_spectrum_properties({"band_count": 8})
    with pytest.raises(ValueError, match="0..1"):
        normalize_spectrum_properties({"smoothing": 1.1})


def test_golden_circular_geometry_uses_project_center_and_size_ratio() -> None:
    doc = _document()
    transform = centered_transform(doc, "circular", size_ratio=0.78)
    layer = doc.layers[0]
    layer.transform = transform
    layer.properties = normalize_spectrum_properties({"spectrum_type": "circular", "style": "circular_spectrum"})
    geometry = spectrum_geometry(doc, layer)
    assert geometry.center_x_px == pytest.approx(960.0)
    assert geometry.center_y_px == pytest.approx(540.0)
    assert geometry.size_ratio == pytest.approx(0.78)
    assert transform.width * 1920 == pytest.approx(842.4)
    assert transform.height * 1080 == pytest.approx(842.4)


def test_type_switch_is_one_undo_and_preserves_center_and_common_fields() -> None:
    doc = _document()
    layer = doc.layers[0]
    controller = EditorController(doc)
    before = controller.snapshot().content_signature()
    before_geometry = spectrum_geometry(controller.snapshot(), layer)
    controller.dispatch(build_type_command(controller.snapshot(), layer.layer_id, "circular"))
    changed = controller.snapshot().layer_map()[layer.layer_id]
    props = normalize_spectrum_properties(changed.properties)
    after_geometry = spectrum_geometry(controller.snapshot(), changed)
    assert props["spectrum_type"] == "circular"
    assert props["style"] == "circular_spectrum"
    assert after_geometry.center_x_px == pytest.approx(before_geometry.center_x_px)
    assert after_geometry.center_y_px == pytest.approx(before_geometry.center_y_px)
    controller.undo()
    assert controller.snapshot().content_signature() == before


def test_classic_preset_is_real_bundle_and_unsupported_mockup_presets_fail_closed() -> None:
    doc = _document()
    layer = doc.layers[0]
    command = build_preset_command(doc, layer.layer_id, "classic")
    controller = EditorController(doc)
    controller.dispatch(command)
    props = normalize_spectrum_properties(controller.snapshot().layer_map()[layer.layer_id].properties)
    assert props["preset"] == "classic"
    assert props["band_count"] == 128
    assert props["thickness"] == pytest.approx(12)
    assert props["smoothing"] == pytest.approx(0.65)
    assert props["reactive_scale"] == pytest.approx(1.20)
    assert props["accent_color"] == "#1B8DFF"
    assert STEP08_PRESETS["neon_glow"]["supported"] is False
    for preset_id in ("neon_glow", "rainbow", "particles"):
        with pytest.raises(ValueError):
            preset_properties(preset_id, layer.properties)


def test_set_spectrum_state_restores_exact_old_properties_on_undo() -> None:
    doc = _document()
    layer = doc.layers[0]
    layer.properties = {"style": "bars", "color": "#abcdef", "gain": 1.0, "legacy_extra": {"x": 1}}
    old_properties = deepcopy(layer.properties)
    controller = EditorController(doc)
    controller.dispatch(
        SetSpectrumLayerState(
            layer.layer_id,
            {"band_count": 96, "smoothing": 0.4, "accent_color": "#1B8DFF"},
            opacity=0.9,
        )
    )
    assert controller.snapshot().layer_map()[layer.layer_id].properties["band_count"] == 96
    controller.undo()
    restored = controller.snapshot().layer_map()[layer.layer_id]
    assert restored.properties == old_properties
    assert restored.opacity == pytest.approx(1.0)


def test_apply_to_all_prevalidates_and_is_atomic_while_preserving_binding() -> None:
    doc = _document()
    source, target = doc.layers
    source.properties = preset_properties("classic", source.properties)
    target.properties = normalize_spectrum_properties({**target.properties, "audio_binding": "project_mix"})
    before = doc.content_signature()
    commands = build_apply_to_all_commands(doc, source.layer_id)
    assert len(commands) == 1
    controller = EditorController(doc)
    controller.dispatch(commands)
    changed = controller.snapshot().layer_map()[target.layer_id]
    changed_props = normalize_spectrum_properties(changed.properties)
    assert changed_props["band_count"] == 128
    assert changed_props["audio_binding"] == "project_mix"
    controller.undo()
    assert controller.snapshot().content_signature() == before

    locked_doc = _document()
    locked_doc.layers[1].locked = True
    with pytest.raises(ValueError, match="terkunci"):
        build_apply_to_all_commands(locked_doc, locked_doc.layers[0].layer_id)


def test_reset_transform_has_explicit_deterministic_semantics() -> None:
    doc = _document()
    circular = default_transform(doc, "circular")
    linear = default_transform(doc, "linear")
    assert circular.width * doc.canvas.width == pytest.approx(circular.height * doc.canvas.height)
    assert (circular.x + circular.width / 2) * doc.canvas.width == pytest.approx(960)
    assert (linear.x + linear.width / 2) * doc.canvas.width == pytest.approx(960)
    assert isinstance(linear, Transform)
