from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

import numpy as np
import pytest

from full_album_maker.audio_analysis_backend import BackendOutput, analyze_pcm
from full_album_maker.audio_analysis_cache import AudioAnalysisCache
from full_album_maker.audio_analysis_contract import (
    ANALYZER_VERSION, AnalysisCurve, AnalysisEvent, AnalysisEventType, AnalysisQuality,
    AudioAnalysisResult, HOP_LENGTH, SAMPLE_RATE, TICKS_PER_FRAME, TICKS_PER_SAMPLE, TempoSummary,
)
from full_album_maker.audio_analysis_fingerprint import AnalysisCancelled, AnalyzerSettings, cache_key, hash_source
from full_album_maker.audio_analysis_quality import QualityDiagnostics, evaluate_quality
from full_album_maker.audio_analysis_service import AudioAnalysisService
from full_album_maker.editor_models import MediaAsset, TIMEBASE


def asset(path: Path, *, asset_id: str | None = None) -> MediaAsset:
    return MediaAsset(asset_id=asset_id or str(uuid4()), kind='audio', locator=str(path), original_name=path.name)


def result_for(a: MediaAsset, digest: str | None = None, quality=AnalysisQuality.HIGH) -> AudioAnalysisResult:
    digest = digest or hashlib.sha256(Path(a.locator).read_bytes()).hexdigest()
    curves = tuple(AnalysisCurve(n, (0.0, .5, 1.0, .25)) for n in ('energy','bass','mid','high','onset'))
    tempo = TempoSummary(120.0 if quality != AnalysisQuality.SILENT else 0.0, .9 if quality==AnalysisQuality.HIGH else .2, quality, .02)
    beats = () if quality in {AnalysisQuality.LOW, AnalysisQuality.SILENT} else (AnalysisEvent(TICKS_PER_FRAME, AnalysisEventType.BEAT, .8, tempo.confidence),)
    return AudioAnalysisResult(a.asset_id,digest,AnalyzerSettings().signature(),ANALYZER_VERSION,4*TICKS_PER_FRAME,SAMPLE_RATE,HOP_LENGTH,tempo,(),beats,(AnalysisEvent(TICKS_PER_FRAME,AnalysisEventType.ONSET,.8,.8),),curves,a.original_name)


def fake_output(*, quality='high'):
    frames=8
    if quality=='silent':
        arr=np.zeros(frames,dtype=np.float32); bpm=0.; beats=(); rms=.0; peak=.0; onsetmean=.0; onsetpeak=.0; cv=1.
    elif quality=='low':
        arr=np.full(frames,.2,dtype=np.float32); bpm=121.; beats=(1,5); rms=.1; peak=.2; onsetmean=.18; onsetpeak=.2; cv=.5
    else:
        arr=np.array([0,.2,.9,.1,.2,1,.1,.3],dtype=np.float32); bpm=120.; beats=(2,5,7); rms=.2; peak=.5; onsetmean=.15; onsetpeak=1.; cv=.03
    return BackendOutput(frames*TICKS_PER_FRAME,bpm,beats,(2,5),cv,{n:arr.copy() for n in ('energy','bass','mid','high','onset')},rms,peak,onsetmean,onsetpeak)


def write_pcm(path: Path, samples: np.ndarray):
    np.asarray(samples,dtype='<f4').tofile(path)


def clicks(bpm: float, seconds=14.0):
    n=int(SAMPLE_RATE*seconds); y=np.zeros(n,dtype=np.float32); step=60*SAMPLE_RATE/bpm
    for k in range(int(seconds*bpm/60)+1):
        s=int(round(k*step));
        if s>=n: break
        end=min(n,s+180); y[s:end]+=np.hanning((end-s)*2)[:end-s].astype(np.float32)
    return y


def octave_error(got, expected):
    return min(abs(got-expected),abs(got-expected/2),abs(got-expected*2))

# 1
def test_contract_valid_result(tmp_path):
    p=tmp_path/'a.raw'; p.write_bytes(b'x'); r=result_for(asset(p)); r.validate()
# 2
def test_contract_rejects_wrong_event_collection(tmp_path):
    p=tmp_path/'a.raw'; p.write_bytes(b'x'); r=result_for(asset(p));
    bad=AudioAnalysisResult(**{**r.__dict__,'beats':(AnalysisEvent(0,AnalysisEventType.ONSET,.5,.5),)})
    with pytest.raises(ValueError): bad.validate()
