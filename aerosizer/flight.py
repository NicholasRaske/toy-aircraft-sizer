"""Flying a mission profile, segment by segment.

The aircraft gets lighter as it burns fuel, and the speed it wants to fly goes
as the square root of its weight. So a profile cannot be evaluated in one shot:
the outbound leg is flown faster and thirstier than the return, and the numbers
have to be marched.

Marching is not a convenience here, it is a requirement. The closed-form
Breguet equations assume a constant specific fuel consumption, and the
load-dependent fuel curve that this class of engine actually has will destroy
that assumption. Stepping through the profile survives it.

``fly`` never refuses. It computes what the profile would cost and reports
whether the fuel aboard covered it. Deciding what to do about a shortfall
belongs to the caller.
"""

from __future__ import annotations

from aerosizer.aero import DragPolar, drag_polar
from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere
from aerosizer.config import Configuration, FlightLog, SegmentOutcome
from aerosizer.mass import mass_properties
from aerosizer.mission import CruiseSegment, LoiterSegment, Segment
from aerosizer.parts import Engine
from aerosizer.performance import loiter_airspeed, power_required, speed_envelope

# Sub-steps per segment. Enough that the mass change within a step is small
# compared with the mass itself; convergence against a finer step is tested.
SUB_STEPS_PER_SEGMENT = 20


def fuel_flow(
    polar: DragPolar,
    engine: Engine,
    mass: float,
    atmosphere: Atmosphere,
    airspeed: float,
) -> float:
    """Kilograms of fuel per second, holding level flight at a speed."""
    thrust_power = power_required(polar, mass, atmosphere, airspeed)
    shaft_power = thrust_power / engine.propeller_efficiency
    return engine.best_specific_fuel_consumption * shaft_power


def fly(
    configuration: Configuration,
    profile: tuple[Segment, ...],
    atmosphere: Atmosphere = SEA_LEVEL_ISA,
) -> FlightLog:
    """Fly a profile and report what each segment cost."""
    polar = drag_polar(configuration)
    mass = mass_properties(configuration).all_up_mass
    dry_mass = mass - configuration.fuel_mass

    outcomes = []
    for segment in profile:
        outcome = _fly_segment(configuration, polar, segment, mass, dry_mass, atmosphere)
        outcomes.append(outcome)
        mass = outcome.mass_at_end

    return FlightLog(outcomes=tuple(outcomes), fuel_aboard=configuration.fuel_mass)


def _fly_segment(
    configuration: Configuration,
    polar: DragPolar,
    segment: Segment,
    mass_at_start: float,
    dry_mass: float,
    atmosphere: Atmosphere,
) -> SegmentOutcome:
    mass = mass_at_start
    elapsed = 0.0
    covered = 0.0
    burned = 0.0
    speed_sum = 0.0

    for _ in range(SUB_STEPS_PER_SEGMENT):
        airspeed = _airspeed_for(configuration, segment, mass, atmosphere)
        step_duration = _step_duration(segment, airspeed)
        flow = fuel_flow(polar, configuration.engine, mass, atmosphere, airspeed)
        step_fuel = flow * step_duration

        elapsed += step_duration
        covered += airspeed * step_duration
        burned += step_fuel
        speed_sum += airspeed

        # The aerodynamic mass never falls below the dry aircraft, even while
        # the fuel demand keeps accumulating. That keeps the sizing loop in
        # fuel.py well behaved when it starts from an empty tank.
        mass = max(mass - step_fuel, dry_mass)

    return SegmentOutcome(
        segment=segment,
        airspeed=speed_sum / SUB_STEPS_PER_SEGMENT,
        duration=elapsed,
        distance=covered,
        fuel_burned=burned,
        mass_at_start=mass_at_start,
        mass_at_end=mass,
    )


def _airspeed_for(
    configuration: Configuration,
    segment: Segment,
    mass: float,
    atmosphere: Atmosphere,
) -> float:
    """Cover ground as cheaply per metre; hold station as cheaply per second.

    A cruise segment carrying a deadline overrides the cheap answer with a
    faster one, capped at what the aircraft can actually sustain in level
    flight. Where the cap binds, the leg simply takes longer than asked.
    """
    if isinstance(segment, CruiseSegment):
        envelope = speed_envelope(configuration, mass, atmosphere)
        wanted = max(envelope.cruise_speed.value, segment.required_speed)
        return min(wanted, envelope.max_level_speed.value)
    return loiter_airspeed(configuration, mass, atmosphere).value


def _step_duration(segment: Segment, airspeed: float) -> float:
    if isinstance(segment, CruiseSegment):
        return (segment.distance / SUB_STEPS_PER_SEGMENT) / airspeed
    if isinstance(segment, LoiterSegment):
        return segment.duration / SUB_STEPS_PER_SEGMENT
    raise TypeError(f"Cannot fly an unknown segment type: {type(segment).__name__}")
