"""The forward model: what will this aircraft do?

``analyze`` evaluates. It never solves for anything.

That rule is load-bearing. Two quantities in this project are found by
iteration -- the fuel mass needed for a requested duration, and the tail
extension needed for a target static margin. Both are inversions, and both
live in ``recommend``, expressed as repeated calls to this function. Keeping
them out means a ``Configuration`` arriving here is always fully determined,
which is what makes the forward model exhaustively testable without a solver
standing in the way.

BUILD STATE -- phase 2, step 1
==============================
Every number below is a placeholder. They are shaped like the real thing so
that ranking and rendering can be exercised end to end, but they are not
physics and must not be flown on. Each is replaced in turn:

    step 2  all-up mass, centre of gravity, stall speed
    step 3  drag polar, the power-required curve, every speed in the envelope
    later   static margin and tail volumes, then tabulated polars and
            part-load fuel consumption

Results carry ``Fidelity.PLACEHOLDER`` until those land, and the assembly card
refuses to be quiet about it.
"""

from __future__ import annotations

import math

from aerosizer.config import (
    Balance,
    Configuration,
    Fidelity,
    Limited,
    MassProperties,
    Results,
    SpeedEnvelope,
)

# The Surveyor wing at its design point. Placeholder numbers are expressed
# relative to this reference so that swapping parts moves the answer in a
# physically sensible direction, even while the magnitudes are invented.
REFERENCE_WING_AREA = 1.6
REFERENCE_ASPECT_RATIO = 9.0

REFERENCE_STALL_SPEED = 12.0
REFERENCE_CRUISE_SPEED = 20.0
REFERENCE_MAX_LEVEL_SPEED = 30.0
REFERENCE_LIFT_TO_DRAG = 12.0

PLACEHOLDER_EMPTY_MASS = 15.4
PLACEHOLDER_CENTRE_OF_GRAVITY_STATION = 0.65
PLACEHOLDER_NEUTRAL_POINT_STATION = 0.70
PLACEHOLDER_STATIC_MARGIN = 0.12
PLACEHOLDER_HORIZONTAL_TAIL_VOLUME = 0.55
PLACEHOLDER_VERTICAL_TAIL_VOLUME = 0.035

# Until the power curve exists, no speed has a real reason for being what it
# is. Every Limited carries this rather than an invented constraint name.
NOT_YET_DERIVED = "placeholder"


def analyze(configuration: Configuration) -> Results:
    """Evaluate one fully determined aircraft."""
    wing = configuration.wing
    area_ratio = wing.reference_area / REFERENCE_WING_AREA
    aspect_ratio_ratio = wing.aspect_ratio / REFERENCE_ASPECT_RATIO

    # A bigger wing stalls slower; a longer, thinner wing is more efficient
    # and slower flat out. The exponents are invented, the directions are not.
    efficiency_ratio = math.sqrt(aspect_ratio_ratio)
    stall_speed = REFERENCE_STALL_SPEED / math.sqrt(area_ratio)
    cruise_speed = REFERENCE_CRUISE_SPEED
    max_level_speed = REFERENCE_MAX_LEVEL_SPEED / aspect_ratio_ratio**0.25

    return Results(
        fidelity=Fidelity.PLACEHOLDER,
        mass=_placeholder_mass(configuration),
        envelope=SpeedEnvelope(
            stall_speed=stall_speed,
            min_power_speed=cruise_speed * 0.76,
            min_drag_speed=cruise_speed,
            loiter_speed=_placeholder_limit(cruise_speed * 0.8),
            cruise_speed=_placeholder_limit(cruise_speed),
            max_level_speed=_placeholder_limit(max_level_speed),
        ),
        balance=Balance(
            neutral_point_station=PLACEHOLDER_NEUTRAL_POINT_STATION,
            static_margin=PLACEHOLDER_STATIC_MARGIN,
            horizontal_tail_volume=PLACEHOLDER_HORIZONTAL_TAIL_VOLUME,
            vertical_tail_volume=PLACEHOLDER_VERTICAL_TAIL_VOLUME,
        ),
        lift_to_drag_max=REFERENCE_LIFT_TO_DRAG * efficiency_ratio,
    )


def _placeholder_mass(configuration: Configuration) -> MassProperties:
    """Fuel and payload are real inputs; the rest waits for step 2."""
    empty_mass = PLACEHOLDER_EMPTY_MASS
    return MassProperties(
        all_up_mass=empty_mass + configuration.payload_mass + configuration.fuel_mass,
        empty_mass=empty_mass,
        fuel_mass=configuration.fuel_mass,
        payload_mass=configuration.payload_mass,
        centre_of_gravity_station=PLACEHOLDER_CENTRE_OF_GRAVITY_STATION,
    )


def _placeholder_limit(speed: float) -> Limited:
    return Limited(value=speed, limited_by=NOT_YET_DERIVED, margin=0.0)
