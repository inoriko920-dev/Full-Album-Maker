from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import threading
from typing import Iterable

import numpy as np

from .audio_analysis_contract import (
    ANALYSIS_SCHEMA,
    ANALYSIS_SCHEMA_VERSION,
    AnalysisCurve,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisQuality,
    AudioAnalysisResult,
    TempoSummary,
)
from .atomic_io import atomic_write_text
from .audio_analysis_fingerprint import AnalysisCancelled
from .paths import data_dir

CACHE_FORMAT = "full-album-maker-audio-analysis-cache-v1"


class CacheCorruptError(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheMaintenanceReport:
    removed_partial_entries: int = 0
    removed_temp_files: int = 0
    removed_quarantine_entries: int = 0
    reclaimed_bytes: int = 0


def _tree_size(path: Path) -> int:
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0
    total = 0
    try:
        values = tuple(path.rglob("*"))
    except OSError:
        return 0
    for item in values:
        if item.is_file():
            try:
                total += int(item.stat().st_size)
            except OSError:
                pass
    return total


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise AnalysisCancelled("analysis cache publish cancelled")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _default_root() -> Path:
    root = data_dir() / "cache" / "audio-analysis-v1"
    root.mkdir(parents=True, exist_ok=True)
    return root


class AudioAnalysisCache:
    """Disposable, content-addressed analysis cache.

    A cache entry is committed only when manifest.json is atomically published.
    curves.npz is published first and its digest is verified when loading.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else _default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.quarantine_root = self.root / "_corrupt"

    def entry_dir(self, key: str) -> Path:
        if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key.lower()):
            raise ValueError("cache key must be a sha256 digest")
        return self.root / key.lower()

    def load(self, key: str) -> AudioAnalysisResult | None:
        folder = self.entry_dir(key)
        manifest_path = folder / "manifest.json"
        curves_path = folder / "curves.npz"
        if not manifest_path.is_file():
            return None
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._validate_manifest(raw, key)
            if not curves_path.is_file():
                raise CacheCorruptError("curves.npz missing")
            actual = _sha256_file(curves_path)
            if actual != raw["curves_sha256"]:
                raise CacheCorruptError("curves checksum mismatch")
            with np.load(curves_path, allow_pickle=False) as archive:
                curves = tuple(
                    AnalysisCurve(
                        name=name,
                        values=tuple(float(v) for v in np.asarray(archive[name], dtype=np.float32)),
                        start_tick=int(raw["curve_timing"][name]["start_tick"]),
                        tick_step=int(raw["curve_timing"][name]["tick_step"]),
                    )
                    for name in raw["curve_names"]
                )
            result = self._result_from_manifest(raw, curves)
            result.validate()
            return result
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, CacheCorruptError) as exc:
            self.quarantine(key, reason=str(exc))
            return None

    def publish(
        self,
        key: str,
        result: AudioAnalysisResult,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        result.validate()
        _raise_if_cancelled(cancel_event)
        folder = self.entry_dir(key)
        folder.mkdir(parents=True, exist_ok=True)
        manifest_path = folder / "manifest.json"
        curves_path = folder / "curves.npz"

        # Stage compressed curve bytes completely before exposing them.
        arrays = {curve.name: np.asarray(curve.values, dtype=np.float32) for curve in result.curves}
        buffer = io.BytesIO()
        _raise_if_cancelled(cancel_event)
        np.savez_compressed(buffer, **arrays)
        curve_bytes = buffer.getvalue()
        _raise_if_cancelled(cancel_event)
        curve_sha = hashlib.sha256(curve_bytes).hexdigest()

        fd, temp_name = tempfile.mkstemp(prefix=".curves.", suffix=".npz.tmp", dir=str(folder))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(curve_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            _raise_if_cancelled(cancel_event)
            os.replace(temp_path, curves_path)
        finally:
            temp_path.unlink(missing_ok=True)

        manifest = self._manifest(result, key, curve_sha)
        # Commit marker: manifest is always the final write.
        atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        return folder

    def invalidate(self, *, content_sha256: str | None = None, key: str | None = None) -> int:
        candidates: Iterable[Path]
        if key is not None:
            candidates = (self.entry_dir(key),)
        else:
            candidates = (p for p in self.root.iterdir() if p.is_dir() and p.name != "_corrupt")
        removed = 0
        for folder in candidates:
            if not folder.exists():
                continue
            if content_sha256 is not None:
                try:
                    raw = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
                except Exception:
                    continue
                if raw.get("content_sha256") != content_sha256.lower():
                    continue
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
        return removed

    def quarantine(self, key: str, *, reason: str = "") -> Path | None:
        folder = self.entry_dir(key)
        if not folder.exists():
            return None
        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        target = self.quarantine_root / f"{key}.{stamp}.{os.getpid()}"
        try:
            os.replace(folder, target)
        except OSError:
            shutil.rmtree(folder, ignore_errors=True)
            return None
        if reason:
            try:
                (target / "CORRUPTION.txt").write_text(reason[:2000] + "\n", encoding="utf-8")
            except OSError:
                pass
        return target

    def maintenance(
        self,
        *,
        stale_partial_seconds: float = 3600.0,
        max_quarantine_entries: int = 32,
        max_quarantine_bytes: int = 256 * 1024 * 1024,
    ) -> CacheMaintenanceReport:
        now = time.time()
        stale = max(0.0, float(stale_partial_seconds))
        removed_partial = 0
        removed_temp = 0
        removed_quarantine = 0
        reclaimed = 0

        for folder in tuple(self.root.iterdir()):
            if not folder.is_dir() or folder.name == "_corrupt":
                continue
            manifest = folder / "manifest.json"
            if not manifest.is_file():
                try:
                    age = now - folder.stat().st_mtime
                except OSError:
                    age = stale
                if age >= stale:
                    size = _tree_size(folder)
                    shutil.rmtree(folder, ignore_errors=True)
                    removed_partial += 1
                    reclaimed += size
                    continue
            for temp_path in tuple(folder.glob(".curves.*.tmp")):
                try:
                    age = now - temp_path.stat().st_mtime
                except OSError:
                    age = stale
                if age >= stale:
                    size = _tree_size(temp_path)
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        continue
                    removed_temp += 1
                    reclaimed += size

        entries = []
        if self.quarantine_root.is_dir():
            for item in self.quarantine_root.iterdir():
                if item.is_dir():
                    try:
                        mtime = item.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    entries.append((mtime, item, _tree_size(item)))
        entries.sort(key=lambda item: (item[0], item[1].name))
        total_bytes = sum(item[2] for item in entries)
        max_entries = max(0, int(max_quarantine_entries))
        max_bytes = max(0, int(max_quarantine_bytes))
        while entries and (len(entries) > max_entries or total_bytes > max_bytes):
            _mtime, item, size = entries.pop(0)
            shutil.rmtree(item, ignore_errors=True)
            removed_quarantine += 1
            reclaimed += size
            total_bytes = max(0, total_bytes - size)

        return CacheMaintenanceReport(
            removed_partial_entries=removed_partial,
            removed_temp_files=removed_temp,
            removed_quarantine_entries=removed_quarantine,
            reclaimed_bytes=reclaimed,
        )

    @staticmethod
    def _manifest(result: AudioAnalysisResult, key: str, curve_sha: str) -> dict:
        return {
            "cache_format": CACHE_FORMAT,
            "schema": ANALYSIS_SCHEMA,
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "cache_key": key,
            "asset_id": result.asset_id,
            "content_sha256": result.content_sha256,
            "settings_signature": result.settings_signature,
            "analyzer_version": result.analyzer_version,
            "duration_tick": result.duration_tick,
            "sample_rate": result.sample_rate,
            "hop_length": result.hop_length,
            "source_name": result.source_name,
            "tempo": {
                "bpm": result.tempo.bpm,
                "confidence": result.tempo.confidence,
                "quality": result.tempo.quality.value,
                "beat_interval_cv": result.tempo.beat_interval_cv,
            },
            "quality_flags": list(result.quality_flags),
            "beats": [
                {"tick": e.tick, "strength": e.strength, "confidence": e.confidence}
                for e in result.beats
            ],
            "onsets": [
                {"tick": e.tick, "strength": e.strength, "confidence": e.confidence}
                for e in result.onsets
            ],
            "curve_names": [curve.name for curve in result.curves],
            "curve_timing": {
                curve.name: {"start_tick": curve.start_tick, "tick_step": curve.tick_step}
                for curve in result.curves
            },
            "curves_sha256": curve_sha,
        }

    @staticmethod
    def _validate_manifest(raw: dict, key: str) -> None:
        if raw.get("cache_format") != CACHE_FORMAT:
            raise CacheCorruptError("cache format mismatch")
        if raw.get("schema") != ANALYSIS_SCHEMA or raw.get("schema_version") != ANALYSIS_SCHEMA_VERSION:
            raise CacheCorruptError("analysis schema mismatch")
        if raw.get("cache_key") != key:
            raise CacheCorruptError("cache key mismatch")
        digest = str(raw.get("curves_sha256", ""))
        if len(digest) != 64:
            raise CacheCorruptError("invalid curves checksum")

    @staticmethod
    def _result_from_manifest(raw: dict, curves: tuple[AnalysisCurve, ...]) -> AudioAnalysisResult:
        tempo_raw = raw["tempo"]
        tempo = TempoSummary(
            bpm=float(tempo_raw["bpm"]),
            confidence=float(tempo_raw["confidence"]),
            quality=AnalysisQuality(str(tempo_raw["quality"])),
            beat_interval_cv=float(tempo_raw.get("beat_interval_cv", 1.0)),
        )
        beat_conf = tempo.confidence
        beats = tuple(
            AnalysisEvent(int(item["tick"]), AnalysisEventType.BEAT, float(item["strength"]), float(item.get("confidence", beat_conf)))
            for item in raw.get("beats", [])
        )
        onsets = tuple(
            AnalysisEvent(int(item["tick"]), AnalysisEventType.ONSET, float(item["strength"]), float(item.get("confidence", item["strength"])))
            for item in raw.get("onsets", [])
        )
        return AudioAnalysisResult(
            asset_id=str(raw["asset_id"]),
            content_sha256=str(raw["content_sha256"]),
            settings_signature=str(raw["settings_signature"]),
            analyzer_version=str(raw["analyzer_version"]),
            duration_tick=int(raw["duration_tick"]),
            sample_rate=int(raw["sample_rate"]),
            hop_length=int(raw["hop_length"]),
            tempo=tempo,
            quality_flags=tuple(str(x) for x in raw.get("quality_flags", [])),
            beats=beats,
            onsets=onsets,
            curves=curves,
            source_name=str(raw.get("source_name", "")),
        )