# 3
def test_tick_profile_exact(): assert TICKS_PER_SAMPLE==10 and TICKS_PER_FRAME==5120 and TIMEBASE==240000
# 4
def test_settings_signature_stable(): assert AnalyzerSettings().signature()==AnalyzerSettings().signature()
# 5
def test_settings_signature_changes(): assert AnalyzerSettings(n_fft=1024).signature()!=AnalyzerSettings().signature()
# 6
def test_cache_key_deterministic():
    s=AnalyzerSettings().signature(); d='a'*64; assert cache_key(d,s)==cache_key(d,s)
# 7
def test_hash_source_deterministic(tmp_path):
    p=tmp_path/'x'; p.write_bytes(b'hello'); assert hash_source(p)[0]==hashlib.sha256(b'hello').hexdigest()
# 8
def test_hash_source_cancelled(tmp_path):
    p=tmp_path/'x'; p.write_bytes(b'x'*100); e=threading.Event(); e.set()
    with pytest.raises(AnalysisCancelled): hash_source(p,e)
# 9
def test_quality_silence():
    t,f=evaluate_quality(QualityDiagnostics(TIMEBASE*10,0,0,1,0,0,0,0)); assert t.quality==AnalysisQuality.SILENT and t.bpm==0 and f
# 10
def test_quality_ambient_fails_closed():
    t,f=evaluate_quality(QualityDiagnostics(TIMEBASE*20,90,4,.5,.1,.2,.18,.2)); assert t.quality==AnalysisQuality.LOW and t.confidence<.5
# 11
def test_quality_regular_is_medium_or_high():
    t,_=evaluate_quality(QualityDiagnostics(TIMEBASE*20,120,40,.02,.2,.7,.1,1.0)); assert t.quality in {AnalysisQuality.MEDIUM,AnalysisQuality.HIGH}
# 12-15
@pytest.mark.parametrize('bpm',[60.,90.,120.,150.])
def test_backend_click_tempo(tmp_path,bpm):
    p=tmp_path/f'{int(bpm)}.f32'; write_pcm(p,clicks(bpm)); out=analyze_pcm(p,AnalyzerSettings(),block_frames=256); assert octave_error(out.tempo_bpm,bpm)<4.0 and len(out.beat_frames)>=3
# 16
def test_backend_silence_has_no_beats(tmp_path):
    p=tmp_path/'silent.f32'; write_pcm(p,np.zeros(SAMPLE_RATE*3,dtype=np.float32)); out=analyze_pcm(p,AnalyzerSettings()); assert len(out.beat_frames)==0 and out.rms_peak==0
# 17
def test_cache_roundtrip(tmp_path):
    src=tmp_path/'s'; src.write_bytes(b'audio'); a=asset(src); r=result_for(a); c=AudioAnalysisCache(tmp_path/'cache'); k=cache_key(r.content_sha256,r.settings_signature); c.publish(k,r); got=c.load(k); assert got==r
# 18
def test_cache_missing_manifest_is_miss(tmp_path):
    c=AudioAnalysisCache(tmp_path/'cache'); assert c.load('1'*64) is None
# 19
def test_cache_corruption_quarantines(tmp_path):
    src=tmp_path/'s'; src.write_bytes(b'audio'); a=asset(src); r=result_for(a); c=AudioAnalysisCache(tmp_path/'cache'); k=cache_key(r.content_sha256,r.settings_signature); folder=c.publish(k,r); (folder/'curves.npz').write_bytes(b'bad'); assert c.load(k) is None; assert list((tmp_path/'cache'/'_corrupt').iterdir())
# 20
def test_cache_invalidate_by_content(tmp_path):
    src=tmp_path/'s'; src.write_bytes(b'audio'); a=asset(src); r=result_for(a); c=AudioAnalysisCache(tmp_path/'cache'); k=cache_key(r.content_sha256,r.settings_signature); c.publish(k,r); assert c.invalidate(content_sha256=r.content_sha256)==1 and c.load(k) is None

class Decoder:
    def __init__(self, *, block=None, mutate=False): self.calls=0; self.block=block; self.mutate=mutate
    def __call__(self, source,dest,**kwargs):
        self.calls+=1
        if self.block is not None: self.block.wait(timeout=2)
        if self.mutate:
            Path(source).write_bytes(Path(source).read_bytes()+b'changed')
        np.ones(4096,dtype='<f4').tofile(dest); return Path(dest)
class Analyzer:
    def __init__(self, quality='high'): self.calls=0; self.quality=quality
    def __call__(self,*args,**kwargs): self.calls+=1; return fake_output(quality=self.quality)

def wait_events(service, results, errors):
    assert service.wait_for_idle(4); time.sleep(.03); return results,errors

