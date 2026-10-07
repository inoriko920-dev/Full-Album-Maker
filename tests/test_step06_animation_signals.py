from __future__ import annotations

from dataclasses import replace

import pytest

from full_album_maker.animation_signal_contract import (
    ANIMATION_SIGNAL_ENGINE_VERSION,
    AnimationSignalChannel,
    AnimationSignalProgram,
    AnimationSignalSettings,
    SignalBlendMode,
    SignalProfile,
    SignalShape,
)
from full_album_maker.animation_signal_engine import AnimationSignalEngine, build_animation_signal_program
from full_album_maker.editor_models import TIMEBASE
from full_album_maker.music_event_contract import MusicEventType, ProjectedMusicEvent


def event(
    tick: int,
    event_type: MusicEventType,
    *,
    strength: float = 1.0,
    confidence: float = 1.0,
    song: str = "song-a",
    asset: str = "asset-a",
    source_tick: int | None = None,
) -> ProjectedMusicEvent:
    value = ProjectedMusicEvent(
        project_tick=tick,
        source_tick=tick if source_tick is None else source_tick,
        song_id=song,
        asset_id=asset,
        event_type=event_type,
        strength=strength,
        confidence=confidence,
        source=f"test.{event_type.value}",
    )
    value.validate()
    return value


def program(events=(), *, duration=10 * TIMEBASE, settings=None):
    return build_animation_signal_program(events, duration, settings)


def engine(events=(), *, duration=10 * TIMEBASE, settings=None):
    return AnimationSignalEngine(program(events, duration=duration, settings=settings))


# 1
def test_default_settings_validate():
    AnimationSignalSettings().validate()


# 2
def test_profile_rejects_negative_timing():
    p = AnimationSignalSettings().profile_for_channel(AnimationSignalChannel.BEAT)
    with pytest.raises(ValueError):
        replace(p, decay_ms=-1).validate()


# 3
def test_profile_rejects_bad_confidence_floor():
    p = AnimationSignalSettings().profile_for_channel(AnimationSignalChannel.BEAT)
    with pytest.raises(ValueError):
        replace(p, confidence_floor=1.1).validate()


# 4
def test_settings_signature_deterministic():
    a = AnimationSignalSettings()
    assert a.signature() == AnimationSignalSettings().signature()
    assert len(a.signature()) == 64


# 5
def test_settings_signature_changes_with_profile():
    base = AnimationSignalSettings()
    profiles = list(base.profiles)
    profiles[0] = replace(profiles[0], decay_ms=181)
    changed = replace(base, profiles=tuple(profiles))
    assert base.signature() != changed.signature()


# 6
def test_empty_program_outputs_zero():
    e = engine(())
    for channel in AnimationSignalChannel:
        assert e.value(channel, TIMEBASE) == 0.0


# 7-12
@pytest.mark.parametrize(
    "event_type,channel",
    [
        (MusicEventType.BEAT, AnimationSignalChannel.BEAT),
        (MusicEventType.STRONG_BEAT, AnimationSignalChannel.STRONG_BEAT),
        (MusicEventType.BASS_HIT, AnimationSignalChannel.BASS),
        (MusicEventType.ONSET, AnimationSignalChannel.ONSET),
        (MusicEventType.ENERGY_RISE, AnimationSignalChannel.ENERGY_UP),
        (MusicEventType.ENERGY_FALL, AnimationSignalChannel.ENERGY_DOWN),
    ],
)
def test_event_routes_to_expected_channel(event_type, channel):
    tick = TIMEBASE
    e = engine((event(tick, event_type),))
    assert e.value(channel, tick) > 0.0


# 13
def test_confidence_below_floor_suppresses_trigger():
    tick = TIMEBASE
    e = engine((event(tick, MusicEventType.STRONG_BEAT, confidence=0.49),))
    assert e.value(AnimationSignalChannel.STRONG_BEAT, tick) == 0.0


# 14
def test_sensitivity_changes_pre_envelope_strength():
    tick = TIMEBASE
    base = AnimationSignalSettings()
    low = replace(base, sensitivity_by_channel=((AnimationSignalChannel.BEAT, 0.5),))
    normal = engine((event(tick, MusicEventType.BEAT, strength=0.8),), settings=base)
    reduced = engine((event(tick, MusicEventType.BEAT, strength=0.8),), settings=low)
    assert 0.0 < reduced.value(AnimationSignalChannel.BEAT, tick) < normal.value(AnimationSignalChannel.BEAT, tick)


