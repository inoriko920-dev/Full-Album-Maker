from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .album_model import (
    PAGE_SIZE,
    AlbumSongRow,
    album_cover_asset_id,
    album_duration_text,
    default_transition,
    format_duration,
    page_rows,
    summary,
)
from .editor_models import ProjectDocument
from .foundation_components import FAMButton, FAMCard, FAMSectionHeader, FAMStatusChip
from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS


class AlbumContextWidget(QFrame):
    filter_requested = Signal(str)
    edit_title_requested = Signal()
    edit_album_cover_requested = Signal()

    FILTERS = (
        ("all", "Semua Lagu"),
        ("missing_cover", "Belum Ada Cover"),
        ("missing_visual", "Belum Ada Visual"),
        ("review", "Perlu Ditinjau"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("albumContext")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel("Album Saya")
        title.setObjectName("sectionHeading")
        root.addWidget(title)

        card = FAMCard()
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)
        self.cover = QLabel("♫")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setFixedSize(68, 68)
        self.cover.setStyleSheet(
            f"background:{TOKENS.app_bg}; border:1px solid {TOKENS.border}; border-radius:8px;"
        )
        self.cover.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cover.mousePressEvent = lambda _event: self.edit_album_cover_requested.emit()
        row.addWidget(self.cover)
        info = QVBoxLayout()
        name_row = QHBoxLayout()
        self.album_title = QLabel("Full Album")
        self.album_title.setObjectName("sectionHeading")
        self.album_title.setWordWrap(True)
        name_row.addWidget(self.album_title, 1)
        edit = QPushButton("✎")
        edit.setToolTip("Edit nama album")
        edit.setFixedWidth(28)
        edit.clicked.connect(self.edit_title_requested)
        name_row.addWidget(edit)
        info.addLayout(name_row)
        self.stats = QLabel("0 lagu • 0m")
        self.stats.setObjectName("metadata")
        info.addWidget(self.stats)
        self.modified = QLabel("Album aktif")
        self.modified.setObjectName("muted")
        info.addWidget(self.modified)
        info.addStretch(1)
        row.addLayout(info, 1)
        root.addWidget(card)

        self.filter_buttons: dict[str, QPushButton] = {}
        for key, label in self.FILTERS:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setIcon(foundation_icon("audio", size=16))
            button.setMinimumHeight(36)
            button.clicked.connect(lambda _checked=False, value=key: self.filter_requested.emit(value))
            self.filter_buttons[key] = button
            root.addWidget(button)
        self.filter_buttons["all"].setChecked(True)
        root.addStretch(1)

    def apply_document(self, document: ProjectDocument, filter_key: str) -> None:
        stats = summary(document)
        self.album_title.setText(document.album_title.strip() or document.name.strip() or "Full Album")
        self.stats.setText(f"{stats.song_count} lagu • {album_duration_text(stats.duration_seconds)}")
        values = {
            "all": stats.song_count,
            "missing_cover": stats.missing_cover,
            "missing_visual": stats.missing_visual,
            "review": stats.needs_review,
        }
        labels = dict(self.FILTERS)
        for key, button in self.filter_buttons.items():
            button.setText(f"{labels[key]}    {values[key]}")
            button.setChecked(key == filter_key)
        self._set_cover(document)

    def _set_cover(self, document: ProjectDocument) -> None:
        asset_id = album_cover_asset_id(document)
        asset = document.asset_map().get(asset_id) if asset_id else None
        path = Path(asset.locator) if asset is not None else None
        if path is not None and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.cover.setPixmap(
                    pixmap.scaled(
                        self.cover.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self.cover.setPixmap(QPixmap())
        self.cover.setText("♫")


class AlbumSongTable(QTableWidget):
    selected_ids_changed = Signal(object)
    reorder_requested = Signal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._refreshing = False
        self._selected_ids: set[str] = set()
        self._rows: list[AlbumSongRow] = []
        self._assets = {}
        self._page_base = 0
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["", "#", "Lagu", "Durasi", "Visual", "Transisi", "Status"])
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col in (3, 4, 5, 6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.setColumnWidth(0, 52)
        self.setColumnWidth(1, 34)
        self.itemChanged.connect(self._item_changed)

    @property
    def selected_song_ids(self) -> set[str]:
        return set(self._selected_ids)

    def set_document_assets(self, assets: dict) -> None:
        self._assets = dict(assets)

    def set_rows(self, values: list[AlbumSongRow], selected_ids: set[str], *, page: int) -> None:
        self._refreshing = True
        self.blockSignals(True)
        self._rows = list(values)
        self._selected_ids = set(selected_ids)
        self._page_base = max(0, (int(page) - 1) * PAGE_SIZE)
        self.setRowCount(len(values))
        for row_index, row in enumerate(values):
            self.setRowHeight(row_index, 43)
            check = QTableWidgetItem("⋮⋮")
            check.setData(Qt.ItemDataRole.UserRole, row.song_id)
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            check.setCheckState(Qt.CheckState.Checked if row.song_id in selected_ids else Qt.CheckState.Unchecked)
            check.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 0, check)

            number = QTableWidgetItem(str(row.position))
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 1, number)

            song = QTableWidgetItem(row.title or Path(row.original_name).stem)
            if row.artist:
                song.setToolTip(f"{row.title}\n{row.artist}")
            cover = self._assets.get(row.cover_asset_id) if row.cover_asset_id else None
            if cover is not None and Path(cover.locator).is_file():
                song.setIcon(QIcon(cover.locator))
            self.setItem(row_index, 2, song)

            duration = QTableWidgetItem(format_duration(row.duration_seconds))
            duration.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 3, duration)
            visual = QTableWidgetItem(row.visual_label)
            visual.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 4, visual)
            transition = QTableWidgetItem(row.transition.label)
            transition.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row_index, 5, transition)
            status = QTableWidgetItem(row.status)
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row.status_state == "success":
                status.setForeground(QColor(TOKENS.success))
            elif row.status_state == "warning":
                status.setForeground(QColor(TOKENS.warning))
            else:
                status.setForeground(QColor(TOKENS.danger))
            self.setItem(row_index, 6, status)
        self.blockSignals(False)
        self._refreshing = False

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or item.column() != 0:
            return
        song_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not song_id:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(song_id)
        else:
            self._selected_ids.discard(song_id)
        self.selected_ids_changed.emit(tuple(self._selected_ids))

    def dropEvent(self, event) -> None:
        source_row = self.currentRow()
        if not 0 <= source_row < len(self._rows):
            event.ignore()
            return
        point = event.position().toPoint()
        target_row = self.indexAt(point).row()
        if target_row < 0:
            target_row = max(0, len(self._rows) - 1)
        song_id = self._rows[source_row].song_id
        target_position = self._page_base + target_row + 1
        event.acceptProposedAction()
        self.reorder_requested.emit(song_id, target_position)


