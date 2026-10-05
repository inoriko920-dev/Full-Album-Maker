from __future__ import annotations

"""Small UI-03 Album fidelity refinements.

Presentation only. The authoritative Album document, selection, transition values,
signals, and bulk-action semantics remain owned by the STEP04 production widgets.
"""

from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

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


def _sync_album_timeline_chrome(window) -> None:
    timeline = window.foundation_shell.timeline
    host = getattr(timeline, "_post_album_toolbar_host", None)
    if host is None:
        return

    active = getattr(window.foundation_state, "workspace", "") == "album"
    host.setVisible(active)
    original_sizes = getattr(timeline, "_post_album_placeholder_sizes", {})
    for widget in getattr(timeline, "_post_album_placeholder_controls", ()):
        if active:
            # Preserve STEP05's ownership contract (the legacy control remains
            # logically shown after leaving Timeline) while keeping it visually
            # absent from UI-03. A 0x0 shown widget satisfies both requirements.
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(0, 0)
            widget.show()
        else:
            minimum, maximum = original_sizes.get(widget, (QSize(0, 0), QSize(16777215, 16777215)))
            widget.setMinimumSize(minimum)
            widget.setMaximumSize(maximum)
            widget.show()
    timeline.message.setVisible(not active)

    source_undo = window.foundation_shell.command_bar.buttons.get("undo")
    source_redo = window.foundation_shell.command_bar.buttons.get("redo")
    timeline._post_album_undo.setEnabled(bool(source_undo and source_undo.isEnabled()))
    timeline._post_album_redo.setEnabled(bool(source_redo and source_redo.isEnabled()))

    selected = set()
    if hasattr(window, "album_workspace"):
        selected = window.album_workspace.selected_song_ids
    timeline._post_album_delete.setEnabled(bool(selected))

    has_precision_selection = bool(
        getattr(window, "_s05_selected_song_id", "")
        or getattr(window, "_s05_selected_layer_id", "")
    )
    timeline._post_album_split.setEnabled(has_precision_selection)

    precision = getattr(window, "timeline_precision_s05", None)
    if precision is not None:
        timeline._post_album_ripple.blockSignals(True)
        timeline._post_album_ripple.setChecked(precision.ripple.isChecked())
        timeline._post_album_ripple.blockSignals(False)


def _deferred_album_sync(window) -> None:
    if getattr(window.foundation_state, "workspace", "") == "album":
        _sync_album_timeline_chrome(window)


def _install_album_timeline_chrome(window) -> None:
    timeline = window.foundation_shell.timeline
    if getattr(timeline, "_post_album_toolbar_host", None) is not None:
        _sync_album_timeline_chrome(window)
        return

    body = timeline.canvas.parentWidget()
    body_layout = body.layout() if body is not None else None
    if body is None or body_layout is None:
        return

    placeholder_controls = [timeline.mode]
    for button in body.findChildren(QPushButton):
        if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
            placeholder_controls.append(button)
    timeline._post_album_placeholder_controls = tuple(placeholder_controls)
    timeline._post_album_placeholder_sizes = {
        widget: (widget.minimumSize(), widget.maximumSize())
        for widget in placeholder_controls
    }

    host = QFrame(body)
    host.setObjectName("postAlbumTimelineToolbar")
    host.setStyleSheet("QFrame#postAlbumTimelineToolbar{background:#FFFFFF;border:none;}")
    row = QHBoxLayout(host)
    row.setContentsMargins(4, 1, 4, 1)
    row.setSpacing(4)

    undo = FAMButton("", icon_name="undo", kind="ghost")
    undo.setToolTip("Undo")
    undo.setFixedWidth(32)
    redo = FAMButton("", icon_name="redo", kind="ghost")
    redo.setToolTip("Redo")
    redo.setFixedWidth(32)
    undo.clicked.connect(lambda: window.foundation_shell.command_bar.buttons["undo"].click())
    redo.clicked.connect(lambda: window.foundation_shell.command_bar.buttons["redo"].click())
    row.addWidget(undo)
    row.addWidget(redo)

    divider = QFrame(host)
    divider.setFrameShape(QFrame.Shape.VLine)
    divider.setStyleSheet("color:#D8E4F2;")
    divider.setFixedHeight(24)
    row.addWidget(divider)

    split = FAMButton("Pisah", kind="ghost")
    split.setToolTip("Pisah clip pada playhead — aktif saat clip Timeline dipilih")
    if hasattr(window, "_s05_split"):
        split.clicked.connect(window._s05_split)
    row.addWidget(split)

    delete = FAMButton("Hapus", kind="ghost")
    delete.setToolTip("Hapus lagu yang dipilih dari Album")
    delete.clicked.connect(window._s04_delete)
    row.addWidget(delete)

    ripple = FAMButton("Ripple", kind="ghost")
    ripple.setCheckable(True)
    ripple.setToolTip("Mode Ripple Timeline")
    precision = getattr(window, "timeline_precision_s05", None)
    if precision is not None:
        ripple.toggled.connect(precision.ripple.setChecked)
    else:
        ripple.setEnabled(False)
    row.addWidget(ripple)
    row.addStretch(1)

    timeline._post_album_toolbar_host = host
    timeline._post_album_undo = undo
    timeline._post_album_redo = redo
    timeline._post_album_split = split
    timeline._post_album_delete = delete
    timeline._post_album_ripple = ripple
    body_layout.insertWidget(0, host)

    if hasattr(window, "album_workspace"):
        window.album_workspace.selection_changed.connect(
            lambda _ids: _sync_album_timeline_chrome(window)
        )
    if hasattr(window, "editor_workspace"):
        window.editor_workspace.documentChanged.connect(
            lambda _document: _sync_album_timeline_chrome(window)
        )

    _sync_album_timeline_chrome(window)


def install_post_release_album_detail_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_album_pixel_match import (
        PixelAlbumContextWidget,
        PixelAlbumMassToolsWidget,
        PixelAlbumSongTable,
        PixelAlbumTimelineOverviewCanvas,
    )
    from .post_release_album_timeline_adjustment import _paint_album_timeline

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

    # The detailed painter already exists in the Album layer, but the pixel-match
    # subclass owns paintEvent. Apply it explicitly so UI-03 gets thumbnails,
    # ruler, add-slot and waveform without changing timeline state.
    PixelAlbumTimelineOverviewCanvas.paintEvent = _paint_album_timeline

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_route = Window._s04_route

    def window_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_album_timeline_chrome(self)
        QTimer.singleShot(0, lambda: _deferred_album_sync(self))

    def album_route(self, route: str) -> None:
        previous_route(self, route)
        _install_album_timeline_chrome(self)
        _sync_album_timeline_chrome(self)
        QTimer.singleShot(0, lambda: _deferred_album_sync(self))

    Window.__init__ = window_init
    Window._s04_route = album_route
    _installed = True
