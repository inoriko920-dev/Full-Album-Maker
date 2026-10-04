from __future__ import annotations

from pathlib import Path
import subprocess, sys, threading
from typing import Any
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from . import async_import as async_mod, visual_feature as visual_mod
from .media_library_model import MediaAddToAlbumCommand, MediaLibraryIndex, MediaType, stable_asset_id
from .media_library_services import MediaSidecarStore, build_project_assets, canonical_path_key, media_type_for_path, scan_folder
from .media_workspace import MediaContextWidget, MediaInspectorWidget, MediaTimelinePreviewCanvas, MediaWorkspace

_installed=False; _originals:dict[str,Any]={}
class _Bridge(QObject):
    progress=Signal(object); imported=Signal(object); relinked=Signal(object)

def _kind_items(w,kind):
    return w.project.videos if kind==MediaType.VIDEO else w.project.audios if kind==MediaType.AUDIO else visual_mod.images(w.project)
def _existing(w): return {canonical_path_key(a.path) for a in build_project_assets(w.project,visual_mod.images(w.project),None)}

def _init(self,*a,**kw):
    _originals['init'](self,*a,**kw); self._s03_cancel=threading.Event(); self._s03_jobs=0; self._s03_project=self.project; self._s03_store=MediaSidecarStore(self._foundation_project_path or None); self._s03_index=MediaLibraryIndex(); self._s03_bridge=_Bridge(); self._s03_bridge.progress.connect(self._s03_progress); self._s03_bridge.imported.connect(self._s03_imported); self._s03_bridge.relinked.connect(self._s03_relinked)
    self.media_workspace=MediaWorkspace(); idx=self.foundation_shell.workspace_stack._index['media']; old=self.foundation_shell.workspace_stack.widget(idx); self.foundation_shell.workspace_stack.removeWidget(old); old.setParent(None); self.foundation_shell.workspace_stack.insertWidget(idx,self.media_workspace)
    lay=self.foundation_shell.context.layout(); self._s03_context_old=[lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget()]; self.media_context=MediaContextWidget(); self.media_context.hide(); lay.addWidget(self.media_context,1)
    self.media_inspector=MediaInspectorWidget(); self._inspector_router.addWidget(self.media_inspector)
    self._s03_timeline_old=self.foundation_shell.timeline.canvas; self.media_timeline_canvas=MediaTimelinePreviewCanvas(); self._s03_timeline_old.parentWidget().layout().addWidget(self.media_timeline_canvas,1); self.media_timeline_canvas.hide()
    self.media_context.category_requested.connect(self.media_workspace.set_category); self.media_context.collection_requested.connect(self.media_workspace.set_collection); self.media_workspace.selection_changed.connect(self._s03_select); self.media_workspace.import_file_requested.connect(self._s03_files); self.media_workspace.import_folder_requested.connect(self._s03_folder); self.media_workspace.cancel_import_requested.connect(self._s03_cancel_job); self.media_workspace.favorite_requested.connect(self._s03_favorite); self.media_workspace.reveal_requested.connect(self._s03_reveal); self.media_workspace.relink_requested.connect(self._s03_relink); self.media_inspector.metadata_changed.connect(self._s03_metadata); self.media_inspector.favorite_changed.connect(self._s03_favorite); self.media_inspector.add_to_album_requested.connect(self._s03_album); self.media_inspector.relink_requested.connect(self._s03_relink); self.media_inspector.reveal_requested.connect(self._s03_reveal); self.foundation_state.workspace_changed.connect(self._s03_route)
    self._s03_refresh(True); self._s03_route(self.foundation_state.workspace); self._sync_foundation_state()

def _home_route(self,route):
    _originals['home_route'](self,route)
    if hasattr(self,'media_inspector') and route=='media': self._inspector_router.setCurrentWidget(self.media_inspector)
def _adopt(self,project,result,*,route='media',add_recent=True):
    _originals['adopt'](self,project,result,route=route,add_recent=add_recent)
    if hasattr(self,'media_workspace'): self._s03_refresh(True)
def _refresh(self,*a,**kw):
    result=_originals['refresh'](self,*a,**kw)
    if hasattr(self,'media_workspace'): self._s03_refresh(False)
    return result
def _sync(self):
    _originals['sync'](self)
    if hasattr(self,'foundation_state'):
        n=int(bool(getattr(self,'render_busy',False)))+int(getattr(self,'_import_job_count',0) or 0)+int(getattr(self,'_s03_jobs',0) or 0); self.foundation_state.set_status(jobs=(f'Jobs: {n}','warning' if n else 'neutral'))

def _route(self,route):
    active=route=='media'; self.media_context.setVisible(active); [w.setVisible(not active) for w in self._s03_context_old]; self.media_timeline_canvas.setVisible(active); self._s03_timeline_old.setVisible(not active)
    if active: self._s03_refresh(False); self._inspector_router.setCurrentWidget(self.media_inspector)
    elif route!='home': self._inspector_router.setCurrentIndex(1)
