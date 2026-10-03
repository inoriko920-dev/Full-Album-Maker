from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import ProjectDocument
from full_album_maker.spectrum_preview_step08 import SpectrumAccuratePreview


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _FakeService:
    calls = 0

    def render_frame(self, _document, tick: int, destination: str | Path) -> str:
        type(self).calls += 1
        # Older seek deliberately finishes after the newer seek.
        time.sleep(0.12 if int(tick) == 100 else 0.01)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"tick={tick}".encode("utf-8"))
        return str(target)


def test_newer_seek_wins_and_stale_result_is_discarded(tmp_path: Path) -> None:
    app = _app()
    _FakeService.calls = 0
    worker = SpectrumAccuratePreview(
        cache_root=tmp_path,
        service_factory=_FakeService,
        max_workers=2,
    )
    received: list[tuple[int, str, str]] = []
    worker.preview_ready.connect(lambda token, path, status: received.append((token, path, status)))
    doc = ProjectDocument.new_empty("Async STEP08")

    first = worker.request(doc, 100)
    second = worker.request(doc, 200)
    assert second > first
    assert worker.wait_for_idle(2.0)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)

    assert len(received) == 1
    token, path, status = received[0]
    assert token == second
    assert status == "RENDERED"
    assert Path(path).read_bytes() == b"tick=200"
    worker.close()


def test_invalidate_prevents_pending_result_from_becoming_current(tmp_path: Path) -> None:
    app = _app()
    worker = SpectrumAccuratePreview(
        cache_root=tmp_path,
        service_factory=_FakeService,
        max_workers=1,
    )
    received: list[tuple[int, str, str]] = []
    worker.preview_ready.connect(lambda token, path, status: received.append((token, path, status)))
    doc = ProjectDocument.new_empty("Invalidate STEP08")
    worker.request(doc, 100)
    worker.invalidate()
    assert worker.wait_for_idle(2.0)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.01)
    assert received == []
    worker.close()
