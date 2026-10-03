from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import ProjectDocument
from full_album_maker.render_service_v2 import ffmpeg_process_args
from full_album_maker.spectrum_preview_step08 import SpectrumAccuratePreview
from full_album_maker.spectrum_workspace_step08 import SpectrumInspector, inspector_state
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_step08 import preset_properties


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _spectrum_document() -> ProjectDocument:
    document = ProjectDocument.new_empty("STEP08 failure")
    track = next(item for item in document.tracks if item.kind == "visual")
    layer = make_spectrum_layer(track.track_id, 0, preset_id="minimal_bars")
    layer.properties = preset_properties("classic", layer.properties)
    document.layers.append(layer)
    document.validate()
    return document


class _MissingAudioService:
    def render_frame(self, _document, _tick: int, _destination: str | Path) -> str:
        raise FileNotFoundError("audio source fixture hilang")


class _AnalyzerFailureService:
    def render_frame(self, _document, _tick: int, _destination: str | Path) -> str:
        raise RuntimeError("deterministic analyzer failure")


def _wait_events(app: QApplication, worker: SpectrumAccuratePreview) -> None:
    assert worker.wait_for_idle(2.0)
    for _ in range(12):
        app.processEvents()
        time.sleep(0.01)


def test_missing_audio_reports_error_without_mutating_project(tmp_path: Path) -> None:
    app = _app()
    document = _spectrum_document()
    before = document.content_signature()
    worker = SpectrumAccuratePreview(
        cache_root=tmp_path,
        service_factory=_MissingAudioService,
        max_workers=1,
    )
    received: list[tuple[int, str, str]] = []
    worker.preview_ready.connect(lambda token, path, status: received.append((token, path, status)))

    worker.request(document, 123)
    _wait_events(app, worker)

    assert len(received) == 1
    _token, path, status = received[0]
    assert path == ""
    assert status.startswith("ERROR:")
    assert "hilang" in status
    assert document.content_signature() == before
    worker.close()


def test_analyzer_failure_is_contained_and_project_remains_editable(tmp_path: Path) -> None:
    app = _app()
    document = _spectrum_document()
    before = document.content_signature()
    worker = SpectrumAccuratePreview(
        cache_root=tmp_path,
        service_factory=_AnalyzerFailureService,
        max_workers=1,
    )
    received: list[tuple[int, str, str]] = []
    worker.preview_ready.connect(lambda token, path, status: received.append((token, path, status)))

    worker.request(document, 456)
    _wait_events(app, worker)

    assert len(received) == 1
    assert received[0][1] == ""
    assert received[0][2].startswith("ERROR:")
    assert document.content_signature() == before

    # Failure is runtime-only. Persisted Spectrum state is still valid/editable.
    layer = document.layers[0]
    layer.opacity = 0.75
    document.validate()
    assert layer.opacity == 0.75
    worker.close()


def test_inspector_does_not_emit_project_mutation_mid_numeric_gesture() -> None:
    _app()
    document = _spectrum_document()
    layer = document.layers[0]
    inspector = SpectrumInspector()
    inspector.set_state(inspector_state(document, layer))

    changes: list[tuple[str, object]] = []
    geometry: list[tuple[float, float, float]] = []
    inspector.property_changed.connect(lambda key, value: changes.append((key, value)))
    inspector.geometry_changed.connect(lambda x, y, size: geometry.append((x, y, size)))

    # Programmatic value changes model a drag/typing gesture before editingFinished.
    inspector.smoothing.setValue(0.80)
    inspector.size.setValue(92.0)
    inspector.x.setValue(1010.0)
    assert changes == []
    assert geometry == []

    inspector.smoothing.editingFinished.emit()
    assert changes == [("smoothing", 0.80)]
    assert geometry == []

    inspector.size.editingFinished.emit()
    assert len(geometry) == 1
    assert geometry[0][0] == 1010.0
    assert geometry[0][2] == 0.92


def test_seek_cache_key_changes_with_tick_and_never_reuses_smoothed_state() -> None:
    document = _spectrum_document()
    first = SpectrumAccuratePreview.cache_key(document, 100)
    second = SpectrumAccuratePreview.cache_key(document, 200)
    assert first != second


def test_non_windows_ffmpeg_bridges_generic_filter_option_file_to_legacy_script_option(tmp_path: Path) -> None:
    script = tmp_path / "filter-complex.txt"
    script.write_text("[0:a]anull[aout]\n", encoding="utf-8")
    source = ("ffmpeg", "-/filter_complex", str(script), "-map", "[aout]", "out.wav")
    normalized = ffmpeg_process_args(source, platform_name="posix")
    assert normalized == (
        "ffmpeg",
        "-filter_complex_script",
        str(script),
        "-map",
        "[aout]",
        "out.wav",
    )


def test_windows_keeps_recovered_generic_filter_option_file_syntax(tmp_path: Path) -> None:
    script = tmp_path / "filter-complex.txt"
    source = ("ffmpeg.exe", "-/filter_complex", str(script), "out.mp4")
    assert ffmpeg_process_args(source, platform_name="nt") == source
