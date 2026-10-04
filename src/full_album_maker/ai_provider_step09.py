from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Protocol
from urllib.parse import quote

from .ai_action_registry_step09 import (
    ACTION_SPECS,
    required_permissions_for_actions,
)
from .ai_agent_core_step09 import (
    AgentActionCall,
    AgentContextSnapshot,
    AgentPlan,
    ProviderInterpretation,
    deterministic_plan_id,
)
from .key_pool import GeminiKeyPool


class AgentProviderError(RuntimeError):
    pass


class AgentPlanProvider(Protocol):
    provider_id: str

    def interpret(
        self,
        prompt: str,
        context: AgentContextSnapshot,
    ) -> ProviderInterpretation: ...


def _normalize(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _media_stem(name: object) -> str:
    return _normalize(Path(str(name or "")).stem)


def _summary(prompt: str) -> str:
    return " ".join(str(prompt).split())[:500]


def _scope_from_actions(
    actions: tuple[AgentActionCall, ...],
    context: AgentContextSnapshot,
) -> tuple[str, ...]:
    ordered: list[str] = []
    for action in actions:
        values = action.args.get("song_ids")
        if isinstance(values, list):
            for value in values:
                song_id = str(value)
                if song_id and song_id not in ordered:
                    ordered.append(song_id)
        one = str(action.args.get("song_id", "") or "")
        if one and one not in ordered:
            ordered.append(one)
    if ordered:
        return tuple(ordered)
    return tuple(context.selected_song_ids)


def _build_plan(
    prompt: str,
    context: AgentContextSnapshot,
    actions: tuple[AgentActionCall, ...],
    *,
    provider: str,
) -> AgentPlan:
    required = required_permissions_for_actions(actions)
    scope = _scope_from_actions(actions, context)
    plan = AgentPlan(
        plan_id=deterministic_plan_id(
            project_id=context.project_id,
            revision=context.revision,
            context_fingerprint=context.fingerprint,
            prompt=prompt,
            actions=actions,
        ),
        project_id=context.project_id,
        expected_revision=context.revision,
        context_fingerprint=context.fingerprint,
        prompt_summary=_summary(prompt),
        scope_song_ids=scope,
        actions=actions,
        required_permissions=required,
        provider=provider,
    )
    plan.validate()
    return plan


class MockStep09Provider:
    """Deterministic provider for golden tests and offline/manual QA.

    It intentionally supports the mandatory STEP09 fixture only. "Visual yang
    cocok" means an exact normalized song-title <-> video filename-stem match.
    Missing or duplicate matches produce clarification instead of guessing.
    """

    provider_id = "mock"

    def interpret(
        self,
        prompt: str,
        context: AgentContextSnapshot,
    ) -> ProviderInterpretation:
        context.validate()
        normalized = _normalize(prompt)
        required_terms = ("20", "visual", "slowmo", "0 5", "susun", "timeline")
        if not all(term in normalized for term in required_terms):
            return ProviderInterpretation(
                message="MOCK STEP09 hanya menjalankan fixture golden deterministic.",
                clarification=(
                    "Gunakan fixture: pilih 20 lagu, visual exact-match, slowmo 0,5x, lalu susun timeline."
                ),
            )

        songs_by_id = {
            str(item.get("song_id", "")): item
            for item in context.payload.get("songs", [])
            if isinstance(item, dict) and item.get("song_id")
        }
        if context.selected_song_ids:
            candidate_ids = [song_id for song_id in context.selected_song_ids if song_id in songs_by_id]
            if len(candidate_ids) < 20:
                return ProviderInterpretation(
                    message="Pilihan lagu belum cukup untuk fixture golden.",
                    clarification=f"Pilih minimal 20 lagu; context saat ini hanya {len(candidate_ids)} lagu.",
                )
            chosen_ids = tuple(candidate_ids[:20])
        else:
            candidate_ids = [str(item.get("song_id", "")) for item in context.payload.get("songs", []) if isinstance(item, dict)]
            candidate_ids = [song_id for song_id in candidate_ids if song_id]
            if len(candidate_ids) < 20:
                return ProviderInterpretation(
                    message="Project context belum memuat 20 lagu.",
                    clarification=f"Fixture golden membutuhkan 20 lagu; context memuat {len(candidate_ids)}.",
                )
            chosen_ids = tuple(candidate_ids[:20])

        allowed_media = set(context.allowed_media_ids)
        videos: dict[str, list[dict[str, Any]]] = {}
        for item in context.payload.get("media_candidates", []):
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id", ""))
            if asset_id not in allowed_media or str(item.get("kind", "")) != "video":
                continue
            key = _media_stem(item.get("name", ""))
            if key:
                videos.setdefault(key, []).append(item)

        matches: list[tuple[str, str]] = []
        problems: list[str] = []
        for song_id in chosen_ids:
            song = songs_by_id[song_id]
            key = _normalize(song.get("title", ""))
            candidates = videos.get(key, [])
            if len(candidates) != 1:
                title = str(song.get("title", "Tanpa judul"))[:80]
                problems.append(
                    f"{title}: {'tidak ada exact-match video' if not candidates else 'lebih dari satu exact-match video'}"
                )
                continue
            matches.append((song_id, str(candidates[0]["asset_id"])))

        if problems:
            return ProviderInterpretation(
                message="Pencocokan visual tidak aman untuk dijalankan otomatis.",
                clarification="; ".join(problems[:6]),
            )

        actions = tuple(
            AgentActionCall(
                "set_song_visual",
                {"song_ids": [song_id], "asset_id": asset_id},
            )
            for song_id, asset_id in matches
        ) + (
            AgentActionCall(
                "set_song_video_speed",
                {"song_ids": list(chosen_ids), "speed": 0.5},
            ),
            AgentActionCall("auto_arrange_timeline", {}),
        )
        plan = _build_plan(prompt, context, actions, provider=self.provider_id)
        return ProviderInterpretation(
            message=(
                "Rencana siap: 20 lagu dipasangkan ke 20 video exact-match, "
                "Visual video 0,5x, lalu Auto Susun Timeline."
            ),
            plan=plan,
        )


def _obj(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = list(required)
    return result


STEP09_GEMINI_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "set_song_visual",
        "description": "Pasang satu image/video asset yang ada di permission_boundary ke satu atau beberapa song_id dalam scope.",
        "parameters": _obj(
            {
                "song_ids": {"type": "array", "items": {"type": "string"}},
                "asset_id": {"type": "string"},
            },
            ("song_ids", "asset_id"),
        ),
    },
    {
        "name": "set_song_cover",
        "description": "Pasang image cover yang diizinkan ke song_id dalam scope.",
        "parameters": _obj(
            {
                "song_ids": {"type": "array", "items": {"type": "string"}},
                "asset_id": {"type": "string"},
            },
            ("song_ids", "asset_id"),
        ),
    },
    {
        "name": "set_song_video_speed",
        "description": "Atur playback speed Visual video saja. 0.5 berarti slowmo 50%; audio tidak berubah.",
        "parameters": _obj(
            {
                "song_ids": {"type": "array", "items": {"type": "string"}},
                "speed": {"type": "number", "minimum": 0.25, "maximum": 4.0},
            },
            ("song_ids", "speed"),
        ),
    },
    {
        "name": "auto_arrange_timeline",
        "description": "Jalankan Auto Susun lokal; jangan mengarang timestamp sendiri.",
        "parameters": _obj(
            {"background_fit": {"type": "string", "enum": ["fit", "fill", "fit_blur"]}}
        ),
    },
    {
        "name": "set_timeline_mode",
        "description": "Ubah Timeline Packed/Free bila pengguna meminta.",
        "parameters": _obj({"mode": {"type": "string", "enum": ["packed", "free"]}}, ("mode",)),
    },
    {
        "name": "set_song_timing",
        "description": "Atur posisi/crossfade satu lagu pada Free Timeline hanya dengan angka yang diminta pengguna.",
        "parameters": _obj(
            {
                "song_id": {"type": "string"},
                "start_seconds": {"type": "number"},
                "crossfade_seconds": {"type": "number"},
            },
            ("song_id", "start_seconds"),
        ),
    },
    {
        "name": "reorder_playlist",
        "description": "Atur ulang playlist memakai semua stable song_id tepat satu kali.",
        "parameters": _obj(
            {"song_ids": {"type": "array", "items": {"type": "string"}}},
            ("song_ids",),
        ),
    },
    {
        "name": "apply_template",
        "description": "Terapkan template built-in yang terdaftar di context.",
        "parameters": _obj({"template_id": {"type": "string"}}, ("template_id",)),
    },
    {
        "name": "set_spectrum_preset",
        "description": "Terapkan preset Spectrum parity-safe ke Spectrum layer yang dipilih dalam context.",
        "parameters": _obj(
            {
                "layer_id": {"type": "string"},
                "preset_id": {"type": "string"},
            },
            ("layer_id", "preset_id"),
        ),
    },
)


