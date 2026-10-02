from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
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
    category_requested = Signal(str); collection_requested = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self._category_buttons={}; self._collection_buttons={}
        root=QVBoxLayout(self); root.setContentsMargins(8,8,8,8); root.setSpacing(3)
        head=QHBoxLayout(); title=QLabel('Media'); title.setObjectName('sectionHeading'); title.setStyleSheet('font-size:16px;font-weight:700;'); head.addWidget(title); head.addStretch(1)
        add=FAMButton('+',kind='ghost'); add.setFixedWidth(32); add.setEnabled(False); add.setToolTip('Koleksi baru — STEP 04'); head.addWidget(add); root.addLayout(head)
        for key,label,glyph in CATEGORIES:
            b=QPushButton(); b.setObjectName('navButton'); b.setCheckable(True); b.setAutoExclusive(True); b.clicked.connect(lambda _=False,k=key:self._category(k)); self._category_buttons[key]=b; root.addWidget(b)
        self._category_buttons['all'].setChecked(True)
        line=QFrame(); line.setFrameShape(QFrame.Shape.HLine); root.addWidget(line); h=QLabel('Folder Proyek'); h.setObjectName('sectionHeading'); root.addWidget(h)
        for name in COLLECTIONS:
            b=QPushButton(); b.setObjectName('navButton'); b.setCheckable(True); b.clicked.connect(lambda _=False,n=name:self._collection(n)); self._collection_buttons[name]=b; root.addWidget(b)
        root.addStretch(1); self.set_counts({}); self.set_collection_counts({})
    def set_counts(self, counts):
        for key,label,glyph in CATEGORIES:
            n=int(counts.get(key,0)); b=self._category_buttons[key]; b.setText(f'{glyph}  {label}                         {n}'); b.setAccessibleName(f'{label}, {n} item')
    def set_collection_counts(self, counts):
        for name,b in self._collection_buttons.items():
            n=int(counts.get(name,0)); b.setText(f'▢  {name}                    {n}'); b.setAccessibleName(f'{name}, {n} item')
    def _category(self,key):
        for b in self._collection_buttons.values(): b.setChecked(False)
        self.category_requested.emit(key)
    def _collection(self,name):
        for b in self._category_buttons.values(): b.setChecked(False)
        for key,b in self._collection_buttons.items(): b.setChecked(key==name)
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
    activated=Signal(str,int); checkbox_changed=Signal(str,bool); favorite_requested=Signal(str,bool); reveal_requested=Signal(str); relink_requested=Signal(str)
    def __init__(self, asset, *, selected=False, list_mode=False, parent=None):
        super().__init__(parent); self.asset=asset; self.setObjectName('famCard'); self.setProperty('selected',selected); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.setCursor(Qt.CursorShape.PointingHandCursor); self.setToolTip(asset.path); self.setAccessibleName(f'{asset.display_name}, {asset.media_type.value}')
        root=QVBoxLayout(self); root.setContentsMargins(7,7,7,7); root.setSpacing(4); top=QHBoxLayout(); self.check=QCheckBox(); self.check.setChecked(selected); self.check.toggled.connect(lambda v:self.checkbox_changed.emit(asset.asset_id,v)); top.addWidget(self.check); top.addStretch(1)
        more=FAMButton('⋯',kind='ghost'); more.setFixedSize(28,26); menu=QMenu(more); menu.addAction('Hapus dari Favorit' if asset.favorite else 'Tambahkan ke Favorit',lambda:self.favorite_requested.emit(asset.asset_id,not asset.favorite)); menu.addAction('Relink…',lambda:self.relink_requested.emit(asset.asset_id)); menu.addAction('Reveal in Explorer',lambda:self.reveal_requested.emit(asset.asset_id)); more.setMenu(menu); top.addWidget(more); root.addLayout(top)
        preview=MediaPreviewPlaceholder(asset); preview.setFixedHeight(46 if list_mode else 92); root.addWidget(preview); title=QLabel(asset.display_name); title.setObjectName('sectionHeading'); title.setToolTip(asset.path); root.addWidget(title); meta=QLabel(_meta_text(asset)); meta.setObjectName('metadata'); root.addWidget(meta); self.setMinimumWidth(145); self.setMaximumHeight(122 if list_mode else 180)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.activated.emit(self.asset.asset_id,int(e.modifiers().value)); e.accept(); return
        super().mousePressEvent(e)
    def keyPressEvent(self,e):
        if e.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Space): self.activated.emit(self.asset.asset_id,int(e.modifiers().value)); e.accept(); return
        super().keyPressEvent(e)


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