# 15
def test_intensity_changes_post_envelope_output():
    tick = TIMEBASE
    base = AnimationSignalSettings()
    quiet = replace(base, intensity_by_channel=((AnimationSignalChannel.BEAT, 0.5),))
    a = engine((event(tick, MusicEventType.BEAT),), settings=base).value(AnimationSignalChannel.BEAT, tick)
    b = engine((event(tick, MusicEventType.BEAT),), settings=quiet).value(AnimationSignalChannel.BEAT, tick)
    assert b == pytest.approx(a * 0.5)


# 16
def test_output_is_always_unit_bounded():
    tick = TIMEBASE
    settings = replace(
        AnimationSignalSettings(),
        sensitivity_by_channel=((AnimationSignalChannel.ONSET, 2.0),),
        intensity_by_channel=((AnimationSignalChannel.ONSET, 2.0),),
    )
    values = [event(tick + i * 1000, MusicEventType.ONSET) for i in range(6)]
    e = engine(values, settings=settings)
    for t in range(tick, tick + TIMEBASE, 5000):
        assert 0.0 <= e.value(AnimationSignalChannel.ONSET, t) <= 1.0


# 17
def test_impulse_peaks_at_event_tick():
    tick = TIMEBASE
    e = engine((event(tick, MusicEventType.BEAT),))
    peak = e.value(AnimationSignalChannel.BEAT, tick)
    assert peak > e.value(AnimationSignalChannel.BEAT, tick + 20_000)


# 18
def test_impulse_decay_is_monotonic():
    tick = TIMEBASE
    e = engine((event(tick, MusicEventType.BEAT),))
    samples = [e.value(AnimationSignalChannel.BEAT, tick + offset) for offset in (0, 10_000, 20_000, 30_000, 40_000)]
    assert samples == sorted(samples, reverse=True)