STEP09_GEMINI_SYSTEM = """Kamu adalah intent planner untuk AI Agent Full Album Maker STEP09.
Bahasa utama Indonesia. Tugasmu hanya menerjemahkan instruksi pengguna menjadi function call dari daftar tool yang diberikan.

Aturan keras:
1. Jangan pernah mengarang ID, path, timestamp, media, lagu, layer, template, atau permission.
2. Gunakan hanya stable ID yang terlihat pada context.
3. Media hanya boleh memakai asset_id dalam permission_boundary.media_asset_ids.
4. Song target hanya boleh memakai song_id dalam context/scope. Jika target ambigu atau tidak cukup data, JANGAN panggil tool; balas satu pertanyaan klarifikasi singkat.
5. Jangan mengklaim perubahan sudah dijalankan. Function call adalah rencana, bukan hasil.
6. Jangan menghitung timing/auto layout sendiri bila pengguna meminta Auto Susun; gunakan auto_arrange_timeline.
7. Slowmo video harus memakai set_song_video_speed. Jangan mengubah audio timing untuk membuat slowmo.
8. Jangan pernah meminta/menampilkan API key, file path, shell command, arbitrary code, render, atau save-template.
9. Bila ada beberapa aksi, keluarkan semua function call dalam urutan dependency logis: assignment sebelum speed, setting sebelum Auto Susun.
10. Jika tidak ada aksi aman yang dapat dibentuk, balas teks klarifikasi tanpa function call.
"""


