from __future__ import annotations

"""Presentation-only alignment for the compact UI-06 Template filter rail.

The original STEP07 filter widgets remain authoritative. Origin buttons are
reflowed vertically, the category combo stays as the state owner behind visible
category chips, and the sort combo remains available to the workspace while its
visual control moves out of the narrow left rail. No filter semantics or project
state are changed.
"""

from PySide6.QtWidgets import QBoxLayout, QFrame, QGridLayout, QLabel, QPushButton

from .template_studio_step07 import CATEGORIES, ORIGIN_BUILT_IN, ORIGIN_CUSTOM

_installed = False


def _chip_style(selected: bool) -> str:
    if selected:
        return (
            "QPushButton{background:#1766E8;color:#FFFFFF;border:1px solid #1766E8;"
            "border-radius:15px;padding:5px 8px;font-size:11px;font-weight:700;}"
        )
    return (
        "QPushButton{background:#FFFFFF;color:#17345F;border:1px solid #D5E1EF;"
        "border-radius:15px;padding:5px 8px;font-size:11px;}"
        "QPushButton:hover{background:#F4F8FD;border-color:#A9C5E8;}"
    )


def install_post_release_template_context_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateFilterContext

    previous_init = TemplateFilterContext.__init__

    def compact_context_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        root = self.layout()
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # UI-06 starts directly with the three origin choices; the workspace/nav
        # already communicate that this rail belongs to Template.
        for label in self.findChildren(QLabel):
            text = label.text().strip()
            if text in {"Template", "Built-in, Custom, dan Favorit"}:
                label.hide()
            elif text == "Urutkan":
                label.hide()

        origin_layout = self.origin.layout()
        if isinstance(origin_layout, QBoxLayout):
            origin_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            origin_layout.setSpacing(3)
        origin_labels = {
            ORIGIN_BUILT_IN: "▣  Built-in",
            ORIGIN_CUSTOM: "▤  Custom",
            "FAVORITE": "♡  Favorit",
        }
        for key, button in self.origin._buttons.items():
            button.setText(origin_labels.get(key, button.text()))
            button.setMinimumHeight(38)
            button.setMaximumHeight(38)
            button.setStyleSheet(
                "QPushButton#tabButton{padding:6px 10px;text-align:left;border-radius:7px;}"
                "QPushButton#tabButton:checked{background:#E7F1FF;color:#1766E8;"
                "border:1px solid #D4E6FC;font-weight:700;}"
            )

        self.search.setMinimumHeight(38)

        # Keep the real combo as the state owner, but surface its options as the
        # compact two-column chip grid used by the approved reference.
        self.category.hide()
        chip_host = QFrame(self)
        chip_host.setObjectName("postTemplateCategoryChips")
        chips = QGridLayout(chip_host)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setHorizontalSpacing(5)
        chips.setVerticalSpacing(5)
        self._post_template_category_buttons = {}

        def refresh_chips(*_args) -> None:
            active = self.category.currentText() or "Semua"
            for value, button in self._post_template_category_buttons.items():
                button.setStyleSheet(_chip_style(value == active))

        for index, value in enumerate(CATEGORIES):
            button = QPushButton(value, chip_host)
            button.setCursor(self.search.cursor())
            button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, item=value: self.category.setCurrentText(item))
            self._post_template_category_buttons[value] = button
            chips.addWidget(button, index // 2, index % 2)
        self.category.currentIndexChanged.connect(refresh_chips)
        refresh_chips()

        # Insert immediately after the existing Kategori label. QVBox indices are
        # stable because the original STEP07 constructor owns this rail.
        category_label_index = -1
        for index in range(root.count()):
            widget = root.itemAt(index).widget()
            if isinstance(widget, QLabel) and widget.text().strip() == "Kategori":
                category_label_index = index
                break
        if category_label_index >= 0:
            root.insertWidget(category_label_index + 1, chip_host)
        else:
            root.addWidget(chip_host)

        # Sorting belongs to the gallery header in UI-06. Keep the combo alive
        # (and therefore sort_key/test contracts intact) but remove it from this rail.
        self.sort.hide()
        self.result_count.hide()
        self.warning.setWordWrap(True)

        # Ratio buttons are already the right semantic control; make them compact.
        for button in self.ratio._buttons.values():
            button.setMinimumHeight(34)

    TemplateFilterContext.__init__ = compact_context_init
    _installed = True
