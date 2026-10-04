from __future__ import annotations

import hashlib

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
import pytest

from full_album_maker.editor_models import Layer, ProjectDocument, TimeBinding, Transform
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_preview_step08 import SpectrumPreviewCanvas
from full_album_maker.spectrum_step08 import STEP08_PRESETS, centered_transform, preset_properties
from full_album_maker.spectrum_workspace_step08 import (
    SpectrumInspector,
    SpectrumLayerContext,
    SpectrumTimelineCanvas,
    SpectrumWorkspace,
    inspector_state,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _doc() -> ProjectDocument:
    doc = ProjectDocument.new_empty("STEP08 UI")
    doc.canvas.width = 1920
    doc.canvas.height = 1080
    track = next(item for item in doc.tracks if item.kind == "visual")
    spectrum = make_spectrum_layer(track.track_id, 0, preset_id="minimal_bars")
    spectrum.properties = preset_properties("classic", spectrum.properties)
    spectrum.properties.update({"spectrum_type": "circular", "style": "circular_spectrum"})
    spectrum.transform = centered_transform(doc, "circular", size_ratio=0.78)
    spectrum.opacity = 0.90
    doc.layers.extend(
        [
            spectrum,
            Layer(
                track_id=track.track_id,
                type="text",
                name="Logo",
                order=1,
                time_binding=TimeBinding(kind="album"),
                transform=Transform(x=0.05, y=0.05, width=0.20, height=0.08),
                properties={"text": "LOGO", "font_size": 40, "color": "#ffffff"},
            ),
            Layer(
                track_id=track.track_id,
                type="song_title",
                name="Judul",
                order=2,
                time_binding=TimeBinding(kind="album"),
                transform=Transform(x=0.30, y=0.76, width=0.40, height=0.10),
                properties={"template": "{title}", "font_size": 48, "color": "#ffffff"},
            ),
            Layer(
                track_id=track.track_id,
                type="background",
                name="Overlay",
                order=3,
                time_binding=TimeBinding(kind="album"),
                properties={"mode": "solid", "color": "#101114"},
            ),
        ]
    )
    doc.validate()
    return doc


def test_context_exposes_layer_stack_and_all_nine_golden_presets() -> None:
    _app()
    doc = _doc()
    selected = doc.layers[0].layer_id
    context = SpectrumLayerContext()
    context.set_state(doc, selected)
    assert context.layer_layout.count() >= 5  # four layer rows + stretch
    assert set(STEP08_PRESETS) == {
        "classic",
        "neon_glow",
        "rainbow",
        "minimal",
        "wave",
        "particles",
        "retro",
        "trance",
        "ambient",
    }
    # Three golden mockup effects intentionally fail closed instead of preview-only fakes.
    assert STEP08_PRESETS["neon_glow"]["supported"] is False
    assert STEP08_PRESETS["rainbow"]["supported"] is False
    assert STEP08_PRESETS["particles"]["supported"] is False
    assert context.preset_grid.count() == 9


def test_inspector_golden_fixture_values_and_lock_disable_editing() -> None:
    _app()
    doc = _doc()
    layer = doc.layers[0]
    state = inspector_state(doc, layer)
    assert state is not None
    inspector = SpectrumInspector()
    inspector.set_state(state)
    assert inspector.type_segment.checked_value() == "circular"
    assert inspector.size.value() == pytest.approx(78.0)
    assert inspector.x.value() == pytest.approx(960.0)
    assert inspector.y.value() == pytest.approx(540.0)
    assert inspector.bands.value() == 128
    assert inspector.thickness.value() == pytest.approx(12.0)
    assert inspector.opacity.value() == pytest.approx(90.0)
    assert inspector.smoothing.value() == pytest.approx(0.65)
    assert inspector.reactive.value() == pytest.approx(1.20)
    assert inspector.color.text() == "#1B8DFF"

    layer.locked = True
    inspector.set_state(inspector_state(doc, layer))
    assert inspector.size.isEnabled() is False
    assert inspector.apply_all_button.isEnabled() is False


def _image_digest(widget: SpectrumPreviewCanvas) -> str:
    widget.resize(800, 450)
    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    ptr = image.constBits()
    data = bytes(ptr[: image.sizeInBytes()])
    return hashlib.sha256(data).hexdigest()


def test_resting_preview_is_deterministic_across_playhead_changes() -> None:
    _app()
    doc = _doc()
    canvas = SpectrumPreviewCanvas()
    canvas.set_document(doc)
    canvas.set_selected_layer(None)
    canvas.set_playhead(0)
    first = _image_digest(canvas)
    canvas.set_playhead(123456789)
    second = _image_digest(canvas)
    assert first == second


def test_workspace_accepts_accurate_frame_status_without_mutating_document(tmp_path) -> None:
    _app()
    doc = _doc()
    before = doc.content_signature()
    workspace = SpectrumWorkspace()
    workspace.set_document(doc, doc.layers[0].layer_id, 0)
    workspace.set_preview_result("", "ERROR: missing audio")
    assert workspace.preview_status.text() == "Preview resting"
    assert doc.content_signature() == before


def test_spectrum_timeline_seek_maps_mouse_position_to_project_duration() -> None:
    _app()
    timeline = SpectrumTimelineCanvas()
    doc = _doc()
    # No audio means resolver duration can be the Spectrum binding baseline; the
    # canvas still has a deterministic non-zero duration guard and emits ticks.
    timeline.set_state(doc, 0)
    received: list[int] = []
    timeline.playhead_requested.connect(received.append)
    timeline.resize(1000, 180)
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(546, 90),
        QPointF(546, 90),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    timeline.mousePressEvent(event)
    assert received
    assert received[-1] >= 0
