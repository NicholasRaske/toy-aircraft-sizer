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

from dataclasses import fields, replace

import pytest

from aerosizer import Configuration, Fidelity, analyze


def test_every_result_field_is_populated(baseline_configuration):
    results = analyze(baseline_configuration)

    # Results are total by design: no field means "not computed yet".
    for field in fields(results):
        assert getattr(results, field.name) is not None


def test_placeholder_model_declares_itself(baseline_configuration):
    assert analyze(baseline_configuration).fidelity is Fidelity.PLACEHOLDER


def test_more_wing_area_lowers_stall_speed(baseline_configuration):
    enlarged = _with_wing_change(
        baseline_configuration,
        reference_area=baseline_configuration.wing.reference_area * 1.5,
    )

    assert analyze(enlarged).stall_speed < analyze(baseline_configuration).stall_speed


def test_higher_aspect_ratio_improves_lift_to_drag(baseline_configuration):
    slender = _with_wing_change(
        baseline_configuration,
        span=baseline_configuration.wing.span * 1.2,
    )

    assert analyze(slender).lift_to_drag_max > analyze(baseline_configuration).lift_to_drag_max


def test_higher_aspect_ratio_improves_endurance(baseline_configuration):
    slender = _with_wing_change(
        baseline_configuration,
        span=baseline_configuration.wing.span * 1.2,
    )

    assert analyze(slender).endurance > analyze(baseline_configuration).endurance


def test_lower_aspect_ratio_raises_top_speed(baseline_configuration):
    stubby = _with_wing_change(
        baseline_configuration,
        span=baseline_configuration.wing.span * 0.8,
    )

    assert analyze(stubby).max_level_speed > analyze(baseline_configuration).max_level_speed


def test_analysis_is_deterministic(baseline_configuration):
    assert analyze(baseline_configuration) == analyze(baseline_configuration)


def test_extending_the_tail_lengthens_the_tail_arm(baseline_configuration):
    extended = replace(baseline_configuration, tail_extension=0.2)

    assert extended.tail_arm == pytest.approx(baseline_configuration.tail_arm + 0.2)


def _with_wing_change(configuration: Configuration, **changes) -> Configuration:
    return replace(configuration, wing=replace(configuration.wing, **changes))
