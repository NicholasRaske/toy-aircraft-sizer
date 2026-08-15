"""The forward model: what will this aircraft do?

``analyze`` evaluates. It never solves for anything.

That rule is load-bearing. Two quantities in this project are found by
iteration -- the fuel mass needed for a requested duration, and the tail
extension needed for a target static margin. Both are inversions, and both
live in ``recommend``, expressed as repeated calls to this function. Keeping
them out means a ``Configuration`` arriving here is always fully determined,
which is what makes the forward model exhaustively testable without a solver
standing in the way.

BUILD STATE -- phase 2, step 2
==============================
Mass, centre of gravity and stall speed are now real. Everything else is still
a placeholder, shaped like the real thing so that ranking and rendering work
end to end, but not physics and not to be flown on:

    step 3  drag polar, the power-required curve, every other speed
    later   static margin and tail volumes, then tabulated polars and
            part-load fuel consumption

Results carry ``Fidelity.PLACEHOLDER`` until those land, and the assembly card
refuses to be quiet about it.
"""

from __future__ import annotations

import math

from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere
from aerosizer.config import (
    Balance,
    Configuration,
    Fidelity,
    Limited,
    Results,
    SpeedEnvelope,
)
from aerosizer.mass import mass_properties
from aerosizer.performance import minimum_safe_speed, stall_speed

# The Surveyor wing at its design point. Remaining placeholders are expressed
# relative to this reference so that swapping parts moves the answer in a
# physically sensible direction, even while the magnitudes are invented.
REFERENCE_ASPECT_RATIO = 9.0
REFERENCE_CRUISE_SPEED = 20.0
REFERENCE_MAX_LEVEL_SPEED = 30.0
REFERENCE_LIFT_TO_DRAG = 12.0

PLACEHOLDER_NEUTRAL_POINT_STATION = 0.70
PLACEHOLDER_STATIC_MARGIN = 0.12
PLACEHOLDER_HORIZONTAL_TAIL_VOLUME = 0.55
PLACEHOLDER_VERTICAL_TAIL_VOLUME = 0.035

LIMITED_BY_STALL_MARGIN = "stall margin"
NOT_YET_DERIVED = "placeholder"


def analyze(configuration: Configuration, atmosphere: Atmosphere = SEA_LEVEL_ISA) -> Results:
    """Evaluate one fully determined aircraft, in stated air."""
    mass = mass_properties(configuration)
    aspect_ratio_ratio = configuration.wing.aspect_ratio / REFERENCE_ASPECT_RATIO

    stall = stall_speed(mass.all_up_mass, configuration.wing, atmosphere)
    slowest_instructable = minimum_safe_speed(stall)

    # A longer, thinner wing is more efficient and slower flat out. The
    # exponents are invented, the directions are not.
    efficiency_ratio = math.sqrt(aspect_ratio_ratio)
    preferred_cruise = REFERENCE_CRUISE_SPEED
    preferred_loiter = REFERENCE_CRUISE_SPEED * 0.8

    return Results(
        fidelity=Fidelity.PLACEHOLDER,
        mass=mass,
        envelope=SpeedEnvelope(
            stall_speed=stall,
            min_power_speed=preferred_loiter,
            min_drag_speed=preferred_cruise,
            loiter_speed=_clipped_to_stall_margin(preferred_loiter, slowest_instructable),
            cruise_speed=_clipped_to_stall_margin(preferred_cruise, slowest_instructable),
            max_level_speed=Limited(
                value=REFERENCE_MAX_LEVEL_SPEED / aspect_ratio_ratio**0.25,
                limited_by=NOT_YET_DERIVED,
                margin=0.0,
            ),
        ),
        balance=Balance(
            neutral_point_station=PLACEHOLDER_NEUTRAL_POINT_STATION,
            static_margin=PLACEHOLDER_STATIC_MARGIN,
            horizontal_tail_volume=PLACEHOLDER_HORIZONTAL_TAIL_VOLUME,
            vertical_tail_volume=PLACEHOLDER_VERTICAL_TAIL_VOLUME,
        ),
        lift_to_drag_max=REFERENCE_LIFT_TO_DRAG * efficiency_ratio,
    )


def _clipped_to_stall_margin(preferred: float, slowest_instructable: float) -> Limited:
    """Never instruct a speed the aerodynamics like but the wing cannot hold."""
    if preferred < slowest_instructable:
        return Limited(
            value=slowest_instructable,
            limited_by=LIMITED_BY_STALL_MARGIN,
            margin=0.0,
        )
    return Limited(
        value=preferred,
        limited_by=NOT_YET_DERIVED,
        margin=preferred - slowest_instructable,
    )
