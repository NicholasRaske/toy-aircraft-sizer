"""The forward model: what will this aircraft do?

``analyze`` evaluates. It never solves for anything.

That rule is load-bearing. Two quantities in this project are found by
iteration -- the fuel mass needed for a requested duration, and the tail
extension needed for a target static margin. Both are inversions, and both
live in ``recommend``, expressed as repeated calls to this function. Keeping
them out means a ``Configuration`` arriving here is always fully determined,
which is what makes the forward model exhaustively testable without a solver
standing in the way.

BUILD STATE -- phase 2, step 3
==============================
Mass, balance and the whole speed envelope are now real, derived from a
component drag buildup and the power-required curve.

Only ``Balance`` remains invented, so results still carry
``Fidelity.PLACEHOLDER`` -- the card quotes a static margin, and quoting a made
up one loudly is better than quoting it quietly. It rises to ``PRELIMINARY``
when the neutral point lands, and to ``VALIDATED`` when tabulated polars and
part-load fuel consumption replace their stand-ins.
"""

from __future__ import annotations

from aerosizer.aero import drag_polar
from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere
from aerosizer.config import (
    Balance,
    Configuration,
    Fidelity,
    Results,
)
from aerosizer.mass import mass_properties
from aerosizer.performance import speed_envelope

PLACEHOLDER_NEUTRAL_POINT_STATION = 0.70
PLACEHOLDER_STATIC_MARGIN = 0.12
PLACEHOLDER_HORIZONTAL_TAIL_VOLUME = 0.55
PLACEHOLDER_VERTICAL_TAIL_VOLUME = 0.035


def analyze(configuration: Configuration, atmosphere: Atmosphere = SEA_LEVEL_ISA) -> Results:
    """Evaluate one fully determined aircraft, in stated air."""
    mass = mass_properties(configuration)

    return Results(
        fidelity=Fidelity.PLACEHOLDER,
        mass=mass,
        envelope=speed_envelope(configuration, mass.all_up_mass, atmosphere),
        balance=Balance(
            neutral_point_station=PLACEHOLDER_NEUTRAL_POINT_STATION,
            static_margin=PLACEHOLDER_STATIC_MARGIN,
            horizontal_tail_volume=PLACEHOLDER_HORIZONTAL_TAIL_VOLUME,
            vertical_tail_volume=PLACEHOLDER_VERTICAL_TAIL_VOLUME,
        ),
        lift_to_drag_max=drag_polar(configuration).lift_to_drag_max,
    )