def mkservice(tmp_path, dec=None, ana=None):
    return AudioAnalysisService(cache=AudioAnalysisCache(tmp_path/'cache'),decoder=dec or Decoder(),analyzer=ana or Analyzer(),temp_root=tmp_path/'temp')
# 21
def test_service_success(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); s=mkservice(tmp_path); rr=[]; ee=[]; s.result_ready.connect(lambda t,r:rr.append(r)); s.request_failed.connect(lambda t,e:ee.append(e)); s.request(a); wait_events(s,rr,ee); assert len(rr)==1 and not ee and rr[0].asset_id==a.asset_id; s.close()
# 22
def test_service_missing_source_error(tmp_path):
    a=asset(tmp_path/'missing'); s=mkservice(tmp_path); ee=[]; s.request_failed.connect(lambda t,e:ee.append(e)); s.request(a); s.wait_for_idle(3); time.sleep(.02); assert ee and ee[0].code=='SOURCE_MISSING'; s.close()
# 23
def test_service_deduplicates_same_asset(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); gate=threading.Event(); dec=Decoder(block=gate); s=mkservice(tmp_path,dec=dec); t1=s.request(a); t2=s.request(a); assert t1==t2; gate.set(); s.wait_for_idle(3); assert dec.calls==1; s.close()
# 24
def test_service_cache_hit_bypasses_decoder(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); dec=Decoder(); ana=Analyzer(); s=mkservice(tmp_path,dec=dec,ana=ana); s.request(a); s.wait_for_idle(3); time.sleep(.02); assert dec.calls==1; s.request(a); s.wait_for_idle(3); time.sleep(.02); assert dec.calls==1 and ana.calls==1; s.close()
# 25
def test_service_force_bypasses_cache(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); dec=Decoder(); ana=Analyzer(); s=mkservice(tmp_path,dec=dec,ana=ana); s.request(a); s.wait_for_idle(3); time.sleep(.02); s.request(a,force=True); s.wait_for_idle(3); assert dec.calls==2 and ana.calls==2; s.close()
# 26
def test_service_low_quality_suppresses_beats(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); s=mkservice(tmp_path,ana=Analyzer('low')); rr=[]; s.result_ready.connect(lambda t,r:rr.append(r)); s.request(a); s.wait_for_idle(3); time.sleep(.02); assert rr and rr[0].tempo.quality==AnalysisQuality.LOW and rr[0].beats==(); s.close()
# 27
def test_service_source_change_fails(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); s=mkservice(tmp_path,dec=Decoder(mutate=True)); ee=[]; s.request_failed.connect(lambda t,e:ee.append(e)); s.request(a); s.wait_for_idle(3); time.sleep(.02); assert ee and ee[0].code=='SOURCE_CHANGED'; s.close()
# 28
def test_service_cancel_suppresses_completion(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); gate=threading.Event(); s=mkservice(tmp_path,dec=Decoder(block=gate)); rr=[]; ee=[]; s.result_ready.connect(lambda *x:rr.append(x)); s.request_failed.connect(lambda *x:ee.append(x)); s.request(a); assert s.cancel(a.asset_id); gate.set(); s.wait_for_idle(3); time.sleep(.02); assert not rr and not ee; s.close()
# 29
def test_service_rebinds_identical_content_to_new_asset(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a1=asset(p); dec=Decoder(); ana=Analyzer(); s=mkservice(tmp_path,dec=dec,ana=ana); s.request(a1); s.wait_for_idle(3); time.sleep(.02); a2=asset(p); rr=[]; s.result_ready.connect(lambda t,r:rr.append(r)); s.request(a2); s.wait_for_idle(3); time.sleep(.02); assert rr[-1].asset_id==a2.asset_id and dec.calls==1; s.close()
# 30
def test_service_does_not_mutate_asset(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); before=dict(a.__dict__); s=mkservice(tmp_path); s.request(a); s.wait_for_idle(3); assert a.__dict__==before; s.close()
# 31
def test_service_close_idempotent(tmp_path):
    s=mkservice(tmp_path); s.close(); s.close(); assert not s.busy
# 32
def test_service_progress_monotonic_enough(tmp_path):
    p=tmp_path/'song'; p.write_bytes(b'audio'); a=asset(p); s=mkservice(tmp_path); values=[]; s.progress_changed.connect(lambda t,p:values.append(p.fraction)); s.request(a); s.wait_for_idle(3); time.sleep(.02); assert values and values[0]>=0 and values[-1]==1 and max(values)<=1; s.close()
