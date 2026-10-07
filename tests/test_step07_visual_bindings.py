from __future__ import annotations

import pytest

from full_album_maker.animation_signal_contract import AnimationSignalChannel, AnimationSignalSample
from full_album_maker.editor_models import Transform
from full_album_maker.visual_binding_contract import (
    CoreBeatPreset,
    VisualBinding,
    VisualBindingSet,
    VisualProperty,
    VisualPropertyState,
)
from full_album_maker.visual_binding_engine import (
    VisualPropertyBindingEngine,
    apply_visual_state,
    combine_binding_sets,
    core_binding_set,
    supported_properties_for_layer,
)


class FakeSignalEngine:
    def __init__(self, values=None, fn=None):
        self.values = dict(values or {})
        self.fn = fn
        self.sample_calls = 0

    def sample(self, tick, channels=None):
        self.sample_calls += 1
        selected = tuple(channels or tuple(AnimationSignalChannel))
        vals = []
        for channel in selected:
            value = self.fn(channel, tick) if self.fn else self.values.get(channel, 0.0)
            vals.append((channel, float(value)))
        sample = AnimationSignalSample(tick=tick, values=tuple(vals))
        sample.validate()
        return sample


def engine(binding_set, values=None, fn=None):
    return VisualPropertyBindingEngine(FakeSignalEngine(values, fn), binding_set)


def approx(value):
    return pytest.approx(value, abs=1e-9)


def test_binding_validation_valid():
    VisualBinding(AnimationSignalChannel.BEAT, VisualProperty.SCALE_MULTIPLIER, 0.1).validate()


@pytest.mark.parametrize("kwargs", [
    {"amount": 1.0},
    {"response_gamma": 0.0},
    {"min_signal": -0.1},
    {"min_signal": 0.96},
])
def test_binding_validation_rejects_invalid(kwargs):
    args = dict(channel=AnimationSignalChannel.BEAT, property=VisualProperty.SCALE_MULTIPLIER, amount=0.1)
    args.update(kwargs)
    with pytest.raises(ValueError):
        VisualBinding(**args).validate()


def test_binding_set_signature_deterministic_across_binding_order():
    a=VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.02)
    b=VisualBinding(AnimationSignalChannel.BASS,VisualProperty.SCALE_MULTIPLIER,.05)
    x=VisualBindingSet("same",(a,b)); y=VisualBindingSet("same",(b,a))
    assert x.signature()==y.signature()


def test_signature_changes_on_binding_change():
    x=VisualBindingSet("x",(VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.02),))
    y=VisualBindingSet("x",(VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.03),))
    assert x.signature()!=y.signature()


def test_empty_set_returns_neutral_state():
    state=engine(VisualBindingSet("empty")).state(0)
    assert state==VisualPropertyState.neutral()


def test_subtle_beat_pulse_exact():
    state=engine(core_binding_set(CoreBeatPreset.SUBTLE_BEAT_PULSE),{AnimationSignalChannel.BEAT:1}).state(10)
    assert state.scale_multiplier==approx(1.025)


def test_bass_pulse_exact():
    state=engine(core_binding_set(CoreBeatPreset.BASS_PULSE),{AnimationSignalChannel.BASS:1}).state(10)
    assert state.scale_multiplier==approx(1.06)


def test_strong_punch_emits_three_properties():
    state=engine(core_binding_set(CoreBeatPreset.STRONG_PUNCH),{AnimationSignalChannel.STRONG_BEAT:1}).state(10)
    assert state.scale_multiplier==approx(1.08)
    assert state.zoom_multiplier==approx(1.06)
    assert state.glow_amount==approx(.35)


def test_onset_flash_glow_exact():
    state=engine(core_binding_set(CoreBeatPreset.ONSET_FLASH),{AnimationSignalChannel.ONSET:1}).state(10)
    assert state.glow_amount==approx(.28)


def test_rotation_nudge_exact_and_zero_returns_baseline():
    bs=core_binding_set(CoreBeatPreset.ROTATION_NUDGE)
    assert engine(bs,{AnimationSignalChannel.STRONG_BEAT:1}).state(10).rotation_offset_deg==approx(2)
    assert engine(bs,{AnimationSignalChannel.STRONG_BEAT:0}).state(10).rotation_offset_deg==0