class MediaInspectorWidget(QWidget):
    metadata_changed=Signal(str,object,str); favorite_changed=Signal(str,bool); add_to_album_requested=Signal(object); relink_requested=Signal(str); reveal_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self._asset=None; self._selected=(); root=QVBoxLayout(self); root.setContentsMargins(12,10,12,12); root.setSpacing(8)
        self.preview=QLabel('Belum ada pilihan'); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setMinimumHeight(116); self.preview.setStyleSheet(f'background:{TOKENS.selection_soft};border:1px solid {TOKENS.border};border-radius:8px;'); root.addWidget(self.preview); self.title=QLabel('Belum ada pilihan'); self.title.setObjectName('sectionHeading'); self.title.setWordWrap(True); root.addWidget(self.title); self.details=QLabel(); self.details.setObjectName('metadata'); self.details.setWordWrap(True); self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); root.addWidget(self.details)
        root.addWidget(QLabel('Tag')); self.tags=QLineEdit(); self.tags.setPlaceholderText('senja, perjalanan, vlog'); root.addWidget(self.tags); root.addWidget(QLabel('Deskripsi')); self.description=QPlainTextEdit(); self.description.setMaximumHeight(74); root.addWidget(self.description); self.save_meta=FAMButton('Simpan Metadata'); self.save_meta.clicked.connect(self._save); root.addWidget(self.save_meta); self.favorite=FAMButton('☆ Tambahkan ke Favorit'); self.favorite.clicked.connect(self._fav); root.addWidget(self.favorite); self.add_album=FAMButton('Tambahkan ke Album',icon_name='open',kind='primary'); self.add_album.clicked.connect(lambda:self.add_to_album_requested.emit(tuple(a.asset_id for a in self._selected))); root.addWidget(self.add_album); row=QHBoxLayout(); self.relink=FAMButton('Relink'); self.reveal=FAMButton('Reveal in Explorer'); self.relink.clicked.connect(lambda:self._asset and self.relink_requested.emit(self._asset.asset_id)); self.reveal.clicked.connect(lambda:self._asset and self.reveal_requested.emit(self._asset.asset_id)); row.addWidget(self.relink); row.addWidget(self.reveal); root.addLayout(row); root.addStretch(1); self.set_selection(())
    def set_selection(self,assets:Iterable[MediaAsset]):
        self._selected=tuple(assets); self._asset=self._selected[0] if len(self._selected)==1 else None
        if not self._selected: self.preview.setText('Belum ada pilihan'); self.title.setText('Belum ada pilihan'); self.details.clear(); self.tags.clear(); self.description.clear(); self._enable(False); return
        if len(self._selected)>1:
            counts={k:sum(a.media_type==k for a in self._selected) for k in MediaType}; self.preview.setText(f'{len(self._selected)} item dipilih'); self.title.setText('Pilihan Banyak'); self.details.setText(f"Video: {counts[MediaType.VIDEO]}\nFoto: {counts[MediaType.PHOTO]}\nAudio: {counts[MediaType.AUDIO]}"); self.tags.clear(); self.description.clear(); self._enable(False); self.add_album.setEnabled(True); return
        a=self._asset; m=a.metadata; self.preview.setText({'audio':'♫ AUDIO','photo':'▧ FOTO','video':'▶ VIDEO'}[a.media_type.value]); self.title.setText(a.display_name); res=f'{m.width} × {m.height}' if m.width and m.height else '—'; fps=f'{m.fps:g} FPS' if m.fps else '—'; created=datetime.fromtimestamp(m.created_at).strftime('%d %b %Y  %H:%M') if m.created_at else '—'; self.details.setText(f'Jenis        {a.media_type.value.title()}\nResolusi     {res}\nDurasi       {_duration(m.duration)}\nFrame Rate   {fps}\nUkuran       {_size(m.size_bytes)}\nWaktu FS     {created}\nLokasi       {a.path}\nFormat       {m.container or Path(a.path).suffix.lstrip(".").upper() or "—"}'); self.tags.setText(', '.join(a.tags)); self.description.setPlainText(a.description); self._enable(True); self.favorite.setText('★ Hapus dari Favorit' if a.favorite else '☆ Tambahkan ke Favorit'); self.relink.setEnabled(a.status==MediaStatus.MISSING); self.reveal.setEnabled(a.status!=MediaStatus.MISSING)
    def _enable(self,value):
        for w in (self.tags,self.description,self.save_meta,self.favorite,self.relink,self.reveal): w.setEnabled(value)
        self.add_album.setEnabled(bool(self._selected))
    def _save(self):
        if self._asset: self.metadata_changed.emit(self._asset.asset_id,[x.strip() for x in self.tags.text().split(',') if x.strip()],self.description.toPlainText().strip())
    def _fav(self):
        if self._asset: self.favorite_changed.emit(self._asset.asset_id,not self._asset.favorite)


