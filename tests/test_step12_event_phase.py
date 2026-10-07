from __future__ import annotations

import pytest

from full_album_maker.animation_signal_contract import AnimationSignalChannel
from full_album_maker.animation_signal_engine import build_animation_signal_program
from full_album_maker.editor_models import TIMEBASE
from full_album_maker.event_phase_modulator import EventPhaseEngine
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent


def ev(tick,event_type,source_tick=None,strength=1.0):
    return ProjectedMusicEvent(
        project_tick=int(tick),
        source_tick=int(tick if source_tick is None else source_tick),
        song_id="song",asset_id="asset",event_type=event_type,
        strength=strength,confidence=1.0,source="step12",
    )


def engine(events,duration=5*TIMEBASE):
    return EventPhaseEngine(build_animation_signal_program(tuple(events),duration))


def test_phase_ordinal_and_alternating_sign_are_stable():
    values=[
        ev(TIMEBASE,MusicEventType.STRONG_BEAT),
        ev(2*TIMEBASE,MusicEventType.STRONG_BEAT),
        ev(3*TIMEBASE,MusicEventType.STRONG_BEAT),
    ]
    phase=engine(values)
    samples=[phase.sample(AnimationSignalChannel.STRONG_BEAT,e.project_tick) for e in values]
    assert [s.event_index for s in samples]==[0,1,2]
    assert [s.alternating_sign for s in samples]==[-1,1,-1]
    assert [s.cardinal_index for s in samples]==[0,1,2]


def test_four_way_cardinal_cycles_every_four_events():
    values=[ev((i+1)*TIMEBASE//2,MusicEventType.STRONG_BEAT) for i in range(5)]
    phase=engine(values)
    samples=[phase.sample(AnimationSignalChannel.STRONG_BEAT,e.project_tick) for e in values]
    assert [s.cardinal_index for s in samples]==[0,1,2,3,0]


def test_same_tick_seek_returns_identical_noise_and_phase():
    phase=engine([ev(TIMEBASE,MusicEventType.STRONG_BEAT)])
    tick=TIMEBASE+20_000
    a=phase.sample(AnimationSignalChannel.STRONG_BEAT,tick)
    phase.sample(AnimationSignalChannel.STRONG_BEAT,TIMEBASE+70_000)
    b=phase.sample(AnimationSignalChannel.STRONG_BEAT,tick)
    assert a==b


def test_noise_is_bounded_and_axes_are_independently_salted():
    phase=engine([ev(TIMEBASE,MusicEventType.STRONG_BEAT)])
    s=phase.sample(AnimationSignalChannel.STRONG_BEAT,TIMEBASE+15_000)
    assert all(-1 <= value <= 1 for value in (s.noise_x,s.noise_y,s.noise_rotation))
    assert len({round(s.noise_x,9),round(s.noise_y,9),round(s.noise_rotation,9)})>1


def test_input_order_does_not_change_phase_identity():
    a=ev(TIMEBASE,MusicEventType.STRONG_BEAT,source_tick=10)
    b=ev(2*TIMEBASE,MusicEventType.STRONG_BEAT,source_tick=20)
    p1=engine([a,b]); p2=engine([b,a])
    assert p1.sample(AnimationSignalChannel.STRONG_BEAT,a.project_tick)==p2.sample(AnimationSignalChannel.STRONG_BEAT,a.project_tick)
    assert p1.sample(AnimationSignalChannel.STRONG_BEAT,b.project_tick)==p2.sample(AnimationSignalChannel.STRONG_BEAT,b.project_tick)


def test_overlap_winner_is_latest_past_event():
    a=ev(TIMEBASE,MusicEventType.STRONG_BEAT)
    b=ev(TIMEBASE+50_000,MusicEventType.STRONG_BEAT,source_tick=50_000)
    phase=engine([a,b])
    sample=phase.sample(AnimationSignalChannel.STRONG_BEAT,TIMEBASE+60_000)
    assert sample.event_tick==b.project_tick
    assert sample.event_index==1


def test_phase_none_outside_active_window():
    phase=engine([ev(TIMEBASE,MusicEventType.BEAT)])
    assert phase.sample(AnimationSignalChannel.BEAT,0) is None
    assert phase.sample(AnimationSignalChannel.BEAT,2*TIMEBASE) is None


def test_negative_tick_rejected():
    phase=engine([ev(TIMEBASE,MusicEventType.BEAT)])
    with pytest.raises(ValueError):
        phase.sample(AnimationSignalChannel.BEAT,-1)
