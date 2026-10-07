from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

import numpy as np
import pytest

from full_album_maker.audio_analysis_backend import BackendOutput
from full_album_maker.audio_analysis_cache import AudioAnalysisCache
from full_album_maker.audio_analysis_contract import (
    ANALYZER_VERSION, AnalysisCurve, AnalysisEvent, AnalysisEventType,
    AnalysisQuality, AudioAnalysisResult, HOP_LENGTH, SAMPLE_RATE,
    TICKS_PER_FRAME, TempoSummary,
)
from full_album_maker.audio_analysis_fingerprint import (
    AnalysisCancelled, AnalyzerSettings, cache_key,
)
from full_album_maker.audio_analysis_service import AudioAnalysisService
from full_album_maker.editor_models import MediaAsset


def _asset(path: Path):
    return MediaAsset(asset_id=str(uuid4()),kind="audio",locator=str(path),original_name=path.name)


def _result(asset, digest=None):
    digest=digest or hashlib.sha256(Path(asset.locator).read_bytes()).hexdigest()
    curves=tuple(AnalysisCurve(name,(0.0,.2,.8,.1)) for name in ("energy","bass","mid","high","onset"))
    tempo=TempoSummary(120.0,.9,AnalysisQuality.HIGH,.02)
    return AudioAnalysisResult(
        asset.asset_id,digest,AnalyzerSettings().signature(),ANALYZER_VERSION,
        4*TICKS_PER_FRAME,SAMPLE_RATE,HOP_LENGTH,tempo,(),
        (AnalysisEvent(TICKS_PER_FRAME,AnalysisEventType.BEAT,.8,.9),),
        (AnalysisEvent(TICKS_PER_FRAME,AnalysisEventType.ONSET,.8,.8),),
        curves,asset.original_name,
    )


class Decoder:
    def __init__(self): self.calls=0
    def __call__(self, source, dest, **kwargs):
        self.calls+=1
        np.ones(4096,dtype="<f4").tofile(dest)
        return Path(dest)


class Analyzer:
    def __init__(self): self.calls=0
    def __call__(self,*args,**kwargs):
        self.calls+=1
        arr=np.array([0,.2,.9,.1,.2,1,.1,.3],dtype=np.float32)
        return BackendOutput(
            8*TICKS_PER_FRAME,120.0,(2,5,7),(2,5),.03,
            {name:arr.copy() for name in ("energy","bass","mid","high","onset")},
            .2,.5,.15,1.0,
        )


def test_cache_maintenance_preserves_valid_entry(tmp_path):
    src=tmp_path/"song"; src.write_bytes(b"audio")
    a=_asset(src); result=_result(a)
    cache=AudioAnalysisCache(tmp_path/"cache")
    key=cache_key(result.content_sha256,result.settings_signature)
    cache.publish(key,result)
    report=cache.maintenance(stale_partial_seconds=0)
    assert report.removed_partial_entries==0
    loaded=cache.load(key)
    assert loaded is not None
    assert loaded.asset_id==result.asset_id
    assert loaded.content_sha256==result.content_sha256
    assert loaded.tempo==result.tempo
    for got,expected in zip(loaded.curves,result.curves):
        assert got.name==expected.name
        assert got.start_tick==expected.start_tick
        assert got.tick_step==expected.tick_step
        assert np.asarray(got.values)==pytest.approx(np.asarray(expected.values),abs=1e-6)


def test_cache_maintenance_removes_stale_partial_and_temp(tmp_path):
    cache=AudioAnalysisCache(tmp_path/"cache")
    partial=cache.root/("a"*64); partial.mkdir()
    temp=partial/".curves.old.npz.tmp"; temp.write_bytes(b"x"*50)
    old=time.time()-7200
    os.utime(partial,(old,old)); os.utime(temp,(old,old))
    report=cache.maintenance(stale_partial_seconds=3600)
    assert report.removed_partial_entries==1
    assert report.reclaimed_bytes>=50
    assert not partial.exists()


def test_cache_quarantine_count_is_bounded(tmp_path):
    cache=AudioAnalysisCache(tmp_path/"cache")
    cache.quarantine_root.mkdir(parents=True)
    for i in range(7):
        item=cache.quarantine_root/f"item-{i}"
        item.mkdir(); (item/"x").write_bytes(b"x"*10)
        old=time.time()-(100-i)
        os.utime(item,(old,old))
    report=cache.maintenance(max_quarantine_entries=3,max_quarantine_bytes=10_000)
    remaining=[p for p in cache.quarantine_root.iterdir() if p.is_dir()]
    assert len(remaining)==3
    assert report.removed_quarantine_entries==4


def test_cache_quarantine_bytes_are_bounded(tmp_path):
    cache=AudioAnalysisCache(tmp_path/"cache")
    cache.quarantine_root.mkdir(parents=True)
    for i in range(4):
        item=cache.quarantine_root/f"item-{i}"
        item.mkdir(); (item/"x").write_bytes(b"x"*100)
    report=cache.maintenance(max_quarantine_entries=10,max_quarantine_bytes=150)
    total=sum(p.stat().st_size for d in cache.quarantine_root.iterdir() for p in d.iterdir())
    assert total<=150
    assert report.removed_quarantine_entries>=3


def test_publish_cancelled_before_commit_creates_no_manifest(tmp_path):
    src=tmp_path/"song"; src.write_bytes(b"audio")
    a=_asset(src); result=_result(a)
    cache=AudioAnalysisCache(tmp_path/"cache")
    key=cache_key(result.content_sha256,result.settings_signature)
    event=threading.Event(); event.set()
    with pytest.raises(AnalysisCancelled):
        cache.publish(key,result,cancel_event=event)
    assert not (cache.entry_dir(key)/"manifest.json").exists()


def test_corrupt_cache_is_reanalyzed_and_replaced(tmp_path):
    src=tmp_path/"song"; src.write_bytes(b"audio")
    a=_asset(src)
    cache=AudioAnalysisCache(tmp_path/"cache")
    old=_result(a)
    key=cache_key(old.content_sha256,old.settings_signature)
    folder=cache.publish(key,old)
    (folder/"curves.npz").write_bytes(b"corrupt")

    decoder=Decoder(); analyzer=Analyzer()
    service=AudioAnalysisService(cache=cache,decoder=decoder,analyzer=analyzer,temp_root=tmp_path/"temp")
    results=[]; errors=[]
    service.result_ready.connect(lambda _t,r:results.append(r))
    service.request_failed.connect(lambda _t,e:errors.append(e))
    service.request(a)
    assert service.wait_for_idle(4)
    time.sleep(.03)
    assert not errors and results
    assert decoder.calls==1 and analyzer.calls==1
    repaired=cache.load(key)
    assert repaired is not None
    assert list(cache.quarantine_root.iterdir())
    service.close()


def test_last_result_and_invalidate(tmp_path):
    src=tmp_path/"song"; src.write_bytes(b"audio")
    a=_asset(src)
    service=AudioAnalysisService(
        cache=AudioAnalysisCache(tmp_path/"cache"),
        decoder=Decoder(),analyzer=Analyzer(),temp_root=tmp_path/"temp",
    )
    service.request(a); assert service.wait_for_idle(4); time.sleep(.03)
    assert service.last_result(a.asset_id) is not None
    service.invalidate(a)
    assert service.last_result(a.asset_id) is None
    service.close()
