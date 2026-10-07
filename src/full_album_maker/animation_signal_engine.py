from __future__ import annotations

from bisect import bisect_right
import math
from typing import Iterable, Sequence

from .animation_signal_contract import (
    AnimationSignalChannel,
    AnimationSignalProgram,
    AnimationSignalSample,
    AnimationSignalSettings,
    SignalBlendMode,
    SignalProfile,
    SignalShape,
    SignalTrigger,
    clamp_unit,
    projected_event_identity,
    signal_trigger_sort_key,
)
from .music_event_contract import ProjectedMusicEvent


def _ease_out_cubic(u: float) -> float:
    u = clamp_unit(u)
    return 1.0 - (1.0 - u) ** 3


def _decay_cubic(u: float) -> float:
    u = clamp_unit(u)
    return (1.0 - u) ** 3


def _trigger_amplitude(event: ProjectedMusicEvent, profile: SignalProfile, settings: AnimationSignalSettings) -> float:
    confidence = clamp_unit(event.confidence)
    if confidence + 1e-12 < profile.confidence_floor:
        return 0.0
    sensitivity = settings.sensitivity(profile.channel)
    effective_strength = clamp_unit(float(event.strength) * sensitivity)
    strength_term = effective_strength ** float(profile.strength_gamma)
    if profile.confidence_floor >= 1.0:
        confidence_term = 1.0 if confidence >= 1.0 else 0.0
    else:
        normalized = clamp_unit((confidence - profile.confidence_floor) / (1.0 - profile.confidence_floor))
        confidence_term = 0.35 + 0.65 * normalized
    value = float(profile.amplitude) * strength_term * confidence_term
    return clamp_unit(min(float(profile.max_value), value))


def _make_trigger(event: ProjectedMusicEvent, profile: SignalProfile, amplitude: float) -> SignalTrigger:
    attack = profile.attack_tick
    hold = profile.hold_tick
    decay = profile.decay_tick
    start = max(0, int(event.project_tick) - attack)
    end = int(event.project_tick) + hold + decay
    trigger = SignalTrigger(
        channel=profile.channel,
        event_type=event.event_type,
        event_tick=int(event.project_tick),
        start_tick=start,
        end_tick=end,
        attack_tick=attack,
        hold_tick=hold,
        decay_tick=decay,
        amplitude=amplitude,
        shape=profile.shape,
        blend_mode=profile.blend_mode,
        song_id=event.song_id,
        asset_id=event.asset_id,
        source_tick=int(event.source_tick),
    )
    trigger.validate()
    return trigger


def build_animation_signal_program(
    events: Iterable[ProjectedMusicEvent],
    duration_tick: int,
    settings: AnimationSignalSettings | None = None,
) -> AnimationSignalProgram:
    if not isinstance(duration_tick, int) or duration_tick < 0:
        raise ValueError("duration_tick must be a non-negative integer")
    cfg = settings or AnimationSignalSettings()
    cfg.validate()

    ordered_events = sorted(tuple(events), key=projected_event_identity)
    best_by_channel_tick: dict[tuple[AnimationSignalChannel, int], SignalTrigger] = {}
    for event in ordered_events:
        event.validate()
        if duration_tick == 0 or event.project_tick >= duration_tick:
            continue
        try:
            profile = cfg.profile_for_event(event.event_type)
        except KeyError as exc:
            raise ValueError(f"no signal profile for event type: {event.event_type.value}") from exc
        amplitude = _trigger_amplitude(event, profile, cfg)
        if amplitude <= 0.0:
            continue
        trigger = _make_trigger(event, profile, amplitude)
        key = (trigger.channel, trigger.event_tick)
        current = best_by_channel_tick.get(key)
        if current is None or (trigger.amplitude, -trigger.source_tick, trigger.song_id) > (
            current.amplitude,
            -current.source_tick,
            current.song_id,
        ):
            best_by_channel_tick[key] = trigger

    channels = tuple(profile.channel for profile in cfg.profiles)
    intensities = tuple((channel, cfg.intensity(channel)) for channel in channels)
    program = AnimationSignalProgram(
        duration_tick=duration_tick,
        settings_signature=cfg.signature(),
        channels=channels,
        triggers=tuple(sorted(best_by_channel_tick.values(), key=signal_trigger_sort_key)),
        intensity_by_channel=intensities,
    )
    program.validate()
    return program