def _refresh_media(self,reset=False):
    path=Path(self._foundation_project_path) if self._foundation_project_path else None
    if reset or self._s03_project is not self.project or self._s03_store.project_path!=path:
        self._s03_project=self.project; self._s03_store=MediaSidecarStore(self._foundation_project_path or None); self._s03_store.load()
    self._s03_index.replace_all(build_project_assets(self.project,visual_mod.images(self.project),self._s03_store)); self.media_workspace.set_index(self._s03_index); self.media_context.set_counts(self._s03_index.counts()); cc={}
    for asset in self._s03_index.all():
        for name in asset.collections: cc[name]=cc.get(name,0)+1
    self.media_context.set_collection_counts(cc); self.media_timeline_canvas.set_project(self.project); enabled=bool(self._foundation_project_open) and not self._s03_jobs; self.media_workspace.import_file.setEnabled(enabled); self.media_workspace.import_folder.setEnabled(enabled); self._s03_select(tuple(self.media_workspace.selection.selected_ids))
def _select(self,ids): self.media_inspector.set_selection(tuple(a for x in tuple(ids or ()) if (a:=self._s03_index.get(str(x))) is not None))

def _files(self):
    if not self._foundation_project_open or self._s03_jobs:return
    paths,_=QFileDialog.getOpenFileNames(self,'Impor Media','','Media (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.jpg *.jpeg *.png *.webp *.mp4 *.mov *.mkv *.webm *.avi *.m4v *.wmv);;Semua file (*)')
    if paths:self._s03_start_import(list(paths),False)
def _folder(self):
    if not self._foundation_project_open or self._s03_jobs:return
    path=QFileDialog.getExistingDirectory(self,'Impor Folder Media','')
    if path:self._s03_start_import([path],True)
def _start_import(self,entries,folder):
    self._s03_cancel=threading.Event(); self._s03_jobs+=1; project=self.project; existing=_existing(self); self.media_workspace.set_import_progress('Menyiapkan impor…',active=True); self._sync_foundation_state()
    def work():
        paths=[]
        if folder:
            for i,p in enumerate(scan_folder(entries[0],self._s03_cancel),1):
                paths.append(str(p))
                if i==1 or i%20==0:self._s03_bridge.progress.emit({'project':project,'text':f'Memindai folder… {i} media'})
        else: paths=list(entries)
        accepted=[]; errors=[]; seen=set(existing); total=len(paths)
        for i,path in enumerate(paths,1):
            if self._s03_cancel.is_set():break
            kind=media_type_for_path(path)
            if kind is None:errors.append(f'Format belum didukung: {Path(path).name}');continue
            key=canonical_path_key(path)
            if key in seen:continue
            seen.add(key); self._s03_bridge.progress.emit({'project':project,'text':f'Membaca {i}/{total}: {Path(path).name}'})
            try:accepted.append((kind.value,async_mod._probe_one('image' if kind==MediaType.PHOTO else kind.value,path)))
            except Exception as exc:errors.append(f'{Path(path).name}: {exc}')
        self._s03_bridge.imported.emit({'project':project,'accepted':accepted,'errors':errors,'canceled':self._s03_cancel.is_set()})
    threading.Thread(target=work,daemon=True,name='fam-step03-import').start()
def _progress(self,p):
    if p.get('project') is self.project:self.media_workspace.set_import_progress(str(p.get('text','Memproses…')),active=True)
def _imported(self,p):
    self._s03_jobs=max(0,self._s03_jobs-1); self.media_workspace.set_import_progress('',active=False)
    if p.get('project') is not self.project:self.log.appendPlainText('Hasil impor Media diabaikan karena proyek aktif berganti.');self._sync_foundation_state();return
    accepted=list(p.get('accepted',())); videos=[x for k,x in accepted if k=='video']; audios=[x for k,x in accepted if k=='audio']; photos=[x for k,x in accepted if k=='photo']; self.project.videos.extend(videos); self.project.audios.extend(audios); visual_mod.images(self.project).extend(photos)
    if videos or photos:
        order=getattr(self.project,'_visual_order',None)
        if not isinstance(order,list):order=[];setattr(self.project,'_visual_order',order)
        known={canonical_path_key(x) for x in order}
        for item in [*videos,*photos]:
            if canonical_path_key(item.path) not in known:order.append(item.path);known.add(canonical_path_key(item.path))
    if accepted:self.invalidate_timeline();self.log.appendPlainText(f'Impor Media selesai: {len(accepted)} file ditambahkan.')
    errors=[str(x) for x in p.get('errors',())]
    if errors:self.log.appendPlainText(f'{len(errors)} media gagal/ditolak:\n'+'\n'.join('• '+x for x in errors[:8]))
    if p.get('canceled'):self.log.appendPlainText('Impor Media dibatalkan; hasil yang selesai sebelum pembatalan dipertahankan.')
    self.refresh(); self._s03_refresh(False); self._sync_foundation_state()
def _cancel(self): self._s03_cancel.set(); self.media_workspace.set_import_progress('Membatalkan setelah probe aktif selesai…',active=True)

