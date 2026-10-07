from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .beat_preset_catalog import preset_definition
from .editor_models import Layer
from .visual_binding_contract import CoreBeatPreset


class BeatRenderLevel(str, Enum):
    FULL = "FULL"
    LIMITED = "LIMITED"
    NONE = "NONE"


@dataclass(frozen=True)
class BeatLayerCapability:
    supported_presets: tuple[CoreBeatPreset, ...]
    final_render_level: BeatRenderLevel
    reason: str = ""

    @property
    def supported(self) -> bool:
        return bool(self.supported_presets) and self.final_render_level != BeatRenderLevel.NONE


_SUPPORTED_VISUAL_TYPES = {
    "song_cover",
    "vinyl",
    "background",
    "song_visual",
    "spectrum",
}


def _rotation_safe(layer: Layer) -> bool:
    return (
        abs(float(layer.transform.rotation)) <= 1e-6
        and abs(float(layer.transform.pivot_x) - 0.5) <= 1e-6
        and abs(float(layer.transform.pivot_y) - 0.5) <= 1e-6
    )


def _supported_for(layer: Layer) -> tuple[CoreBeatPreset, ...]:
    rotation_safe = _rotation_safe(layer)
    values: list[CoreBeatPreset] = []
    for preset in CoreBeatPreset:
        definition = preset_definition(preset)
        if layer.type in {"text", "song_title"} and not definition.text_safe:
            continue
        if definition.rotation_required and not rotation_safe:
            continue
        values.append(preset)
    return tuple(values)


def beat_capability_for_layer(layer: Layer) -> BeatLayerCapability:
    if layer.type in {"text", "song_title"}:
        return BeatLayerCapability(
            _supported_for(layer),
            BeatRenderLevel.LIMITED,
            "Text/Title memakai drawtext runtime commands; preset rotasi belum didukung.",
        )
    if layer.type in _SUPPORTED_VISUAL_TYPES:
        presets = _supported_for(layer)
        rotation_missing = any(
            preset_definition(p).rotation_required for p in CoreBeatPreset
        ) and not _rotation_safe(layer)
        reason = (
            "Preset rotasi disembunyikan karena membutuhkan base rotation 0° dan center pivot."
            if rotation_missing else ""
        )
        return BeatLayerCapability(presets, BeatRenderLevel.FULL, reason)
    return BeatLayerCapability((), BeatRenderLevel.NONE, "Tipe layer belum memiliki adapter Beat V2.")


def preset_supported_for_layer(layer: Layer, preset: CoreBeatPreset | str) -> bool:
    try:
        selected = preset if isinstance(preset, CoreBeatPreset) else CoreBeatPreset(str(preset))
    except ValueError:
        return False
    return selected in beat_capability_for_layer(layer).supported_presets
