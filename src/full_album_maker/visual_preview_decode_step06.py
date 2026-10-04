from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .media_library_model import MediaAsset as LibraryAsset, MediaStatus, MediaType
from .media_preview_cache import MediaPreviewCache, PreviewResult
from .visual_assignment import assignment_status
from .visual_precision import visual_settings_for_song
from .visual_workspace_step06 import (
    MOTION_LABELS,
    TRANSITION_LABELS,
    VisualPreviewCanvas,
    VisualPreviewWorkspace,
    _song_title,
)


class DecodedVisualPreviewCanvas(VisualPreviewCanvas):
    """STEP06 canvas that can layer a decoded video frame over safe fallback UI."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._decoded_image = QImage()
        self._decoded_asset_id = ""

    @property
    def decoded_asset_id(self) -> str:
        return self._decoded_asset_id

    def clear_decoded_frame(self) -> None:
        self._decoded_image = QImage()
        self._decoded_asset_id = ""
        self.update()

    def set_decoded_frame(self, asset_id: str, path: str) -> bool:
        image = QImage(str(path))
        if image.isNull():
            self.clear_decoded_frame()
            return False
        self._decoded_image = image
        self._decoded_asset_id = str(asset_id)
        self.update()
        return True

    def set_state(self, document, song_id: str, playhead_tick: int) -> None:
        song = document.song_map().get(song_id)
        expected = song.visual_asset_id if song is not None else None
        if expected != self._decoded_asset_id:
            self._decoded_image = QImage()
            self._decoded_asset_id = ""
        super().set_state(document, song_id, playhead_tick)

    def paintEvent(self, event) -> None:
        # Base canvas always paints a deterministic fallback first. If decoding is
        # unavailable/error, the fallback remains fully usable and honest.
        super().paintEvent(event)
        song = self._document.song_map().get(self._song_id)
        if song is None or not song.visual_asset_id:
            return
        asset = self._document.asset_map().get(song.visual_asset_id)
        if (
            asset is None
            or asset.kind != "video"
            or self._decoded_image.isNull()
            or self._decoded_asset_id != asset.asset_id
        ):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        margin = 14
        available = self.rect().adjusted(margin, margin, -margin, -margin)
        aspect = 16 / 9
        width = available.width()
        height = int(width / aspect)
        if height > available.height():
            height = available.height()
            width = int(height * aspect)
        canvas = QRectF(
            available.center().x() - width / 2,
            available.center().y() - height / 2,
            width,
            height,
        )
        painter.fillRect(canvas, QColor("#17212F"))
        settings = visual_settings_for_song(self._document, self._song_id)
        self._paint_image(painter, canvas, self._decoded_image, settings)
        painter.setPen(QPen(QColor("#CBD8E8"), 1))
        painter.drawRect(canvas)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            canvas.adjusted(12, 8, -12, -8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            _song_title(self._document, self._song_id),
        )
        transition = TRANSITION_LABELS.get(settings["transition"], settings["transition"])
        painter.drawText(
            canvas.adjusted(12, 8, -12, -8),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            f"{settings['fit'].upper()} • {MOTION_LABELS.get(settings['image_motion'], settings['image_motion'])} • {transition} {settings['transition_seconds']:.1f}s",
        )
        painter.end()


class DecodedVisualPreviewWorkspace(VisualPreviewWorkspace):
    """Reuse STEP03 bounded preview workers with an explicit STEP06 stale guard."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.preview_cache = MediaPreviewCache(self, workers=1)
        self.preview_cache.preview_ready.connect(self._preview_ready)
        self._requested_asset_id = ""
        self._requested_generation = self.preview_cache.generation

    @staticmethod
    def _library_asset(asset) -> LibraryAsset:
        exists = False
        try:
            exists = Path(asset.locator).expanduser().is_file()
        except OSError:
            pass
        return LibraryAsset(
            asset_id=asset.asset_id,
            path=asset.locator,
            display_name=asset.original_name or Path(asset.locator).name or "Video",
            media_type=MediaType.VIDEO,
            status=MediaStatus.READY if exists else MediaStatus.MISSING,
        )

    def apply_state(self, document, song_id: str, playhead_tick: int) -> None:
        previous = self._requested_asset_id
        super().apply_state(document, song_id, playhead_tick)
        song = document.song_map().get(song_id)
        asset = document.asset_map().get(song.visual_asset_id or "") if song is not None else None
        requested = asset.asset_id if asset is not None and asset.kind == "video" else ""
        if requested != previous:
            self.preview_cache.reset()
            self._requested_generation = self.preview_cache.generation
            self._requested_asset_id = requested
            self.preview.clear_decoded_frame()
        if not requested or asset is None:
            return
        status = assignment_status(document, song_id)
        if status.state == "missing":
            return
        self._requested_generation = self.preview_cache.generation
        self.preview_cache.request(self._library_asset(asset))

    def accepts_preview_result(self, result: PreviewResult) -> bool:
        if not result.path or result.error:
            return False
        if result.generation != self.preview_cache.generation:
            return False
        if result.generation != self._requested_generation:
            return False
        if result.asset_id != self._requested_asset_id:
            return False
        song = self.preview._document.song_map().get(self.preview._song_id)
        return bool(song is not None and song.visual_asset_id == result.asset_id)

    def _preview_ready(self, result: PreviewResult) -> None:
        if self.accepts_preview_result(result):
            self.preview.set_decoded_frame(result.asset_id, result.path)


def install_step06_visual_preview_decode() -> None:
    # The feature module imported the workspace class by value, while the base
    # workspace resolves VisualPreviewCanvas from its own module globals. Patch
    # both factories before any FoundationMainWindow instance is created.
    from . import visual_feature_step06 as feature
    from . import visual_workspace_step06 as workspace

    workspace.VisualPreviewCanvas = DecodedVisualPreviewCanvas
    feature.VisualPreviewWorkspace = DecodedVisualPreviewWorkspace
