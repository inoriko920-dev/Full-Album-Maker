from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class AdvancedMotionPreset(str, Enum):
    ALTERNATING_WOBBLE = "alternating_wobble"
    BASS_SWAY = "bass_sway"
    CAMERA_SHAKE = "camera_shake"
    BEAT_BOUNCE = "beat_bounce"
    FOUR_WAY_KICK = "four_way_kick"
    SPARK_BURST = "spark_burst"


@dataclass(frozen=True)
class AdvancedMotionState:
    x_offset_normalized: float = 0.0
    y_offset_normalized: float = 0.0
    rotation_offset_deg: float = 0.0

    def validate(self) -> None:
        ranges={
            "x_offset_normalized":(-0.15,0.15),
            "y_offset_normalized":(-0.15,0.15),
            "rotation_offset_deg":(-12.0,12.0),
        }
        for name,(low,high) in ranges.items():
            value=float(getattr(self,name))
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be in {low}..{high}")


@dataclass(frozen=True)
class MotionPresetDefinition:
    preset: AdvancedMotionPreset
    label: str
    channel: str
    recommended_intensity: float
    text_safe: bool = True


MOTION_PRESET_CATALOG: dict[AdvancedMotionPreset, MotionPresetDefinition] = {
    AdvancedMotionPreset.ALTERNATING_WOBBLE: MotionPresetDefinition(AdvancedMotionPreset.ALTERNATING_WOBBLE,"Alternating Wobble","strong_beat",.85,True),
    AdvancedMotionPreset.BASS_SWAY: MotionPresetDefinition(AdvancedMotionPreset.BASS_SWAY,"Bass Sway","bass",.90,False),
    AdvancedMotionPreset.CAMERA_SHAKE: MotionPresetDefinition(AdvancedMotionPreset.CAMERA_SHAKE,"Camera Shake","strong_beat",.80,False),
    AdvancedMotionPreset.BEAT_BOUNCE: MotionPresetDefinition(AdvancedMotionPreset.BEAT_BOUNCE,"Beat Bounce","beat",.75,True),
    AdvancedMotionPreset.FOUR_WAY_KICK: MotionPresetDefinition(AdvancedMotionPreset.FOUR_WAY_KICK,"Four-Way Kick","strong_beat",.90,False),
    AdvancedMotionPreset.SPARK_BURST: MotionPresetDefinition(AdvancedMotionPreset.SPARK_BURST,"Spark Burst","strong_beat",.85,False),
}


def motion_label(preset: AdvancedMotionPreset | str) -> str:
    try:
        p=preset if isinstance(preset,AdvancedMotionPreset) else AdvancedMotionPreset(str(preset))
    except ValueError as exc:
        raise KeyError(preset) from exc
    return MOTION_PRESET_CATALOG[p].label


def motion_supported_for_layer(layer, preset: AdvancedMotionPreset | str) -> bool:
    try:
        p=preset if isinstance(preset,AdvancedMotionPreset) else AdvancedMotionPreset(str(preset))
    except ValueError:
        return False
    if getattr(layer,"type","") not in {"song_cover","vinyl","background","song_visual","spectrum","text","song_title"}:
        return False
    layer_type=getattr(layer,"type","")
    if layer_type in {"text","song_title"} and not MOTION_PRESET_CATALOG[p].text_safe:
        return False
    if layer_type=="song_visual" and str(getattr(layer,"properties",{}).get("transition","cut")) in {"slide","slide_left","slide_right"}:
        if p in {
            AdvancedMotionPreset.BASS_SWAY,
            AdvancedMotionPreset.CAMERA_SHAKE,
            AdvancedMotionPreset.BEAT_BOUNCE,
            AdvancedMotionPreset.FOUR_WAY_KICK,
        }:
            return False
    if p in {AdvancedMotionPreset.ALTERNATING_WOBBLE,AdvancedMotionPreset.CAMERA_SHAKE}:
        tr=getattr(layer,"transform",None)
        if tr is not None and (abs(float(tr.pivot_x)-0.5)>1e-6 or abs(float(tr.pivot_y)-0.5)>1e-6):
            return False
    return True
