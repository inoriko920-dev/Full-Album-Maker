from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .spectrum_workspace_step08 import SpectrumLayerContext, SpectrumLayerRow, SpectrumWorkspace

_installed = False
_originals: dict[str, Any] = {}


def _layer_row_init(self, *args, **kwargs) -> None:
    _originals["layer_row_init"](self, *args, **kwargs)
    self.setFixedHeight(36)


def _context_init(self, *args, **kwargs) -> None:
    _originals["context_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(8, 6, 8, 7)
    root.setSpacing(5)
    self.layer_scroll.setMinimumHeight(156)
    self.layer_scroll.setMaximumHeight(164)
    self.add_button.setText("＋  Tambah Spectrum")
    self.add_button.setMinimumWidth(138)


def _workspace_init(self, *args, **kwargs) -> None:
    _originals["workspace_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(8, 7, 8, 6)
    root.setSpacing(5)
    self.preview.setMinimumHeight(310)
    # Golden UI keeps the transport compact. Preview status remains part of the
    # runtime contract/evidence but is not rendered as an extra transport chip.
    self.preview_status.hide()


def _hide_foundation_context(window) -> None:
    for widget in getattr(window, "_s06_context_old", ()):
        if widget is not None:
            widget.hide()


def _ensure_timeline_panel(window) -> None:
    if hasattr(window, "_ui07_timeline_panel"):
        return

    host = window.foundation_shell.timeline
    panel = QFrame()
    panel.setObjectName("ui07SpectrumTimelinePanel")
    root = QVBoxLayout(panel)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar = QHBoxLayout(toolbar_widget)
    toolbar.setContentsMargins(8, 3, 8, 3)
    toolbar.setSpacing(7)

    title = QLabel("▴  Timeline")
    title.setObjectName("sectionHeading")
    toolbar.addWidget(title)

    add = FAMButton("＋", kind="ghost")
    add.setToolTip("Tambah layer Spectrum.")
    add.clicked.connect(window._s08_add_spectrum)
    toolbar.addWidget(add)

    split = FAMButton("✂  Split", kind="ghost")
    split.setEnabled(False)
    split.setToolTip("Split tetap dimiliki Timeline Editor; Spectrum mengikuti interval project.")
    toolbar.addWidget(split)

    delete = FAMButton("Hapus", kind="ghost")
    delete.setEnabled(False)
    delete.setToolTip("Penghapusan layer tidak dipalsukan di presentation remediation.")
    toolbar.addWidget(delete)

    toolbar.addStretch(1)
    toolbar.addWidget(QLabel("🔍"))
    toolbar.addWidget(QLabel("−"))
    toolbar.addWidget(QLabel("100%"))
    toolbar.addWidget(QLabel("+"))
    root.addWidget(toolbar_widget)

    canvas = window.spectrum_timeline_s08
    old_parent = canvas.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(canvas)
    root.addWidget(canvas, 1)
    host.layout().addWidget(panel, 1)
    panel.hide()
    window._ui07_timeline_panel = panel

    header = host.layout().itemAt(0).layout()
    window._ui07_timeline_header_widgets = []
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if widget is not None:
                window._ui07_timeline_header_widgets.append(widget)


def _apply_spectrum_geometry(window) -> None:
    shell = window.foundation_shell
    compact = bool(getattr(shell, "_responsive_compact", False))
    total = max(1, shell.width())

    nav = TOKENS.nav_compact_width if compact else TOKENS.nav_width
    context = 300 if compact else 384
    right = 38 if shell.inspector.collapsed else (300 if compact else 320)
    center = max(440 if compact else 560, total - nav - context - right - TOKENS.splitter_handle * 3)

    shell.navigation.setMinimumWidth(nav)
    shell.navigation.setMaximumWidth(nav)
    shell.context.setMinimumWidth(context)
    shell.context.setMaximumWidth(context)
    if not shell.inspector.collapsed:
        shell.inspector._expanded_width = right
        shell.inspector.setMinimumWidth(right)
        shell.inspector.setMaximumWidth(420)
    shell.horizontal_splitter.setSizes([nav, context, center, right])

    host = shell.timeline
    host.body.hide()
    inherited_header = host.layout().itemAt(0).layout() if host.layout().count() else None
    if inherited_header is not None:
        for index in range(inherited_header.count()):
            widget = inherited_header.itemAt(index).widget()
            if widget is not None:
                widget.hide()

    panel = getattr(window, "_ui07_timeline_panel", None)
    if panel is not None:
        panel.show()

    timeline_h = 252
    host._preferred_height = timeline_h
    host.setMinimumHeight(timeline_h)
    host.setMaximumHeight(timeline_h)
    top_h = max(300 if compact else 360, shell.height() - timeline_h - TOKENS.status_height - TOKENS.command_height)
    shell.vertical_splitter.setSizes([top_h, timeline_h])


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    _ensure_timeline_panel(self)
    active = route == "spectrum"

    self._ui07_timeline_panel.setVisible(active)
    for widget in getattr(self, "_ui07_timeline_header_widgets", ()):
        widget.setVisible(not active)

    if active:
        _hide_foundation_context(self)
        self.foundation_shell.timeline.body.hide()
        self.spectrum_timeline_s08.show()
        self.foundation_shell._apply_shell_sizes("spectrum")
        _apply_spectrum_geometry(self)
        QTimer.singleShot(
            0,
            lambda: _apply_spectrum_geometry(self)
            if getattr(self, "foundation_state", None) is not None
            and self.foundation_state.workspace == "spectrum"
            else None,
        )
    else:
        self._ui07_timeline_panel.hide()
        self.foundation_shell._apply_shell_sizes(route)


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    if route == "spectrum":
        _apply_spectrum_geometry(self.window())


def _shell_resize(self, event) -> None:
    _originals["shell_resize"](self, event)
    if getattr(getattr(self, "state", None), "workspace", "") == "spectrum":
        _apply_spectrum_geometry(self.window())


def _shell_sizes(self, route: str) -> None:
    _originals["shell_sizes"](self, route)
    if route == "spectrum":
        _apply_spectrum_geometry(self.window())


def install_ui07_spectrum_remediation() -> None:
    """UI-07 presentation only; STEP08 + Beat/Spectrum render semantics stay authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget
    from .foundation_window import FoundationMainWindow

    _originals.update(
        layer_row_init=SpectrumLayerRow.__init__,
        context_init=SpectrumLayerContext.__init__,
        workspace_init=SpectrumWorkspace.__init__,
        window_route=FoundationMainWindow._s08_route,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_resize=FoundationShellWidget.resizeEvent,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    SpectrumLayerRow.__init__ = _layer_row_init
    SpectrumLayerContext.__init__ = _context_init
    SpectrumWorkspace.__init__ = _workspace_init
    FoundationMainWindow._s08_route = _window_route
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget.resizeEvent = _shell_resize
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
