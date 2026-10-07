from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

from .animation_signal_contract import AnimationSignalChannel, SignalTrigger
from .editor_models import TIMEBASE
from .event_phase_modulator import EventPhaseEngine

SPARK_PARTICLES_PER_BURST=6
SPARK_LIFETIME_MS=220
SPARK_LIFETIME_TICK=int(round(TIMEBASE*(SPARK_LIFETIME_MS/1000.0)))


@dataclass(frozen=True)
class SparkParticleSample:
    event_tick: int
    particle_index: int
    x_offset_normalized: float
    y_offset_normalized: float
    size_normalized: float
    alpha: float

    def validate(self):
        if self.event_tick < 0 or not 0 <= self.particle_index < SPARK_PARTICLES_PER_BURST:
            raise ValueError("spark identity invalid")
        if not -0.25 <= self.x_offset_normalized <= 0.25 or not -0.25 <= self.y_offset_normalized <= 0.25:
            raise ValueError("spark offset invalid")
        if not 0.001 <= self.size_normalized <= 0.03:
            raise ValueError("spark size invalid")
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("spark alpha invalid")


def _unit(seed: str, index: int, salt: str) -> float:
    digest=hashlib.sha256(f"{seed}|{index}|{salt}".encode()).digest()
    return int.from_bytes(digest[:8],"big")/float((1<<64)-1)


def _seed(trigger: SignalTrigger) -> str:
    return f"{trigger.channel.value}|{trigger.event_tick}|{trigger.song_id}|{trigger.asset_id}|{trigger.source_tick}"


def particles_for_trigger(trigger: SignalTrigger, tick: int, intensity: float = 1.0) -> tuple[SparkParticleSample,...]:
    if tick < trigger.event_tick or tick > trigger.event_tick+SPARK_LIFETIME_TICK:
        return ()
    intensity=max(0.0,min(2.0,float(intensity)))
    progress=(tick-trigger.event_tick)/max(1,SPARK_LIFETIME_TICK)
    ease=1.0-(1.0-progress)**3
    alpha=(1.0-progress)**2
    seed=_seed(trigger)
    result=[]
    for i in range(SPARK_PARTICLES_PER_BURST):
        jitter=(_unit(seed,i,"angle")-.5)*0.45
        angle=(2.0*math.pi*i/SPARK_PARTICLES_PER_BURST)+jitter
        start=.010+.012*_unit(seed,i,"start")
        travel=(.070+.055*_unit(seed,i,"travel"))*min(1.5,max(.35,intensity))
        radius=start+travel*ease
        size=(.004+.004*_unit(seed,i,"size"))*min(1.5,max(.5,intensity))
        sample=SparkParticleSample(
            event_tick=trigger.event_tick,
            particle_index=i,
            x_offset_normalized=math.cos(angle)*radius,
            y_offset_normalized=math.sin(angle)*radius,
            size_normalized=max(.001,min(.03,size)),
            alpha=max(0.0,min(1.0,alpha*(.65+.35*_unit(seed,i,"alpha")))),
        )
        sample.validate(); result.append(sample)
    return tuple(result)


class SparkBurstEngine:
    def __init__(self, phase_engine: EventPhaseEngine, intensity: float = 1.0) -> None:
        self.phase_engine=phase_engine
        self.intensity=float(intensity)
        if not math.isfinite(self.intensity) or not 0.0 <= self.intensity <= 2.0:
            raise ValueError("spark intensity must be in 0..2")

    def particles(self,tick:int) -> tuple[SparkParticleSample,...]:
        if tick < 0:
            raise ValueError("tick must be non-negative")
        result=[]
        for trigger in self.phase_engine.triggers(AnimationSignalChannel.STRONG_BEAT):
            if trigger.event_tick <= tick <= trigger.event_tick+SPARK_LIFETIME_TICK:
                result.extend(particles_for_trigger(trigger,tick,self.intensity))
        return tuple(result)
