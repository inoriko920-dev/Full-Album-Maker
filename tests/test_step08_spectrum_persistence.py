from __future__ import annotations

from pathlib import Path

import pytest

from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import ProjectDocument
from full_album_maker.project_repository import load_project_document, save_project_document
from full_album_maker.spectrum_feature import normalize_spectrum_properties
from full_album_maker.spectrum_step08 import (
    SetSpectrumLayerState,
    build_type_command,
    centered_transform,
    preset_properties,
)
from full_album_maker.template_system import build_template_layers


def _normalized_layer(document: ProjectDocument, layer_id: str) -> tuple[dict, tuple[float, ...], float, bool, bool]:
    layer = document.layer_map()[layer_id]
    transform = layer.transform
    return (
        normalize_spectrum_properties(layer.properties),
        (
            transform.x,
            transform.y,
            transform.width,
            transform.height,
            transform.rotation,
        ),
        layer.opacity,
        layer.enabled,
        layer.locked,
    )


def test_template_apply_builds_normal_spectrum_layer_not_runtime_mode() -> None:
    doc = ProjectDocument.new_empty("STEP08 Template")
    layers = build_template_layers(doc, "neon_spectrum")
    spectrum = next(layer for layer in layers if layer.type == "spectrum")
    props = normalize_spectrum_properties(spectrum.properties)
    assert spectrum.layer_id
    assert spectrum.type == "spectrum"
    assert spectrum.origin == "template"
    assert props["audio_binding"] == "project_mix"
    assert "analyzer_cache" not in spectrum.properties
    assert "runtime_cache" not in spectrum.properties


def test_complex_spectrum_state_round_trips_without_schema_migration(tmp_path: Path) -> None:
    doc = ProjectDocument.new_empty("STEP08 Persistence")
    track = next(item for item in doc.tracks if item.kind == "visual")
    layers = build_template_layers(doc, "neon_spectrum")
    spectrum = next(layer for layer in layers if layer.type == "spectrum")
    doc.layers = layers
    doc.validate()

    controller = EditorController(doc)
    controller.dispatch(build_type_command(controller.snapshot(), spectrum.layer_id, "circular"))
    current = controller.snapshot()
    layer = current.layer_map()[spectrum.layer_id]
    props = preset_properties("classic", layer.properties)
    props.update(
        normalize_spectrum_properties(
            {
                **props,
                "spectrum_type": "circular",
                "style": "circular_spectrum",
                "band_count": 128,
                "thickness": 12.0,
                "smoothing": 0.65,
                "reactive_scale": 1.20,
                "accent_color": "#1B8DFF",
            }
        )
    )
    controller.dispatch(
        SetSpectrumLayerState(
            spectrum.layer_id,
            props,
            transform=centered_transform(current, "circular", size_ratio=0.78),
            opacity=0.90,
        )
    )
    expected = controller.snapshot()
    expected_layer = expected.layer_map()[spectrum.layer_id]
    expected_layer.locked = True
    expected.validate()

    target = tmp_path / "step08-project.json"
    save_project_document(str(target), expected)
    reopened = load_project_document(str(target))
    assert reopened.schema_version == expected.schema_version
    assert spectrum.layer_id in reopened.layer_map()
    before = _normalized_layer(expected, spectrum.layer_id)
    after = _normalized_layer(reopened, spectrum.layer_id)
    assert after[0] == before[0]
    assert after[1] == pytest.approx(before[1])
    assert after[2:] == before[2:]
    assert after[0]["spectrum_type"] == "circular"
    assert after[0]["band_count"] == 128
    assert after[0]["thickness"] == pytest.approx(12.0)
    assert after[0]["smoothing"] == pytest.approx(0.65)
    assert after[0]["reactive_scale"] == pytest.approx(1.20)
    assert after[0]["accent_color"] == "#1B8DFF"
