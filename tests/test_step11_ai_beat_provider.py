from __future__ import annotations

from full_album_maker.ai_agent_core_step09 import build_agent_context_snapshot
from full_album_maker.ai_provider_step09 import (
    GeminiStep09Provider,
    MockStep09Provider,
    STEP09_GEMINI_SYSTEM,
    STEP11_BEAT_GEMINI_TOOLS,
)
from full_album_maker.album_visuals import make_song_cover_layer
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


class FailPool:
    def request_json(self,*args,**kwargs):
        raise AssertionError("network/provider should not be called for local Beat fast-path")


def _context(selected=True):
    doc=ProjectDocument.new_empty("STEP11 provider")
    audio=MediaAsset(kind="audio",locator="song.wav",original_name="song.wav",source_duration_tick=TIMEBASE)
    image=MediaAsset(kind="image",locator="cover.png",original_name="cover.png")
    doc.media.extend([audio,image])
    doc.playlist.entries.append(SongInstance(
        asset_id=audio.asset_id,source_out_tick=TIMEBASE,display_title="Song",
        cover_asset_id=image.asset_id,
    ))
    cover=make_song_cover_layer(doc.tracks[0].track_id,1,fallback_asset_id=image.asset_id)
    doc.layers.append(cover); doc.validate()
    ctx=build_agent_context_snapshot(
        doc,
        selected_layer_ids=(cover.layer_id,) if selected else (),
        enabled_contexts=("beat",),
        user_text="beat",
    )
    return doc,cover,ctx


def test_gemini_declares_exactly_five_step11_beat_tools():
    names={item["name"] for item in STEP11_BEAT_GEMINI_TOOLS}
    assert names=={
        "set_beat_preset","adjust_beat_intensity","clear_beat_animation",
        "apply_music_style","set_vinyl_bpm_sync",
    }


def test_gemini_system_contains_registry_and_no_analyzer_rules():
    lowered=STEP09_GEMINI_SYSTEM.casefold()
    assert "beat_context" in lowered
    assert "jangan pernah membuat bpm" in lowered
    assert "apply_music_style" in lowered
    assert "adjust_beat_intensity" in lowered


def test_gemini_provider_uses_local_fast_path_without_network():
    doc,cover,ctx=_context()
    provider=GeminiStep09Provider(FailPool())
    result=provider.interpret("Pakai Club Punch 120% di layer ini",ctx)
    assert result.plan is not None
    assert result.plan.provider=="local-beat"
    assert result.plan.actions[0].name=="set_beat_preset"
    assert result.plan.required_permissions==("beat.write",)


def test_mock_provider_also_supports_beat_fast_path():
    doc,cover,ctx=_context()
    result=MockStep09Provider().interpret("Buat animasinya cocok untuk EDM",ctx)
    assert result.plan is not None
    assert result.plan.actions[0].name=="apply_music_style"
    assert result.plan.required_permissions==("beat.write",)
