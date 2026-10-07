from __future__ import annotations

from dataclasses import replace
import math

from .advanced_motion_contract import AdvancedMotionPreset, AdvancedMotionState
from .animation_signal_contract import AnimationSignalChannel
from .animation_signal_engine import AnimationSignalEngine
from .event_phase_modulator import EventPhaseEngine
from .visual_binding_contract import VisualPropertyState


def _clamp(v,lo,hi):
    return max(lo,min(hi,float(v)))


class AdvancedMotionEngine:
    def __init__(
        self,
        signal_engine: AnimationSignalEngine,
        phase_engine: EventPhaseEngine,
        preset: AdvancedMotionPreset,
        intensity: float = 1.0,
    ) -> None:
        self.signal_engine=signal_engine
        self.phase_engine=phase_engine
        self.preset=preset if isinstance(preset,AdvancedMotionPreset) else AdvancedMotionPreset(str(preset))
        self.intensity=float(intensity)
        if not math.isfinite(self.intensity) or not 0.0 <= self.intensity <= 2.0:
            raise ValueError("motion intensity must be in 0..2")

    def state(self,tick:int) -> AdvancedMotionState:
        if not isinstance(tick,int) or tick < 0:
            raise ValueError("tick must be non-negative integer")
        p=self.preset
        x=y=rot=0.0
        if p==AdvancedMotionPreset.ALTERNATING_WOBBLE:
            signal=self.signal_engine.value(AnimationSignalChannel.STRONG_BEAT,tick)
            phase=self.phase_engine.sample(AnimationSignalChannel.STRONG_BEAT,tick)
            if phase is not None:
                rot=signal*phase.alternating_sign*3.0*self.intensity
        elif p==AdvancedMotionPreset.BASS_SWAY:
            signal=self.signal_engine.value(AnimationSignalChannel.BASS,tick)
            phase=self.phase_engine.sample(AnimationSignalChannel.BASS,tick)
            if phase is not None:
                x=signal*phase.alternating_sign*0.030*self.intensity
        elif p==AdvancedMotionPreset.CAMERA_SHAKE:
            signal=self.signal_engine.value(AnimationSignalChannel.STRONG_BEAT,tick)
            phase=self.phase_engine.sample(AnimationSignalChannel.STRONG_BEAT,tick)
            if phase is not None:
                m=signal*self.intensity
                x=phase.noise_x*0.014*m
                y=phase.noise_y*0.011*m
                rot=phase.noise_rotation*0.80*m
        elif p==AdvancedMotionPreset.BEAT_BOUNCE:
            signal=self.signal_engine.value(AnimationSignalChannel.BEAT,tick)
            y=-signal*0.030*self.intensity
        elif p==AdvancedMotionPreset.FOUR_WAY_KICK:
            signal=self.signal_engine.value(AnimationSignalChannel.STRONG_BEAT,tick)
            phase=self.phase_engine.sample(AnimationSignalChannel.STRONG_BEAT,tick)
            if phase is not None:
                vectors=((-1.0,0.0),(0.0,-1.0),(1.0,0.0),(0.0,1.0))
                vx,vy=vectors[phase.cardinal_index]
                x=vx*signal*0.028*self.intensity
                y=vy*signal*0.028*self.intensity
        elif p==AdvancedMotionPreset.SPARK_BURST:
            pass
        state=AdvancedMotionState(
            _clamp(x,-0.15,0.15),
            _clamp(y,-0.15,0.15),
            _clamp(rot,-12.0,12.0),
        )
        state.validate()
        return state


def merge_visual_and_motion(
    visual: VisualPropertyState,
    motion: AdvancedMotionState,
) -> VisualPropertyState:
    visual.validate(); motion.validate()
    merged=replace(
        visual,
        x_offset_normalized=_clamp(visual.x_offset_normalized+motion.x_offset_normalized,-0.15,0.15),
        y_offset_normalized=_clamp(visual.y_offset_normalized+motion.y_offset_normalized,-0.15,0.15),
        rotation_offset_deg=_clamp(visual.rotation_offset_deg+motion.rotation_offset_deg,-12.0,12.0),
    )
    merged.validate()
    return merged
