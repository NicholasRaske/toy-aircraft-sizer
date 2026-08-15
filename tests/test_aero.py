"""The drag polar, against hand-computed component buildup.

Surveyor + Standard + fuselage:

    flat plate area = 0.020 + 0.008 + 0.028 = 0.056 m^2
    CD0 = 0.056 / 1.6 = 0.0350
    AR  = 3.8^2 / 1.6 = 9.0250
    e   = 1.78 (1 - 0.045 x 9.025^0.68) - 0.64 = 0.78245
    k   = 1 / (pi x 9.025 x 0.78245) = 0.04507
    L/D = 1 / (2 sqrt(0.04507 x 0.0350)) = 12.59
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from aerosizer.aero import (
    MAXIMUM_OSWALD_EFFICIENCY,
    drag_polar,
    induced_drag_factor,
    oswald_efficiency,
)

EXPECTED_ZERO_LIFT_DRAG = 0.0350
EXPECTED_INDUCED_FACTOR = 0.04507
EXPECTED_OSWALD_EFFICIENCY = 0.78245
EXPECTED_LIFT_TO_DRAG_MAX = 12.59


def test_parasite_drag_is_built_up_from_the_parts(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    assert polar.zero_lift_drag_coefficient == pytest.approx(EXPECTED_ZERO_LIFT_DRAG, abs=1e-4)


def test_induced_drag_factor_matches_hand_calculation(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    assert polar.induced_drag_factor == pytest.approx(EXPECTED_INDUCED_FACTOR, rel=1e-3)


def test_oswald_efficiency_matches_hand_calculation(baseline_configuration):
    aspect_ratio = baseline_configuration.wing.aspect_ratio

    assert oswald_efficiency(aspect_ratio) == pytest.approx(EXPECTED_OSWALD_EFFICIENCY, abs=1e-4)


def test_oswald_efficiency_never_exceeds_unity():
    # Raymer's estimate rises above 1.0 for very low aspect ratios, which no
    # real wing achieves.
    for aspect_ratio in (1.0, 2.0, 3.0, 6.0, 12.0, 20.0):
        efficiency = oswald_efficiency(aspect_ratio)
        assert 0.0 < efficiency <= MAXIMUM_OSWALD_EFFICIENCY


def test_lift_to_drag_max_matches_the_closed_form(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    closed_form = 1.0 / (
        2.0 * math.sqrt(polar.induced_drag_factor * polar.zero_lift_drag_coefficient)
    )
    assert polar.lift_to_drag_max == pytest.approx(closed_form)
    assert polar.lift_to_drag_max == pytest.approx(EXPECTED_LIFT_TO_DRAG_MAX, abs=0.01)


def test_drag_at_zero_lift_is_the_parasite_drag(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    assert polar.drag_coefficient(0.0) == pytest.approx(polar.zero_lift_drag_coefficient)


def test_drag_rises_with_the_square_of_lift(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    lift_induced_at_one = polar.drag_coefficient(1.0) - polar.zero_lift_drag_coefficient
    lift_induced_at_two = polar.drag_coefficient(2.0) - polar.zero_lift_drag_coefficient

    assert lift_induced_at_two == pytest.approx(4.0 * lift_induced_at_one)


def test_higher_aspect_ratio_reduces_induced_drag():
    assert induced_drag_factor(12.0) < induced_drag_factor(6.0)


def test_a_smaller_wing_raises_the_drag_coefficient(baseline_configuration):
    """CD0 is normalised by wing area, so it is not a measure of total drag.

    Fitting a smaller wing makes the aircraft no draggier in newtons, but its
    drag coefficient rises because the reference it is divided by shrank.
    """
    wing = baseline_configuration.wing
    smaller = replace(
        baseline_configuration,
        wing=replace(wing, reference_area=wing.reference_area / 2.0),
    )

    smaller_cd0 = drag_polar(smaller).zero_lift_drag_coefficient
    assert smaller_cd0 > drag_polar(baseline_configuration).zero_lift_drag_coefficient


def test_a_draggier_empennage_raises_parasite_drag(baseline_configuration):
    empennage = baseline_configuration.empennage
    draggier = replace(
        baseline_configuration,
        empennage=replace(
            empennage,
            equivalent_flat_plate_area=empennage.equivalent_flat_plate_area * 2.0,
        ),
    )

    baseline_cd0 = drag_polar(baseline_configuration).zero_lift_drag_coefficient
    assert drag_polar(draggier).zero_lift_drag_coefficient > baseline_cd0