def test_energy_breathe_exact():
    state=engine(core_binding_set(CoreBeatPreset.ENERGY_BREATHE),{AnimationSignalChannel.ENERGY_UP:1}).state(10)
    assert state.scale_multiplier==approx(1.03)
    assert state.glow_amount==approx(.20)


def test_min_signal_gates_response():
    b=VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.1,min_signal=.5)
    assert engine(VisualBindingSet("g",(b,)),{AnimationSignalChannel.BEAT:.49}).state(0).scale_multiplier==1


def test_response_gamma_transfer():
    b=VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.2,response_gamma=2)
    state=engine(VisualBindingSet("g",(b,)),{AnimationSignalChannel.BEAT:.5}).state(0)
    assert state.scale_multiplier==approx(1.05)


def test_multiple_scale_bindings_add_then_clamp():
    bs=VisualBindingSet("many",(
        VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.35),
        VisualBinding(AnimationSignalChannel.BASS,VisualProperty.SCALE_MULTIPLIER,.35),
    ))
    state=engine(bs,{AnimationSignalChannel.BEAT:1,AnimationSignalChannel.BASS:1}).state(0)
    assert state.scale_multiplier==1.35


def test_glow_uses_saturating_add():
    bs=VisualBindingSet("glow",(
        VisualBinding(AnimationSignalChannel.ONSET,VisualProperty.GLOW_AMOUNT,.5),
        VisualBinding(AnimationSignalChannel.ENERGY_UP,VisualProperty.GLOW_AMOUNT,.5),
    ))
    state=engine(bs,{AnimationSignalChannel.ONSET:1,AnimationSignalChannel.ENERGY_UP:1}).state(0)
    assert state.glow_amount==approx(.75)


def test_opacity_multiplier_bounds():
    bs=VisualBindingSet("opacity",(VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.OPACITY_MULTIPLIER,-1.0),))
    assert engine(bs,{AnimationSignalChannel.BEAT:1}).state(0).opacity_multiplier==0


def test_rotation_clamps():
    bs=VisualBindingSet("r",(
        VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.ROTATION_OFFSET_DEG,12),
        VisualBinding(AnimationSignalChannel.BASS,VisualProperty.ROTATION_OFFSET_DEG,12),
    ))
    assert engine(bs,{AnimationSignalChannel.BEAT:1,AnimationSignalChannel.BASS:1}).state(0).rotation_offset_deg==12


@pytest.mark.parametrize("prop,field",[
    (VisualProperty.X_OFFSET_NORMALIZED,"x_offset_normalized"),
    (VisualProperty.Y_OFFSET_NORMALIZED,"y_offset_normalized"),
])
def test_position_offsets_clamp(prop,field):
    bs=VisualBindingSet("p",(
        VisualBinding(AnimationSignalChannel.BEAT,prop,.15),
        VisualBinding(AnimationSignalChannel.BASS,prop,.15),
    ))
    state=engine(bs,{AnimationSignalChannel.BEAT:1,AnimationSignalChannel.BASS:1}).state(0)
    assert getattr(state,field)==.15


def test_center_pivot_preserved_during_scale():
    base=Transform(x=.2,y=.3,width=.4,height=.2,pivot_x=.5,pivot_y=.5)
    state=VisualPropertyState(scale_multiplier=1.25)
    eff=apply_visual_state(base,.8,state)
    assert eff.x+eff.pivot_x*eff.width==approx(base.x+base.pivot_x*base.width)
    assert eff.y+eff.pivot_y*eff.height==approx(base.y+base.pivot_y*base.height)


def test_non_center_pivot_preserved():
    base=Transform(x=.1,y=.2,width=.5,height=.4,pivot_x=.2,pivot_y=.8)
    eff=apply_visual_state(base,1,VisualPropertyState(scale_multiplier=1.1))
    assert eff.x+eff.pivot_x*eff.width==approx(base.x+base.pivot_x*base.width)
    assert eff.y+eff.pivot_y*eff.height==approx(base.y+base.pivot_y*base.height)


def test_apply_does_not_mutate_base_transform():
    base=Transform(x=.1,y=.2,width=.5,height=.4,rotation=5)
    before=vars(base).copy(); apply_visual_state(base,.7,VisualPropertyState(scale_multiplier=1.1,rotation_offset_deg=2))
    assert vars(base)==before


