from __future__ import annotations

"""Presentation-only UI-06 scope selector alignment.

The production QComboBox remains the authoritative scope control used by
TemplateInspector.scope_key. This layer presents the same three values as radio
choices and synchronizes both directions, preserving existing tests/signals and
apply semantics.
"""

from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QRadioButton, QWidget

_installed = False


def _row_index_with_widget(layout, target) -> int:
    for index in range(layout.count()):
        child = layout.itemAt(index).layout()
        if child is None:
            continue
        for item_index in range(child.count()):
            if child.itemAt(item_index).widget() is target:
                return index
    return -1


def install_post_release_template_scope_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateInspector

    previous_init = TemplateInspector.__init__

    def init_with_scope_radios(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        root = self.layout()
        if root is None or getattr(self, "_post_template_scope_radios", False):
            return

        index = _row_index_with_widget(root, self.scope)
        if index < 0:
            return

        old_row_item = root.takeAt(index)
        old_row = old_row_item.layout()
        if old_row is not None:
            while old_row.count():
                item = old_row.takeAt(0)
                widget = item.widget()
                if widget is self.scope:
                    widget.hide()
                elif widget is not None:
                    widget.hide()
                    widget.deleteLater()

        host = QWidget(self)
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)
        label = QLabel("Terapkan ke")
        label.setObjectName("metadata")
        label.setMinimumWidth(94)
        label.setMaximumWidth(94)
        row.addWidget(label)

        group = QButtonGroup(host)
        group.setExclusive(True)
        buttons: dict[str, QRadioButton] = {}
        labels = (("current", "Lagu Ini"), ("selected", "Pilihan"), ("all", "Semua Lagu"))
        for key, text in labels:
            button = QRadioButton(text, host)
            button.setMinimumHeight(28)
            button.setStyleSheet("QRadioButton{color:#17345F;spacing:5px;} QRadioButton::indicator{width:14px;height:14px;}")
            row.addWidget(button)
            group.addButton(button)
            buttons[key] = button
            button.toggled.connect(
                lambda checked, scope_key=key: checked and _set_combo_scope(self.scope, scope_key)
            )
        row.addStretch(1)
        root.insertWidget(index, host)

        def sync_from_combo(_index: int = -1) -> None:
            key = str(self.scope.currentData() or "current")
            button = buttons.get(key)
            if button is not None and not button.isChecked():
                button.setChecked(True)

        self.scope.currentIndexChanged.connect(sync_from_combo)
        sync_from_combo()
        self._post_template_scope_group = group
        self._post_template_scope_buttons = buttons
        self._post_template_scope_radios = True

    TemplateInspector.__init__ = init_with_scope_radios
    _installed = True


def _set_combo_scope(combo, key: str) -> None:
    index = combo.findData(str(key))
    if index >= 0 and combo.currentIndex() != index:
        combo.setCurrentIndex(index)
