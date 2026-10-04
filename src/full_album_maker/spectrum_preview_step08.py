from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
import hashlib
import math
from pathlib import Path
import threading
from typing import Callable

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen

from .editor_models import ProjectDocument
from .paths import temp_dir
from .preview_scene import PreviewCanvas
from .preview_service import AccuratePreviewService
from .spectrum_feature import normalize_spectrum_properties


class SpectrumPreviewCanvas(PreviewCanvas):
    """Recovered preview canvas with a non-fake Spectrum fallback.

    Real audio-reactive pixels arrive through AccuratePreviewService. While that
    worker is pending/unavailable, Spectrum renders only a deterministic resting
    geometry. It never animates from playhead math, so silence/missing analysis
    cannot look like fake audio reactivity.
    """

    def _paint_approx_layer(self, painter: QPainter, rect: QRectF, layer) -> None:
        if layer.type != "spectrum":
            return super()._paint_approx_layer(painter, rect, layer)
        try:
            props = normalize_spectrum_properties(layer.properties)
        except Exception:
            props = normalize_spectrum_properties({})
        color = QColor(props["accent_color"])
        color.setAlphaF(max(0.0, min(1.0, float(layer.opacity))))
        pen_width = max(
            1.0,
            min(
                10.0,
                float(props["thickness"])
                * min(rect.width(), rect.height())
                / 1080.0,
            ),
        )
        painter.setPen(QPen(color, pen_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if props["spectrum_type"] == "circular":
            radius = min(rect.width(), rect.height()) * 0.39
            center = rect.center()
            count = max(16, min(128, int(props["band_count"])))
            baseline = max(1.0, min(rect.width(), rect.height()) * 0.012)
            for index in range(count):
                angle = (index / count) * math.tau - math.pi / 2
                start = QPointF(
                    center.x() + math.cos(angle) * radius,
                    center.y() + math.sin(angle) * radius,
                )
                end = QPointF(
                    center.x() + math.cos(angle) * (radius + baseline),
                    center.y() + math.sin(angle) * (radius + baseline),
                )
                painter.drawLine(start, end)
        else:
            count = max(16, min(128, int(props["band_count"])))
            baseline = max(2.0, rect.height() * 0.05)
            for index in range(count):
                x = rect.left() + (index + 0.5) * rect.width() / count
                painter.drawLine(
                    QPointF(x, rect.bottom()),
                    QPointF(x, rect.bottom() - baseline),
                )


PreviewServiceFactory = Callable[[], AccuratePreviewService]


class SpectrumAccuratePreview(QObject):
    preview_ready = Signal(int, str, str)

    def __init__(
        self,
        *,
        cache_root: str | Path | None = None,
        service_factory: PreviewServiceFactory | None = None,
        max_workers: int = 1,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.cache_root = (
            Path(cache_root)
            if cache_root is not None
            else temp_dir() / "spectrum-preview-step08-v1"
        )
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self._service_factory = service_factory or AccuratePreviewService
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="fam-spectrum-preview",
        )
        self._lock = threading.Lock()
        self._generation = 0
        self._pending: dict[int, Future] = {}

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @staticmethod
    def cache_key(document: ProjectDocument, tick: int) -> str:
        raw = (
            f"step08-v1|{document.content_signature()}|{max(0, int(tick))}"
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def request(self, document: ProjectDocument, tick: int) -> int:
        snapshot = document.clone()
        tick = max(0, int(tick))
        key = self.cache_key(snapshot, tick)
        destination = self.cache_root / f"{key}.png"
        with self._lock:
            self._generation += 1
            token = self._generation
        if destination.is_file() and destination.stat().st_size > 0:
            # Defer the cache-hit notification one event-loop turn. The caller
            # can then store the returned generation token before handling the
            # signal, exactly like the asynchronous render path.
            QTimer.singleShot(
                0,
                lambda value=token, path=str(destination): self._emit_if_current(
                    value,
                    path,
                    "CACHE_HIT",
                ),
            )
            return token

        future = self._executor.submit(
            self._render,
            token,
            snapshot,
            tick,
            destination,
        )
        with self._lock:
            self._pending[token] = future
        future.add_done_callback(
            lambda done, value=token: self._finish(value, done)
        )
        return token

    def invalidate(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def _emit_if_current(self, token: int, path: str, status: str) -> None:
        with self._lock:
            current = self._generation
        if int(token) != int(current):
            return
        self.preview_ready.emit(int(token), str(path), str(status))

    def _render(
        self,
        token: int,
        document: ProjectDocument,
        tick: int,
        destination: Path,
    ) -> tuple[int, str, str]:
        try:
            service = self._service_factory()
            path = service.render_frame(document, tick, destination)
            return token, str(path), "RENDERED"
        except Exception as exc:
            destination.unlink(missing_ok=True)
            return token, "", f"ERROR: {exc}"

    def _finish(self, token: int, future: Future) -> None:
        with self._lock:
            self._pending.pop(token, None)
        try:
            result_token, path, status = future.result()
        except Exception as exc:
            result_token, path, status = token, "", f"ERROR: {exc}"
        # Worker callbacks may run outside the GUI thread, but Qt's signal
        # delivery to GUI receivers is queued automatically. Generation is
        # checked immediately before emission to reject stale seeks.
        self._emit_if_current(result_token, path, status)

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        with self._lock:
            pending = tuple(self._pending.values())
        if not pending:
            return True
        _done, not_done = wait(
            pending,
            timeout=max(0.0, float(timeout)),
        )
        return not not_done

    def close(self) -> None:
        self.invalidate()
        self._executor.shutdown(wait=False, cancel_futures=True)