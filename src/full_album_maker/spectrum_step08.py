from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from .editor_commands import CommandError, EditorCommand
from .editor_models import Layer, ProjectDocument, Transform
from .spectrum_feature import normalize_spectrum_properties, style_for_spectrum_type


STEP08_PRESETS: dict[str, dict[str, object]] = {
    "classic": {
        "label": "Classic",
        "supported": True,
        "properties": {
            "spectrum_type": "linear",
            "style": "bars",
            "band_count": 128,
            "thickness": 12.0,
            "smoothing": 0.65,
            "reactive_scale": 1.20,
            "accent_color": "#1B8DFF",
            "frequency_scale": "log",
            "amplitude_scale": "sqrt",
            "mirror": False,
        },
    },
    "neon_glow": {
        "label": "Neon Glow",
        "supported": False,
        "reason": "Renderer recovered tidak memiliki glow compositor Spectrum yang parity-safe.",
    },
    "rainbow": {
        "label": "Rainbow",
        "supported": False,
        "reason": "Renderer recovered memakai satu accent color; multi-color mapping belum ada.",
    },
    "minimal": {
        "label": "Minimal",
        "supported": True,
        "properties": {
            "spectrum_type": "linear",
            "style": "bars",
            "band_count": 64,
            "thickness": 6.0,
            "smoothing": 0.35,
            "reactive_scale": 0.85,
            "accent_color": "#E8F1FC",
            "frequency_scale": "log",
            "amplitude_scale": "sqrt",
            "mirror": False,
        },
    },
    "wave": {
        "label": "Wave",
        "supported": True,
        "properties": {
            "spectrum_type": "linear",
            "style": "waveform",
            "band_count": 128,
            "thickness": 4.0,
            "smoothing": 0.0,
            "reactive_scale": 1.10,
            "accent_color": "#67F0C2",
            "frequency_scale": "linear",
            "amplitude_scale": "sqrt",
            "mirror": False,
        },
    },
    "particles": {
        "label": "Particles",
        "supported": False,
        "reason": "Particles tidak ada pada renderer recovered dan tidak boleh dipalsukan di preview.",
    },
    "retro": {
        "label": "Retro",
        "supported": True,
        "properties": {
            "spectrum_type": "linear",
            "style": "spectrum_line",
            "band_count": 96,
            "thickness": 5.0,
            "smoothing": 0.50,
            "reactive_scale": 1.05,
            "accent_color": "#FF9F43",
            "frequency_scale": "log",
            "amplitude_scale": "sqrt",
            "mirror": False,
        },
    },
    "trance": {
        "label": "Trance",
        "supported": True,
        "properties": {
            "spectrum_type": "circular",
            "style": "circular_spectrum",
            "band_count": 160,
            "thickness": 10.0,
            "smoothing": 0.70,
            "reactive_scale": 1.50,
            "accent_color": "#4DE8FF",
            "frequency_scale": "log",
            "amplitude_scale": "sqrt",
            "inner_ratio": 0.58,
            "mirror": False,
        },
    },
    "ambient": {
        "label": "Ambient",
        "supported": True,
        "properties": {
            "spectrum_type": "circular",
            "style": "circular_spectrum",
            "band_count": 96,
            "thickness": 7.0,
            "smoothing": 0.85,
            "reactive_scale": 0.75,
            "accent_color": "#8CB8FF",
            "frequency_scale": "log",
            "amplitude_scale": "sqrt",
            "inner_ratio": 0.62,
            "mirror": False,
        },
    },
}

STEP08_STYLE_KEYS = {
    "style",
    "spectrum_type",
    "color",
    "accent_color",
    "gain",
    "reactive_scale",
    "frequency_scale",
    "amplitude_scale",
    "mirror",
    "inner_ratio",
    "band_count",
    "thickness",
    "smoothing",
    "preset",
}


@dataclass(frozen=True)
class SpectrumGeometry:
    center_x_px: float
    center_y_px: float
    size_ratio: float


@dataclass(frozen=True)
class SpectrumLayerSnapshot:
    properties: dict
    transform: Transform
    opacity: float
    name: str


def spectrum_layers(document: ProjectDocument) -> tuple[Layer, ...]:
    return tuple(sorted((layer for layer in document.layers if layer.type == "spectrum"), key=lambda item: item.order))


