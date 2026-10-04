from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence

from .atomic_io import atomic_write_text
from .custom_template_builder import (
    CustomTemplate,
    CustomTemplateStore,
    SetCustomTemplateMarker,
    build_custom_template_layers,
    capture_custom_template,
)
from .editor_commands import EditorCommand, SetCanvasBackground
from .editor_controller import EditorController
from .editor_models import Layer, ProjectDocument, TimeBinding, Transform
from .paths import data_dir
from .template_system import ReplaceTemplateLayers, build_template_layers, template_choices
from .visual_precision import ApplySongVisualSettings, normalize_song_visual_settings

STUDIO_SCHEMA_VERSION = 1
FAVORITES_FORMAT = "full-album-maker-template-favorites"
FAVORITES_VERSION = 1

ORIGIN_BUILT_IN = "BUILT_IN"
ORIGIN_CUSTOM = "CUSTOM"
CATEGORIES = (
    "Semua",
    "Cinematic",
    "Romantis",
    "Perjalanan",
    "Keluarga",
    "Minimalis",
    "Modern",
    "Klasik",
)
RATIOS = ("16:9", "9:16")
TITLE_LAYOUTS = ("left", "center", "right")
COVER_POSITIONS = ("left", "right", "full")
BACKGROUND_STYLES = ("template", "photo_dark_overlay", "solid_dark")
SPACING_OPTIONS = ("compact", "normal", "relaxed")
TYPOGRAPHY_OPTIONS = ("noto_sans_safe",)
APPLY_SCOPES = ("current", "selected", "all")

# Presentation metadata deliberately wraps the recovered stable engine IDs.
# Engine IDs are never renamed because old projects/templates rely on them.
_BUILTIN_PRESENTATION: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "spotify_clean": ("Senja di Kota Ini", ("Minimalis", "Modern"), ("clean", "minimal", "senja")),
    "cafe_acoustic": ("Jalan Pulang", ("Klasik", "Romantis"), ("hangat", "akustik", "pulang")),
    "viral_full_album": ("Perjalanan Kita", ("Perjalanan", "Modern"), ("album", "travel", "modern")),
    "vinyl_nostalgia": ("Cerita Baru", ("Klasik",), ("vinyl", "retro", "cerita")),
    "neon_spectrum": ("Kisah Kita", ("Modern",), ("neon", "modern", "spectrum")),
    "romantic_bokeh": ("Album Kenangan", ("Romantis", "Keluarga"), ("bokeh", "romantis", "kenangan")),
    "dark_cinematic": ("Langit yang Sama", ("Cinematic",), ("gelap", "cinematic", "langit")),
    "photo_album": ("Waktu di Sini", ("Keluarga", "Perjalanan"), ("foto", "album", "waktu")),
    "cassette_retro": ("Nada Lama", ("Klasik",), ("kaset", "retro", "analog")),
    "music_channel_pro": ("Studio Malam", ("Modern", "Cinematic"), ("studio", "pro", "channel")),
}


@dataclass(frozen=True)
class TemplateStudioDescriptor:
    template_id: str
    name: str
    origin: str
    categories: tuple[str, ...] = ()
    ratios: tuple[str, ...] = RATIOS
    tags: tuple[str, ...] = ()
    description: str = ""
    schema_version: int = STUDIO_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != STUDIO_SCHEMA_VERSION:
            raise ValueError("Versi descriptor Template Studio tidak didukung.")
        if not self.template_id or not self.name.strip():
            raise ValueError("Template membutuhkan ID dan nama.")
        if self.origin not in {ORIGIN_BUILT_IN, ORIGIN_CUSTOM}:
            raise ValueError("Origin template tidak valid.")
        if not self.ratios or any(value not in RATIOS for value in self.ratios):
            raise ValueError("Rasio template tidak valid.")
        if any(value not in CATEGORIES[1:] for value in self.categories):
            raise ValueError("Kategori template tidak valid.")


