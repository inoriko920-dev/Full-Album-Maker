from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .album_model import PAGE_SIZE, album_duration_text, page_rows, summary
from .album_workspace import (
    AlbumContextWidget,
    AlbumMassToolsWidget,
    AlbumSongTable,
    AlbumTimelineOverviewCanvas,
    AlbumWorkspace,
)
from .editor_models import ProjectDocument
from .foundation_components import FAMButton, FAMCard, FAMStatusChip
from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS


_installed = False
_originals: dict[str, Any] = {}


def _context_init(self: AlbumContextWidget, parent=None) -> None:
    QFrame.__init__(self, parent)
    self.setObjectName("albumContext")
    root = QVBoxLayout(self)
    root.setContentsMargins(11, 10, 11, 10)
    root.setSpacing(8)

    title = QLabel("Album Saya")
    title.setObjectName("sectionHeading")
    title.setStyleSheet("font-size:18px;font-weight:750;")
    title.setFixedHeight(28)
    root.addWidget(title)

    card = FAMCard()
    card.setMinimumHeight(126)
    row = QHBoxLayout(card)
    row.setContentsMargins(9, 9, 9, 9)
    row.setSpacing(10)

    self.cover = QLabel("♫")
    self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.cover.setFixedSize(102, 104)
    self.cover.setStyleSheet(
        f"background:{TOKENS.app_bg}; border:1px solid {TOKENS.border}; border-radius:7px;"
    )
    self.cover.setCursor(Qt.CursorShape.PointingHandCursor)
    self.cover.mousePressEvent = lambda _event: self.edit_album_cover_requested.emit()
    row.addWidget(self.cover)

    info = QVBoxLayout()
    info.setContentsMargins(0, 2, 0, 1)
    info.setSpacing(5)
    name_row = QHBoxLayout()
    name_row.setContentsMargins(0, 0, 0, 0)
    name_row.setSpacing(3)
    self.album_title = QLabel("Full Album")
    self.album_title.setObjectName("sectionHeading")
    self.album_title.setStyleSheet("font-size:15px;font-weight:750;")
    self.album_title.setWordWrap(True)
    name_row.addWidget(self.album_title, 1)
    edit = FAMButton("", icon_name="settings", kind="ghost")
    edit.setToolTip("Edit nama album")
    edit.setFixedSize(29, 29)
    edit.clicked.connect(self.edit_title_requested)
    name_row.addWidget(edit)
    info.addLayout(name_row)
    self.stats = QLabel("0 lagu • 0m")
    self.stats.setObjectName("metadata")
    self.stats.setStyleSheet(f"color:{TOKENS.primary_600};font-size:12px;")
    info.addWidget(self.stats)
    self.modified = QLabel("Album aktif")
    self.modified.setObjectName("muted")
    self.modified.setStyleSheet(f"color:{TOKENS.text_muted};font-size:11px;")
    self.modified.setWordWrap(True)
    info.addWidget(self.modified)
    info.addStretch(1)
    row.addLayout(info, 1)
    root.addWidget(card)

    icon_names = {
        "all": "album",
        "missing_cover": "media",
        "missing_visual": "timeline",
        "review": "settings",
    }
    self.filter_buttons = {}
    for key, label in self.FILTERS:
        button = QPushButton(label)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setIcon(foundation_icon(icon_names[key], size=19))
        button.setIconSize(QSize(19, 19))
        button.setFixedHeight(49)
        button.setStyleSheet(
            "QPushButton#navButton{min-height:49px;max-height:49px;padding:3px 10px;"
            "border-radius:7px;text-align:left;}"
        )
        button.clicked.connect(lambda _checked=False, value=key: self.filter_requested.emit(value))
        self.filter_buttons[key] = button
        root.addWidget(button)
    self.filter_buttons["all"].setChecked(True)
    root.addStretch(1)


def _context_apply(self: AlbumContextWidget, document: ProjectDocument, filter_key: str) -> None:
    _originals["context_apply"](self, document, filter_key)
    label = str(document.extensions.get("album_created_label", "") or "").strip()
    self.modified.setText(label or "Album aktif")


