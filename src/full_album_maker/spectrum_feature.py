from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .editor_models import Layer, TimeBinding, Transform


MIN_BAND_COUNT = 16
MAX_BAND_COUNT = 512
DEFAULT_BAND_COUNT = 128
MIN_THICKNESS = 1.0
MAX_THICKNESS = 64.0
DEFAULT_THICKNESS = 12.0
MIN_SMOOTHING = 0.0
MAX_SMOOTHING = 1.0
DEFAULT_SMOOTHING = 0.0
DEFAULT_REACTIVE_SCALE = 1.0
DEFAULT_ACCENT_COLOR = "#4de8ff"


@dataclass(frozen=True)
class SpectrumCapability:
    style_id: str
    label: str
    ffmpeg_filter: str
    supports_frequency_scale: bool
    supports_amplitude_scale: bool
    supports_split_channels: bool = False
    supports_smoothing: bool = False
    supports_inner_ratio: bool = False


SPECTRUM_CAPABILITIES: dict[str, SpectrumCapability] = {
    "bars": SpectrumCapability(
        "bars", "Bars", "showfreqs", True, True, False, True, False
    ),
    "spectrum_line": SpectrumCapability(
        "spectrum_line", "Spectrum Line", "showfreqs", True, True, False, True, False
    ),
    "waveform": SpectrumCapability(
        "waveform", "Waveform", "showwaves", False, True, False, False, False
    ),
    "stereo_waveform": SpectrumCapability(
        "stereo_waveform", "Stereo Waveform", "showwaves", False, True, True, False, False
    ),
    "circular_spectrum": SpectrumCapability(
        "circular_spectrum",
        "Circular Spectrum",
        "showfreqs+geq",
        True,
        True,
        False,
        True,
        True,
    ),
}


# Recovered presets remain stable. STEP08 adds a golden-facing semantic preset
# registry in spectrum_step08.py rather than silently renaming these IDs.
SPECTRUM_PRESETS: dict[str, dict[str, Any]] = {
    "minimal_bars": {
        "label": "Minimal Bars",
        "style": "bars",
        "color": "#f4f7fb",
        "gain": 1.0,
        "frequency_scale": "log",
        "amplitude_scale": "sqrt",
        "mirror": False,
    },
    "neon_bars": {
        "label": "Neon Bars",
        "style": "bars",
        "color": "#4de8ff",
        "gain": 1.35,
        "frequency_scale": "log",
        "amplitude_scale": "log",
        "mirror": True,
    },
    "bass_bars": {
        "label": "Bass Bars",
        "style": "bars",
        "color": "#ff5c9a",
        "gain": 1.8,
        "frequency_scale": "log",
        "amplitude_scale": "cbrt",
        "mirror": False,
    },
    "thin_line": {
        "label": "Thin Line",
        "style": "spectrum_line",
        "color": "#ffffff",
        "gain": 1.1,
        "frequency_scale": "log",
        "amplitude_scale": "sqrt",
        "mirror": False,
    },
    "mirror": {
        "label": "Mirror",
        "style": "waveform",
        "color": "#67f0c2",
        "gain": 1.0,
        "frequency_scale": "linear",
        "amplitude_scale": "linear",
        "mirror": True,
    },
    "circular_neon": {
        "label": "Circular Neon",
        "style": "circular_spectrum",
        "color": "#4de8ff",
        "gain": 1.35,
        "frequency_scale": "log",
        "amplitude_scale": "sqrt",
        "mirror": False,
        "inner_ratio": 0.58,
    },
}


def supported_spectrum_styles() -> tuple[str, ...]:
    return tuple(SPECTRUM_CAPABILITIES)


def spectrum_capability(style: str) -> SpectrumCapability:
    try:
        return SPECTRUM_CAPABILITIES[str(style)]
    except KeyError as exc:
        raise ValueError(f"Style spectrum belum didukung: {style}") from exc


def spectrum_type_for_style(style: str) -> str:
    spectrum_capability(style)
    return "circular" if style == "circular_spectrum" else "linear"


def style_for_spectrum_type(spectrum_type: str, current_style: str = "bars") -> str:
    value = str(spectrum_type or "linear").casefold()
    if value not in {"linear", "circular"}:
        raise ValueError("spectrum_type harus linear/circular.")
    if value == "circular":
        return "circular_spectrum"
    # Keep a recovered linear style when switching among STEP08 common fields.
    return current_style if current_style in {"bars", "spectrum_line", "waveform", "stereo_waveform"} else "bars"


def smoothing_to_averaging(smoothing: float) -> int:
    """Map normalized STEP08 smoothing to FFmpeg showfreqs time averaging.

    0.0 deliberately maps to the recovered default of one analysis frame.
    The upper bound is finite so seek/reseed never creates unbounded lag.
    """

    value = float(smoothing)
    if not MIN_SMOOTHING <= value <= MAX_SMOOTHING:
        raise ValueError("Smoothing spectrum harus 0..1.")
    return 1 + int(round(value * 15.0))


def _validated_color(value: object) -> str:
    color = str(value or DEFAULT_ACCENT_COLOR).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Warna spectrum harus #RRGGBB.")
    return color.upper()


