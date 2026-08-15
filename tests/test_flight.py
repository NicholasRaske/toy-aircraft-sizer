"""Flying a profile, and sizing the fuel it needs.

The properties here are the ones that must survive every later change of
fidelity: that segments account for themselves, that the integration has
converged, and that more mission never costs less fuel.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerosizer.aero import drag_polar
from aerosizer.atmosphere import SEA_LEVEL_ISA
from aerosizer.flight import SUB_STEPS_PER_SEGMENT, fly, fuel_flow
from aerosizer.fuel import (
    GRADUATION_VOLUME,
    PETROL_DENSITY,
    mass_for_volume,
    size_fuel,
    volume_for_mass,
)
from aerosizer.mass import mass_properties
from aerosizer.mission import (
    CruiseSegment,
    LoiterMission,
    LoiterSegment,
    OneWayRangeMission,
    ReturnRangeMission,
)
from aerosizer.performance import cruise_airspeed, loiter_airspeed

ONE_HOUR = 3600.0
TEN_KILOMETRES = 10_000.0


def _sized(configuration, mission):
    """Configuration carrying exactly the fuel its mission needs."""
    requirement = size_fuel(replace(configuration, fuel_mass=0.0), mission.profile())
    return replace(configuration, fuel_mass=requirement.mass), requirement


# --------------------------------------------------------------- flying


def test_each_segment_accounts_for_itself(baseline_configuration):
    mission = LoiterMission(TEN_KILOMETRES, ONE_HOUR)
    log = fly(baseline_configuration, mission.profile())

    assert len(log.outcomes) == 3
    assert log.total_fuel == pytest.approx(sum(o.fuel_burned for o in log.outcomes))
    assert log.total_duration == pytest.approx(sum(o.duration for o in log.outcomes))


def test_mass_decreases_monotonically_through_the_flight(baseline_configuration):
    mission = LoiterMission(TEN_KILOMETRES, ONE_HOUR)
    log = fly(baseline_configuration, mission.profile())

    for outcome in log.outcomes:
        assert outcome.mass_at_end <= outcome.mass_at_start

    for earlier, later in zip(log.outcomes, log.outcomes[1:]):
        assert later.mass_at_start == pytest.approx(earlier.mass_at_end)


def test_a_cruise_segment_covers_the_distance_it_was_given(baseline_configuration):
    mission = OneWayRangeMission(50_000.0)
    log = fly(baseline_configuration, mission.profile())

    assert log.total_distance == pytest.approx(50_000.0, rel=1e-3)


def test_a_loiter_segment_lasts_as_long_as_it_was_given(baseline_configuration):
    log = fly(baseline_configuration, (LoiterSegment(ONE_HOUR),))

    assert log.total_duration == pytest.approx(ONE_HOUR)


def test_cruise_and_loiter_are_flown_at_different_speeds(baseline_configuration):
    """Cover ground cheaply per metre; hold station cheaply per second."""
    log = fly(
        baseline_configuration,
        (CruiseSegment(TEN_KILOMETRES), LoiterSegment(ONE_HOUR)),
    )
    cruise, loiter = log.outcomes

    assert cruise.airspeed > loiter.airspeed


def test_segment_speeds_match_the_performance_model(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass
    log = fly(baseline_configuration, (CruiseSegment(1000.0),))

    # A short leg burns almost nothing, so the mean speed should be the
    # take-off cruise speed.
    expected = cruise_airspeed(baseline_configuration, mass, SEA_LEVEL_ISA).value
    assert log.outcomes[0].airspeed == pytest.approx(expected, rel=1e-3)


def test_a_heavier_aircraft_burns_more_over_the_same_route(baseline_configuration):
    profile = OneWayRangeMission(50_000.0).profile()

    light = fly(replace(baseline_configuration, payload_mass=1.0), profile)
    heavy = fly(replace(baseline_configuration, payload_mass=7.0), profile)

    assert heavy.total_fuel > light.total_fuel


def test_the_flight_reports_whether_the_fuel_aboard_was_enough(baseline_configuration):
    profile = OneWayRangeMission(200_000.0).profile()

    assert not fly(replace(baseline_configuration, fuel_mass=0.05), profile).completed
    assert fly(replace(baseline_configuration, fuel_mass=3.0), profile).completed


def test_fuel_flow_follows_shaft_power(baseline_configuration):
    polar = drag_polar(baseline_configuration)
    engine = baseline_configuration.engine

    flow = fuel_flow(polar, engine, 21.4, SEA_LEVEL_ISA, 16.0)
    assert flow > 0.0

    # Double the specific consumption, double the flow.
    thirsty = replace(
        engine,
        best_specific_fuel_consumption=engine.best_specific_fuel_consumption * 2.0,
    )
    assert fuel_flow(polar, thirsty, 21.4, SEA_LEVEL_ISA, 16.0) == pytest.approx(2.0 * flow)


# ---------------------------------------------------------- integration


def test_halving_the_step_barely_changes_the_answer(baseline_configuration, monkeypatch):
    """The integration must have converged, not merely run.

    If the answer moves when the step shrinks, the step was too coarse and
    every fuel figure is a function of an arbitrary constant.
    """
    import aerosizer.flight as flight_module

    profile = LoiterMission(TEN_KILOMETRES, 2 * ONE_HOUR).profile()
    coarse = fly(baseline_configuration, profile).total_fuel

    monkeypatch.setattr(flight_module, "SUB_STEPS_PER_SEGMENT", SUB_STEPS_PER_SEGMENT * 4)
    fine = fly(baseline_configuration, profile).total_fuel

    assert fine == pytest.approx(coarse, rel=0.005)


# --------------------------------------------------------------- sizing


def test_sizing_converges_and_the_answer_is_pourable(baseline_configuration):
    mission = OneWayRangeMission(80_000.0)
    configuration, requirement = _sized(baseline_configuration, mission)

    assert requirement.iterations < 20
    assert requirement.mass > 0.0

    # Rounded up to a graduation, so the tank always holds at least the burn.
    flown = fly(configuration, mission.profile())
    assert flown.total_fuel <= requirement.mass
    assert flown.completed

    # And not rounded up by more than one graduation.
    assert requirement.mass - flown.total_fuel < mass_for_volume(GRADUATION_VOLUME)


def test_a_fuel_instruction_lands_on_a_graduation(baseline_configuration):
    """An instruction the pilot cannot pour is an instruction that is wrong."""
    _, requirement = _sized(baseline_configuration, OneWayRangeMission(37_123.0))

    graduations = requirement.volume / GRADUATION_VOLUME
    assert graduations == pytest.approx(round(graduations), abs=1e-6)


def test_a_longer_mission_never_needs_less_fuel(baseline_configuration):
    previous = 0.0
    for kilometres in (10, 25, 50, 100, 200):
        _, requirement = _sized(baseline_configuration, OneWayRangeMission(kilometres * 1000.0))

        assert requirement.mass > previous
        previous = requirement.mass


def test_more_time_on_station_never_needs_less_fuel(baseline_configuration):
    previous = 0.0
    for hours in (0.5, 1.0, 2.0, 4.0):
        _, requirement = _sized(
            baseline_configuration, LoiterMission(TEN_KILOMETRES, hours * ONE_HOUR)
        )

        assert requirement.mass > previous
        previous = requirement.mass


def test_more_payload_never_needs_less_fuel(baseline_configuration):
    mission = OneWayRangeMission(80_000.0)

    previous = 0.0
    for payload in (0.0, 2.0, 4.0, 8.0):
        _, requirement = _sized(replace(baseline_configuration, payload_mass=payload), mission)

        assert requirement.mass > previous
        previous = requirement.mass


def test_carrying_the_homeward_fuel_costs_extra_on_the_way_out(baseline_configuration):
    """A return trip is more than twice a one-way trip, not exactly twice.

    The outbound leg of a return trip is heavier, because it is carrying the
    fuel that will bring the aircraft home. Compared on burn rather than on
    the quantised tank figure, which at these small fuel loads is dominated by
    the graduation it was rounded to.
    """
    _, one_way = _sized(baseline_configuration, OneWayRangeMission(80_000.0))
    _, return_trip = _sized(baseline_configuration, ReturnRangeMission(80_000.0))

    outbound_alone = one_way.flight.outcomes[0].fuel_burned
    outbound_carrying_the_return = return_trip.flight.outcomes[0].fuel_burned

    assert outbound_carrying_the_return > outbound_alone
    assert return_trip.mass > one_way.mass


def test_an_impossible_mission_is_reported_not_refused(baseline_configuration):
    """No exception, no empty result. The gate decides what to do about it."""
    _, requirement = _sized(baseline_configuration, OneWayRangeMission(5_000_000.0))

    assert requirement.exceeds_capacity
    assert requirement.mass > requirement.capacity


def test_volume_follows_petrol_density():
    assert volume_for_mass(PETROL_DENSITY) == pytest.approx(1.0)
    assert volume_for_mass(0.72) * 1000.0 == pytest.approx(1.0, rel=1e-3)


def test_loiter_speed_is_slower_than_cruise_speed(baseline_configuration):
    mass = mass_properties(baseline_configuration).all_up_mass

    loiter = loiter_airspeed(baseline_configuration, mass, SEA_LEVEL_ISA).value
    cruise = cruise_airspeed(baseline_configuration, mass, SEA_LEVEL_ISA).value

    assert loiter < cruise
