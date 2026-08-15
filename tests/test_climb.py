"""Climb performance from excess power."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerosizer.atmosphere import SEA_LEVEL_ISA, atmosphere_at, weight
from aerosizer.mass import mass_properties
from aerosizer.performance import (
    LIMITED_BY_INSUFFICIENT_POWER,
    best_climb,
    minimum_power_speed,
    power_available,
    power_required,
    speed_envelope,
)
from aerosizer.aero import drag_polar


def test_climb_rate_is_the_excess_power_divided_by_weight(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    polar = drag_polar(baseline_configuration)

    climb = best_climb(baseline_configuration, mass, SEA_LEVEL_ISA)
    excess = power_available(baseline_configuration.engine, SEA_LEVEL_ISA) - power_required(
        polar, mass, SEA_LEVEL_ISA, climb.speed_for_best_rate.value
    )

    assert climb.best_rate == pytest.approx(excess / weight(mass))
    assert climb.best_rate > 0.0


def test_best_climb_speed_coincides_with_minimum_power_speed(baseline_configuration):
    """Not a bug, and worth pinning so it is noticed when it stops being true.

    With propeller efficiency constant, power available does not vary with
    airspeed, so the greatest excess sits wherever the requirement is least.
    The two speeds separate once efficiency becomes a function of airspeed.
    """
    mass = mass_properties(baseline_configuration).all_up_mass
    envelope = speed_envelope(baseline_configuration, mass, SEA_LEVEL_ISA)

    climb = best_climb(baseline_configuration, mass, SEA_LEVEL_ISA)
    assert climb.speed_for_best_rate.value == pytest.approx(
        envelope.loiter_speed.value, rel=1e-6
    )


def test_a_heavier_aircraft_climbs_worse(baseline_configuration):
    light = best_climb(baseline_configuration, 18.0, SEA_LEVEL_ISA)
    heavy = best_climb(baseline_configuration, 26.0, SEA_LEVEL_ISA)

    assert heavy.best_rate < light.best_rate


def test_thinner_air_reduces_the_climb_rate(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass

    high = best_climb(baseline_configuration, mass, atmosphere_at(2500.0))
    low = best_climb(baseline_configuration, mass, SEA_LEVEL_ISA)

    assert high.best_rate < low.best_rate


def test_an_underpowered_aircraft_cannot_climb(baseline_configuration):
    feeble = replace(
        baseline_configuration,
        engine=replace(baseline_configuration.engine, max_shaft_power=50.0),
    )
    mass = mass_properties(feeble).all_up_mass

    assert best_climb(feeble, mass, SEA_LEVEL_ISA).best_rate < 0.0
    envelope = speed_envelope(feeble, mass, SEA_LEVEL_ISA)
    assert envelope.max_level_speed.limited_by == LIMITED_BY_INSUFFICIENT_POWER


def test_minimum_power_speed_is_where_the_requirement_is_least(baseline_configuration):
    polar = drag_polar(baseline_configuration)
    best = minimum_power_speed(polar, 21.4, SEA_LEVEL_ISA)

    at_best = power_required(polar, 21.4, SEA_LEVEL_ISA, best)
    for offset in (-2.0, -0.5, 0.5, 2.0):
        assert power_required(polar, 21.4, SEA_LEVEL_ISA, best + offset) >= at_best
