from __future__ import annotations

from pathlib import Path
import threading
import time

import numpy as np
import pytest

import full_album_maker.audio_analysis_backend as backend
import full_album_maker.beat_visual_runtime as runtime_mod
import full_album_maker.preview_service as preview_mod
from full_album_maker.album_visuals import make_vinyl_layer
from full_album_maker.audio_analysis_cache import AudioAnalysisCache
from full_album_maker.audio_analysis_fingerprint import AnalysisCancelled, AnalyzerSettings
from full_album_maker.audio_analysis_service import AudioAnalysisService
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE


class CancelAwareDecoder:
    def __call__(self, source, dest, **kwargs):
        event=kwargs.get("cancel_event")
        while event is not None and not event.is_set():
            time.sleep(.01)
        raise AnalysisCancelled("cancelled in decoder")


def _doc(tmp_path):
    audio_path=tmp_path/"song.raw"; audio_path.write_bytes(b"audio")
    doc=ProjectDocument.new_empty("memo")
    audio=MediaAsset(kind="audio",locator=str(audio_path),original_name="song.raw",source_duration_tick=4*TIMEBASE)
    doc.media.append(audio)
    doc.playlist.entries.append(SongInstance(asset_id=audio.asset_id,source_out_tick=4*TIMEBASE,display_title="Song"))
    vinyl=make_vinyl_layer(doc.tracks[0].track_id,1)
    vinyl.properties["bpm_sync"]=True
    doc.layers.append(vinyl)
    doc.validate()
    return doc,audio,vinyl,audio_path


def test_external_cancel_propagates_and_emits_no_completion(tmp_path):
    src=tmp_path/"song"; src.write_bytes(b"audio")
    asset=MediaAsset(kind="audio",locator=str(src),original_name="song")
    service=AudioAnalysisService(
        cache=AudioAnalysisCache(tmp_path/"cache"),
        decoder=CancelAwareDecoder(),temp_root=tmp_path/"temp",
    )
    results=[]; errors=[]
    service.result_ready.connect(lambda *x:results.append(x))
    service.request_failed.connect(lambda *x:errors.append(x))
    service.request(asset)
    external=threading.Event(); external.set()
    with pytest.raises(AnalysisCancelled):
        service.wait_for_idle(4,cancel_event=external,poll_interval=.01)
    time.sleep(.03)
    assert not results and not errors
    assert not service.busy
    service.close()


def test_backend_cancel_after_beat_track_skips_onset(monkeypatch,tmp_path):
    pcm=tmp_path/"x.f32"
    np.ones(24000,dtype="<f4").tofile(pcm)
    event=threading.Event()
    called={"onset":False}

    def fake_beat_track(**kwargs):
        event.set()
        return np.array([120.0]),np.array([1,5,9])

    def fake_onset_detect(**kwargs):
        called["onset"]=True
        return np.array([1])

    import librosa
    monkeypatch.setattr(librosa.beat,"beat_track",fake_beat_track)
    monkeypatch.setattr(librosa.onset,"onset_detect",fake_onset_detect)
    with pytest.raises(AnalysisCancelled):
        backend.analyze_pcm(pcm,AnalyzerSettings(),cancel_event=event,block_frames=32)
    assert not called["onset"]


def test_ensure_analysis_uses_last_result_without_second_peek(monkeypatch,tmp_path):
    doc,audio,vinyl,path=_doc(tmp_path)
    sentinel=object()
    instances=[]

    class FakeService:
        def __init__(self,**kwargs):
            self.request_failed=type("Sig",(),{"connect":lambda self,cb:None})()
            self.peek_calls=0
            instances.append(self)
        def peek_cached(self,asset):
            self.peek_calls+=1
            return None
        def request(self,asset): return None
        def wait_for_idle(self,*args,**kwargs): return True
        def last_result(self,asset_id): return sentinel
        def cancel(self): return True
        def close(self): pass

    monkeypatch.setattr(runtime_mod,"AudioAnalysisService",FakeService)
    got=runtime_mod.ensure_beat_analysis(doc,cache=AudioAnalysisCache(tmp_path/"cache"))
    assert got[audio.asset_id] is sentinel
    assert instances[0].peek_calls==1


def test_accurate_preview_runtime_memo_reuses_same_document(monkeypatch,tmp_path):
    doc,audio,vinyl,path=_doc(tmp_path)
    built=[]
    dummy=object()
    monkeypatch.setattr(preview_mod,"build_beat_visual_runtime",lambda *a,**k:(built.append(1) or dummy))
    service=preview_mod.AccuratePreviewService(ffmpeg="ffmpeg")
    assert service._runtime_for(doc) is dummy
    assert service._runtime_for(doc) is dummy
    assert len(built)==1
    assert service.runtime_memo_hits==1 and service.runtime_memo_misses==1


def test_preview_runtime_memo_invalidates_on_source_mtime(monkeypatch,tmp_path):
    doc,audio,vinyl,path=_doc(tmp_path)
    built=[]
    monkeypatch.setattr(preview_mod,"build_beat_visual_runtime",lambda *a,**k:(built.append(object()) or built[-1]))
    service=preview_mod.AccuratePreviewService(ffmpeg="ffmpeg")
    first=service._runtime_for(doc)
    stat=path.stat()
    os_time=stat.st_mtime_ns+1_000_000
    import os
    os.utime(path,ns=(stat.st_atime_ns,os_time))
    second=service._runtime_for(doc)
    assert first is not second
    assert len(built)==2


def test_preview_runtime_memo_invalidates_on_document_edit(monkeypatch,tmp_path):
    doc,audio,vinyl,path=_doc(tmp_path)
    built=[]
    monkeypatch.setattr(preview_mod,"build_beat_visual_runtime",lambda *a,**k:(built.append(object()) or built[-1]))
    service=preview_mod.AccuratePreviewService(ffmpeg="ffmpeg")
    first=service._runtime_for(doc)
    vinyl.properties["spin_seconds"]=7.0
    second=service._runtime_for(doc)
    assert first is not second and len(built)==2


def test_preview_runtime_cache_clear_forces_rebuild(monkeypatch,tmp_path):
    doc,audio,vinyl,path=_doc(tmp_path)
    built=[]
    monkeypatch.setattr(preview_mod,"build_beat_visual_runtime",lambda *a,**k:(built.append(object()) or built[-1]))
    service=preview_mod.AccuratePreviewService(ffmpeg="ffmpeg")
    service._runtime_for(doc)
    service.clear_beat_runtime_cache()
    service._runtime_for(doc)
    assert len(built)==2
