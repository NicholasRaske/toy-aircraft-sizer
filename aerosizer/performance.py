"""Performance: the speeds a configuration can actually fly.

Every speed here is found by searching the power-required curve rather than by
evaluating a closed-form equation. The closed forms exist, and are used as test
oracles, but they assume a parabolic polar and a constant propeller efficiency.
Both assumptions die when tabulated polars arrive. Searching a computed curve
survives that change without altering a single call site.

Searching also removes special cases. Two of the speeds an aircraft would like
to fly can fall below the speed at which its wing stops working -- clipping
them is then one operation applied twice, rather than a branch each.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from aerosizer.aero import DragPolar, drag_polar
from aerosizer.atmosphere import (
    SEA_LEVEL_ISA,
    Atmosphere,
    airspeed_for_lift_coefficient,
    dynamic_pressure,
    weight,
)
from aerosizer.config import ClimbPerformance, Configuration, Limited, SpeedEnvelope
from aerosizer.parts import Engine, Wing

# The margin over stall at which this class of aircraft is flown. Any speed
# the aerodynamics would prefer below this is clipped up to it.
STALL_MARGIN_FACTOR = 1.2

SEARCH_LOWEST_SPEED = 1.0
SEARCH_HIGHEST_SPEED = 200.0
SEARCH_TOLERANCE = 1e-5

LIMITED_BY_STALL_MARGIN = "stall margin"
LIMITED_BY_MINIMUM_POWER = "minimum power"
LIMITED_BY_MINIMUM_DRAG = "minimum drag"
LIMITED_BY_EXCESS_POWER = "excess power"
LIMITED_BY_ENGINE_POWER = "engine power"
LIMITED_BY_INSUFFICIENT_POWER = "insufficient power"

_GOLDEN_SECTION = (math.sqrt(5.0) - 1.0) / 2.0


def stall_speed(mass: float, wing: Wing, atmosphere: Atmosphere) -> float:
    """Slowest speed at which the wing can still carry the aircraft.

    Scales with the square root of mass, so the envelope is narrowest at
    takeoff and widens as fuel burns.
    """
    return airspeed_for_lift_coefficient(
        lift=weight(mass),
        reference_area=wing.reference_area,
        lift_coefficient=wing.max_lift_coefficient,
        atmosphere=atmosphere,
    )


def minimum_safe_speed(stall: float) -> float:
    """The slowest speed we will ever instruct, whatever the aerodynamics say."""
    return STALL_MARGIN_FACTOR * stall


def power_required(
    polar: DragPolar,
    mass: float,
    atmosphere: Atmosphere,
    airspeed: float,
) -> float:
    """Power needed to hold level flight at a speed.

    Written as lift coefficient, then drag coefficient, then drag times speed,
    rather than as the expanded algebraic form. Slower, and the only version
    that still works once the polar stops being parabolic.
    """
    pressure = dynamic_pressure(atmosphere, airspeed)
    lift_coefficient = weight(mass) / (pressure * polar.reference_area)
    drag = pressure * polar.reference_area * polar.drag_coefficient(lift_coefficient)
    return drag * airspeed


def power_available(engine: Engine, atmosphere: Atmosphere) -> float:
    """Thrust power at the propeller, falling with air density."""
    density_ratio = atmosphere.density / SEA_LEVEL_ISA.density
    return engine.max_shaft_power * engine.propeller_efficiency * density_ratio


def speed_envelope(
    configuration: Configuration,
    mass: float,
    atmosphere: Atmosphere,
) -> SpeedEnvelope:
    """Every speed of interest for one configuration at one mass."""
    polar = drag_polar(configuration)
    stall = stall_speed(mass, configuration.wing, atmosphere)
    slowest_instructable = minimum_safe_speed(stall)

    def power_at(airspeed: float) -> float:
        return power_required(polar, mass, atmosphere, airspeed)

    min_power = minimum_power_speed(polar, mass, atmosphere)
    min_drag = minimum_drag_speed(polar, mass, atmosphere)

    return SpeedEnvelope(
        stall_speed=stall,
        min_power_speed=min_power,
        min_drag_speed=min_drag,
        loiter_speed=_clipped_to_stall_margin(
            min_power, slowest_instructable, LIMITED_BY_MINIMUM_POWER
        ),
        cruise_speed=_clipped_to_stall_margin(
            min_drag, slowest_instructable, LIMITED_BY_MINIMUM_DRAG
        ),
        max_level_speed=_maximum_level_speed(
            power_at,
            min_power,
            power_available(configuration.engine, atmosphere),
            slowest_instructable,
        ),
    )


def minimum_power_speed(polar: DragPolar, mass: float, atmosphere: Atmosphere) -> float:
    """Where the aircraft stays airborne most cheaply per second."""
    return _minimise(lambda airspeed: power_required(polar, mass, atmosphere, airspeed))


def minimum_drag_speed(polar: DragPolar, mass: float, atmosphere: Atmosphere) -> float:
    """Where the aircraft stays airborne most cheaply per metre."""
    return _minimise(
        lambda airspeed: power_required(polar, mass, atmosphere, airspeed) / airspeed
    )


def loiter_airspeed(
    configuration: Configuration,
    mass: float,
    atmosphere: Atmosphere,
) -> Limited:
    """The speed to hold station at, respecting stall margin.

    Separate from ``speed_envelope`` because flying a mission needs one speed
    per sub-step, and searching for the others would double the work for
    nothing.
    """
    polar = drag_polar(configuration)
    slowest = minimum_safe_speed(stall_speed(mass, configuration.wing, atmosphere))
    return _clipped_to_stall_margin(
        minimum_power_speed(polar, mass, atmosphere), slowest, LIMITED_BY_MINIMUM_POWER
    )


def cruise_airspeed(
    configuration: Configuration,
    mass: float,
    atmosphere: Atmosphere,
) -> Limited:
    """The speed to cover ground at, respecting stall margin."""
    polar = drag_polar(configuration)
    slowest = minimum_safe_speed(stall_speed(mass, configuration.wing, atmosphere))
    return _clipped_to_stall_margin(
        minimum_drag_speed(polar, mass, atmosphere), slowest, LIMITED_BY_MINIMUM_DRAG
    )


def best_climb(
    configuration: Configuration,
    mass: float,
    atmosphere: Atmosphere,
) -> ClimbPerformance:
    """Best rate of climb, from whatever power is left over after level flight.

    Note that the speed for best climb comes out identical to the minimum
    power speed. That is not a coincidence or a bug: with propeller efficiency
    modelled as constant, power available does not vary with airspeed, so the
    greatest excess is wherever the requirement is least. The two speeds
    separate once efficiency becomes a function of airspeed.
    """
    polar = drag_polar(configuration)
    available = power_available(configuration.engine, atmosphere)
    slowest = minimum_safe_speed(stall_speed(mass, configuration.wing, atmosphere))

    speed = _clipped_to_stall_margin(
        minimum_power_speed(polar, mass, atmosphere), slowest, LIMITED_BY_EXCESS_POWER
    )
    excess = available - power_required(polar, mass, atmosphere, speed.value)

    return ClimbPerformance(
        best_rate=excess / weight(mass),
        speed_for_best_rate=speed,
    )


def _clipped_to_stall_margin(
    preferred: float,
    slowest_instructable: float,
    reason_when_unclipped: str,
) -> Limited:
    """Never instruct a speed the aerodynamics prefer but the wing cannot hold.

    ``margin`` is how far the speed sits above the slowest we would instruct.
    A clipped speed has none, which is exactly what makes it worth reporting.
    """
    if preferred < slowest_instructable:
        return Limited(
            value=slowest_instructable,
            limited_by=LIMITED_BY_STALL_MARGIN,
            margin=0.0,
        )
    return Limited(
        value=preferred,
        limited_by=reason_when_unclipped,
        margin=preferred - slowest_instructable,
    )


def _maximum_level_speed(
    power_at: Callable[[float], float],
    min_power_speed: float,
    available: float,
    slowest_instructable: float,
) -> Limited:
    """Where power required meets power available."""
    if power_at(min_power_speed) >= available:
        # Level flight is impossible at any speed. Reported rather than
        # refused; excluding such a configuration is the gate's job.
        return Limited(
            value=slowest_instructable,
            limited_by=LIMITED_BY_INSUFFICIENT_POWER,
            margin=0.0,
        )

    top_speed = _find_crossing(
        lambda airspeed: power_at(airspeed) - available,
        lower=min_power_speed,
        upper=SEARCH_HIGHEST_SPEED,
    )
    return Limited(
        value=top_speed,
        limited_by=LIMITED_BY_ENGINE_POWER,
        margin=top_speed - slowest_instructable,
    )


def _minimise(
    function: Callable[[float], float],
    lower: float = SEARCH_LOWEST_SPEED,
    upper: float = SEARCH_HIGHEST_SPEED,
) -> float:
    """Golden-section search for the minimum of a unimodal function.

    Power required and drag are both unimodal in airspeed -- induced drag
    dominates below the minimum, parasite drag above it -- so this converges
    without a derivative or a starting guess.
    """
    while upper - lower > SEARCH_TOLERANCE:
        span = (upper - lower) * _GOLDEN_SECTION
        left, right = upper - span, lower + span
        if function(left) < function(right):
            upper = right
        else:
            lower = left
    return 0.5 * (lower + upper)


def _find_crossing(
    function: Callable[[float], float],
    lower: float,
    upper: float,
) -> float:
    """Bisect for the zero of a function that rises through it."""
    while upper - lower > SEARCH_TOLERANCE:
        middle = 0.5 * (lower + upper)
        if function(middle) < 0.0:
            lower = middle
        else:
            upper = middle
    return 0.5 * (lower + upper)