def spectrum_geometry(document: ProjectDocument, layer: Layer) -> SpectrumGeometry:
    if layer.type != "spectrum":
        raise ValueError("Layer bukan Spectrum.")
    canvas_w = max(1, document.canvas.width)
    canvas_h = max(1, document.canvas.height)
    transform = layer.transform
    center_x = (transform.x + transform.width / 2.0) * canvas_w
    center_y = (transform.y + transform.height / 2.0) * canvas_h
    props = normalize_spectrum_properties(layer.properties)
    if props["spectrum_type"] == "circular":
        diameter_px = min(transform.width * canvas_w, transform.height * canvas_h)
        size_ratio = diameter_px / min(canvas_w, canvas_h)
    else:
        size_ratio = transform.width
    return SpectrumGeometry(center_x, center_y, size_ratio)


def transform_from_geometry(
    document: ProjectDocument,
    spectrum_type: str,
    *,
    center_x_px: float,
    center_y_px: float,
    size_ratio: float,
    rotation: float = 0.0,
) -> Transform:
    canvas_w = max(1, document.canvas.width)
    canvas_h = max(1, document.canvas.height)
    size = float(size_ratio)
    if not 0.10 <= size <= 1.50:
        raise ValueError("Ukuran Spectrum harus 10%..150%.")
    cx = float(center_x_px) / canvas_w
    cy = float(center_y_px) / canvas_h
    if spectrum_type == "circular":
        diameter_px = size * min(canvas_w, canvas_h)
        width = diameter_px / canvas_w
        height = diameter_px / canvas_h
    elif spectrum_type == "linear":
        width = size
        height = min(0.40, max(0.08, size * 0.24))
    else:
        raise ValueError("spectrum_type harus linear/circular.")
    result = Transform(
        x=cx - width / 2.0,
        y=cy - height / 2.0,
        width=width,
        height=height,
        rotation=float(rotation),
    )
    result.validate()
    return result


def centered_transform(
    document: ProjectDocument,
    spectrum_type: str,
    *,
    size_ratio: float,
    rotation: float = 0.0,
) -> Transform:
    return transform_from_geometry(
        document,
        spectrum_type,
        center_x_px=document.canvas.width / 2.0,
        center_y_px=document.canvas.height / 2.0,
        size_ratio=size_ratio,
        rotation=rotation,
    )


def default_transform(document: ProjectDocument, spectrum_type: str) -> Transform:
    if spectrum_type == "circular":
        return centered_transform(document, "circular", size_ratio=0.78)
    return centered_transform(document, "linear", size_ratio=0.78)


def _merged_properties(current: dict, requested: dict) -> dict:
    merged = dict(current)
    merged.update(deepcopy(requested))
    normalized = normalize_spectrum_properties(merged)
    # Normalized Spectrum keys are the source of truth; unrelated extension keys
    # remain untouched for forward compatibility.
    for key, value in normalized.items():
        merged[key] = deepcopy(value)
    return merged


@dataclass
class SetSpectrumLayerState(EditorCommand):
    layer_id: str
    properties: dict
    transform: Transform | None = None
    opacity: float | None = None
    name: str | None = None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        layer = document.layer_map().get(self.layer_id)
        if layer is None or layer.type != "spectrum":
            raise CommandError("Layer Spectrum tidak ditemukan.")
        if layer.locked:
            raise CommandError("Layer Spectrum terkunci tidak dapat diubah.")
        old = SpectrumLayerSnapshot(
            deepcopy(layer.properties),
            deepcopy(layer.transform),
            float(layer.opacity),
            layer.name,
        )
        merged = _merged_properties(layer.properties, self.properties)
        replacement_transform = deepcopy(self.transform) if self.transform is not None else deepcopy(layer.transform)
        replacement_transform.validate()
        replacement_opacity = layer.opacity if self.opacity is None else float(self.opacity)
        if not 0.0 <= replacement_opacity <= 1.0:
            raise CommandError("Opacity Spectrum harus 0..1.")
        layer.properties = merged
        layer.transform = replacement_transform
        layer.opacity = replacement_opacity
        if self.name is not None:
            layer.name = str(self.name)
        elif normalize_spectrum_properties(merged)["spectrum_type"] == "circular":
            layer.name = "Circular Spectrum"
        else:
            layer.name = "Spectrum"
        return RestoreSpectrumLayerState(self.layer_id, old)


