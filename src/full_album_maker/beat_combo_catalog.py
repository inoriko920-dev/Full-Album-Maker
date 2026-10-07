from __future__ import annotations

from dataclasses import dataclass

from .advanced_motion_contract import AdvancedMotionPreset, motion_supported_for_layer
from .beat_layer_capabilities import preset_supported_for_layer
from .visual_binding_contract import CoreBeatPreset


@dataclass(frozen=True)
class BeatComboDefinition:
    combo_id: str
    label: str
    visual_preset: CoreBeatPreset
    visual_intensity: float
    motion_preset: AdvancedMotionPreset
    motion_intensity: float
    description: str
    ai_aliases: tuple[str, ...] = ()

    def payload(self) -> dict:
        return {
            "enabled": True,
            "presets": [self.visual_preset.value],
            "intensity": float(self.visual_intensity),
            "motion_preset": self.motion_preset.value,
            "motion_intensity": float(self.motion_intensity),
        }


def _c(
    combo_id: str,
    label: str,
    visual: CoreBeatPreset,
    visual_intensity: float,
    motion: AdvancedMotionPreset,
    motion_intensity: float,
    description: str,
    aliases: tuple[str, ...] = (),
) -> BeatComboDefinition:
    return BeatComboDefinition(
        combo_id, label, visual, float(visual_intensity), motion,
        float(motion_intensity), description, tuple(aliases)
    )


BEAT_COMBO_CATALOG: dict[str, BeatComboDefinition] = {
    "club_impact": _c(
        "club_impact", "Club Impact", CoreBeatPreset.CLUB_PUNCH, 1.10,
        AdvancedMotionPreset.CAMERA_SHAKE, .75, "EDM/club punch dengan shake.",
        ("club impact", "edm impact", "club shake"),
    ),
    "bass_rider": _c(
        "bass_rider", "Bass Rider", CoreBeatPreset.BASS_PUNCH, 1.05,
        AdvancedMotionPreset.BASS_SWAY, .85, "Bass punch dengan sway kiri-kanan.",
        ("bass rider", "bass sway combo", "hiphop motion"),
    ),
    "neon_kick": _c(
        "neon_kick", "Neon Kick", CoreBeatPreset.STRONG_GLOW, .95,
        AdvancedMotionPreset.FOUR_WAY_KICK, .75, "Strong glow dengan arah kick empat sisi.",
        ("neon kick", "four way neon", "neon punch"),
    ),
    "clean_bounce": _c(
        "clean_bounce", "Clean Bounce", CoreBeatPreset.BEAT_ZOOM, .80,
        AdvancedMotionPreset.BEAT_BOUNCE, .70, "Beat zoom bersih dengan bounce.",
        ("clean bounce", "pop bounce", "beat bounce combo"),
    ),
    "cinematic_spark": _c(
        "cinematic_spark", "Cinematic Spark", CoreBeatPreset.CINEMATIC_SWELL, .80,
        AdvancedMotionPreset.SPARK_BURST, .65, "Swell dramatis dengan spark accent.",
        ("cinematic spark", "dramatic spark", "cinematic particles"),
    ),
    "remix_wobble": _c(
        "remix_wobble", "Remix Wobble", CoreBeatPreset.CLUB_PUNCH, 1.05,
        AdvancedMotionPreset.ALTERNATING_WOBBLE, .70, "Club punch dengan wobble bergantian.",
        ("remix wobble", "dangdut wobble", "koplo wobble"),
    ),
    "rock_shake": _c(
        "rock_shake", "Rock Shake", CoreBeatPreset.BASS_PUNCH, .95,
        AdvancedMotionPreset.CAMERA_SHAKE, .65, "Bass punch dengan shake yang terkendali.",
        ("rock shake", "rock impact", "guncang rock"),
    ),
    "ambient_breathe": _c(
        "ambient_breathe", "Ambient Breathe", CoreBeatPreset.ENERGY_GLOW, .65,
        AdvancedMotionPreset.BEAT_BOUNCE, .25, "Energy glow dengan bounce sangat lembut.",
        ("ambient breathe", "ambient bounce", "soft breathe"),
    ),
}


def combo_definition(combo_id: str) -> BeatComboDefinition:
    key = str(combo_id).strip()
    try:
        return BEAT_COMBO_CATALOG[key]
    except KeyError as exc:
        raise KeyError(combo_id) from exc


def combo_supported_for_layer(layer, combo: BeatComboDefinition | str) -> bool:
    definition = combo_definition(combo) if isinstance(combo, str) else combo
    return (
        preset_supported_for_layer(layer, definition.visual_preset)
        and motion_supported_for_layer(layer, definition.motion_preset)
    )


def supported_combos_for_layer(layer) -> tuple[BeatComboDefinition, ...]:
    return tuple(
        definition for definition in BEAT_COMBO_CATALOG.values()
        if combo_supported_for_layer(layer, definition)
    )


def matching_combo_id(assignment) -> str | None:
    if assignment is None or len(assignment.presets) != 1 or assignment.motion_preset is None:
        return None
    for combo_id, definition in BEAT_COMBO_CATALOG.items():
        if (
            assignment.presets[0] == definition.visual_preset
            and abs(float(assignment.intensity) - definition.visual_intensity) <= 1e-9
            and assignment.motion_preset == definition.motion_preset
            and abs(float(assignment.motion_intensity) - definition.motion_intensity) <= 1e-9
        ):
            return combo_id
    return None


def validate_combo_catalog() -> None:
    if len(BEAT_COMBO_CATALOG) != 8:
        raise ValueError("STEP13 requires exactly 8 Beat combo definitions")
    seen_labels=set()
    for key, definition in BEAT_COMBO_CATALOG.items():
        if key != definition.combo_id or not key:
            raise ValueError("Beat combo id mismatch")
        if definition.label in seen_labels or not definition.label.strip():
            raise ValueError("Beat combo labels must be unique and non-empty")
        seen_labels.add(definition.label)
        if not 0.0 <= definition.visual_intensity <= 2.0:
            raise ValueError("Beat combo visual intensity invalid")
        if not 0.0 <= definition.motion_intensity <= 2.0:
            raise ValueError("Beat combo motion intensity invalid")


validate_combo_catalog()