def _table_init(self: AlbumSongTable, parent=None) -> None:
    QTableWidget.__init__(self, parent)
    self._refreshing = False
    self._selected_ids: set[str] = set()
    self._rows = []
    self._assets = {}
    self._page_base = 0

    self.setColumnCount(9)
    self.setHorizontalHeaderLabels(["", "", "#", "Lagu", "Durasi", "Visual", "Transisi", "Status", ""])
    self.verticalHeader().hide()
    self.setShowGrid(False)
    self.setAlternatingRowColors(False)
    self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.setDragEnabled(True)
    self.setAcceptDrops(True)
    self.setDropIndicatorShown(True)
    self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    self.setDefaultDropAction(Qt.DropAction.MoveAction)
    self.setDragDropOverwriteMode(False)
    self.setIconSize(QSize(42, 28))

    header = self.horizontalHeader()
    header.setFixedHeight(36)
    header.setMinimumSectionSize(20)
    for col in range(9):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    self.setColumnWidth(0, 27)
    self.setColumnWidth(1, 32)
    self.setColumnWidth(2, 33)
    self.setColumnWidth(4, 70)
    self.setColumnWidth(5, 116)
    self.setColumnWidth(6, 105)
    self.setColumnWidth(7, 126)
    self.setColumnWidth(8, 30)
    self.setStyleSheet(
        "QTableWidget{background:#FFFFFF;border:1px solid #D8E4F2;border-radius:7px;"
        "selection-background-color:#EAF3FF;selection-color:#10234A;}"
        "QHeaderView::section{background:#FFFFFF;color:#10234A;border:none;"
        "border-bottom:1px solid #D8E4F2;padding:4px 5px;font-weight:650;}"
        "QTableWidget::item{border:none;border-bottom:1px solid #E5EDF7;padding:2px 5px;}"
    )
    self.itemChanged.connect(self._item_changed)


def _asset_preview_path(table: AlbumSongTable, row, *, visual: bool = False) -> str:
    audio = table._assets.get(row.asset_id)
    metadata = getattr(audio, "metadata", {}) if audio is not None else {}
    if visual:
        preview = str(metadata.get("visual_preview_path", "") or "")
        asset = table._assets.get(row.visual_asset_id) if row.visual_asset_id else None
    else:
        preview = str(metadata.get("artwork_path", "") or "")
        asset = table._assets.get(row.cover_asset_id) if row.cover_asset_id else None
    if asset is not None:
        locator = str(getattr(asset, "locator", "") or "")
        if locator and Path(locator).is_file() and Path(locator).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return locator
    return preview if preview and Path(preview).is_file() else ""


def _set_item_bg(item: QTableWidgetItem, selected: bool) -> None:
    if selected:
        item.setBackground(QColor("#F3F8FF"))


def _table_set_rows(self: AlbumSongTable, values, selected_ids: set[str], *, page: int) -> None:
    self._refreshing = True
    self.blockSignals(True)
    self._rows = list(values)
    self._selected_ids = set(selected_ids)
    self._page_base = max(0, (int(page) - 1) * PAGE_SIZE)
    self.setRowCount(len(values))

    for row_index, row in enumerate(values):
        selected = row.song_id in selected_ids
        self.setRowHeight(row_index, 38)

        drag = QTableWidgetItem("⋮⋮")
        drag.setData(Qt.ItemDataRole.UserRole, row.song_id)
        drag.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
        drag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        drag.setForeground(QColor(TOKENS.primary_600))
        _set_item_bg(drag, selected)
        self.setItem(row_index, 0, drag)

        check = QTableWidgetItem("")
        check.setData(Qt.ItemDataRole.UserRole, row.song_id)
        check.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        check.setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
        check.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_item_bg(check, selected)
        self.setItem(row_index, 1, check)

        number = QTableWidgetItem(str(row.position))
        number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_item_bg(number, selected)
        self.setItem(row_index, 2, number)

        song = QTableWidgetItem(row.title or Path(row.original_name).stem)
        if row.artist:
            song.setToolTip(f"{row.title}\n{row.artist}")
        preview = _asset_preview_path(self, row)
        if preview:
            song.setIcon(QIcon(preview))
        _set_item_bg(song, selected)
        self.setItem(row_index, 3, song)

        duration = QTableWidgetItem(__import__("full_album_maker.album_model", fromlist=["format_duration"]).format_duration(row.duration_seconds))
        duration.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        duration.setForeground(QColor("#275A9F"))
        _set_item_bg(duration, selected)
        self.setItem(row_index, 4, duration)

        visual = QTableWidgetItem(row.visual_label)
        visual.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        visual_preview = _asset_preview_path(self, row, visual=True)
        if visual_preview and row.visual_asset_id:
            visual.setIcon(QIcon(visual_preview))
        elif not row.visual_asset_id:
            visual.setIcon(foundation_icon("media", color="#6D88AE", size=18))
            visual.setForeground(QColor("#6A7A92"))
        _set_item_bg(visual, selected)
        self.setItem(row_index, 5, visual)

        transition = QTableWidgetItem(row.transition.label)
        transition.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        transition.setForeground(QColor("#3B639B"))
        transition.setBackground(QColor("#EDF4FF"))
        self.setItem(row_index, 6, transition)

        status = QTableWidgetItem(row.status)
        status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if row.status_state == "success":
            status.setForeground(QColor("#187A43"))
            status.setBackground(QColor("#EEFAF3"))
        elif row.status_state == "warning":
            status.setForeground(QColor("#966A00"))
            status.setBackground(QColor("#FFF4DD"))
        else:
            status.setForeground(QColor("#B53A3A"))
            status.setBackground(QColor("#FFF0F0"))
        self.setItem(row_index, 7, status)

        menu = QTableWidgetItem("•••")
        menu.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        menu.setForeground(QColor("#275A9F"))
        _set_item_bg(menu, selected)
        self.setItem(row_index, 8, menu)

    self.blockSignals(False)
    self._refreshing = False