class AlbumWorkspace(QFrame):
    selection_changed = Signal(object)
    auto_arrange_requested = Signal()
    set_cover_requested = Signal()
    assign_visual_requested = Signal()
    clear_visual_requested = Signal()
    transition_requested = Signal(str, float)
    delete_requested = Signal()
    move_top_requested = Signal()
    move_bottom_requested = Signal()
    reorder_requested = Signal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("albumWorkspace")
        self._document = ProjectDocument.new_empty()
        self._filter_key = "all"
        self._page = 1
        self._selected_ids: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 8)
        root.setSpacing(8)
        header = FAMSectionHeader("Daftar Lagu Album", "Kelola urutan lagu, cover, visual, dan transisi untuk video album Anda.")
        auto = FAMButton("Auto Susun Timeline", icon_name="auto", kind="primary")
        auto.setMinimumWidth(164)
        auto.clicked.connect(self.auto_arrange_requested)
        header.actions.addWidget(auto)
        root.addWidget(header)

        self.bulk = FAMCard()
        bulk_row = QHBoxLayout(self.bulk)
        bulk_row.setContentsMargins(8, 5, 8, 5)
        bulk_row.setSpacing(4)
        self.bulk_count = QLabel("0 lagu dipilih")
        self.bulk_count.setObjectName("metadata")
        bulk_row.addWidget(self.bulk_count)
        self.bulk_buttons: list[QPushButton] = []
        actions = (
            ("Set Cover", self.set_cover_requested),
            ("Assign Visual", self.assign_visual_requested),
            ("Transisi", lambda: self.transition_requested.emit("fade", 2.0)),
            ("Hapus", self.delete_requested),
            ("↑ Pindah ke Atas", self.move_top_requested),
            ("↓ Pindah ke Bawah", self.move_bottom_requested),
        )
        for text, signal_or_fn in actions:
            button = FAMButton(text, kind="ghost")
            if hasattr(signal_or_fn, "emit"):
                button.clicked.connect(signal_or_fn.emit)
            else:
                button.clicked.connect(signal_or_fn)
            self.bulk_buttons.append(button)
            bulk_row.addWidget(button)
        bulk_row.addStretch(1)
        root.addWidget(self.bulk)

        self.table = AlbumSongTable()
        self.table.selected_ids_changed.connect(self._selection_from_table)
        self.table.reorder_requested.connect(self.reorder_requested)
        root.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.total_label = QLabel("0 lagu")
        self.total_label.setObjectName("metadata")
        footer.addWidget(self.total_label)
        footer.addStretch(1)
        self.prev_page = FAMButton("‹", kind="ghost")
        self.next_page = FAMButton("›", kind="ghost")
        self.page_label = QLabel("Halaman 1 dari 1")
        footer.addWidget(self.prev_page)
        footer.addWidget(self.page_label)
        footer.addWidget(self.next_page)
        self.prev_page.clicked.connect(lambda: self.set_page(self._page - 1))
        self.next_page.clicked.connect(lambda: self.set_page(self._page + 1))
        root.addLayout(footer)
        self._refresh()

    @property
    def selected_song_ids(self) -> set[str]:
        return set(self._selected_ids)

    @property
    def filter_key(self) -> str:
        return self._filter_key

    def set_filter(self, filter_key: str) -> None:
        if filter_key not in {"all", "missing_cover", "missing_visual", "review"}:
            filter_key = "all"
        self._filter_key = filter_key
        self._page = 1
        self._refresh()

    def set_page(self, page: int) -> None:
        self._page = max(1, int(page))
        self._refresh()

    def set_selection(self, song_ids: set[str]) -> None:
        valid = set(self._document.song_map())
        self._selected_ids = set(song_ids) & valid
        self._refresh()
        self.selection_changed.emit(tuple(self._selected_ids))

    def apply_document(self, document: ProjectDocument) -> None:
        self._document = document.clone()
        valid = set(self._document.song_map())
        self._selected_ids &= valid
        self._refresh()

    def _selection_from_table(self, song_ids) -> None:
        self._selected_ids = set(song_ids)
        self._update_bulk_state()
        self.selection_changed.emit(tuple(self._selected_ids))

    def _refresh(self) -> None:
        values, pages = page_rows(self._document, self._filter_key, self._page)
        self._page = min(max(1, self._page), pages)
        values, pages = page_rows(self._document, self._filter_key, self._page)
        self.table.set_document_assets(self._document.asset_map())
        self.table.set_rows(values, self._selected_ids, page=self._page)
        self.page_label.setText(f"Halaman {self._page} dari {pages}")
        self.prev_page.setEnabled(self._page > 1)
        self.next_page.setEnabled(self._page < pages)
        self.total_label.setText(f"{len(self._document.playlist.entries)} lagu • {album_duration_text(summary(self._document).duration_seconds)}")
        self._update_bulk_state()

    def _update_bulk_state(self) -> None:
        count = len(self._selected_ids)
        self.bulk_count.setText(f"{count} lagu dipilih")
        for button in self.bulk_buttons:
            button.setEnabled(count > 0)


