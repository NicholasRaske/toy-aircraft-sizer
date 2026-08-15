"""Atmosphere and stall speed, against textbook values.

Stall speed is the first genuinely real number in the tool, and several other
speeds end up limited by it, so it is worth pinning tightly.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from aerosizer.aero import drag_polar
from aerosizer.atmosphere import (
    SEA_LEVEL_ISA,
    SEA_LEVEL_TEMPERATURE,
    atmosphere_at,
    weight,
)
from aerosizer.mass import mass_properties
from aerosizer.performance import (
    LIMITED_BY_ENGINE_POWER,
    LIMITED_BY_INSUFFICIENT_POWER,
    LIMITED_BY_MINIMUM_DRAG,
    LIMITED_BY_STALL_MARGIN,
    STALL_MARGIN_FACTOR,
    minimum_safe_speed,
    power_available,
    power_required,
    speed_envelope,
    stall_speed,
)

# Surveyor at the baseline 21.4 kg, sea level ISA:
#   W = 21.4 x 9.80665 = 209.86 N
#   Vs = sqrt(2 x 209.86 / (1.225 x 1.6 x 1.4)) = 12.37 m/s
EXPECTED_BASELINE_STALL_SPEED = 12.37


def test_sea_level_density_matches_the_standard_atmosphere():
    assert SEA_LEVEL_ISA.density == pytest.approx(1.225, abs=1e-3)
    assert SEA_LEVEL_ISA.temperature == pytest.approx(SEA_LEVEL_TEMPERATURE)
    assert SEA_LEVEL_ISA.pressure == pytest.approx(101325.0)


def test_density_falls_with_elevation():
    # Roughly 10% down at 1000 m is the standard rule of thumb.
    thinner = atmosphere_at(1000.0)

    assert thinner.density < SEA_LEVEL_ISA.density
    assert thinner.density == pytest.approx(1.112, abs=5e-3)


def test_a_hot_day_thins_the_air():
    hot = atmosphere_at(0.0, sea_level_temperature=SEA_LEVEL_TEMPERATURE + 20.0)

    assert hot.density < SEA_LEVEL_ISA.density


def test_weight_is_mass_times_standard_gravity():
    assert weight(21.4) == pytest.approx(209.86, abs=0.01)


def test_stall_speed_matches_hand_calculation(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass

    speed = stall_speed(mass, baseline_configuration.wing, SEA_LEVEL_ISA)
    assert speed == pytest.approx(EXPECTED_BASELINE_STALL_SPEED, abs=0.01)


def test_stall_speed_rises_with_the_square_root_of_mass(baseline_configuration):
    wing = baseline_configuration.wing

    single = stall_speed(20.0, wing, SEA_LEVEL_ISA)
    quadrupled = stall_speed(80.0, wing, SEA_LEVEL_ISA)

    assert quadrupled == pytest.approx(2.0 * single)


def test_a_bigger_wing_stalls_slower(baseline_configuration):
    wing = baseline_configuration.wing
    larger = replace(wing, reference_area=wing.reference_area * 2.0)

    assert stall_speed(21.4, larger, SEA_LEVEL_ISA) < stall_speed(21.4, wing, SEA_LEVEL_ISA)


def test_thinner_air_raises_stall_speed(baseline_configuration):
    wing = baseline_configuration.wing
    altitude = atmosphere_at(1500.0)

    assert stall_speed(21.4, wing, altitude) > stall_speed(21.4, wing, SEA_LEVEL_ISA)


def test_the_slowest_instructable_speed_keeps_a_margin_over_stall():
    assert minimum_safe_speed(12.0) == pytest.approx(12.0 * STALL_MARGIN_FACTOR)
    assert STALL_MARGIN_FACTOR > 1.0


def test_searched_speeds_match_their_closed_forms(baseline_configuration):
    """The numerical search must agree with the textbook equations.

    Those equations are the oracle, not the implementation: they assume a
    parabolic polar and constant propeller efficiency, and both assumptions
    end when tabulated polars arrive.

        V_md = sqrt(2W / rho S) (k / CD0)^(1/4)
        V_mp = V_md / 3^(1/4)
    """
    mass = mass_properties(baseline_configuration).all_up_mass
    polar = drag_polar(baseline_configuration)
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    reference_speed = math.sqrt(
        2.0 * weight(mass) / (SEA_LEVEL_ISA.density * polar.reference_area)
    )
    expected_min_drag = reference_speed * (
        polar.induced_drag_factor / polar.zero_lift_drag_coefficient
    ) ** 0.25

    assert envelope.min_drag_speed == pytest.approx(expected_min_drag, rel=0.005)
    assert envelope.min_power_speed == pytest.approx(expected_min_drag * 3.0**-0.25, rel=0.005)


def test_minimum_drag_speed_achieves_the_polar_best_lift_to_drag(baseline_configuration):
    """Ties the searched speed back to the polar it was searched on."""
    mass = mass_properties(baseline_configuration).all_up_mass
    polar = drag_polar(baseline_configuration)
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    expected_power = weight(mass) * envelope.min_drag_speed / polar.lift_to_drag_max
    actual_power = power_required(polar, mass, SEA_LEVEL_ISA, envelope.min_drag_speed)

    assert actual_power == pytest.approx(expected_power, rel=0.005)


def test_loiter_is_stall_limited_rather_than_power_limited(baseline_configuration):
    """The finding that motivated carrying a reason on every speed.

    Minimum-power flight at this wing loading needs a lift coefficient beyond
    what the wing can reach, so the textbook best-endurance speed is
    unattainable. Reporting it would promise an endurance the aircraft cannot
    fly -- quietly, and by several minutes.
    """
    mass = mass_properties(baseline_configuration).all_up_mass
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    assert envelope.min_power_speed < envelope.stall_speed
    assert envelope.loiter_speed.limited_by == LIMITED_BY_STALL_MARGIN
    assert envelope.loiter_speed.value == pytest.approx(minimum_safe_speed(envelope.stall_speed))
    assert envelope.loiter_speed.margin == 0.0


def test_cruise_is_limited_by_drag_not_stall(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    assert envelope.cruise_speed.limited_by == LIMITED_BY_MINIMUM_DRAG
    assert envelope.cruise_speed.margin > 0.0


def test_the_envelope_is_ordered(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    assert envelope.stall_speed < envelope.loiter_speed.value
    assert envelope.loiter_speed.value <= envelope.cruise_speed.value
    assert envelope.cruise_speed.value < envelope.max_level_speed.value


def test_top_speed_is_set_by_available_power(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    polar = drag_polar(baseline_configuration)
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    available = power_available(baseline_configuration.engine, SEA_LEVEL_ISA)
    at_top_speed = power_required(polar, mass, SEA_LEVEL_ISA, envelope.max_level_speed.value)

    assert envelope.max_level_speed.limited_by == LIMITED_BY_ENGINE_POWER
    assert at_top_speed == pytest.approx(available, rel=0.005)


def test_an_underpowered_aircraft_reports_that_it_cannot_hold_level_flight(
    baseline_configuration,
):
    """Reported, not refused. Excluding it is the flyability gate's job."""
    feeble = replace(
        baseline_configuration,
        engine=replace(baseline_configuration.engine, max_shaft_power=50.0),
    )
    mass = mass_properties(feeble).all_up_mass

    envelope = speed_envelope(feeble, mass, SEA_LEVEL_ISA)
    assert envelope.max_level_speed.limited_by == LIMITED_BY_INSUFFICIENT_POWER


def test_thinner_air_narrows_the_envelope(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    altitude = atmosphere_at(2000.0)

    high = speed_envelope(baseline_configuration, mass, altitude)
    low = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    assert high.stall_speed > low.stall_speed
    assert high.max_level_speed.value < low.max_level_speed.value


def test_a_heavier_aircraft_needs_more_power(baseline_configuration):
    polar = drag_polar(baseline_configuration)

    light = power_required(polar, 18.0, SEA_LEVEL_ISA, 20.0)
    heavy = power_required(polar, 26.0, SEA_LEVEL_ISA, 20.0)

    assert heavy > light
