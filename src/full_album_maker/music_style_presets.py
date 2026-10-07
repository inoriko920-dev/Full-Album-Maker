from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum

from .beat_layer_capabilities import preset_supported_for_layer
from .editor_models import ProjectDocument
from .visual_binding_contract import CoreBeatPreset


class MusicStylePreset(str, Enum):
    CHILL = "chill"
    AMBIENT = "ambient"
    POP = "pop"
    ROCK = "rock"
    EDM = "edm"
    HIP_HOP = "hip_hop"
    DANGDUT_REMIX = "dangdut_remix"
    ACOUSTIC = "acoustic"
    CINEMATIC = "cinematic"


@dataclass(frozen=True)
class LayerStyleRecipe:
    preset: CoreBeatPreset
    intensity: float
    bpm_sync: bool = False
    beats_per_rotation: float = 4.0


@dataclass(frozen=True)
class MusicStyleDefinition:
    style: MusicStylePreset
    label: str
    description: str
    recipes: dict[str, LayerStyleRecipe]
    ai_aliases: tuple[str, ...]


@dataclass(frozen=True)
class MusicStyleApplyReport:
    style: MusicStylePreset
    applied_layers: int
    skipped_locked: int
    skipped_incompatible: int


def _r(preset: CoreBeatPreset, intensity: float, *, bpm_sync: bool=False, bpr: float=4.0) -> LayerStyleRecipe:
    return LayerStyleRecipe(preset, float(intensity), bool(bpm_sync), float(bpr))


def _recipes(cover, visual, spectrum, vinyl, title):
    return {
        "song_cover": cover,
        "background": visual,
        "song_visual": visual,
        "spectrum": spectrum,
        "vinyl": vinyl,
        "text": title,
        "song_title": title,
    }


MUSIC_STYLE_CATALOG: dict[MusicStylePreset, MusicStyleDefinition] = {
    MusicStylePreset.CHILL: MusicStyleDefinition(MusicStylePreset.CHILL,"Chill","Gerak lembut dan hangat.",_recipes(_r(CoreBeatPreset.ENERGY_BREATHE,.70),_r(CoreBeatPreset.CINEMATIC_SWELL,.45),_r(CoreBeatPreset.GLOW_PUMP,.40),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.45),_r(CoreBeatPreset.ONSET_FLASH,.30)),("chill","santai","lofi lembut")),
    MusicStylePreset.AMBIENT: MusicStyleDefinition(MusicStylePreset.AMBIENT,"Ambient","Atmosfer tenang dan perlahan.",_recipes(_r(CoreBeatPreset.CINEMATIC_SWELL,.55),_r(CoreBeatPreset.ENERGY_GLOW,.40),_r(CoreBeatPreset.ENERGY_BREATHE,.35),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.30),_r(CoreBeatPreset.ENERGY_GLOW,.30)),("ambient","atmosfer","tenang")),
    MusicStylePreset.POP: MusicStyleDefinition(MusicStylePreset.POP,"Pop","Beat jelas namun tetap bersih.",_recipes(_r(CoreBeatPreset.BEAT_ZOOM,.85),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.50),_r(CoreBeatPreset.GLOW_PUMP,.75),_r(CoreBeatPreset.BASS_PULSE,.70),_r(CoreBeatPreset.ONSET_FLASH,.50)),("pop","modern pop","beat pop")),
    MusicStylePreset.ROCK: MusicStyleDefinition(MusicStylePreset.ROCK,"Rock","Bass dan accent lebih tegas.",_recipes(_r(CoreBeatPreset.BASS_PUNCH,1.00),_r(CoreBeatPreset.BEAT_TILT,.45),_r(CoreBeatPreset.STRONG_GLOW,.85),_r(CoreBeatPreset.STRONG_PUNCH,.80),_r(CoreBeatPreset.BEAT_ZOOM,.65)),("rock","rock punch","gitar rock")),
    MusicStylePreset.EDM: MusicStyleDefinition(MusicStylePreset.EDM,"EDM / Club","Punch kuat dan glow club.",_recipes(_r(CoreBeatPreset.CLUB_PUNCH,1.15),_r(CoreBeatPreset.STRONG_GLOW,.80),_r(CoreBeatPreset.BASS_PUNCH,1.10),_r(CoreBeatPreset.BASS_PUNCH,1.00,bpm_sync=True),_r(CoreBeatPreset.ONSET_FLASH,.65)),("edm","club","dance","electronic")),
    MusicStylePreset.HIP_HOP: MusicStyleDefinition(MusicStylePreset.HIP_HOP,"Hip-Hop","Low-end dominan dan punch bass.",_recipes(_r(CoreBeatPreset.BASS_PUNCH,1.05),_r(CoreBeatPreset.BASS_ZOOM,.55),_r(CoreBeatPreset.BASS_GLOW,.90),_r(CoreBeatPreset.BASS_PULSE,.85,bpm_sync=True),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.45)),("hip hop","hiphop","rap beat")),
    MusicStylePreset.DANGDUT_REMIX: MusicStyleDefinition(MusicStylePreset.DANGDUT_REMIX,"Dangdut / Remix","Hentakan kuat cocok remix Indonesia.",_recipes(_r(CoreBeatPreset.CLUB_PUNCH,1.10),_r(CoreBeatPreset.BEAT_ZOOM,.65),_r(CoreBeatPreset.BASS_PUNCH,1.05),_r(CoreBeatPreset.BASS_PULSE,1.00,bpm_sync=True),_r(CoreBeatPreset.ONSET_FLASH,.55)),("dangdut remix","koplo remix","remix indonesia")),
    MusicStylePreset.ACOUSTIC: MusicStyleDefinition(MusicStylePreset.ACOUSTIC,"Acoustic","Respons tipis dan natural.",_recipes(_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.45),_r(CoreBeatPreset.ENERGY_BREATHE,.30),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.30),_r(CoreBeatPreset.SUBTLE_BEAT_PULSE,.30),_r(CoreBeatPreset.ONSET_FLASH,.25)),("acoustic","akustik","natural")),
    MusicStylePreset.CINEMATIC: MusicStyleDefinition(MusicStylePreset.CINEMATIC,"Cinematic","Swell dramatis dan atmosfer.",_recipes(_r(CoreBeatPreset.CINEMATIC_SWELL,.75),_r(CoreBeatPreset.CINEMATIC_SWELL,.65),_r(CoreBeatPreset.ENERGY_GLOW,.45),_r(CoreBeatPreset.ENERGY_BREATHE,.35),_r(CoreBeatPreset.ENERGY_GLOW,.40)),("cinematic","dramatic","film score")),
}


