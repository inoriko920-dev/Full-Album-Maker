from __future__ import annotations

from dataclasses import dataclass
import re

from .spectrum_feature import smoothing_to_averaging


MIN_INTERNAL_SIDE = 64
MAX_INTERNAL_SIDE = 512
OUTER_RADIUS_RATIO = 0.48


@dataclass(frozen=True)
class CircularSpectrumGeometry:
    internal_side: int
    target_width: int
    target_height: int
    inner_ratio: float


def circular_internal_side(width: int, height: int) -> int:
    """Bound polar remap cost independently from the final layer size."""

    smallest = max(2, min(int(width), int(height)))
    return max(MIN_INTERNAL_SIDE, min(MAX_INTERNAL_SIDE, smallest))


def circular_geometry(width: int, height: int, inner_ratio: float) -> CircularSpectrumGeometry:
    width = int(width)
    height = int(height)
    if width < 2 or height < 2:
        raise ValueError("Ukuran Circular Spectrum minimal 2x2 pixel.")
    try:
        ratio = float(inner_ratio)
    except (TypeError, ValueError) as exc:
        raise ValueError("Radius dalam Circular Spectrum tidak valid.") from exc
    if not 0.15 <= ratio <= 0.85:
        raise ValueError("Radius dalam Circular Spectrum harus 0.15..0.85.")
    return CircularSpectrumGeometry(
        internal_side=circular_internal_side(width, height),
        target_width=width,
        target_height=height,
        inner_ratio=ratio,
    )


def _color_factors(color: str) -> tuple[float, float, float]:
    value = str(color or "").strip().lower()
    if value.startswith("0x"):
        value = value[2:]
    elif value.startswith("#"):
        value = value[1:]
    if not re.fullmatch(r"[0-9a-f]{6}", value):
        raise ValueError("Warna Circular Spectrum harus #RRGGBB/0xRRGGBB.")
    return tuple(int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4))


def circular_spectrum_filter(
    *,
    width: int,
    height: int,
    color: str,
    frequency_scale: str,
    amplitude_scale: str,
    inner_ratio: float,
    band_count: int | None = None,
    thickness: float | None = None,
    smoothing: float | None = None,
) -> str:
    """Return a transparent audio visualizer chain that wraps showfreqs into a ring.

    Recovered calls that omit STEP08 parameters keep the exact v1.2 chain. When
    STEP08 values are supplied, band_count becomes the real frequency-image
    horizontal resolution, smoothing maps to showfreqs time averaging, and
    thickness controls radial width in final project pixels before the bounded
    polar remap is scaled to the requested layer box.
    """

    geometry = circular_geometry(width, height, inner_ratio)
    side = geometry.internal_side

    if thickness is None:
        inner = OUTER_RADIUS_RATIO * geometry.inner_ratio
    else:
        value = float(thickness)
        if value <= 0:
            raise ValueError("Ketebalan Circular Spectrum harus > 0.")
        target_min = max(2.0, float(min(width, height)))
        # Radial width expressed in final project pixels. Clamp so the ring can
        # never invert or consume the whole radius.
        band_ratio = max(1.0 / target_min, min(OUTER_RADIUS_RATIO - 0.04, value / target_min))
        inner = OUTER_RADIUS_RATIO - band_ratio
    band = OUTER_RADIUS_RATIO - inner
    if band <= 0:
        raise ValueError("Radius Circular Spectrum menghasilkan ketebalan nol.")
    red, green, blue = _color_factors(color)

    radius = "hypot(X-W/2,Y-H/2)"
    angle_x = "clip((atan2(Y-H/2,X-W/2)+PI)/(2*PI)*(W-1),0,W-1)"
    source_y = (
        "clip(H-1-("
        + radius
        + f"-min(W,H)*{inner:.6f})/(min(W,H)*{band:.6f})*(H-1),0,H-1)"
    )
    radial_luma = (
        f"if(between({radius},min(W,H)*{inner:.6f},"
        f"min(W,H)*{OUTER_RADIUS_RATIO:.6f}),"
        f"lum({angle_x},{source_y}),0)"
    )

    if band_count is None and smoothing is None and thickness is None:
        frequency_source = f"showfreqs=s={side}x{side}:mode=bar:fscale={frequency_scale}:ascale={amplitude_scale}:colors=white,"
    else:
        bands = max(16, min(512, int(band_count if band_count is not None else side)))
        averaging = smoothing_to_averaging(0.0 if smoothing is None else float(smoothing))
        frequency_source = (
            f"showfreqs=s={bands}x{side}:mode=bar:fscale={frequency_scale}:"
            f"ascale={amplitude_scale}:averaging={averaging}:colors=white,"
            f"scale={side}:{side}:flags=neighbor,"
        )

    return (
        frequency_source
        + "format=gray,"
        + f"geq=lum='{radial_luma}':interpolation=bilinear,"
        + "format=rgba,colorkey=0x000000:0.02:0.0,"
        + f"colorchannelmixer=rr={red:.6f}:gg={green:.6f}:bb={blue:.6f},"
        + f"scale={geometry.target_width}:{geometry.target_height}:force_original_aspect_ratio=decrease,"
        + f"pad={geometry.target_width}:{geometry.target_height}:(ow-iw)/2:(oh-ih)/2:color=black@0,format=rgba"
    )