def _envelope_value(trigger: SignalTrigger, tick: int) -> float:
    if tick < trigger.start_tick or tick > trigger.end_tick:
        return 0.0
    if trigger.shape == SignalShape.IMPULSE_DECAY:
        if tick < trigger.event_tick:
            return 0.0
        if trigger.decay_tick <= 0:
            return trigger.amplitude if tick == trigger.event_tick else 0.0
        elapsed = tick - trigger.event_tick
        if elapsed > trigger.decay_tick:
            return 0.0
        return trigger.amplitude * _decay_cubic(elapsed / trigger.decay_tick)

    if trigger.shape == SignalShape.ATTACK_HOLD_DECAY:
        if tick < trigger.event_tick:
            if trigger.attack_tick <= 0:
                return 0.0
            nominal_start = trigger.event_tick - trigger.attack_tick
            u = (tick - nominal_start) / trigger.attack_tick
            return trigger.amplitude * _ease_out_cubic(u)
        hold_end = trigger.event_tick + trigger.hold_tick
        if tick <= hold_end:
            return trigger.amplitude
        if trigger.decay_tick <= 0:
            return 0.0
        elapsed = tick - hold_end
        if elapsed > trigger.decay_tick:
            return 0.0
        return trigger.amplitude * _decay_cubic(elapsed / trigger.decay_tick)

    raise ValueError(f"unsupported signal shape: {trigger.shape}")


def _blend(current: float, incoming: float, mode: SignalBlendMode) -> float:
    a, b = clamp_unit(current), clamp_unit(incoming)
    if mode == SignalBlendMode.MAX:
        return max(a, b)
    if mode == SignalBlendMode.SATURATING_ADD:
        return clamp_unit(1.0 - (1.0 - a) * (1.0 - b))
    raise ValueError(f"unsupported blend mode: {mode}")


class AnimationSignalEngine:
    def __init__(self, program: AnimationSignalProgram) -> None:
        program.validate()
        self.program = program
        grouped: dict[AnimationSignalChannel, list[SignalTrigger]] = {channel: [] for channel in program.channels}
        for trigger in program.triggers:
            grouped[trigger.channel].append(trigger)
        self._triggers = {channel: tuple(values) for channel, values in grouped.items()}
        self._starts = {
            channel: tuple(trigger.start_tick for trigger in values)
            for channel, values in self._triggers.items()
        }

    @staticmethod
    def _channel(channel: AnimationSignalChannel | str) -> AnimationSignalChannel:
        if isinstance(channel, AnimationSignalChannel):
            return channel
        try:
            return AnimationSignalChannel(str(channel))
        except ValueError as exc:
            raise KeyError(channel) from exc

    def _raw_value(self, channel: AnimationSignalChannel, tick: int) -> float:
        triggers = self._triggers[channel]
        if not triggers:
            return 0.0
        starts = self._starts[channel]
        index = bisect_right(starts, tick) - 1
        if index < 0:
            return 0.0
        value = 0.0
        while index >= 0:
            trigger = triggers[index]
            if trigger.end_tick < tick:
                break
            incoming = _envelope_value(trigger, tick)
            if incoming > 0.0:
                value = _blend(value, incoming, trigger.blend_mode)
            index -= 1
        return clamp_unit(value)

    def value(self, channel: AnimationSignalChannel | str, tick: int) -> float:
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        selected = self._channel(channel)
        if selected not in self._triggers:
            raise KeyError(selected)
        if self.program.duration_tick == 0 or tick >= self.program.duration_tick:
            return 0.0
        raw = self._raw_value(selected, tick)
        return clamp_unit(raw * self.program.intensity(selected))

    def sample(
        self,
        tick: int,
        channels: Sequence[AnimationSignalChannel | str] | None = None,
    ) -> AnimationSignalSample:
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if channels is None:
            selected = self.program.channels
        else:
            selected = tuple(self._channel(channel) for channel in channels)
            if len(set(selected)) != len(selected):
                raise ValueError("channels must be unique")
            for channel in selected:
                if channel not in self._triggers:
                    raise KeyError(channel)
        sample = AnimationSignalSample(
            tick=tick,
            values=tuple((channel, self.value(channel, tick)) for channel in selected),
        )
        sample.validate()
        return sample

    def sample_range(
        self,
        start_tick: int,
        end_tick: int,
        step_tick: int,
        channels: Sequence[AnimationSignalChannel | str] | None = None,
    ) -> tuple[AnimationSignalSample, ...]:
        if not isinstance(start_tick, int) or start_tick < 0:
            raise ValueError("start_tick must be a non-negative integer")
        if not isinstance(end_tick, int) or end_tick < start_tick:
            raise ValueError("end_tick must be >= start_tick")
        if not isinstance(step_tick, int) or step_tick <= 0:
            raise ValueError("step_tick must be a positive integer")
        return tuple(self.sample(tick, channels) for tick in range(start_tick, end_tick, step_tick))

    def active_triggers(self, channel: AnimationSignalChannel | str, tick: int) -> tuple[SignalTrigger, ...]:
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        selected = self._channel(channel)
        if selected not in self._triggers:
            raise KeyError(selected)
        if self.program.duration_tick == 0 or tick >= self.program.duration_tick:
            return ()
        values = []
        starts = self._starts[selected]
        index = bisect_right(starts, tick) - 1
        triggers = self._triggers[selected]
        while index >= 0:
            trigger = triggers[index]
            if trigger.end_tick < tick:
                break
            if _envelope_value(trigger, tick) > 0.0:
                values.append(trigger)
            index -= 1
        return tuple(reversed(values))