@dataclass
class RestoreSpectrumLayerState(EditorCommand):
    layer_id: str
    snapshot: SpectrumLayerSnapshot

    def apply(self, document: ProjectDocument) -> EditorCommand:
        layer = document.layer_map().get(self.layer_id)
        if layer is None or layer.type != "spectrum":
            raise CommandError("Layer Spectrum tidak ditemukan.")
        current = SpectrumLayerSnapshot(
            deepcopy(layer.properties), deepcopy(layer.transform), float(layer.opacity), layer.name
        )
        layer.properties = deepcopy(self.snapshot.properties)
        layer.transform = deepcopy(self.snapshot.transform)
        layer.opacity = float(self.snapshot.opacity)
        layer.name = self.snapshot.name
        layer.validate()
        return RestoreSpectrumLayerState(self.layer_id, current)


def preset_properties(preset_id: str, current: dict | None = None) -> dict:
    try:
        preset = STEP08_PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError("Preset Spectrum tidak ditemukan.") from exc
    if not bool(preset.get("supported")):
        raise ValueError(str(preset.get("reason") or "Preset belum didukung renderer final."))
    requested = dict(preset.get("properties", {}))
    requested["preset"] = preset_id
    return _merged_properties(dict(current or {}), requested)


def build_preset_command(document: ProjectDocument, layer_id: str, preset_id: str) -> SetSpectrumLayerState:
    layer = document.layer_map().get(layer_id)
    if layer is None or layer.type != "spectrum":
        raise ValueError("Layer Spectrum tidak ditemukan.")
    properties = preset_properties(preset_id, layer.properties)
    spectrum_type = normalize_spectrum_properties(properties)["spectrum_type"]
    geometry = spectrum_geometry(document, layer)
    transform = transform_from_geometry(
        document,
        spectrum_type,
        center_x_px=geometry.center_x_px,
        center_y_px=geometry.center_y_px,
        size_ratio=geometry.size_ratio,
        rotation=layer.transform.rotation,
    )
    return SetSpectrumLayerState(layer_id, properties, transform=transform)


def build_type_command(document: ProjectDocument, layer_id: str, spectrum_type: str) -> SetSpectrumLayerState:
    layer = document.layer_map().get(layer_id)
    if layer is None or layer.type != "spectrum":
        raise ValueError("Layer Spectrum tidak ditemukan.")
    current = normalize_spectrum_properties(layer.properties)
    style = style_for_spectrum_type(spectrum_type, current["style"])
    geometry = spectrum_geometry(document, layer)
    transform = transform_from_geometry(
        document,
        spectrum_type,
        center_x_px=geometry.center_x_px,
        center_y_px=geometry.center_y_px,
        size_ratio=geometry.size_ratio,
        rotation=layer.transform.rotation,
    )
    return SetSpectrumLayerState(
        layer_id,
        {"spectrum_type": spectrum_type, "style": style, "preset": ""},
        transform=transform,
    )


def build_apply_to_all_commands(
    document: ProjectDocument,
    source_layer_id: str,
    *,
    include_position: bool = True,
) -> tuple[SetSpectrumLayerState, ...]:
    source = document.layer_map().get(source_layer_id)
    if source is None or source.type != "spectrum":
        raise ValueError("Layer Spectrum sumber tidak ditemukan.")
    source_props = normalize_spectrum_properties(source.properties)
    source_geometry = spectrum_geometry(document, source)
    result: list[SetSpectrumLayerState] = []
    for target in spectrum_layers(document):
        if target.layer_id == source_layer_id:
            continue
        if target.locked:
            raise ValueError(f"Target Spectrum '{target.name}' terkunci.")
        target_props = normalize_spectrum_properties(target.properties)
        # Audio binding belongs to each target. Never copy the source identity.
        requested = {key: deepcopy(source_props[key]) for key in STEP08_STYLE_KEYS if key in source_props}
        requested["audio_binding"] = target_props["audio_binding"]
        if include_position:
            target_transform = transform_from_geometry(
                document,
                source_props["spectrum_type"],
                center_x_px=source_geometry.center_x_px,
                center_y_px=source_geometry.center_y_px,
                size_ratio=source_geometry.size_ratio,
                rotation=source.transform.rotation,
            )
        else:
            target_transform = deepcopy(target.transform)
        result.append(
            SetSpectrumLayerState(
                target.layer_id,
                requested,
                transform=target_transform,
                opacity=source.opacity,
            )
        )
    return tuple(result)


def normalize_spectrum_layer(document: ProjectDocument, layer_id: str) -> SetSpectrumLayerState:
    layer = document.layer_map().get(layer_id)
    if layer is None or layer.type != "spectrum":
        raise ValueError("Layer Spectrum tidak ditemukan.")
    return SetSpectrumLayerState(layer.layer_id, normalize_spectrum_properties(layer.properties))
