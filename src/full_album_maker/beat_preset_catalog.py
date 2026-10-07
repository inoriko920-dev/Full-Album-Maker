from __future__ import annotations

from dataclasses import dataclass

from .visual_binding_contract import CoreBeatPreset, VisualProperty


@dataclass(frozen=True)
class BeatPresetDefinition:
    preset: CoreBeatPreset
    label: str
    category: str
    description: str
    properties: tuple[VisualProperty, ...]
    recommended_intensity: float
    text_safe: bool
    rotation_required: bool
    ai_aliases: tuple[str, ...]


def _d(
    preset: CoreBeatPreset,
    label: str,
    category: str,
    description: str,
    properties: tuple[VisualProperty, ...],
    recommended_intensity: float = 1.0,
    *,
    text_safe: bool = True,
    rotation_required: bool = False,
    aliases: tuple[str, ...] = (),
) -> BeatPresetDefinition:
    return BeatPresetDefinition(
        preset=preset,
        label=label,
        category=category,
        description=description,
        properties=properties,
        recommended_intensity=float(recommended_intensity),
        text_safe=bool(text_safe),
        rotation_required=bool(rotation_required),
        ai_aliases=tuple(aliases),
    )


P = VisualProperty
BEAT_PRESET_CATALOG: dict[CoreBeatPreset, BeatPresetDefinition] = {
    CoreBeatPreset.SUBTLE_BEAT_PULSE: _d(CoreBeatPreset.SUBTLE_BEAT_PULSE, "Beat Pulse", "pulse", "Scale ringan mengikuti beat.", (P.SCALE_MULTIPLIER,), .75, aliases=("beat pulse","pulse ringan","ikuti beat")),
    CoreBeatPreset.BASS_PULSE: _d(CoreBeatPreset.BASS_PULSE, "Bass Pulse", "bass", "Scale mengikuti bass hit.", (P.SCALE_MULTIPLIER,), .9, aliases=("bass pulse","hentak bass","pulse bass")),
    CoreBeatPreset.STRONG_PUNCH: _d(CoreBeatPreset.STRONG_PUNCH, "Strong Punch", "combo", "Scale, zoom, dan glow pada beat kuat.", (P.SCALE_MULTIPLIER,P.ZOOM_MULTIPLIER,P.GLOW_AMOUNT), 1.0, aliases=("strong punch","hentak kuat","beat punch")),
    CoreBeatPreset.ONSET_FLASH: _d(CoreBeatPreset.ONSET_FLASH, "Onset Flash", "glow", "Glow singkat pada transient.", (P.GLOW_AMOUNT,), .75, aliases=("onset flash","flash beat","transient flash")),
    CoreBeatPreset.ROTATION_NUDGE: _d(CoreBeatPreset.ROTATION_NUDGE, "Rotation Nudge", "rotation", "Rotasi kecil pada beat kuat.", (P.ROTATION_OFFSET_DEG,), .75, text_safe=False, rotation_required=True, aliases=("rotation nudge","putar beat","tilt beat")),
    CoreBeatPreset.ENERGY_BREATHE: _d(CoreBeatPreset.ENERGY_BREATHE, "Energy Breathe", "energy", "Scale dan glow lembut saat energi naik.", (P.SCALE_MULTIPLIER,P.GLOW_AMOUNT), .7, aliases=("energy breathe","napas musik","energy pulse")),
    CoreBeatPreset.BEAT_ZOOM: _d(CoreBeatPreset.BEAT_ZOOM, "Beat Zoom", "zoom", "Zoom ritmis mengikuti beat.", (P.ZOOM_MULTIPLIER,), .85, aliases=("beat zoom","zoom beat","zoom ritmis")),
    CoreBeatPreset.BASS_ZOOM: _d(CoreBeatPreset.BASS_ZOOM, "Bass Zoom", "bass", "Zoom lebih kuat mengikuti bass.", (P.ZOOM_MULTIPLIER,), .9, aliases=("bass zoom","zoom bass","hentak zoom")),
    CoreBeatPreset.GLOW_PUMP: _d(CoreBeatPreset.GLOW_PUMP, "Glow Pump", "glow", "Glow berdenyut mengikuti beat.", (P.GLOW_AMOUNT,), .8, aliases=("glow pump","cahaya beat","glow beat")),
    CoreBeatPreset.BASS_GLOW: _d(CoreBeatPreset.BASS_GLOW, "Bass Glow", "bass", "Glow mengikuti bass hit.", (P.GLOW_AMOUNT,), .9, aliases=("bass glow","glow bass","cahaya bass")),
    CoreBeatPreset.STRONG_GLOW: _d(CoreBeatPreset.STRONG_GLOW, "Strong Glow", "glow", "Accent glow besar pada beat kuat.", (P.GLOW_AMOUNT,), .9, aliases=("strong glow","glow kuat","accent glow")),
    CoreBeatPreset.BEAT_TILT: _d(CoreBeatPreset.BEAT_TILT, "Beat Tilt", "rotation", "Tilt halus mengikuti beat.", (P.ROTATION_OFFSET_DEG,), .65, text_safe=False, rotation_required=True, aliases=("beat tilt","miring beat","tilt ringan")),
    CoreBeatPreset.BASS_TILT: _d(CoreBeatPreset.BASS_TILT, "Bass Tilt", "rotation", "Tilt lebih kuat mengikuti bass.", (P.ROTATION_OFFSET_DEG,), .8, text_safe=False, rotation_required=True, aliases=("bass tilt","miring bass","tilt bass")),
    CoreBeatPreset.ENERGY_ZOOM: _d(CoreBeatPreset.ENERGY_ZOOM, "Energy Zoom", "energy", "Zoom lembut saat energi meningkat.", (P.ZOOM_MULTIPLIER,), .75, aliases=("energy zoom","build up zoom","zoom energi")),
    CoreBeatPreset.ENERGY_GLOW: _d(CoreBeatPreset.ENERGY_GLOW, "Energy Glow", "energy", "Glow atmosfer saat energi meningkat.", (P.GLOW_AMOUNT,), .75, aliases=("energy glow","glow energi","ambient glow")),
    CoreBeatPreset.CLUB_PUNCH: _d(CoreBeatPreset.CLUB_PUNCH, "Club Punch", "combo", "Punch kuat untuk EDM/club.", (P.SCALE_MULTIPLIER,P.ZOOM_MULTIPLIER,P.GLOW_AMOUNT), 1.1, aliases=("edm punch","hentak kuat","club beat","punch edm")),
    CoreBeatPreset.BASS_PUNCH: _d(CoreBeatPreset.BASS_PUNCH, "Bass Punch", "combo", "Scale, zoom, dan glow yang mengikuti bass.", (P.SCALE_MULTIPLIER,P.ZOOM_MULTIPLIER,P.GLOW_AMOUNT), 1.0, aliases=("bass punch","hentak bass","hiphop bass")),
    CoreBeatPreset.CINEMATIC_SWELL: _d(CoreBeatPreset.CINEMATIC_SWELL, "Cinematic Swell", "energy", "Build-up lembut dan dramatis.", (P.SCALE_MULTIPLIER,P.ZOOM_MULTIPLIER,P.GLOW_AMOUNT), .75, aliases=("cinematic","naik perlahan","dramatic swell","cinematic swell")),
}