class MediaTimelinePreviewCanvas(QWidget):
    def __init__(self,parent=None): super().__init__(parent); self._videos=[]; self._audios=[]; self.setMinimumHeight(82)
    def set_project(self,project): self._videos=[(Path(x.path).stem,max(1.0,float(getattr(x,'duration',0) or 0))) for x in list(getattr(project,'videos',()))[:8]]; self._audios=[(Path(x.path).stem,max(1.0,float(getattr(x,'duration',0) or 0))) for x in list(getattr(project,'audios',()))[:8]]; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#FFFFFF')); left=66; ruler=20; h=max(24,(self.height()-ruler)//3); total=max(sum(x[1] for x in self._audios),sum(x[1] for x in self._videos),90.0); p.setPen(QPen(QColor(TOKENS.border),1))
        for i in range(7):
            x=left+int((self.width()-left)*i/6); p.drawLine(x,0,x,self.height()); p.setPen(QColor(TOKENS.text_muted)); p.drawText(x+3,13,_duration(total*i/6)); p.setPen(QPen(QColor(TOKENS.border),1))
        for row,label in enumerate(('Video','Audio','Teks')):
            y=ruler+row*h; p.fillRect(0,y,left,h,QColor('#F8FBFF')); p.drawLine(0,y,self.width(),y); p.setPen(QColor(TOKENS.text_primary)); p.drawText(9,y+h//2+4,label); p.setPen(QPen(QColor(TOKENS.border),1))
        self._clips(p,self._videos,ruler+3,h-6,total,QColor('#D8E9FF'),QColor('#1766E8')); self._clips(p,self._audios,ruler+h+3,h-6,total,QColor('#CFF3E5'),QColor('#168B68')); p.end()
    def _clips(self,p,clips,y,h,total,fill,border):
        x=66; usable=max(1,self.width()-70)
        for name,d in clips:
            w=min(max(45,int(usable*d/total)),max(45,self.width()-x-4)); r=QRect(x,y,w,h); p.fillRect(r,fill); p.setPen(QPen(border,1)); p.drawRect(r); p.setPen(QColor(TOKENS.text_primary)); p.drawText(r.adjusted(6,0,-4,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,name[:22]); x+=w+4
            if x>=self.width()-20: break


def _duration(v):
    if v is None:return '—'
    total=max(0,int(round(v))); m,s=divmod(total,60); h,m=divmod(m,60); return f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'
def _size(v):
    if v is None:return '—'
    n=float(max(0,v))
    for u in ('B','KB','MB','GB','TB'):
        if n<1024 or u=='TB':return f'{n:.0f} {u}' if u=='B' else f'{n:.1f} {u}'
        n/=1024
    return '—'
def _meta_text(a):
    m=a.metadata
    if a.status==MediaStatus.MISSING:return f'{a.media_type.value.title()} • Tidak ditemukan'
    if a.media_type==MediaType.AUDIO:return f'♫ Audio • {_duration(m.duration)} • {_size(m.size_bytes)}'
    if a.media_type==MediaType.PHOTO:return f'▧ Foto • {f"{m.width}×{m.height}" if m.width and m.height else "Resolusi —"} • {_size(m.size_bytes)}'
    return f'▣ Video • {_duration(m.duration)} • {f"{m.width}×{m.height}" if m.width and m.height else "Resolusi —"} • {f"{m.fps:g} FPS" if m.fps else "FPS —"}'
