"""Mass and balance, checked against hand-computed moments.

The catalogue numbers are small and round precisely so that the centre of
gravity can be worked out on paper and compared. If these ever disagree with
the arithmetic in the comments, the arithmetic wins until proven otherwise.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerosizer.mass import FUEL, PAYLOAD, mass_items, mass_properties

# Surveyor + Standard, boom retracted, 4.0 kg payload, 2.0 kg fuel.
#
#   fuselage   8.5 kg @ 0.75 m = 6.375
#   engine     2.6 kg @ 0.18 m = 0.468
#   wing       3.6 kg @ 0.62 m = 2.232
#   empennage  1.1 kg @ 1.85 m = 2.035
#   boom       0.0 kg          = 0.000
#   payload    4.0 kg @ 0.55 m = 2.200
#   fuel       2.0 kg @ 0.70 m = 1.400
#                               -------
#   21.8 kg                      14.710 kg m  ->  CG 0.6748 m
EXPECTED_EMPTY_MASS = 15.8
EXPECTED_ALL_UP_MASS = 21.8
EXPECTED_CENTRE_OF_GRAVITY = 0.6748


def test_all_up_mass_is_the_sum_of_its_parts(baseline_configuration):
    properties = mass_properties(baseline_configuration)

    assert properties.empty_mass == pytest.approx(EXPECTED_EMPTY_MASS)
    assert properties.all_up_mass == pytest.approx(EXPECTED_ALL_UP_MASS)
    assert properties.all_up_mass == pytest.approx(
        properties.empty_mass + properties.payload_mass + properties.fuel_mass
    )


def test_centre_of_gravity_matches_hand_computed_moments(baseline_configuration):
    properties = mass_properties(baseline_configuration)

    assert properties.centre_of_gravity_station == pytest.approx(
        EXPECTED_CENTRE_OF_GRAVITY, abs=1e-4
    )


def test_every_part_contributes_exactly_once(baseline_configuration):
    items = mass_items(baseline_configuration)
    names = [item.name for item in items]

    assert len(names) == len(set(names))
    assert PAYLOAD in names
    assert FUEL in names
    assert baseline_configuration.wing.name in names
    assert baseline_configuration.empennage.name in names


def test_the_empty_aircraft_excludes_payload_and_fuel(baseline_configuration):
    stripped = replace(baseline_configuration, payload_mass=0.0, fuel_mass=0.0)
    properties = mass_properties(stripped)

    assert properties.all_up_mass == pytest.approx(properties.empty_mass)


def test_extending_the_tail_moves_the_centre_of_gravity_aft(baseline_configuration):
    extended = replace(baseline_configuration, tail_extension=0.4)

    baseline_cg = mass_properties(baseline_configuration).centre_of_gravity_station
    assert mass_properties(extended).centre_of_gravity_station > baseline_cg


def test_extending_the_tail_adds_boom_mass(baseline_configuration):
    extended = replace(baseline_configuration, tail_extension=0.4)
    boom = baseline_configuration.fuselage.tail_boom

    added = (
        mass_properties(extended).empty_mass
        - mass_properties(baseline_configuration).empty_mass
    )
    assert added == pytest.approx(boom.mass_per_metre * 0.4)


def test_burning_fuel_moves_the_centre_of_gravity(baseline_configuration):
    """The tank sits aft of the centre of gravity, so emptying it trims nose-down.

    Which way it moves is a property of where the tank is, not a universal
    truth -- this test exists to catch a sign error, and would need rewriting
    if the tank ever moved forward of the balance point.
    """
    fuselage = baseline_configuration.fuselage
    full = mass_properties(baseline_configuration)
    assert fuselage.fuel_tank_station > full.centre_of_gravity_station

    dry = mass_properties(replace(baseline_configuration, fuel_mass=0.0))
    assert dry.centre_of_gravity_station < full.centre_of_gravity_station


def test_a_heavier_payload_moves_the_centre_of_gravity_toward_the_bay(
    baseline_configuration,
):
    fuselage = baseline_configuration.fuselage
    light = mass_properties(baseline_configuration)
    assert fuselage.payload_station < light.centre_of_gravity_station

    heavy = mass_properties(replace(baseline_configuration, payload_mass=8.0))
    assert heavy.centre_of_gravity_station < light.centre_of_gravity_station