def _table_item_changed(self: AlbumSongTable, item: QTableWidgetItem) -> None:
    if self._refreshing or item.column() != 1:
        return
    song_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
    if not song_id:
        return
    if item.checkState() == Qt.CheckState.Checked:
        self._selected_ids.add(song_id)
    else:
        self._selected_ids.discard(song_id)
    self.selected_ids_changed.emit(tuple(self._selected_ids))


def _workspace_init(self: AlbumWorkspace, parent=None) -> None:
    QFrame.__init__(self, parent)
    self.setObjectName("albumWorkspace")
    self._document = ProjectDocument.new_empty()
    self._filter_key = "all"
    self._page = 1
    self._selected_ids: set[str] = set()

    root = QVBoxLayout(self)
    root.setContentsMargins(14, 10, 14, 7)
    root.setSpacing(7)

    header = QWidget()
    header_row = QHBoxLayout(header)
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(10)
    heading_box = QVBoxLayout()
    heading_box.setContentsMargins(0, 0, 0, 0)
    heading_box.setSpacing(0)
    title = QLabel("Daftar Lagu Album")
    title.setObjectName("workspaceHeading")
    title.setStyleSheet("font-size:27px;font-weight:780;color:#10234A;")
    subtitle = QLabel("Kelola urutan lagu, cover, visual, dan transisi untuk video album Anda.")
    subtitle.setObjectName("muted")
    subtitle.setStyleSheet("font-size:13px;color:#5872A0;")
    heading_box.addWidget(title)
    heading_box.addWidget(subtitle)
    header_row.addLayout(heading_box, 1)
    auto = FAMButton("Auto Susun Timeline", icon_name="auto", kind="primary")
    auto.setMinimumWidth(270)
    auto.setFixedHeight(47)
    auto.clicked.connect(self.auto_arrange_requested)
    header_row.addWidget(auto)
    root.addWidget(header)

    self.bulk = FAMCard()
    self.bulk.setFixedHeight(48)
    bulk_row = QHBoxLayout(self.bulk)
    bulk_row.setContentsMargins(9, 5, 7, 5)
    bulk_row.setSpacing(3)
    marker = QLabel("✓")
    marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
    marker.setFixedSize(22, 22)
    marker.setStyleSheet(
        f"background:{TOKENS.primary_600};color:white;border-radius:4px;font-weight:800;"
    )
    bulk_row.addWidget(marker)
    self.bulk_count = QLabel("0 lagu dipilih")
    self.bulk_count.setStyleSheet("font-weight:700;color:#10234A;padding-right:4px;")
    bulk_row.addWidget(self.bulk_count)

    self.bulk_buttons = []
    actions = (
        ("Set Cover", "media", self.set_cover_requested),
        ("Assign Visual", "timeline", self.assign_visual_requested),
        ("Transisi", "auto", lambda: self.transition_requested.emit("fade", 2.0)),
        ("Hapus", "render", self.delete_requested),
        ("Pindah ke Atas", "undo", self.move_top_requested),
        ("Pindah ke Bawah", "redo", self.move_bottom_requested),
    )
    for text, icon_name, signal_or_fn in actions:
        button = FAMButton(text, icon_name=icon_name, kind="ghost")
        button.setMinimumWidth(0)
        if hasattr(signal_or_fn, "emit"):
            button.clicked.connect(signal_or_fn.emit)
        else:
            button.clicked.connect(signal_or_fn)
        self.bulk_buttons.append(button)
        bulk_row.addWidget(button)
    overflow = FAMButton("•••", kind="ghost")
    overflow.setFixedWidth(36)
    overflow.setToolTip("Aksi Album lainnya")
    self.bulk_buttons.append(overflow)
    bulk_row.addWidget(overflow)
    bulk_row.addStretch(1)
    root.addWidget(self.bulk)

    self.table = AlbumSongTable()
    self.table.selected_ids_changed.connect(self._selection_from_table)
    self.table.reorder_requested.connect(self.reorder_requested)
    root.addWidget(self.table, 1)

    footer = QHBoxLayout()
    footer.setContentsMargins(0, 1, 0, 0)
    self.total_label = QLabel("0 lagu")
    self.total_label.setObjectName("metadata")
    self.total_label.setStyleSheet("color:#365B91;font-size:12px;")
    footer.addWidget(self.total_label)
    footer.addStretch(1)
    self.prev_page = FAMButton("‹", kind="ghost")
    self.prev_page.setFixedWidth(36)
    self.page_label = QLabel("Halaman 1 dari 1")
    self.page_label.setStyleSheet("color:#365B91;")
    self.next_page = FAMButton("›", kind="ghost")
    self.next_page.setFixedWidth(36)
    footer.addWidget(self.prev_page)
    footer.addWidget(self.page_label)
    footer.addWidget(self.next_page)
    self.prev_page.clicked.connect(lambda: self.set_page(self._page - 1))
    self.next_page.clicked.connect(lambda: self.set_page(self._page + 1))
    root.addLayout(footer)
    self._refresh()


