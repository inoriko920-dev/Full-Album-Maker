from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.template_studio_step07 import TemplateStudioDraft, builtin_descriptors
from full_album_maker.template_workspace_step07 import (
    TemplateFilterContext,
    TemplateGalleryWorkspace,
    TemplateInspector,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_template_context_and_gallery_match_golden_interaction_contract() -> None:
    _app()
    context = TemplateFilterContext()
    assert context.search.placeholderText() == "Cari template..."
    assert context.origin.checked_value() == "BUILT_IN"
    assert context.ratio.checked_value() == "16:9"
    assert context.category.currentText() == "Semua"
    assert context.sort.currentText() == "Terbaru"

    gallery = TemplateGalleryWorkspace()
    descriptors = builtin_descriptors()
    gallery.set_templates(descriptors, selected_id="spotify_clean")
    assert len(gallery._cards) == 10
    assert gallery.selected_template_id == "spotify_clean"
    assert gallery.grid.getItemPosition(0)[:2] == (0, 0)
    assert gallery.grid.getItemPosition(3)[:2] == (0, 3)
    assert gallery.grid.getItemPosition(4)[:2] == (1, 0)


def test_template_inspector_defaults_are_semantic_and_builtin_save_is_disabled() -> None:
    _app()
    descriptor = builtin_descriptors()[0]
    inspector = TemplateInspector()
    inspector.set_template(descriptor, TemplateStudioDraft(template_id=descriptor.template_id))
    assert inspector.title_layout.currentText() == "Judul di Kiri"
    assert inspector.cover_position.currentText() == "Penuh Layar"
    assert inspector.background.currentText() == "Foto + Overlay Gelap"
    assert inspector.spacing.currentText() == "Normal"
    assert inspector.typography.currentText() == "Noto Sans — fallback aman"
    assert inspector.overlay.value() == 60
    assert inspector.scope.currentText() == "Lagu Ini"
    assert inspector.save_custom.isEnabled() is False
    assert inspector.draft().template_id == descriptor.template_id


def test_production_template_route_uses_step07_surfaces_without_mutation(tmp_path: Path) -> None:
    script = textwrap.dedent(
        r'''
        import os
        from pathlib import Path
        import tempfile
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        import full_album_maker.main  # installs production layers through STEP07
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="s07-ui-") as root:
            root = Path(root)
            doc = ProjectDocument.new_empty("Video Full Album")
            image_path = root / "cover.png"
            image_path.write_bytes(b"fixture")
            image = MediaAsset(kind="image", locator=str(image_path), original_name=image_path.name)
            doc.media.append(image)
            for index in range(4):
                audio_path = root / f"song-{index}.mp3"
                audio_path.write_bytes(b"fixture")
                audio = MediaAsset(
                    kind="audio",
                    locator=str(audio_path),
                    original_name=audio_path.name,
                    source_duration_tick=20 * TIMEBASE,
                )
                doc.media.append(audio)
                doc.playlist.entries.append(
                    SongInstance(
                        asset_id=audio.asset_id,
                        display_title=("Senja di Kota Ini" if index == 0 else f"Lagu {index+1}"),
                        display_artist="Perjalanan Kita",
                        source_out_tick=20 * TIMEBASE,
                        cover_asset_id=image.asset_id,
                    )
                )
            doc.validate()

            window = FoundationMainWindow()
            window._foundation_project_open = True
            window.editor_workspace.set_document(doc)
            before = window.editor_workspace.document().content_signature()
            window.foundation_shell.set_workspace("template")
            app.processEvents()

            assert window.foundation_state.workspace == "template"
            assert window.foundation_shell.workspace_stack.currentWidget() is window.template_workspace_s07
            assert not window.template_context_s07.isHidden()
            assert window._inspector_router.currentWidget() is window.template_inspector_s07
            assert not window.template_timeline_s07.isHidden()
            assert window._s07_selected_template_id == "spotify_clean"
            assert window.template_workspace_s07.selected_template_id == "spotify_clean"
            assert len(window.template_workspace_s07._cards) == 10
            assert window.editor_workspace.document().content_signature() == before

            window._s07_preview()
            app.processEvents()
            assert window.editor_workspace.document().content_signature() == before
            assert "belum diterapkan" in window.template_workspace_s07.preview_state.text()
            window.hide()
            window.deleteLater()
            app.processEvents()
        '''
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout + "\n" + result.stderr)
