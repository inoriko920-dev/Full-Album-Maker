from __future__ import annotations

"""Presentation-only collapse for AI Agent permission controls.

All production QCheckBox permission widgets remain authoritative and editable.
They are simply collapsed behind one compact toggle by default to match UI-08.
"""

from PySide6.QtWidgets import QLabel

from .foundation_components import FAMButton

_installed = False


def install_post_release_ai_permission_collapse() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AIContextDock

    original_init = AIContextDock.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        permission_heading = None
        safety_label = None
        for label in self.findChildren(QLabel):
            text = label.text().strip()
            if text == "Permission":
                permission_heading = label
            elif text.startswith("• AI hanya membuat rencana"):
                safety_label = label

        if permission_heading is not None:
            permission_heading.hide()
        for check in self.permissions.values():
            check.hide()

        toggle = FAMButton("Izin Editing • 5 aktif", kind="ghost", parent=self)
        toggle.setMinimumHeight(30)
        toggle.setToolTip("Tampilkan atau sembunyikan izin editing AI Agent")
        self._post_release_permission_toggle = toggle
        self._post_release_permissions_expanded = False

        key_index = root.indexOf(self.key_status)
        root.insertWidget(max(0, key_index + 1), toggle)

        def refresh_toggle() -> None:
            active = sum(1 for check in self.permissions.values() if check.isChecked())
            arrow = "▾" if self._post_release_permissions_expanded else "▸"
            toggle.setText(f"{arrow}  Izin Editing • {active} aktif")

        def toggle_permissions() -> None:
            self._post_release_permissions_expanded = not self._post_release_permissions_expanded
            for check in self.permissions.values():
                check.setVisible(self._post_release_permissions_expanded)
            if permission_heading is not None:
                permission_heading.setVisible(self._post_release_permissions_expanded)
            refresh_toggle()

        toggle.clicked.connect(toggle_permissions)
        for check in self.permissions.values():
            check.toggled.connect(lambda _checked: refresh_toggle())
        refresh_toggle()

        if safety_label is not None:
            safety_label.setStyleSheet(
                "background:#FFF8E8;border:1px solid #F2D991;border-radius:8px;"
                "padding:8px;color:#6E5320;"
            )

    AIContextDock.__init__ = adjusted_init
    _installed = True
