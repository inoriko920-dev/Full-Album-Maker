from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .foundation_components import FAMButton, FAMEmptyState
from .foundation_tokens import TOKENS
from .media_library_model import (
    MediaAsset, MediaLibraryIndex, MediaQuery, MediaSelection, MediaSort,
    MediaStatus, MediaType, MediaViewMode,
)

CATEGORIES = (
    ('all','Semua','▤'), ('audio','Audio','♫'), ('photo','Foto','▧'),
    ('video','Video','▣'), ('favorite','Favorit','☆'), ('missing','Missing','⚠'),
)
COLLECTIONS = ('Aset Utama','B-Roll','Musik','Narasi','Outro')


class MediaContextWidget(QWidget):
    category_requested = Signal(str)
    collection_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._category_buttons = {}
        self._collection_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(1)

        head = QHBoxLayout()
        head.setContentsMargins(4, 0, 2, 3)
        title = QLabel("Media")
        title.setObjectName("sectionHeading")
        title.setStyleSheet("font-size:16px;font-weight:700;")
        title.setFixedHeight(34)
        head.addWidget(title)
        head.addStretch(1)
        add = FAMButton("+", kind="ghost")
        add.setFixedSize(30, 30)
        add.setEnabled(False)
        add.setToolTip("Koleksi baru — tersedia pada pengelolaan koleksi")
        head.addWidget(add)
        root.addLayout(head)

        for key, label, glyph in CATEGORIES:
            button = QPushButton()
            button.setObjectName("mediaContextButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setFixedHeight(35)
            button.setStyleSheet(
                "QPushButton#mediaContextButton{min-height:35px;max-height:35px;text-align:left;"
                "padding:0 8px;border:none;border-left:3px solid transparent;border-radius:6px;"
                "background:transparent;color:#10234A;}"
                "QPushButton#mediaContextButton:hover{background:#F3F8FF;}"
                "QPushButton#mediaContextButton:checked{background:#EAF3FF;color:#1766E8;"
                "border-left:3px solid #1766E8;font-weight:650;}"
            )
            button.clicked.connect(lambda _=False, k=key: self._category(k))
            self._category_buttons[key] = button
            root.addWidget(button)

        self._category_buttons["all"].setChecked(True)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        root.addSpacing(5)
        root.addWidget(line)

        heading = QLabel("Folder Proyek")
        heading.setObjectName("sectionHeading")
        heading.setStyleSheet("font-size:14px;font-weight:700;")
        heading.setFixedHeight(28)
        root.addWidget(heading)

        for name in COLLECTIONS:
            button = QPushButton()
            button.setObjectName("mediaContextButton")
            button.setCheckable(True)
            button.setFixedHeight(34)
            button.setStyleSheet(
                "QPushButton#mediaContextButton{min-height:34px;max-height:34px;text-align:left;"
                "padding:0 8px;border:none;border-left:3px solid transparent;border-radius:6px;"
                "background:transparent;color:#10234A;}"
                "QPushButton#mediaContextButton:hover{background:#F3F8FF;}"
                "QPushButton#mediaContextButton:checked{background:#EAF3FF;color:#1766E8;"
                "border-left:3px solid #1766E8;font-weight:650;}"
            )
            button.clicked.connect(lambda _=False, n=name: self._collection(n))
            self._collection_buttons[name] = button
            root.addWidget(button)

        root.addStretch(1)
        self.set_counts({})
        self.set_collection_counts({})

    def set_counts(self, counts):
        for key, label, glyph in CATEGORIES:
            count = int(counts.get(key, 0))
            button = self._category_buttons[key]
            button.setText(f"{glyph}  {label}    {count}")
            button.setAccessibleName(f"{label}, {count} item")

    def set_collection_counts(self, counts):
        for name, button in self._collection_buttons.items():
            count = int(counts.get(name, 0))
            button.setText(f"▢  {name}    {count}")
            button.setAccessibleName(f"{name}, {count} item")

    def _category(self, key):
        for button in self._collection_buttons.values():
            button.setChecked(False)
        self.category_requested.emit(key)

    def _collection(self, name):
        for button in self._category_buttons.values():
            button.setChecked(False)
        for key, button in self._collection_buttons.items():
            button.setChecked(key == name)
        self.collection_requested.emit(name)

class MediaPreviewPlaceholder(QWidget):
    def __init__(self, asset, parent=None):
        super().__init__(parent); self.asset=asset; self.setMinimumHeight(48); self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing,True); r=self.rect().adjusted(0,0,-1,-1); p.fillRect(r,QColor('#EEF5FF')); p.setPen(QPen(QColor(TOKENS.border),1)); p.drawRoundedRect(r,7,7)
        if self.asset.media_type==MediaType.AUDIO:
            p.setPen(QPen(QColor('#76A9FF'),2)); mid=r.center().y(); usable=max(1,r.width()-20)
            for i in range(28):
                x=r.left()+10+int(i*usable/28); h=6+((i*17+7)%34); p.drawLine(x,mid-h//2,x,mid+h//2)
        else:
            p.setPen(QColor(TOKENS.primary_600)); f=p.font(); f.setPointSize(22); f.setBold(True); p.setFont(f); p.drawText(r,Qt.AlignmentFlag.AlignCenter,'▧' if self.asset.media_type==MediaType.PHOTO else '▶')
        if self.asset.status==MediaStatus.MISSING:
            p.fillRect(r,QColor(255,245,220,170)); p.setPen(QColor('#A56D00')); p.drawText(r.adjusted(6,6,-6,-6),Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeft,'SOURCE MISSING')
        p.end()


class MediaCard(QFrame):
    activated = Signal(str, int)
    checkbox_changed = Signal(str, bool)
    favorite_requested = Signal(str, bool)
    reveal_requested = Signal(str)
    relink_requested = Signal(str)

    def __init__(self, asset, *, selected=False, list_mode=False, parent=None):
        super().__init__(parent)
        self.asset = asset
        self.setObjectName("famCard")
        self.setProperty("selected", selected)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(asset.path)
        self.setAccessibleName(f"{asset.display_name}, {asset.media_type.value}")

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(3)

        self.preview_host = QFrame()
        self.preview_host.setFixedHeight(52 if list_mode else 108)
        preview_grid = QGridLayout(self.preview_host)
        preview_grid.setContentsMargins(0, 0, 0, 0)
        preview_grid.setSpacing(0)

        self.preview = MediaPreviewPlaceholder(asset)
        preview_grid.addWidget(self.preview, 0, 0)

        overlay = QWidget()
        overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        overlay_row = QHBoxLayout(overlay)
        overlay_row.setContentsMargins(6, 5, 6, 0)
        overlay_row.setSpacing(4)

        self.check = QCheckBox()
        self.check.setChecked(selected)
        self.check.setStyleSheet("QCheckBox { background:rgba(255,255,255,225); border-radius:4px; padding:1px; }")
        self.check.toggled.connect(lambda value: self.checkbox_changed.emit(asset.asset_id, value))
        overlay_row.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        overlay_row.addStretch(1)

        more = FAMButton("⋯", kind="secondary")
        more.setFixedSize(28, 26)
        more.setStyleSheet("background:rgba(255,255,255,235);")
        menu = QMenu(more)
        menu.addAction(
            "Hapus dari Favorit" if asset.favorite else "Tambahkan ke Favorit",
            lambda: self.favorite_requested.emit(asset.asset_id, not asset.favorite),
        )
        menu.addAction("Relink…", lambda: self.relink_requested.emit(asset.asset_id))
        menu.addAction("Reveal in Explorer", lambda: self.reveal_requested.emit(asset.asset_id))
        more.setMenu(menu)
        overlay_row.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)
        preview_grid.addWidget(overlay, 0, 0, Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.preview_host)

        self.title = QLabel(asset.display_name)
        self.title.setObjectName("sectionHeading")
        self.title.setStyleSheet("font-size:12px;font-weight:650;")
        self.title.setToolTip(asset.path)
        self.title.setFixedHeight(18)
        root.addWidget(self.title)

        self.meta = QLabel(_meta_text(asset))
        self.meta.setObjectName("metadata")
        self.meta.setStyleSheet("font-size:11px;")
        self.meta.setFixedHeight(17)
        root.addWidget(self.meta)

        self.setMinimumWidth(145)
        self.setFixedHeight(108 if list_mode else 166)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.asset.asset_id, int(event.modifiers().value))
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit(self.asset.asset_id, int(event.modifiers().value))
            event.accept()
            return
        super().keyPressEvent(event)

