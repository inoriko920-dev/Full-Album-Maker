from __future__ import annotations

from dataclasses import dataclass
import re

from .ai_agent_core_step09 import AgentActionCall, AgentContextSnapshot


@dataclass(frozen=True)
class BeatNLUDecision:
    actions: tuple[AgentActionCall, ...] = ()
    message: str = ""
    clarification: str = ""

    @property
    def handled(self) -> bool:
        return bool(self.actions) or bool(self.clarification)


def _norm(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _contains_phrase(text: str, phrase: str) -> bool:
    p=_norm(phrase)
    if not p:
        return False
    return f" {p} " in f" {text} "


def _beat_context(context: AgentContextSnapshot) -> dict:
    beat=context.payload.get("beat_context")
    return beat if isinstance(beat,dict) else {}


def _layers(context: AgentContextSnapshot) -> list[dict]:
    return [
        item for item in _beat_context(context).get("layers",[])
        if isinstance(item,dict) and str(item.get("layer_id",""))
    ]


def _target_layers(
    context: AgentContextSnapshot,
    *,
    require_assignment: bool=False,
    vinyl_only: bool=False,
    allow_all_explicit: bool=False,
    prompt_norm: str="",
) -> tuple[tuple[str,...], str]:
    layers=_layers(context)
    writable=set(str(x) for x in _beat_context(context).get("writable_layer_ids",[]) if str(x))
    candidates=[]
    for item in layers:
        layer_id=str(item.get("layer_id",""))
        if layer_id not in writable or bool(item.get("locked",False)):
            continue
        if vinyl_only and str(item.get("type",""))!="vinyl":
            continue
        if require_assignment and not item.get("current_presets"):
            continue
        candidates.append(item)

    selected=[item for item in candidates if bool(item.get("selected",False))]
    if selected:
        return tuple(str(item["layer_id"]) for item in selected), ""
    if allow_all_explicit and ("semua" in prompt_norm or "seluruh" in prompt_norm):
        if candidates:
            return tuple(str(item["layer_id"]) for item in candidates), ""
    if len(candidates)==1:
        return (str(candidates[0]["layer_id"]),), ""
    if not candidates:
        return (), "Tidak ada layer yang kompatibel untuk perintah Beat tersebut."
    return (), "Pilih layer target terlebih dahulu, atau sebutkan bahwa perubahan berlaku untuk semua layer Beat yang kompatibel."


def _aliases(entries: list[dict]) -> list[tuple[str,dict]]:
    result=[]
    for item in entries:
        if not isinstance(item,dict):
            continue
        values=[item.get("id",""),item.get("label","")]
        raw_aliases=item.get("aliases",[])
        if isinstance(raw_aliases,list):
            values.extend(raw_aliases)
        for value in values:
            normalized=_norm(value)
            if normalized and (normalized,item) not in result:
                result.append((normalized,item))
    result.sort(key=lambda pair:len(pair[0]),reverse=True)
    return result


def _percent_intensity(prompt: str) -> float | None:
    match=re.search(r"(?<!\d)(\d{1,3})(?:[\.,](\d+))?\s*%",prompt)
    if not match:
        return None
    value=float(match.group(1)+(("." + match.group(2)) if match.group(2) else ""))
    return max(0.0,min(2.0,value/100.0))


def interpret_beat_prompt(prompt: str, context: AgentContextSnapshot) -> BeatNLUDecision | None:
    context.validate()
    beat=_beat_context(context)
    if not beat:
        return None
    raw=str(prompt or "")
    text=_norm(raw)
    if not text:
        return None

    # Project-wide music style intent.
    style_verbs=("pakai","gunakan","terapkan","gaya","cocok")
    style_matches=[]
    for alias,item in _aliases(beat.get("music_styles",[])):
        if _contains_phrase(text,alias):
            style_matches.append(item)
    unique_styles={str(item.get("id","")):item for item in style_matches if str(item.get("id",""))}
    if len(unique_styles)==1 and any(word in text.split() for word in style_verbs):
        item=next(iter(unique_styles.values()))
        action=AgentActionCall("apply_music_style",{"style_id":str(item["id"])})
        action.validate()
        return BeatNLUDecision((action,),f"Gaya Beat {item.get('label',item['id'])} siap dipreview.")

    # Vinyl BPM sync.
    if ("vinyl" in text.split()) and ("bpm" in text.split() or "tempo" in text.split()) and (
        "sinkron" in text.split() or "sinkronkan" in text.split() or "sync" in text.split()
    ):
        ids,clarification=_target_layers(
            context,vinyl_only=True,allow_all_explicit=True,prompt_norm=text
        )
        if clarification:
            return BeatNLUDecision(clarification=clarification,message="Target Vinyl belum unik.")
        action=AgentActionCall(
            "set_vinyl_bpm_sync",
            {"layer_ids":list(ids),"enabled":True,"beats_per_rotation":4.0},
        )
        action.validate()
        return BeatNLUDecision((action,),"Vinyl akan disinkronkan ke BPM dengan 4 beat per putaran.")

    # Explicit disable Beat Animation.
    if ("beat" in text.split()) and any(word in text.split() for word in ("matikan","nonaktifkan","hapus")):
        ids,clarification=_target_layers(
            context,allow_all_explicit=True,prompt_norm=text
        )
        if clarification:
            return BeatNLUDecision(clarification=clarification,message="Target Beat belum unik.")
        action=AgentActionCall("clear_beat_animation",{"layer_ids":list(ids)})
        action.validate()
        return BeatNLUDecision((action,),"Beat Animation akan dinonaktifkan pada target.")

    # Explicit preset alias, optionally with percentage.
    preset_matches=[]
    for alias,item in _aliases(beat.get("preset_catalog",[])):
        if _contains_phrase(text,alias):
            preset_matches.append(item)
    unique_presets={str(item.get("id","")):item for item in preset_matches if str(item.get("id",""))}
    if len(unique_presets)==1:
        item=next(iter(unique_presets.values()))
        ids,clarification=_target_layers(
            context,allow_all_explicit=True,prompt_norm=text
        )
        if clarification:
            return BeatNLUDecision(clarification=clarification,message="Target preset Beat belum unik.")
        intensity=_percent_intensity(raw)
        if intensity is None:
            intensity=1.0
        action=AgentActionCall(
            "set_beat_preset",
            {"layer_ids":list(ids),"preset_id":str(item["id"]),"intensity":float(intensity)},
        )
        action.validate()
        return BeatNLUDecision((action,),f"Preset Beat {item.get('label',item['id'])} siap dipreview.")

    # Qualitative intensity adjustment. Keep the current preset intact.
    positive=None
    if "sedikit lebih kuat" in text:
        positive=.10
    elif "jauh lebih kuat" in text or "sangat lebih kuat" in text or "jauh kuat" in text:
        positive=.50
    elif "lebih kuat" in text or "kuatkan" in text:
        positive=.25
    elif "sedikit lebih lembut" in text or "sedikit lebih pelan" in text:
        positive=-.10
    elif "lebih lembut" in text or "lebih pelan" in text or "kurangi intensity" in text:
        positive=-.25
    if positive is not None:
        ids,clarification=_target_layers(
            context,require_assignment=True,allow_all_explicit=True,prompt_norm=text
        )
        if clarification:
            return BeatNLUDecision(clarification=clarification,message="Target intensity Beat belum unik.")
        action=AgentActionCall(
            "adjust_beat_intensity",
            {"layer_ids":list(ids),"delta":float(positive)},
        )
        action.validate()
        sign="+" if positive>=0 else ""
        return BeatNLUDecision((action,),f"Beat intensity akan diubah {sign}{positive:.2f}.")

    return None
