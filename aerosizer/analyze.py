"""The forward model: what will this aircraft do?

``analyze`` evaluates. It never solves for anything.

That rule is load-bearing. Two quantities in this project are found by
iteration -- the fuel mass needed for a requested duration, and the tail
extension needed for a target static margin. Both are inversions, and both
live in ``recommend``, expressed as repeated calls to this function. Keeping
them out means a ``Configuration`` arriving here is always fully determined,
which is what makes the forward model exhaustively testable without a solver
standing in the way.

BUILD STATE -- B1
=================
Every number below is a placeholder. They are shaped like the real thing so
that ranking, tie-breaking and rendering can be exercised end to end, but they
are not physics and must not be flown on. Each one is replaced in turn:

    B2  stall speed, all-up mass, centre of gravity
    B3  drag polar, lift-to-drag, endurance, range, speeds
    T2  static margin, tail volumes
    T5  part-load fuel consumption, tabulated polars, real atmosphere

Results carry ``Fidelity.PLACEHOLDER`` until those land, and the assembly card
refuses to be quiet about it.
"""

from __future__ import annotations

import math

from aerosizer.config import Configuration, Fidelity, Results

# The Surveyor wing at its design point. Placeholder numbers are expressed
# relative to this reference so that swapping parts moves the answer in a
# physically sensible direction, even while the magnitudes are invented.
REFERENCE_WING_AREA = 1.6
REFERENCE_ASPECT_RATIO = 9.0

REFERENCE_STALL_SPEED = 12.0
REFERENCE_CRUISE_SPEED = 20.0
REFERENCE_MAX_LEVEL_SPEED = 30.0
REFERENCE_LIFT_TO_DRAG = 12.0
REFERENCE_ENDURANCE = 3600.0
REFERENCE_RATE_OF_CLIMB = 4.0

PLACEHOLDER_ALL_UP_MASS = 20.0
PLACEHOLDER_CENTRE_OF_GRAVITY_STATION = 0.65
PLACEHOLDER_STATIC_MARGIN = 0.12
PLACEHOLDER_HORIZONTAL_TAIL_VOLUME = 0.55
PLACEHOLDER_VERTICAL_TAIL_VOLUME = 0.035


def analyze(configuration: Configuration) -> Results:
    """Evaluate one fully determined aircraft."""
    area_ratio = configuration.wing.reference_area / REFERENCE_WING_AREA
    aspect_ratio_ratio = configuration.wing.aspect_ratio / REFERENCE_ASPECT_RATIO

    # A bigger wing stalls slower; a longer, thinner wing is more efficient
    # and slower flat out. The exponents are invented, the directions are not.
    stall_speed = REFERENCE_STALL_SPEED / math.sqrt(area_ratio)
    efficiency_ratio = math.sqrt(aspect_ratio_ratio)
    endurance = REFERENCE_ENDURANCE * efficiency_ratio
    cruise_speed = REFERENCE_CRUISE_SPEED

    return Results(
        fidelity=Fidelity.PLACEHOLDER,
        all_up_mass=PLACEHOLDER_ALL_UP_MASS,
        centre_of_gravity_station=PLACEHOLDER_CENTRE_OF_GRAVITY_STATION,
        stall_speed=stall_speed,
        cruise_speed=cruise_speed,
        max_level_speed=REFERENCE_MAX_LEVEL_SPEED / aspect_ratio_ratio**0.25,
        lift_to_drag_max=REFERENCE_LIFT_TO_DRAG * efficiency_ratio,
        endurance=endurance,
        still_air_range=endurance * cruise_speed,
        rate_of_climb=REFERENCE_RATE_OF_CLIMB,
        static_margin=PLACEHOLDER_STATIC_MARGIN,
        horizontal_tail_volume=PLACEHOLDER_HORIZONTAL_TAIL_VOLUME,
        vertical_tail_volume=PLACEHOLDER_VERTICAL_TAIL_VOLUME,
    )
