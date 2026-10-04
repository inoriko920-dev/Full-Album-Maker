from __future__ import annotations

"""Post-release visual-fidelity layer.

This module deliberately changes presentation only. It does not own project state,
render state, provider state, or persistence. The published v1.4.0 behavior stays
behind the same feature/domain contracts while the post-release branch converges
on the immutable 1672x941 UI reference pack.
"""

from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout

from .foundation_components import FAMButton, FAMCard
from .foundation_shell import FoundationShellWidget
from .foundation_tokens import TOKENS, WORKSPACE_LABELS
from .render_workspace_step10 import (
    RenderCenterWorkspace as _BaseRenderCenterWorkspace,
    RenderHistoryContext as _BaseRenderHistoryContext,
)


_CANONICAL_CONTEXT_WIDTH = 292
_CANONICAL_RIGHT_DOCK_WIDTH = 320
_installed = False


def _pixel_match_shell_sizes(self: FoundationShellWidget, route: str) -> None:
    """Keep the proven splitter contract while matching canonical desktop geometry."""

    total = max(1, self.width())
    nav = TOKENS.nav_compact_width if self._responsive_compact else TOKENS.nav_width

    # The immutable reference pack uses a visible context rail on every desktop
    # workspace except Beranda. The recovered implementation had intentionally
    # hidden Render's context rail and used 264/348 context/inspector widths,
    # shifting the center workspace ~28 px left at the golden viewport.
    if route == "home":
        context = 0
    elif self._responsive_compact:
        context = TOKENS.context_width
    else:
        context = _CANONICAL_CONTEXT_WIDTH

    right = 38 if self.inspector.collapsed else (
        TOKENS.right_dock_compact_width
        if self._responsive_compact
        else _CANONICAL_RIGHT_DOCK_WIDTH
    )
    minimum_center = 360 if self._responsive_compact else 560
    center = max(minimum_center, total - nav - context - right - TOKENS.splitter_handle * 3)

    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(420 if context else 0)
    self.inspector.set_expanded_width(right)
    self.horizontal_splitter.setSizes([nav, context, center, right])

    timeline_h = TOKENS.timeline_collapsed_height if self.timeline.collapsed else self.timeline.preferred_height
    top_h = max(
        300 if self._responsive_compact else 360,
        self.height() - timeline_h - TOKENS.status_height - TOKENS.command_height,
    )
    self.vertical_splitter.setSizes([top_h, timeline_h])


class PixelMatchRenderHistoryContext(_BaseRenderHistoryContext):
    """Render context rail shaped like immutable UI-09 while retaining STEP10 signals."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = self.layout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        labels = self.findChildren(QLabel)
        for label in labels:
            if label.text() == "Render":
                label.setText("Preset Render")
            elif label.text() == "Antrian & riwayat attempt":
                label.hide()

        self.filter.hide()
        self.retry.hide()

        presets = QFrame()
        presets.setObjectName("renderPresetRail")
        preset_layout = QVBoxLayout(presets)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(7)
        for text, detail in (
            ("YouTube 1080p", "1920 × 1080  •  H.264  •  MP4"),
            ("YouTube 1440p", "2560 × 1440  •  H.264  •  MP4"),
            ("YouTube 4K", "3840 × 2160  •  H.265  •  MP4"),
            ("Custom", "Atur pengaturan sendiri"),
        ):
            card = FAMCard()
            lay = QVBoxLayout(card)
            lay.setContentsMargins(10, 7, 10, 7)
            lay.setSpacing(1)
            title = QLabel(text)
            title.setObjectName("sectionHeading")
            meta = QLabel(detail)
            meta.setObjectName("metadata")
            lay.addWidget(title)
            lay.addWidget(meta)
            preset_layout.addWidget(card)

        # Existing layout: title, subtitle, segmented, listing, retry row.
        root.insertWidget(2, presets)
        previous = QLabel("Proyek Sebelumnya")
        previous.setObjectName("sectionHeading")
        root.insertWidget(4, previous)
        self.listing.setMinimumHeight(170)


class PixelMatchRenderCenterWorkspace(_BaseRenderCenterWorkspace):
    """First-pass UI-09 structure correction; render/domain behavior is untouched."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = self.layout()
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(7)

        for label in self.findChildren(QLabel):
            if label.text() == "Render Center":
                label.setText("Pusat Render")
            elif label.text() == "Snapshot immutable • Preflight • Verified output • Atomic finalize":
                label.setText("Ekspor video album musik Anda dengan aman dan profesional.")

        names = {
            "snapshot": "Timeline Valid",
            "media": "Media Lengkap",
            "ffmpeg": "FFmpeg Siap",
            "output": "Output Folder",
            "disk": "Disk Space",
        }
        for key, title in names.items():
            self.preflight_cards[key].title.setText(title)

        # UI-09 uses five preflight cards on one row. Encoder capability remains
        # validated by the same model but is represented by FFmpeg/inspector state.
        grid = root.itemAt(1).layout()
        if grid is not None:
            order = ("snapshot", "media", "ffmpeg", "output", "disk")
            encoder = self.preflight_cards.get("encoder")
            if encoder is not None:
                encoder.hide()
            for card in self.preflight_cards.values():
                grid.removeWidget(card)
            for column, key in enumerate(order):
                grid.addWidget(self.preflight_cards[key], 0, column)
                self.preflight_cards[key].show()


def install_post_release_pixel_match() -> None:
    global _installed
    if _installed:
        return

    # Install after STEP10/STEP11 monkey patches but before the first window is
    # instantiated. _install_widgets in render_feature_step10 resolves these
    # module globals at runtime, so replacing the presentation classes is safe.
    from . import render_feature_step10 as render_feature
    from .foundation_window import FoundationMainWindow as Window

    FoundationShellWidget._apply_shell_sizes = _pixel_match_shell_sizes
    render_feature.RenderHistoryContext = PixelMatchRenderHistoryContext
    render_feature.RenderCenterWorkspace = PixelMatchRenderCenterWorkspace

    original_route = Window._s10_route

    def route_with_canonical_context(self, route: str) -> None:
        original_route(self, route)
        if route != "render":
            return

        # Match the established context-router pattern used by Album and later
        # workspaces: only the Render context is visible while Render is active.
        layout = self.foundation_shell.context.layout()
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None and widget is not self.render_history_s10:
                widget.setVisible(False)
        self.render_history_s10.setVisible(True)
        self.foundation_shell._apply_shell_sizes(route)

    Window._s10_route = route_with_canonical_context
    _installed = True
