from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QMenu, QPushButton, QSizePolicy

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .media_library_services import MediaSidecarStore
from .media_preview_cache import MediaPreviewCache, PreviewResult, invalidate_source, preview_cache_path
from .media_workspace import COLLECTIONS, MediaPreviewPlaceholder, MediaWorkspace, MediaInspectorWidget

_installed = False
_originals: dict[str, Any] = {}


def _preview_set_path(self: MediaPreviewPlaceholder, path: str) -> None:
    path = str(path or "")
    self._step03_preview_path = path
    pixmap = QPixmap(path) if path and Path(path).is_file() else QPixmap()
    self._step03_preview_pixmap = None if pixmap.isNull() else pixmap
    self.update()


def _preview_paint(self: MediaPreviewPlaceholder, event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = self.rect().adjusted(0, 0, -1, -1)
    painter.setClipRect(rect)

    pixmap = getattr(self, "_step03_preview_pixmap", None)
    if pixmap is not None:
        scaled = pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(
            rect.center().x() - scaled.width() // 2,
            rect.center().y() - scaled.height() // 2,
            scaled,
        )
    elif self.asset.media_type.value == "audio":
        painter.fillRect(rect, QColor("#F4F8FF"))
        painter.setPen(QPen(QColor("#6FA7FF"), 2))
        middle = rect.center().y()
        usable = max(1, rect.width() - 26)
        bars = max(28, min(48, usable // 6))
        for index in range(bars):
            x = rect.left() + 13 + int(index * usable / bars)
            height = 9 + ((index * 17 + 11) % max(14, rect.height() - 30))
            painter.drawLine(x, middle - height // 2, x, middle + height // 2)
    else:
        # Deterministic scenic fallback: visually distinguishes photo/video
        # without copying the immutable golden or inventing user media.
        name = self.asset.display_name.casefold()
        video = self.asset.media_type.value == "video"
        if any(word in name for word in ("senja", "bromo", "cerita")):
            top, bottom, terrain = "#F1A15D", "#F6D18B", "#6E745F"
        elif any(word in name for word in ("pantai", "danau")):
            top, bottom, terrain = "#92D6F3", "#5EC2C8", "#668C76"
        elif "hutan" in name:
            top, bottom, terrain = "#A9D0B1", "#5E8968", "#3F6048"
        elif any(word in name for word in ("kota malam", "timelapse")):
            top, bottom, terrain = "#556F92", "#D68762", "#31465B"
        elif "perjalanan" in name:
            top, bottom, terrain = "#C9DFF1", "#E8D4AA", "#778D68"
        else:
            name_seed = sum(ord(ch) for ch in self.asset.display_name)
            skies = (
                ("#B9D9F6", "#DDF1FF", "#6E9274"),
                ("#F5B66B", "#FFE2A7", "#758060"),
                ("#BFDFF0", "#E9F7FF", "#668C76"),
                ("#C6DAF0", "#F2D7B6", "#788A68"),
            )
            top, bottom, terrain = skies[name_seed % len(skies)]
        painter.fillRect(rect, QColor(top))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bottom))
        painter.drawRect(rect.left(), rect.top() + rect.height() // 2, rect.width(), rect.height() // 2)

        painter.setBrush(QColor(terrain))
        mountain = QPolygon([
            QPoint(rect.left(), rect.bottom()),
            QPoint(rect.left() + int(rect.width() * 0.18), rect.top() + int(rect.height() * 0.62)),
            QPoint(rect.left() + int(rect.width() * 0.36), rect.top() + int(rect.height() * 0.43)),
            QPoint(rect.left() + int(rect.width() * 0.54), rect.top() + int(rect.height() * 0.64)),
            QPoint(rect.left() + int(rect.width() * 0.76), rect.top() + int(rect.height() * 0.36)),
            QPoint(rect.right(), rect.bottom()),
        ])
        painter.drawPolygon(mountain)
        if video:
            painter.setBrush(QColor(255, 200, 85, 210))
            painter.drawEllipse(
                rect.left() + int(rect.width() * 0.72),
                rect.top() + int(rect.height() * 0.18),
                18,
                18,
            )

    metadata = self.asset.metadata

    def badge(text: str, x: int, y: int, *, align_right: bool = False) -> int:
        if not text:
            return 0
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 10
        if align_right:
            x -= width
        box = QRect(x, y, width, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 35, 74, 205))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        return width

    duration = ""
    if metadata.duration is not None:
        seconds = max(0, int(round(metadata.duration)))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        duration = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

    bottom_y = rect.bottom() - 24
    if self.asset.media_type.value == "audio":
        badge(duration, rect.right() - 6, bottom_y, align_right=True)
    elif self.asset.media_type.value == "photo":
        painter.setPen(QColor("#FFFFFF"))
        painter.setBrush(QColor(16, 35, 74, 180))
        painter.drawRoundedRect(QRect(rect.left() + 6, bottom_y, 22, 20), 4, 4)
        painter.drawText(QRect(rect.left() + 6, bottom_y, 22, 20), Qt.AlignmentFlag.AlignCenter, "▧")
        resolution = f"{metadata.width} × {metadata.height}" if metadata.width and metadata.height else ""
        badge(resolution, rect.right() - 6, bottom_y, align_right=True)
    else:
        badge(duration, rect.left() + 6, bottom_y)
        parts = []
        if metadata.width and metadata.height:
            if metadata.width >= 3000:
                parts.append("4K")
            elif metadata.height >= 1000:
                parts.append("1080p")
            elif metadata.height >= 700:
                parts.append("720p")
            else:
                parts.append(f"{metadata.width}×{metadata.height}")
        if metadata.fps:
            parts.append(f"{metadata.fps:g} FPS")
        right = rect.right() - 6
        for text in reversed(parts):
            width = badge(text, right, bottom_y, align_right=True)
            right -= width + 4

    painter.setClipping(False)
    painter.setPen(QPen(QColor(TOKENS.border), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect, 7, 7)

    if self.asset.status.value == "missing":
        painter.fillRect(rect, QColor(255, 245, 220, 210))
        painter.setPen(QColor("#A56D00"))
        painter.drawText(
            rect.adjusted(8, 8, -8, -8),
            Qt.AlignmentFlag.AlignCenter,
            "SOURCE MISSING",
        )
    painter.end()

def _workspace_init(self: MediaWorkspace, *args, **kwargs) -> None:
    _originals["workspace_init"](self, *args, **kwargs)
    self._step03_preview_paths: dict[str, str] = {}
    self._step03_preview_failed: set[str] = set()
    self._step03_preview_requester: Callable[[Any], None] | None = None
    self._step03_collection_handler: Callable[[str, str, bool], None] | None = None
    self.scroll.verticalScrollBar().valueChanged.connect(lambda _v: QTimer.singleShot(40, self._step03_request_nearby))


def _workspace_columns(self: MediaWorkspace) -> int:
    width = max(360, self.scroll.viewport().width())
    return max(2, min(5, width // 180))


def _workspace_refresh(self: MediaWorkspace) -> None:
    _originals["workspace_refresh"](self)
    for card in self._cards:
        asset = card.asset
        grid_mode = self.query.view_mode.value == "grid"
        card.setFixedHeight(166 if grid_mode else 108)
        if hasattr(card, "preview_host"):
            card.preview_host.setFixedHeight(108 if grid_mode else 52)
        preview = card.findChild(MediaPreviewPlaceholder)
        if preview is not None:
            preview.setMinimumHeight(44 if not grid_mode else 84)
            cached = self._step03_preview_paths.get(asset.asset_id, "")
            if cached:
                preview.set_preview_path(cached)
        menus = card.findChildren(QMenu)
        if menus:
            menu = menus[0]
            collection_menu = menu.addMenu("Koleksi")
            for collection in COLLECTIONS:
                action = collection_menu.addAction(collection)
                action.setCheckable(True)
                action.setChecked(collection in asset.collections)
                action.triggered.connect(
                    lambda checked=False, asset_id=asset.asset_id, name=collection, workspace=self:
                    workspace._step03_collection_handler and workspace._step03_collection_handler(asset_id, name, bool(checked))
                )
    QTimer.singleShot(0, self._step03_request_nearby)


def _workspace_request_nearby(self: MediaWorkspace) -> None:
    requester = getattr(self, "_step03_preview_requester", None)
    if not callable(requester) or not self.isVisible():
        return
    viewport = self.scroll.viewport()
    top = self.scroll.verticalScrollBar().value() - 220
    bottom = top + viewport.height() + 440
    for card in self._cards:
        asset = card.asset
        if asset.status.value == "missing" or asset.asset_id in self._step03_preview_failed:
            continue
        if asset.asset_id in self._step03_preview_paths:
            continue
        y = card.geometry().top()
        if y + card.height() < top or y > bottom:
            continue
        requester(asset)


def _workspace_preview_result(self: MediaWorkspace, result: PreviewResult) -> None:
    asset_id = str(result.asset_id)
    if result.path:
        self._step03_preview_paths[asset_id] = result.path
        self._step03_preview_failed.discard(asset_id)
    elif result.error:
        self._step03_preview_failed.add(asset_id)
    for card in self._cards:
        if card.asset.asset_id != asset_id:
            continue
        preview = card.findChild(MediaPreviewPlaceholder)
        if preview is not None and result.path:
            preview.set_preview_path(result.path)


def _inspector_init(self: MediaInspectorWidget, *args, **kwargs) -> None:
    _originals["inspector_init"](self, *args, **kwargs)
    layout = self.layout()
    if layout is not None:
        layout.setContentsMargins(10, 0, 10, 8)
        layout.setSpacing(5)
    self.preview.setMinimumHeight(128)
    self.preview.setMaximumHeight(132)
    self.description.setMaximumHeight(66)
    self.save_meta.hide()
    self.favorite.hide()
    self.setMinimumHeight(0)
    self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    self._step03_meta_timer = QTimer(self)
    self._step03_meta_timer.setSingleShot(True)
    self._step03_meta_timer.setInterval(450)
    self._step03_meta_timer.timeout.connect(self._save)
    self.tags.editingFinished.connect(self._save)
    self.description.textChanged.connect(lambda: self._step03_meta_timer.start())


def _inspector_preview(self: MediaInspectorWidget, asset_id: str, path: str) -> None:
    asset = getattr(self, "_asset", None)
    if asset is None or asset.asset_id != asset_id or not path:
        return
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return
    self.preview.setText("")
    self.preview.setPixmap(
        pixmap.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
    )


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    media_active = route == "media"
    timeline = self.timeline

    if not hasattr(timeline, "_media_header_tools"):
        head = timeline.layout().itemAt(0).layout()
        timeline._media_header_tools = []
        labels = ("Split", "Potong", "Kecepatan", "Audio", "Teks", "Transisi", "Efek", "AI Tools")
        insert_at = 3
        for label in labels:
            button = FAMButton(label, kind="ghost")
            button.setEnabled(False)
            button.setToolTip(f"{label} — aktif ketika clip timeline yang kompatibel dipilih")
            button.setMinimumWidth(0)
            head.insertWidget(insert_at, button)
            insert_at += 1
            timeline._media_header_tools.append(button)

    timeline.message.setVisible(not media_active)
    for button in timeline._media_header_tools:
        button.setVisible(media_active)

    timeline.mode.setVisible(not media_active)
    for button in timeline.body.findChildren(QPushButton):
        if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
            button.setVisible(not media_active)


def _shell_sizes(self, route: str) -> None:
    if route != "media":
        _originals["shell_sizes"](self, route)
        return
    total = max(1, self.width())
    compact = bool(getattr(self, "_responsive_compact", False))
    nav = TOKENS.nav_compact_width if compact else 158
    context = 196 if compact else 205
    right = 38 if self.inspector.collapsed else (274 if compact else 286)
    center = max(430 if compact else 640, total - nav - context - right - TOKENS.splitter_handle * 3)

    self.navigation.setMinimumWidth(nav)
    self.navigation.setMaximumWidth(nav)
    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(context)
    if not self.inspector.collapsed:
        self.inspector.setMinimumWidth(right)
        self.inspector.setMaximumWidth(520)
    self.horizontal_splitter.setSizes([nav, context, center, right])

    timeline_height = TOKENS.timeline_collapsed_height if self.timeline.collapsed else self.timeline.preferred_height
    top_height = max(300, self.height() - timeline_height - TOKENS.status_height - TOKENS.command_height)
    self.vertical_splitter.setSizes([top_height, timeline_height])


def _window_init(self, *args, **kwargs) -> None:
    _originals["window_init"](self, *args, **kwargs)
    self._s03_preview_project_identity = id(self.project)
    self._s03_preview_jobs = 0
    self._s03_preview_cache = MediaPreviewCache(self, workers=2)
    self._s03_preview_cache.preview_ready.connect(self._s03_completion_preview_ready)
    self._s03_preview_cache.jobs_changed.connect(self._s03_completion_preview_jobs)
    self.media_workspace._step03_preview_requester = self._s03_preview_cache.request
    self.media_workspace._step03_collection_handler = self._s03_completion_collection

    timeline = self.foundation_shell.timeline
    controls = [timeline.mode]
    for button in timeline.body.findChildren(QPushButton):
        if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
            controls.append(button)
    self._s03_generic_timeline_controls = controls
    self.foundation_state.workspace_changed.connect(self._s03_completion_timeline_controls)

    self.foundation_shell.horizontal_splitter.setMinimumHeight(0)
    self.foundation_shell.inspector.setMinimumHeight(0)
    self.foundation_shell.inspector.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    self._inspector_router.setMinimumHeight(0)
    self._inspector_router.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
    self._s03_completion_timeline_controls(self.foundation_state.workspace)
    QTimer.singleShot(0, lambda: self.foundation_shell._apply_shell_sizes(self.foundation_state.workspace))
    QTimer.singleShot(0, self.media_workspace._step03_request_nearby)


def _timeline_controls(self, route: str) -> None:
    media_active = route == "media"
    for widget in getattr(self, "_s03_generic_timeline_controls", ()):
        widget.setVisible(not media_active)


def _collection(self, asset_id: str, collection: str, enabled: bool) -> None:
    asset = self._s03_index.get(str(asset_id))
    if asset is None or collection not in COLLECTIONS:
        return
    values = list(asset.collections)
    if enabled and collection not in values:
        values.append(collection)
    if not enabled:
        values = [value for value in values if value != collection]
    try:
        self._s03_store.update(
            asset.asset_id,
            collections=values,
            persist=bool(self._foundation_project_path),
        )
    except OSError as exc:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Koleksi Media", f"Koleksi tidak dapat disimpan:\n{exc}")
        return
    self._s03_refresh(False)


def _preview_ready(self, result: PreviewResult) -> None:
    if result.generation != self._s03_preview_cache.generation:
        return
    self.media_workspace._step03_preview_result(result)
    if result.path:
        self.media_inspector.set_preview_path(result.asset_id, result.path)


def _preview_jobs(self, jobs: int) -> None:
    self._s03_preview_jobs = max(0, int(jobs))
    self._sync_foundation_state()


def _selected_summary(self) -> str:
    ids = tuple(self.media_workspace.selection.selected_ids)
    assets = [self._s03_index.get(asset_id) for asset_id in ids]
    assets = [asset for asset in assets if asset is not None]
    video = sum(asset.media_type.value == "video" for asset in assets)
    photo = sum(asset.media_type.value == "photo" for asset in assets)
    audio = sum(asset.media_type.value == "audio" for asset in assets)
    duration = max(
        sum(float(getattr(item, "duration", 0) or 0) for item in getattr(self.project, "audios", ())),
        sum(float(getattr(item, "duration", 0) or 0) for item in getattr(self.project, "videos", ())),
        0.0,
    )
    minutes, seconds = divmod(int(round(duration)), 60)
    hours, minutes = divmod(minutes, 60)
    duration_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return (
        f"Media: {len(assets)} dipilih ({video} video, {photo} foto, {audio} audio)"
        f"  •  Durasi Proyek {duration_text}  •  {len(self._s03_index.all())} item"
    )


def _sync(self) -> None:
    _originals["sync"](self)
    if not getattr(self, "_foundation_ready", False):
        return
    import_jobs = int(getattr(self, "_s03_jobs", 0) or 0)
    recovered_jobs = int(getattr(self, "_import_job_count", 0) or 0)
    render_jobs = int(bool(getattr(self, "render_busy", False)))
    preview_jobs = int(getattr(self, "_s03_preview_jobs", 0) or 0)
    total_jobs = import_jobs + recovered_jobs + render_jobs + preview_jobs
    updates = {"jobs": (f"Jobs: {total_jobs}", "warning" if total_jobs else "neutral")}
    if self.foundation_state.workspace == "media":
        updates["project_context"] = self._s03_completion_selected_summary()
        self.foundation_shell.timeline.set_project_context(f"Media: {len(self._s03_index.all())} item")
    self.foundation_state.set_status(**updates)


def _select(self, ids) -> None:
    _originals["select"](self, ids)
    asset = getattr(self.media_inspector, "_asset", None)
    if asset is not None:
        path = self.media_workspace._step03_preview_paths.get(asset.asset_id, "")
        if not path:
            candidate = preview_cache_path(asset)
            path = str(candidate) if candidate.is_file() else ""
        if path:
            self.media_inspector.set_preview_path(asset.asset_id, path)
    self._sync_foundation_state()


def _refresh_media(self, reset=False) -> None:
    project_changed = id(self.project) != getattr(self, "_s03_preview_project_identity", id(self.project))
    _originals["refresh_media"](self, reset)
    if project_changed and hasattr(self, "_s03_preview_cache"):
        self._s03_preview_project_identity = id(self.project)
        self._s03_preview_cache.reset()
        self.media_workspace._step03_preview_paths.clear()
        self.media_workspace._step03_preview_failed.clear()
    if hasattr(self, "media_workspace"):
        QTimer.singleShot(0, self.media_workspace._step03_request_nearby)


def _relinked(self, payload) -> None:
    old_path = str(payload.get("old", "")) if isinstance(payload, dict) else ""
    if old_path:
        invalidate_source(old_path)
    _originals["relinked"](self, payload)
    if hasattr(self, "_s03_preview_cache"):
        self._s03_preview_cache.reset()
    if hasattr(self, "media_workspace"):
        self.media_workspace._step03_preview_paths.clear()
        self.media_workspace._step03_preview_failed.clear()
        QTimer.singleShot(0, self.media_workspace._step03_request_nearby)


def _save_project(self) -> None:
    old_store = getattr(self, "_s03_store", None)
    old_records = old_store.records() if old_store is not None else {}
    _originals["save_project"](self)
    if not self._foundation_project_path:
        current = str(getattr(self, "_current_project_path", "") or "")
        if current:
            self._foundation_project_path = current
    if not self._foundation_project_path:
        return
    target = Path(self._foundation_project_path)
    if old_store is not None and old_store.project_path == target:
        return
    store = MediaSidecarStore(target)
    store.load()
    try:
        for asset_id, record in old_records.items():
            store.set(asset_id, record, persist=False)
        if old_records:
            store.save()
    except OSError:
        return
    self._s03_store = store
    self._s03_refresh(False)


def install_step03_media_completion() -> None:
    """Close STEP03 collection/cache/golden-layout gaps without a second shell."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget
    from .foundation_window import FoundationMainWindow

    _originals.update(
        workspace_init=MediaWorkspace.__init__,
        workspace_refresh=MediaWorkspace.refresh_view,
        inspector_init=MediaInspectorWidget.__init__,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
        window_init=FoundationMainWindow.__init__,
        sync=FoundationMainWindow._sync_foundation_state,
        select=FoundationMainWindow._s03_select,
        refresh_media=FoundationMainWindow._s03_refresh,
        relinked=FoundationMainWindow._s03_relinked,
        save_project=FoundationMainWindow._foundation_save_project,
    )

    MediaPreviewPlaceholder.set_preview_path = _preview_set_path
    MediaPreviewPlaceholder.paintEvent = _preview_paint
    MediaWorkspace.__init__ = _workspace_init
    MediaWorkspace.refresh_view = _workspace_refresh
    MediaWorkspace._columns = _workspace_columns
    MediaWorkspace._step03_request_nearby = _workspace_request_nearby
    MediaWorkspace._step03_preview_result = _workspace_preview_result
    MediaInspectorWidget.__init__ = _inspector_init
    MediaInspectorWidget.set_preview_path = _inspector_preview
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    FoundationMainWindow.__init__ = _window_init
    FoundationMainWindow._s03_completion_timeline_controls = _timeline_controls
    FoundationMainWindow._s03_completion_collection = _collection
    FoundationMainWindow._s03_completion_preview_ready = _preview_ready
    FoundationMainWindow._s03_completion_preview_jobs = _preview_jobs
    FoundationMainWindow._s03_completion_selected_summary = _selected_summary
    FoundationMainWindow._sync_foundation_state = _sync
    FoundationMainWindow._s03_select = _select
    FoundationMainWindow._s03_refresh = _refresh_media
    FoundationMainWindow._s03_relinked = _relinked
    FoundationMainWindow._foundation_save_project = _save_project
    _installed = True