class MediaWorkspace(QWidget):
    query_changed=Signal(object); selection_changed=Signal(object); import_file_requested=Signal(); import_folder_requested=Signal(); cancel_import_requested=Signal(); favorite_requested=Signal(str,bool); reveal_requested=Signal(str); relink_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName('workspaceHost'); self.index=MediaLibraryIndex(); self.query=MediaQuery(); self.selection=MediaSelection(); self._visible_assets=[]; self._cards=[]
        self._debounce=QTimer(self); self._debounce.setSingleShot(True); self._debounce.setInterval(220); self._debounce.timeout.connect(self._apply_search)
        root=QVBoxLayout(self); root.setContentsMargins(12,10,12,8); root.setSpacing(7); tb=QHBoxLayout(); tb.setSpacing(7)
        self.search=QLineEdit(); self.search.setPlaceholderText('Cari media, judul, atau tag...'); self.search.setClearButtonEnabled(True); self.search.textChanged.connect(lambda _t:self._debounce.start()); tb.addWidget(self.search,1)
        self.filter=QComboBox(); [self.filter.addItem(label,data) for label,data in (('Filter: Semua','all'),('Siap','ready'),('Missing','missing'),('Favorit','favorite'))]; self.filter.currentIndexChanged.connect(self._controls_changed); tb.addWidget(self.filter)
        self.sort=QComboBox(); [self.sort.addItem(label,data.value) for label,data in (('Urutkan: Terbaru',MediaSort.NEWEST),('Terlama',MediaSort.OLDEST),('Nama A–Z',MediaSort.NAME_ASC),('Nama Z–A',MediaSort.NAME_DESC))]; self.sort.currentIndexChanged.connect(self._controls_changed); tb.addWidget(self.sort)
        self.grid_btn=FAMButton('▦'); self.list_btn=FAMButton('☷'); self.grid_btn.setCheckable(True); self.list_btn.setCheckable(True); self.grid_btn.setChecked(True); self.grid_btn.clicked.connect(lambda:self.set_view_mode(MediaViewMode.GRID)); self.list_btn.clicked.connect(lambda:self.set_view_mode(MediaViewMode.LIST)); tb.addWidget(self.grid_btn); tb.addWidget(self.list_btn)
        self.import_file=FAMButton('Impor File',icon_name='import',kind='primary'); self.import_folder=FAMButton('Impor Folder',icon_name='open'); self.import_file.clicked.connect(self.import_file_requested.emit); self.import_folder.clicked.connect(self.import_folder_requested.emit); tb.addWidget(self.import_file); tb.addWidget(self.import_folder); root.addLayout(tb)
        self.import_banner=QFrame(); self.import_banner.setObjectName('famCard'); ib=QHBoxLayout(self.import_banner); ib.setContentsMargins(10,4,10,4); self.import_status=QLabel(); self.import_status.setObjectName('metadata'); ib.addWidget(self.import_status,1); self.cancel_import=FAMButton('Batal',kind='ghost'); self.cancel_import.clicked.connect(self.cancel_import_requested.emit); ib.addWidget(self.cancel_import); self.import_banner.hide(); root.addWidget(self.import_banner)
        head=QHBoxLayout(); self.heading=QLabel('Semua Media (0)'); self.heading.setObjectName('sectionHeading'); self.heading.setStyleSheet('font-size:16px;font-weight:700;'); head.addWidget(self.heading); head.addStretch(1); self.selection_label=QLabel('0 dipilih'); self.selection_label.setObjectName('metadata'); head.addWidget(self.selection_label); root.addLayout(head)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame); self.card_host=QWidget(); self.grid=QGridLayout(self.card_host); self.grid.setContentsMargins(0,0,0,0); self.grid.setSpacing(8); self.scroll.setWidget(self.card_host); root.addWidget(self.scroll,1)
        self.empty=FAMEmptyState('Belum ada media','Impor file atau folder untuk menambahkan Audio, Foto, dan Video ke proyek.'); root.addWidget(self.empty,1); self.empty.hide()
    def _copy_query(self, **changes):
        data=dict(category=self.query.category,search=self.query.search,status=self.query.status,favorite_only=self.query.favorite_only,collection=self.query.collection,sort=self.query.sort,view_mode=self.query.view_mode); data.update(changes); self.query=MediaQuery(**data)
    def set_index(self,index):
        self.index=index; valid={a.asset_id for a in index.all()}; self.selection.selected_ids[:]=[x for x in self.selection.selected_ids if x in valid]; self.refresh_view()
    def set_category(self,value): self._copy_query(category=value,collection=''); self.refresh_view(); self.query_changed.emit(self.query)
    def set_collection(self,value): self._copy_query(category='all',collection=value); self.refresh_view(); self.query_changed.emit(self.query)
    def set_view_mode(self,value): self._copy_query(view_mode=value); self.grid_btn.setChecked(value==MediaViewMode.GRID); self.list_btn.setChecked(value==MediaViewMode.LIST); self.refresh_view(); self.query_changed.emit(self.query)
    def _apply_search(self): self._copy_query(search=self.search.text()); self.refresh_view(); self.query_changed.emit(self.query)
    def _controls_changed(self):
        value=str(self.filter.currentData() or 'all'); status=MediaStatus.READY if value=='ready' else MediaStatus.MISSING if value=='missing' else None; self._copy_query(status=status,favorite_only=value=='favorite',sort=MediaSort(str(self.sort.currentData()))); self.refresh_view(); self.query_changed.emit(self.query)
    def refresh_view(self):
        self._visible_assets=self.index.project(self.query)
        while self.grid.count():
            w=self.grid.takeAt(0).widget()
            if w: w.deleteLater()
        self._cards=[]; labels={'all':'Semua Media','audio':'Audio','photo':'Foto','video':'Video','favorite':'Favorit','missing':'Missing'}; self.heading.setText(f'{self.query.collection or labels.get(self.query.category,"Media")} ({len(self._visible_assets)})'); self.selection_label.setText(f'{len(self.selection.selected_ids)} dipilih'); self.empty.setVisible(not self._visible_assets); self.scroll.setVisible(bool(self._visible_assets)); cols=1 if self.query.view_mode==MediaViewMode.LIST else self._columns()
        for i,a in enumerate(self._visible_assets):
            c=MediaCard(a,selected=a.asset_id in self.selection.selected_ids,list_mode=self.query.view_mode==MediaViewMode.LIST); c.activated.connect(self._activate); c.checkbox_changed.connect(self._checkbox); c.favorite_requested.connect(self.favorite_requested.emit); c.reveal_requested.connect(self.reveal_requested.emit); c.relink_requested.connect(self.relink_requested.emit); self.grid.addWidget(c,i//cols,i%cols); self._cards.append(c)
        for col in range(cols): self.grid.setColumnStretch(col,1)
    def _columns(self): return max(2,min(5,max(400,self.scroll.viewport().width())//175))
    def _activate(self,asset_id,mods):
        visible=[a.asset_id for a in self._visible_assets]; m=Qt.KeyboardModifier(mods)
        if m&Qt.KeyboardModifier.ShiftModifier: self.selection.select_range(visible,asset_id,additive=bool(m&Qt.KeyboardModifier.ControlModifier))
        elif m&Qt.KeyboardModifier.ControlModifier: self.selection.toggle(asset_id)
        else: self.selection.select_only(asset_id)
        self.refresh_view(); self.selection_changed.emit(tuple(self.selection.selected_ids))
    def _checkbox(self,asset_id,checked):
        if checked!=(asset_id in self.selection.selected_ids): self.selection.toggle(asset_id)
        self.selection_label.setText(f'{len(self.selection.selected_ids)} dipilih'); self.selection_changed.emit(tuple(self.selection.selected_ids))
    def set_import_progress(self,text,*,active): self.import_status.setText(text); self.import_banner.setVisible(active); self.cancel_import.setEnabled(active)
    def resizeEvent(self,e):
        before=self._columns(); super().resizeEvent(e)
        if self.query.view_mode==MediaViewMode.GRID and before!=self._columns(): QTimer.singleShot(0,self.refresh_view)


class MediaInspectorPreview(QLabel):
    """Deterministic visual fallback; a generated/real cached preview still takes priority."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asset = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_asset(self, asset):
        self._asset = asset
        self.clear()
        self.update()

    def paintEvent(self, event):
        pixmap = self.pixmap()
        if pixmap is not None and not pixmap.isNull():
            super().paintEvent(event)
            return
        if self._asset is None:
            super().paintEvent(event)
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.fillRect(r, QColor("#D6E8FF"))
        p.setPen(Qt.PenStyle.NoPen)

        if self._asset.media_type == MediaType.AUDIO:
            p.fillRect(r, QColor("#F4F8FF"))
            p.setPen(QPen(QColor("#66A0FF"), 3))
            middle = r.center().y()
            usable = max(1, r.width() - 36)
            for index in range(44):
                x = r.left() + 18 + int(index * usable / 44)
                height = 8 + ((index * 13 + 9) % max(16, r.height() - 34))
                p.drawLine(x, middle - height // 2, x, middle + height // 2)
        else:
            is_video = self._asset.media_type == MediaType.VIDEO
            sky = QColor("#E99467") if is_video else QColor("#BFE2F8")
            p.fillRect(r, sky)
            p.setPen(Qt.PenStyle.NoPen)

            if is_video:
                # Generic sunset fallback for video preview. It is intentionally
                # synthetic and never sourced from the immutable golden image.
                p.setBrush(QColor("#F5C37B"))
                p.drawRect(r.left(), r.top() + int(r.height() * 0.48), r.width(), int(r.height() * 0.52))
                p.setBrush(QColor("#5D6260"))
                p.drawPolygon(
                    QPolygon([
                        r.bottomLeft(),
                        QPoint(r.left() + int(r.width() * 0.30), r.top() + int(r.height() * 0.65)),
                        QPoint(r.left() + int(r.width() * 0.52), r.top() + int(r.height() * 0.78)),
                        QPoint(r.left() + int(r.width() * 0.72), r.top() + int(r.height() * 0.55)),
                        r.bottomRight(),
                    ])
                )
                # A simple human-like silhouette gives a recognizable "video
                # subject" fallback without reproducing any reference artwork.
                p.setBrush(QColor("#3F3E48"))
                person_x = r.left() + int(r.width() * 0.69)
                p.drawEllipse(QRect(person_x, r.top() + 24, 24, 24))
                p.drawRoundedRect(QRect(person_x - 7, r.top() + 45, 38, 72), 14, 14)
            else:
                p.setBrush(QColor("#7A956F"))
                p.drawPolygon(
                    QPolygon([
                        r.bottomLeft(),
                        r.topLeft() + QPoint(0, int(r.height() * 0.70)),
                        QPoint(int(r.width() * 0.30), int(r.height() * 0.46)),
                        QPoint(int(r.width() * 0.52), int(r.height() * 0.68)),
                        QPoint(int(r.width() * 0.75), int(r.height() * 0.38)),
                        r.bottomRight(),
                    ])
                )

            if is_video:
                p.setBrush(QColor(16, 35, 74, 190))
                center = r.center()
                p.drawEllipse(center, 20, 20)
                p.setPen(QColor("#FFFFFF"))
                font = p.font()
                font.setPointSize(15)
                font.setBold(True)
                p.setFont(font)
                p.drawText(QRect(center.x() - 16, center.y() - 16, 35, 34), Qt.AlignmentFlag.AlignCenter, "▶")

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(TOKENS.border), 1))
        p.drawRoundedRect(r, 8, 8)
        p.end()


class MediaInspectorWidget(QWidget):
    metadata_changed=Signal(str,object,str); favorite_changed=Signal(str,bool); add_to_album_requested=Signal(object); relink_requested=Signal(str); reveal_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self._asset=None; self._selected=(); root=QVBoxLayout(self); root.setContentsMargins(9,8,9,9); root.setSpacing(5)
        self.preview=MediaInspectorPreview(); self.preview.setMinimumHeight(128); self.preview.setMaximumHeight(132); self.preview.setStyleSheet(f'background:{TOKENS.selection_soft};border:1px solid {TOKENS.border};border-radius:8px;'); root.addWidget(self.preview); self.title=QLabel('Belum ada pilihan'); self.title.setObjectName('sectionHeading'); self.title.setStyleSheet('font-size:14px;font-weight:700;'); self.title.setWordWrap(True); root.addWidget(self.title); self.details=QLabel(); self.details.setObjectName('metadata'); self.details.setStyleSheet('font-size:11px;'); self.details.setWordWrap(True); self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); root.addWidget(self.details)
        root.addWidget(QLabel('Tag')); self.tags=QLineEdit(); self.tags.setPlaceholderText('senja, perjalanan, vlog'); root.addWidget(self.tags); root.addWidget(QLabel('Deskripsi')); self.description=QPlainTextEdit(); self.description.setMaximumHeight(74); root.addWidget(self.description); self.save_meta=FAMButton('Simpan Metadata'); self.save_meta.clicked.connect(self._save); root.addWidget(self.save_meta); self.favorite=FAMButton('☆ Tambahkan ke Favorit'); self.favorite.clicked.connect(self._fav); root.addWidget(self.favorite); self.add_album=FAMButton('Tambahkan ke Album',icon_name='open',kind='primary'); self.add_album.clicked.connect(lambda:self.add_to_album_requested.emit(tuple(a.asset_id for a in self._selected))); root.addWidget(self.add_album); row=QHBoxLayout(); self.relink=FAMButton('Relink'); self.reveal=FAMButton('Reveal in Explorer'); self.relink.clicked.connect(lambda:self._asset and self.relink_requested.emit(self._asset.asset_id)); self.reveal.clicked.connect(lambda:self._asset and self.reveal_requested.emit(self._asset.asset_id)); row.addWidget(self.relink); row.addWidget(self.reveal); root.addLayout(row); root.addStretch(1); self.set_selection(())
    def set_selection(self,assets:Iterable[MediaAsset]):
        self._selected=tuple(assets); self._asset=self._selected[0] if len(self._selected)==1 else None
        if not self._selected: self.preview.set_asset(None); self.preview.setText('Belum ada pilihan'); self.title.setText('Belum ada pilihan'); self.details.clear(); self.tags.clear(); self.description.clear(); self._enable(False); return
        if len(self._selected)>1:
            counts={k:sum(a.media_type==k for a in self._selected) for k in MediaType}; self.preview.set_asset(None); self.preview.setText(f'{len(self._selected)} item dipilih'); self.title.setText('Pilihan Banyak'); self.details.setText(f"Video: {counts[MediaType.VIDEO]}\nFoto: {counts[MediaType.PHOTO]}\nAudio: {counts[MediaType.AUDIO]}"); self.tags.clear(); self.description.clear(); self._enable(False); self.add_album.setEnabled(True); return
        a=self._asset; m=a.metadata; self.preview.set_asset(a); self.title.setText(a.display_name); res=f'{m.width} × {m.height}' if m.width and m.height else '—'; fps=f'{m.fps:g} FPS' if m.fps else '—'; created=datetime.fromtimestamp(m.created_at).strftime('%d %b %Y  %H:%M') if m.created_at else '—'; self.details.setText(f'Jenis        {a.media_type.value.title()}\nResolusi     {res}\nDurasi       {_duration(m.duration)}\nFrame Rate   {fps}\nUkuran       {_size(m.size_bytes)}\nWaktu FS     {created}\nLokasi       {_location_text(a.path)}\nFormat       {m.container or Path(a.path).suffix.lstrip(".").upper() or "—"}'); self.tags.setText(', '.join(a.tags)); self.description.setPlainText(a.description); self._enable(True); self.favorite.setText('★ Hapus dari Favorit' if a.favorite else '☆ Tambahkan ke Favorit'); self.relink.setEnabled(a.status==MediaStatus.MISSING); self.reveal.setEnabled(a.status!=MediaStatus.MISSING)
    def _enable(self,value):
        for w in (self.tags,self.description,self.save_meta,self.favorite,self.relink,self.reveal): w.setEnabled(value)
        self.add_album.setEnabled(bool(self._selected))
    def _save(self):
        if self._asset: self.metadata_changed.emit(self._asset.asset_id,[x.strip() for x in self.tags.text().split(',') if x.strip()],self.description.toPlainText().strip())
    def _fav(self):
        if self._asset: self.favorite_changed.emit(self._asset.asset_id,not self._asset.favorite)


class MediaTimelinePreviewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._videos = []
        self._audios = []
        self._texts = []
        self.setMinimumHeight(120)

    def set_project(self, project):
        self._videos = [
            (Path(item.path).stem, max(1.0, float(getattr(item, "duration", 0) or 0)))
            for item in list(getattr(project, "videos", ()))[:8]
        ]
        self._audios = [
            (Path(item.path).stem, max(1.0, float(getattr(item, "duration", 0) or 0)))
            for item in list(getattr(project, "audios", ()))[:8]
        ]
        names = [name for name, _duration_value in self._videos]
        self._texts = []
        if "Cerita Baru" in names:
            self._texts.append(("Cerita Baru", 18.0))
        if "Perjalanan Kita" in names:
            self._texts.append(("Perjalanan Kita", 22.0))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        toolbar_h = 0
        ruler_h = 20
        left = 145

        track_top = toolbar_h + ruler_h
        track_h = max(25, (self.height() - track_top) // 3)
        total = max(
            sum(value for _name, value in self._audios),
            sum(value for _name, value in self._videos),
            90.0,
        )

        p.setPen(QPen(QColor(TOKENS.border), 1))
        tick = 0
        while tick <= int(total):
            x = left + int((self.width() - left) * tick / max(1.0, total))
            p.drawLine(x, toolbar_h, x, self.height())
            p.setPen(QColor(TOKENS.text_muted))
            p.drawText(x + 3, toolbar_h + 14, _duration(tick))
            p.setPen(QPen(QColor(TOKENS.border), 1))
            tick += 10

        for row, label in enumerate(("Video", "Audio", "Teks")):
            y = track_top + row * track_h
            p.fillRect(0, y, left, track_h, QColor("#F8FBFF"))
            p.drawLine(0, y, self.width(), y)
            p.setPen(QColor(TOKENS.text_primary))
            p.drawText(10, y + track_h // 2 + 4, label)
            p.setPen(QPen(QColor(TOKENS.border), 1))

        self._clips(p, self._videos, track_top + 3, track_h - 6, total, QColor("#D8E9FF"), QColor("#1766E8"), waveform=False)
        self._clips(p, self._audios, track_top + track_h + 3, track_h - 6, total, QColor("#BFEBD9"), QColor("#168B68"), waveform=True)
        self._clips(p, self._texts, track_top + track_h * 2 + 3, track_h - 6, total, QColor("#DDCDF8"), QColor("#8055C7"), waveform=False, start_fraction=0.34)
        p.end()

    def _clips(self, p, clips, y, h, total, fill, border, *, waveform=False, start_fraction=0.0):
        x = 145 + int((self.width() - 151) * start_fraction)
        usable = max(1, self.width() - 151)
        for name, duration in clips:
            width = min(max(52, int(usable * duration / total)), max(52, self.width() - x - 4))
            rect = QRect(x, y, width, h)
            p.fillRect(rect, fill)
            p.setPen(QPen(border, 1))
            p.drawRect(rect)
            if waveform and width > 80:
                p.setPen(QPen(QColor("#6EC7AD"), 1))
                middle = rect.center().y()
                for bar_x in range(rect.left() + 8, rect.right() - 8, 7):
                    amp = 3 + ((bar_x * 7) % max(5, h - 7))
                    p.drawLine(bar_x, middle - amp // 2, bar_x, middle + amp // 2)
            p.setPen(QColor(TOKENS.text_primary))
            p.drawText(rect.adjusted(7, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name[:22])
            x += width + 4
            if x >= self.width() - 20:
                break




def _location_text(value: str) -> str:
    text = str(value or "")
    if "\\" in text:
        head, _sep, _tail = text.rpartition("\\")
        return head + "\\" if head else text
    path = Path(text)
    parent = str(path.parent)
    return parent if parent not in {"", "."} else text

def _duration(value):
    if value is None:
        return "—"
    total = max(0, int(round(value)))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _size(value):
    if value is None:
        return "—"
    amount = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "—"


def _meta_text(asset):
    metadata = asset.metadata
    if asset.status == MediaStatus.MISSING:
        return f"{asset.media_type.value.title()} • Tidak ditemukan"
    if asset.media_type == MediaType.AUDIO:
        return f"♫ Audio   {_size(metadata.size_bytes)}"
    if asset.media_type == MediaType.PHOTO:
        return f"▧ Foto   {_size(metadata.size_bytes)}"
    return f"▣ Video   {_size(metadata.size_bytes)}"