def style_definition(style: MusicStylePreset | str) -> MusicStyleDefinition:
    try:
        selected=style if isinstance(style,MusicStylePreset) else MusicStylePreset(str(style))
    except ValueError as exc:
        raise KeyError(style) from exc
    return MUSIC_STYLE_CATALOG[selected]


def apply_music_style(document: ProjectDocument, style: MusicStylePreset | str) -> tuple[ProjectDocument, MusicStyleApplyReport]:
    definition=style_definition(style)
    replacement=document.clone()
    track_map={t.track_id:t for t in replacement.tracks}
    applied=locked=incompatible=0
    for layer in replacement.layers:
        track=track_map.get(layer.track_id)
        if not layer.enabled or track is None or not track.enabled:
            continue
        recipe=definition.recipes.get(layer.type)
        if recipe is None:
            continue
        if layer.locked:
            locked += 1
            continue
        if not preset_supported_for_layer(layer, recipe.preset):
            incompatible += 1
            continue
        layer.animation=deepcopy(layer.animation)
        layer.animation["beat_v1"]={"enabled":True,"presets":[recipe.preset.value],"intensity":float(recipe.intensity)}
        if layer.type=="vinyl":
            layer.properties=deepcopy(layer.properties)
            layer.properties["bpm_sync"]=bool(recipe.bpm_sync)
            layer.properties["beats_per_rotation"]=float(recipe.beats_per_rotation)
            layer.properties.setdefault("bpm_sync_min_confidence",0.55)
        applied += 1
    replacement.validate()
    return replacement, MusicStyleApplyReport(definition.style,applied,locked,incompatible)


def validate_music_styles() -> None:
    if len(MUSIC_STYLE_CATALOG)!=len(MusicStylePreset):
        raise ValueError("music style catalog incomplete")
    for style in MusicStylePreset:
        definition=MUSIC_STYLE_CATALOG[style]
        if not definition.label.strip():
            raise ValueError("music style label is required")
        for recipe in definition.recipes.values():
            if not isinstance(recipe.preset,CoreBeatPreset) or not 0.0<=recipe.intensity<=2.0:
                raise ValueError(f"invalid music style recipe: {style.value}")


validate_music_styles()
