"""The forward model: what will this aircraft do?

``analyze`` evaluates. It never solves for anything.

That rule is load-bearing. Two quantities in this project are found by
iteration -- the fuel mass needed for a requested duration, and the tail
extension needed for a target static margin. Both are inversions, and both
live in ``recommend``, expressed as repeated calls to this function. Keeping
them out means a ``Configuration`` arriving here is always fully determined,
which is what makes the forward model exhaustively testable without a solver
standing in the way.

BUILD STATE -- phase 2 complete
===============================
Mass, balance and the whole speed envelope are computed rather than invented.
Results carry ``Fidelity.PRELIMINARY``: the formulae are real and the geometry
is real, but two coefficients underneath them are not yet trustworthy.

The larger by far is fuel consumption, which is modelled at the engine's best
point while the aircraft actually cruises at around an eighth of full power.
Endurance and range are optimistic, probably by a factor of two or more, until
that curve is measured.
"""

from __future__ import annotations

from aerosizer.aero import drag_polar
from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere
from aerosizer.config import Configuration, Fidelity, Results
from aerosizer.mass import mass_properties
from aerosizer.performance import best_climb, speed_envelope
from aerosizer.stability import balance_of


def analyze(configuration: Configuration, atmosphere: Atmosphere = SEA_LEVEL_ISA) -> Results:
    """Evaluate one fully determined aircraft, in stated air."""
    mass = mass_properties(configuration)

    return Results(
        fidelity=Fidelity.PRELIMINARY,
        mass=mass,
        envelope=speed_envelope(configuration, mass.all_up_mass, atmosphere),
        climb=best_climb(configuration, mass.all_up_mass, atmosphere),
        balance=balance_of(configuration, mass),
        lift_to_drag_max=drag_polar(configuration).lift_to_drag_max,
    )
