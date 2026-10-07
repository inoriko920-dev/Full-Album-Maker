from __future__ import annotations

import random

from full_album_maker.animation_signal_engine import build_animation_signal_program
from full_album_maker.beat_render_preflight import estimate_command_load
from full_album_maker.editor_models import TIMEBASE
from full_album_maker.event_phase_modulator import EventPhaseEngine
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent
from full_album_maker.animation_signal_contract import AnimationSignalChannel


def _two_hour_events():
    duration=2*60*60*TIMEBASE
    step=TIMEBASE//2  # 120 BPM
    events=[]
    tick=0; index=0
    while tick<duration:
        events.append(ProjectedMusicEvent(
            tick,tick,f"song-{index//240}","asset",
            MusicEventType.STRONG_BEAT,1.0,.95,
        ))
        tick+=step; index+=1
    return duration,tuple(events)


def test_two_hour_event_phase_random_seek_is_deterministic():
    duration,events=_two_hour_events()
    program=build_animation_signal_program(events,duration)
    phase=EventPhaseEngine(program)
    rng=random.Random(14)
    ticks=[rng.randrange(0,duration) for _ in range(1000)]
    first=[phase.sample(AnimationSignalChannel.STRONG_BEAT,t) for t in ticks]
    second=[phase.sample(AnimationSignalChannel.STRONG_BEAT,t) for t in ticks]
    assert first==second
    assert len(program.triggers)==len(events)


def test_two_hour_command_estimate_stays_under_row_architecture():
    duration=2*60*60*TIMEBASE
    estimate=estimate_command_load(duration,30.0,3)
    assert estimate.sample_ticks<=216001
    assert estimate.command_rows_upper_bound<=250000
    assert estimate.command_ops_upper_bound<=1_500_000