@dataclass
class TemplateStudioDraft:
    template_id: str
    ratio: str = "16:9"
    title_layout: str = "left"
    cover_position: str = "full"
    background_style: str = "photo_dark_overlay"
    spacing: str = "normal"
    typography: str = "noto_sans_safe"
    overlay_opacity: float = 0.60
    visual_defaults: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.template_id:
            raise ValueError("Pilih template terlebih dahulu.")
        if self.ratio not in RATIOS:
            raise ValueError("Rasio draft template tidak didukung.")
        if self.title_layout not in TITLE_LAYOUTS:
            raise ValueError("Title Layout tidak didukung.")
        if self.cover_position not in COVER_POSITIONS:
            raise ValueError("Posisi Cover tidak didukung.")
        if self.background_style not in BACKGROUND_STYLES:
            raise ValueError("Background template tidak didukung.")
        if self.spacing not in SPACING_OPTIONS:
            raise ValueError("Spacing template tidak didukung.")
        if self.typography not in TYPOGRAPHY_OPTIONS:
            raise ValueError("Typography belum tersedia pada renderer recovered.")
        opacity = float(self.overlay_opacity)
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Overlay Opacity harus 0..1.")
        normalize_song_visual_settings(self.effective_visual_defaults())

    def effective_visual_defaults(self) -> dict[str, object]:
        base: dict[str, object] = {
            "fit": "fill",
            "crop_x": 0.0,
            "crop_y": 0.0,
            "crop_width": 1.0,
            "crop_height": 1.0,
            "position_x": 0.0,
            "position_y": 0.0,
            "scale": 1.0,
            "pan_zoom": True,
            "image_motion": "ken_burns",
            "loop_video": False,
            "freeze_end": False,
            "transition": "fade",
            "transition_seconds": 1.0,
        }
        base.update(deepcopy(self.visual_defaults))
        return normalize_song_visual_settings(base)

    def payload(self) -> dict[str, object]:
        self.validate()
        return {
            "schema_version": STUDIO_SCHEMA_VERSION,
            "template_id": self.template_id,
            "ratio": self.ratio,
            "title_layout": self.title_layout,
            "cover_position": self.cover_position,
            "background_style": self.background_style,
            "spacing": self.spacing,
            "typography": self.typography,
            "overlay_opacity": float(self.overlay_opacity),
            "visual_defaults": self.effective_visual_defaults(),
        }


