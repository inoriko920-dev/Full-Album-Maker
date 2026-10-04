from __future__ import annotations

"""Presentation-only refinement for the UI-08 AI Agent inspector.

The authoritative provider selector, permission checkboxes, key state, and
context labels are reused directly. This layer only groups those existing
widgets into compact cards and collapses advanced permission controls by
default so the inspector matches the approved visual hierarchy more closely.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .foundation_components import FAMButton, FAMCard

_installed = False


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeading")
    return label


def install_post_release_ai_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AIContextDock

    original_init = AIContextDock.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)
        root = self.layout()
        if root is None:
            return

        # Preserve the existing safety label before detaching the old layout
        # items. Provider/permission/context widgets remain the same objects.
        safety = None
        for label in self.findChildren(QLabel):
            if label is self.project or label is self.songs or label is self.media or label is self.key_status or label is self.stale:
                continue
            if "AI hanya membuat rencana" in label.text():
                safety = label
                break

        while root.count():
            item = root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()

        root.setContentsMargins(8, 8, 8, 10)
        root.setSpacing(8)

        context_card = FAMCard()
        context_layout = QVBoxLayout(context_card)
        context_layout.setContentsMargins(10, 9, 10, 9)
        context_layout.setSpacing(5)
        context_layout.addWidget(_heading("Konteks & Izin"))
        self.project.setVisible(True)
        self.songs.setVisible(True)
        self.media.setVisible(True)
        context_layout.addWidget(self.project)
        context_layout.addWidget(self.songs)
        context_layout.addWidget(self.media)
        root.addWidget(context_card)

        provider_card = FAMCard()
        provider_layout = QVBoxLayout(provider_card)
        provider_layout.setContentsMargins(10, 9, 10, 9)
        provider_layout.setSpacing(6)
        provider_layout.addWidget(_heading("Provider AI"))
        provider_row = QHBoxLayout()
        provider_row.setContentsMargins(0, 0, 0, 0)
        provider_row.setSpacing(7)
        self.provider.setVisible(True)
        self.provider.setMaximumWidth(154)
        provider_row.addWidget(self.provider, 1)
        self.key_status.setVisible(True)
        self.key_status.setObjectName("statusChip")
        self.key_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_status.setWordWrap(True)
        self.key_status.setMaximumWidth(138)
        provider_row.addWidget(self.key_status)
        provider_layout.addLayout(provider_row)
        root.addWidget(provider_card)

        permission_card = FAMCard()
        permission_layout = QVBoxLayout(permission_card)
        permission_layout.setContentsMargins(10, 7, 10, 7)
        permission_layout.setSpacing(5)
        permission_header = QHBoxLayout()
        permission_header.setContentsMargins(0, 0, 0, 0)
        permission_header.addWidget(_heading("Izin Editing"))
        permission_header.addStretch(1)
        permission_toggle = FAMButton("5/5 aktif", kind="ghost")
        permission_toggle.setCheckable(True)
        permission_toggle.setChecked(False)
        permission_toggle.setMaximumWidth(92)
        permission_header.addWidget(permission_toggle)
        permission_layout.addLayout(permission_header)

        permission_body = QWidget()
        permission_grid = QGridLayout(permission_body)
        permission_grid.setContentsMargins(0, 2, 0, 0)
        permission_grid.setHorizontalSpacing(10)
        permission_grid.setVerticalSpacing(3)
        for index, check in enumerate(self.permissions.values()):
            check.setVisible(True)
            permission_grid.addWidget(check, index // 2, index % 2)
        permission_body.setVisible(False)
        permission_layout.addWidget(permission_body)

        def refresh_permission_summary(*_args) -> None:
            enabled = sum(1 for check in self.permissions.values() if check.isChecked())
            total = len(self.permissions)
            permission_toggle.setText(f"{enabled}/{total} aktif")

        def toggle_permissions(expanded: bool) -> None:
            permission_body.setVisible(bool(expanded))
            permission_toggle.setText("Tutup" if expanded else permission_toggle.text())
            if not expanded:
                refresh_permission_summary()

        permission_toggle.toggled.connect(toggle_permissions)
        for check in self.permissions.values():
            check.toggled.connect(refresh_permission_summary)
        refresh_permission_summary()
        root.addWidget(permission_card)

        safety_card = FAMCard()
        safety_card.setStyleSheet(
            "QFrame#famCard { background: #FFF9E8; border: 1px solid #F3D98A; border-radius: 8px; }"
        )
        safety_layout = QVBoxLayout(safety_card)
        safety_layout.setContentsMargins(10, 8, 10, 8)
        safety_layout.setSpacing(4)
        safety_layout.addWidget(_heading("Catatan Keamanan"))
        if safety is None:
            safety = QLabel("AI hanya memakai context project yang sudah divalidasi.")
        safety.setVisible(True)
        safety.setObjectName("metadata")
        safety.setWordWrap(True)
        safety_layout.addWidget(safety)
        root.addWidget(safety_card)

        self.stale.setVisible(True)
        root.addWidget(self.stale)
        root.addStretch(1)

        self._post_release_permission_toggle = permission_toggle
        self._post_release_permission_body = permission_body

    AIContextDock.__init__ = adjusted_init
    _installed = True
