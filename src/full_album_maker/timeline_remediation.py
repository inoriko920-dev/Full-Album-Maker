from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .timeline_workspace_step05 import (
    TimelineClipInspector,
    TimelineContextWidget,
    TimelinePrecisionCanvas,
    TimelinePrecisionPanel,
    TimelinePreviewWorkspace,
)

_installed = False
_originals: dict[str, Any] = {}


def _context_init(self, *args, **kwargs) -> None:
    _originals["context_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(12, 10, 12, 10)
    root.setSpacing(8)

    header = QWidget(self)
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    self.ui04_project_title = QLabel("Proyek: -")
    self.ui04_project_title.setObjectName("sectionHeading")
    row.addWidget(self.ui04_project_title, 1)
    more = FAMButton("•••", kind="ghost")
    more.setEnabled(False)
    more.setToolTip("Opsi proyek tersedia dari menu utama")
    more.setFixedWidth(34)
    row.addWidget(more)
    root.insertWidget(0, header)

    self.tabs.setMinimumHeight(36)
    for track_row in self.track_rows.values():
        # Golden UI exposes visibility in the navigator; editing lock remains
        # authoritative in the precision canvas/inspector and model.
        track_row.lock.hide()
        track_row.eye.setFixedSize(26, 26)
        track_row.eye.setText("◉")


def _context_apply(self, document) -> None:
    _originals["context_apply"](self, document)
    title = str(getattr(document, "album_title", "") or getattr(document, "name", "") or "Proyek")
    if hasattr(self, "ui04_project_title"):
        self.ui04_project_title.setText(f"Proyek: {title}")


def _preview_init(self, *args, **kwargs) -> None:
    _originals["preview_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(10, 10, 10, 8)
    root.setSpacing(6)
    self.preview.setMinimumHeight(220)
    self.monitor_volume.setMaximumWidth(118)
    self.aspect.setMinimumWidth(74)


def _inspector_init(self, *args, **kwargs) -> None:
    _originals["inspector_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(14, 10, 14, 10)
    root.setSpacing(8)
    # Golden reference applies edits directly. Keep the same command/Undo
    # boundary but remove the extra visual Apply row.
    self.apply_button.hide()
    for widget in (self.start, self.duration, self.fade_in, self.fade_out, self.crossfade, self.volume):
        widget.editingFinished.connect(self._emit_apply)
    self.locked.toggled.connect(lambda _checked: self._emit_apply())


def _inspector_set_song(self, document, song_id: str) -> None:
    _originals["inspector_set_song"](self, document, song_id)
    song = document.song_map().get(song_id)
    if song is None:
        return
    asset = document.asset_map().get(song.asset_id)
    if asset is not None:
        self.subtitle.setText(asset.original_name or asset.locator.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])


def _panel_init(self, *args, **kwargs) -> None:
    _originals["panel_init"](self, *args, **kwargs)
    root = self.layout()
    root.setSpacing(0)
    toolbar = root.itemAt(0).layout()
    if toolbar is not None:
        toolbar.setContentsMargins(10, 4, 10, 4)
        toolbar.setSpacing(8)
    self.delete_gap.hide()
    self.ripple.setText("↔  Ripple")
    self.snap.setText("⌁  Snap")
    self.marker.setText("●  Marker")


def _move_precision_panel_to_host(shell) -> None:
    window = shell.window()
    panel = getattr(window, "timeline_precision_s05", None)
    if panel is None:
        return
    host = shell.timeline
    if getattr(host, "_ui04_precision_direct", False):
        return
    old_parent = panel.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(panel)
    host.layout().addWidget(panel, 1)
    host._ui04_precision_direct = True

    header = host.layout().itemAt(0).layout()
    host._ui04_header_widgets = []
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if widget is not None:
                host._ui04_header_widgets.append(widget)


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    host = self.timeline
    _move_precision_panel_to_host(self)

    active = route == "timeline"
    for widget in getattr(host, "_ui04_header_widgets", ()):
        widget.setVisible(not active)

    window = self.window()
    panel = getattr(window, "timeline_precision_s05", None)
    if panel is not None:
        panel.setVisible(active)

    if active:
        host.body.hide()
        host._preferred_height = 345
        host.setMinimumHeight(345)
        host.setMaximumHeight(345)
    else:
        host.body.setVisible(not host.collapsed)


def _shell_sizes(self, route: str) -> None:
    if route != "timeline":
        _originals["shell_sizes"](self, route)
        return

    total = max(1, self.width())
    compact = bool(getattr(self, "_responsive_compact", False))
    nav = TOKENS.nav_compact_width if compact else TOKENS.nav_width
    context = 236 if compact else 329
    right = 38 if self.inspector.collapsed else (286 if compact else 348)
    center = max(420 if compact else 560, total - nav - context - right - TOKENS.splitter_handle * 3)

    self.navigation.setMinimumWidth(nav)
    self.navigation.setMaximumWidth(nav)
    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(context)
    if not self.inspector.collapsed:
        self.inspector.setMinimumWidth(right)
        self.inspector.setMaximumWidth(520)
    self.horizontal_splitter.setSizes([nav, context, center, right])

    timeline_height = 345
    self.timeline._preferred_height = timeline_height
    self.timeline.setMinimumHeight(timeline_height)
    self.timeline.setMaximumHeight(timeline_height)
    top_height = max(285 if compact else 360, self.height() - timeline_height - TOKENS.status_height - TOKENS.command_height)
    self.vertical_splitter.setSizes([top_height, timeline_height])


def install_ui04_timeline_remediation() -> None:
    """Post-release UI-04 Timeline parity layer; model/engine contracts remain authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget

    _originals.update(
        context_init=TimelineContextWidget.__init__,
        context_apply=TimelineContextWidget.apply_document,
        preview_init=TimelinePreviewWorkspace.__init__,
        inspector_init=TimelineClipInspector.__init__,
        inspector_set_song=TimelineClipInspector.set_song,
        panel_init=TimelinePrecisionPanel.__init__,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    # Golden Timeline uses a substantially wider lane header and taller ruler.
    TimelinePrecisionCanvas.LEFT = 286
    TimelinePrecisionCanvas.RULER = 43
    TimelinePrecisionCanvas.ROW = 32

    TimelineContextWidget.__init__ = _context_init
    TimelineContextWidget.apply_document = _context_apply
    TimelinePreviewWorkspace.__init__ = _preview_init
    TimelineClipInspector.__init__ = _inspector_init
    TimelineClipInspector.set_song = _inspector_set_song
    TimelinePrecisionPanel.__init__ = _panel_init
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
