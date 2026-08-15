"""Properties of the forward model.

These are deliberately written as directional and structural assertions rather
than value assertions. A test that says "more wing area lowers the stall
speed" is true of the placeholder model, will still be true of the real
formula at B2, and will still be true once tabulated polars land at T5 -- so
it pins the domain logic while every implementation underneath it churns.

Value assertions against hand calculations arrive alongside the physics they
check.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace

import pytest

from aerosizer import Configuration, Fidelity, analyze


def test_every_result_field_is_populated(baseline_configuration):
    results = analyze(baseline_configuration)

    # Results are total by design, all the way down the tree: no field means
    # "not computed yet".
    for path, value in _all_leaf_values(results):
        assert value is not None, f"{path} is not populated"


def test_every_speed_carries_the_reason_it_is_limited(baseline_configuration):
    envelope = analyze(baseline_configuration).envelope

    for speed in (envelope.loiter_speed, envelope.cruise_speed, envelope.max_level_speed):
        assert speed.limited_by, "a limited speed must say what limits it"


def test_placeholder_model_declares_itself(baseline_configuration):
    assert analyze(baseline_configuration).fidelity is Fidelity.PLACEHOLDER


def test_more_wing_area_lowers_stall_speed(baseline_configuration):
    enlarged = _with_wing_change(
        baseline_configuration,
        reference_area=baseline_configuration.wing.reference_area * 1.5,
    )

    enlarged_stall = analyze(enlarged).envelope.stall_speed
    assert enlarged_stall < analyze(baseline_configuration).envelope.stall_speed


def test_higher_aspect_ratio_improves_lift_to_drag(baseline_configuration):
    slender = _with_wing_change(
        baseline_configuration,
        span=baseline_configuration.wing.span * 1.2,
    )

    assert analyze(slender).lift_to_drag_max > analyze(baseline_configuration).lift_to_drag_max


def test_lower_aspect_ratio_lowers_top_speed(baseline_configuration):
    """A stubbier wing of the same area is slower flat out, not faster.

    The placeholder model asserted the opposite and this test was written to
    match it. Shortening the span at constant area raises the induced drag
    factor and leaves parasite drag alone, so the aircraft is worse
    everywhere. The intuition that low aspect ratio means fast comes from
    fitting a *smaller* wing, which is a different change entirely.
    """
    stubby = _with_wing_change(
        baseline_configuration,
        span=baseline_configuration.wing.span * 0.8,
    )

    stubby_top_speed = analyze(stubby).envelope.max_level_speed.value
    assert stubby_top_speed < analyze(baseline_configuration).envelope.max_level_speed.value


def test_analysis_is_deterministic(baseline_configuration):
    assert analyze(baseline_configuration) == analyze(baseline_configuration)


def test_extending_the_tail_lengthens_the_tail_arm(baseline_configuration):
    extended = replace(baseline_configuration, tail_extension=0.2)

    assert extended.tail_arm == pytest.approx(baseline_configuration.tail_arm + 0.2)


def _with_wing_change(configuration: Configuration, **changes) -> Configuration:
    return replace(configuration, wing=replace(configuration.wing, **changes))


def _all_leaf_values(record, prefix: str = ""):
    """Walk a nested dataclass, yielding every leaf and its dotted path."""
    for field in fields(record):
        value = getattr(record, field.name)
        path = f"{prefix}{field.name}"
        if is_dataclass(value):
            yield from _all_leaf_values(value, f"{path}.")
        else:
            yield path, value
