from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.render_center_model_step10 import RenderSettings, settings_from_preset
from full_album_maker.render_preflight_step10 import (
    EncoderResolution,
    FFmpegCapability,
    PreflightLevel,
    probe_ffmpeg,
    resolve_encoder,
    run_preflight,
    verify_encoder_runtime,
)


def _document(tmp_path: Path, *, missing: bool = False) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Preflight")
    audio_path = tmp_path / "audio.wav"
    fingerprint = {}
    if not missing:
        audio_path.write_bytes(b"non-empty-audio")
        stat = audio_path.stat()
        fingerprint = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    audio = MediaAsset(
        kind="audio",
        locator=str(audio_path),
        original_name=audio_path.name,
        fingerprint=fingerprint,
        source_duration_tick=10 * TIMEBASE,
    )
    doc.media.append(audio)
    doc.playlist.entries.append(
        SongInstance(asset_id=audio.asset_id, display_title="Lagu", source_out_tick=10 * TIMEBASE)
    )
    doc.validate()
    return doc


def _capability(*, runtime_nvenc: bool = False, h265: bool = True) -> FFmpegCapability:
    encoders = {"libx264", "h264_nvenc"}
    if h265:
        encoders.update({"libx265", "hevc_nvenc"})
    return FFmpegCapability(
        ffmpeg="/portable/tools/ffmpeg/ffmpeg",
        ffprobe="/portable/tools/ffmpeg/ffprobe",
        version="ffmpeg version fixture",
        encoders=frozenset(encoders),
        runtime_verified_encoders=frozenset({"h264_nvenc"} if runtime_nvenc else set()),
        source="bundled",
    )


def _levels(report) -> dict[str, PreflightLevel]:
    return {item.key: item.level for item in report.checks}


def _disk_ok(_path):
    return SimpleNamespace(total=100 * 1024**3, used=10 * 1024**3, free=90 * 1024**3)


def test_probe_ffmpeg_parses_bounded_diagnostics_without_shell() -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if args[-1] == "-version":
            name = Path(args[0]).name
            return SimpleNamespace(stdout=f"{name} version 7.0 fixture\n", stderr="", returncode=0)
        if args[-1] == "-encoders":
            return SimpleNamespace(stdout=" V..... libx264 fixture\n V..... h264_nvenc fixture\n", stderr="", returncode=0)
        raise AssertionError(args)

    capability = probe_ffmpeg("C:/Portable App/tools/ffmpeg/ffmpeg.exe", "C:/Portable App/tools/ffmpeg/ffprobe.exe", run=fake_run)
    assert capability.source == "bundled"
    assert capability.has_encoder("libx264")
    assert capability.has_encoder("h264_nvenc")
    assert all(isinstance(call, list) for call in calls)


def test_runtime_probe_is_required_for_explicit_hardware_encoder(tmp_path: Path) -> None:
    settings = RenderSettings(filename="nvenc", output_folder=str(tmp_path), hardware_mode="h264_nvenc")
    with pytest.raises(RuntimeError, match="runtime probe"):
        resolve_encoder(settings, _capability(runtime_nvenc=False))
    resolved = resolve_encoder(settings, _capability(runtime_nvenc=True))
    assert resolved == EncoderResolution("h264_nvenc", True, False, "Hardware encoder lolos runtime probe.")


def test_auto_uses_verified_hardware_else_explicit_software_fallback(tmp_path: Path) -> None:
    settings = settings_from_preset("youtube_1080p", filename="auto", output_folder=str(tmp_path))
    fallback = resolve_encoder(settings, _capability(runtime_nvenc=False))
    assert fallback.encoder == "libx264" and fallback.fallback_used is True
    hardware = resolve_encoder(settings, _capability(runtime_nvenc=True))
    assert hardware.encoder == "h264_nvenc" and hardware.hardware is True


def test_verify_encoder_runtime_only_marks_successful_tiny_probe() -> None:
    cap = _capability(runtime_nvenc=False)

    def ok_run(args, **kwargs):
        assert args[0] == cap.ffmpeg and "h264_nvenc" in args and isinstance(args, list)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert verify_encoder_runtime(cap, "h264_nvenc", run=ok_run).runtime_verified("h264_nvenc")

    def fail_run(args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="driver unavailable")

    assert not verify_encoder_runtime(cap, "h264_nvenc", run=fail_run).runtime_verified("h264_nvenc")


