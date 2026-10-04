from __future__ import annotations

"""Post-release shared command-bar geometry matching.

Only widget sizing/order is changed. Existing buttons, shortcuts, callbacks and
enabled-state logic remain owned by the recovered foundation command adapter.
"""

from PySide6.QtCore import QSize

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


def _apply_geometry(bar, *, compact: bool) -> None:
    row = bar.layout()
    if compact:
        row.setSpacing(4)
        bar.app_name.setMinimumWidth(118)
        for key, button in bar.buttons.items():
            button.setMinimumWidth(0 if key != "render" else 96)
            button.setIconSize(QSize(16, 16))
        return

    row.setSpacing(18)
    bar.app_name.setMinimumWidth(152)
    for key, width in _DESKTOP_WIDTHS.items():
        button = bar.buttons.get(key)
        if button is None:
            continue
        button.setMinimumWidth(width)
        button.setMinimumHeight(36)
        button.setIconSize(QSize(20, 20))


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
