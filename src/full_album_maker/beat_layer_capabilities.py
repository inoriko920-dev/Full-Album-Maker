from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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


_ALL_PRESETS = tuple(CoreBeatPreset)
_TEXT_PRESETS = tuple(p for p in CoreBeatPreset if p != CoreBeatPreset.ROTATION_NUDGE)
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


def beat_capability_for_layer(layer: Layer) -> BeatLayerCapability:
    if layer.type in {"text", "song_title"}:
        return BeatLayerCapability(
            _TEXT_PRESETS,
            BeatRenderLevel.LIMITED,
            "Text/Title memakai drawtext runtime commands; Rotation Nudge belum didukung.",
        )
    if layer.type in _SUPPORTED_VISUAL_TYPES:
        presets = _ALL_PRESETS if _rotation_safe(layer) else tuple(
            p for p in _ALL_PRESETS if p != CoreBeatPreset.ROTATION_NUDGE
        )
        reason = "" if _rotation_safe(layer) else (
            "Rotation Nudge disembunyikan karena membutuhkan base rotation 0° dan center pivot."
        )
        return BeatLayerCapability(presets, BeatRenderLevel.FULL, reason)
    return BeatLayerCapability((), BeatRenderLevel.NONE, "Tipe layer belum memiliki adapter Beat V2.")


def preset_supported_for_layer(layer: Layer, preset: CoreBeatPreset | str) -> bool:
    try:
        selected = preset if isinstance(preset, CoreBeatPreset) else CoreBeatPreset(str(preset))
    except ValueError:
        return False
    return selected in beat_capability_for_layer(layer).supported_presets