def test_preflight_passes_snapshot_media_timeline_ffmpeg_output_and_encoder(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    settings = settings_from_preset("youtube_1080p", filename="final", output_folder=str(output))
    report = run_preflight(doc, settings, capability=_capability(runtime_nvenc=False), disk_usage=_disk_ok)
    levels = _levels(report)
    assert report.ready is True and report.snapshot is not None
    assert levels["snapshot"] == PreflightLevel.PASS
    assert levels["timeline"] == PreflightLevel.PASS
    assert levels["media"] == PreflightLevel.PASS
    assert levels["output_source"] == PreflightLevel.PASS
    assert levels["ffmpeg"] == PreflightLevel.PASS
    assert levels["output"] == PreflightLevel.PASS
    assert levels["disk"] == PreflightLevel.PASS
    assert levels["encoder"] == PreflightLevel.WARN
    assert report.encoder and report.encoder.encoder == "libx264"


def test_missing_required_media_blocks_before_render(tmp_path: Path) -> None:
    doc = _document(tmp_path, missing=True)
    output = tmp_path / "output"
    output.mkdir()
    settings = settings_from_preset("youtube_1080p", filename="missing", output_folder=str(output))
    report = run_preflight(doc, settings, capability=_capability(), disk_usage=_disk_ok)
    assert _levels(report)["media"] == PreflightLevel.BLOCK
    assert report.blocked is True


def test_changed_source_fingerprint_blocks_before_render(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    source = Path(doc.media[0].locator)
    source.write_bytes(b"changed-and-longer-source")
    output = tmp_path / "output"
    output.mkdir()
    settings = settings_from_preset("youtube_1080p", filename="changed", output_folder=str(output))
    report = run_preflight(doc, settings, capability=_capability(), disk_usage=_disk_ok)
    check = next(item for item in report.checks if item.key == "media")
    assert check.level == PreflightLevel.BLOCK
    assert "changed-size" in check.message or "changed-mtime" in check.message


def test_missing_fingerprint_is_visible_warning_not_fake_pass(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    doc.media[0].fingerprint = {}
    output = tmp_path / "output"
    output.mkdir()
    report = run_preflight(
        doc,
        settings_from_preset("youtube_1080p", filename="warn", output_folder=str(output)),
        capability=_capability(),
        disk_usage=_disk_ok,
    )
    assert _levels(report)["media"] == PreflightLevel.WARN
    assert report.ready is True


def test_output_may_never_overwrite_active_source(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    old = Path(doc.media[0].locator)
    source = tmp_path / "same.mp4"
    old.replace(source)
    stat = source.stat()
    doc.media[0].locator = str(source)
    doc.media[0].original_name = source.name
    doc.media[0].fingerprint = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    doc.validate()
    settings = settings_from_preset("youtube_1080p", filename="same.mp4", output_folder=str(tmp_path))
    report = run_preflight(doc, settings, capability=_capability(), disk_usage=_disk_ok)
    assert _levels(report)["output_source"] == PreflightLevel.BLOCK
    assert report.ready is False


def test_invalid_timeline_snapshot_blocks(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    doc.playlist.entries[0].source_out_tick = 20 * TIMEBASE
    output = tmp_path / "output"
    output.mkdir()
    settings = settings_from_preset("youtube_1080p", filename="invalid", output_folder=str(output))
    report = run_preflight(doc, settings, capability=_capability(), disk_usage=_disk_ok)
    levels = _levels(report)
    assert levels["snapshot"] == PreflightLevel.BLOCK
    assert levels["timeline"] == PreflightLevel.BLOCK
    assert report.ready is False


def test_existing_final_requires_explicit_overwrite(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.mp4").write_bytes(b"old-final")
    blocked = run_preflight(
        doc,
        settings_from_preset("youtube_1080p", filename="existing", output_folder=str(output)),
        capability=_capability(), disk_usage=_disk_ok,
    )
    assert _levels(blocked)["output"] == PreflightLevel.BLOCK

    overwrite = RenderSettings(**{
        **settings_from_preset("youtube_1080p", filename="existing", output_folder=str(output)).__dict__,
        "overwrite": True,
    })
    warned = run_preflight(doc, overwrite, capability=_capability(), disk_usage=_disk_ok)
    assert _levels(warned)["output"] == PreflightLevel.WARN
    assert warned.ready is True


def test_disk_warn_and_block_are_real_thresholds(tmp_path: Path) -> None:
    doc = _document(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    settings = settings_from_preset("youtube_1080p", filename="disk", output_folder=str(output))
    warn_disk = lambda _path: SimpleNamespace(total=100 * 1024**3, used=82 * 1024**3, free=18 * 1024**3)
    warn = run_preflight(doc, settings, capability=_capability(), disk_usage=warn_disk)
    assert _levels(warn)["disk"] == PreflightLevel.WARN and warn.ready is True

    block_disk = lambda _path: SimpleNamespace(total=100 * 1024**3, used=99.9 * 1024**3, free=100 * 1024**2)
    blocked = run_preflight(doc, settings, capability=_capability(), disk_usage=block_disk)
    assert _levels(blocked)["disk"] == PreflightLevel.BLOCK and blocked.ready is False
