from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from .editor_models import ProjectDocument
from .paths import ffmpeg_path, ffprobe_path
from .render_center_model_step10 import RenderSettings, RenderSnapshot, build_render_snapshot


class PreflightLevel(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class PreflightCheck:
    key: str
    label: str
    level: PreflightLevel
    message: str


@dataclass(frozen=True)
class FFmpegCapability:
    ffmpeg: str
    ffprobe: str
    version: str
    encoders: frozenset[str]
    runtime_verified_encoders: frozenset[str] = frozenset()
    source: str = "unknown"

    def has_encoder(self, encoder: str) -> bool:
        return str(encoder) in self.encoders

    def runtime_verified(self, encoder: str) -> bool:
        return str(encoder) in self.runtime_verified_encoders


@dataclass(frozen=True)
class EncoderResolution:
    encoder: str
    hardware: bool
    fallback_used: bool
    message: str


@dataclass(frozen=True)
class PreflightReport:
    snapshot: RenderSnapshot | None
    settings_signature: str
    checks: tuple[PreflightCheck, ...]
    capability: FFmpegCapability | None
    encoder: EncoderResolution | None
    estimated_output_bytes: int
    required_free_bytes: int
    recommended_free_bytes: int

    @property
    def blocked(self) -> bool:
        return any(check.level == PreflightLevel.BLOCK for check in self.checks)

    @property
    def warnings(self) -> tuple[PreflightCheck, ...]:
        return tuple(check for check in self.checks if check.level == PreflightLevel.WARN)

    @property
    def ready(self) -> bool:
        return self.snapshot is not None and not self.blocked


Run = Callable[..., subprocess.CompletedProcess]


def _tool_source(path: str) -> str:
    value = Path(path).resolve(strict=False)
    parts = {part.casefold() for part in value.parts}
    return "bundled" if "tools" in parts and "ffmpeg" in parts else "system"


def probe_ffmpeg(
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
    *,
    run: Run = subprocess.run,
    timeout: float = 8.0,
) -> FFmpegCapability:
    ffmpeg = str(ffmpeg or ffmpeg_path() or "")
    ffprobe = str(ffprobe or ffprobe_path() or "")
    if not ffmpeg:
        raise RuntimeError("FFmpeg tidak ditemukan.")
    if not ffprobe:
        raise RuntimeError("ffprobe tidak ditemukan.")
    try:
        version_result = run(
            [ffmpeg, "-hide_banner", "-version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=True,
        )
        enc_result = run(
            [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=True,
        )
        probe_result = run(
            [ffprobe, "-hide_banner", "-version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=True,
        )
    except Exception as exc:
        raise RuntimeError(f"Probe FFmpeg/ffprobe gagal: {exc}") from exc

    version_line = ((version_result.stdout or version_result.stderr or "").splitlines() or [""])[0].strip()
    probe_line = ((probe_result.stdout or probe_result.stderr or "").splitlines() or [""])[0].strip()
    if not version_line or not probe_line:
        raise RuntimeError("Versi FFmpeg/ffprobe tidak dapat dibaca.")

    encoders: set[str] = set()
    for line in ((enc_result.stdout or "") + "\n" + (enc_result.stderr or "")).splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) >= 2 and parts[0][0] in {"V", "."}:
            encoders.add(parts[1])
    if not encoders:
        raise RuntimeError("Daftar encoder FFmpeg kosong/tidak dapat diparse.")
    return FFmpegCapability(
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        version=version_line,
        encoders=frozenset(encoders),
        source=_tool_source(ffmpeg),
    )


def verify_encoder_runtime(
    capability: FFmpegCapability,
    encoder: str,
    *,
    run: Run = subprocess.run,
    timeout: float = 10.0,
) -> FFmpegCapability:
    if encoder not in capability.encoders:
        return capability
    args = [
        capability.ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
        "-i", "color=size=64x64:rate=1:duration=1", "-frames:v", "1",
        "-c:v", encoder, "-f", "null", "-",
    ]
    try:
        result = run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except Exception:
        return capability
    if int(getattr(result, "returncode", 1)) != 0:
        return capability
    verified = set(capability.runtime_verified_encoders)
    verified.add(encoder)
    return FFmpegCapability(
        ffmpeg=capability.ffmpeg,
        ffprobe=capability.ffprobe,
        version=capability.version,
        encoders=capability.encoders,
        runtime_verified_encoders=frozenset(verified),
        source=capability.source,
    )


def software_encoder(video_codec: str) -> str:
    if video_codec == "h264":
        return "libx264"
    if video_codec == "h265":
        return "libx265"
    raise ValueError("Video codec belum didukung.")


def hardware_encoder(video_codec: str) -> str:
    if video_codec == "h264":
        return "h264_nvenc"
    if video_codec == "h265":
        return "hevc_nvenc"
    raise ValueError("Video codec belum didukung.")


def resolve_encoder(settings: RenderSettings, capability: FFmpegCapability) -> EncoderResolution:
    settings.validate()
    software = software_encoder(settings.video_codec)
    hardware = hardware_encoder(settings.video_codec)
    if settings.hardware_mode == "software":
        if not capability.has_encoder(software):
            raise RuntimeError(f"Encoder software {software} tidak tersedia.")
        return EncoderResolution(software, False, False, "Software encoder terverifikasi tersedia.")

    if settings.hardware_mode in {"h264_nvenc", "hevc_nvenc"}:
        requested = settings.hardware_mode
        if requested != hardware:
            raise RuntimeError("Hardware encoder tidak cocok dengan codec yang dipilih.")
        if not capability.has_encoder(requested):
            raise RuntimeError(f"Encoder hardware {requested} tidak tersedia di FFmpeg.")
        if not capability.runtime_verified(requested):
            raise RuntimeError(f"Encoder hardware {requested} belum lolos runtime probe.")
        return EncoderResolution(requested, True, False, "Hardware encoder lolos runtime probe.")

    if capability.has_encoder(hardware) and capability.runtime_verified(hardware):
        return EncoderResolution(hardware, True, False, "AUTO memilih hardware encoder yang lolos runtime probe.")
    if capability.has_encoder(software):
        return EncoderResolution(software, False, True, "AUTO memakai software fallback yang terverifikasi tersedia.")
    raise RuntimeError(f"Tidak ada encoder kompatibel untuk {settings.video_codec}.")


def _required_asset_ids(document: ProjectDocument) -> set[str]:
    ids = {song.asset_id for song in document.playlist.entries if song.enabled}
    for song in document.playlist.entries:
        if not song.enabled:
            continue
        if song.cover_asset_id:
            ids.add(song.cover_asset_id)
        if song.visual_asset_id:
            ids.add(song.visual_asset_id)
    for layer in document.layers:
        if layer.enabled:
            ids.update(layer.asset_refs)
    return ids


def required_media_paths(document: ProjectDocument) -> tuple[Path, ...]:
    assets = document.asset_map()
    paths: list[Path] = []
    for asset_id in sorted(_required_asset_ids(document)):
        asset = assets.get(asset_id)
        if asset is not None and asset.locator:
            paths.append(Path(asset.locator).expanduser())
    return tuple(paths)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def media_integrity_issues(document: ProjectDocument) -> tuple[list[str], list[str], int]:
    """Return blocking issues, warnings, and active-source count.

    Fingerprints are optional for backward compatibility. When a snapshot does
    carry a known size/mtime/sha256, mismatch is a BLOCK because the queued
    render would otherwise consume bytes different from the source identity the
    project recorded. Missing fingerprints remain a visible WARN, not a fake
    PASS claim.
    """

    assets = document.asset_map()
    blocking: list[str] = []
    warnings: list[str] = []
    count = 0
    for asset_id in sorted(_required_asset_ids(document)):
        asset = assets.get(asset_id)
        if asset is None or not asset.locator:
            blocking.append(f"asset:{asset_id[:8]} tidak ditemukan")
            continue
        count += 1
        path = Path(asset.locator).expanduser()
        try:
            if not path.is_file():
                blocking.append(f"missing:{path.name or str(path)}")
                continue
            stat = path.stat()
            if stat.st_size <= 0:
                blocking.append(f"empty:{path.name}")
                continue
        except OSError:
            blocking.append(f"unreadable:{path.name or str(path)}")
            continue

        fingerprint = dict(asset.fingerprint or {})
        if not fingerprint:
            warnings.append(f"no-fingerprint:{path.name}")
            continue
        expected_size = fingerprint.get("size")
        if expected_size is not None:
            try:
                if int(expected_size) != int(stat.st_size):
                    blocking.append(f"changed-size:{path.name}")
                    continue
            except (TypeError, ValueError):
                warnings.append(f"bad-size-fingerprint:{path.name}")
        expected_mtime = fingerprint.get("mtime_ns")
        if expected_mtime is not None:
            try:
                if int(expected_mtime) != int(stat.st_mtime_ns):
                    blocking.append(f"changed-mtime:{path.name}")
                    continue
            except (TypeError, ValueError):
                warnings.append(f"bad-mtime-fingerprint:{path.name}")
        expected_sha = str(fingerprint.get("sha256") or "").strip().casefold()
        if expected_sha:
            if _sha256(path).casefold() != expected_sha:
                blocking.append(f"changed-sha256:{path.name}")
    return blocking, warnings, count


def estimate_output_bytes(snapshot: RenderSnapshot, settings: RenderSettings) -> int:
    seconds = snapshot.duration_tick / max(1, snapshot.timebase)
    total_bps = int(settings.video_bitrate_bps) + int(settings.audio_bitrate_bps)
    return max(1, int(seconds * total_bps / 8.0 * 1.15))


def _existing_disk_anchor(path: Path) -> Path:
    current = path.resolve(strict=False)
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _output_folder_check(settings: RenderSettings) -> tuple[PreflightLevel, str, Path]:
    target = settings.final_output
    folder = target.parent
    anchor = _existing_disk_anchor(folder)
    if not anchor.exists() or not anchor.is_dir():
        return PreflightLevel.BLOCK, "Folder output/parent tidak tersedia.", anchor
    if folder.exists() and not folder.is_dir():
        return PreflightLevel.BLOCK, "Output folder bukan directory.", anchor
    if not os.access(anchor, os.W_OK):
        return PreflightLevel.BLOCK, "Folder output/parent tidak dapat ditulis.", anchor
    if target.exists() and not settings.overwrite:
        return PreflightLevel.BLOCK, "File final sudah ada dan overwrite belum diizinkan.", anchor
    if target.exists() and settings.overwrite:
        return PreflightLevel.WARN, "File final akan diganti secara transactional setelah verifikasi.", anchor
    return PreflightLevel.PASS, "Folder output dapat digunakan.", anchor


def run_preflight(
    document: ProjectDocument,
    settings: RenderSettings,
    *,
    capability: FFmpegCapability | None = None,
    disk_usage: Callable[[str | os.PathLike[str]], shutil._ntuple_diskusage] = shutil.disk_usage,
) -> PreflightReport:
    checks: list[PreflightCheck] = []
    snapshot: RenderSnapshot | None = None
    encoder: EncoderResolution | None = None
    settings.validate()

    try:
        snapshot = build_render_snapshot(document)
        checks.append(PreflightCheck("snapshot", "Project Snapshot", PreflightLevel.PASS, f"Snapshot {snapshot.snapshot_hash[:12]} • rev {snapshot.project_revision}"))
        checks.append(PreflightCheck("timeline", "Timeline Valid", PreflightLevel.PASS, "RenderPlan dapat dikompilasi dari snapshot."))
    except Exception as exc:
        checks.append(PreflightCheck("snapshot", "Project Snapshot", PreflightLevel.BLOCK, str(exc)))
        checks.append(PreflightCheck("timeline", "Timeline Valid", PreflightLevel.BLOCK, "Timeline/snapshot belum dapat dirender."))

    if snapshot is not None:
        snap_doc = snapshot.document()
        blocking, warnings, media_count = media_integrity_issues(snap_doc)
        if blocking:
            checks.append(PreflightCheck("media", "Media Lengkap & Stabil", PreflightLevel.BLOCK, "Media tidak siap: " + ", ".join(blocking[:8])))
        elif warnings:
            checks.append(PreflightCheck("media", "Media Lengkap & Stabil", PreflightLevel.WARN, f"{media_count} source tersedia; fingerprint parsial: " + ", ".join(warnings[:5])))
        else:
            checks.append(PreflightCheck("media", "Media Lengkap & Stabil", PreflightLevel.PASS, f"{media_count} source aktif cocok dengan fingerprint proyek."))

        final_resolved = settings.final_output.resolve(strict=False)
        source_paths = {path.resolve(strict=False) for path in required_media_paths(snap_doc)}
        if final_resolved in source_paths:
            checks.append(PreflightCheck("output_source", "Output vs Source", PreflightLevel.BLOCK, "Lokasi output sama dengan media source aktif."))
        else:
            checks.append(PreflightCheck("output_source", "Output vs Source", PreflightLevel.PASS, "Output tidak menimpa source aktif."))
    else:
        checks.append(PreflightCheck("media", "Media Lengkap & Stabil", PreflightLevel.BLOCK, "Snapshot tidak tersedia."))
        checks.append(PreflightCheck("output_source", "Output vs Source", PreflightLevel.BLOCK, "Snapshot tidak tersedia."))

    if capability is None:
        try:
            capability = probe_ffmpeg()
        except Exception as exc:
            checks.append(PreflightCheck("ffmpeg", "FFmpeg Siap", PreflightLevel.BLOCK, str(exc)))
    if capability is not None:
        checks.append(PreflightCheck("ffmpeg", "FFmpeg Siap", PreflightLevel.PASS, f"{capability.source}: {capability.version}"))
        try:
            encoder = resolve_encoder(settings, capability)
            level = PreflightLevel.WARN if encoder.fallback_used else PreflightLevel.PASS
            checks.append(PreflightCheck("encoder", "Encoder", level, encoder.message + f" ({encoder.encoder})"))
        except Exception as exc:
            checks.append(PreflightCheck("encoder", "Encoder", PreflightLevel.BLOCK, str(exc)))
    else:
        checks.append(PreflightCheck("encoder", "Encoder", PreflightLevel.BLOCK, "Encoder belum dapat diprobe."))

    folder_level, folder_message, disk_anchor = _output_folder_check(settings)
    checks.append(PreflightCheck("output", "Output Folder", folder_level, folder_message))

    estimated = estimate_output_bytes(snapshot, settings) if snapshot is not None else 0
    required_free = max(512 * 1024**2, estimated * 2)
    recommended = max(20 * 1024**3, required_free * 2)
    try:
        free = int(disk_usage(disk_anchor).free)
        if free < required_free:
            checks.append(PreflightCheck("disk", "Disk Space", PreflightLevel.BLOCK, f"Free {free / 1024**3:.1f} GB < minimum {required_free / 1024**3:.1f} GB."))
        elif free < recommended:
            checks.append(PreflightCheck("disk", "Disk Space", PreflightLevel.WARN, f"Free {free / 1024**3:.1f} GB < recommended {recommended / 1024**3:.1f} GB."))
        else:
            checks.append(PreflightCheck("disk", "Disk Space", PreflightLevel.PASS, f"Free {free / 1024**3:.1f} GB."))
    except Exception as exc:
        checks.append(PreflightCheck("disk", "Disk Space", PreflightLevel.BLOCK, f"Disk space tidak dapat diperiksa: {exc}"))

    return PreflightReport(
        snapshot=snapshot,
        settings_signature=settings.signature(),
        checks=tuple(checks),
        capability=capability,
        encoder=encoder,
        estimated_output_bytes=estimated,
        required_free_bytes=required_free,
        recommended_free_bytes=recommended,
    )