def _favorite(self,asset_id,value):
    if not self._s03_index.get(asset_id):return
    try:self._s03_store.update(asset_id,favorite=value,persist=bool(self._foundation_project_path))
    except OSError as exc:QMessageBox.warning(self,'Metadata Media',f'Favorit tidak dapat disimpan:\n{exc}');return
    self._s03_refresh(False)
def _metadata(self,asset_id,tags,description):
    if not self._s03_index.get(asset_id):return
    try:self._s03_store.update(asset_id,tags=tags,description=description,persist=bool(self._foundation_project_path))
    except OSError as exc:QMessageBox.warning(self,'Metadata Media',f'Metadata tidak dapat disimpan:\n{exc}');return
    self._s03_refresh(False)
def _reveal(self,asset_id):
    a=self._s03_index.get(asset_id)
    if not a or not Path(a.path).exists():return
    target=Path(a.path).resolve(strict=False)
    try:
        if sys.platform.startswith('win'):subprocess.Popen(['explorer','/select,',str(target)])
        elif sys.platform=='darwin':subprocess.Popen(['open','-R',str(target)])
        else:subprocess.Popen(['xdg-open',str(target.parent)])
    except OSError as exc:QMessageBox.warning(self,'Reveal Media',f'Lokasi tidak dapat dibuka:\n{exc}')
def _relink(self,asset_id):
    a=self._s03_index.get(asset_id)
    if not a:return
    filt={MediaType.VIDEO:'Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.wmv)',MediaType.AUDIO:'Audio (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus)',MediaType.PHOTO:'Foto (*.jpg *.jpeg *.png *.webp)'}[a.media_type]; path,_=QFileDialog.getOpenFileName(self,f'Relink {a.display_name}',str(Path(a.path).parent),filt)
    if not path:return
    if media_type_for_path(path)!=a.media_type:QMessageBox.warning(self,'Relink Media','Jenis media pengganti harus sama.');return
    project=self.project
    def work():
        try:item=async_mod._probe_one('image' if a.media_type==MediaType.PHOTO else a.media_type.value,path);err=''
        except Exception as exc:item=None;err=str(exc)
        self._s03_bridge.relinked.emit({'project':project,'asset_id':asset_id,'old':a.path,'new':path,'kind':a.media_type.value,'item':item,'error':err})
    threading.Thread(target=work,daemon=True,name='fam-step03-relink').start()
def _relinked(self,p):
    if p.get('project') is not self.project:return
    if p.get('error'):QMessageBox.warning(self,'Relink Media',f"Media pengganti tidak valid:\n{p['error']}");return
    kind=MediaType(p['kind']); target=next((x for x in _kind_items(self,kind) if canonical_path_key(x.path)==canonical_path_key(p['old'])),None)
    if target is None:return
    target.path=p['new']; probed=p['item']
    if getattr(self,'timeline_plan',None) is None:target.duration=getattr(probed,'duration',target.duration)
    elif float(getattr(probed,'duration',target.duration) or 0)!=float(getattr(target,'duration',0) or 0):self.log.appendPlainText('Relink selesai; durasi timeline tidak diubah otomatis. Review/rebuild timeline bila diperlukan.')
    for name in ('width','height','fps','container','codec'):
        if hasattr(probed,name):setattr(target,name,getattr(probed,name))
    order=getattr(self.project,'_visual_order',None)
    if isinstance(order,list):
        for i,value in enumerate(order):
            if canonical_path_key(value)==canonical_path_key(p['old']):order[i]=p['new']
    try:self._s03_store.migrate_asset_id(p['asset_id'],stable_asset_id(p['new'],kind),persist=bool(self._foundation_project_path))
    except OSError:pass
    self.refresh();self._s03_refresh(False)
def _album(self,ids):
    cmd=MediaAddToAlbumCommand(tuple(str(x) for x in ids))
    try:cmd.validate()
    except ValueError:return
    self._step03_album_handoff=cmd; self.log.appendPlainText(f'{len(cmd.asset_ids)} media disiapkan untuk handoff Album; STEP 04 mengelola assignment final.'); self.foundation_shell.set_workspace('album')

def install_step03_media():
    global _installed
    if _installed:return
    from .foundation_window import FoundationMainWindow as W
    _originals.update(init=W.__init__,refresh=W.refresh,sync=W._sync_foundation_state,home_route=W._home_workspace_changed,adopt=W._adopt_home_project); W.__init__=_init; W.refresh=_refresh; W._sync_foundation_state=_sync; W._home_workspace_changed=_home_route; W._adopt_home_project=_adopt
    for name,fn in {'_s03_route':_route,'_s03_refresh':_refresh_media,'_s03_select':_select,'_s03_files':_files,'_s03_folder':_folder,'_s03_start_import':_start_import,'_s03_progress':_progress,'_s03_imported':_imported,'_s03_cancel_job':_cancel,'_s03_favorite':_favorite,'_s03_metadata':_metadata,'_s03_reveal':_reveal,'_s03_relink':_relink,'_s03_relinked':_relinked,'_s03_album':_album}.items():setattr(W,name,fn)
    _installed=True
