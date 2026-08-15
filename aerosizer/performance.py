"""Performance: the speeds a configuration can actually fly.

BUILD STATE -- phase 2, step 2
==============================
Only the stall speed is real. It is the foundation the rest of the envelope
rests on, because several speeds turn out to be limited by stall margin rather
than by the aerodynamic optimum they are named after.

The power-required curve, and every speed read off it, arrives at step 3.
"""

from __future__ import annotations

from aerosizer.atmosphere import Atmosphere, airspeed_for_lift_coefficient, weight
from aerosizer.parts import Wing

# The margin over stall at which this class of aircraft is flown. Any speed
# the aerodynamics would prefer below this is clipped up to it.
STALL_MARGIN_FACTOR = 1.2


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
