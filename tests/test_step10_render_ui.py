from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.render_center_model_step10 import RenderJob, RenderJobState, build_render_snapshot, settings_from_preset
from full_album_maker.render_feature_step10 import safe_job_log_text, verified_output_path
from full_album_maker.render_performance_step10 import RenderPerformanceGraph
from full_album_maker.render_center_model_step10 import RenderMetrics


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _doc(tmp_path: Path) -> ProjectDocument:
    path = tmp_path / "song.wav"
    path.write_bytes(b"fixture-audio")
    doc = ProjectDocument.new_empty("Render UI")
    asset = MediaAsset(
        kind="audio",
        locator=str(path),
        original_name=path.name,
        source_duration_tick=4 * TIMEBASE,
    )
    doc.media.append(asset)
    doc.playlist.entries.append(
        SongInstance(asset_id=asset.asset_id, display_title="Senja di Kota Ini", source_out_tick=4 * TIMEBASE)
    )
    doc.validate()
    return doc


def test_performance_graph_only_visualizes_reported_metrics() -> None:
    _app()
    graph = RenderPerformanceGraph()
    assert graph.point_count == 0
    graph.append_metrics(RenderMetrics(percent=25.0, rendered_seconds=1.0, fps=80.0, average_fps=78.0, speed=2.2, eta_seconds=3.0))
    graph.append_metrics(RenderMetrics(percent=63.0, rendered_seconds=2.5, fps=112.0, average_fps=105.0, speed=2.5, eta_seconds=1.5))
    assert graph.point_count == 2
    graph.clear()
    assert graph.point_count == 0


def test_copy_log_helper_redacts_and_verified_output_gate_is_fail_closed(tmp_path: Path) -> None:
    doc = _doc(tmp_path)
    settings = settings_from_preset("youtube_1080p", filename="safe", output_folder=str(tmp_path))
    job = RenderJob(build_render_snapshot(doc), settings)
    job.log_lines.extend(["frame=1 token=abc123", "Authorization: Bearer secret-value"])
    text = safe_job_log_text(job)
    assert "abc123" not in text
    assert "secret-value" not in text
    assert "[REDACTED]" in text
    assert verified_output_path(job) is None

    output = settings.final_output
    output.write_bytes(b"verified-mp4")
    job.state = RenderJobState.COMPLETED
    job.verified_output = str(output)
    assert verified_output_path(job) == output
    output.unlink()
    assert verified_output_path(job) is None


def test_production_render_route_uses_step10_surfaces_without_project_mutation(tmp_path: Path) -> None:
    script = textwrap.dedent(
        r'''
        import os
        from pathlib import Path
        import tempfile
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_STEP09_PROVIDER", "mock")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        from PySide6.QtWidgets import QApplication
        import full_album_maker.main  # installs all production layers through STEP10
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="s10-ui-") as root:
            root = Path(root)
            media = root / "song.wav"
            media.write_bytes(b"fixture")
            doc = ProjectDocument.new_empty("Render Center Fixture")
            asset = MediaAsset(kind="audio", locator=str(media), original_name=media.name, source_duration_tick=5 * TIMEBASE)
            doc.media.append(asset)
            doc.playlist.entries.append(SongInstance(asset_id=asset.asset_id, display_title="Senja di Kota Ini", source_out_tick=5 * TIMEBASE))
            doc.validate()

            window = FoundationMainWindow()
            window._foundation_project_open = True
            window.editor_workspace.set_document(doc)
            before = window.editor_workspace.document().content_signature()
            window.foundation_shell.set_workspace("render")
            app.processEvents()

            assert window.foundation_state.workspace == "render"
            assert window.foundation_shell.workspace_stack.currentWidget() is window.render_workspace_s10
            assert window._inspector_router.currentWidget() is window.render_inspector_s10
            assert window.foundation_shell.context.maximumWidth() == 0
            assert window.foundation_shell.timeline.collapsed is True
            assert window.render_inspector_s10.pause.isEnabled() is False
            assert window.render_add_queue_s10.text() == "Tambah ke Antrian"
            assert window.render_copy_log_s10.text() == "Salin Log"
            assert window.render_open_output_s10.text() == "Buka Output"
            assert window.render_add_queue_s10.isEnabled() is False
            assert window.render_performance_s10.point_count == 0
            assert window.editor_workspace.document().content_signature() == before

            window._s10_async.close()
            window.hide()
            window.deleteLater()
            app.processEvents()
        '''
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FAM_STEP09_PROVIDER"] = "mock"
    env["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=35,
    )
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
