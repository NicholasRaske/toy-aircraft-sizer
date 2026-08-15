"""Deadlines on range missions, and the wing choice they drive.

A mission with no deadline is flown at minimum drag, which the most efficient
wing always wins. A deadline changes the question: the leg has to be covered
faster, and flying above minimum drag costs a large wing more than a small one,
because parasite drag grows with area and with the square of speed.

That is the only mechanism in the tool by which a less efficient wing can be
the right answer, so it is worth pinning carefully.
"""

from __future__ import annotations

import pytest

from aerosizer import Requirements, load_catalog, recommend
from aerosizer.mission import (
    NO_DEADLINE,
    CruiseSegment,
    OneWayRangeMission,
    ReturnRangeMission,
)

SIXTY_KILOMETRES = 60_000.0


def _recommend_within(catalog, minutes: float, distance: float = SIXTY_KILOMETRES):
    return recommend(
        Requirements(
            mission=OneWayRangeMission(distance, minutes * 60.0),
            payload_mass=4.0,
        ),
        catalog,
    )


def test_a_mission_without_a_deadline_asks_for_no_particular_speed():
    profile = OneWayRangeMission(SIXTY_KILOMETRES).profile()

    assert profile[0].required_speed == 0.0


def test_a_deadline_becomes_a_required_speed():
    mission = OneWayRangeMission(SIXTY_KILOMETRES, time_limit=3600.0)

    assert mission.profile()[0].required_speed == pytest.approx(SIXTY_KILOMETRES / 3600.0)


def test_a_return_trip_paces_both_legs_against_the_whole_sortie():
    """The deadline covers there and back, so each leg is flown at the pace
    the round trip needs, not the pace one leg would need."""
    mission = ReturnRangeMission(30_000.0, time_limit=3600.0)
    outbound, inbound = mission.profile()

    assert outbound.required_speed == pytest.approx(60_000.0 / 3600.0)
    assert outbound == inbound


def test_no_deadline_is_the_default():
    assert OneWayRangeMission(1000.0).time_limit is NO_DEADLINE
    assert ReturnRangeMission(1000.0).time_limit is NO_DEADLINE


def test_a_slack_deadline_does_not_change_how_the_aircraft_is_flown(catalog):
    """Below the minimum drag speed, a deadline should be invisible."""
    relaxed = _recommend_within(catalog, minutes=120)
    unhurried = recommend(
        Requirements(mission=OneWayRangeMission(SIXTY_KILOMETRES), payload_mass=4.0),
        catalog,
    )

    assert relaxed.configuration.wing.name == unhurried.configuration.wing.name
    assert relaxed.chosen.flight.outcomes[0].airspeed == pytest.approx(
        unhurried.chosen.flight.outcomes[0].airspeed, rel=1e-3
    )


def test_a_tighter_deadline_never_costs_less_fuel(catalog):
    previous = 0.0
    for minutes in (120, 60, 45, 35, 30):
        burned = _recommend_within(catalog, minutes).chosen.flight.total_fuel

        assert burned >= previous
        previous = burned


def test_a_tight_deadline_switches_to_the_faster_wing(catalog):
    """The efficient wing wins when there is time; the fast one when there is not.

    This is what makes the catalogue worth having more than one wing in.
    """
    unhurried = _recommend_within(catalog, minutes=120)
    hurried = _recommend_within(catalog, minutes=28)

    assert unhurried.configuration.wing.name == "Surveyor"
    assert hurried.configuration.wing.name == "Dash"


def test_the_aircraft_flies_the_pace_it_was_asked_for(catalog):
    recommendation = _recommend_within(catalog, minutes=40)

    required = SIXTY_KILOMETRES / (40 * 60.0)
    assert recommendation.chosen.flight.outcomes[0].airspeed == pytest.approx(required, rel=0.01)


def test_an_impossible_deadline_is_flown_as_fast_as_the_aircraft_can(catalog):
    """Capped at level flight, so the leg simply takes longer than asked.

    The mean speed flown edges just above the maximum quoted in ``Results``,
    and should: that figure is for takeoff mass, and the aircraft gets lighter
    and therefore faster as it burns fuel.

    Reported rather than refused. Deciding what to do about a missed deadline
    is the gate's job, and there is not one yet.
    """
    recommendation = _recommend_within(catalog, minutes=5)
    flown = recommendation.chosen.flight.outcomes[0].airspeed
    at_takeoff = recommendation.results.envelope.max_level_speed.value

    assert flown < SIXTY_KILOMETRES / (5 * 60.0), "the deadline should have been missed"
    assert flown >= at_takeoff, "should be flying flat out"
    assert flown < at_takeoff * 1.05, "but not far beyond the takeoff limit"


def test_a_cruise_segment_defaults_to_no_required_speed():
    assert CruiseSegment(1000.0).required_speed == 0.0
