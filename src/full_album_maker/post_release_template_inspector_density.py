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
            # QVBoxLayout already contributes its normal spacing on both sides
            # of this inserted item; 10 px here yields roughly +14 px effective
            # separation versus the previous preview-to-heading geometry.
            root.insertSpacing(1, 10)

        self.heading.setMinimumHeight(22)
        self.heading.setMaximumHeight(26)
        self.title_layout.setMinimumHeight(29)
        self.title_layout.setMaximumHeight(31)
        root.setSpacing(4)

        # The compact inspector layout installed earlier keeps the scope row at
        # index 8 before the presentation spacer is inserted. Resolve the scope
        # row by locating the production combo's parent layout after insertion.
        scope_row = None
        for index in range(root.count()):
            candidate = root.itemAt(index).layout()
            if candidate is None:
                continue
            for child_index in range(candidate.count()):
                item = candidate.itemAt(child_index)
                if item is not None and item.widget() is self.scope:
                    scope_row = candidate
                    break
            if scope_row is not None:
                break
        if scope_row is None:
            return

        self.scope.hide()
        host = QWidget(self)
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._post_template_scope_buttons = {}
        for key, label in (("current", "Lagu Ini"), ("selected", "Pilihan"), ("all", "Semua Lagu")):
            button = QRadioButton(label, host)
            button.setMinimumHeight(24)
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