class TemplateFavoriteStore:
    """User preference store; never mutates built-in/custom template payloads."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else data_dir() / "preferences" / "template_favorites_v1.json"

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(raw, dict):
            return set()
        if raw.get("format") != FAVORITES_FORMAT or raw.get("version") != FAVORITES_VERSION:
            return set()
        values = raw.get("template_ids", [])
        if not isinstance(values, list):
            return set()
        return {str(value) for value in values if str(value).strip()}

    def save(self, template_ids: Iterable[str]) -> None:
        values = sorted({str(value) for value in template_ids if str(value).strip()})
        payload = {
            "format": FAVORITES_FORMAT,
            "version": FAVORITES_VERSION,
            "template_ids": values,
        }
        atomic_write_text(self.path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def set_favorite(self, template_id: str, favorite: bool) -> set[str]:
        value = str(template_id).strip()
        if not value:
            raise ValueError("Template ID kosong.")
        current = self.load()
        if favorite:
            current.add(value)
        else:
            current.discard(value)
        self.save(current)
        return current


def builtin_descriptors() -> tuple[TemplateStudioDescriptor, ...]:
    result: list[TemplateStudioDescriptor] = []
    for definition in template_choices():
        name, categories, tags = _BUILTIN_PRESENTATION.get(
            definition.template_id,
            (definition.label, ("Modern",), (definition.label.casefold(),)),
        )
        item = TemplateStudioDescriptor(
            template_id=definition.template_id,
            name=name,
            origin=ORIGIN_BUILT_IN,
            categories=categories,
            tags=tags,
            description=definition.description,
        )
        item.validate()
        result.append(item)
    return tuple(result)


def custom_descriptors(templates: Iterable[CustomTemplate]) -> tuple[TemplateStudioDescriptor, ...]:
    result: list[TemplateStudioDescriptor] = []
    for template in templates:
        template.validate()
        item = TemplateStudioDescriptor(
            template_id=template.template_id,
            name=template.label,
            origin=ORIGIN_CUSTOM,
            categories=("Modern",),
            ratios=RATIOS,
            tags=("custom", template.label.casefold()),
            description=template.description,
        )
        item.validate()
        result.append(item)
    return tuple(result)


def filter_templates(
    templates: Sequence[TemplateStudioDescriptor],
    *,
    search: str = "",
    origin: str = "ALL",
    category: str = "Semua",
    ratio: str = "16:9",
    favorites: Iterable[str] = (),
    sort: str = "Terbaru",
) -> tuple[TemplateStudioDescriptor, ...]:
    query = " ".join(str(search).casefold().split())
    favorite_ids = {str(value) for value in favorites}
    result: list[TemplateStudioDescriptor] = []
    for item in templates:
        item.validate()
        if origin in {ORIGIN_BUILT_IN, ORIGIN_CUSTOM} and item.origin != origin:
            continue
        if origin == "FAVORITE" and item.template_id not in favorite_ids:
            continue
        if category != "Semua" and category not in item.categories:
            continue
        if ratio and ratio not in item.ratios:
            continue
        if query:
            haystack = " ".join((item.name, item.description, *item.tags, *item.categories)).casefold()
            if query not in haystack:
                continue
        result.append(item)
    if sort == "Nama A-Z":
        result.sort(key=lambda item: (item.name.casefold(), item.template_id))
    elif sort != "Terbaru":
        raise ValueError("Sort template tidak didukung.")
    return tuple(result)


def template_payload_hash(descriptor: TemplateStudioDescriptor, draft: TemplateStudioDraft | None = None) -> str:
    descriptor.validate()
    payload: dict[str, object] = {
        "schema_version": descriptor.schema_version,
        "template_id": descriptor.template_id,
        "name": descriptor.name,
        "origin": descriptor.origin,
        "categories": descriptor.categories,
        "ratios": descriptor.ratios,
        "tags": descriptor.tags,
    }
    if draft is not None:
        payload["draft"] = draft.payload()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_scope_song_ids(
    document: ProjectDocument,
    scope: str,
    *,
    current_song_id: str = "",
    selected_song_ids: Iterable[str] = (),
) -> tuple[str, ...]:
    if scope not in APPLY_SCOPES:
        raise ValueError("Scope template tidak didukung.")
    ordered = [song.song_id for song in document.playlist.entries]
    valid = set(ordered)
    if scope == "current":
        if current_song_id not in valid:
            raise ValueError("Lagu aktif tidak ditemukan.")
        return (current_song_id,)
    if scope == "selected":
        requested = {str(value) for value in selected_song_ids}
        targets = tuple(song_id for song_id in ordered if song_id in requested)
        if not targets:
            raise ValueError("Pilih minimal satu lagu.")
        if requested - valid:
            raise ValueError("Pilihan lagu mengandung ID yang sudah tidak valid.")
        return targets
    targets = tuple(ordered)
    if not targets:
        raise ValueError("Album belum memiliki lagu yang dapat menerima template.")
    return targets


def _tune_template_layers(layers: Sequence[Layer], draft: TemplateStudioDraft) -> list[Layer]:
    draft.validate()
    tuned = deepcopy(list(layers))
    if not tuned:
        raise ValueError("Template tidak menghasilkan layer visual.")

    for layer in tuned:
        if layer.type == "song_title":
            if draft.title_layout == "left":
                layer.transform = Transform(x=0.07, y=0.64, width=0.54, height=0.12)
            elif draft.title_layout == "center":
                layer.transform = Transform(x=0.22, y=0.66, width=0.56, height=0.12)
            else:
                layer.transform = Transform(x=0.43, y=0.64, width=0.50, height=0.12)
            layer.properties = dict(layer.properties)
            layer.properties["font_family_hint"] = "Noto Sans"
            if draft.spacing == "compact":
                layer.properties["font_size"] = max(20, int(float(layer.properties.get("font_size", 50)) * 0.90))
            elif draft.spacing == "relaxed":
                layer.properties["font_size"] = min(120, int(float(layer.properties.get("font_size", 50)) * 1.06))
        elif layer.type == "song_cover":
            if draft.cover_position == "left":
                layer.transform = Transform(x=0.06, y=0.18, width=0.28, height=0.50)
            elif draft.cover_position == "right":
                layer.transform = Transform(x=0.66, y=0.18, width=0.28, height=0.50)
            else:
                layer.transform = Transform(x=0.0, y=0.0, width=1.0, height=1.0)
        elif layer.type == "playlist_visual":
            if draft.spacing == "compact":
                layer.properties = dict(layer.properties)
                layer.properties["max_items"] = min(20, int(layer.properties.get("max_items", 8)) + 2)
            elif draft.spacing == "relaxed":
                layer.properties = dict(layer.properties)
                layer.properties["max_items"] = max(3, int(layer.properties.get("max_items", 8)) - 2)
        elif layer.type == "background" and draft.background_style == "solid_dark" and int(layer.order) == 0:
            layer.properties = {"mode": "solid", "color": "#101114", "playback": "loop", "motion": "static", "template_id": draft.template_id}
            layer.asset_refs = []
            layer.opacity = 1.0

    if draft.background_style == "photo_dark_overlay" and float(draft.overlay_opacity) > 0:
        track_id = tuned[0].track_id
        tuned.append(
            Layer(
                track_id=track_id,
                type="background",
                name="Template Dark Overlay",
                enabled=True,
                opacity=float(draft.overlay_opacity),
                order=10,
                time_binding=TimeBinding(kind="album"),
                transform=Transform(x=0.0, y=0.0, width=1.0, height=1.0),
                properties={"mode": "solid", "color": "#000000", "playback": "loop", "motion": "static", "template_id": draft.template_id},
                origin="template",
            )
        )

    tuned.sort(key=lambda layer: layer.order)
    for layer in tuned:
        layer.validate()
    return tuned


def build_template_apply_commands(
    document: ProjectDocument,
    draft: TemplateStudioDraft,
    target_song_ids: Iterable[str],
    *,
    custom_template: CustomTemplate | None = None,
) -> tuple[EditorCommand, ...]:
    draft.validate()
    targets = tuple(str(value) for value in target_song_ids)
    if not targets:
        raise ValueError("Scope template tidak memiliki target lagu.")
    songs = document.song_map()
    if any(song_id not in songs for song_id in targets):
        raise ValueError("Scope template mengandung lagu yang tidak ditemukan.")

    if custom_template is None:
        layers = _tune_template_layers(build_template_layers(document, draft.template_id), draft)
        commands: list[EditorCommand] = [
            ReplaceTemplateLayers(layers, draft.template_id),
            SetCustomTemplateMarker(""),
        ]
    else:
        custom_template.validate()
        if custom_template.template_id != draft.template_id:
            raise ValueError("Draft dan template kustom tidak cocok.")
        layers = _tune_template_layers(build_custom_template_layers(document, custom_template), draft)
        commands = [
            ReplaceTemplateLayers(layers, ""),
            SetCanvasBackground(custom_template.canvas_background_color),
            SetCustomTemplateMarker(custom_template.template_id),
        ]

    # Per-song defaults deliberately use the recovered STEP06 contract. The
    # template layer design stays album-level; the requested scope controls
    # Visual defaults without copying media assignments or reordering songs.
    commands.append(ApplySongVisualSettings(targets, draft.effective_visual_defaults()))
    return tuple(commands)


def preview_template_document(
    document: ProjectDocument,
    draft: TemplateStudioDraft,
    target_song_ids: Iterable[str],
    *,
    custom_template: CustomTemplate | None = None,
) -> ProjectDocument:
    """Create a disposable preview snapshot; never mutates project/history."""
    controller = EditorController(document.clone())
    controller.dispatch(build_template_apply_commands(controller.snapshot(), draft, target_song_ids, custom_template=custom_template))
    return controller.snapshot()


def duplicate_to_custom(
    document: ProjectDocument,
    draft: TemplateStudioDraft,
    target_song_ids: Iterable[str],
    *,
    label: str,
    description: str = "",
    store: CustomTemplateStore | None = None,
    custom_template: CustomTemplate | None = None,
) -> CustomTemplate:
    preview = preview_template_document(document, draft, target_song_ids, custom_template=custom_template)
    copied = capture_custom_template(preview, label=label, description=description)
    (store or CustomTemplateStore()).save(copied)
    return copied
