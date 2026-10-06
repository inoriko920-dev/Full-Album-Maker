from __future__ import annotations

import argparse
import json
from pathlib import Path

from .foundation_capture import _compose_native_title_preview, _logical_viewport_image, _prepare_qt
from .foundation_tokens import TOKENS
from .media_library_model import (
    MediaAsset, MediaLibraryIndex, MediaMetadata, MediaStatus, MediaType, stable_asset_id,
)
from .media_workspace import MediaContextWidget, MediaInspectorWidget, MediaTimelinePreviewCanvas, MediaWorkspace


def _asset(name: str, kind: MediaType, index: int, *, favorite: bool = False,
           missing: bool = False, collections: tuple[str, ...] = ()) -> MediaAsset:
    duration = 0.0 if kind == MediaType.PHOTO else float(42 + index * 13)
    width = 1920 if kind != MediaType.AUDIO else None
    height = 1080 if kind != MediaType.AUDIO else None
    fps = 24.0 if kind == MediaType.VIDEO else None
    path = f'C:/Fixtures/{name}'
    return MediaAsset(
        asset_id=stable_asset_id(path, kind),
        path=path,
        display_name=name,
        media_type=kind,
        status=MediaStatus.MISSING if missing else MediaStatus.READY,
        favorite=favorite,
        tags=('senja', 'vlog') if index == 0 else (),
        description='Momen senja di kota, pemandangan kota dari ketinggian.' if index == 0 else '',
        collections=collections,
        metadata=MediaMetadata(
            duration=duration,
            width=3840 if index == 0 and kind == MediaType.VIDEO else width,
            height=2160 if index == 0 and kind == MediaType.VIDEO else height,
            fps=fps,
            size_bytes=(1_200_000_000 if index == 0 and kind == MediaType.VIDEO else 2_400_000 + index * 310_000),
            created_at=1736519520.0 + index * 3600,
            container='MP4' if kind == MediaType.VIDEO else ('MP3' if kind == MediaType.AUDIO else 'JPG'),
            codec='H.264/AAC' if kind == MediaType.VIDEO else '',
        ),
        imported_at=1736519520.0 + index * 100,
    )


def fixture_assets() -> list[MediaAsset]:
    values: list[MediaAsset] = []
    audios = ['Senja di Kota Ini.mp3','Jalan Pulang.mp3','Inspirasi.mp3','Pelangi.mp3','Harmoni.mp3','Langit.mp3','Cerita.mp3','Outro.mp3']
    photos = ['Pantai Bali.jpg','Gunung Bromo.jpg','Perjalanan.jpg','Hutan.jpg','Danau.jpg','Kota Malam.jpg','Sawah.jpg','Jembatan.jpg','Studio.jpg']
    videos = ['Senja di Kota Ini.mp4','Jalan Pulang.mp4','Perjalanan Kita.mp4','Cerita Baru.mp4','Timelapse.mp4','B-Roll Kota.mp4','Missing Shot.mp4']
    i = 0
    for name in audios:
        values.append(_asset(name, MediaType.AUDIO, i, favorite=i in {0,1}, collections=('Musik',))); i += 1
    for name in photos:
        values.append(_asset(name, MediaType.PHOTO, i, favorite=i == 8, collections=('Aset Utama',) if i % 2 == 0 else ('B-Roll',))); i += 1
    for idx, name in enumerate(videos):
        collections = ('Aset Utama',) if idx < 4 else ('B-Roll',)
        values.append(_asset(name, MediaType.VIDEO, i, missing=idx == 6, collections=collections)); i += 1
    return values


def _fake_project():
    class Item:
        def __init__(self, path, duration): self.path, self.duration = path, duration
    class Project:
        videos = [Item('Senja di Kota Ini.mp4', 20), Item('Jalan Pulang.mp4', 18), Item('Perjalanan Kita.mp4', 35), Item('Cerita Baru.mp4', 19)]
        audios = [Item('Senja di Kota Ini.mp3', 34), Item('Jalan Pulang.mp3', 58)]
    return Project()