class GeminiStep09Provider:
    provider_id = "gemini"

    def __init__(
        self,
        pool: GeminiKeyPool,
        model: str = "gemini-3.8-flash",
    ) -> None:
        self.pool = pool
        self.model = str(model).strip() or "gemini-3.8-flash"

    def _url(self) -> str:
        model = quote(self.model, safe="-_.")
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def interpret(
        self,
        prompt: str,
        context: AgentContextSnapshot,
    ) -> ProviderInterpretation:
        context.validate()
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": STEP09_GEMINI_SYSTEM
                        + "\n\nCONTEXT SANITIZED:\n"
                        + json.dumps(context.payload, ensure_ascii=False, separators=(",", ":"))
                    }
                ]
            },
            "contents": [{"role": "user", "parts": [{"text": str(prompt)[:4000]}]}],
            "tools": [{"functionDeclarations": list(STEP09_GEMINI_TOOLS)}],
        }
        response = self.pool.request_json(self._url(), payload)
        candidates = response.get("candidates") or []
        if not candidates:
            raise AgentProviderError("Gemini tidak mengembalikan candidate.")
        content = candidates[0].get("content") or {"parts": []}
        parts = content.get("parts") or []
        actions: list[AgentActionCall] = []
        texts: list[str] = []
        for part in parts:
            if part.get("text"):
                texts.append(str(part["text"]).strip())
            call = part.get("functionCall")
            if not call:
                continue
            name = str(call.get("name", "")).strip()
            if name not in ACTION_SPECS:
                raise AgentProviderError(f"Provider mengembalikan action di luar whitelist STEP09: {name}")
            args = call.get("args") or {}
            if not isinstance(args, dict):
                raise AgentProviderError(f"Argumen provider untuk {name} bukan object.")
            action = AgentActionCall(name, dict(args))
            action.validate()
            actions.append(action)

        message = "\n".join(value for value in texts if value).strip()
        if not actions:
            return ProviderInterpretation(
                message=message or "Rencana belum cukup jelas untuk dibentuk.",
                clarification=message or "Perjelas target lagu/media dan perubahan yang diinginkan.",
            )
        plan = _build_plan(prompt, context, tuple(actions), provider=self.provider_id)
        return ProviderInterpretation(
            message=message or "Rencana aksi siap untuk Preview Diff.",
            plan=plan,
        )