# 19
def test_attack_hold_decay_boundaries():
    tick = TIMEBASE
    e = engine((event(tick, MusicEventType.STRONG_BEAT),))
    profile = AnimationSignalSettings().profile_for_channel(AnimationSignalChannel.STRONG_BEAT)
    before = tick - profile.attack_tick
    mid_attack = tick - max(1, profile.attack_tick // 2)
    hold_end = tick + profile.hold_tick
    after_end = hold_end + profile.decay_tick
    assert e.value(AnimationSignalChannel.STRONG_BEAT, before) == pytest.approx(0.0)
    assert 0.0 < e.value(AnimationSignalChannel.STRONG_BEAT, mid_attack) < e.value(AnimationSignalChannel.STRONG_BEAT, tick)
    assert e.value(AnimationSignalChannel.STRONG_BEAT, hold_end) == pytest.approx(e.value(AnimationSignalChannel.STRONG_BEAT, tick))
    assert e.value(AnimationSignalChannel.STRONG_BEAT, after_end) == pytest.approx(0.0)


# 20
def test_max_overlap_never_clips():
    tick = TIMEBASE
    values = (
        event(tick, MusicEventType.BEAT, strength=1.0),
        event(tick + 10_000, MusicEventType.BEAT, strength=1.0, song="song-b"),
    )
    e = engine(values)
    assert 0.0 <= e.value(AnimationSignalChannel.BEAT, tick + 10_000) <= 1.0


# 21
def test_saturating_add_never_clips():
    tick = TIMEBASE
    values = tuple(
        event(tick + i * 5_000, MusicEventType.ONSET, strength=1.0, song=f"s{i}")
        for i in range(5)
    )
    e = engine(values)
    assert 0.0 < e.value(AnimationSignalChannel.ONSET, tick + 20_000) <= 1.0


# 22
def test_same_tick_duplicate_keeps_stronger_trigger():
    tick = TIMEBASE
    p = program((
        event(tick, MusicEventType.BEAT, strength=0.4, song="weak"),
        event(tick, MusicEventType.BEAT, strength=1.0, song="strong"),
    ))
    beat_triggers = [x for x in p.triggers if x.channel == AnimationSignalChannel.BEAT]
    assert len(beat_triggers) == 1
    assert beat_triggers[0].song_id == "strong"


# 23
def test_cross_channel_same_tick_stays_independent():
    tick = TIMEBASE
    e = engine((
        event(tick, MusicEventType.STRONG_BEAT),
        event(tick, MusicEventType.BASS_HIT),
    ))
    assert e.value(AnimationSignalChannel.STRONG_BEAT, tick) > 0
    assert e.value(AnimationSignalChannel.BASS, tick) > 0


# 24
def test_random_seek_equals_sequential_sampling():
    events = tuple(event(i * 100_000, MusicEventType.BEAT) for i in range(1, 12))
    e = engine(events, duration=20 * TIMEBASE)
    ticks = [50_000, 100_000, 175_000, 250_000, 525_000, 900_000]
    direct = [e.value(AnimationSignalChannel.BEAT, t) for t in ticks]
    sequential = {s.tick: s.value(AnimationSignalChannel.BEAT) for s in e.sample_range(0, 1_000_000, 25_000)}
    assert direct == [sequential[t] for t in ticks]


# 25
def test_sample_range_equals_repeated_sample_calls():
    tick = TIMEBASE
    e = engine((event(tick, MusicEventType.BASS_HIT),))
    values = e.sample_range(tick - 20_000, tick + 80_000, 10_000)
    assert values == tuple(e.sample(v.tick) for v in values)


# 26
def test_negative_tick_rejected():
    e = engine(())
    with pytest.raises(ValueError):
        e.value(AnimationSignalChannel.BEAT, -1)


# 27
def test_tick_at_or_after_duration_is_zero():
    e = engine((event(TIMEBASE, MusicEventType.BEAT),), duration=2 * TIMEBASE)
    assert e.value(AnimationSignalChannel.BEAT, 2 * TIMEBASE) == 0.0
    assert e.value(AnimationSignalChannel.BEAT, 3 * TIMEBASE) == 0.0


# 28
def test_program_does_not_mutate_projected_events():
    values = [event(TIMEBASE, MusicEventType.BEAT)]
    before = tuple(values)
    program(values)
    assert tuple(values) == before


# 29
def test_input_order_does_not_change_program():
    values = [
        event(2 * TIMEBASE, MusicEventType.BEAT, song="b"),
        event(TIMEBASE, MusicEventType.BASS_HIT, song="a"),
        event(3 * TIMEBASE, MusicEventType.ONSET, song="c"),
    ]
    assert program(values) == program(reversed(values))


# 30
def test_two_song_overlap_blends_deterministically():
    tick = TIMEBASE
    events = (
        event(tick, MusicEventType.ONSET, song="song-a"),
        event(tick + 5_000, MusicEventType.ONSET, song="song-b"),
    )
    a = engine(events).value(AnimationSignalChannel.ONSET, tick + 10_000)
    b = engine(reversed(events)).value(AnimationSignalChannel.ONSET, tick + 10_000)
    assert a == pytest.approx(b)
    assert 0.0 < a <= 1.0


# 31
def test_unknown_channel_raises_keyerror():
    e = engine(())
    with pytest.raises(KeyError):
        e.value("not-a-channel", 0)


# 32
def test_sample_subset_preserves_requested_order():
    e = engine((event(TIMEBASE, MusicEventType.BASS_HIT),))
    s = e.sample(TIMEBASE, (AnimationSignalChannel.BASS, AnimationSignalChannel.BEAT))
    assert [channel for channel, _ in s.values] == [AnimationSignalChannel.BASS, AnimationSignalChannel.BEAT]


# 33
def test_settings_reject_duplicate_channel_profile():
    base = AnimationSignalSettings()
    duplicate = replace(base.profiles[1], event_type=MusicEventType.STRONG_BEAT, channel=AnimationSignalChannel.BEAT)
    with pytest.raises(ValueError):
        replace(base, profiles=(base.profiles[0], duplicate, *base.profiles[2:])).validate()


# 34
def test_program_validates_signature_and_version_contract():
    p = program((event(TIMEBASE, MusicEventType.BEAT),))
    p.validate()
    assert len(p.settings_signature) == 64
    assert ANIMATION_SIGNAL_ENGINE_VERSION == "animation-signals-v1"


# 35
def test_long_sparse_program_can_be_sampled():
    events = tuple(
        event(i * 2 * TIMEBASE, MusicEventType.BEAT, song=f"song-{i}")
        for i in range(1000)
    )
    e = engine(events, duration=2001 * TIMEBASE)
    assert 0.0 <= e.value(AnimationSignalChannel.BEAT, 999 * 2 * TIMEBASE) <= 1.0