def _mass_init(self: AlbumMassToolsWidget, parent=None) -> None:
    QScrollArea.__init__(self, parent)
    self.setWidgetResizable(True)
    self.setFrameShape(QFrame.Shape.NoFrame)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    body = QWidget()
    root = QVBoxLayout(body)
    root.setContentsMargins(9, 3, 9, 8)
    root.setSpacing(7)

    self.heading = QLabel("Alat Massal (0 lagu dipilih)")
    self.heading.setObjectName("sectionHeading")
    self.heading.setStyleSheet("font-size:16px;font-weight:750;")
    root.addWidget(self.heading)

    self._action_widgets = []

    def add_action(title: str, subtitle: str, icon: str, callback) -> None:
        button = FAMButton(f"{title}\n{subtitle}", icon_name=icon, kind="secondary")
        button.setStyleSheet(
            "QPushButton{text-align:left;padding:6px 10px;font-weight:650;}"
        )
        button.setMinimumHeight(58)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(callback)
        root.addWidget(button)
        self._action_widgets.append(button)

    add_action("Kelola Cover", "Atur cover untuk lagu yang dipilih", "media", self.set_cover_requested.emit)
    add_action("Auto Match Cover", "Cocokkan cover dari media", "ai", self.auto_match_cover_requested.emit)
    add_action("Assign Visual", "Terapkan visual ke lagu terpilih", "timeline", self.assign_visual_requested.emit)
    add_action("Clear Visual", "Hapus visual dari lagu terpilih", "render", self.clear_visual_requested.emit)

    self.transition = QComboBox()
    self.transition.addItem("Fade", "fade")
    self.transition.addItem("Cross Fade", "cross_fade")
    self.transition.addItem("Zoom", "zoom")
    self.transition.addItem("Slide", "slide")
    self.transition.addItem("Cut", "cut")

    self.duration = QDoubleSpinBox()
    self.duration.setRange(0.0, 10.0)
    self.duration.setDecimals(1)
    self.duration.setSingleStep(0.1)
    self.duration.setSuffix(" detik")
    self.duration.setValue(2.0)

    add_action("Default Transition", "Terapkan transisi yang sama", "auto", self._emit_transition)

    summary_title = QLabel("Ringkasan Pilihan")
    summary_title.setStyleSheet("font-weight:700;color:#10234A;")
    root.addWidget(summary_title)
    self.selection_chip = FAMStatusChip("Dipilih: 0 lagu", "neutral")
    self.selection_chip.setMinimumHeight(38)
    self.selection_chip.setStyleSheet(
        "padding:8px 10px;border:1px solid #D8E8FB;border-radius:7px;"
        "background:#EAF3FF;color:#1766E8;font-weight:700;"
    )
    root.addWidget(self.selection_chip)

    quick = QFrame()
    quick_row = QVBoxLayout(quick)
    quick_row.setContentsMargins(0, 3, 0, 0)
    quick_row.setSpacing(6)
    trans_row = QHBoxLayout()
    trans_row.addWidget(QLabel("Opsi Transisi Cepat"))
    trans_row.addWidget(self.transition, 1)
    quick_row.addLayout(trans_row)
    dur_row = QHBoxLayout()
    dur_row.addWidget(QLabel("Durasi Transisi"))
    dur_row.addWidget(self.duration, 1)
    quick_row.addLayout(dur_row)
    root.addWidget(quick)
    root.addStretch(1)
    self.setWidget(body)
    self.set_selection_count(0)


