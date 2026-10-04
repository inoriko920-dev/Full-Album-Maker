from __future__ import annotations

"""Presentation-only UI-06 card-density refinement.

Keeps TemplateCard's real descriptor, selection/favorite state and Preview/Gunakan
signals intact. Only vertical sizing/spacing is tightened so the four-column grid
lands on the same row rhythm as the approved Template Video reference.
"""

from PySide6.QtWidgets import QLabel, QSizePolicy

_installed = False


def install_post_release_template_card_density_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateCard

    previous_init = TemplateCard.__init__

    def dense_init(self, descriptor, *args, **kwargs) -> None:
        previous_init(self, descriptor, *args, **kwargs)
        root = self.layout()
        if root is not None:
            root.setContentsMargins(5, 5, 5, 5)
            root.setSpacing(2)

        # UI-06 spends more of the fixed card height on the visual preview and
        # less on the action row.  Use fixed heights here because the global
        # QPushButton style's sizeHint can otherwise reclaim this space.
        self.thumbnail.setFixedHeight(116)

        labels = [
            label for label in self.findChildren(QLabel)
            if label.parent() is self
        ]
        for label in labels:
            if label.objectName() == "sectionHeading":
                label.setMaximumHeight(22)
                label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            elif label.objectName() == "metadata":
                label.setMaximumHeight(19)
                label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        for button in (self.preview, self.use):
            button.setFixedHeight(28)

        self.setMinimumHeight(0)
        self.setMaximumHeight(196)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    TemplateCard.__init__ = dense_init
    _installed = True
