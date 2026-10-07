from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Callable, Generic, TypeVar

import numpy as np

from .audio_analysis_backend import analyze_pcm
from .audio_analysis_cache import AudioAnalysisCache
from .audio_analysis_contract import (
    ANALYZER_VERSION,
    AnalysisCurve,
    AnalysisError,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisProgress,
    AnalysisQuality,
    AnalysisTicket,
    AudioAnalysisResult,
    HOP_LENGTH,
    SAMPLE_RATE,
    TICKS_PER_FRAME,
    event_tuple,
)
from .audio_analysis_decode import DecodeError, NoAudioStreamError, decode_to_f32
from .audio_analysis_fingerprint import (
    AnalysisCancelled,
    AnalyzerSettings,
    SourceChangedError,
    cache_key,
    hash_source,
    snapshot,
)
from .audio_analysis_quality import QualityDiagnostics, evaluate_quality
from .editor_models import MediaAsset
from .paths import temp_dir

T = TypeVar("T")


class CallbackSignal(Generic[T]):
    """Tiny thread-safe callback signal so the service remains Qt-independent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args) -> None:
        with self._lock:
            callbacks = tuple(self._callbacks)
        for callback in callbacks:
            callback(*args)


@dataclass
class _Job:
    ticket: AnalysisTicket
    asset: MediaAsset
    force: bool
    cancel_event: threading.Event
    generation: int


class AudioAnalysisService:
    """Single-heavy-worker audio analysis service with cache and stale guards."""

    def __init__(
        self,
        *,
        cache: AudioAnalysisCache | None = None,
        settings: AnalyzerSettings | None = None,
        workers: int = 1,
        ffmpeg_executable: str | None = None,
        analyzer: Callable = analyze_pcm,
        decoder: Callable = decode_to_f32,
        temp_root: str | Path | None = None,
    ) -> None:
        self.cache = cache or AudioAnalysisCache()
        self.settings = settings or AnalyzerSettings()
        self.ffmpeg_executable = ffmpeg_executable
        self._analyzer = analyzer
        self._decoder = decoder
        self._temp_root = Path(temp_root) if temp_root is not None else temp_dir() / "audio-analysis-v1"
        self._temp_root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=max(1, min(1, int(workers))), thread_name_prefix="fam-audio-analysis")
        self._lock = threading.RLock()
        self._token = 0
        self._generation = 0
        self._pending_by_asset: dict[str, Future] = {}
        self._jobs_by_asset: dict[str, _Job] = {}
        self._last_result_by_asset: dict[str, AudioAnalysisResult] = {}
        self._closed = False

        self.state_changed = CallbackSignal()
        self.progress_changed = CallbackSignal()
        self.result_ready = CallbackSignal()
        self.request_failed = CallbackSignal()
        self.busy_changed = CallbackSignal()

    def request(self, asset: MediaAsset, *, force: bool = False) -> AnalysisTicket:
        if asset.kind != "audio":
            raise ValueError("AudioAnalysisService accepts audio MediaAsset only")
        asset.validate()
        with self._lock:
            if self._closed:
                raise RuntimeError("analysis service is closed")
            existing = self._jobs_by_asset.get(asset.asset_id)
            if existing is not None:
                return existing.ticket
            self._token += 1
            ticket = AnalysisTicket(self._token, asset.asset_id)
            job = _Job(ticket, asset, bool(force), threading.Event(), self._generation)
            future = self._executor.submit(self._run_job, job)
            self._jobs_by_asset[asset.asset_id] = job
            self._pending_by_asset[asset.asset_id] = future
            future.add_done_callback(lambda done, aid=asset.asset_id, tok=ticket.token: self._finish(aid, tok, done))
            busy = len(self._pending_by_asset) == 1
        if busy:
            self.busy_changed.emit(True)
        return ticket

    def peek_cached(self, asset: MediaAsset) -> AudioAnalysisResult | None:
        source = Path(asset.locator)
        if not source.is_file():
            return None
        digest, _ = hash_source(source)
        key = cache_key(digest, self.settings.signature())
        result = self.cache.load(key)
        if result is None:
            return None
        # Cache is content-addressed; the same bytes can legitimately have a new asset_id.
        if result.asset_id != asset.asset_id:
            result = AudioAnalysisResult(
                asset_id=asset.asset_id,
                content_sha256=result.content_sha256,
                settings_signature=result.settings_signature,
                analyzer_version=result.analyzer_version,
                duration_tick=result.duration_tick,
                sample_rate=result.sample_rate,
                hop_length=result.hop_length,
                tempo=result.tempo,
                quality_flags=result.quality_flags,
                beats=result.beats,
                onsets=result.onsets,
                curves=result.curves,
                source_name=asset.original_name or source.name,
            )
        return result

    def invalidate(self, asset: MediaAsset) -> int:
        source = Path(asset.locator)
        if not source.is_file():
            return 0
        digest, _ = hash_source(source)
        removed = self.cache.invalidate(content_sha256=digest)
        with self._lock:
            self._last_result_by_asset.pop(asset.asset_id, None)
        return removed

    def cancel(self, asset_id: str | None = None) -> bool:
        cancelled = False
        with self._lock:
            jobs = list(self._jobs_by_asset.values()) if asset_id is None else ([self._jobs_by_asset[asset_id]] if asset_id in self._jobs_by_asset else [])
            for job in jobs:
                if not job.cancel_event.is_set():
                    job.cancel_event.set()
                    cancelled = True
            if asset_id is None:
                self._generation += 1
        return cancelled

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        with self._lock:
            pending = tuple(self._pending_by_asset.values())
        if not pending:
            return True
        _, not_done = wait(pending, timeout=max(0.0, float(timeout)))
        return not not_done

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            for job in self._jobs_by_asset.values():
                job.cancel_event.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._pending_by_asset)

    def _emit_progress(self, job: _Job, state: str, fraction: float, message: str = "") -> None:
        with self._lock:
            if job.generation != self._generation or job.cancel_event.is_set():
                return
        progress = AnalysisProgress(state, max(0.0, min(1.0, float(fraction))), message)
        self.state_changed.emit(job.ticket, state)
        self.progress_changed.emit(job.ticket, progress)

    def _run_job(self, job: _Job) -> AudioAnalysisResult:
        source = Path(job.asset.locator)
        if not source.is_file():
            raise _ServiceFailure("SOURCE_MISSING", "File audio tidak ditemukan.", True)
        try:
            self._emit_progress(job, "fingerprint", 0.02, "Memeriksa identitas audio")
            digest, source_snapshot = hash_source(
                source,
                job.cancel_event,
                lambda x: self._emit_progress(job, "fingerprint", 0.02 + 0.13 * x, "Menghitung fingerprint audio"),
            )
            settings_signature = self.settings.signature()
            key = cache_key(digest, settings_signature)
            if not job.force:
                self._emit_progress(job, "cache_lookup", 0.16, "Memeriksa cache analisis")
                cached = self.cache.load(key)
                if cached is not None:
                    self._emit_progress(job, "ready", 1.0, "Analisis dimuat dari cache")
                    return self._rebind_asset(cached, job.asset)

            _raise_if_cancelled(job.cancel_event)
            work = Path(tempfile.mkdtemp(prefix=f"fam-analysis-{job.asset.asset_id[:8]}-", dir=str(self._temp_root)))
            try:
                pcm_path = work / "audio.f32"
                self._emit_progress(job, "decode", 0.18, "Mendekode audio")
                try:
                    self._decoder(source, pcm_path, cancel_event=job.cancel_event, executable=self.ffmpeg_executable)
                except TypeError:
                    # Test doubles may expose a smaller signature.
                    self._decoder(source, pcm_path, cancel_event=job.cancel_event)
                _raise_if_cancelled(job.cancel_event)
                if snapshot(source) != source_snapshot:
                    raise SourceChangedError("source changed during decode")

                self._emit_progress(job, "features", 0.36, "Menganalisis energi, frekuensi, beat, dan onset")
                output = self._analyzer(
                    pcm_path,
                    self.settings,
                    cancel_event=job.cancel_event,
                    on_progress=lambda x: self._emit_progress(job, "features", 0.36 + 0.42 * x, "Menganalisis fitur audio"),
                )
                _raise_if_cancelled(job.cancel_event)
                if snapshot(source) != source_snapshot:
                    raise SourceChangedError("source changed during analysis")

                self._emit_progress(job, "quality", 0.80, "Menilai kualitas beat")
                tempo, flags = evaluate_quality(QualityDiagnostics(
                    duration_tick=output.duration_tick,
                    tempo_bpm=output.tempo_bpm,
                    beat_count=len(output.beat_frames),
                    beat_interval_cv=output.beat_interval_cv,
                    rms_mean=output.rms_mean,
                    rms_peak=output.rms_peak,
                    onset_mean=output.onset_mean,
                    onset_peak=output.onset_peak,
                ))
                result = self._build_result(job.asset, digest, settings_signature, output, tempo, flags)
                result.validate()
                _raise_if_cancelled(job.cancel_event)
                self._emit_progress(job, "serialize", 0.88, "Menyiapkan cache analisis")
                try:
                    self.cache.publish(key, result)
                except (OSError, ValueError) as exc:
                    raise _ServiceFailure("CACHE_WRITE_FAILED", str(exc), True) from exc
                _raise_if_cancelled(job.cancel_event)
                self._emit_progress(job, "ready", 1.0, "Analisis audio selesai")
                return result
            finally:
                shutil.rmtree(work, ignore_errors=True)
        except AnalysisCancelled:
            raise _ServiceFailure("CANCELLED", "Analisis dibatalkan.", True)
        except SourceChangedError:
            raise _ServiceFailure("SOURCE_CHANGED", "File audio berubah saat dianalisis. Jalankan ulang analisis.", True)
        except FileNotFoundError as exc:
            if "FFmpeg" in str(exc) or "ffmpeg" in str(exc):
                raise _ServiceFailure("FFMPEG_UNAVAILABLE", "FFmpeg tidak tersedia untuk analisis audio.", True) from exc
            raise _ServiceFailure("SOURCE_MISSING", "File audio tidak ditemukan.", True) from exc
        except NoAudioStreamError as exc:
            raise _ServiceFailure("NO_AUDIO_STREAM", str(exc), False) from exc
        except DecodeError as exc:
            raise _ServiceFailure("DECODE_FAILED", str(exc), True) from exc
        except _ServiceFailure:
            raise
        except (OSError, ValueError) as exc:
            raise _ServiceFailure("ANALYZER_FAILED", str(exc), True) from exc
        except Exception as exc:
            raise _ServiceFailure("INTERNAL_ERROR", str(exc), True) from exc

    def _finish(self, asset_id: str, token: int, future: Future) -> None:
        with self._lock:
            job = self._jobs_by_asset.get(asset_id)
            current_generation = self._generation
            if job is None or job.ticket.token != token:
                return
            self._jobs_by_asset.pop(asset_id, None)
            self._pending_by_asset.pop(asset_id, None)
            emit = job.generation == current_generation and not self._closed
            busy = bool(self._pending_by_asset)
        if emit:
            try:
                result = future.result()
            except _ServiceFailure as exc:
                if exc.code != "CANCELLED":
                    self.request_failed.emit(job.ticket, AnalysisError(exc.code, exc.message, exc.retryable))
            except Exception as exc:
                self.request_failed.emit(job.ticket, AnalysisError("INTERNAL_ERROR", str(exc), True))
            else:
                with self._lock:
                    self._last_result_by_asset[asset_id] = result
                self.result_ready.emit(job.ticket, result)
        self.busy_changed.emit(busy)

    @staticmethod
    def _rebind_asset(result: AudioAnalysisResult, asset: MediaAsset) -> AudioAnalysisResult:
        return AudioAnalysisResult(
            asset_id=asset.asset_id,
            content_sha256=result.content_sha256,
            settings_signature=result.settings_signature,
            analyzer_version=result.analyzer_version,
            duration_tick=result.duration_tick,
            sample_rate=result.sample_rate,
            hop_length=result.hop_length,
            tempo=result.tempo,
            quality_flags=result.quality_flags,
            beats=result.beats,
            onsets=result.onsets,
            curves=result.curves,
            source_name=asset.original_name or Path(asset.locator).name,
        )

    @staticmethod
    def _build_result(asset: MediaAsset, digest: str, settings_signature: str, output, tempo, flags) -> AudioAnalysisResult:
        onset_curve = np.asarray(output.curves["onset"], dtype=np.float32)
        energy_curve = np.asarray(output.curves["energy"], dtype=np.float32)

        beats = []
        for frame in output.beat_frames:
            if tempo.quality in {AnalysisQuality.SILENT, AnalysisQuality.LOW}:
                # Low-confidence BPM is retained as metadata, but discrete beat triggers fail closed.
                break
            strength = float(max(onset_curve[frame], energy_curve[frame])) if frame < len(onset_curve) else 0.0
            beats.append(AnalysisEvent(frame * TICKS_PER_FRAME, AnalysisEventType.BEAT, _unit(strength), _unit(tempo.confidence)))

        onsets = []
        for frame in output.onset_frames:
            strength = float(onset_curve[frame]) if frame < len(onset_curve) else 0.0
            if strength <= 0.0:
                continue
            onsets.append(AnalysisEvent(frame * TICKS_PER_FRAME, AnalysisEventType.ONSET, _unit(strength), _unit(strength)))

        curves = tuple(
            AnalysisCurve(name=name, values=tuple(float(v) for v in np.asarray(output.curves[name], dtype=np.float32)))
            for name in ("energy", "bass", "mid", "high", "onset")
        )
        return AudioAnalysisResult(
            asset_id=asset.asset_id,
            content_sha256=digest,
            settings_signature=settings_signature,
            analyzer_version=ANALYZER_VERSION,
            duration_tick=int(output.duration_tick),
            sample_rate=SAMPLE_RATE,
            hop_length=HOP_LENGTH,
            tempo=tempo,
            quality_flags=tuple(flags),
            beats=event_tuple(beats),
            onsets=event_tuple(onsets),
            curves=curves,
            source_name=asset.original_name or Path(asset.locator).name,
        )


class _ServiceFailure(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _unit(value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def _raise_if_cancelled(event: threading.Event) -> None:
    if event.is_set():
        raise AnalysisCancelled("analysis cancelled")