def preset_definition(preset: CoreBeatPreset | str) -> BeatPresetDefinition:
    try:
        selected = preset if isinstance(preset, CoreBeatPreset) else CoreBeatPreset(str(preset))
    except ValueError as exc:
        raise KeyError(preset) from exc
    return BEAT_PRESET_CATALOG[selected]


def preset_label(preset: CoreBeatPreset | str) -> str:
    return preset_definition(preset).label


def catalog_presets() -> tuple[CoreBeatPreset, ...]:
    return tuple(CoreBeatPreset)


def validate_catalog() -> None:
    missing = set(CoreBeatPreset) - set(BEAT_PRESET_CATALOG)
    extra = set(BEAT_PRESET_CATALOG) - set(CoreBeatPreset)
    if missing or extra:
        raise ValueError(f"Beat preset catalog mismatch: missing={missing}, extra={extra}")
    labels=set()
    for preset in CoreBeatPreset:
        d=BEAT_PRESET_CATALOG[preset]
        if not d.label.strip() or d.label in labels:
            raise ValueError("Beat preset labels must be non-empty and unique")
        labels.add(d.label)
        if not 0.0 <= d.recommended_intensity <= 2.0:
            raise ValueError(f"recommended intensity invalid: {preset.value}")


validate_catalog()
