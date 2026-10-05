from __future__ import annotations

"""Small UI-06 inspector density refinement.

The production TemplateInspector widgets remain authoritative. This layer only
aligns the preview/field density and renders the existing scope QComboBox as
three visible radio choices like the approved reference. Scope values still
live in the original QComboBox so all STEP07 apply semantics remain unchanged.
"""

from PySide6.QtWidgets import QHBoxLayout, QRadioButton, QWidget

_installed = False


def install_post_release_template_inspector_density() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateInspector

    previous_init = TemplateInspector.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        root = self.layout()
        if root is None:
            return

        preview = getattr(self, "_post_template_preview", None)
        if preview is not None:
            preview.setMinimumHeight(152)
            preview.setMaximumHeight(152)

        settings_heading = getattr(self, "_post_template_settings_heading", None)
        if settings_heading is not None:
            settings_heading.setMinimumHeight(24)
            settings_heading.setMaximumHeight(24)
            settings_heading.show()

        header_host = getattr(self, "_post_template_header_host", None)
        if header_host is not None:
            # 152 preview + 7 inner spacing + 24 heading. Locking the composite
            # height prevents any overlap while keeping the first field aligned
            # immediately below the section heading.
            header_host.setMinimumHeight(183)
            header_host.setMaximumHeight(183)

        for combo in (
            self.title_layout,
            self.cover_position,
            self.background,
            self.spacing,
            self.typography,
        ):
            combo.setMinimumHeight(29)
            combo.setMaximumHeight(31)
        root.setSpacing(4)

        # The compact inspector layer exposes the production scope row directly.
        # This avoids relying on a fragile layout index when presentation rows are
        # refined later.
        scope_row = getattr(self, "_post_template_scope_row", None)
        if scope_row is None:
            return

        self.scope.hide()
        host = QWidget(self)
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._post_template_scope_buttons = {}
        for key, label in (("current", "Lagu Ini"), ("selected", "Pilihan"), ("all", "Semua Lagu")):
            button = QRadioButton(label, host)
            button.setMinimumHeight(26)
            button.setChecked(str(self.scope.currentData() or "current") == key)
            button.toggled.connect(
                lambda checked, value=key: (
                    self.scope.setCurrentIndex(self.scope.findData(value))
                    if checked and self.scope.findData(value) >= 0
                    else None
                )
            )
            row.addWidget(button)
            self._post_template_scope_buttons[key] = button
        row.addStretch(1)
        scope_row.addWidget(host, 1)
        self._post_template_scope_host = host

        def sync_scope(_index: int) -> None:
            current = str(self.scope.currentData() or "current")
            for key, button in self._post_template_scope_buttons.items():
                button.blockSignals(True)
                button.setChecked(key == current)
                button.blockSignals(False)

        self.scope.currentIndexChanged.connect(sync_scope)

    TemplateInspector.__init__ = adjusted_init
    _installed = True
