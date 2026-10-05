from __future__ import annotations

"""Small UI-03 Album fidelity refinements.

Presentation only. The authoritative Album document, selection, transition values,
signals, and bulk-action semantics remain owned by the STEP04 production widgets.
"""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .foundation_components import FAMButton
from .foundation_icons import foundation_icon

_installed = False


_ACTION_STYLE = (
    "QPushButton{text-align:left;padding:7px 12px;background:#FFFFFF;"
    "border:1px solid #D7E3F2;border-radius:7px;color:#17345F;}"
    "QPushButton:disabled{color:#94A3B8;background:#F8FAFC;}"
)

_FIELD_STYLE = (
    "background:#FFFFFF;color:#17345F;border:1px solid #D7E3F2;"
    "border-radius:6px;padding:4px 8px;"
)


def _quick_row(label_text: str, control) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    label = QLabel(label_text)
    label.setMinimumWidth(118)
    label.setStyleSheet("font-size:12px;font-weight:600;color:#17345F;")
    row.addWidget(label)
    row.addWidget(control, 1)
    return row


def install_post_release_album_detail_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_album_pixel_match import (
        PixelAlbumContextWidget,
        PixelAlbumMassToolsWidget,
        PixelAlbumSongTable,
    )

    original_table_init = PixelAlbumSongTable.__init__
    original_table_set_rows = PixelAlbumSongTable.set_rows

    def table_init(self, *args, **kwargs) -> None:
        original_table_init(self, *args, **kwargs)
        self.setColumnWidth(0, 48)
        self.setColumnWidth(1, 34)
        self.setColumnWidth(3, 68)
        self.setColumnWidth(4, 148)
        self.setColumnWidth(5, 100)
        self.setColumnWidth(6, 130)
        self.setIconSize(QSize(42, 30))

    def table_set_rows(self, values, selected_ids, *, page: int) -> None:
        original_table_set_rows(self, values, selected_ids, page=page)
        for row_index, row in enumerate(values):
            item = self.item(row_index, 4)
            if item is not None:
                # The thumbnail cell-widget owns the visible Visual label. Clear
                # the underlying item text so Qt does not paint a duplicate string.
                item.setText("")
            host = self.cellWidget(row_index, 4)
            if host is None:
                continue
            labels = host.findChildren(QLabel)
            if not labels:
                continue
            text_label = labels[-1]
            text_label.setText("Video" if row.visual_asset_id else "Belum Ada")
            text_label.setStyleSheet(
                "font-size:12px;color:#35517A;"
                if row.visual_asset_id
                else "font-size:12px;color:#7C8CA5;"
            )

    PixelAlbumSongTable.__init__ = table_init
    PixelAlbumSongTable.set_rows = table_set_rows

    original_context_init = PixelAlbumContextWidget.__init__

    def context_init(self, *args, **kwargs) -> None:
        original_context_init(self, *args, **kwargs)
        self.cover.setFixedSize(88, 88)
        self.album_title.setWordWrap(False)
        self.album_title.setMinimumWidth(0)
        self.album_title.setStyleSheet("font-size:12px;font-weight:700;color:#10234A;")
        for button in self.findChildren(QPushButton):
            if button.text() == "✎":
                button.setFixedWidth(18)
                button.setStyleSheet(
                    "QPushButton{background:transparent;border:none;color:#31527E;"
                    "font-size:14px;padding:0;}"
                )

    PixelAlbumContextWidget.__init__ = context_init

    original_mass_init = PixelAlbumMassToolsWidget.__init__

    def mass_init(self, *args, **kwargs) -> None:
        original_mass_init(self, *args, **kwargs)

        body = self.widget()
        root = body.layout() if body is not None else None
        if body is None or root is None:
            return

        icon_map = {
            "Kelola Cover": "media",
            "Auto Match Cover": "auto",
            "Assign Visual": "visual",
            "Clear Visual": "properties",
        }
        for button in body.findChildren(QPushButton):
            title = button.text().split("\n", 1)[0]
            icon_name = icon_map.get(title)
            if icon_name:
                button.setIcon(foundation_icon(icon_name, color="#1766E8", size=19))
                button.setIconSize(QSize(19, 19))

        transition_card = self.transition.parentWidget()
        summary_card = self.selection_chip.parentWidget()
        if transition_card is None or summary_card is None:
            return

        self.transition.setParent(body)
        self.duration.setParent(body)
        transition_card.hide()

        default_transition = FAMButton(
            "Default Transition\nTerapkan transisi yang sama",
            icon_name="timeline",
            kind="secondary",
        )
        default_transition.setMinimumHeight(58)
        default_transition.setIconSize(QSize(19, 19))
        default_transition.setStyleSheet(_ACTION_STYLE)
        default_transition.clicked.connect(self._emit_transition)
        default_transition.setEnabled(False)
        self._post_album_default_transition_button = default_transition
        self._action_widgets.append(default_transition)

        summary_index = root.indexOf(summary_card)
        if summary_index < 0:
            summary_index = max(0, root.count() - 1)
        root.insertWidget(summary_index, default_transition)

        self.transition.setMinimumHeight(32)
        self.transition.setMaximumHeight(34)
        self.transition.setStyleSheet(_FIELD_STYLE)
        self.duration.setMinimumHeight(32)
        self.duration.setMaximumHeight(34)
        self.duration.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.duration.setStyleSheet(_FIELD_STYLE)

        quick = QFrame()
        quick.setStyleSheet("background:transparent;")
        quick_root = QVBoxLayout(quick)
        quick_root.setContentsMargins(0, 2, 0, 0)
        quick_root.setSpacing(7)
        quick_root.addLayout(_quick_row("Opsi Transisi Cepat", self.transition))
        quick_root.addLayout(_quick_row("Durasi Transisi", self.duration))
        self._post_album_quick_transition = quick

        summary_index = root.indexOf(summary_card)
        root.insertWidget(summary_index + 1, quick)

    PixelAlbumMassToolsWidget.__init__ = mass_init
    _installed = True
