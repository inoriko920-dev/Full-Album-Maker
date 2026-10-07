from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
import hashlib
import math

from .animation_signal_contract import (
    AnimationSignalChannel,
    AnimationSignalProgram,
    SignalTrigger,
)
from .editor_models import TIMEBASE

EVENT_PHASE_ENGINE_VERSION = "event-phase-v1"
NOISE_HZ = 30.0


@dataclass(frozen=True)
class PhaseSample:
    channel: AnimationSignalChannel
    event_tick: int
    event_index: int
    local_progress: float
    alternating_sign: int
    cardinal_index: int
    noise_x: float
    noise_y: float
    noise_rotation: float

    def validate(self) -> None:
        if not isinstance(self.channel, AnimationSignalChannel):
            raise ValueError("phase channel invalid")
        if not isinstance(self.event_tick, int) or self.event_tick < 0:
            raise ValueError("phase event_tick invalid")
        if not isinstance(self.event_index, int) or self.event_index < 0:
            raise ValueError("phase event_index invalid")
        if not 0.0 <= float(self.local_progress) <= 1.0:
            raise ValueError("phase progress must be 0..1")
        if self.alternating_sign not in {-1, 1}:
            raise ValueError("phase alternating_sign invalid")
        if self.cardinal_index not in {0, 1, 2, 3}:
            raise ValueError("phase cardinal_index invalid")
        for name in ("noise_x", "noise_y", "noise_rotation"):
            value=float(getattr(self,name))
            if not math.isfinite(value) or not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} must be -1..1")


def _trigger_identity(trigger: SignalTrigger) -> tuple:
    return (
        trigger.channel.value,
        trigger.event_tick,
        trigger.start_tick,
        trigger.end_tick,
        trigger.song_id,
        trigger.asset_id,
        trigger.source_tick,
    )


def _seed_text(trigger: SignalTrigger) -> str:
    return "|".join(str(v) for v in _trigger_identity(trigger))


def _hash_signed(seed: str, bucket: int, salt: str) -> float:
    raw=f"{seed}|{bucket}|{salt}".encode("utf-8")
    digest=hashlib.sha256(raw).digest()
    n=int.from_bytes(digest[:8],"big") / float((1<<64)-1)
    return (n*2.0)-1.0


def _smoothstep(u: float) -> float:
    u=max(0.0,min(1.0,float(u)))
    return u*u*(3.0-2.0*u)


def _noise(trigger: SignalTrigger, tick: int, salt: str) -> float:
    bucket_tick=max(1,int(round(TIMEBASE/NOISE_HZ)))
    rel=int(tick)-int(trigger.event_tick)
    pos=rel/bucket_tick
    b0=math.floor(pos)
    frac=pos-b0
    a=_hash_signed(_seed_text(trigger),b0,salt)
    b=_hash_signed(_seed_text(trigger),b0+1,salt)
    u=_smoothstep(frac)
    return max(-1.0,min(1.0,a+(b-a)*u))


class EventPhaseEngine:
    def __init__(self, program: AnimationSignalProgram) -> None:
        program.validate()
        self.program=program
        grouped: dict[AnimationSignalChannel,list[SignalTrigger]]={}
        for trigger in program.triggers:
            grouped.setdefault(trigger.channel,[]).append(trigger)
        self._by_channel={
            channel: tuple(sorted(values,key=lambda t:(t.event_tick,t.start_tick,t.song_id,t.asset_id,t.source_tick)))
            for channel,values in grouped.items()
        }
        self._event_ticks={channel: tuple(t.event_tick for t in values) for channel,values in self._by_channel.items()}
        self._index={
            _trigger_identity(trigger): index
            for channel in sorted(self._by_channel,key=lambda c:c.value)
            for index,trigger in enumerate(self._by_channel[channel])
        }

    def triggers(self, channel: AnimationSignalChannel) -> tuple[SignalTrigger,...]:
        return self._by_channel.get(channel,())

    def trigger_index(self, trigger: SignalTrigger) -> int:
        try:
            return self._index[_trigger_identity(trigger)]
        except KeyError as exc:
            raise KeyError("trigger not part of phase program") from exc

    def active_triggers(self, channel: AnimationSignalChannel, tick: int) -> tuple[SignalTrigger,...]:
        if not isinstance(tick,int) or tick < 0:
            raise ValueError("tick must be non-negative integer")
        values=self._by_channel.get(channel,())
        return tuple(t for t in values if t.start_tick <= tick <= t.end_tick)

    def _winner(self, channel: AnimationSignalChannel, tick: int) -> SignalTrigger | None:
        active=self.active_triggers(channel,tick)
        if not active:
            return None
        past=[t for t in active if t.event_tick <= tick]
        if past:
            return max(past,key=lambda t:(t.event_tick,t.amplitude,-t.source_tick,t.song_id,t.asset_id))
        return min(active,key=lambda t:(t.event_tick,-t.amplitude,t.source_tick,t.song_id,t.asset_id))

    def sample(self, channel: AnimationSignalChannel, tick: int) -> PhaseSample | None:
        trigger=self._winner(channel,tick)
        if trigger is None:
            return None
        index=self.trigger_index(trigger)
        if tick <= trigger.event_tick:
            progress=0.0
        else:
            span=max(1,trigger.end_tick-trigger.event_tick)
            progress=max(0.0,min(1.0,(tick-trigger.event_tick)/span))
        sample=PhaseSample(
            channel=channel,
            event_tick=trigger.event_tick,
            event_index=index,
            local_progress=progress,
            alternating_sign=-1 if index%2==0 else 1,
            cardinal_index=index%4,
            noise_x=_noise(trigger,tick,"x"),
            noise_y=_noise(trigger,tick,"y"),
            noise_rotation=_noise(trigger,tick,"rotation"),
        )
        sample.validate()
        return sample