def normalize_spectrum_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize recovered Spectrum properties plus STEP08 semantic aliases.

    Compatibility rules:
    - old `gain` and `color` remain authoritative aliases;
    - new `reactive_scale` and `accent_color` are persisted alongside them;
    - old projects without STEP08 fields receive deterministic defaults;
    - no project schema bump is required because Spectrum data already lives in
      Layer.properties.
    """

    source = dict(properties or {})
    original_style = str(source.get("style", "bars"))
    inferred_type = spectrum_type_for_style(original_style)
    spectrum_type = str(source.get("spectrum_type", inferred_type)).casefold()
    style = style_for_spectrum_type(spectrum_type, original_style)
    capability = spectrum_capability(style)

    accent_color = _validated_color(source.get("accent_color", source.get("color", DEFAULT_ACCENT_COLOR)))

    try:
        reactive_scale = float(source.get("reactive_scale", source.get("gain", DEFAULT_REACTIVE_SCALE)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Reactive Scale spectrum tidak valid.") from exc
    if not 0.05 <= reactive_scale <= 8.0:
        raise ValueError("Reactive Scale spectrum harus 0.05..8.0.")

    frequency_scale = str(
        source.get(
            "frequency_scale",
            "log" if capability.supports_frequency_scale else "linear",
        )
    )
    if capability.supports_frequency_scale:
        if frequency_scale not in {"linear", "log", "rlog"}:
            raise ValueError("frequency_scale spectrum tidak didukung.")
    else:
        frequency_scale = "linear"

    amplitude_scale = str(source.get("amplitude_scale", "sqrt"))
    if amplitude_scale not in {"linear", "sqrt", "cbrt", "log"}:
        raise ValueError("amplitude_scale spectrum tidak didukung.")

    try:
        inner_ratio = float(source.get("inner_ratio", 0.58))
    except (TypeError, ValueError) as exc:
        raise ValueError("Radius dalam Circular Spectrum tidak valid.") from exc
    if capability.supports_inner_ratio:
        if not 0.15 <= inner_ratio <= 0.85:
            raise ValueError("Radius dalam Circular Spectrum harus 0.15..0.85.")
    else:
        inner_ratio = 0.58

    try:
        band_count = int(source.get("band_count", DEFAULT_BAND_COUNT))
    except (TypeError, ValueError) as exc:
        raise ValueError("Jumlah Band spectrum tidak valid.") from exc
    if not MIN_BAND_COUNT <= band_count <= MAX_BAND_COUNT:
        raise ValueError(f"Jumlah Band spectrum harus {MIN_BAND_COUNT}..{MAX_BAND_COUNT}.")

    try:
        thickness = float(source.get("thickness", DEFAULT_THICKNESS))
    except (TypeError, ValueError) as exc:
        raise ValueError("Ketebalan spectrum tidak valid.") from exc
    if not MIN_THICKNESS <= thickness <= MAX_THICKNESS:
        raise ValueError(f"Ketebalan spectrum harus {MIN_THICKNESS:g}..{MAX_THICKNESS:g}.")

    try:
        smoothing = float(source.get("smoothing", DEFAULT_SMOOTHING))
    except (TypeError, ValueError) as exc:
        raise ValueError("Smoothing spectrum tidak valid.") from exc
    if not MIN_SMOOTHING <= smoothing <= MAX_SMOOTHING:
        raise ValueError("Smoothing spectrum harus 0..1.")

    audio_binding = str(source.get("audio_binding", "project_mix") or "project_mix")
    if audio_binding != "project_mix":
        raise ValueError("Audio binding Spectrum recovered saat ini hanya mendukung project_mix.")

    mirror = bool(source.get("mirror", False))
    return {
        "style": style,
        "spectrum_type": spectrum_type,
        "color": accent_color,
        "accent_color": accent_color,
        "gain": reactive_scale,
        "reactive_scale": reactive_scale,
        "frequency_scale": frequency_scale,
        "amplitude_scale": amplitude_scale,
        "mirror": mirror,
        "inner_ratio": inner_ratio,
        "band_count": band_count,
        "thickness": thickness,
        "smoothing": smoothing,
        "audio_binding": audio_binding,
        "preset": str(source.get("preset", "") or ""),
    }


def apply_spectrum_preset(properties: dict[str, Any] | None, preset_id: str) -> dict[str, Any]:
    if preset_id not in SPECTRUM_PRESETS:
        raise ValueError(f"Preset spectrum tidak ditemukan: {preset_id}")
    merged = dict(properties or {})
    preset = SPECTRUM_PRESETS[preset_id]
    merged.update({key: value for key, value in preset.items() if key != "label"})
    # Preserve recovered semantics while making aliases explicit.
    if "gain" in preset:
        merged["reactive_scale"] = preset["gain"]
    if "color" in preset:
        merged["accent_color"] = preset["color"]
    merged["spectrum_type"] = spectrum_type_for_style(str(preset.get("style", merged.get("style", "bars"))))
    merged["preset"] = preset_id
    return normalize_spectrum_properties(merged)


def make_spectrum_layer(track_id: str, order: int, *, preset_id: str = "neon_bars") -> Layer:
    properties = apply_spectrum_preset({}, preset_id)
    circular = properties["spectrum_type"] == "circular"
    return Layer(
        track_id=track_id,
        type="spectrum",
        name="Circular Spectrum" if circular else "Spectrum",
        order=order,
        time_binding=TimeBinding(kind="album"),
        transform=(
            Transform(x=0.34, y=0.22, width=0.32, height=0.56)
            if circular
            else Transform(x=0.08, y=0.72, width=0.84, height=0.20)
        ),
        properties=properties,
        origin="manual",
    )


def make_dynamic_title_layer(track_id: str, order: int) -> Layer:
    return Layer(
        track_id=track_id,
        type="song_title",
        name="Judul Lagu Dinamis",
        order=order,
        time_binding=TimeBinding(kind="album"),
        transform=Transform(x=0.06, y=0.78, width=0.70, height=0.16),
        properties={
            "template": "{title}\n{artist}",
            "font_size": 58,
            "color": "#ffffff",
        },
        origin="manual",
    )


def dynamic_song_text(template: str, title: str, artist: str) -> str:
    value = str(template or "{title}\n{artist}")
    return value.replace("{title}", str(title or "")).replace("{artist}", str(artist or ""))