def capture(output: Path, width: int = 1672, height: int = 941, scale: float = 1.0, state: str = 'golden') -> dict[str, object]:
    _prepare_qt(scale)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow
    from .foundation_font import install_foundation_font
    from .foundation_shell import FoundationCommandAdapter, FoundationShellWidget, FoundationUiState
    from .foundation_theme import FOUNDATION_STYLE

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    ui_state = FoundationUiState()
    shell = FoundationShellWidget(state=ui_state, adapter=FoundationCommandAdapter(can_save=lambda: True, can_project_action=lambda: True))
    workspace = MediaWorkspace(); context = MediaContextWidget(); inspector = MediaInspectorWidget()
    index = MediaLibraryIndex(fixture_assets())
    if state == 'empty': index = MediaLibraryIndex()
    workspace.set_index(index)
    context.set_counts(index.counts())
    cc = {}
    for asset in index.all():
        for name in asset.collections: cc[name] = cc.get(name, 0) + 1
    context.set_collection_counts(cc)
    media_index = shell.workspace_stack._index['media']; old = shell.workspace_stack.widget(media_index); shell.workspace_stack.removeWidget(old); old.setParent(None); shell.workspace_stack.insertWidget(media_index, workspace)
    context_layout = shell.context.layout()
    for i in range(context_layout.count()):
        widget = context_layout.itemAt(i).widget()
        if widget is not None: widget.hide()
    context_layout.addWidget(context, 1)
    shell.inspector.content.set_properties_widget(inspector)
    timeline_old = shell.timeline.canvas; timeline_old.hide(); timeline = MediaTimelinePreviewCanvas(); timeline.set_project(_fake_project()); timeline_old.parentWidget().layout().addWidget(timeline, 1)
    shell.set_workspace('media')
    ui_state.set_status(
        save=('Tersimpan','success'),
        ffmpeg=('FFmpeg Siap','success'),
        ai=('AI Opsional','neutral'),
        jobs=('Jobs: 0','neutral'),
        project_context='Full Album Maker  v1.0.0 Portable  |  Media: 4 dipilih (2 video, 1 foto, 1 audio)  |  Durasi Proyek: 01:32  |  24 item',
    )
    shell.timeline.set_project_context('Media: 24 item')
    if state == 'list': workspace.set_view_mode(workspace.query.view_mode.__class__.LIST)
    selected = [a.asset_id for a in index.all() if a.display_name in {'Senja di Kota Ini.mp4','Pantai Bali.jpg','Senja di Kota Ini.mp3','Cerita Baru.mp4'}]
    if selected:
        workspace.selection.selected_ids[:] = selected; workspace.refresh_view(); inspector.set_selection([index.get(x) for x in selected if index.get(x)])
        first_video = next((a for a in index.all() if a.display_name == 'Senja di Kota Ini.mp4'), None)
        if first_video: inspector.set_selection((first_video,))

    client_height = max(320, height - TOKENS.title_height)
    window = QMainWindow(); window.setWindowTitle('Full Album Maker'); window.setStyleSheet(FOUNDATION_STYLE); window.setCentralWidget(shell); window.resize(width, client_height); shell.set_compact_mode(width < TOKENS.compact_breakpoint); window.show()
    loop = QEventLoop(); QTimer.singleShot(260, loop.quit); loop.exec(); app.processEvents()
    raw = window.grab(); client = _logical_viewport_image(raw, width, client_height, scale); framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), 'PNG'): raise RuntimeError(f'Gagal menyimpan screenshot: {output}')
    geometry = {
        'window':[width,height], 'state':state, 'workspace':shell.state.workspace,
        'nav_right':shell.navigation.geometry().right(), 'context_width':shell.context.width(),
        'right_dock_width':shell.inspector.width(), 'timeline_height':shell.timeline.height(),
        'status_height':shell.status_bar.height(), 'media_active':shell.workspace_stack.currentWidget() is workspace,
        'visible_cards':len(workspace._visible_assets), 'selected_count':len(workspace.selection.selected_ids),
        'scale':scale, 'font_family':font_family,
    }
    window.close(); return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Capture deterministic STEP 03 Media fixture')
    parser.add_argument('--output', required=True); parser.add_argument('--report'); parser.add_argument('--state', default='golden', choices=('golden','empty','list'))
    parser.add_argument('--width', type=int, default=1672); parser.add_argument('--height', type=int, default=941); parser.add_argument('--scale', type=float, default=1.0)
    ns = parser.parse_args(argv); result={'current':ns.output,'geometry':capture(Path(ns.output),ns.width,ns.height,ns.scale,ns.state)}
    if ns.report:
        path=Path(ns.report); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2)); return 0


if __name__ == '__main__': raise SystemExit(main())
