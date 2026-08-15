"""The mission model: shapes only, no physics yet.

These tests pin the decisions taken in review -- that Loiter returns to its
launch point, that Return Range flies the distance twice, and that a mode
declares the numbers it needs rather than an interface knowing them.
"""

from __future__ import annotations

import pytest

from aerosizer.mission import (
    PAYLOAD_FIELD,
    CruiseSegment,
    FlightMode,
    LoiterMission,
    LoiterSegment,
    OneWayRangeMission,
    ReturnRangeMission,
    default_values,
    input_fields,
    mission_fields,
    mission_from,
    mode_of,
    total_distance,
    total_loiter_time,
)


def test_loiter_flies_out_holds_station_and_returns():
    mission = LoiterMission(transit_distance=10_000.0, station_time=3600.0)

    profile = mission.profile()
    assert profile == (
        CruiseSegment(10_000.0),
        LoiterSegment(3600.0),
        CruiseSegment(10_000.0),
    )


def test_loiter_covers_the_transit_distance_twice():
    mission = LoiterMission(transit_distance=10_000.0, station_time=3600.0)

    assert total_distance(mission.profile()) == pytest.approx(20_000.0)
    assert total_loiter_time(mission.profile()) == pytest.approx(3600.0)


def test_one_way_range_does_not_come_back():
    mission = OneWayRangeMission(distance=50_000.0)

    assert mission.profile() == (CruiseSegment(50_000.0),)
    assert total_distance(mission.profile()) == pytest.approx(50_000.0)


def test_return_range_flies_the_distance_twice():
    mission = ReturnRangeMission(distance=30_000.0)

    assert mission.profile() == (CruiseSegment(30_000.0), CruiseSegment(30_000.0))
    assert total_distance(mission.profile()) == pytest.approx(60_000.0)


def test_no_profile_holds_station_unless_it_was_asked_to():
    for mission in (OneWayRangeMission(1000.0), ReturnRangeMission(1000.0)):
        assert total_loiter_time(mission.profile()) == 0.0


@pytest.mark.parametrize("mode", list(FlightMode))
def test_a_mission_knows_which_mode_produced_it(mode):
    mission = mission_from(mode, default_values(mode))

    assert mode_of(mission) is mode


@pytest.mark.parametrize("mode", list(FlightMode))
def test_every_mode_declares_the_numbers_it_needs(mode):
    fields = input_fields(mode)

    assert fields, "a mode must ask for something"
    assert fields[-1] is PAYLOAD_FIELD, "payload is common to every mode, and asked for last"


@pytest.mark.parametrize("mode", list(FlightMode))
def test_declared_fields_match_the_mission_they_build(mode):
    """A field key is the attribute name, so an interface can read it back."""
    mission = mission_from(mode, default_values(mode))

    for field in mission_fields(mode):
        assert hasattr(mission, field.key)


@pytest.mark.parametrize("mode", list(FlightMode))
def test_defaults_sit_within_their_own_bounds(mode):
    for field in input_fields(mode):
        assert field.minimum <= field.default <= field.maximum
        assert field.step > 0.0
        assert field.step <= field.maximum - field.minimum
