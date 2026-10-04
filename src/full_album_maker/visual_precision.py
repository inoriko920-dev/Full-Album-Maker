from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .editor_commands import CommandError, EditorCommand
from .editor_models import ProjectDocument
from .song_visuals import normalize_song_visual_properties

VISUAL_SETTINGS_KEY = "song_visual_settings_v1"
MOTIONS = {"static", "ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right"}
TRANSITIONS = {"cut", "fade", "slide", "slide_left", "slide_right"}
MIN_VIDEO_SPEED = 0.25
MAX_VIDEO_SPEED = 4.0
DEFAULT_VIDEO_SPEED = 1.0


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} tidak valid.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} tidak valid.") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"{label} tidak valid.")
    return result


def normalize_song_visual_settings(
    settings: dict[str, Any] | None,
    *,
    fallback_layer_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize the editable per-song Visual contract.

    Older recovered projects stored a single style on the shared `song_visual`
    layer. Those values remain the fallback so STEP06 is additive and does not
    silently rewrite older projects.

    STEP09 prerequisite: ``video_speed`` is a normal Visual-domain property,
    not an AI-only shortcut. It changes only decoded video presentation and
    never audio timing. Older projects default to 1.0x.
    """

    fallback = normalize_song_visual_properties(fallback_layer_properties or {})
    source = dict(settings or {})

    fit = str(source.get("fit", fallback["fit"]))
    if fit not in {"fit", "fill"}:
        raise ValueError("Fit Visual harus fit/fill.")

    crop_x = _number(source.get("crop_x", 0.0), "Crop X")
    crop_y = _number(source.get("crop_y", 0.0), "Crop Y")
    crop_width = _number(source.get("crop_width", 1.0), "Crop Width")
    crop_height = _number(source.get("crop_height", 1.0), "Crop Height")
    if not 0.0 <= crop_x < 1.0 or not 0.0 <= crop_y < 1.0:
        raise ValueError("Posisi Crop harus di dalam 0..1.")
    if not 0.05 <= crop_width <= 1.0 or not 0.05 <= crop_height <= 1.0:
        raise ValueError("Ukuran Crop harus 0.05..1.")
    if crop_x + crop_width > 1.000001 or crop_y + crop_height > 1.000001:
        raise ValueError("Area Crop melewati batas sumber visual.")

    position_x = _number(source.get("position_x", 0.0), "Posisi X")
    position_y = _number(source.get("position_y", 0.0), "Posisi Y")
    if not -1.0 <= position_x <= 1.0 or not -1.0 <= position_y <= 1.0:
        raise ValueError("Posisi Visual harus -1..1.")

    scale = _number(source.get("scale", 1.0), "Skala")
    if not 0.25 <= scale <= 4.0:
        raise ValueError("Skala Visual harus 0.25..4.0.")

    image_motion = str(source.get("image_motion", fallback["image_motion"]))
    if image_motion not in MOTIONS:
        raise ValueError("Motion Visual belum didukung.")
    pan_zoom = source.get("pan_zoom", image_motion != "static")
    if not isinstance(pan_zoom, bool):
        raise ValueError("Pan & Zoom harus boolean.")

    legacy_playback = fallback["video_playback"]
    loop_video = source.get("loop_video", legacy_playback == "loop")
    freeze_end = source.get("freeze_end", legacy_playback == "freeze")
    if not isinstance(loop_video, bool) or not isinstance(freeze_end, bool):
        raise ValueError("Loop/Freeze Visual harus boolean.")
    if loop_video and freeze_end:
        raise ValueError("Loop Video dan Freeze di Akhir tidak boleh aktif bersamaan.")

    video_speed = _number(
        source.get("video_speed", DEFAULT_VIDEO_SPEED),
        "Kecepatan Video",
    )
    if not MIN_VIDEO_SPEED <= video_speed <= MAX_VIDEO_SPEED:
        raise ValueError(
            f"Kecepatan Video harus {MIN_VIDEO_SPEED:g}x..{MAX_VIDEO_SPEED:g}x."
        )

    transition = str(source.get("transition", fallback["transition"]))
    if transition not in TRANSITIONS:
        raise ValueError("Transisi Visual belum didukung.")
    transition_seconds = _number(
        source.get("transition_seconds", fallback["transition_seconds"]),
        "Durasi Transisi",
    )
    if not 0.0 <= transition_seconds <= 5.0:
        raise ValueError("Durasi Transisi harus 0..5 detik.")
    if transition == "cut":
        transition_seconds = 0.0

    return {
        "fit": fit,
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_width": crop_width,
        "crop_height": crop_height,
        "position_x": position_x,
        "position_y": position_y,
        "scale": scale,
        "pan_zoom": pan_zoom,
        "image_motion": image_motion,
        "loop_video": loop_video,
        "freeze_end": freeze_end,
        "video_speed": video_speed,
        # Kept for recovered renderer/API compatibility.
        "video_playback": "loop" if loop_video else "freeze" if freeze_end else "none",
        "transition": transition,
        "transition_seconds": transition_seconds,
    }


def visual_settings_map(document: ProjectDocument) -> dict[str, dict[str, Any]]:
    raw = document.extensions.get(VISUAL_SETTINGS_KEY, {})
    if not isinstance(raw, dict):
        raise ValueError("Metadata Visual per lagu tidak valid.")
    result: dict[str, dict[str, Any]] = {}
    for song_id, settings in raw.items():
        if not isinstance(song_id, str) or not isinstance(settings, dict):
            raise ValueError("Metadata Visual per lagu tidak valid.")
        result[song_id] = deepcopy(settings)
    return result


def song_visual_layer_properties(document: ProjectDocument) -> dict[str, Any]:
    layer = next((item for item in document.layers if item.type == "song_visual"), None)
    return dict(layer.properties) if layer is not None else {}


def visual_settings_for_song(
    document: ProjectDocument,
    song_id: str,
    *,
    fallback_layer_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if song_id not in document.song_map():
        raise ValueError("Lagu tidak ditemukan.")
    mapping = visual_settings_map(document)
    fallback = (
        dict(fallback_layer_properties)
        if fallback_layer_properties is not None
        else song_visual_layer_properties(document)
    )
    return normalize_song_visual_settings(
        mapping.get(song_id), fallback_layer_properties=fallback
    )


def _merge_preserved_speed(
    current: dict[str, Any] | None,
    requested: dict[str, Any],
) -> dict[str, Any]:
    """Keep an existing speed when an older UI payload omits the new field."""

    merged = dict(requested)
    if "video_speed" not in merged and isinstance(current, dict) and "video_speed" in current:
        merged["video_speed"] = current["video_speed"]
    return merged


@dataclass
class RestoreSongVisualSettingsMap(EditorCommand):
    mapping: dict[str, dict[str, Any]]

    def apply(self, document: ProjectDocument) -> EditorCommand:
        current = visual_settings_map(document)
        if self.mapping:
            document.extensions[VISUAL_SETTINGS_KEY] = deepcopy(self.mapping)
        else:
            document.extensions.pop(VISUAL_SETTINGS_KEY, None)
        return RestoreSongVisualSettingsMap(current)


@dataclass
class SetSongVisualSettings(EditorCommand):
    song_id: str
    settings: dict[str, Any]

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if self.song_id not in document.song_map():
            raise CommandError("Lagu tidak ditemukan.")
        old = visual_settings_map(document)
        fallback = song_visual_layer_properties(document)
        requested = _merge_preserved_speed(old.get(self.song_id), dict(self.settings))
        normalized = normalize_song_visual_settings(
            requested, fallback_layer_properties=fallback
        )
        updated = deepcopy(old)
        updated[self.song_id] = normalized
        document.extensions[VISUAL_SETTINGS_KEY] = updated
        return RestoreSongVisualSettingsMap(old)


@dataclass
class ApplySongVisualSettings(EditorCommand):
    song_ids: tuple[str, ...]
    settings: dict[str, Any]

    def __init__(self, song_ids: Iterable[str], settings: dict[str, Any]) -> None:
        unique: list[str] = []
        for song_id in song_ids:
            value = str(song_id)
            if value and value not in unique:
                unique.append(value)
        self.song_ids = tuple(unique)
        self.settings = dict(settings)

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if not self.song_ids:
            raise CommandError("Pilih minimal satu lagu untuk menerapkan Visual.")
        songs = document.song_map()
        missing = [song_id for song_id in self.song_ids if song_id not in songs]
        if missing:
            raise CommandError("Satu atau lebih lagu tidak ditemukan.")
        old = visual_settings_map(document)
        fallback = song_visual_layer_properties(document)
        updated = deepcopy(old)
        for song_id in self.song_ids:
            requested = _merge_preserved_speed(old.get(song_id), dict(self.settings))
            updated[song_id] = normalize_song_visual_settings(
                requested, fallback_layer_properties=fallback
            )
        document.extensions[VISUAL_SETTINGS_KEY] = updated
        return RestoreSongVisualSettingsMap(old)


@dataclass
class SetSongVideoSpeed(EditorCommand):
    """Set presentation speed for one or more assigned video visuals.

    This command is deliberately Visual-domain only. It does not touch audio,
    playlist timing, song duration, or source media. Every target must already
    point at a video asset; mixed image/video requests fail before mutation.
    """

    song_ids: tuple[str, ...]
    speed: float

    def __init__(self, song_ids: Iterable[str], speed: float) -> None:
        unique: list[str] = []
        for song_id in song_ids:
            value = str(song_id)
            if value and value not in unique:
                unique.append(value)
        self.song_ids = tuple(unique)
        self.speed = float(speed)

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if not self.song_ids:
            raise CommandError("Pilih minimal satu lagu untuk slowmo Visual.")
        if not MIN_VIDEO_SPEED <= self.speed <= MAX_VIDEO_SPEED:
            raise CommandError(
                f"Kecepatan Video harus {MIN_VIDEO_SPEED:g}x..{MAX_VIDEO_SPEED:g}x."
            )
        songs = document.song_map()
        assets = document.asset_map()
        for song_id in self.song_ids:
            song = songs.get(song_id)
            if song is None:
                raise CommandError("Satu atau lebih lagu tidak ditemukan.")
            asset = assets.get(song.visual_asset_id or "")
            if asset is None or asset.kind != "video":
                raise CommandError(
                    "Slowmo Visual hanya dapat diterapkan pada lagu yang memiliki sumber Video."
                )

        old = visual_settings_map(document)
        fallback = song_visual_layer_properties(document)
        updated = deepcopy(old)
        for song_id in self.song_ids:
            current = normalize_song_visual_settings(
                updated.get(song_id), fallback_layer_properties=fallback
            )
            current["video_speed"] = self.speed
            updated[song_id] = normalize_song_visual_settings(
                current, fallback_layer_properties=fallback
            )
        document.extensions[VISUAL_SETTINGS_KEY] = updated
        return RestoreSongVisualSettingsMap(old)


def prune_orphan_visual_settings(document: ProjectDocument) -> dict[str, dict[str, Any]]:
    """Pure helper for diagnostics/migration; does not mutate the document."""
    songs = document.song_map()
    return {
        song_id: settings
        for song_id, settings in visual_settings_map(document).items()
        if song_id in songs
    }