class AlbumMassToolsWidget(QScrollArea):
    set_cover_requested = Signal()
    auto_match_cover_requested = Signal()
    assign_visual_requested = Signal()
    clear_visual_requested = Signal()
    default_transition_requested = Signal(str, float)
    delete_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.heading = QLabel("Alat Massal (0 lagu dipilih)")
        self.heading.setObjectName("sectionHeading")
        root.addWidget(self.heading)

        for title, subtitle, signal in (
            ("Kelola Cover", "Atur cover untuk lagu yang dipilih", self.set_cover_requested),
            ("Auto Match Cover", "Cocokkan cover dari Media secara aman", self.auto_match_cover_requested),
            ("Assign Visual", "Terapkan visual ke lagu terpilih", self.assign_visual_requested),
            ("Clear Visual", "Hapus visual dari lagu terpilih", self.clear_visual_requested),
        ):
            card = FAMButton(title, kind="secondary")
            card.setToolTip(subtitle)
            card.setMinimumHeight(42)
            card.clicked.connect(signal.emit)
            root.addWidget(card)

        transition_card = FAMCard()
        transition_lay = QVBoxLayout(transition_card)
        transition_lay.setContentsMargins(8, 8, 8, 8)
        transition_lay.addWidget(QLabel("Default Transition"))
        self.transition = QComboBox()
        self.transition.addItem("Fade", "fade")
        self.transition.addItem("Cross Fade", "cross_fade")
        self.transition.addItem("Zoom", "zoom")
        self.transition.addItem("Slide", "slide")
        self.transition.addItem("Cut", "cut")
        transition_lay.addWidget(self.transition)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Durasi"))
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.0, 10.0)
        self.duration.setDecimals(1)
        self.duration.setSingleStep(0.1)
        self.duration.setSuffix(" detik")
        self.duration.setValue(2.0)
        duration_row.addWidget(self.duration, 1)
        transition_lay.addLayout(duration_row)
        apply_transition = FAMButton("Terapkan ke Pilihan", kind="secondary")
        apply_transition.clicked.connect(self._emit_transition)
        transition_lay.addWidget(apply_transition)
        root.addWidget(transition_card)

        summary_card = FAMCard()
        summary_lay = QVBoxLayout(summary_card)
        summary_lay.setContentsMargins(8, 8, 8, 8)
        summary_lay.addWidget(QLabel("Ringkasan Pilihan"))
        self.selection_chip = FAMStatusChip("Dipilih: 0 lagu", "neutral")
        summary_lay.addWidget(self.selection_chip)
        root.addWidget(summary_card)

        delete = FAMButton("Hapus dari Album", kind="ghost")
        delete.clicked.connect(self.delete_requested)
        root.addWidget(delete)
        root.addStretch(1)
        self._action_widgets = [w for w in body.findChildren(QPushButton)]
        self.setWidget(body)
        self.set_selection_count(0)

    def _emit_transition(self) -> None:
        self.default_transition_requested.emit(str(self.transition.currentData()), float(self.duration.value()))

    def set_selection_count(self, count: int) -> None:
        count = max(0, int(count))
        self.heading.setText(f"Alat Massal ({count} lagu dipilih)")
        self.selection_chip.setText(f"Dipilih: {count} lagu")
        for widget in self._action_widgets:
            widget.setEnabled(count > 0)

    def apply_document(self, document: ProjectDocument) -> None:
        value = default_transition(document)
        index = self.transition.findData(value.kind)
        if index >= 0:
            self.transition.setCurrentIndex(index)
        self.duration.setValue(value.duration_seconds)


class AlbumTimelineOverviewCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = ProjectDocument.new_empty()
        self._selected_ids: set[str] = set()
        self.setMinimumHeight(72)

    def set_document(self, document: ProjectDocument, selected_ids: set[str] | None = None) -> None:
        self._document = document.clone()
        self._selected_ids = set(selected_ids or ())
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(TOKENS.surface))
        left = 70
        ruler = 18
        video_y = ruler + 5
        video_h = max(24, int((self.height() - ruler - 12) * 0.43))
        audio_y = video_y + video_h + 4
        audio_h = max(20, self.height() - audio_y - 4)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawLine(left, ruler, self.width(), ruler)
        painter.drawText(QRectF(8, video_y, left - 12, video_h), Qt.AlignmentFlag.AlignVCenter, "Video")
        painter.drawText(QRectF(8, audio_y, left - 12, audio_h), Qt.AlignmentFlag.AlignVCenter, "Audio")
        songs = list(self._document.playlist.entries)
        assets = self._document.asset_map()
        durations = []
        total = 0
        for song in songs:
            asset = assets.get(song.asset_id)
            duration = max(1, int((song.source_out_tick or (asset.source_duration_tick if asset else 0)) - song.source_in_tick))
            durations.append(duration)
            total += duration
        usable = max(1, self.width() - left - 8)
        cursor = left
        for song, duration in zip(songs, durations):
            width = max(3, int(usable * duration / max(1, total)))
            selected = song.song_id in self._selected_ids
            painter.fillRect(QRectF(cursor, video_y, width - 1, video_h), QColor("#D8E8FF" if selected else "#E9F1FB"))
            painter.fillRect(QRectF(cursor, audio_y, width - 1, audio_h), QColor("#B9EEE9" if selected else "#D7F4F1"))
            painter.setPen(QPen(QColor(TOKENS.border), 1))
            painter.drawRect(QRectF(cursor, video_y, width - 1, video_h))
            cursor += width
        painter.end()
