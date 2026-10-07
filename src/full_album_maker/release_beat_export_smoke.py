from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw

from .album_visuals import make_song_cover_layer, make_vinyl_layer
from .animation_signal_contract import AnimationSignalChannel
from .beat_visual_runtime import build_beat_visual_runtime
from .editor_models import MediaAsset, ProjectDocument, SongInstance, seconds_to_tick
from .paths import app_root, ffmpeg_path, ffprobe_path, temp_dir
from .spectrum_feature import make_spectrum_layer
from .spectrum_render_step08 import Step08FFmpegCompiler


def _run(args, *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=True,
    )


def _write_click_wav(path: Path, *, bpm: float = 120.0, seconds: float = 5.0) -> None:
    sample_rate = 24_000
    count = int(sample_rate * seconds)
    data = np.zeros(count, dtype=np.float32)
    step = 60.0 * sample_rate / bpm
    for index in range(int(seconds * bpm / 60.0) + 1):
        start = int(round(index * step))
        if start >= count:
            break
        length = min(240, count - start)
        if length <= 1:
            continue
        pulse = np.hanning(length * 2)[:length].astype(np.float32)
        data[start:start + length] += pulse
    pcm = np.clip(data * 0.88, -1.0, 1.0)
    pcm_i16 = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm_i16.tobytes())


def _write_cover(path: Path) -> None:
    image = Image.new("RGB", (480, 480), "#15213a")
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 22, 457, 457), outline="#72b6ff", width=14)
    draw.ellipse((115, 115, 365, 365), fill="#2467a8", outline="#cfe8ff", width=10)
    draw.ellipse((210, 210, 270, 270), fill="#f1f6fb")
    image.save(path)


def _report_path() -> Path:
    return temp_dir() / "beat-export-smoke.json"


def _write_report(payload: dict) -> Path:
    target = _report_path()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def run_beat_export_smoke() -> int:
    root = app_root().resolve()
    report: dict[str, object] = {
        "ok": False,
        "app_root": str(root),
        "api_key_present": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    }
    try:
        ffmpeg = ffmpeg_path()
        ffprobe = ffprobe_path()
        if not ffmpeg or not ffprobe:
            raise RuntimeError("Bundled FFmpeg/ffprobe tidak tersedia.")

        work = temp_dir() / "release-beat-export-smoke"
        work.mkdir(parents=True, exist_ok=True)
        audio_path = work / "beat-120.wav"
        image_path = work / "cover.png"
        output_path = work / "beat-v2-smoke.mp4"
        _write_click_wav(audio_path)
        _write_cover(image_path)

        duration_tick = seconds_to_tick(5.0)
        doc = ProjectDocument.new_empty("Beat V2 Portable Smoke")
        doc.canvas.width = 640
        doc.canvas.height = 360
        doc.canvas.fps_num = 30
        doc.canvas.fps_den = 1

        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=duration_tick,
        )
        cover_asset = MediaAsset(
            kind="image",
            locator=str(image_path),
            original_name=image_path.name,
        )
        doc.media.extend([audio, cover_asset])
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title="Beat V2 RC Smoke",
            display_artist="Full Album Maker",
            cover_asset_id=cover_asset.asset_id,
            source_out_tick=duration_tick,
        )
        doc.playlist.entries.append(song)

        track_id = doc.tracks[0].track_id
        cover = make_song_cover_layer(track_id, 10, fallback_asset_id=cover_asset.asset_id)
        cover.animation = {
            "beat_v1": {
                "enabled": True,
                "presets": ["subtle_beat_pulse"],
                "intensity": 1.0,
            }
        }
        vinyl = make_vinyl_layer(track_id, 20)
        vinyl.properties["bpm_sync"] = True
        vinyl.properties["beats_per_rotation"] = 4.0
        vinyl.properties["bpm_sync_min_confidence"] = 0.55
        spectrum = make_spectrum_layer(track_id, 30, preset_id="neon_bars")
        spectrum.animation = {
            "beat_v1": {
                "enabled": True,
                "presets": ["onset_flash"],
                "intensity": 1.0,
            }
        }
        doc.layers.extend([cover, vinyl, spectrum])
        doc.validate()

        runtime = build_beat_visual_runtime(
            doc,
            ffmpeg_executable=ffmpeg,
            ensure_analysis=True,
        )
        if runtime is None or runtime.diagnostics.trigger_count <= 0:
            raise RuntimeError("Beat runtime tidak menghasilkan trigger.")

        beat_trigger = next(
            (t for t in runtime.signal_engine.program.triggers if t.channel == AnimationSignalChannel.BEAT),
            None,
        )
        onset_trigger = next(
            (t for t in runtime.signal_engine.program.triggers if t.channel == AnimationSignalChannel.ONSET),
            None,
        )
        if beat_trigger is None or onset_trigger is None:
            raise RuntimeError("Beat/onset trigger smoke tidak tersedia.")

        cover_state = runtime.state_for_layer(cover.layer_id, beat_trigger.event_tick)
        spectrum_state = runtime.state_for_layer(spectrum.layer_id, onset_trigger.event_tick)
        if cover_state.scale_multiplier <= 1.0:
            raise RuntimeError("Cover Beat preset tidak aktif pada trigger.")
        if spectrum_state.glow_amount <= 0.0:
            raise RuntimeError("Spectrum Beat modulation tidak aktif pada onset.")

        fallback_spin = float(vinyl.properties.get("spin_seconds", 8.0))
        synced_spin = runtime.vinyl_spin_seconds_at(
            beat_trigger.event_tick,
            fallback_spin_seconds=fallback_spin,
            beats_per_rotation=4.0,
            min_confidence=0.55,
        )
        if not (0.5 < synced_spin < fallback_spin):
            raise RuntimeError(f"Vinyl BPM Sync tidak aktif: {synced_spin}")

        compiler = Step08FFmpegCompiler(ffmpeg, beat_runtime=runtime)
        compiled = compiler.compile_video(doc, output_path, work / "compile", include_audio=True)
        _run(compiled.args, timeout=180)
        if not output_path.is_file() or output_path.stat().st_size <= 0:
            raise RuntimeError("Beat V2 export smoke tidak menghasilkan MP4.")

        probe = _run([
            ffprobe, "-v", "error",
            "-show_entries", "stream=codec_type",
            "-show_entries", "format=duration",
            "-of", "json",
            str(output_path),
        ], timeout=30)
        data = json.loads(probe.stdout)
        streams = sorted(item.get("codec_type", "") for item in data.get("streams", []))
        if "audio" not in streams or "video" not in streams:
            raise RuntimeError(f"Beat V2 smoke output tidak memiliki A/V: {streams}")

        report.update({
            "ok": True,
            "output": str(output_path),
            "output_bytes": output_path.stat().st_size,
            "output_streams": streams,
            "trigger_count": runtime.diagnostics.trigger_count,
            "event_count": runtime.diagnostics.event_count,
            "cover_scale_at_beat": cover_state.scale_multiplier,
            "spectrum_glow_at_onset": spectrum_state.glow_amount,
            "vinyl_synced_spin_seconds": synced_spin,
            "api_key_present": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        })
        target = _write_report(report)
        print(f"STEP15_BEAT_EXPORT_SMOKE_OK {target}")
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        target = _write_report(report)
        print(f"STEP15_BEAT_EXPORT_SMOKE_FAILED {target}: {report['error']}")
        return 2