def test_apply_does_not_mutate_base_opacity_value():
    opacity=.7; apply_visual_state(Transform(),opacity,VisualPropertyState(opacity_multiplier=.5)); assert opacity==.7


def test_effective_size_renderer_safe():
    base=Transform(width=2.9,height=2.9)
    eff=apply_visual_state(base,1,VisualPropertyState(scale_multiplier=1.35))
    assert eff.width==3 and eff.height==3


def test_effective_rotation_renderer_safe():
    base=Transform(rotation=179)
    eff=apply_visual_state(base,1,VisualPropertyState(rotation_offset_deg=12))
    assert eff.rotation==180


def test_binding_order_does_not_change_state():
    a=VisualBinding(AnimationSignalChannel.BEAT,VisualProperty.SCALE_MULTIPLIER,.02)
    b=VisualBinding(AnimationSignalChannel.BASS,VisualProperty.SCALE_MULTIPLIER,.06)
    values={AnimationSignalChannel.BEAT:.7,AnimationSignalChannel.BASS:.8}
    assert engine(VisualBindingSet("x",(a,b)),values).state(1)==engine(VisualBindingSet("x",(b,a)),values).state(1)


def test_combined_preset_deterministic_across_set_order():
    a=core_binding_set(CoreBeatPreset.SUBTLE_BEAT_PULSE); b=core_binding_set(CoreBeatPreset.BASS_PULSE)
    assert combine_binding_sets(a,b).signature()==combine_binding_sets(b,a).signature()


def test_signal_sample_is_called_once_for_multiple_bindings_same_channel():
    fake=FakeSignalEngine({AnimationSignalChannel.STRONG_BEAT:1})
    eng=VisualPropertyBindingEngine(fake,core_binding_set(CoreBeatPreset.STRONG_PUNCH))
    eng.state(0); assert fake.sample_calls==1


def test_random_seek_is_deterministic():
    fake=FakeSignalEngine(fn=lambda c,t: ((t%100)/100) if c==AnimationSignalChannel.BEAT else 0)
    eng=VisualPropertyBindingEngine(fake,core_binding_set(CoreBeatPreset.SUBTLE_BEAT_PULSE))
    first=eng.state(77); eng.state(12); second=eng.state(77); assert first==second


def test_zero_signal_exactly_restores_baseline():
    bs=combine_binding_sets(*(core_binding_set(p) for p in CoreBeatPreset))
    state=engine(bs,{}).state(0); base=Transform(x=.2,y=.25,width=.35,height=.4,rotation=7,pivot_x=.3,pivot_y=.6)
    eff=apply_visual_state(base,.63,state)
    assert (eff.x,eff.y,eff.width,eff.height,eff.rotation,eff.opacity)==pytest.approx((base.x,base.y,base.width,base.height,base.rotation,.63))


def test_core_preset_ids_unique():
    ids=[core_binding_set(p).binding_set_id for p in CoreBeatPreset]
    assert len(ids)==len(set(ids))==18
    legacy={
        "subtle_beat_pulse",
        "bass_pulse",
        "strong_punch",
        "onset_flash",
        "rotation_nudge",
        "energy_breathe",
    }
    assert legacy.issubset(set(ids))


def test_layer_compatibility_is_deterministic():
    assert supported_properties_for_layer("song_cover")==supported_properties_for_layer("song_cover")
    assert VisualProperty.ZOOM_MULTIPLIER in supported_properties_for_layer("song_cover")
    assert VisualProperty.ZOOM_MULTIPLIER not in supported_properties_for_layer("spectrum")
    assert supported_properties_for_layer("unknown")==()


def test_unknown_preset_raises_key_error():
    with pytest.raises(KeyError): core_binding_set("not-a-preset")


def test_effective_opacity_clamps_to_one():
    eff=apply_visual_state(Transform(),.9,VisualPropertyState(opacity_multiplier=1.25)); assert eff.opacity==1


def test_offset_is_applied_after_pivot_scale():
    base=Transform(x=.2,y=.3,width=.4,height=.2,pivot_x=.5,pivot_y=.5)
    eff=apply_visual_state(base,1,VisualPropertyState(scale_multiplier=1.1,x_offset_normalized=.1,y_offset_normalized=-.05))
    px=base.x+.5*base.width; py=base.y+.5*base.height
    assert eff.x+.5*eff.width==approx(px+.1)
    assert eff.y+.5*eff.height==approx(py-.05)
