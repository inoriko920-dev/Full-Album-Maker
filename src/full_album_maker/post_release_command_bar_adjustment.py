from __future__ import annotations

"""Post-release shared command-bar geometry matching.

Only widget sizing/order/icon presentation is changed. Existing buttons,
shortcuts, callbacks and enabled-state logic remain owned by the recovered
foundation command adapter.
"""

from PySide6.QtCore import QSize

from .foundation_icons import foundation_icon

_installed = False

# Tuned against the immutable 1672x941 reference. The added width is distributed
# across groups rather than placing one large spacer before Render, so the two
# divider positions and every intermediate command also converge on the golden.
_DESKTOP_WIDTHS = {
    "new": 95,
    "open": 97,
    "save": 113,
    "undo": 99,
    "redo": 97,
    "import": 130,
    "auto": 137,
    "preview": 116,
    "render": 145,
}

_ICON_NAMES = {
    "new": "new",
    "open": "open",
    "save": "save",
    "undo": "undo",
    "redo": "redo",
    "import": "import",
    "auto": "auto",
    "preview": "preview",
    "render": "render",
}


def _refresh_command_icons(bar, *, compact: bool) -> None:
    # FAMButton creates these icons from the 18 px inline token. Merely asking
    # QPushButton for a larger icon therefore left the visible glyph at ~12 px.
    # Re-render the source pixmap at the canonical visual scale instead.
    source_size = 28 if compact else 32
    display_size = 27 if compact else 32
    for key, icon_name in _ICON_NAMES.items():
        button = bar.buttons.get(key)
        if button is None:
            continue
        color = "#FFFFFF" if key == "render" else "#1766E8"
        button.setIcon(foundation_icon(icon_name, color=color, size=source_size))
        button.setIconSize(QSize(display_size, display_size))


def _apply_geometry(bar, *, compact: bool) -> None:
    row = bar.layout()
    if compact:
        row.setSpacing(4)
        bar.app_name.setMinimumWidth(118)
        for key, button in bar.buttons.items():
            button.setMinimumWidth(0 if key != "render" else 96)
        _refresh_command_icons(bar, compact=True)
        return

    # Candidate bottom edge was y=95/96 while the canonical edge is y=92/93.
    # The original token is 55 px, so 52 px aligns the shared command surface.
    bar.setFixedHeight(52)
    row.setSpacing(18)
    bar.app_name.setMinimumWidth(152)
    for key, width in _DESKTOP_WIDTHS.items():
        button = bar.buttons.get(key)
        if button is None:
            continue
        button.setMinimumWidth(width)
        button.setMinimumHeight(36)
    _refresh_command_icons(bar, compact=False)


def install_post_release_command_bar_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget, GlobalCommandBar

    original_bar_init = GlobalCommandBar.__init__
    original_compact = FoundationShellWidget.set_compact_mode

    def adjusted_bar_init(self, *args, **kwargs) -> None:
        original_bar_init(self, *args, **kwargs)
        row = self.layout()
        render = self.buttons["render"]
        preview = self.buttons["preview"]
        row.removeWidget(render)
        preview_index = row.indexOf(preview)
        row.insertWidget(preview_index + 1, render)
        _apply_geometry(self, compact=False)

    def adjusted_compact(self, compact: bool) -> None:
        original_compact(self, compact)
        _apply_geometry(self.command_bar, compact=bool(compact))

    GlobalCommandBar.__init__ = adjusted_bar_init
    FoundationShellWidget.set_compact_mode = adjusted_compact
    _installed = True