def _timeline_paint(self: AlbumTimelineOverviewCanvas, event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(self.rect(), QColor(TOKENS.surface))

    left = 124
    ruler_h = 22
    video_y = 25
    video_h = max(34, int((self.height() - ruler_h - 10) * 0.48))
    audio_y = video_y + video_h + 4
    audio_h = max(26, self.height() - audio_y - 3)
    right = max(left + 40, self.width() - 12)
    usable = max(1, right - left)

    painter.setPen(QPen(QColor("#D7E4F3"), 1))
    painter.drawLine(left, ruler_h, right, ruler_h)
    tick_count = 16
    for i in range(tick_count):
        x = left + int(usable * i / max(1, tick_count - 1))
        painter.setPen(QPen(QColor("#AFC7E7"), 1))
        painter.drawLine(x, ruler_h - 3, x, ruler_h + 3)
        painter.setPen(QColor("#55709B"))
        label = "00:00" if i == 0 else (f"{i*10//60}:{i*10%60:02d}:00" if i >= 6 else f"{i*10:02d}:00")
        painter.drawText(QRectF(x - 8, 1, 58, 17), Qt.AlignmentFlag.AlignLeft, label)

    painter.setPen(QColor("#183B73"))
    painter.drawText(QRectF(18, video_y, left - 26, video_h), Qt.AlignmentFlag.AlignVCenter, "▣  Video")
    painter.drawText(QRectF(18, audio_y, left - 26, audio_h), Qt.AlignmentFlag.AlignVCenter, "♫  Audio")
    painter.setPen(QPen(QColor("#D8E4F2"), 1))
    painter.drawLine(0, audio_y - 2, self.width(), audio_y - 2)

    songs = list(self._document.playlist.entries)
    assets = self._document.asset_map()
    shown = songs[:7]
    clip_area = int(usable * 0.86)
    clip_width = max(72, clip_area // max(1, len(shown)))
    cursor = left + 2

    for index, song in enumerate(shown):
        width = min(clip_width - 3, max(54, right - cursor - 60))
        rect = QRectF(cursor, video_y + 1, width, video_h - 2)
        audio = assets.get(song.asset_id)
        preview_path = ""
        if audio is not None:
            preview_path = str(audio.metadata.get("artwork_path", "") or "")
        pixmap = QPixmap(preview_path) if preview_path and Path(preview_path).is_file() else QPixmap()
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                int(rect.width()),
                int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.save()
            painter.setClipRect(rect)
            painter.drawPixmap(int(rect.x()), int(rect.y()), scaled)
            painter.fillRect(rect, QColor(8, 31, 63, 55))
            painter.restore()
        else:
            colors = ("#D9E9FA", "#EADFBF", "#D8E8DD", "#F0D5B7", "#D7E3F2", "#D3E8EF", "#E9D9C3")
            painter.fillRect(rect, QColor(colors[index % len(colors)]))
        painter.setPen(QColor("#FFFFFF" if not pixmap.isNull() else "#16345F"))
        title = song.display_title or (Path(audio.original_name).stem if audio is not None else f"Lagu {index+1}")
        painter.drawText(rect.adjusted(7, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, f"{index+1}. {title}")
        painter.setPen(QPen(QColor("#6EA5E8"), 1))
        painter.drawRect(rect)
        cursor += clip_width
        if cursor >= right - 80:
            break

    if cursor < right - 36:
        add_rect = QRectF(cursor + 2, video_y + 1, right - cursor - 4, video_h - 2)
        painter.setPen(QPen(QColor("#9CBCE6"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor("#F7FBFF"))
        painter.drawRect(add_rect)
        painter.setPen(QColor(TOKENS.primary_600))
        painter.drawText(add_rect, Qt.AlignmentFlag.AlignCenter, "+")

    wave_rect = QRectF(left + 2, audio_y + 2, usable - 4, audio_h - 5)
    painter.fillRect(wave_rect, QColor("#D9F7F4"))
    painter.setPen(QPen(QColor("#42D4C9"), 1))
    mid = wave_rect.center().y()
    bars = max(100, int(wave_rect.width() // 5))
    for i in range(bars):
        x = wave_rect.left() + i * wave_rect.width() / bars
        amp = 3 + ((i * 17 + i * i * 3) % max(5, int(wave_rect.height() - 7)))
        painter.drawLine(int(x), int(mid - amp / 2), int(x), int(mid + amp / 2))

    painter.setPen(QPen(QColor("#0D6BFF"), 2))
    painter.drawLine(left + 2, ruler_h - 2, left + 2, self.height())
    painter.end()


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    timeline = self.timeline

    if not hasattr(timeline, "_album_header_tools"):
        head = timeline.layout().itemAt(0).layout()
        timeline._album_header_tools = []
        specs = (
            ("", "undo", "Undo terakhir tersedia dari command bar"),
            ("", "redo", "Redo terakhir tersedia dari command bar"),
            ("Potong", "auto", "Buka Timeline precision untuk memotong clip"),
            ("Pisah", "timeline", "Buka Timeline precision untuk memisah clip"),
            ("Hapus", "render", "Buka Timeline precision untuk menghapus clip"),
            ("Ripple", "auto", "Buka Timeline precision untuk ripple edit"),
        )
        insert_at = 2
        for label, icon_name, tooltip in specs:
            button = FAMButton(label, icon_name=icon_name, kind="ghost")
            button.setEnabled(False)
            button.setToolTip(tooltip)
            button.setMinimumWidth(0)
            head.insertWidget(insert_at, button)
            insert_at += 1
            timeline._album_header_tools.append(button)

    album_active = route == "album"
    for button in timeline._album_header_tools:
        button.setVisible(album_active)
    if album_active:
        timeline.message.hide()
        timeline.mode.hide()
        for button in timeline.body.findChildren(QPushButton):
            if button.text() in {"Split", "Ripple", "Snap", "Marker"}:
                button.hide()


def _shell_sizes(self, route: str) -> None:
    if route != "album":
        _originals["shell_sizes"](self, route)
        return

    total = max(1, self.width())
    compact = bool(getattr(self, "_responsive_compact", False))
    nav = TOKENS.nav_compact_width if compact else 168
    context = 216 if compact else 297
    right = 38 if self.inspector.collapsed else (286 if compact else 324)
    center = max(430 if compact else 600, total - nav - context - right - TOKENS.splitter_handle * 3)

    self.navigation.setMinimumWidth(nav)
    self.navigation.setMaximumWidth(nav)
    self.context.setMinimumWidth(context)
    self.context.setMaximumWidth(context)
    if not self.inspector.collapsed:
        self.inspector.setMinimumWidth(right)
        self.inspector.setMaximumWidth(520)
    self.horizontal_splitter.setSizes([nav, context, center, right])

    timeline_height = TOKENS.timeline_collapsed_height if self.timeline.collapsed else self.timeline.preferred_height
    top_height = max(300, self.height() - timeline_height - TOKENS.status_height - TOKENS.command_height)
    self.vertical_splitter.setSizes([top_height, timeline_height])


def install_ui03_album_remediation() -> None:
    """Post-release UI-03 parity layer. Functional Album contracts remain authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget

    _originals.update(
        context_init=AlbumContextWidget.__init__,
        context_apply=AlbumContextWidget.apply_document,
        table_init=AlbumSongTable.__init__,
        table_set_rows=AlbumSongTable.set_rows,
        table_item_changed=AlbumSongTable._item_changed,
        workspace_init=AlbumWorkspace.__init__,
        mass_init=AlbumMassToolsWidget.__init__,
        timeline_paint=AlbumTimelineOverviewCanvas.paintEvent,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    AlbumContextWidget.__init__ = _context_init
    AlbumContextWidget.apply_document = _context_apply
    AlbumSongTable.__init__ = _table_init
    AlbumSongTable.set_rows = _table_set_rows
    AlbumSongTable._item_changed = _table_item_changed
    AlbumWorkspace.__init__ = _workspace_init
    AlbumMassToolsWidget.__init__ = _mass_init
    AlbumTimelineOverviewCanvas.paintEvent = _timeline_paint
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
