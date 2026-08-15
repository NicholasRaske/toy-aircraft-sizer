"""Fuel: the variable that makes this an aircraft-sizing problem.

Fuel burns off in flight, so the aircraft gets lighter and its centre of
gravity moves. This module owns the fuel itself: what it weighs, what volume
the pilot has to pour in to get that weight, and how much of it a stated
mission needs.

Sizing is a fixed point. Burn depends on mass, mass includes fuel, so the
answer has to be iterated -- but fuel is a small fraction of all-up mass here,
which makes the iteration strongly contractive and quick to settle.

There is no reserve. The number is what the mission costs and nothing more;
margin is the pilot's judgement, not ours. That is why it is reported as
mission fuel rather than as a fill instruction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere
from aerosizer.config import Configuration, FlightLog
from aerosizer.flight import fly
from aerosizer.mission import Segment

# Automotive petrol at typical field temperatures. Density varies by a few
# percent with temperature and blend; that is well inside the accuracy of
# everything else in the fuel path.
PETROL_DENSITY = 720.0

# The finest division a pilot can read off a graduated tank. Fuel is always
# rounded *up* to one of these: pouring a little more than the mission needs
# is a quantisation artefact, pouring a little less strands the aircraft.
#
# This is not a reserve. It is the resolution of the instruction.
GRADUATION_VOLUME = 0.05 / 1000.0

# One gram. Finer than any tank graduation a pilot can read.
CONVERGENCE_TOLERANCE = 0.001
MAXIMUM_ITERATIONS = 20


@dataclass(frozen=True)
class FuelRequirement:
    """What a mission costs, and whether the aircraft can carry it."""

    mass: float
    flight: FlightLog
    capacity: float
    iterations: int

    @property
    def volume(self) -> float:
        return volume_for_mass(self.mass)

    @property
    def exceeds_capacity(self) -> bool:
        return self.mass > self.capacity


def volume_for_mass(fuel_mass: float) -> float:
    """Cubic metres of petrol weighing ``fuel_mass`` kilograms."""
    return fuel_mass / PETROL_DENSITY


def mass_for_volume(fuel_volume: float) -> float:
    return fuel_volume * PETROL_DENSITY


def quantise_upward(fuel_mass: float) -> float:
    """Round a fuel mass up to the next graduation the pilot can pour to."""
    graduations = math.ceil(volume_for_mass(fuel_mass) / GRADUATION_VOLUME)
    return mass_for_volume(graduations * GRADUATION_VOLUME)


def size_fuel(
    configuration: Configuration,
    profile: tuple[Segment, ...],
    atmosphere: Atmosphere = SEA_LEVEL_ISA,
) -> FuelRequirement:
    """Find the fuel load that completes the profile.

    Starts from an empty tank and converges upward: each pass flies the
    profile at the previous pass's mass, and the fuel it burned becomes the
    next guess. Carrying more fuel costs a little more fuel, so the sequence
    increases and settles rather than oscillating.

    Converging from below means the fixed point is approached but never quite
    reached, so the settled figure is rounded up to a graduation before it is
    reported. That makes the instruction pourable and puts the residual on the
    safe side of the answer.
    """
    fuel_mass = 0.0
    iterations = 0

    for iterations in range(1, MAXIMUM_ITERATIONS + 1):
        burned = fly(replace(configuration, fuel_mass=fuel_mass), profile, atmosphere).total_fuel
        settled = abs(burned - fuel_mass) < CONVERGENCE_TOLERANCE
        fuel_mass = burned
        if settled:
            break

    fuel_mass = quantise_upward(fuel_mass)
    return FuelRequirement(
        mass=fuel_mass,
        flight=fly(replace(configuration, fuel_mass=fuel_mass), profile, atmosphere),
        capacity=configuration.fuselage.max_fuel_mass,
        iterations=iterations,
    )
