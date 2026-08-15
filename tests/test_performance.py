"""Atmosphere and stall speed, against textbook values.

Stall speed is the first genuinely real number in the tool, and several other
speeds end up limited by it, so it is worth pinning tightly.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerosizer.atmosphere import (
    SEA_LEVEL_ISA,
    SEA_LEVEL_TEMPERATURE,
    atmosphere_at,
    weight,
)
from aerosizer.mass import mass_properties
from aerosizer.performance import STALL_MARGIN_FACTOR, minimum_safe_speed, stall_speed

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
